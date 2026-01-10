"""Log correlation with OpenTelemetry traces via structlog.

This module provides trace context injection into structured logs.
Logs within an active span include trace_id and span_id for correlation.

Contract Version: 1.0.0

Requirements Covered:
- FR-015: Inject trace_id into all log records when a trace is active
- FR-016: Inject span_id into all log records when a span is active
- FR-017: Support structured logging format with trace context as fields
- FR-018: Support configurable log levels

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import INVALID_SPAN_ID, INVALID_TRACE_ID

# Type alias for structlog EventDict
EventDict = MutableMapping[str, Any]


def add_trace_context(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: EventDict,
) -> EventDict:
    """Add trace context to structlog event dictionary.

    Structlog processor that injects trace_id and span_id from the
    active OpenTelemetry span into the log event dictionary.

    Args:
        logger: The logger instance (unused, required by structlog processor API).
        method_name: The log method name (e.g., "info", "debug").
        event_dict: The event dictionary to enrich with trace context.

    Returns:
        The event dictionary with trace_id and span_id added if a span is active.

    Examples:
        >>> import structlog
        >>> structlog.configure(processors=[add_trace_context, ...])
        >>> log = structlog.get_logger()
        >>> with create_span("my_operation"):
        ...     log.info("processing")  # Includes trace_id and span_id
    """
    # Get the current span from context
    span = trace.get_current_span()
    ctx = span.get_span_context()

    # Only add trace context if we have a valid span
    if ctx.trace_id != INVALID_TRACE_ID and ctx.span_id != INVALID_SPAN_ID:
        # Format as 32-char hex for trace_id, 16-char hex for span_id
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")

    return event_dict


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = True,
) -> None:
    """Configure structlog with trace context injection.

    Sets up structlog with the add_trace_context processor and
    JSON output format for log aggregation compatibility.

    Args:
        log_level: The minimum log level to emit (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, output logs as JSON. If False, use console format.

    Examples:
        >>> configure_logging(log_level="DEBUG", json_output=True)
        >>> log = structlog.get_logger()
        >>> log.info("configured")  # JSON output with trace context
    """
    # TODO: T062 - Implement configure_logging
    # This stub exists to enable TDD - tests should fail until T062 implementation
    raise NotImplementedError("configure_logging not yet implemented (T062)")


__all__ = [
    "add_trace_context",
    "configure_logging",
]
