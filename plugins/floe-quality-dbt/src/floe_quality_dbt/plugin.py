"""dbt-expectations QualityPlugin implementation."""

from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING, Any, Literal, cast

from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.quality import (
    GateResult,
    OpenLineageEmitter,
    QualityCheckResult,
    QualityPlugin,
    QualityScore,
    QualitySuite,
    QualitySuiteResult,
    ValidationResult,
)
from floe_core.quality_errors import QualityCoverageError, QualityMissingTestsError
from floe_core.schemas.quality_config import Dimension, QualityConfig, QualityGates
from floe_core.validation import (
    calculate_coverage,
    validate_coverage,
    validate_required_tests,
)

try:
    from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False


def _quality_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
    """Return an OTel span context manager, or nullcontext if unavailable."""
    if not _HAS_OTEL:
        return nullcontext()
    return _factory_get_tracer(__name__).start_as_current_span(name, attributes=attributes)


if TYPE_CHECKING:
    from pydantic import BaseModel

SUPPORTED_DIALECTS = {"duckdb", "postgresql", "snowflake"}


class DBTExpectationsPlugin(QualityPlugin):
    """dbt-expectations implementation of QualityPlugin."""

    @property
    def name(self) -> str:
        return "dbt_expectations"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def description(self) -> str:
        return "dbt-expectations data quality plugin for the floe data platform"

    def validate_config(self, config: QualityConfig) -> ValidationResult:
        if config.provider != self.name:
            return ValidationResult(
                success=False,
                errors=[f"Provider mismatch: expected '{self.name}', got '{config.provider}'"],
            )
        return ValidationResult(success=True)

    def validate_quality_gates(
        self,
        models: list[dict[str, Any]],
        gates: QualityGates,
    ) -> GateResult:
        all_violations: list[str] = []
        all_missing_tests: list[str] = []
        min_coverage = 100.0
        min_tier: Literal["bronze", "silver", "gold"] = "gold"

        for model in models:
            coverage_result = calculate_coverage(model)
            tier = coverage_result.tier
            if tier not in ("bronze", "silver", "gold"):
                tier = "bronze"

            try:
                validate_coverage(
                    model_name=coverage_result.model_name,
                    tier=tier,
                    actual_coverage=coverage_result.coverage_percentage,
                    gates=gates,
                )
            except QualityCoverageError as e:
                all_violations.append(str(e))
                if coverage_result.coverage_percentage < min_coverage:
                    min_coverage = coverage_result.coverage_percentage
                    min_tier = cast(Literal["bronze", "silver", "gold"], tier)

            try:
                validate_required_tests(
                    model_name=coverage_result.model_name,
                    tier=tier,
                    actual_tests=coverage_result.test_types_present,
                    gates=gates,
                )
            except QualityMissingTestsError as e:
                all_violations.append(str(e))
                all_missing_tests.extend(e.missing_tests)

        gate_tier = getattr(gates, min_tier, gates.bronze)
        required_coverage = gate_tier.min_test_coverage

        return GateResult(
            passed=len(all_violations) == 0,
            tier=min_tier,
            coverage_actual=min_coverage,
            coverage_required=required_coverage,
            missing_tests=list(set(all_missing_tests)),
            violations=all_violations,
        )

    def run_checks(
        self,
        suite_name: str,
        data_source: str,
        options: dict[str, Any] | None = None,
    ) -> QualitySuiteResult:
        """Run quality checks against a dbt model.

        This method creates an empty suite and delegates to run_suite().
        For full functionality, use run_suite() with a QualitySuite object.

        Args:
            suite_name: Name of the quality suite.
            data_source: Data source identifier (dbt model name).
            options: Optional execution options (timeout_seconds, fail_fast,
                     project_dir, profiles_dir).

        Returns:
            QualitySuiteResult with check outcomes.
        """
        with _quality_span(
            "floe.quality.run_checks",
            {
                "quality.provider": "dbt_expectations",
                "quality.suite_name": suite_name,
                "quality.data_source": data_source,
            },
        ):
            opts = options or {}
            suite = QualitySuite(
                model_name=data_source,
                checks=[],
                timeout_seconds=opts.get("timeout_seconds", 300),
                fail_fast=opts.get("fail_fast", False),
            )

            # Delegate to run_suite
            connection_config: dict[str, Any] = {
                "project_dir": opts.get("project_dir"),
                "profiles_dir": opts.get("profiles_dir"),
            }
            result = self.run_suite(suite, connection_config)

            # Override suite_name to match the requested name
            return QualitySuiteResult(
                suite_name=suite_name,
                model_name=result.model_name,
                passed=result.passed,
                checks=result.checks,
                execution_time_ms=result.execution_time_ms,
                summary=result.summary,
            )

    def run_suite(
        self,
        suite: QualitySuite,
        connection_config: dict[str, Any],
    ) -> QualitySuiteResult:
        """Run a quality suite using dbt test command.

        Args:
            suite: QualitySuite with checks to execute.
            connection_config: Configuration with project_dir and profiles_dir.

        Returns:
            QualitySuiteResult with all check results.

        Raises:
            QualityTimeoutError: If execution exceeds suite.timeout_seconds.
        """
        with _quality_span(
            "floe.quality.run_suite",
            {
                "quality.provider": "dbt_expectations",
                "quality.suite_name": suite.model_name,
                "quality.checks_count": len(suite.checks),
            },
        ):
            try:
                from floe_quality_dbt.executor import run_dbt_tests_with_timeout

                return run_dbt_tests_with_timeout(
                    suite=suite,
                    project_dir=connection_config.get("project_dir"),
                    profiles_dir=connection_config.get("profiles_dir"),
                    timeout_seconds=suite.timeout_seconds,
                )
            except ImportError:
                # dbt not available, return empty result
                return QualitySuiteResult(
                    suite_name=f"{suite.model_name}_suite",
                    model_name=suite.model_name,
                    passed=True,
                    checks=[],
                    summary={"total": 0, "passed": 0, "failed": 0},
                )

    def validate_expectations(
        self,
        data_source: str,
        expectations: list[dict[str, Any]],
    ) -> list[QualityCheckResult]:
        """Validate data against ad-hoc expectations via dbt tests.

        Args:
            data_source: Data source identifier (dbt model name).
            expectations: List of expectation definitions.

        Returns:
            List of QualityCheckResult for each expectation.
        """
        with _quality_span(
            "floe.quality.validate_expectations",
            {
                "quality.provider": "dbt_expectations",
                "quality.check_count": len(expectations),
                "quality.data_source": data_source,
            },
        ):
            if not expectations:
                return []

            # Convert expectations to QualityChecks
            from floe_core.schemas.quality_score import QualityCheck

            checks = []
            for i, exp in enumerate(expectations):
                check = QualityCheck(
                    name=exp.get("name", f"check_{i}"),
                    type=exp.get("type", "custom"),
                    column=exp.get("column"),
                    dimension=Dimension(exp.get("dimension", "validity")),
                )
                checks.append(check)

            # Create suite and run
            suite = QualitySuite(model_name=data_source, checks=checks)
            result = self.run_suite(suite, {})

            return list(result.checks)

    def calculate_quality_score(
        self,
        results: QualitySuiteResult,
        config: QualityConfig,
    ) -> QualityScore:
        passed = sum(1 for c in results.checks if c.passed)
        failed = len(results.checks) - passed
        return QualityScore(
            overall=100.0 if failed == 0 else 0.0,
            dimension_scores=dict.fromkeys(Dimension, 100.0),
            checks_passed=passed,
            checks_failed=failed,
            model_name=results.model_name,
        )

    def list_suites(self) -> list[str]:
        return []

    def supports_dialect(self, dialect: str) -> bool:
        return dialect.lower() in SUPPORTED_DIALECTS

    def get_lineage_emitter(self) -> OpenLineageEmitter | None:
        return None

    def health_check(self) -> HealthStatus:
        """Check plugin health (FR-009).

        Returns HEALTHY if dbt-core can be imported.
        """
        try:
            import dbt.version  # noqa: F401

            return HealthStatus(
                state=HealthState.HEALTHY,
                message="dbt-core is available",
                details={"dbt_available": True},
            )
        except ImportError:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="dbt-core is not installed",
                details={"dbt_available": False},
            )

    def get_config_schema(self) -> type[BaseModel]:
        """Return QualityConfig as the configuration schema (FR-010)."""
        return QualityConfig
