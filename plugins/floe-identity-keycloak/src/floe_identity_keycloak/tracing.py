"""OpenTelemetry tracing helpers for the Keycloak Identity Plugin.

This module provides utilities for instrumenting identity operations with
OpenTelemetry spans. Operations like authenticate, validate_token, and
validate_token_for_realm emit spans for observability.

Security:
    - Spans MUST NOT include credentials, tokens, passwords, or PII
    - Only include operation metadata (realm, multi-tenant flag, operation name)

Example:
    >>> from floe_identity_keycloak.tracing import get_tracer, identity_span
    >>> tracer = get_tracer()
    >>> with identity_span(tracer, "authenticate", realm="floe") as span:
    ...     # perform authentication
    ...     span.set_attribute("identity.grant_type", "client_credentials")

Requirements Covered:
    - OB-005: OpenTelemetry tracing for authentication operations
    - 6C-FR-020: Plugin-level tracing with identity_span context manager
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
TRACER_NAME = "floe.identity.keycloak"

# Semantic attribute names for identity operations
ATTR_OPERATION = "identity.operation"
ATTR_REALM = "identity.realm"
ATTR_MULTI_TENANT = "identity.multi_tenant"
ATTR_TOKEN_TYPE = "identity.token_type"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for identity operations.

    Returns a thread-safe tracer instance from the factory configured for
    the Keycloak identity plugin. If no tracer provider is configured or
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
def identity_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    realm: str | None = None,
    multi_tenant: bool = False,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating identity operation spans.

    Creates an OpenTelemetry span with standard identity attributes.
    The span automatically records duration and handles exceptions.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "authenticate", "validate_token").
        realm: Keycloak realm name for the operation.
        multi_tenant: Whether this is a multi-tenant operation.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.

    Example:
        >>> tracer = get_tracer()
        >>> with identity_span(
        ...     tracer,
        ...     "authenticate",
        ...     realm="floe",
        ... ) as span:
        ...     span.set_attribute("identity.grant_type", "password")
    """
    span_name = f"identity.{operation}"

    # Build attributes dict, excluding None values
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}

    if realm is not None:
        attributes[ATTR_REALM] = realm
    if multi_tenant:
        attributes[ATTR_MULTI_TENANT] = True
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
