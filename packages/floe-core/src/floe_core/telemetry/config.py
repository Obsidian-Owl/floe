"""Telemetry configuration re-exports for backward compatibility.

This module re-exports telemetry configuration classes from their canonical
location in floe_core.schemas.telemetry. This maintains backward compatibility
for code that imports from floe_core.telemetry.config.

MOVED: All TelemetryConfig classes now live in floe_core.schemas.telemetry
to break the circular dependency: schemas -> telemetry -> plugins -> schemas

Resolution Details (12B-ARCH-001):
    The circular dependency occurred because:
    1. schemas/compiled_artifacts.py needed TelemetryConfig
    2. telemetry/config.py was in the telemetry module
    3. telemetry module imported from plugins
    4. plugins imported from schemas

    Solution: TelemetryConfig is a Pydantic schema (data definition), so it
    belongs in the schemas module. This module re-exports for compatibility.

Contract Version: 1.0.0

Deprecated:
    Import from floe_core.schemas.telemetry instead:
    >>> from floe_core.schemas.telemetry import TelemetryConfig

See Also:
    - floe_core.schemas.telemetry: Canonical location
    - specs/001-opentelemetry/contracts/telemetry_config.py: Contract source
    - ADR-0006: Telemetry architecture
    - 12B-ARCH-001: Circular dependency resolution
"""

from __future__ import annotations

# Re-export all classes from schemas.telemetry for backward compatibility
from floe_core.schemas.telemetry import (
    BatchSpanProcessorConfig,
    LoggingConfig,
    ResourceAttributes,
    SamplingConfig,
    TelemetryAuth,
    TelemetryConfig,
)

__all__ = [
    "ResourceAttributes",
    "TelemetryAuth",
    "BatchSpanProcessorConfig",
    "LoggingConfig",
    "SamplingConfig",
    "TelemetryConfig",
]
