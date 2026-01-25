"""OpenTelemetry instrumentation for floe-iceberg operations.

This module provides the @traced decorator for automatic span creation
around IcebergTableManager operations. Supports nested spans, custom
attributes, and exception recording.

Uses OpenTelemetry API (tracer from GlobalTracerProvider) for compatibility
with any OTLP-compliant backend.

Example:
    >>> from floe_iceberg.telemetry import traced
    >>>
    >>> @traced
    ... def create_table(namespace: str, table_name: str) -> Table:
    ...     # Creates a span named "create_table"
    ...     ...
    >>>
    >>> @traced(operation_name="iceberg.write", attributes={"mode": "append"})
    ... def write_data(table: Table, data: DataFrame) -> None:
    ...     # Creates a span named "iceberg.write" with custom attributes
    ...     ...

Attributes:
    TRACER_NAME: Instrumentation library name for OpenTelemetry.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, overload

from opentelemetry.trace import Status, StatusCode, Tracer

from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from floe_core.telemetry.tracer_factory import reset_tracer as _reset_tracer

if TYPE_CHECKING:
    from collections.abc import Callable

# Type variables for generic decorator typing
P = ParamSpec("P")
R = TypeVar("R")

# =============================================================================
# Constants
# =============================================================================

TRACER_NAME = "floe-iceberg"
"""OpenTelemetry instrumentation library name.

Used to identify spans created by this package in distributed traces.
"""


# =============================================================================
# Tracer Access
# =============================================================================


def get_tracer() -> Tracer:
    """Get the package tracer from GlobalTracerProvider.

    Returns the thread-safe cached tracer instance from the factory.
    Uses the global tracer provider configured by the application.

    Returns a NoOpTracer if OTel is not properly configured or initialization
    fails (e.g., due to corrupted global state from test fixtures).

    Returns:
        OpenTelemetry Tracer instance for floe-iceberg.

    Example:
        >>> tracer = get_tracer()
        >>> with tracer.start_as_current_span("my_operation"):
        ...     # Span is active here
        ...     pass
    """
    return _factory_get_tracer(TRACER_NAME)


# =============================================================================
# Traced Decorator
# =============================================================================


@overload
def traced(
    func: Callable[P, R],
    *,
    operation_name: str | None = ...,
    attributes: dict[str, Any] | None = ...,
    attributes_fn: Callable[..., dict[str, Any]] | None = ...,
) -> Callable[P, R]: ...


@overload
def traced(
    func: None = ...,
    *,
    operation_name: str | None = ...,
    attributes: dict[str, Any] | None = ...,
    attributes_fn: Callable[..., dict[str, Any]] | None = ...,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def traced(
    func: Callable[P, R] | None = None,
    *,
    operation_name: str | None = None,
    attributes: dict[str, Any] | None = None,
    attributes_fn: Callable[..., dict[str, Any]] | None = None,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to create OpenTelemetry spans for functions.

    Creates a span around the decorated function, automatically recording
    the operation name, custom attributes, and any exceptions raised.

    Can be used with or without parentheses:
        @traced
        def my_function(): ...

        @traced(operation_name="custom_name")
        def my_function(): ...

    Args:
        func: The function to decorate (when used without parentheses).
        operation_name: Custom span name. Defaults to function name.
        attributes: Static attributes to add to the span.
        attributes_fn: Callable that receives function arguments and returns
            attributes dict. Called with (*args, **kwargs) of decorated function.

    Returns:
        Decorated function that creates a span on each call.

    Example:
        >>> @traced
        ... def simple_operation() -> None:
        ...     pass
        >>>
        >>> @traced(operation_name="iceberg.create_table")
        ... def create_table(namespace: str, name: str) -> Table:
        ...     pass
        >>>
        >>> @traced(attributes={"mode": "append"})
        ... def write_data(data: DataFrame) -> None:
        ...     pass
        >>>
        >>> def get_attrs(table_id: str, **kwargs) -> dict[str, str]:
        ...     return {"table_id": table_id}
        >>>
        >>> @traced(attributes_fn=get_attrs)
        ... def load_table(table_id: str, namespace: str) -> Table:
        ...     pass
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tracer = get_tracer()
            span_name = operation_name or fn.__name__

            with tracer.start_as_current_span(span_name) as span:
                # Set operation name attribute
                span.set_attribute("floe.iceberg.operation", fn.__name__)

                # Set static attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Set dynamic attributes from function args
                if attributes_fn:
                    try:
                        dynamic_attrs = attributes_fn(*args, **kwargs)
                        for key, value in dynamic_attrs.items():
                            span.set_attribute(key, value)
                    except Exception:
                        # Don't fail the operation if attribute extraction fails
                        pass

                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise

        return wrapper

    # Handle both @traced and @traced(...) syntax
    if func is not None:
        # Called without parentheses: @traced
        return decorator(func)
    else:
        # Called with parentheses: @traced(...) or @traced()
        return decorator


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TRACER_NAME",
    "get_tracer",
    "traced",
]
