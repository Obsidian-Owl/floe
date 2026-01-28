"""dbt-expectations QualityPlugin implementation."""

from __future__ import annotations

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
        # TODO: Implement using dbt-expectations via DBTPlugin
        return QualitySuiteResult(
            suite_name=suite_name,
            model_name=data_source,
            passed=True,
            checks=[],
        )

    def run_suite(
        self,
        suite: QualitySuite,
        connection_config: dict[str, Any],
    ) -> QualitySuiteResult:
        # TODO: Implement using dbt-expectations via DBTPlugin
        return QualitySuiteResult(
            suite_name=f"{suite.model_name}_suite",
            model_name=suite.model_name,
            passed=True,
            checks=[],
        )

    def validate_expectations(
        self,
        data_source: str,
        expectations: list[dict[str, Any]],
    ) -> list[QualityCheckResult]:
        # TODO: Implement using dbt-expectations
        return []

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
