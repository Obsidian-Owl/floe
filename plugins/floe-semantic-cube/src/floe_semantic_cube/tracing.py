"""OpenTelemetry tracing helpers for the Cube Semantic Layer Plugin.

This module provides utilities for instrumenting semantic layer operations with
OpenTelemetry spans. Operations like schema generation, health checks, and
datasource configuration emit spans for observability.

Security:
    - Spans MUST NOT include credentials, PII, or sensitive data
    - Only include operation metadata (server URL, model name, duration)

Example:
    >>> from floe_semantic_cube.tracing import get_tracer, semantic_span
    >>> tracer = get_tracer()
    >>> with semantic_span(tracer, "sync_schema", model_name="orders") as span:
    ...     # perform operation
    ...     span.set_attribute("schema.model_count", 5)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Iterator

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.semantic.cube"

# Semantic attribute names for semantic layer operations
ATTR_OPERATION = "semantic.operation"
ATTR_SERVER_URL = "semantic.server_url"
ATTR_MODEL_NAME = "semantic.model.name"
ATTR_MODEL_COUNT = "semantic.model.count"
ATTR_SCHEMA_PATH = "semantic.schema.path"
ATTR_DURATION_MS = "semantic.duration_ms"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for semantic layer operations.

    Returns a thread-safe tracer instance from the factory configured for
    the Cube semantic layer plugin. If no tracer provider is configured or
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
def semantic_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    server_url: str | None = None,
    model_name: str | None = None,
    schema_path: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating semantic layer operation spans.

    Creates an OpenTelemetry span with standard semantic layer attributes.
    The span automatically records duration and handles exceptions.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "sync_schema", "health_check").
        server_url: Cube server URL (sanitized, no credentials).
        model_name: dbt model name being processed.
        schema_path: Path to schema output directory.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with semantic_span(
        ...     tracer,
        ...     "sync_schema",
        ...     model_name="orders",
        ...     schema_path="/output/schema",
        ... ) as span:
        ...     span.set_attribute("schema.model_count", 5)
    """
    span_name = f"semantic.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if server_url is not None:
        attributes[ATTR_SERVER_URL] = _sanitize_url(server_url)
    if model_name is not None:
        attributes[ATTR_MODEL_NAME] = model_name
    if schema_path is not None:
        attributes[ATTR_SCHEMA_PATH] = schema_path
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


def _sanitize_url(url: str) -> str:
    """Remove credentials from URL for safe logging/tracing.

    Uses ``urllib.parse`` for robust handling of URLs with embedded
    credentials, including edge-cases with multiple ``@`` characters.

    Args:
        url: URL that may contain credentials.

    Returns:
        URL with credentials removed.

    Example:
        >>> _sanitize_url("https://user:pass@cube.example.com/api")
        'https://cube.example.com/api'
    """
    from urllib.parse import urlparse, urlunparse

    try:
        parsed = urlparse(url)
    except ValueError:
        return url

    if parsed.username is not None or parsed.password is not None:
        # Rebuild with userinfo stripped
        replaced = parsed._replace(
            netloc=parsed.hostname or ""
            if parsed.port is None
            else f"{parsed.hostname or ''}:{parsed.port}",
        )
        return urlunparse(replaced)
    return url


def set_error_attributes(
    span: trace.Span,
    error: Exception,
    *,
    include_message: bool = True,
) -> None:
    """Set error attributes on a span safely.

    Adds error information to a span without exposing sensitive data.
    Only records exception type and optionally a sanitized message.

    Args:
        span: The span to add error attributes to.
        error: The exception that occurred.
        include_message: Whether to include error message (default True).
            Set to False if message might contain sensitive data.

    Example:
        >>> with semantic_span(tracer, "health_check") as span:
        ...     try:
        ...         check_health()
        ...     except CubeHealthCheckError as e:
        ...         set_error_attributes(span, e)
        ...         raise
    """
    span.set_attribute("error.type", type(error).__name__)
    if include_message:
        message = str(error)[:500]
        span.set_attribute("error.message", message)
