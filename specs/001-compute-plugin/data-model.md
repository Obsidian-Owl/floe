# Data Model: Compute Plugin ABC with Multi-Compute Pipeline Support

**Date**: 2026-01-09
**Feature**: 001-compute-plugin

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ComputePlugin (ABC)                         │
│  (extends PluginMetadata, defines compute target interface)     │
├─────────────────────────────────────────────────────────────────┤
│  <<inherited from PluginMetadata>>                              │
│  + name: str                                                    │
│  + version: str                                                 │
│  + floe_api_version: str                                        │
│                                                                 │
│  <<abstract methods>>                                           │
│  + generate_dbt_profile(config) -> dict                         │
│  + get_required_dbt_packages() -> list[str]                     │
│  + validate_connection(config) -> ConnectionResult              │
│  + get_resource_requirements(workload_size) -> ResourceSpec     │
│  + get_catalog_attachment_sql(catalog_config) -> list[str]|None │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ implemented by
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DuckDBComputePlugin                           │
│  (reference implementation in plugins/floe-compute-duckdb/)     │
├─────────────────────────────────────────────────────────────────┤
│  + name = "duckdb"                                              │
│  + version = "0.1.0"                                            │
│  + floe_api_version = "1.0"                                     │
│  + generate_dbt_profile(config: DuckDBConfig) -> dict           │
│  + get_required_dbt_packages() -> ["dbt-duckdb>=1.9.0"]         │
│  + validate_connection(config) -> ConnectionResult              │
│  + get_resource_requirements(workload_size) -> ResourceSpec     │
│  + get_catalog_attachment_sql(catalog_config) -> list[str]      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      ComputeConfig                              │
│  (Pydantic model - configuration passed to plugin methods)      │
├─────────────────────────────────────────────────────────────────┤
│  + plugin: str                    # Plugin name (e.g., "duckdb")│
│  + timeout_seconds: int           # Query timeout (default: 3600)
│  + threads: int                   # Parallel threads (default: 4)
│  + connection: dict[str, Any]     # Plugin-specific connection  │
│  + credentials: dict[str, SecretStr]  # Runtime credentials     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ subclassed by
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DuckDBConfig                                 │
│  (DuckDB-specific configuration)                                │
├─────────────────────────────────────────────────────────────────┤
│  + plugin: Literal["duckdb"]      # Discriminator               │
│  + path: str                      # Database path (default: :memory:)
│  + memory_limit: str              # Max memory (default: "4GB") │
│  + extensions: list[str]          # Extensions to load          │
│  + attach: list[AttachConfig]     # Iceberg catalogs to attach  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    ConnectionResult                             │
│  (Return type from validate_connection())                       │
├─────────────────────────────────────────────────────────────────┤
│  + status: ConnectionStatus       # HEALTHY/DEGRADED/UNHEALTHY  │
│  + latency_ms: float              # Connection latency          │
│  + message: str                   # Status message              │
│  + warnings: list[str]            # Optional warnings           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      ResourceSpec                               │
│  (K8s resource requirements for dbt job pods)                   │
├─────────────────────────────────────────────────────────────────┤
│  + cpu_request: str               # CPU request (e.g., "100m")  │
│  + cpu_limit: str                 # CPU limit (e.g., "1000m")   │
│  + memory_request: str            # Memory request (e.g., "256Mi")
│  + memory_limit: str              # Memory limit (e.g., "1Gi")  │
│  + ephemeral_storage_request: str # Storage request             │
│  + ephemeral_storage_limit: str   # Storage limit               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Entities

### 1. ComputePlugin (ABC)

**Purpose**: Abstract base class defining the contract for compute target configuration. Generates dbt profiles.yml (dbt handles SQL execution), validates connections via native drivers, and provides K8s resource requirements.

**Inherits From**: `PluginMetadata`

| Method | Parameters | Return Type | Description |
|--------|------------|-------------|-------------|
| `generate_dbt_profile()` | `config: ComputeConfig` | `dict[str, Any]` | Generate dbt profiles.yml configuration |
| `get_required_dbt_packages()` | - | `list[str]` | Return required dbt adapter packages |
| `validate_connection()` | `config: ComputeConfig` | `ConnectionResult` | Test connection using native driver |
| `get_resource_requirements()` | `workload_size: str` | `ResourceSpec` | Return K8s resource requirements |
| `get_catalog_attachment_sql()` | `catalog_config: CatalogConfig` | `list[str] \| None` | Return SQL to attach Iceberg catalog |

**Validation Rules**:
- All abstract methods MUST be implemented by subclasses
- `generate_dbt_profile()` MUST return valid dbt profiles.yml structure
- `validate_connection()` MUST complete within 5 seconds (SC-007)

**Key Constraint**: ComputePlugin MUST NOT execute SQL directly - dbt adapters handle all SQL execution via profiles.yml configuration (FR-004a).

---

### 2. ComputeConfig (Pydantic Model)

**Purpose**: Configuration for a compute target, passed to `generate_dbt_profile()` and `validate_connection()`.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `plugin` | `str` | Yes | - | Compute plugin name (e.g., "duckdb") |
| `timeout_seconds` | `int` | No | 3600 | Query timeout in seconds |
| `threads` | `int` | No | 4 | Parallel query threads |
| `connection` | `dict[str, Any]` | No | `{}` | Plugin-specific connection settings |
| `credentials` | `dict[str, SecretStr]` | No | `{}` | Runtime credentials (resolved from env/secrets) |

**Validation Rules**:
- `plugin`: Non-empty string, must match a registered compute plugin
- `timeout_seconds`: ge=1, le=86400 (1 second to 24 hours)
- `threads`: ge=1, le=64
- `credentials`: All values must be `SecretStr` (never logged)

---

### 3. DuckDBConfig (Pydantic Model)

**Purpose**: DuckDB-specific compute configuration, extends ComputeConfig.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `plugin` | `Literal["duckdb"]` | Yes | `"duckdb"` | Discriminator for plugin type |
| `path` | `str` | No | `":memory:"` | Database path (`:memory:` for in-memory) |
| `memory_limit` | `str` | No | `"4GB"` | Maximum memory for DuckDB |
| `extensions` | `list[str]` | No | `[]` | Extensions to load (e.g., "iceberg", "httpfs") |
| `attach` | `list[AttachConfig]` | No | `[]` | Iceberg catalogs to attach |

**Validation Rules**:
- `path`: Valid file path or `:memory:`
- `memory_limit`: Must match pattern `^\d+(GB|MB)$`
- `extensions`: Each must be a valid DuckDB extension name

---

### 4. ConnectionResult (Pydantic Model)

**Purpose**: Structured result from `validate_connection()` health check.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | `ConnectionStatus` | Yes | - | Health status enum |
| `latency_ms` | `float` | Yes | - | Connection latency in milliseconds |
| `message` | `str` | No | `""` | Human-readable status message |
| `warnings` | `list[str]` | No | `[]` | Optional warning messages |

**Validation Rules**:
- `latency_ms`: ge=0 (non-negative)

---

### 5. ConnectionStatus (Enum)

**Purpose**: Health check result states.

| Value | Description |
|-------|-------------|
| `HEALTHY` | Connection successful, all checks passed |
| `DEGRADED` | Connection works but with issues (e.g., extension not loaded) |
| `UNHEALTHY` | Connection failed |

---

### 6. ResourceSpec (Pydantic Model)

**Purpose**: K8s resource requirements for dbt job pods.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `cpu_request` | `str` | No | `"100m"` | CPU request (K8s format) |
| `cpu_limit` | `str` | No | `"1000m"` | CPU limit (K8s format) |
| `memory_request` | `str` | No | `"256Mi"` | Memory request (K8s format) |
| `memory_limit` | `str` | No | `"1Gi"` | Memory limit (K8s format) |
| `ephemeral_storage_request` | `str` | No | `"100Mi"` | Ephemeral storage request |
| `ephemeral_storage_limit` | `str` | No | `"1Gi"` | Ephemeral storage limit |

**Validation Rules**:
- All values must match K8s resource format (e.g., `100m`, `1Gi`, `256Mi`)

**Presets**:
| Size | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| `small` | 100m | 500m | 256Mi | 512Mi |
| `medium` | 500m | 2000m | 1Gi | 4Gi |
| `large` | 2000m | 8000m | 4Gi | 16Gi |

---

### 7. CatalogConfig (Pydantic Model)

**Purpose**: Configuration for Iceberg catalog attachment (used by `get_catalog_attachment_sql()`).

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `catalog_type` | `str` | Yes | - | Catalog type (e.g., "rest", "glue") |
| `catalog_uri` | `str` | Yes | - | Catalog REST endpoint |
| `catalog_name` | `str` | Yes | - | Catalog name in floe platform |
| `warehouse` | `str` | No | `None` | S3 warehouse path |
| `credentials` | `dict[str, SecretStr]` | No | `{}` | OAuth2 or IAM credentials |

---

### 8. AttachConfig (Pydantic Model)

**Purpose**: Configuration for DuckDB ATTACH statement (Iceberg catalog attachment).

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `str` | Yes | - | Attach path (e.g., "iceberg:catalog_name") |
| `alias` | `str` | Yes | - | Database alias in DuckDB |
| `type` | `str` | No | `"iceberg"` | Attachment type |
| `options` | `dict[str, str]` | No | `{}` | Additional options (catalog_uri, etc.) |

---

## Error Entities

### ComputeError Hierarchy

```
ComputeError (base)
├── ComputeConnectionError   # Connection to compute target failed
├── ComputeTimeoutError      # Operation timed out
└── ComputeConfigurationError # Invalid compute configuration
```

| Exception | Raised When | Contains |
|-----------|-------------|----------|
| `ComputeConnectionError` | `validate_connection()` fails | plugin_name, original_error, correlation_id |
| `ComputeTimeoutError` | Connection or query exceeds timeout | plugin_name, timeout_seconds, correlation_id |
| `ComputeConfigurationError` | Config validation fails | plugin_name, validation_errors |

All exceptions include optional `correlation_id` for debugging (FR-023).

---

## Relationships

```
PluginMetadata  1 ──────── 1 ComputePlugin (inheritance)
                           (extends with compute-specific methods)

ComputePlugin   1 ──────── * ComputeConfig (uses)
                           (configuration passed to methods)

ComputeConfig   1 ──────── 0..* DuckDBConfig (specialization)
                           (plugin-specific subclasses)

ComputePlugin   * ──────── 1 ConnectionResult (returns)
                           (from validate_connection())

ComputePlugin   * ──────── 1 ResourceSpec (returns)
                           (from get_resource_requirements())

DuckDBConfig    1 ──────── * AttachConfig (contains)
                           (Iceberg catalog attachments)
```

---

## Data Flow

```
manifest.yaml (compute.approved, compute.default)
         │
         ▼
┌─────────────────┐
│  ComputeConfig  │ ◄──── Platform configuration
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ComputePlugin   │ ◄──── Plugin lookup via PluginRegistry
│  .generate_dbt_ │
│  profile()      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  profiles.yml   │ ◄──── dbt profiles.yml output
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ dbt-duckdb      │ ◄──── dbt adapter executes SQL
│ (dbt adapter)   │
└─────────────────┘
```

---

## Data Volume Assumptions

| Entity | Expected Count | Notes |
|--------|----------------|-------|
| ComputePlugin implementations | 5-10 | DuckDB, Snowflake, Spark, BigQuery, etc. |
| ComputeConfig instances | 1-5 per pipeline | Multi-compute pipeline support |
| ConnectionResult | Transient | Health check results, not persisted |
| ResourceSpec | 1 per compute target | Cached per workload size |

---

## Pydantic Models (Summary)

All Pydantic models use v2 syntax:

```python
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ConnectionStatus(Enum):
    """Health check status for compute connections."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ConnectionResult(BaseModel):
    """Result of validate_connection() health check."""
    model_config = ConfigDict(frozen=True)

    status: ConnectionStatus
    latency_ms: float = Field(..., ge=0)
    message: str = ""
    warnings: list[str] = Field(default_factory=list)


class ResourceSpec(BaseModel):
    """K8s resource requirements for dbt job pods."""
    model_config = ConfigDict(frozen=True)

    cpu_request: str = Field(default="100m")
    cpu_limit: str = Field(default="1000m")
    memory_request: str = Field(default="256Mi")
    memory_limit: str = Field(default="1Gi")
    ephemeral_storage_request: str = Field(default="100Mi")
    ephemeral_storage_limit: str = Field(default="1Gi")


class ComputeConfig(BaseModel):
    """Configuration for a compute target."""
    model_config = ConfigDict(extra="allow")

    plugin: str = Field(..., min_length=1)
    timeout_seconds: int = Field(default=3600, ge=1, le=86400)
    threads: int = Field(default=4, ge=1, le=64)
    connection: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, SecretStr] = Field(default_factory=dict)


class DuckDBConfig(ComputeConfig):
    """DuckDB-specific compute configuration."""
    plugin: Literal["duckdb"] = "duckdb"

    path: str = Field(default=":memory:")
    memory_limit: str = Field(default="4GB")
    extensions: list[str] = Field(default_factory=list)

    @field_validator("memory_limit")
    @classmethod
    def validate_memory_limit(cls, v: str) -> str:
        if not v.endswith(("GB", "MB")):
            raise ValueError("memory_limit must end with GB or MB")
        return v
```
