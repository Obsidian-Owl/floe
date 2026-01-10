# Data Model: OpenTelemetry Integration

**Feature**: 001-opentelemetry
**Date**: 2026-01-09

## Overview

This document defines the Pydantic v2 models for OpenTelemetry configuration and the TelemetryBackendPlugin interface.

---

## Core Entities

### 1. TelemetryConfig

Central configuration for telemetry initialization. Included in CompiledArtifacts.

```python
class TelemetryConfig(BaseModel):
    """Configuration for OpenTelemetry telemetry emission.

    Included in CompiledArtifacts to configure telemetry in data pipelines.
    Platform Team configures via manifest.yaml; Data Engineers inherit.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = True
    otlp_endpoint: str = "http://otel-collector:4317"
    otlp_protocol: Literal["grpc", "http"] = "grpc"
    sampling_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    resource_attributes: ResourceAttributes
    authentication: TelemetryAuth | None = None
```

**Relationships**:
- Contains `ResourceAttributes` (service identification)
- Contains optional `TelemetryAuth` (authentication)
- Referenced by `CompiledArtifacts`

---

### 2. ResourceAttributes

Service identification attributes applied to all telemetry signals.

```python
class ResourceAttributes(BaseModel):
    """OpenTelemetry resource attributes for service identification.

    Applied to all traces, metrics, and logs from the service.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    service_name: str = Field(..., min_length=1, max_length=128)
    service_version: str = Field(..., pattern=r"^\d+\.\d+\.\d+.*$")
    deployment_environment: Literal["dev", "staging", "prod"]

    # Floe-specific semantic conventions (per ADR-0006)
    floe_namespace: str = Field(..., min_length=1, max_length=128)
    floe_product_name: str = Field(..., min_length=1, max_length=128)
    floe_product_version: str
    floe_mode: Literal["dev", "staging", "prod"]
```

**Validation Rules**:
- `service_name`: Required, 1-128 characters
- `service_version`: Semantic versioning pattern
- `floe_namespace`: Required, maps to Polaris catalog namespace

---

### 3. TelemetryAuth

Authentication for OTLP exports.

```python
class TelemetryAuth(BaseModel):
    """Authentication for OTLP exports.

    Supports API key and bearer token authentication.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    auth_type: Literal["api_key", "bearer"]
    api_key: SecretStr | None = None
    bearer_token: SecretStr | None = None
    header_name: str = "Authorization"

    @model_validator(mode="after")
    def validate_credentials(self) -> Self:
        if self.auth_type == "api_key" and not self.api_key:
            raise ValueError("api_key required when auth_type is api_key")
        if self.auth_type == "bearer" and not self.bearer_token:
            raise ValueError("bearer_token required when auth_type is bearer")
        return self
```

**Security**:
- Credentials use `SecretStr` (never logged)
- Loaded from environment variables at runtime

---

### 4. SamplingConfig

Environment-based sampling configuration.

```python
class SamplingConfig(BaseModel):
    """Sampling configuration per environment.

    Default ratios: dev=100%, staging=50%, prod=10%
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    dev: float = Field(default=1.0, ge=0.0, le=1.0)
    staging: float = Field(default=0.5, ge=0.0, le=1.0)
    prod: float = Field(default=0.1, ge=0.0, le=1.0)

    def get_ratio(self, environment: str) -> float:
        return getattr(self, environment, 1.0)
```

---

### 5. FloeSpanAttributes

Floe-specific span attributes (semantic conventions).

```python
class FloeSpanAttributes(BaseModel):
    """Floe semantic conventions for span attributes.

    Per ADR-0006: Every span MUST include floe.namespace.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(..., alias="floe.namespace")
    product_name: str = Field(..., alias="floe.product.name")
    product_version: str = Field(..., alias="floe.product.version")
    mode: Literal["dev", "staging", "prod"] = Field(..., alias="floe.mode")

    # Optional operation-specific attributes
    pipeline_id: str | None = Field(default=None, alias="floe.pipeline.id")
    job_type: str | None = Field(default=None, alias="floe.job.type")
    model_name: str | None = Field(default=None, alias="floe.dbt.model")
    asset_key: str | None = Field(default=None, alias="floe.dagster.asset")
```

---

## Plugin Interface

### 6. TelemetryBackendPlugin (ABC)

Abstract base class for pluggable telemetry backends.

```python
class TelemetryBackendPlugin(ABC):
    """Plugin interface for OTLP telemetry backends.

    Layer 3 (Backend) is PLUGGABLE via this interface.
    Platform teams select backend via manifest.yaml.

    Entry point: floe.telemetry_backends
    """

    # Plugin metadata (required)
    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        Returns:
            Dictionary for OTLP Collector config exporters section.
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for backend deployment.

        Returns:
            Helm values dict. Empty for SaaS backends.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate backend connectivity.

        Returns:
            True if backend reachable and credentials valid.
        """
        pass
```

---

## State Transitions

### TelemetryProvider Lifecycle

```
┌─────────────┐     initialize()     ┌──────────────┐
│ UNINITIALIZED│ ─────────────────> │ INITIALIZED  │
└─────────────┘                      └──────────────┘
                                            │
                                   force_flush()
                                            │
                                            v
                                     ┌──────────────┐
                                     │   FLUSHING   │
                                     └──────────────┘
                                            │
                                   shutdown()
                                            │
                                            v
                                     ┌──────────────┐
                                     │   SHUTDOWN   │
                                     └──────────────┘
```

**States**:
- `UNINITIALIZED`: SDK not initialized, API returns no-op
- `INITIALIZED`: Active telemetry emission
- `FLUSHING`: Force-flush in progress (graceful shutdown)
- `SHUTDOWN`: Provider closed, no more telemetry

---

## Entity Relationships

```
CompiledArtifacts (floe-core)
    └── TelemetryConfig
            ├── ResourceAttributes
            │       └── FloeSpanAttributes (semantic conventions)
            └── TelemetryAuth (optional)

TelemetryBackendPlugin (ABC)
    ├── JaegerTelemetryPlugin
    ├── DatadogTelemetryPlugin
    └── ConsoleTelemetryPlugin
```

---

## Validation Rules Summary

| Entity | Field | Rule |
|--------|-------|------|
| TelemetryConfig | sampling_ratio | 0.0 ≤ x ≤ 1.0 |
| TelemetryConfig | otlp_protocol | "grpc" or "http" |
| ResourceAttributes | service_name | 1-128 chars |
| ResourceAttributes | service_version | Semver pattern |
| TelemetryAuth | credentials | Required based on auth_type |
| FloeSpanAttributes | namespace | Required (per ADR-0006) |

---

## Contract Versioning

Adding `TelemetryConfig` to `CompiledArtifacts` is a **MINOR** change:
- New optional field
- Backward compatible
- Existing artifacts without telemetry continue to work

Version: `CompiledArtifacts 2.1.0` (from 2.0.0)
