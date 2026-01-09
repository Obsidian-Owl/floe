"""OpenTelemetry integration for floe-core.

This module provides OpenTelemetry-based telemetry capabilities for the floe
data platform, including:

- TelemetryConfig: Configuration for telemetry emission
- TelemetryProvider: Central provider for traces, metrics, and logs
- Tracing: Span creation and trace context propagation
- Metrics: Counter, gauge, and histogram instrumentation
- Logging: Structured logging with trace context correlation

The telemetry architecture follows a three-layer model (per ADR-0006):
- Layer 1 (Enforced): OpenTelemetry SDK emission (this module)
- Layer 2 (Enforced): OTLP Collector aggregation
- Layer 3 (Pluggable): Backend storage/visualization (TelemetryBackendPlugin)

Example:
    >>> from floe_core.telemetry import TelemetryProvider, TelemetryConfig
    >>> config = TelemetryConfig(...)
    >>> with TelemetryProvider(config) as provider:
    ...     # Application code with automatic telemetry
    ...     pass

See Also:
    - specs/001-opentelemetry/: Feature specification
    - docs/architecture/adr/ADR-0006: Telemetry architecture
"""

from __future__ import annotations

# Public API will be exported here as modules are implemented
# See T003-T006 for implementation of config, conventions, and provider modules

__all__: list[str] = []
