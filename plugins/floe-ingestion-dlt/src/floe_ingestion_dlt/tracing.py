"""OpenTelemetry tracing helpers for the dlt ingestion plugin.

This module provides utilities for instrumenting ingestion operations with
OpenTelemetry spans. Operations like create_pipeline, run, and
get_destination_config emit spans for observability.

Security:
    - Spans MUST NOT include credentials, PII, or sensitive data (FR-049)
    - Only include operation metadata (source_type, destination_table, duration)

Example:
    >>> from floe_ingestion_dlt.tracing import get_tracer, ingestion_span
    >>> tracer = get_tracer()
    >>> with ingestion_span(tracer, "create_pipeline", source_type="rest_api") as span:
    ...     # perform operation
    ...     span.set_attribute("ingestion.rows_loaded", 1000)

Requirements Covered:
    - FR-044: OTel spans for pipeline operations
    - FR-045: Span attributes for source context
    - FR-046: Completed run span attributes
    - FR-047: Failed run span attributes
    - FR-049: No secret values in traces
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Iterator

    from floe_core.plugins.ingestion import IngestionResult
    from floe_core.plugins.sink import EgressResult

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.ingestion.dlt"

# Ingestion attribute names (FR-045)
ATTR_OPERATION = "ingestion.operation"
ATTR_SOURCE_TYPE = "ingestion.source_type"
ATTR_DESTINATION_TABLE = "ingestion.destination_table"
ATTR_WRITE_MODE = "ingestion.write_mode"
ATTR_PIPELINE_NAME = "ingestion.pipeline_name"
ATTR_SCHEMA_CONTRACT = "ingestion.schema_contract"

# Result attributes (FR-046)
ATTR_ROWS_LOADED = "ingestion.rows_loaded"
ATTR_BYTES_WRITTEN = "ingestion.bytes_written"
ATTR_DURATION_SECONDS = "ingestion.duration_seconds"
ATTR_SUCCESS = "ingestion.success"

# Error attributes (FR-047)
ATTR_ERROR_TYPE = "error.type"
ATTR_ERROR_MESSAGE = "error.message"
ATTR_ERROR_CATEGORY = "error.category"

# Egress/Sink attributes (Epic 4G - FR-010)
ATTR_SINK_TYPE = "egress.sink_type"
ATTR_SINK_DESTINATION = "egress.destination"
ATTR_SINK_ROWS_WRITTEN = "egress.rows_written"
ATTR_SINK_DURATION_MS = "egress.duration_ms"
ATTR_SINK_STATUS = "egress.status"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for ingestion operations.

    Returns a thread-safe tracer instance from the factory configured for
    the dlt ingestion plugin. If no tracer provider is configured or
    initialization fails, returns a no-op tracer.

    Returns:
        OpenTelemetry Tracer instance.

    Example:
        >>> tracer = get_tracer()
        >>> with tracer.start_as_current_span("my_operation"):
        ...     pass
    """
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def ingestion_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    source_type: str | None = None,
    destination_table: str | None = None,
    write_mode: str | None = None,
    pipeline_name: str | None = None,
    schema_contract: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating ingestion operation spans.

    Creates an OpenTelemetry span with standard ingestion attributes.
    The span automatically records duration and handles exceptions.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "create_pipeline", "run").
        source_type: Type of data source (e.g., "rest_api").
        destination_table: Target Iceberg table path.
        write_mode: Write mode (append, replace, merge).
        pipeline_name: dlt pipeline name.
        schema_contract: Schema contract mode (evolve, freeze, discard_value).
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with ingestion_span(
        ...     tracer,
        ...     "run",
        ...     source_type="rest_api",
        ...     destination_table="bronze.raw_events",
        ... ) as span:
        ...     span.set_attribute("ingestion.rows_loaded", 5000)
    """
    span_name = f"ingestion.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if source_type is not None:
        attributes[ATTR_SOURCE_TYPE] = source_type
    if destination_table is not None:
        attributes[ATTR_DESTINATION_TABLE] = destination_table
    if write_mode is not None:
        attributes[ATTR_WRITE_MODE] = write_mode
    if pipeline_name is not None:
        attributes[ATTR_PIPELINE_NAME] = pipeline_name
    if schema_contract is not None:
        attributes[ATTR_SCHEMA_CONTRACT] = schema_contract
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, type(e).__name__))
            span.record_exception(e)
            raise


def record_ingestion_result(span: trace.Span, result: IngestionResult) -> None:
    """Record ingestion result attributes on a span.

    Sets span attributes for a completed ingestion run, including
    rows loaded, bytes written, and duration (FR-046).

    Args:
        span: The active span to add attributes to.
        result: The ingestion result with execution metrics.

    Example:
        >>> with ingestion_span(tracer, "run") as span:
        ...     result = pipeline.run()
        ...     record_ingestion_result(span, result)
    """
    span.set_attribute(ATTR_SUCCESS, result.success)
    span.set_attribute(ATTR_ROWS_LOADED, result.rows_loaded)
    span.set_attribute(ATTR_BYTES_WRITTEN, result.bytes_written)
    span.set_attribute(ATTR_DURATION_SECONDS, result.duration_seconds)


def record_ingestion_error(
    span: trace.Span,
    error: Exception,
    *,
    category: str | None = None,
) -> None:
    """Record error attributes on a span safely.

    Adds error information to a span without exposing sensitive data (FR-047).
    Only records exception type, a truncated message, and error category.

    Args:
        span: The span to add error attributes to.
        error: The exception that occurred.
        category: Error category (TRANSIENT, PERMANENT, PARTIAL, CONFIGURATION).

    Example:
        >>> with ingestion_span(tracer, "run") as span:
        ...     try:
        ...         run_pipeline()
        ...     except IngestionError as e:
        ...         record_ingestion_error(span, e, category=e.category.value)
        ...         raise
    """
    span.set_attribute(ATTR_ERROR_TYPE, type(error).__name__)
    # Truncate message to prevent sensitive data leakage in long error strings
    message = str(error)[:500]
    span.set_attribute(ATTR_ERROR_MESSAGE, message)
    if category is not None:
        span.set_attribute(ATTR_ERROR_CATEGORY, category)


@contextmanager
def egress_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    sink_type: str | None = None,
    destination: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating egress operation spans.

    Creates an OpenTelemetry span with standard egress attributes.
    The span automatically records duration and handles exceptions.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "write", "create_sink").
        sink_type: Type of sink destination (e.g., "rest_api").
        destination: Target destination identifier.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with egress_span(tracer, "write", sink_type="rest_api") as span:
        ...     span.set_attribute("egress.rows_written", 1000)
    """
    span_name = f"egress.{operation}"

    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if sink_type is not None:
        attributes[ATTR_SINK_TYPE] = sink_type
    if destination is not None:
        attributes[ATTR_SINK_DESTINATION] = destination
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, type(e).__name__))
            span.record_exception(e)
            raise


def record_egress_result(span: trace.Span, result: EgressResult) -> None:
    """Record egress result attributes on a span.

    Sets span attributes for a completed egress write, including
    rows written, duration, and status (FR-010).

    Args:
        span: The active span to add attributes to.
        result: The egress result with delivery metrics.

    Example:
        >>> with egress_span(tracer, "write") as span:
        ...     result = plugin.write(sink, data)
        ...     record_egress_result(span, result)
    """
    span.set_attribute(ATTR_SINK_STATUS, "success" if result.success else "failure")
    span.set_attribute(ATTR_SINK_ROWS_WRITTEN, result.rows_delivered)
    span.set_attribute(ATTR_SINK_DURATION_MS, result.duration_seconds * 1000)


def record_egress_error(
    span: trace.Span,
    error: Exception,
    *,
    category: str | None = None,
) -> None:
    """Record error attributes on an egress span safely.

    Adds error information to a span without exposing sensitive data.
    Only records exception type, a truncated message, and error category.

    Args:
        span: The span to add error attributes to.
        error: The exception that occurred.
        category: Error category (TRANSIENT, PERMANENT, CONFIGURATION).

    Example:
        >>> with egress_span(tracer, "write") as span:
        ...     try:
        ...         write_to_sink()
        ...     except SinkWriteError as e:
        ...         record_egress_error(span, e, category="transient")
        ...         raise
    """
    span.set_attribute(ATTR_ERROR_TYPE, type(error).__name__)
    message = str(error)[:500]
    span.set_attribute(ATTR_ERROR_MESSAGE, message)
    if category is not None:
        span.set_attribute(ATTR_ERROR_CATEGORY, category)
