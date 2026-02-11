"""OpenTelemetry tracing helpers for the Infisical Secrets Plugin.

This module provides utilities for instrumenting secrets operations with
OpenTelemetry spans. Operations like get_secret, set_secret, delete_secret,
and list_secrets emit spans for observability.

Security:
    - Spans MUST NOT include secret values, credentials, or PII
    - Only include operation metadata (key names, provider, paths)

Example:
    >>> from floe_secrets_infisical.tracing import get_tracer, secrets_span
    >>> tracer = get_tracer()
    >>> with secrets_span(tracer, "get_secret", provider="infisical", key_name="db-pass") as span:
    ...     # perform operation
    ...     span.set_attribute("secrets.found", True)

Requirements Covered:
    - 6C-FR-020: OTel spans for secrets operations
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
TRACER_NAME = "floe.secrets.infisical"

# Semantic attribute names for secrets operations
ATTR_OPERATION = "secrets.operation"
ATTR_PROVIDER = "secrets.provider"
ATTR_KEY_NAME = "secrets.key_name"
ATTR_FOUND = "secrets.found"
ATTR_COUNT = "secrets.count"
ATTR_PATH = "secrets.path"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for secrets operations.

    Returns a thread-safe tracer instance from the factory configured for
    the Infisical secrets plugin. If no tracer provider is configured or
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
def secrets_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    provider: str | None = None,
    key_name: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating secrets operation spans.

    Creates an OpenTelemetry span with standard secrets attributes.
    The span automatically records duration and handles exceptions.

    SECURITY: Never pass secret values as attributes. Only key names
    and operation metadata are safe to include.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "get_secret", "set_secret").
        provider: Secrets provider name (e.g., "infisical").
        key_name: Secret key name (NOT the value).
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with secrets_span(
        ...     tracer,
        ...     "get_secret",
        ...     provider="infisical",
        ...     key_name="db-password",
        ... ) as span:
        ...     span.set_attribute("secrets.found", True)
    """
    span_name = f"secrets.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if provider is not None:
        attributes[ATTR_PROVIDER] = provider
    if key_name is not None:
        attributes[ATTR_KEY_NAME] = key_name
    if extra_attributes:
        attributes.update(extra_attributes)

    with tracer.start_as_current_span(span_name, attributes=attributes) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            sanitized = sanitize_error_message(str(e))
            span.set_status(Status(StatusCode.ERROR, type(e).__name__))
            span.set_attribute("exception.type", type(e).__name__)
            span.set_attribute("exception.message", sanitized)
            raise


def record_result(
    span: trace.Span,
    *,
    found: bool | None = None,
    count: int | None = None,
    operation_type: str | None = None,
) -> None:
    """Record success attributes on a secrets operation span.

    Sets span attributes for a completed secrets operation.
    Never records secret values -- only metadata about the operation.

    Args:
        span: The active span to add attributes to.
        found: Whether the secret was found (for get operations).
        count: Number of secrets returned (for list operations).
        operation_type: Sub-operation type (e.g., "create" or "update").

    Example:
        >>> with secrets_span(tracer, "get_secret", key_name="db-pass") as span:
        ...     secret = backend.get("db-pass")
        ...     record_result(span, found=secret is not None)
    """
    if found is not None:
        span.set_attribute(ATTR_FOUND, found)
    if count is not None:
        span.set_attribute(ATTR_COUNT, count)
    if operation_type is not None:
        span.set_attribute("secrets.operation_type", operation_type)


__all__ = [
    "ATTR_COUNT",
    "ATTR_FOUND",
    "ATTR_KEY_NAME",
    "ATTR_OPERATION",
    "ATTR_PATH",
    "ATTR_PROVIDER",
    "TRACER_NAME",
    "get_tracer",
    "record_result",
    "secrets_span",
]
