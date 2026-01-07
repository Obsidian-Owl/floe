# Plugin Interface Reference

This directory contains the Abstract Base Class (ABC) definitions for all floe plugin interfaces. Plugins extend floe's capabilities while maintaining consistent contracts and composability.

Each interface defines the methods that plugin implementations must provide, enabling platform teams to swap implementations (e.g., DuckDB vs Snowflake compute, Dagster vs Airflow orchestration) without changing data product code.

> **Composability Principle**: See [ADR-0037](../adr/0037-composability-model.md) for how plugins compose to form complete platform configurations.

## Interface Overview

| Interface | Purpose | Location | ADR |
|-----------|---------|----------|-----|
| [ComputePlugin](compute-plugin.md) | Where dbt transforms execute | `floe_core/interfaces/compute.py` | [ADR-0010](../adr/0010-target-agnostic-compute.md) |
| [OrchestratorPlugin](orchestrator-plugin.md) | Job scheduling and execution | `floe_core/interfaces/orchestrator.py` | [ADR-0033](../adr/0033-orchestrator-plugin.md) |
| [CatalogPlugin](catalog-plugin.md) | Iceberg table catalog | `floe_core/interfaces/catalog.py` | [ADR-0008](../adr/0008-repository-split.md) |
| [StoragePlugin](storage-plugin.md) | Object storage (S3, GCS, Azure, MinIO) | `floe_core/interfaces/storage.py` | [ADR-0036](../adr/0036-storage-plugin-interface.md) |
| [TelemetryBackendPlugin](telemetry-backend-plugin.md) | OTLP telemetry backends (traces, metrics, logs) | `floe_core/interfaces/telemetry.py` | [ADR-0035](../adr/0035-observability-plugin-interface.md) |
| [LineageBackendPlugin](lineage-backend-plugin.md) | OpenLineage backends (data lineage) | `floe_core/interfaces/lineage.py` | [ADR-0035](../adr/0035-observability-plugin-interface.md) |
| [DBTPlugin](dbt-plugin.md) | dbt compilation environment (local/fusion/cloud) | `floe_core/interfaces/dbt.py` | [ADR-0043](../adr/0043-dbt-plugin.md) |
| [SemanticLayerPlugin](semantic-layer-plugin.md) | Business intelligence API | `floe_core/interfaces/semantic_layer.py` | [ADR-0001](../adr/0001-semantic-layer.md) |
| [IngestionPlugin](ingestion-plugin.md) | Data loading from sources | `floe_core/interfaces/ingestion.py` | [ADR-0020](../adr/0020-ingestion-plugins.md) |
| [DataQualityPlugin](data-quality-plugin.md) | Data quality validation | `floe_core/interfaces/data_quality.py` | [ADR-0044](../adr/0044-data-quality-plugin.md) |
| [SecretsPlugin](secrets-plugin.md) | Credential management | `floe_core/interfaces/secrets.py` | [ADR-0023](../adr/0023-secrets-management.md) |
| [IdentityPlugin](identity-plugin.md) | User authentication (OIDC) | `floe_core/interfaces/identity.py` | [ADR-0024](../adr/0024-identity-access-management.md) |

**Total:** 12 plugin interfaces (see [plugin-architecture.md](../plugin-architecture.md) for canonical registry)

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugin interfaces. See [ADR-0015](../adr/0015-policy-enforcer.md) and [ADR-0026](../adr/0026-data-contract-architecture.md).

## Plugin Metadata

All plugins must declare metadata for registration and compatibility checking:

```python
from dataclasses import dataclass
from typing import Final

FLOE_PLUGIN_API_VERSION: Final[str] = "1.0"

@dataclass
class PluginMetadata:
    """Metadata for plugin registration and compatibility checking."""
    name: str                   # Plugin name (e.g., "dagster")
    version: str                # Plugin version (e.g., "1.0.0")
    floe_api_version: str       # Required API version (e.g., "1.0")
    description: str            # Human-readable description
    author: str                 # Author/maintainer
    homepage: str | None = None # Plugin homepage URL
    license: str | None = None  # License identifier
```

## Related Documents

- [Plugin Architecture](../plugin-architecture.md) - Plugin structure, discovery, and registration
- [ADR-0037: Composability Model](../adr/0037-composability-model.md) - How plugins compose together
- [ADR-0008: Repository Split](../adr/0008-repository-split.md) - Plugin architecture origins
