# Plugin Discovery and Registry

This document describes how floe discovers and registers plugins.

## Plugin Discovery

Plugins register via Python entry points:

```toml
# pyproject.toml
[project]
name = "floe-orchestrator-dagster"
version = "1.0.0"
dependencies = [
    "floe-core>=1.0.0",
    "dagster>=1.6.0",
]

[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterOrchestratorPlugin"

[project.entry-points."floe.charts"]
dagster = "floe_orchestrator_dagster:chart"
```

## Plugin Registry

```python
# floe_core/registry.py
from importlib.metadata import entry_points

class PluginRegistry:
    """Discovers and loads plugins via entry points."""

    def __init__(self):
        self._orchestrators: dict[str, type[OrchestratorPlugin]] = {}
        self._computes: dict[str, type[ComputePlugin]] = {}
        self._catalogs: dict[str, type[CatalogPlugin]] = {}
        self._storage: dict[str, type[StoragePlugin]] = {}
        self._telemetry_backends: dict[str, type[TelemetryBackendPlugin]] = {}
        self._lineage_backends: dict[str, type[LineageBackendPlugin]] = {}
        self._dbt: dict[str, type[DBTPlugin]] = {}
        self._semantic_layers: dict[str, type[SemanticLayerPlugin]] = {}
        self._ingestion: dict[str, type[IngestionPlugin]] = {}
        self._secrets: dict[str, type[SecretsPlugin]] = {}
        self._identity: dict[str, type[IdentityPlugin]] = {}

    def discover_all(self) -> None:
        """Scan all installed packages for floe.* entry points."""
        for group in [
            "floe.orchestrators",
            "floe.computes",
            "floe.catalogs",
            "floe.storage",
            "floe.telemetry_backends",
            "floe.lineage_backends",
            "floe.dbt",
            "floe.semantic_layers",
            "floe.ingestion",
            "floe.secrets",
            "floe.identity",
        ]:
            eps = entry_points(group=group)
            for ep in eps:
                plugin_class = ep.load()
                self._register(group, ep.name, plugin_class)

    def get_orchestrator(self, name: str) -> OrchestratorPlugin:
        """Get orchestrator plugin by name."""
        return self._orchestrators[name]()

    def list_available(self) -> dict[str, list[str]]:
        """List all available plugins by type (11 types total)."""
        return {
            "orchestrators": list(self._orchestrators.keys()),
            "computes": list(self._computes.keys()),
            "catalogs": list(self._catalogs.keys()),
            "storage": list(self._storage.keys()),
            "telemetry_backends": list(self._telemetry_backends.keys()),
            "lineage_backends": list(self._lineage_backends.keys()),
            "dbt": list(self._dbt.keys()),
            "semantic_layers": list(self._semantic_layers.keys()),
            "ingestion": list(self._ingestion.keys()),
            "secrets": list(self._secrets.keys()),
            "identity": list(self._identity.keys()),
        }
```

## Related Documents

- [Plugin Architecture Overview](index.md)
- [Plugin Interfaces](interfaces.md)
- [Lifecycle and Versioning](lifecycle.md)
