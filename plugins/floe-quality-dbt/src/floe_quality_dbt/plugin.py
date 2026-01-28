"""dbt-expectations QualityPlugin implementation."""

from __future__ import annotations

from typing import Any

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
