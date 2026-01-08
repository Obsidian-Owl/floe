# Data Model: Plugin Registry Foundation

**Date**: 2026-01-08
**Feature**: 001-plugin-registry

## Entity Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                       PluginRegistry                            │
│  (singleton, manages all plugin types)                          │
├─────────────────────────────────────────────────────────────────┤
│  - _discovered: dict[str, EntryPoint]                           │
│  - _loaded: dict[str, PluginMetadata]                           │
│  + discover_all()                                               │
│  + register(plugin: PluginMetadata)                             │
│  + get(type: PluginType, name: str) -> PluginMetadata           │
│  + list(type: PluginType) -> list[PluginMetadata]               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ manages instances of
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PluginMetadata (ABC)                         │
│  (base class for all 11 plugin type interfaces)                 │
├─────────────────────────────────────────────────────────────────┤
│  <<abstract>>                                                   │
│  + name: str                                                    │
│  + version: str                                                 │
│  + floe_api_version: str                                        │
│  + description: str                                             │
│  + dependencies: list[str]                                      │
│  + get_config_schema() -> type[BaseModel] | None                │
│  + health_check() -> HealthStatus                               │
│  + startup() -> None                                            │
│  + shutdown() -> None                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ComputePlugin  │ │OrchestratorPlugin│ │  CatalogPlugin  │
│     (ABC)       │ │      (ABC)       │ │      (ABC)      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
    ... + 8 more plugin type ABCs (11 total) ...
```

---

## Core Entities

### 1. PluginType (Enum)

**Purpose**: Enumeration of the 11 plugin categories.

| Value | Entry Point Group | Description |
|-------|-------------------|-------------|
| `COMPUTE` | `floe.computes` | Where dbt transforms execute |
| `ORCHESTRATOR` | `floe.orchestrators` | Job scheduling and execution |
| `CATALOG` | `floe.catalogs` | Iceberg table catalog |
| `STORAGE` | `floe.storage` | Object storage for Iceberg data |
| `TELEMETRY_BACKEND` | `floe.telemetry_backends` | OTLP telemetry backend |
| `LINEAGE_BACKEND` | `floe.lineage_backends` | OpenLineage backend |
| `DBT` | `floe.dbt` | dbt compilation environment |
| `SEMANTIC_LAYER` | `floe.semantic_layers` | Business intelligence API |
| `INGESTION` | `floe.ingestion` | Data loading from sources |
| `SECRETS` | `floe.secrets` | Credential management |
| `IDENTITY` | `floe.identity` | Authentication provider |

**Validation Rules**:
- Immutable (Enum)
- Each value maps to exactly one entry point group

---

### 2. PluginMetadata (ABC)

**Purpose**: Base abstract class for all plugins. Defines required metadata attributes.

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | Yes (abstract) | Plugin identifier (e.g., "duckdb", "dagster") |
| `version` | `str` | Yes (abstract) | Plugin version (semver format) |
| `floe_api_version` | `str` | Yes (abstract) | Required floe API version |
| `description` | `str` | No (default: "") | Human-readable description |
| `dependencies` | `list[str]` | No (default: []) | Required plugin names |

| Method | Return Type | Description |
|--------|-------------|-------------|
| `get_config_schema()` | `type[BaseModel] \| None` | Pydantic model for config validation |
| `health_check()` | `HealthStatus` | Check plugin health (default: healthy) |
| `startup()` | `None` | Lifecycle hook: initialization |
| `shutdown()` | `None` | Lifecycle hook: cleanup |

**Validation Rules**:
- `name`: Non-empty, alphanumeric with underscores/hyphens
- `version`: Valid semver format (X.Y.Z)
- `floe_api_version`: Valid semver format (X.Y)

**State Transitions**: N/A (stateless metadata)

---

### 3. PluginRegistry (Singleton)

**Purpose**: Central registry managing plugin discovery, registration, and lookup.

| Attribute | Type | Description |
|-----------|------|-------------|
| `_discovered` | `dict[str, EntryPoint]` | Entry points found during discovery |
| `_loaded` | `dict[str, PluginMetadata]` | Lazily loaded plugin instances |
| `_configs` | `dict[str, BaseModel]` | Validated plugin configurations |

| Method | Parameters | Return Type | Description |
|--------|------------|-------------|-------------|
| `discover_all()` | - | `None` | Scan all 11 entry point groups |
| `register()` | `plugin: PluginMetadata` | `None` | Manually register a plugin |
| `get()` | `type: PluginType, name: str` | `PluginMetadata` | Get plugin by type and name |
| `list()` | `type: PluginType` | `list[PluginMetadata]` | List all plugins of a type |
| `list_all()` | - | `dict[PluginType, list[str]]` | List all available plugins |
| `configure()` | `type: PluginType, name: str, config: dict` | `BaseModel` | Validate and store config |
| `health_check_all()` | - | `dict[str, HealthStatus]` | Check health of all loaded plugins |

**Identity/Uniqueness**:
- Plugin identity: `(PluginType, name)` tuple
- Duplicate registration raises `DuplicatePluginError`

**State Transitions**:
```
[Created] --discover_all()--> [Discovered] --get()/load--> [Loaded]
                                    │
                                    │ --configure()
                                    ▼
                              [Configured]
```

---

### 4. HealthStatus (DataClass)

**Purpose**: Structured health check response.

| Attribute | Type | Description |
|-----------|------|-------------|
| `state` | `HealthState` | HEALTHY, DEGRADED, or UNHEALTHY |
| `message` | `str` | Human-readable status message |
| `details` | `dict[str, Any]` | Additional diagnostic information |

---

### 5. HealthState (Enum)

**Purpose**: Health check result states.

| Value | Description |
|-------|-------------|
| `HEALTHY` | Plugin is fully operational |
| `DEGRADED` | Plugin is operational but with reduced capability |
| `UNHEALTHY` | Plugin is not operational |

---

## Error Entities

### PluginError Hierarchy

```
PluginError (base)
├── PluginNotFoundError      # Plugin not in registry
├── PluginIncompatibleError  # API version mismatch
├── PluginConfigurationError # Config validation failed
├── DuplicatePluginError     # Same type+name already registered
└── CircularDependencyError  # Circular dependency in plugin graph
```

| Exception | Raised When | Contains |
|-----------|-------------|----------|
| `PluginNotFoundError` | `get()` for non-existent plugin | plugin_type, plugin_name |
| `PluginIncompatibleError` | API version check fails | plugin_name, required_version, platform_version |
| `PluginConfigurationError` | Pydantic validation fails | plugin_name, validation_errors |
| `DuplicatePluginError` | `register()` with existing key | plugin_type, plugin_name |
| `CircularDependencyError` | Dependency resolution fails | cycle_path |

---

## Type-Specific Plugin ABCs

Each of the 11 plugin types extends `PluginMetadata` with type-specific methods. These are defined in `docs/architecture/plugin-system/interfaces.md`.

| Plugin ABC | Inherits From | Key Methods |
|------------|---------------|-------------|
| `ComputePlugin` | `PluginMetadata` | `generate_dbt_profile()`, `validate_connection()` |
| `OrchestratorPlugin` | `PluginMetadata` | `create_definitions()`, `create_assets_from_transforms()` |
| `CatalogPlugin` | `PluginMetadata` | `connect()`, `create_namespace()`, `vend_credentials()` |
| `StoragePlugin` | `PluginMetadata` | `get_pyiceberg_fileio()`, `get_warehouse_uri()` |
| `TelemetryBackendPlugin` | `PluginMetadata` | `get_otlp_exporter_config()`, `get_helm_values()` |
| `LineageBackendPlugin` | `PluginMetadata` | `get_transport_config()`, `get_namespace_strategy()` |
| `DBTPlugin` | `PluginMetadata` | `compile_project()`, `run_models()`, `test_models()` |
| `SemanticLayerPlugin` | `PluginMetadata` | `sync_from_dbt_manifest()`, `get_datasource_config()` |
| `IngestionPlugin` | `PluginMetadata` | `create_pipeline()`, `run()`, `get_destination_config()` |
| `SecretsPlugin` | `PluginMetadata` | `get_secret()`, `set_secret()`, `list_secrets()` |
| `IdentityPlugin` | `PluginMetadata` | `authenticate()`, `get_user_info()`, `validate_token()` |

---

## Relationships

```
PluginRegistry  1 ──────── * PluginMetadata
                           (manages lifecycle)

PluginMetadata  1 ──────── 0..1 ConfigSchema (Pydantic BaseModel)
                           (optional config validation)

PluginMetadata  * ──────── * PluginMetadata
                           (dependencies - resolved via topological sort)

PluginType      1 ──────── * PluginMetadata
                           (categorization)
```

---

## Data Volume Assumptions

| Entity | Expected Count | Notes |
|--------|----------------|-------|
| PluginType | 11 (fixed) | Enum, never changes at runtime |
| PluginMetadata instances | 10-50 | Typical deployment |
| Configurations | 10-50 | One per active plugin |
| Dependencies per plugin | 0-3 | Most plugins independent |

---

## Pydantic Models (Summary)

All Pydantic models use v2 syntax:

```python
from pydantic import BaseModel, ConfigDict, Field

class PluginInfo(BaseModel):
    """Serializable plugin information."""
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    floe_api_version: str
    plugin_type: PluginType
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    is_loaded: bool = False
    is_configured: bool = False
```
