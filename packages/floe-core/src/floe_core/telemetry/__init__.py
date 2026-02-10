"""OpenTelemetry integration for floe-core.

This module provides OpenTelemetry-based telemetry capabilities for the floe
data platform, including:

- TelemetryConfig: Configuration for telemetry emission
- TelemetryProvider: SDK lifecycle management (init, shutdown, context manager)
- ResourceAttributes: Service identification for OTel resources
- SamplingConfig: Environment-based trace sampling
- FloeSpanAttributes: Floe semantic conventions for spans

The telemetry architecture follows a three-layer model (per ADR-0006):
- Layer 1 (Enforced): OpenTelemetry SDK emission (this module)
- Layer 2 (Enforced): OTLP Collector aggregation
- Layer 3 (Pluggable): Backend storage/visualization (TelemetryBackendPlugin)

Example:
    >>> from floe_core.telemetry import TelemetryConfig, TelemetryProvider, ResourceAttributes
    >>> attrs = ResourceAttributes(
    ...     service_name="my-service",
    ...     service_version="1.0.0",
    ...     deployment_environment="dev",
    ...     floe_namespace="analytics",
    ...     floe_product_name="customer-360",
    ...     floe_product_version="1.0.0",
    ...     floe_mode="dev",
    ... )
    >>> config = TelemetryConfig(resource_attributes=attrs, otlp_endpoint="http://localhost:4317")
    >>> with TelemetryProvider(config) as provider:
    ...     # Telemetry is active
    ...     pass

See Also:
    - specs/001-opentelemetry/: Feature specification
    - docs/architecture/adr/ADR-0006: Telemetry architecture
"""

from __future__ import annotations

# Configuration models
from floe_core.telemetry.config import (
    BatchSpanProcessorConfig,
    ResourceAttributes,
    SamplingConfig,
    TelemetryAuth,
    TelemetryConfig,
)

# Semantic conventions
from floe_core.telemetry.conventions import (
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

# Propagation utilities
from floe_core.telemetry.propagation import (
    BAGGAGE_MODE,
    BAGGAGE_NAMESPACE,
    BAGGAGE_PRODUCT_NAME,
    BAGGAGE_PRODUCT_VERSION,
    configure_propagators,
    create_context_from_headers,
    extract_context,
    get_baggage_value,
    get_current_span,
    get_current_span_context,
    get_propagator,
    get_span_id,
    get_trace_id,
    inject_context,
    inject_headers,
    is_trace_active,
    set_baggage_value,
    set_floe_baggage,
)

# Provider
from floe_core.telemetry.provider import ProviderState, TelemetryProvider

# Sanitization utilities
from floe_core.telemetry.sanitization import (
    sanitize_error_message as sanitize_error_message,
)

# Tracing utilities
from floe_core.telemetry.tracing import (
    create_span,
    get_tracer,
    reset_tracer,
    set_tracer,
    traced,
)

__all__: list[str] = [
    # Configuration models
    "TelemetryConfig",
    "ResourceAttributes",
    "SamplingConfig",
    "TelemetryAuth",
    "BatchSpanProcessorConfig",
    # Provider
    "TelemetryProvider",
    "ProviderState",
    # Semantic conventions
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
    # Propagation
    "configure_propagators",
    "get_propagator",
    "inject_context",
    "extract_context",
    "inject_headers",
    "create_context_from_headers",
    "set_baggage_value",
    "get_baggage_value",
    "set_floe_baggage",
    "get_current_span",
    "get_current_span_context",
    "get_trace_id",
    "get_span_id",
    "is_trace_active",
    # Baggage keys
    "BAGGAGE_NAMESPACE",
    "BAGGAGE_PRODUCT_NAME",
    "BAGGAGE_PRODUCT_VERSION",
    "BAGGAGE_MODE",
    # Tracing
    "traced",
    "create_span",
    "get_tracer",
    "set_tracer",
    "reset_tracer",
    # Sanitization
    "sanitize_error_message",
]
