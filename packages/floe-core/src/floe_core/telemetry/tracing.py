"""OpenTelemetry tracing utilities for floe.

This module provides tracing utilities including the @traced decorator
and create_span() context manager for instrumenting floe operations.

Contract Version: 1.0.0

Requirements Covered:
- FR-004: Spans for compilation operations
- FR-005: Spans for dbt operations
- FR-006: Spans for Dagster asset materializations
- FR-007: floe.namespace attribute on ALL spans
- FR-007b: floe.product.name attribute
- FR-007c: floe.product.version attribute
- FR-007d: floe.mode attribute
- FR-019: OpenTelemetry semantic conventions
- FR-022: Error recording with exception details

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, overload

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.trace import Span

    from floe_core.telemetry.conventions import FloeSpanAttributes

logger = logging.getLogger(__name__)

# Type variables for decorator typing
P = ParamSpec("P")
R = TypeVar("R")

# Module-level tracer instance (can be overridden for testing)
_tracer: Tracer | None = None
_tracer_lock = threading.Lock()
_tracer_init_failed: bool = False


def get_tracer() -> Tracer:
    """Get the tracer instance for floe telemetry.

    Returns the module-level tracer, creating it if necessary.
    This indirection allows tests to inject a test tracer.
    Thread-safe via double-checked locking pattern.

    Returns a NoOpTracer if OTel initialization fails (e.g., corrupted state).

    Returns:
        Tracer instance for creating spans.
    """
    global _tracer, _tracer_init_failed

    if _tracer is not None:
        return _tracer

    if _tracer_init_failed:
        return trace.NoOpTracer()

    with _tracer_lock:
        # Double-check after acquiring lock
        if _tracer is not None:
            return _tracer

        if _tracer_init_failed:
            return trace.NoOpTracer()

        try:
            _tracer = trace.get_tracer("floe_core.telemetry")
            return _tracer
        except RecursionError:
            _tracer_init_failed = True
            return trace.NoOpTracer()
        except Exception:
            _tracer_init_failed = True
            return trace.NoOpTracer()


def set_tracer(tracer: Tracer | None) -> None:
    """Set the module-level tracer (for testing).

    Args:
        tracer: Tracer instance to use, or None to reset.
    """
    global _tracer
    _tracer = tracer


@overload
def traced(func: Callable[P, R]) -> Callable[P, R]: ...


@overload
def traced(
    *,
    name: str | None = None,
    attributes: dict[str, str] | None = None,
    floe_attributes: FloeSpanAttributes | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def traced(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    attributes: dict[str, str] | None = None,
    floe_attributes: FloeSpanAttributes | None = None,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace function execution with OpenTelemetry span.

    Creates a span for the decorated function, automatically recording
    the function name, duration, and any exceptions that occur.

    Can be used with or without arguments:
        @traced
        def my_function(): ...

        @traced(name="custom_name", attributes={"key": "value"})
        def my_function(): ...

    Args:
        func: The function to decorate (when used without parentheses).
        name: Optional custom span name. Defaults to function name.
        attributes: Optional span attributes to set.
        floe_attributes: Optional FloeSpanAttributes to inject Floe semantic
            conventions (floe.namespace, floe.product.name, etc.) onto the span.

    Returns:
        Decorated function that creates a span on each invocation.

    Examples:
        >>> @traced
        ... def compile_spec(spec_path: str) -> dict:
        ...     return {"compiled": True}
        >>> compile_spec("/path/to/spec.yaml")
        {'compiled': True}

        >>> @traced(name="dbt.run", attributes={"dbt.command": "run"})
        ... def run_dbt():
        ...     pass

        >>> from floe_core.telemetry.conventions import FloeSpanAttributes
        >>> attrs = FloeSpanAttributes(
        ...     namespace="analytics", product_name="customer-360",
        ...     product_version="1.0.0", mode="prod"
        ... )
        >>> @traced(floe_attributes=attrs)
        ... def pipeline_run():
        ...     pass
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        span_name = name if name is not None else fn.__name__

        def _set_span_attributes(span: Span) -> None:
            """Set all attributes on the span."""
            # Set Floe semantic attributes first (if provided)
            if floe_attributes is not None:
                for key, value in floe_attributes.to_otel_dict().items():
                    span.set_attribute(key, value)
            # Set custom attributes (can override floe attributes if needed)
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                tracer = get_tracer()
                with tracer.start_as_current_span(span_name) as span:
                    _set_span_attributes(span)
                    try:
                        result = await fn(*args, **kwargs)
                        return cast(R, result)
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                tracer = get_tracer()
                with tracer.start_as_current_span(span_name) as span:
                    _set_span_attributes(span)
                    try:
                        result = fn(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            return sync_wrapper

    if func is not None:
        # Called without parentheses: @traced
        return decorator(func)
    else:
        # Called with parentheses: @traced() or @traced(name="...")
        return decorator


@contextmanager
def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    floe_attributes: FloeSpanAttributes | None = None,
) -> Generator[Span, None, None]:
    """Create a span as a context manager.

    Creates an OpenTelemetry span with the given name and optional attributes.
    The span is automatically ended when exiting the context. Nested calls
    create parent-child relationships automatically.

    Args:
        name: The name for the span.
        attributes: Optional dictionary of attributes to set on the span.
        floe_attributes: Optional FloeSpanAttributes to inject Floe semantic
            conventions (floe.namespace, floe.product.name, etc.) onto the span.

    Yields:
        The created span for additional attribute setting.

    Examples:
        >>> with create_span("pipeline_execution") as span:
        ...     span.set_attribute("pipeline.name", "customer-360")
        ...     with create_span("load_data") as child:
        ...         child.set_attribute("source", "s3://bucket/data")

        >>> with create_span("operation", attributes={"op.type": "test"}):
        ...     pass

        >>> from floe_core.telemetry.conventions import FloeSpanAttributes
        >>> attrs = FloeSpanAttributes(
        ...     namespace="analytics", product_name="customer-360",
        ...     product_version="1.0.0", mode="prod"
        ... )
        >>> with create_span("pipeline_run", floe_attributes=attrs):
        ...     pass
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        # Set Floe semantic attributes first (if provided)
        if floe_attributes is not None:
            for key, value in floe_attributes.to_otel_dict().items():
                span.set_attribute(key, value)
        # Set custom attributes (can override floe attributes if needed)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
