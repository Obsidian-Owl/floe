"""OpenTelemetry instrumentation for floe-iceberg operations.

This module re-exports the unified @traced decorator from floe-core
and provides the package-specific tracer for floe-iceberg. All callers
import ``traced`` from this module for backwards compatibility.

The @traced decorator supports ``name``, ``attributes``, ``floe_attributes``,
and ``attributes_fn`` parameters. See ``floe_core.telemetry.tracing.traced``
for full documentation.

Example:
    >>> from floe_iceberg.telemetry import traced
    >>>
    >>> @traced
    ... def create_table(namespace: str, table_name: str) -> Table:
    ...     # Creates a span named "create_table"
    ...     ...
    >>>
    >>> @traced(name="iceberg.write", attributes={"mode": "append"})
    ... def write_data(table: Table, data: DataFrame) -> None:
    ...     # Creates a span named "iceberg.write" with custom attributes
    ...     ...

Attributes:
    TRACER_NAME: Instrumentation library name for OpenTelemetry.
"""

from __future__ import annotations

from floe_core.telemetry.tracer_factory import get_tracer as _factory_get_tracer
from floe_core.telemetry.tracing import traced
from opentelemetry.trace import Tracer

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
# Exports
# =============================================================================

__all__ = [
    "TRACER_NAME",
    "get_tracer",
    "traced",
]
