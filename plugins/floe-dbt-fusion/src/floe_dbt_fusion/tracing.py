"""OpenTelemetry tracing helpers for the dbt-fusion plugin.

This module provides utilities for instrumenting dbt-fusion operations with
OpenTelemetry spans. Operations like compile, run, test, and lint emit spans.

Security:
    - Spans MUST NOT include SQL content, credentials, or PII
    - Only metadata (mode, operation, fallback status) are recorded
    - Error messages are sanitized before recording

Requirements Covered:
    - 6C-FR-018: Span attributes for dbt-fusion context
    - 6C-FR-020: Unit tests for tracing helpers
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

TRACER_NAME = "floe.dbt.fusion"

# DBT Fusion attribute names (6C-FR-018)
ATTR_MODE = "dbt_fusion.mode"
ATTR_OPERATION = "dbt_fusion.operation"
ATTR_FALLBACK = "dbt_fusion.fallback"
ATTR_MODEL_COUNT = "dbt_fusion.model_count"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for dbt-fusion operations."""
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def dbt_fusion_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    mode: str | None = None,
    fallback: bool | None = None,
    model_count: int | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating dbt-fusion operation spans.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "compile", "run", "test", "lint").
        mode: Execution mode (e.g., "core", "cloud", "fusion").
        fallback: Whether this operation is a fallback from fusion to core.
        model_count: Number of dbt models being processed.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.
    """
    span_name = f"dbt_fusion.{operation}"

    attributes: dict[str, Any] = {}

    if mode is not None:
        attributes[ATTR_MODE] = mode
    if fallback is not None:
        attributes[ATTR_FALLBACK] = fallback
    if model_count is not None:
        attributes[ATTR_MODEL_COUNT] = model_count
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
    "ATTR_FALLBACK",
    "ATTR_MODE",
    "ATTR_MODEL_COUNT",
    "ATTR_OPERATION",
    "TRACER_NAME",
    "dbt_fusion_span",
    "get_tracer",
]
