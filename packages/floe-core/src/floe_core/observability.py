"""OpenTelemetry instrumentation for floe-core.

This module provides observability primitives for compute plugin monitoring.
It follows OpenTelemetry semantic conventions and provides:
- Tracer for distributed tracing
- Meter for metrics (histograms, counters)
- Pre-configured metrics for connection validation

Requirements:
    - FR-024: System MUST emit compute metrics via OpenTelemetry

Example:
    >>> from floe_core.observability import get_tracer, get_meter
    >>> from floe_core.observability import record_validation_duration, record_validation_error
    >>>
    >>> tracer = get_tracer()
    >>> with tracer.start_as_current_span("validate_connection") as span:
    ...     span.set_attribute("compute.plugin", "duckdb")
    ...     # ... validation logic
    ...     record_validation_duration("duckdb", 23.5, "healthy")
    >>>
    >>> # On error
    >>> record_validation_error("duckdb", "connection_timeout")

See Also:
    - FR-024: OTel metrics emission
    - https://opentelemetry.io/docs/specs/semconv/
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import TYPE_CHECKING

import structlog

from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter
    from opentelemetry.trace import Span, Tracer

logger = structlog.get_logger(__name__)

# Module-level singletons for metrics (tracer uses factory)
_meter: Meter | None = None
_validation_duration_histogram: Histogram | None = None
_validation_errors_counter: Counter | None = None

# Service name for OTel
OTEL_SERVICE_NAME = "floe-core"
OTEL_SERVICE_VERSION = "0.1.0"


def get_tracer() -> Tracer:
    """Get or create the floe-core OpenTelemetry tracer.

    Returns a thread-safe tracer from the factory for distributed tracing.
    The tracer is lazily initialized on first call and reused for subsequent calls.

    Returns a NoOpTracer if OTel initialization fails (e.g., corrupted state).

    Returns:
        OpenTelemetry Tracer instance for floe-core.

    Example:
        >>> tracer = get_tracer()
        >>> with tracer.start_as_current_span("my_operation") as span:
        ...     span.set_attribute("my.attribute", "value")
        ...     # ... operation logic
    """
    return _factory_get_tracer(OTEL_SERVICE_NAME)


def get_meter() -> Meter:
    """Get or create the floe-core OpenTelemetry meter.

    Returns a configured meter for metrics collection. The meter is
    lazily initialized on first call and reused for subsequent calls.

    Returns:
        OpenTelemetry Meter instance for floe-core.

    Example:
        >>> meter = get_meter()
        >>> counter = meter.create_counter(
        ...     name="my_counter",
        ...     description="Counts something",
        ... )
        >>> counter.add(1, {"label": "value"})
    """
    global _meter

    if _meter is None:
        from opentelemetry import metrics

        _meter = metrics.get_meter(
            name=OTEL_SERVICE_NAME,
            version=OTEL_SERVICE_VERSION,
        )
        logger.debug("observability.meter_initialized", service=OTEL_SERVICE_NAME)

    return _meter


def _get_validation_duration_histogram() -> Histogram:
    """Get or create the validation_duration histogram.

    Internal function to lazily create the histogram metric.

    Returns:
        Histogram for recording validation durations.
    """
    global _validation_duration_histogram

    if _validation_duration_histogram is None:
        meter = get_meter()
        _validation_duration_histogram = meter.create_histogram(
            name="floe.compute.validation_duration",
            description="Duration of compute connection validation in milliseconds",
            unit="ms",
        )
        logger.debug("observability.histogram_created", name="floe.compute.validation_duration")

    return _validation_duration_histogram


def _get_validation_errors_counter() -> Counter:
    """Get or create the validation_errors counter.

    Internal function to lazily create the counter metric.

    Returns:
        Counter for tracking validation errors.
    """
    global _validation_errors_counter

    if _validation_errors_counter is None:
        meter = get_meter()
        _validation_errors_counter = meter.create_counter(
            name="floe.compute.validation_errors",
            description="Count of compute connection validation errors",
            unit="{errors}",
        )
        logger.debug("observability.counter_created", name="floe.compute.validation_errors")

    return _validation_errors_counter


def record_validation_duration(
    plugin_name: str,
    duration_ms: float,
    status: str,
) -> None:
    """Record connection validation duration metric.

    Records the duration of a validate_connection() call to the
    validation_duration histogram with appropriate labels.

    Args:
        plugin_name: Name of the compute plugin (e.g., "duckdb", "snowflake").
        duration_ms: Validation duration in milliseconds.
        status: Validation result status ("healthy", "degraded", "unhealthy").

    Example:
        >>> record_validation_duration("duckdb", 23.5, "healthy")
        >>> record_validation_duration("snowflake", 1500.0, "unhealthy")
    """
    histogram = _get_validation_duration_histogram()
    attributes = {
        "compute.plugin": plugin_name,
        "validation.status": status,
    }
    histogram.record(duration_ms, attributes)

    logger.debug(
        "observability.validation_duration_recorded",
        plugin=plugin_name,
        duration_ms=duration_ms,
        status=status,
    )


def record_validation_error(
    plugin_name: str,
    error_type: str,
) -> None:
    """Record connection validation error metric.

    Increments the validation_errors counter when a connection validation
    fails. This should be called when validate_connection() returns an
    UNHEALTHY status.

    Args:
        plugin_name: Name of the compute plugin (e.g., "duckdb", "snowflake").
        error_type: Type of error (e.g., "connection_timeout", "auth_failure").

    Example:
        >>> record_validation_error("duckdb", "connection_timeout")
        >>> record_validation_error("snowflake", "auth_failure")
    """
    counter = _get_validation_errors_counter()
    attributes = {
        "compute.plugin": plugin_name,
        "error.type": error_type,
    }
    counter.add(1, attributes)

    logger.debug(
        "observability.validation_error_recorded",
        plugin=plugin_name,
        error_type=error_type,
    )


def start_validation_span(plugin_name: str) -> AbstractContextManager[Span]:
    """Start a span for connection validation.

    Creates and returns a span context manager for tracing validate_connection
    operations. The span is automatically configured with the plugin name.

    Args:
        plugin_name: Name of the compute plugin (e.g., "duckdb", "snowflake").

    Returns:
        Span context manager that can be used with `with` statement.

    Example:
        >>> with start_validation_span("duckdb") as span:
        ...     span.set_attribute("db.path", ":memory:")
        ...     # ... validation logic
        ...     span.set_attribute("validation.status", "healthy")
    """
    tracer = get_tracer()
    span = tracer.start_as_current_span(
        name="compute.validate_connection",
        attributes={"compute.plugin": plugin_name},
    )
    return span


def reset_for_testing() -> None:
    """Reset all module-level singletons for testing.

    This function should only be used in tests to ensure a clean state
    between test runs.

    Example:
        >>> from floe_core.observability import reset_for_testing
        >>> reset_for_testing()
    """
    global _tracer, _meter, _validation_duration_histogram, _validation_errors_counter
    _tracer = None
    _meter = None
    _validation_duration_histogram = None
    _validation_errors_counter = None
    logger.debug("observability.reset_for_testing")
