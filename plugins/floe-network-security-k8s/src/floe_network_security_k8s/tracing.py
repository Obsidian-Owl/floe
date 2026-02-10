"""OpenTelemetry tracing helpers for the K8s network security plugin.

This module provides utilities for instrumenting security policy generation
operations with OpenTelemetry spans.

Security:
    - Spans MUST NOT include sensitive policy details or credentials
    - Only metadata (policy type, resource count, status) are recorded
    - Error messages are sanitized before recording

Requirements Covered:
    - 6C-FR-007: OTel spans for security operations
    - 6C-FR-018: Span attributes for security context
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

TRACER_NAME = "floe.security.network"

# Security attribute names (6C-FR-018)
ATTR_POLICY_TYPE = "security.policy_type"
ATTR_RESOURCE_COUNT = "security.resource_count"
ATTR_NAMESPACE = "security.namespace"
ATTR_PSS_LEVEL = "security.pss_level"


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer for K8s network security operations."""
    return _factory_get_tracer(TRACER_NAME)


@contextmanager
def security_span(
    tracer: trace.Tracer,
    operation: str,
    *,
    policy_type: str | None = None,
    resource_count: int | None = None,
    namespace: str | None = None,
    pss_level: str | None = None,
    extra_attributes: dict[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Context manager for creating security operation spans.

    Args:
        tracer: OpenTelemetry tracer instance.
        operation: Operation name (e.g., "generate_network_policy").
        policy_type: Type of policy being generated.
        resource_count: Number of resources affected.
        namespace: K8s namespace scope.
        pss_level: Pod Security Standards level.
        extra_attributes: Additional span attributes.

    Yields:
        The active span for adding custom attributes.
    """
    span_name = f"security.{operation}"

    attributes: dict[str, Any] = {}

    if policy_type is not None:
        attributes[ATTR_POLICY_TYPE] = policy_type
    if resource_count is not None:
        attributes[ATTR_RESOURCE_COUNT] = resource_count
    if namespace is not None:
        attributes[ATTR_NAMESPACE] = namespace
    if pss_level is not None:
        attributes[ATTR_PSS_LEVEL] = pss_level
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
    "ATTR_NAMESPACE",
    "ATTR_POLICY_TYPE",
    "ATTR_PSS_LEVEL",
    "ATTR_RESOURCE_COUNT",
    "TRACER_NAME",
    "get_tracer",
    "security_span",
]
