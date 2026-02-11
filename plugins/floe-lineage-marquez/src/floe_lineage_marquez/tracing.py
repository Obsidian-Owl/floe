"""OpenTelemetry tracing helpers for the Marquez lineage plugin.

This module provides utilities for instrumenting lineage operations with
OpenTelemetry spans. Operations like get_transport_config, get_namespace_strategy,
get_helm_values, and validate_connection emit spans for observability.

Security:
    - Spans MUST NOT include credentials, API keys, or PII (FR-049)
    - Only metadata like job names, event types, namespaces are recorded
    - Error messages are sanitized before recording

Example:
    >>> from floe_lineage_marquez.tracing import get_tracer, lineage_span
    >>> tracer = get_tracer()
    >>> with lineage_span(
    ...     tracer,
    ...     "emit_run_event",
    ...     job_name="my_job",
    ...     event_type="START"
    ... ) as span:
    ...     # perform operation
    ...     pass

Requirements Covered:
    - 6C-FR-020: OTel spans for lineage operations
    - 6C-FR-021: Span attributes for lineage context
    - 6C-FR-023: No credentials in traces
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from floe_core.telemetry.sanitization import sanitize_error_message
from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Iterator

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.lineage.marquez"

# Lineage attribute names (6C-FR-021)
ATTR_JOB_NAME = "lineage.job_name"
ATTR_EVENT_TYPE = "lineage.event_type"
ATTR_NAMESPACE = "lineage.namespace"
ATTR_RUN_ID = "lineage.run_id"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for lineage operations.

    Returns a thread-safe tracer instance from the factory configured for
    the Marquez lineage plugin. If no tracer provider is configured or
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
def lineage_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    job_name: str | None = None,
    event_type: str | None = None,
    namespace: str | None = None,
    run_id: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating lineage operation spans.

    Creates an OpenTelemetry span with standard lineage attributes.
    The span automatically records duration and handles exceptions.

    Security: Only metadata like job names, event types, and namespaces
    are recorded. NEVER API keys, credentials, or PII. Error messages
    are sanitized to redact any leaked credentials before recording
    on the span.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "get_transport_config", "validate_connection").
        job_name: Job name for lineage event.
        event_type: Event type (e.g., "START", "COMPLETE", "FAIL").
        namespace: Lineage namespace.
        run_id: Run identifier for lineage event.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with lineage_span(
        ...     tracer,
        ...     "emit_run_event",
        ...     job_name="etl_pipeline",
        ...     event_type="START",
        ...     namespace="production",
        ... ) as span:
        ...     pass
    """
    span_name = f"lineage.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {}

    if job_name is not None:
        attributes[ATTR_JOB_NAME] = job_name
    if event_type is not None:
        attributes[ATTR_EVENT_TYPE] = event_type
    if namespace is not None:
        attributes[ATTR_NAMESPACE] = namespace
    if run_id is not None:
        attributes[ATTR_RUN_ID] = run_id
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(
        span_name,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            sanitized = sanitize_error_message(str(e))
            span.set_status(Status(StatusCode.ERROR, type(e).__name__))
            span.set_attribute("exception.type", type(e).__name__)
            span.set_attribute("exception.message", sanitized)
            raise


__all__ = [
    "ATTR_EVENT_TYPE",
    "ATTR_JOB_NAME",
    "ATTR_NAMESPACE",
    "ATTR_RUN_ID",
    "TRACER_NAME",
    "get_tracer",
    "lineage_span",
]
