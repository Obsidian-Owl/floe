"""OpenTelemetry tracing utilities for floe.

This module provides tracing utilities including the @traced decorator
and create_span() context manager for instrumenting floe operations.

The @traced decorator supports:
- ``name``: Custom span name (default: function name).
- ``attributes``: Static attributes dict applied to every invocation.
- ``floe_attributes``: Typed FloeSpanAttributes for semantic conventions.
- ``attributes_fn``: Callable receiving the decorated function's ``*args, **kwargs``
  and returning a ``dict[str, Any]`` of dynamic span attributes. Exceptions
  inside ``attributes_fn`` are logged at WARNING level and never propagate.

Contract Version: 1.1.0

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
- 6C-FR-008: Unified @traced with attributes_fn and sanitized errors

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, overload

from opentelemetry.trace import Status, StatusCode, Tracer

from floe_core.telemetry.sanitization import sanitize_error_message
from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from floe_core.telemetry.tracer_factory import (
    reset_tracer,  # Re-exported for test isolation
)
from floe_core.telemetry.tracer_factory import set_tracer as _factory_set_tracer

# Re-export reset_tracer for convenience
__all__ = ["traced", "create_span", "get_tracer", "set_tracer", "reset_tracer"]

if TYPE_CHECKING:
    from collections.abc import Generator

    from opentelemetry.trace import Span

    from floe_core.telemetry.conventions import FloeSpanAttributes

logger = logging.getLogger(__name__)

# Type variables for decorator typing
P = ParamSpec("P")
R = TypeVar("R")

# Tracer name for this module
_TRACER_NAME = "floe_core.telemetry"


def get_tracer() -> Tracer:
    """Get the tracer instance for floe telemetry.

    Returns the thread-safe tracer from the factory, creating it if necessary.
    This indirection allows tests to inject a test tracer.

    Returns a NoOpTracer if OTel initialization fails (e.g., corrupted state).

    Returns:
        Tracer instance for creating spans.
    """
    return _factory_get_tracer(_TRACER_NAME)


def set_tracer(tracer: Tracer | None) -> None:
    """Set the module-level tracer (for testing).

    Args:
        tracer: Tracer instance to use, or None to reset.
    """
    _factory_set_tracer(_TRACER_NAME, tracer)


@overload
def traced(func: Callable[P, R]) -> Callable[P, R]: ...


@overload
def traced(
    *,
    name: str | None = None,
    attributes: dict[str, str] | None = None,
    floe_attributes: FloeSpanAttributes | None = None,
    attributes_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def traced(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    attributes: dict[str, str] | None = None,
    floe_attributes: FloeSpanAttributes | None = None,
    attributes_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace function execution with OpenTelemetry span.

    Creates a span for the decorated function, automatically recording
    the function name, duration, and any exceptions that occur. Error
    messages are sanitized via ``sanitize_error_message()`` to strip
    credentials before recording on the span.

    Can be used with or without arguments:
        @traced
        def my_function(): ...

        @traced(name="custom_name", attributes={"key": "value"})
        def my_function(): ...

    Args:
        func: The function to decorate (when used without parentheses).
        name: Optional custom span name. Defaults to function name.
        attributes: Optional static span attributes to set on every invocation.
        floe_attributes: Optional FloeSpanAttributes to inject Floe semantic
            conventions (floe.namespace, floe.product.name, etc.) onto the span.
        attributes_fn: Optional callable that receives the decorated function's
            ``*args, **kwargs`` and returns a ``dict[str, Any]`` of dynamic
            attributes. Failures are logged at WARNING and never propagate.

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

        >>> def get_attrs(table_id: str, **kw: str) -> dict[str, str]:
        ...     return {"table_id": table_id}
        >>> @traced(attributes_fn=get_attrs)
        ... def load_table(table_id: str) -> None:
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

        def _set_dynamic_attributes(span: Span, *args: Any, **kwargs: Any) -> None:
            """Set dynamic attributes from attributes_fn, swallowing errors."""
            if attributes_fn is not None:
                try:
                    dynamic_attrs = attributes_fn(*args, **kwargs)
                    for key, value in dynamic_attrs.items():
                        span.set_attribute(key, value)
                except Exception:
                    logger.warning(
                        "attributes_fn failed for span %s",
                        span_name,
                        exc_info=True,
                    )

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    span_name,
                    record_exception=False,
                    set_status_on_exception=False,
                ) as span:
                    _set_span_attributes(span)
                    _set_dynamic_attributes(span, *args, **kwargs)
                    try:
                        result = await fn(*args, **kwargs)
                        return cast(R, result)
                    except Exception as e:
                        sanitized = sanitize_error_message(str(e))
                        span.set_status(Status(StatusCode.ERROR, sanitized))
                        span.set_attribute("exception.type", type(e).__name__)
                        span.set_attribute("exception.message", sanitized)
                        raise

            return async_wrapper  # type: ignore[return-value]
        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                tracer = get_tracer()
                with tracer.start_as_current_span(
                    span_name,
                    record_exception=False,
                    set_status_on_exception=False,
                ) as span:
                    _set_span_attributes(span)
                    _set_dynamic_attributes(span, *args, **kwargs)
                    try:
                        result = fn(*args, **kwargs)
                        return result
                    except Exception as e:
                        sanitized = sanitize_error_message(str(e))
                        span.set_status(Status(StatusCode.ERROR, sanitized))
                        span.set_attribute("exception.type", type(e).__name__)
                        span.set_attribute("exception.message", sanitized)
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
    with tracer.start_as_current_span(
        name,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
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
            sanitized = sanitize_error_message(str(e))
            span.set_status(Status(StatusCode.ERROR, sanitized))
            span.set_attribute("exception.type", type(e).__name__)
            span.set_attribute("exception.message", sanitized)
            raise
