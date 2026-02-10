"""OpenTelemetry tracing helpers for the Dagster orchestrator plugin.

This module provides utilities for instrumenting orchestrator operations with
OpenTelemetry spans. Operations like create_definitions, validate_connection,
and emit_lineage_event emit spans for observability.

Security:
    - Spans MUST NOT include connection credentials or PII
    - Only metadata (operation, asset keys, status) are recorded
    - Error messages are sanitized before recording

Requirements Covered:
    - 6C-FR-006: OTel spans for orchestrator operations
    - 6C-FR-018: Span attributes for orchestrator context
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

TRACER_NAME = "floe.orchestrator.dagster"

# Orchestrator attribute names (6C-FR-018)
ATTR_OPERATION = "orchestrator.operation"
ATTR_ASSET_KEY = "orchestrator.asset_key"
ATTR_ASSET_COUNT = "orchestrator.asset_count"
ATTR_SCHEDULE_CRON = "orchestrator.schedule_cron"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for Dagster orchestrator operations."""
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def orchestrator_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    asset_key: str | None = None,
    asset_count: int | None = None,
    schedule_cron: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating orchestrator operation spans.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "create_definitions", "validate_connection").
        asset_key: Asset key being operated on.
        asset_count: Number of assets being created/managed.
        schedule_cron: Cron expression for schedule operations.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.
    """
    span_name = f"orchestrator.{operation}"

    attributes: dict[str, Any] = {}

    if asset_key is not None:
        attributes[ATTR_ASSET_KEY] = asset_key
    if asset_count is not None:
        attributes[ATTR_ASSET_COUNT] = asset_count
    if schedule_cron is not None:
        attributes[ATTR_SCHEDULE_CRON] = schedule_cron
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
    "ATTR_ASSET_COUNT",
    "ATTR_ASSET_KEY",
    "ATTR_OPERATION",
    "ATTR_SCHEDULE_CRON",
    "TRACER_NAME",
    "get_tracer",
    "orchestrator_span",
]
