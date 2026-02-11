"""OpenTelemetry tracing helpers for the K8s RBAC plugin.

This module provides utilities for instrumenting RBAC security operations with
OpenTelemetry spans. All RBAC operations (generate_service_account, generate_role,
generate_role_binding, generate_namespace, generate_pod_security_context) emit
spans for observability.

Security:
    - Spans MUST NOT include credentials, PII, or sensitive data (FR-049)
    - Error messages are sanitized via floe_core.telemetry.sanitization
    - Only include operation metadata (policy_type, resource_count)

Example:
    >>> from floe_rbac_k8s.tracing import get_tracer, security_span
    >>> tracer = get_tracer()
    >>> with security_span(tracer, "generate_role", policy_type="Role") as span:
    ...     # perform operation
    ...     span.set_attribute("security.resource_count", 3)

Requirements Covered:
    - 6C-FR-020: OTel spans for RBAC security operations
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
TRACER_NAME = "floe.security.rbac"

# Semantic attribute names for security operations
ATTR_OPERATION = "security.operation"
ATTR_POLICY_TYPE = "security.policy_type"
ATTR_RESOURCE_COUNT = "security.resource_count"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for RBAC security operations.

    Returns a thread-safe tracer instance from the factory configured for
    the K8s RBAC plugin. If no tracer provider is configured or
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
def security_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    policy_type: str | None = None,
    resource_count: int | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating RBAC security operation spans.

    Creates an OpenTelemetry span with standard security attributes.
    The span automatically records duration and handles exceptions.
    Error messages are sanitized to prevent credential leakage.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "generate_role", "generate_namespace").
        policy_type: K8s resource type being generated (e.g., "Role",
            "ServiceAccount", "Namespace").
        resource_count: Number of resources involved in the operation.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with security_span(
        ...     tracer,
        ...     "generate_role",
        ...     policy_type="Role",
        ...     resource_count=3,
        ... ) as span:
        ...     span.set_attribute("security.namespace", "floe-jobs")
    """
    span_name = f"security.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if policy_type is not None:
        attributes[ATTR_POLICY_TYPE] = policy_type
    if resource_count is not None:
        attributes[ATTR_RESOURCE_COUNT] = resource_count
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
