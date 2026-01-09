"""OpenTelemetry tracing utilities for floe.

This module provides tracing utilities including the @traced decorator
and create_span() context manager for instrumenting floe operations.

Contract Version: 1.0.0

Requirements Covered:
- FR-004: Spans for compilation operations
- FR-005: Spans for dbt operations
- FR-006: Spans for Dagster asset materializations
- FR-007: floe.namespace attribute on ALL spans
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
from typing import Callable, ParamSpec, TypeVar, cast, overload

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

logger = logging.getLogger(__name__)

# Type variables for decorator typing
P = ParamSpec("P")
R = TypeVar("R")

# Module-level tracer instance (can be overridden for testing)
_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Get the tracer instance for floe telemetry.

    Returns the module-level tracer, creating it if necessary.
    This indirection allows tests to inject a test tracer.

    Returns:
        Tracer instance for creating spans.
    """
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer("floe_core.telemetry")
    return _tracer


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
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def traced(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    attributes: dict[str, str] | None = None,
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
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        span_name = name if name is not None else fn.__name__

        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                tracer = get_tracer()
                with tracer.start_as_current_span(span_name) as span:
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, value)
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
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, value)
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
