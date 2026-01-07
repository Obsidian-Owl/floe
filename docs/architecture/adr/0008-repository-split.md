# ADR-0008: Standalone Repository Architecture

## Status

Accepted

## Context

floe is designed as a **100% standalone open-source project**. We need to decide how to organize the codebase to:

- Enable community contribution
- Support enterprise self-hosting
- Allow external systems to integrate via contracts
- Maintain clear boundaries between enforced and pluggable components

Considerations:
- Apache 2.0 licensing throughout
- Plugin architecture for extensibility
- Contract-based integration for external orchestration systems
- Independent versioning

## Decision

Organize floe as a **single public repository** with:

1. **Core packages** - Enforced components (floe-core, floe-iceberg). Note: dbt framework is enforced, but dbt compilation environment is pluggable (ADR-0043)
2. **Plugins** - Pluggable components (compute, orchestrator, catalog, etc.)
3. **Contracts** - Well-defined interfaces for external integration

## Consequences

### Positive

- **Clear licensing** - Apache 2.0 for everything
- **Community contribution** - Open development, public roadmap
- **Enterprise option** - Self-host with any external orchestration
- **Extensible** - Plugin architecture for customization
- **Contract-based** - External systems integrate via documented contracts

### Negative

- **External integration complexity** - External systems must implement contracts
- **No managed option** - Users manage their own infrastructure

### Neutral

- Clear interface contracts (CompiledArtifacts, Observability)
- Semantic versioning for compatibility
- Comprehensive documentation required

## Repository Structure

```
floe/
├── floe-core/                           # Schemas, interfaces, enforcement engine
├── floe-cli/                            # CLI for Platform Team and Data Team
├── floe-dbt/                            # ENFORCED: dbt framework (compilation environment is pluggable)
├── floe-iceberg/                        # ENFORCED: Iceberg utilities (not pluggable)
│
├── plugins/                             # PLUGGABLE: Selected by Platform Team
│   ├── floe-compute-duckdb/            # Compute plugins
│   ├── floe-compute-spark/
│   ├── floe-compute-snowflake/
│   ├── floe-orchestrator-dagster/      # Orchestration plugins
│   ├── floe-orchestrator-airflow/
│   ├── floe-catalog-polaris/           # Catalog plugins
│   ├── floe-catalog-glue/
│   ├── floe-semantic-cube/             # Semantic layer plugins
│   ├── floe-ingestion-dlt/             # Ingestion plugins
│   └── floe-secrets-eso/               # Secrets plugins
│
├── charts/
│   ├── floe-platform/                  # Meta-chart: assembles plugin charts
│   └── floe-jobs/                      # Base chart for pipeline jobs
│
└── docs/                               # Runtime documentation
```

**Key Design Principle**: Only ENFORCED components (Iceberg, OpenTelemetry, OpenLineage) live at the top level. All PLUGGABLE components follow the plugin pattern under `plugins/`. Note: dbt framework integration (floe-dbt) is core but uses pluggable DBTPlugin for execution (ADR-0043). See [ADR-0016](0016-platform-enforcement-architecture.md) for the platform enforcement architecture.

### Out of Scope (Deferred)

| Component | Status | Rationale |
|-----------|--------|-----------|
| **Synthetic Data (SDV)** | Deferred | Requires ML infrastructure, future plugin |
| **Flink streaming** | Deferred | Design for extensibility, implement later. See [ADR-0014](0014-flink-streaming-deferred.md) |

The runtime executes pipelines on whatever data exists (real, synthetic, or test fixtures).

## Integration Contracts

External systems can integrate with floe through well-defined contracts documented in [`docs/contracts/`](../../contracts/index.md):

| Contract | Location | Purpose |
|----------|----------|---------|
| [CompiledArtifacts](../../contracts/compiled-artifacts.md) | `floe/floe-core` (Pydantic) | Runtime configuration schema |
| [Observability Attributes](../../contracts/observability-attributes.md) | Documented in contracts | OpenTelemetry/OpenLineage conventions |
| floe.yaml Schema | `floe/floe-core` | User-facing config format |
| Helm Values | `floe/charts` | Runtime deployment config |

### Contract Ownership

- **Runtime-owned contracts**: Defined as Pydantic models in floe-core, exported as JSON Schema
- **Standard contracts**: OpenTelemetry and OpenLineage follow industry standards

## Versioning Strategy

- Semantic versioning (MAJOR.MINOR.PATCH)
- Breaking changes require major version bump
- Plugin API versioning for compatibility

## Plugin Architecture

Each plugin is a self-contained package with:

1. **Python code** (`src/`) - implements the ABC interface from floe-core
2. **Helm chart** (`chart/`) - deploys the service (if applicable)
3. **Entry point** - registered via pyproject.toml

### Plugin Structure

```
plugins/floe-orchestrator-dagster/
├── src/
│   ├── __init__.py
│   └── plugin.py           # DagsterOrchestratorPlugin class
├── chart/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── webserver.yaml
│       ├── daemon.yaml
│       └── services.yaml
└── pyproject.toml          # Entry point registration
```

### Plugin Discovery via Entry Points

Plugins register via Python entry points (standard, proven pattern used by pytest, Dagster, DataHub):

```toml
# plugins/floe-orchestrator-dagster/pyproject.toml
[project]
name = "floe-orchestrator-dagster"
version = "1.0.0"
dependencies = ["floe-core>=1.0.0", "dagster>=1.6.0"]

[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterOrchestratorPlugin"

[project.entry-points."floe.charts"]
dagster = "floe_orchestrator_dagster:chart"
```

### Plugin Registry

```python
# floe_core/registry.py
class PluginRegistry:
    """Discovers and loads plugins via entry points."""

    def discover_all(self) -> None:
        """Scan all installed packages for floe.* entry points."""
        ...

    def get_orchestrator(self, name: str) -> OrchestratorPlugin:
        """Get orchestrator plugin by name."""
        ...

    def get_compute(self, name: str) -> ComputePlugin:
        """Get compute plugin by name."""
        ...

    def list_available(self) -> dict[str, list[str]]:
        """List all available plugins by type."""
        ...

    def validate_manifest(self, manifest: Manifest) -> list[str]:
        """Validate manifest config against available plugins."""
        ...
```

## Plugin API Versioning

To ensure compatibility between floe-core and plugins:

### Version Declaration

```python
# floe_core/plugin_api.py
from typing import Final

FLOE_PLUGIN_API_VERSION: Final[str] = "1.0"
FLOE_PLUGIN_API_MIN_VERSION: Final[str] = "1.0"
```

### Plugin Metadata

```python
# Every plugin must declare API compatibility
from dataclasses import dataclass

@dataclass
class PluginMetadata:
    name: str                   # e.g., "dagster"
    version: str                # Plugin version, e.g., "1.0.0"
    floe_api_version: str       # Required - checked at load time
    description: str
    author: str
```

### Compatibility Check

```python
# floe_core/registry.py
def load_plugin(self, entry_point) -> Plugin:
    plugin_class = entry_point.load()
    metadata = plugin_class.metadata

    # Check API version compatibility
    if not is_compatible(metadata.floe_api_version, FLOE_PLUGIN_API_MIN_VERSION):
        raise PluginIncompatibleError(
            f"Plugin {metadata.name} requires API v{metadata.floe_api_version}, "
            f"but minimum supported is v{FLOE_PLUGIN_API_MIN_VERSION}"
        )

    return plugin_class()
```

### Breaking vs Non-Breaking Changes

| Change Type | API Version Impact | Example |
|-------------|-------------------|---------|
| Add optional method | Minor (1.0 → 1.1) | Add `health_check()` with default impl |
| Add required method | Major (1.0 → 2.0) | Add abstract `validate()` method |
| Remove method | Major (1.0 → 2.0) | Remove deprecated `old_method()` |
| Change signature | Major (1.0 → 2.0) | Change `run(config)` to `run(config, context)` |

## Plugin Types

| Type | Entry Point | Example Plugins |
|------|-------------|-----------------|
| Compute | `floe.computes` | duckdb, spark, snowflake, databricks, bigquery |
| Orchestrator | `floe.orchestrators` | dagster, airflow |
| Catalog | `floe.catalogs` | polaris, glue, hive |
| Semantic Layer | `floe.semantic_layers` | cube, none |
| Ingestion | `floe.ingestion` | dlt, airbyte |
| Secrets | `floe.secrets` | eso, vault, k8s |

## References

- [Open Core Model](https://en.wikipedia.org/wiki/Open-core_model)
- [GitLab's Open Core](https://about.gitlab.com/company/stewardship/)
- [Python Entry Points](https://packaging.python.org/en/latest/specifications/entry-points/)
- [ADR-0016](0016-platform-enforcement-architecture.md) - Platform enforcement architecture
