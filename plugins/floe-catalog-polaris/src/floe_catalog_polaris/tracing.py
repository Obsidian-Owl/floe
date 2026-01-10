"""OpenTelemetry tracing helpers for the Polaris Catalog Plugin.

This module provides utilities for instrumenting catalog operations with
OpenTelemetry spans. All catalog operations (connect, create_namespace,
create_table, vend_credentials, etc.) should emit spans for observability.

Security:
    - Spans MUST NOT include credentials, PII, or sensitive data
    - Only include operation metadata (catalog name, namespace, table name)

Example:
    >>> from floe_catalog_polaris.tracing import get_tracer, catalog_span
    >>> tracer = get_tracer()
    >>> with catalog_span(tracer, "create_namespace", namespace="bronze") as span:
    ...     # perform operation
    ...     span.set_attribute("namespace.location", "s3://bucket/bronze")
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from collections.abc import Iterator

# Tracer name follows OpenTelemetry naming conventions
TRACER_NAME = "floe.catalog.polaris"

# Semantic attribute names for catalog operations
ATTR_CATALOG_NAME = "catalog.name"
ATTR_CATALOG_URI = "catalog.uri"
ATTR_NAMESPACE = "catalog.namespace"
ATTR_TABLE_NAME = "catalog.table.name"
ATTR_TABLE_FULL_NAME = "catalog.table.full_name"
ATTR_OPERATION = "catalog.operation"
ATTR_WAREHOUSE = "catalog.warehouse"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for catalog operations.

    Returns a tracer instance configured for the Polaris catalog plugin.
    If no tracer provider is configured, returns a no-op tracer.

    Returns:
        OpenTelemetry Tracer instance.

    Example:
        >>> tracer = get_tracer()
        >>> with tracer.start_as_current_span("my_operation"):
        ...     pass
    """
    return trace.get_tracer(TRACER_NAME)


@contextmanager
def catalog_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    catalog_name: str | None = None,
    catalog_uri: str | None = None,
    warehouse: str | None = None,
    namespace: str | None = None,
    table_name: str | None = None,
    table_full_name: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating catalog operation spans.

    Creates an OpenTelemetry span with standard catalog attributes.
    The span automatically records duration and handles exceptions.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "connect", "create_namespace").
        catalog_name: Name of the catalog (e.g., "polaris").
        catalog_uri: Catalog REST API URI (sanitized, no credentials).
        warehouse: Warehouse identifier.
        namespace: Namespace name for the operation.
        table_name: Table name (without namespace).
        table_full_name: Full table identifier (namespace.table).
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with catalog_span(
        ...     tracer,
        ...     "create_table",
        ...     catalog_name="polaris",
        ...     namespace="bronze",
        ...     table_name="customers"
        ... ) as span:
        ...     span.set_attribute("table.partition_count", 10)
        ...     # perform operation
    """
    span_name = f"catalog.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if catalog_name is not None:
        attributes[ATTR_CATALOG_NAME] = catalog_name
    if catalog_uri is not None:
        attributes[ATTR_CATALOG_URI] = _sanitize_uri(catalog_uri)
    if warehouse is not None:
        attributes[ATTR_WAREHOUSE] = warehouse
    if namespace is not None:
        attributes[ATTR_NAMESPACE] = namespace
    if table_name is not None:
        attributes[ATTR_TABLE_NAME] = table_name
    if table_full_name is not None:
        attributes[ATTR_TABLE_FULL_NAME] = table_full_name
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            # Record exception but DO NOT include sensitive details
            span.set_status(Status(StatusCode.ERROR, str(type(e).__name__)))
            span.record_exception(e)
            raise


def _sanitize_uri(uri: str) -> str:
    """Remove credentials from URI for safe logging/tracing.

    Removes userinfo (username:password@) from URIs to prevent
    accidental credential exposure in traces.

    Args:
        uri: URI that may contain credentials.

    Returns:
        URI with credentials removed.

    Example:
        >>> _sanitize_uri("https://user:pass@example.com/api")
        'https://example.com/api'
    """
    # Simple sanitization - remove userinfo from URI
    # Format: scheme://[userinfo@]host[:port]/path
    if "@" in uri and "://" in uri:
        scheme_end = uri.index("://") + 3
        at_pos = uri.index("@")
        # Only sanitize if @ is in the authority section (before first /)
        slash_pos = uri.find("/", scheme_end)
        if slash_pos == -1 or at_pos < slash_pos:
            return uri[:scheme_end] + uri[at_pos + 1 :]
    return uri


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
        >>> with catalog_span(tracer, "connect") as span:
        ...     try:
        ...         connect_to_catalog()
        ...     except AuthenticationError as e:
        ...         set_error_attributes(span, e, include_message=False)
        ...         raise
    """
    span.set_attribute("error.type", type(error).__name__)
    if include_message:
        # Truncate message to avoid large payloads
        message = str(error)[:500]
        span.set_attribute("error.message", message)
