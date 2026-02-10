"""OpenTelemetry tracing helpers for the K8s secrets plugin.

This module provides utilities for instrumenting secrets operations with
OpenTelemetry spans. Operations like get_secret, set_secret, list_secrets,
and health_check emit spans for observability.

Security:
    - Spans MUST NOT include secret values, credentials, or PII (FR-049)
    - Only key names (never values) are recorded as span attributes
    - Error messages are sanitized before recording

Example:
    >>> from floe_secrets_k8s.tracing import get_tracer, secrets_span
    >>> tracer = get_tracer()
    >>> with secrets_span(tracer, "get_secret", provider="k8s", key_name="db-password") as span:
    ...     # perform operation
    ...     pass

Requirements Covered:
    - 6C-FR-012: OTel spans for secrets operations
    - 6C-FR-016: Span attributes for secrets context
    - 6C-FR-020: Unit tests for tracing helpers
    - 6C-FR-023: No secret values in traces
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
TRACER_NAME = "floe.secrets.k8s"

# Secrets attribute names (6C-FR-016)
ATTR_OPERATION = "secrets.operation"
ATTR_PROVIDER = "secrets.provider"
ATTR_KEY_NAME = "secrets.key_name"
ATTR_NAMESPACE = "secrets.namespace"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for secrets operations.

    Returns a thread-safe tracer instance from the factory configured for
    the K8s secrets plugin. If no tracer provider is configured or
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
    namespace: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating secrets operation spans.

    Creates an OpenTelemetry span with standard secrets attributes.
    The span automatically records duration and handles exceptions.

    Security: Only key names are recorded, NEVER secret values. Error
    messages are sanitized to redact any leaked credentials before
    recording on the span.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "get_secret", "set_secret").
        provider: Secrets backend provider (e.g., "k8s").
        key_name: Secret key name (NEVER the value).
        namespace: Kubernetes namespace for the operation.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with secrets_span(
        ...     tracer,
        ...     "get_secret",
        ...     provider="k8s",
        ...     key_name="db-password",
        ...     namespace="production",
        ... ) as span:
        ...     pass
    """
    span_name = f"secrets.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if provider is not None:
        attributes[ATTR_PROVIDER] = provider
    if key_name is not None:
        attributes[ATTR_KEY_NAME] = key_name
    if namespace is not None:
        attributes[ATTR_NAMESPACE] = namespace
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


__all__ = [
    "ATTR_KEY_NAME",
    "ATTR_NAMESPACE",
    "ATTR_OPERATION",
    "ATTR_PROVIDER",
    "TRACER_NAME",
    "get_tracer",
    "secrets_span",
]
