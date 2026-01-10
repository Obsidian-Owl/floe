"""OpenTelemetry Integration Contracts.

Contract Version: 1.0.0

This package contains Pydantic v2 contracts for OpenTelemetry configuration
and the TelemetryBackendPlugin interface.

Exports:
    - TelemetryConfig: Central telemetry configuration
    - ResourceAttributes: Service identification attributes
    - TelemetryAuth: OTLP authentication
    - SamplingConfig: Environment-based sampling
    - FloeSpanAttributes: Floe semantic conventions
    - TelemetryBackendPlugin: ABC for pluggable backends
    - PluginMetadata: Plugin identification
"""

from __future__ import annotations

from .span_attributes import (
    FLOE_DAGSTER_ASSET,
    FLOE_DBT_MODEL,
    FLOE_JOB_TYPE,
    FLOE_MODE,
    FLOE_NAMESPACE,
    FLOE_PIPELINE_ID,
    FLOE_PRODUCT_NAME,
    FLOE_PRODUCT_VERSION,
    FloeSpanAttributes,
)
from .telemetry_backend import PluginMetadata, TelemetryBackendPlugin
from .telemetry_config import (
    ResourceAttributes,
    SamplingConfig,
    TelemetryAuth,
    TelemetryConfig,
)

__all__ = [
    # Configuration contracts
    "TelemetryConfig",
    "ResourceAttributes",
    "TelemetryAuth",
    "SamplingConfig",
    # Span attributes
    "FloeSpanAttributes",
    # Semantic convention constants
    "FLOE_NAMESPACE",
    "FLOE_PRODUCT_NAME",
    "FLOE_PRODUCT_VERSION",
    "FLOE_MODE",
    "FLOE_PIPELINE_ID",
    "FLOE_JOB_TYPE",
    "FLOE_DBT_MODEL",
    "FLOE_DAGSTER_ASSET",
    # Plugin interface
    "TelemetryBackendPlugin",
    "PluginMetadata",
]
