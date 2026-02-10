"""OpenTelemetry tracing helpers for the Alertmanager alert plugin.

This module provides utilities for instrumenting alert operations with
OpenTelemetry spans. Operations like send_alert and validate_config emit
spans for observability.

Security:
    - Spans MUST NOT include alert content, credentials, or PII (FR-049)
    - Only metadata (channel, destination, status) are recorded as attributes
    - Error messages are sanitized before recording

Example:
    >>> from floe_alert_alertmanager.tracing import get_tracer, alert_span
    >>> tracer = get_tracer()
    >>> with alert_span(
    ...     tracer,
    ...     "send_alert",
    ...     channel="alertmanager",
    ...     destination="https://alertmanager:9093"
    ... ) as span:
    ...     # perform operation
    ...     pass

Requirements Covered:
    - 6C-FR-014: OTel spans for alert operations
    - 6C-FR-018: Span attributes for alert context
    - 6C-FR-020: Unit tests for tracing helpers
    - 6C-FR-023: No alert content in traces
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
TRACER_NAME = "floe.alert.alertmanager"

# Alert attribute names (6C-FR-018)
ATTR_CHANNEL = "alert.channel"
ATTR_DESTINATION = "alert.destination"
ATTR_SEVERITY = "alert.severity"
ATTR_DELIVERY_STATUS = "alert.delivery_status"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for Alertmanager alert operations.

    Returns a thread-safe tracer instance from the factory configured for
    the Alertmanager alert plugin. If no tracer provider is configured or
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
def alert_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    channel: str | None = None,
    destination: str | None = None,
    severity: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating alert operation spans.

    Creates an OpenTelemetry span with standard alert attributes.
    The span automatically records duration and handles exceptions.

    Security: Only metadata is recorded, NEVER alert content. Error
    messages are sanitized to redact any leaked credentials before
    recording on the span.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "send_alert", "validate_config").
        channel: Alert channel name (e.g., "alertmanager").
        destination: Alert destination (e.g., API URL).
        severity: Alert severity level.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with alert_span(
        ...     tracer,
        ...     "send_alert",
        ...     channel="alertmanager",
        ...     destination="https://alertmanager:9093",
        ...     severity="critical",
        ... ) as span:
        ...     pass
    """
    span_name = f"alert.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {}

    if channel is not None:
        attributes[ATTR_CHANNEL] = channel
    if destination is not None:
        attributes[ATTR_DESTINATION] = destination
    if severity is not None:
        attributes[ATTR_SEVERITY] = severity
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
    "ATTR_CHANNEL",
    "ATTR_DELIVERY_STATUS",
    "ATTR_DESTINATION",
    "ATTR_SEVERITY",
    "TRACER_NAME",
    "alert_span",
    "get_tracer",
]
