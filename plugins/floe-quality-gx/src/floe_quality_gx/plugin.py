"""Great Expectations QualityPlugin implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from floe_core.schemas.quality_config import Dimension, QualityConfig, QualityGates

if TYPE_CHECKING:
    from pydantic import BaseModel

SUPPORTED_DIALECTS = {"duckdb", "postgresql", "snowflake"}


class GreatExpectationsPlugin(QualityPlugin):
    """Great Expectations implementation of QualityPlugin."""

    @property
    def name(self) -> str:
        return "great_expectations"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def description(self) -> str:
        return "Great Expectations data quality plugin for the floe data platform"

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
        # TODO: Implement gate validation
        return GateResult(
            passed=True,
            tier="bronze",
            coverage_actual=0.0,
            coverage_required=0.0,
        )

    def run_checks(
        self,
        suite_name: str,
        data_source: str,
        options: dict[str, Any] | None = None,
    ) -> QualitySuiteResult:
        # TODO: Implement using Great Expectations
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
        # TODO: Implement using Great Expectations
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
        # TODO: Implement using Great Expectations
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

        Returns HEALTHY if Great Expectations can be imported.
        """
        try:
            import great_expectations  # noqa: F401

            return HealthStatus(
                state=HealthState.HEALTHY,
                message="Great Expectations is available",
                details={"gx_available": True},
            )
        except ImportError:
            return HealthStatus(
                state=HealthState.UNHEALTHY,
                message="Great Expectations is not installed",
                details={"gx_available": False},
            )

    def get_config_schema(self) -> type[BaseModel]:
        """Return QualityConfig as the configuration schema (FR-010)."""
        return QualityConfig
