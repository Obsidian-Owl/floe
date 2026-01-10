"""Console telemetry backend plugin for floe.

This plugin provides a console exporter for OpenTelemetry traces,
useful for local development and debugging.

Contract Version: 1.0.0

Requirements Covered:
- FR-027: Console backend for local development

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture
"""

from __future__ import annotations

# Plugin will be implemented in T070
# This stub enables TDD - tests should fail until implementation

__all__ = [
    "ConsoleTelemetryPlugin",
]


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies."""
    if name == "ConsoleTelemetryPlugin":
        from floe_telemetry_console.plugin import ConsoleTelemetryPlugin

        return ConsoleTelemetryPlugin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
