"""Jaeger telemetry backend plugin for floe.

This plugin provides OTLP exporter configuration for Jaeger,
enabling distributed tracing visualization and analysis.

Contract Version: 1.0.0

Requirements Covered:
- FR-029: Jaeger backend for production tracing

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

# Plugin will be implemented in T073
# This stub enables TDD - tests should fail until implementation

__all__ = [
    "JaegerTelemetryPlugin",
]


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies."""
    if name == "JaegerTelemetryPlugin":
        from floe_telemetry_jaeger.plugin import JaegerTelemetryPlugin

        return JaegerTelemetryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
