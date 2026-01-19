# Data Model: Epic 4B Dagster Orchestrator Plugin

**Date**: 2026-01-19
**Feature**: Dagster Orchestrator Plugin

## Entity Overview

This plugin primarily uses **existing dataclasses from floe-core**. No new entities are defined - the plugin implements the `OrchestratorPlugin` ABC and uses existing contracts.

## Existing Entities (from floe-core)

### OrchestratorPlugin (ABC)

**File**: `packages/floe-core/src/floe_core/plugins/orchestrator.py`

Abstract base class that DagsterOrchestratorPlugin must implement.

| Property/Method | Type | Description |
|----------------|------|-------------|
| `name` | `str` | Plugin identifier ("dagster") |
| `version` | `str` | Plugin semver ("0.1.0") |
| `floe_api_version` | `str` | Required floe API version ("1.0") |
| `create_definitions()` | `dict -> Any` | Generate Dagster Definitions |
| `create_assets_from_transforms()` | `list[TransformConfig] -> list[Any]` | Generate assets |
| `get_helm_values()` | `-> dict[str, Any]` | Helm chart values |
| `validate_connection()` | `-> ValidationResult` | Health check |
| `get_resource_requirements()` | `str -> ResourceSpec` | K8s resources |
| `emit_lineage_event()` | `-> None` | OpenLineage events |
| `schedule_job()` | `-> None` | Create schedules |

### TransformConfig (dataclass)

**File**: `packages/floe-core/src/floe_core/plugins/orchestrator.py`

Configuration for a dbt transform/model.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Model name (e.g., "stg_customers") |
| `path` | `str` | `""` | Path to model file |
| `schema_name` | `str` | `""` | Target schema |
| `materialization` | `str` | `"table"` | table, view, incremental |
| `tags` | `list[str]` | `[]` | Model tags |
| `depends_on` | `list[str]` | `[]` | Upstream model names |
| `meta` | `dict[str, Any]` | `{}` | Additional metadata |
| `compute` | `str \| None` | `None` | Compute target override |

### ValidationResult (dataclass)

**File**: `packages/floe-core/src/floe_core/plugins/orchestrator.py`

Result of connection validation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `success` | `bool` | required | Whether validation passed |
| `message` | `str` | `""` | Human-readable status |
| `errors` | `list[str]` | `[]` | Error messages |
| `warnings` | `list[str]` | `[]` | Warning messages |

### Dataset (dataclass)

**File**: `packages/floe-core/src/floe_core/plugins/orchestrator.py`

OpenLineage dataset representation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `namespace` | `str` | required | Dataset namespace (e.g., "floe-prod") |
| `name` | `str` | required | Dataset name (e.g., "bronze.raw_customers") |
| `facets` | `dict[str, Any]` | `{}` | OpenLineage facets |

### ResourceSpec (dataclass)

**File**: `packages/floe-core/src/floe_core/plugins/orchestrator.py`

Kubernetes resource requirements.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cpu_request` | `str` | `"100m"` | CPU request |
| `cpu_limit` | `str` | `"500m"` | CPU limit |
| `memory_request` | `str` | `"256Mi"` | Memory request |
| `memory_limit` | `str` | `"512Mi"` | Memory limit |

### CompiledArtifacts (Pydantic model)

**File**: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`

The SOLE cross-package contract consumed by the plugin.

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | Schema version ("0.2.0") |
| `metadata` | `CompilationMetadata` | Compilation info |
| `identity` | `ProductIdentity` | Product identity |
| `mode` | `DeploymentMode` | simple/centralized/mesh |
| `transforms` | `ResolvedTransforms \| None` | Transform configuration |
| `dbt_profiles` | `dict[str, Any] \| None` | dbt profiles.yml |
| `observability` | `ObservabilityConfig` | Telemetry settings |

### ResolvedModel (Pydantic model)

**File**: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`

Individual transform model with resolved compute.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Model identifier |
| `compute` | `str` | Resolved compute target (never None) |
| `tags` | `list[str] \| None` | Optional tags |
| `depends_on` | `list[str] \| None` | Optional dependencies |

## New Entity: DagsterOrchestratorPlugin (class)

The only new entity is the plugin implementation class itself.

**File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`

```python
class DagsterOrchestratorPlugin(OrchestratorPlugin):
    """Dagster orchestrator plugin for floe data platform."""

    # Class attributes
    _RESOURCE_PRESETS: dict[str, ResourceSpec]  # small/medium/large

    # Properties (required)
    name: str = "dagster"
    version: str = "0.1.0"
    floe_api_version: str = "1.0"
    description: str = "Dagster orchestrator for floe pipelines"

    # Methods (required - from ABC)
    def create_definitions(self, artifacts: dict[str, Any]) -> Definitions
    def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list[AssetsDefinition]
    def get_helm_values(self) -> dict[str, Any]
    def validate_connection(self) -> ValidationResult
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec
    def emit_lineage_event(event_type, job, inputs, outputs) -> None
    def schedule_job(job_name, cron, timezone) -> None
```

## State Transitions

### Plugin Lifecycle

```
[Not Discovered] → discover_all() → [Discovered] → get() → [Loaded] → activate() → [Active]
                                                                                      ↓
                                                              shutdown() ← [Shutting Down]
```

### Job Execution Lineage Events

```
[Pending] → emit_lineage_event("START") → [Running] → emit_lineage_event("COMPLETE") → [Succeeded]
                                              ↓
                                    emit_lineage_event("FAIL") → [Failed]
```

## Validation Rules

### TransformConfig Validation
- `name`: Must be non-empty, valid SQL identifier
- `materialization`: Must be one of: table, view, incremental, ephemeral
- `depends_on`: All referenced models must exist

### Schedule Validation
- `cron`: Must be valid 5-field cron expression (validated by croniter)
- `timezone`: Must be valid IANA timezone (validated by pytz)

### Workload Size Validation
- Must be one of: "small", "medium", "large"

## Relationships

```
CompiledArtifacts
    └─► ResolvedTransforms
            └─► ResolvedModel[] ─────────► TransformConfig[]
                                                  │
                                                  ▼
                                          DagsterOrchestratorPlugin
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                             Definitions    ResourceSpec   ValidationResult
                                    │
                            ┌───────┴───────┐
                            ▼               ▼
                    AssetsDefinition  ScheduleDefinition
```
