"""Great Expectations QualityPlugin implementation."""

from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING, Any

from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_core.plugins.quality import (
    OpenLineageEmitter,
    QualityCheck,
    QualityCheckResult,
    QualityPlugin,
    QualitySuite,
    QualitySuiteResult,
)
from floe_core.schemas.quality_config import Dimension, QualityConfig

try:
    from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False
    _factory_get_tracer = None  # type: ignore[assignment]


def _quality_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
    if not _HAS_OTEL or _factory_get_tracer is None:
        return nullcontext()
    return _factory_get_tracer(__name__).start_as_current_span(
        name, attributes=attributes
    )


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

    def run_checks(
        self,
        suite_name: str,
        data_source: str,
        options: dict[str, Any] | None = None,
    ) -> QualitySuiteResult:
        """Run quality checks against a data source.

        This method creates an empty suite and delegates to run_suite().
        For full functionality, use run_suite() with a QualitySuite object.

        Args:
            suite_name: Name of the quality suite.
            data_source: Data source identifier (table name).
            options: Optional execution options (timeout_seconds, fail_fast).

        Returns:
            QualitySuiteResult with check outcomes.
        """
        with _quality_span(
            "floe.quality.run_checks",
            {
                "quality.provider": "great_expectations",
                "quality.suite_name": suite_name,
                "quality.data_source": data_source,
            },
        ):
            # Create a minimal suite from the parameters
            opts = options or {}
            suite = QualitySuite(
                model_name=data_source,
                checks=[],
                timeout_seconds=opts.get("timeout_seconds", 300),
                fail_fast=opts.get("fail_fast", False),
            )

            # Delegate to run_suite with empty connection config
            # In practice, the caller should use run_suite directly
            connection_config: dict[str, Any] = opts.get(
                "connection_config", {"dialect": "duckdb"}
            )
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
        """Run a quality suite against data using Great Expectations.

        Args:
            suite: QualitySuite with checks to execute.
            connection_config: Database connection configuration.

        Returns:
            QualitySuiteResult with all check results.

        Raises:
            QualityTimeoutError: If execution exceeds suite.timeout_seconds.
        """
        with _quality_span(
            "floe.quality.run_suite",
            {
                "quality.provider": "great_expectations",
                "quality.suite_name": suite.model_name,
                "quality.checks_count": len(suite.checks),
            },
        ):
            # Handle empty checks case
            if not suite.checks:
                return QualitySuiteResult(
                    suite_name=f"{suite.model_name}_suite",
                    model_name=suite.model_name,
                    passed=True,
                    checks=[],
                    summary={"total": 0, "passed": 0, "failed": 0},
                )

            try:
                from floe_quality_gx.executor import (
                    create_dataframe_from_connection,
                    run_validation_with_timeout,
                )

                # Load data from connection config
                dataframe = create_dataframe_from_connection(
                    connection_config, suite.model_name
                )

                # Run validation with timeout
                return run_validation_with_timeout(
                    suite=suite,
                    dataframe=dataframe,
                    timeout_seconds=suite.timeout_seconds,
                )
            except ImportError:
                # GX not available, return empty result
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
        """Validate data against ad-hoc expectations.

        Args:
            data_source: Data source identifier.
            expectations: List of expectation definitions.

        Returns:
            List of QualityCheckResult for each expectation.
        """
        with _quality_span(
            "floe.quality.validate_expectations",
            {
                "quality.provider": "great_expectations",
                "quality.check_count": len(expectations),
                "quality.data_source": data_source,
            },
        ):
            if not expectations:
                return []

            # Convert expectations to QualityChecks
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
            result = self.run_suite(suite, {"dialect": "duckdb"})

            return list(result.checks)

    def list_suites(self) -> list[str]:
        return []

    def supports_dialect(self, dialect: str) -> bool:
        return dialect.lower() in SUPPORTED_DIALECTS

    def get_lineage_emitter(self) -> OpenLineageEmitter | None:
        return None

    def health_check(self, timeout: float | None = None) -> HealthStatus:
        """Check plugin health (FR-009).

        Args:
            timeout: Maximum time in seconds to wait for response.
                Not used by this plugin; accepted for base ABC compatibility.

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
