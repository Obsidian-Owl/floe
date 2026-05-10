# Plugin Interface Reference

This directory contains the Abstract Base Class (ABC) definitions for floe plugin interfaces. Plugins extend floe's capabilities while maintaining consistent contracts and composability.

Each interface defines the methods that plugin implementations must provide, enabling platform teams to swap implementations (e.g., DuckDB vs Snowflake compute, Dagster vs Airflow orchestration) without changing data product code.

> **Composability Principle**: See [ADR-0037](../adr/0037-composability-principle.md) for how plugins compose to form complete platform configurations.
>
> **Category Count:** The implementation-truth plugin category list is [Plugin Catalog](../../reference/plugin-catalog.md). This interface reference documents the public ABC surface and may lag newly introduced implementation categories until their dedicated interface pages are published.
>
> **Source of Truth:** Live ABCs are under `packages/floe-core/src/floe_core/plugins/`. Code blocks in these pages are conceptual excerpts unless they explicitly say they are copied from a live file.

## Interface Overview

| Interface | Purpose | Location | ADR |
|-----------|---------|----------|-----|
| [ComputePlugin](compute-plugin.md) | Where dbt transforms execute | `packages/floe-core/src/floe_core/plugins/compute.py` | [ADR-0010](../adr/0010-target-agnostic-compute.md) |
| [OrchestratorPlugin](orchestrator-plugin.md) | Job scheduling and execution | `packages/floe-core/src/floe_core/plugins/orchestrator.py` | [ADR-0011](../adr/0011-pluggable-orchestration.md) |
| [CatalogPlugin](catalog-plugin.md) | Iceberg table catalog | `packages/floe-core/src/floe_core/plugins/catalog.py` | [ADR-0008](../adr/0008-repository-split.md) |
| [StoragePlugin](storage-plugin.md) | Object storage (S3-compatible, GCS, Azure, MinIO) | `packages/floe-core/src/floe_core/plugins/storage.py` | [ADR-0036](../adr/0036-storage-plugin-interface.md) |
| [TelemetryBackendPlugin](telemetry-backend-plugin.md) | OTLP telemetry backends (traces, metrics, logs) | `packages/floe-core/src/floe_core/plugins/telemetry.py` | [ADR-0035](../adr/0035-observability-plugin-interface.md) |
| [LineageBackendPlugin](lineage-backend-plugin.md) | OpenLineage backends (data lineage) | `packages/floe-core/src/floe_core/plugins/lineage.py` | [ADR-0035](../adr/0035-observability-plugin-interface.md) |
| [DBTPlugin](dbt-plugin.md) | dbt compilation environment (local/fusion/cloud) | `packages/floe-core/src/floe_core/plugins/dbt.py` | [ADR-0043](../adr/0043-dbt-runtime-abstraction.md) |
| [SemanticLayerPlugin](semantic-layer-plugin.md) | Business intelligence API | `packages/floe-core/src/floe_core/plugins/semantic.py` | [ADR-0001](../adr/0001-cube-semantic-layer.md) |
| [IngestionPlugin](ingestion-plugin.md) | Data loading from sources | `packages/floe-core/src/floe_core/plugins/ingestion.py` | [ADR-0020](../adr/0020-ingestion-plugins.md) |
| [DataQualityPlugin](data-quality-plugin.md) | Data quality validation | `packages/floe-core/src/floe_core/plugins/quality.py` | [ADR-0044](../adr/0044-unified-data-quality-plugin.md) |
| [SecretsPlugin](secrets-plugin.md) | Credential management | `packages/floe-core/src/floe_core/plugins/secrets.py` | [ADR-0023](../adr/0023-secrets-management.md) |
| [IdentityPlugin](identity-plugin.md) | User authentication (OIDC) | `packages/floe-core/src/floe_core/plugins/identity.py` | [ADR-0024](../adr/0024-identity-access-management.md) |

**Interface coverage:** This page documents the public plugin ABC reference surface. See [Plugin Catalog](../../reference/plugin-catalog.md) for the canonical `PluginType` category count and entry point groups.

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugin interfaces. See [ADR-0015](../adr/0015-policy-enforcement.md) and [ADR-0026](../adr/0026-data-contract-architecture.md).

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

- [Plugin Architecture](../plugin-system/index.md) - Plugin structure, discovery, and registration
- [ADR-0037: Composability Model](../adr/0037-composability-principle.md) - How plugins compose together
- [ADR-0008: Repository Split](../adr/0008-repository-split.md) - Plugin architecture origins
