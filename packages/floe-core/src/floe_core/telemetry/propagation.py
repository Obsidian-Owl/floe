"""W3C Trace Context and Baggage propagation for floe.

This module provides context propagation utilities for distributed tracing,
implementing W3C Trace Context and W3C Baggage standards.

Contract Version: 1.0.0

Requirements Covered:
- FR-002: W3C Trace Context propagation
- FR-003: W3C Baggage propagation
- FR-007a: floe.namespace propagation via Baggage

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from opentelemetry import baggage, context, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.propagate import get_global_textmap, set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

if TYPE_CHECKING:
    from opentelemetry.context import Context
    from opentelemetry.trace import Span, SpanContext

logger = logging.getLogger(__name__)

# Baggage keys for floe attributes (per ADR-0006)
BAGGAGE_NAMESPACE = "floe.namespace"
BAGGAGE_PRODUCT_NAME = "floe.product.name"
BAGGAGE_PRODUCT_VERSION = "floe.product.version"
BAGGAGE_MODE = "floe.mode"


def configure_propagators() -> CompositePropagator:
    """Configure and set global W3C propagators.

    Sets up a composite propagator with both W3C Trace Context and
    W3C Baggage propagators, then registers it globally.

    This should be called during TelemetryProvider initialization.

    Returns:
        The configured CompositePropagator instance.

    Examples:
        >>> propagator = configure_propagators()
        >>> isinstance(propagator, CompositePropagator)
        True
    """
    propagator = CompositePropagator(
        [
            TraceContextTextMapPropagator(),
            W3CBaggagePropagator(),
        ]
    )
    set_global_textmap(propagator)
    logger.debug("Configured W3C Trace Context and Baggage propagators")
    return propagator


def get_propagator() -> Any:
    """Get the global text map propagator.

    Returns:
        The currently configured global propagator.
    """
    return get_global_textmap()


def inject_context(
    carrier: dict[str, str],
    ctx: Context | None = None,
) -> dict[str, str]:
    """Inject trace context and baggage into a carrier.

    Injects W3C Trace Context (traceparent, tracestate) and W3C Baggage
    headers into the provided carrier dictionary.

    Args:
        carrier: Mutable dictionary to inject headers into.
        ctx: Optional context to inject. Uses current context if not provided.

    Returns:
        The carrier with injected headers.

    Examples:
        >>> carrier = {}
        >>> inject_context(carrier)
        >>> 'traceparent' in carrier  # When span is active
        True
    """
    propagator = get_global_textmap()
    if ctx is not None:
        propagator.inject(carrier, context=ctx)  # type: ignore[arg-type]
    else:
        propagator.inject(carrier)  # type: ignore[arg-type]
    return carrier


def extract_context(carrier: dict[str, str]) -> Context:
    """Extract trace context and baggage from a carrier.

    Extracts W3C Trace Context and W3C Baggage from the provided carrier
    dictionary, returning a context with the extracted values.

    Args:
        carrier: Dictionary containing headers to extract from.

    Returns:
        Context with extracted trace context and baggage.

    Examples:
        >>> carrier = {
        ...     "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        ...     "baggage": "floe.namespace=analytics"
        ... }
        >>> ctx = extract_context(carrier)
        >>> get_baggage_value("floe.namespace", ctx)
        'analytics'
    """
    propagator = get_global_textmap()
    return propagator.extract(carrier)


def set_baggage_value(key: str, value: str, ctx: Context | None = None) -> Context:
    """Set a baggage value in the context.

    Args:
        key: Baggage key (e.g., "floe.namespace").
        value: Baggage value to set.
        ctx: Optional context to modify. Uses current context if not provided.

    Returns:
        New context with the baggage value set.

    Examples:
        >>> ctx = set_baggage_value("floe.namespace", "analytics")
        >>> get_baggage_value("floe.namespace", ctx)
        'analytics'
    """
    if ctx is not None:
        return baggage.set_baggage(key, value, ctx)
    return baggage.set_baggage(key, value)


def get_baggage_value(key: str, ctx: Context | None = None) -> str | None:
    """Get a baggage value from the context.

    Args:
        key: Baggage key to retrieve.
        ctx: Optional context to read from. Uses current context if not provided.

    Returns:
        The baggage value, or None if not set.

    Examples:
        >>> ctx = set_baggage_value("floe.namespace", "analytics")
        >>> get_baggage_value("floe.namespace", ctx)
        'analytics'
        >>> get_baggage_value("nonexistent", ctx)
        None
    """
    if ctx is not None:
        value = baggage.get_baggage(key, ctx)
    else:
        value = baggage.get_baggage(key)
    # OTel baggage returns object, but we only set str values
    return str(value) if value is not None else None


def set_floe_baggage(
    namespace: str,
    product_name: str | None = None,
    product_version: str | None = None,
    mode: str | None = None,
    ctx: Context | None = None,
) -> Context:
    """Set all floe baggage values in the context.

    Convenience function to set floe-specific baggage values.
    Per ADR-0006, namespace is mandatory; others are optional.

    Args:
        namespace: Polaris catalog namespace (MANDATORY).
        product_name: Optional data product name.
        product_version: Optional data product version.
        mode: Optional execution mode (dev/staging/prod).
        ctx: Optional context to modify. Uses current context if not provided.

    Returns:
        New context with all floe baggage values set.

    Examples:
        >>> ctx = set_floe_baggage(
        ...     namespace="analytics",
        ...     product_name="customer-360",
        ...     mode="prod"
        ... )
        >>> get_baggage_value("floe.namespace", ctx)
        'analytics'
    """
    result_ctx = ctx if ctx is not None else context.get_current()

    # Set mandatory namespace
    result_ctx = baggage.set_baggage(BAGGAGE_NAMESPACE, namespace, result_ctx)

    # Set optional values if provided
    if product_name is not None:
        result_ctx = baggage.set_baggage(BAGGAGE_PRODUCT_NAME, product_name, result_ctx)
    if product_version is not None:
        result_ctx = baggage.set_baggage(
            BAGGAGE_PRODUCT_VERSION, product_version, result_ctx
        )
    if mode is not None:
        result_ctx = baggage.set_baggage(BAGGAGE_MODE, mode, result_ctx)

    return result_ctx


def get_current_span() -> Span:
    """Get the current active span.

    Returns:
        The current span, or a non-recording span if none is active.
    """
    return trace.get_current_span()


def get_current_span_context() -> SpanContext:
    """Get the span context of the current active span.

    Returns:
        The current span's context.
    """
    return trace.get_current_span().get_span_context()


def get_trace_id() -> str | None:
    """Get the current trace ID as a hex string.

    Returns:
        Trace ID as 32-character hex string, or None if no valid trace.

    Examples:
        >>> # Within an active span
        >>> trace_id = get_trace_id()
        >>> len(trace_id) if trace_id else 0
        32
    """
    span_ctx = get_current_span_context()
    if span_ctx.is_valid:
        return format(span_ctx.trace_id, "032x")
    return None


def get_span_id() -> str | None:
    """Get the current span ID as a hex string.

    Returns:
        Span ID as 16-character hex string, or None if no valid span.

    Examples:
        >>> # Within an active span
        >>> span_id = get_span_id()
        >>> len(span_id) if span_id else 0
        16
    """
    span_ctx = get_current_span_context()
    if span_ctx.is_valid:
        return format(span_ctx.span_id, "016x")
    return None


def is_trace_active() -> bool:
    """Check if a valid trace is currently active.

    Returns:
        True if a valid trace context exists.
    """
    return get_current_span_context().is_valid


def create_context_from_headers(headers: dict[str, str]) -> Context:
    """Create a context from HTTP headers.

    Convenience function for extracting trace context from HTTP request headers.
    Handles both W3C Trace Context and Baggage headers.

    Args:
        headers: HTTP headers dictionary.

    Returns:
        Context with extracted trace context and baggage.

    Examples:
        >>> headers = {
        ...     "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        ...     "baggage": "floe.namespace=analytics,floe.mode=prod"
        ... }
        >>> ctx = create_context_from_headers(headers)
        >>> get_baggage_value("floe.namespace", ctx)
        'analytics'
    """
    return extract_context(headers)


def inject_headers(ctx: Context | None = None) -> dict[str, str]:
    """Create headers with injected trace context.

    Convenience function for creating HTTP headers with trace context.
    Injects both W3C Trace Context and Baggage headers.

    Args:
        ctx: Optional context to inject. Uses current context if not provided.

    Returns:
        Dictionary with traceparent, tracestate (if set), and baggage headers.

    Examples:
        >>> # Within an active span with baggage
        >>> headers = inject_headers()
        >>> 'traceparent' in headers
        True
    """
    carrier: dict[str, str] = {}
    return inject_context(carrier, ctx)
