"""OpenTelemetry tracing helpers for the DuckDB compute plugin.

This module provides utilities for instrumenting compute operations with
OpenTelemetry spans. Operations like validate_connection, generate_dbt_profile,
and get_catalog_attachment_sql emit spans for observability.

Security:
    - Spans MUST NOT include connection credentials or PII
    - Only metadata (engine type, operation, status) are recorded as attributes
    - Error messages are sanitized before recording

Requirements Covered:
    - 6C-FR-005: OTel spans for compute operations
    - 6C-FR-018: Span attributes for compute context
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

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.compute.duckdb"

# Compute attribute names (6C-FR-018)
ATTR_ENGINE = "compute.engine"
ATTR_OPERATION = "compute.operation"
ATTR_DB_PATH = "compute.db_path"
ATTR_TARGET = "compute.target"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for DuckDB compute operations."""
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def compute_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    engine: str | None = None,
    db_path: str | None = None,
    target: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating compute operation spans.

    Creates an OpenTelemetry span with standard compute attributes.
    The span automatically records duration and handles exceptions.

    Security: Only metadata is recorded, NEVER credentials. Error
    messages are sanitized to redact any leaked credentials.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "validate_connection", "generate_profile").
        engine: Compute engine name (e.g., "duckdb").
        db_path: Database file path (for local DuckDB).
        target: dbt target name.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.
    """
    span_name = f"compute.{operation}"

    attributes: dict[str, Any] = {}

    if engine is not None:
        attributes[ATTR_ENGINE] = engine
    if db_path is not None:
        attributes[ATTR_DB_PATH] = db_path
    if target is not None:
        attributes[ATTR_TARGET] = target
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
    "ATTR_DB_PATH",
    "ATTR_ENGINE",
    "ATTR_OPERATION",
    "ATTR_TARGET",
    "TRACER_NAME",
    "compute_span",
    "get_tracer",
]
