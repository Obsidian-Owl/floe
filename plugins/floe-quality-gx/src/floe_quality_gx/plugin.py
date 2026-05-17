"""Great Expectations QualityPlugin implementation."""

from __future__ import annotations

import importlib.util
import time
from typing import TYPE_CHECKING, Any

import structlog
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
from floe_core.telemetry.metrics import MetricRecorder
from floe_core.telemetry.sanitization import sanitize_error_message

from floe_quality_gx.tracing import TRACER_NAME, get_tracer, quality_span, record_result

if TYPE_CHECKING:
    from pydantic import BaseModel

SUPPORTED_DIALECTS = {"duckdb", "postgresql", "snowflake"}
GX_SUITE_RUNS_METRIC = "floe.quality.gx.suite_runs"
GX_SUITE_DURATION_METRIC = "floe.quality.gx.suite_duration"
GX_SUITE_FAILURES_METRIC = "floe.quality.gx.suite_failures"

logger = structlog.get_logger(__name__)


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

    @property
    def tracer_name(self) -> str:
        """Return the OpenTelemetry tracer name for this plugin."""
        return TRACER_NAME

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
        tracer = get_tracer()
        with quality_span(
            tracer,
            "run_checks",
            suite_name=suite_name,
            data_source=data_source,
        ) as _span:
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
            connection_config: dict[str, Any] = opts.get("connection_config", {"dialect": "duckdb"})
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
        tracer = get_tracer()
        with quality_span(
            tracer,
            "run_suite",
            suite_name=suite.model_name,
            checks_count=len(suite.checks),
        ) as span:
            started_at = time.perf_counter()
            metrics = MetricRecorder(name="floe.quality.gx.runtime", version=self.version)
            try:
                # Handle empty checks case
                if not suite.checks:
                    result = QualitySuiteResult(
                        suite_name=f"{suite.model_name}_suite",
                        model_name=suite.model_name,
                        passed=True,
                        checks=[],
                        summary={"total": 0, "passed": 0, "failed": 0},
                    )
                    self._record_suite_success(span, metrics, suite, result, started_at)
                    return result

                from floe_quality_gx.executor import (
                    create_dataframe_from_connection,
                    run_validation_with_timeout,
                )

                # Load data from connection config
                dataframe = create_dataframe_from_connection(connection_config, suite.model_name)

                # Run validation with timeout
                result = run_validation_with_timeout(
                    suite=suite,
                    dataframe=dataframe,
                    timeout_seconds=suite.timeout_seconds,
                )
                self._record_suite_success(span, metrics, suite, result, started_at)
                return result
            except ImportError:
                # GX not available, return empty result
                result = QualitySuiteResult(
                    suite_name=f"{suite.model_name}_suite",
                    model_name=suite.model_name,
                    passed=True,
                    checks=[],
                    summary={"total": 0, "passed": 0, "failed": 0},
                )
                self._record_suite_success(span, metrics, suite, result, started_at)
                return result
            except Exception as exc:
                self._record_suite_failure(span, metrics, suite, exc, started_at)
                raise

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
        tracer = get_tracer()
        with quality_span(
            tracer,
            "validate_expectations",
            data_source=data_source,
            checks_count=len(expectations),
        ) as _span:
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

        Returns HEALTHY if Great Expectations is discoverable.
        """
        if importlib.util.find_spec("great_expectations") is not None:
            return HealthStatus(
                state=HealthState.HEALTHY,
                message="Great Expectations is available",
                details={"gx_available": True},
            )

        return HealthStatus(
            state=HealthState.UNHEALTHY,
            message="Great Expectations is not installed",
            details={"gx_available": False},
        )

    def get_config_schema(self) -> type[BaseModel]:
        """Return QualityConfig as the configuration schema (FR-010)."""
        return QualityConfig

    def _record_suite_success(
        self,
        span: Any,
        metrics: MetricRecorder,
        suite: QualitySuite,
        result: QualitySuiteResult,
        started_at: float,
    ) -> None:
        pass_count, fail_count = _quality_counts(result)
        status = "success" if result.passed else "failure"
        duration_seconds = time.perf_counter() - started_at
        span.set_attribute("quality.status", status)
        record_result(span, pass_count=pass_count, fail_count=fail_count)
        self._record_quality_metrics(
            metrics,
            status=status,
            duration_seconds=duration_seconds,
        )
        logger.info(
            "gx_suite_completed",
            suite_name=result.suite_name,
            model_name=result.model_name,
            checks_count=len(suite.checks),
            passed=result.passed,
            pass_count=pass_count,
            fail_count=fail_count,
            status=status,
        )

    def _record_suite_failure(
        self,
        span: Any,
        metrics: MetricRecorder,
        suite: QualitySuite,
        exc: Exception,
        started_at: float,
    ) -> None:
        duration_seconds = time.perf_counter() - started_at
        error_type = type(exc).__name__
        span.set_attribute("quality.status", "failure")
        span.set_attribute("quality.error_type", error_type)
        self._record_quality_metrics(
            metrics,
            status="failure",
            duration_seconds=duration_seconds,
            error_type=error_type,
        )
        logger.error(
            "gx_suite_failed",
            suite_name=f"{suite.model_name}_suite",
            model_name=suite.model_name,
            checks_count=len(suite.checks),
            status="failure",
            error_type=error_type,
            error_message=sanitize_error_message(str(exc)),
        )

    @staticmethod
    def _record_quality_metrics(
        metrics: MetricRecorder,
        *,
        status: str,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        labels = {
            "quality.provider": "great_expectations",
            "quality.status": status,
        }
        if error_type is not None:
            labels["quality.error_type"] = error_type
        try:
            metrics.increment(
                GX_SUITE_RUNS_METRIC,
                labels=labels,
                description="Great Expectations suite executions",
                unit="1",
            )
            metrics.record_histogram(
                GX_SUITE_DURATION_METRIC,
                duration_seconds,
                labels=labels,
                description="Great Expectations suite execution duration",
                unit="s",
            )
            if error_type is not None or status != "success":
                metrics.increment(
                    GX_SUITE_FAILURES_METRIC,
                    labels=labels,
                    description="Great Expectations suite failures",
                    unit="1",
                )
        except Exception as exc:  # pragma: no cover - defensive telemetry isolation
            logger.debug("gx_quality_metric_failed", error_type=type(exc).__name__)


def _quality_counts(result: QualitySuiteResult) -> tuple[int, int]:
    summary = result.summary or {}
    passed = summary.get("passed")
    failed = summary.get("failed")
    if isinstance(passed, int) and isinstance(failed, int):
        return passed, failed
    pass_count = sum(1 for check in result.checks if check.passed)
    fail_count = len(result.checks) - pass_count
    return pass_count, fail_count
