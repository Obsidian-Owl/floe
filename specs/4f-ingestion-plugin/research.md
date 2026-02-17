# Research: Epic 4F — Ingestion Plugin (dlt)

**Date**: 2026-02-07
**Spec**: `specs/4f-ingestion-plugin/spec.md`
**Prior Research**: migrated from legacy OMC research notes

## Prior Decisions (from Agent Memory & Research Synthesis)

| Decision | Rationale | Source |
|----------|-----------|--------|
| dlt v1.21.0 as implementation | Production-ready, Apache 2.0, native Iceberg+Polaris+Dagster integration, 30+ sources | Research synthesis |
| SinkConnector deferred to Epic 4G | Mixin pattern scored 8.2/10; zero breaking changes; keeps 4F focused | Epic 4F/4G research |
| IngestionPlugin ABC unchanged | Existing 3 abstract methods + 1 property sufficient; no breaking changes | Codebase analysis |
| CompiledArtifacts unchanged | `plugins.ingestion: PluginRef \| None` already in v0.5.0 | Codebase analysis |
| Orchestrator-agnostic plugin | All Dagster code in `plugins/floe-orchestrator-dagster/`; matches Epic 4E pattern | Clarification Round 2 |

## Technical Research

### 1. IngestionPlugin ABC (Existing — No Changes)

**File**: `packages/floe-core/src/floe_core/plugins/ingestion.py`

```python
@dataclass
class IngestionConfig:
    source_type: str
    source_config: dict[str, Any] = field(default_factory=lambda: {})
    destination_table: str = ""
    write_mode: str = "append"
    schema_contract: str = "evolve"

@dataclass
class IngestionResult:
    success: bool
    rows_loaded: int = 0
    bytes_written: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=lambda: [])

class IngestionPlugin(PluginMetadata):
    @property
    @abstractmethod
    def is_external(self) -> bool: ...

    @abstractmethod
    def create_pipeline(self, config: IngestionConfig) -> Any: ...

    @abstractmethod
    def run(self, pipeline: Any, **kwargs: Any) -> IngestionResult: ...

    @abstractmethod
    def get_destination_config(self, catalog_config: dict[str, Any]) -> dict[str, Any]: ...
```

**PluginMetadata** requires: `name`, `version`, `floe_api_version` properties, optional `startup()`, `shutdown()`, `health_check()`, `get_config_schema()`.

### 2. Plugin Entry Point Registration

**Pattern** (from Epic 4E/Cube):
```toml
[project.entry-points."floe.ingestion"]
dlt = "floe_ingestion_dlt:DltIngestionPlugin"
```

**PluginType enum**: `INGESTION = "floe.ingestion"` (already exists in `plugin_types.py`)

### 3. dlt Framework Integration

#### Pipeline Creation API
```python
pipeline = dlt.pipeline(
    pipeline_name="my_pipeline",     # Unique identifier, dlt state isolation
    destination="iceberg",           # Iceberg destination
    dataset_name="my_dataset",       # Maps to Iceberg namespace
)
load_info = pipeline.run(source_data, write_disposition="append")
```

#### Iceberg Destination Configuration
```python
# For Polaris REST catalog:
destination_config = {
    "catalog_type": "rest",
    "credentials": {
        "uri": "http://polaris:8181/api/catalog",
        "warehouse": "floe_warehouse",
    },
}
```

#### Schema Contracts
- `evolve`: Allow all schema changes (default)
- `freeze`: Block changes, raise error
- `discard_value`: Drop non-matching values
- Configurable per-resource or per-pipeline run

#### Incremental Loading
```python
@dlt.resource(primary_key="id")
def items(updated_at=dlt.sources.incremental("updated_at", initial_value="1970-01-01T00:00:00Z")):
    yield api.get_items(since=updated_at.start_value)
```
- Cursor state managed by dlt (persisted in destination)
- Automatic deduplication via `primary_key`
- Resumes from last cursor position after restart

#### Write Dispositions
- `append`: Additive loading (default)
- `replace`: Full refresh
- `merge`: Upsert with primary key support

#### Error Handling
- `PipelineStepFailed`: Step-level failure (extract/normalize/load)
- Terminal exceptions: Auth errors, missing config (NOT retried)
- Retry via `tenacity` with `retry_load()` helper

### 4. Dagster-dlt Integration (Orchestrator Plugin)

**Lives in `plugins/floe-orchestrator-dagster/`**, NOT in the ingestion plugin.

```python
from dagster_embedded_elt.dlt import DagsterDltResource, dlt_assets, DagsterDltTranslator

@dlt_assets(
    dlt_source=my_source(),
    dlt_pipeline=dlt.pipeline(...),
    dagster_dlt_translator=CustomTranslator(),
)
def ingestion_assets(context, dlt: DagsterDltResource):
    yield from dlt.run(context=context)
```

**Custom Translator** maps dlt resource names to `ingestion__{source}__{resource}` naming.

### 5. Orchestrator Wiring Pattern (from Epic 4E)

**File**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py`

Two-function pattern:
1. `create_X_resources(X_ref: PluginRef) -> dict[str, Any]` — core logic
2. `try_create_X_resources(plugins: ResolvedPlugins | None) -> dict[str, Any]` — safe wrapper

Called from `plugin.py::create_definitions()`:
```python
resources = self._create_iceberg_resources(validated.plugins)
semantic_resources = self._create_semantic_resources(validated.plugins)
resources.update(semantic_resources)
```

### 6. Test Infrastructure Patterns

**BasePluginDiscoveryTests**: 11 inherited tests for entry point registration, loading, metadata, ABC compliance
**BaseHealthCheckTests**: 11 inherited tests for health check compliance
**Fixture pattern**: Session-scoped config, function-scoped plugin with startup/shutdown lifecycle

### 7. Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `dlt[iceberg]` | `>=1.20.0,<2.0.0` | Core framework + Iceberg destination |
| `floe-core` | `>=0.1.0` | ABC, PluginMetadata, telemetry |
| `pydantic` | `>=2.0,<3.0` | Config validation |
| `structlog` | `>=24.0,<26.0` | Structured logging |
| `opentelemetry-api` | `>=1.0,<2.0` | OTel tracing |
| `tenacity` | `>=8.0,<10.0` | Retry logic |

**Orchestrator plugin additions**:
| Package | Version | Purpose |
|---------|---------|---------|
| `dagster-dlt` | `>=0.25.0` | Dagster-dlt integration (adds to existing orchestrator deps) |

## Resolved NEEDS CLARIFICATION

All clarifications were resolved during `/speckit.clarify`:
- Round 1: 8 questions (data sources, write modes, state, credentials, CLI, SinkConnector, source installation, multi-source)
- Round 2: 4 questions (orchestrator abstraction, FR language, data flow diagrams, coupling concerns)

No remaining unknowns.
