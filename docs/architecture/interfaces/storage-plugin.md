# StoragePlugin

**Purpose**: Pluggable object storage backends (S3, GCS, Azure Blob, MinIO)
**Location**: `floe_core/interfaces/storage.py`
**Entry Point**: `floe.storage`
**ADR**: [ADR-0036: Storage Plugin Interface](../adr/0036-storage-plugin-interface.md)

StoragePlugin abstracts object storage using a neutral deployment binding backed
by the PyIceberg FileIO pattern. This enables multi-cloud portability, data
sovereignty compliance, and hybrid cloud deployments while keeping catalog,
compute, orchestrator, and Helm-specific translation out of the storage plugin.

**Key Pattern**: storage plugins emit secret-free storage desired state;
`floe-core` resolves compatibility and attaches typed deployment bindings;
consumer plugins translate those bindings into their owned deployment/runtime
surfaces.

## Composition Role

Storage plugins participate in Floe's composition resolver:

1. The storage plugin emits a neutral `StorageDeploymentBinding`.
2. The selected catalog plugin declares storage requirements.
3. `floe-core` validates compatibility and builds typed deployment bindings
   before deployment values are rendered.
4. Consumer plugins translate the neutral storage binding into their owned
   config.

For example, MinIO emits S3-compatible endpoint, bucket, path-style, STS
capability, provisioning intent, runtime fragments, and credential-ref facts.
Polaris translates those facts into `storageConfigInfo`; MinIO does not know
Polaris bootstrap JSON.

Storage credential capabilities use the shared composition vocabulary.
`credential_modes` may include `kubernetes-secret`, `external-secret-sync`,
`csi-secret-volume`, `environment`, `workload-identity`, and `none`.
`secret_projection_modes` and `identity_modes` describe how the selected
credential mode is realized through secrets or workload identity plugins. The
selected deployment credential mode must be one of the storage plugin's
declared modes before deployment bindings are rendered.

## Interface Definition

The snippet below shows the target semantic contract. The current migration-era
ABC may still expose legacy helper methods for dbt, Dagster, warehouse URI, and
Helm fragments until the plugin uplift tracker closes them out. Those helpers
are compatibility surface, not the architecture contract.

```python
from abc import ABC, abstractmethod
from typing import Any
from pyiceberg.io import FileIO
from floe_core.schemas.compiled_artifacts import StorageDeploymentBinding

class StoragePlugin(ABC):
    """Plugin interface for object storage backends.

    Storage plugins provide neutral storage deployment bindings and runtime
    FileIO configuration. Catalog, compute, orchestrator, and deployment
    plugins consume those bindings through their own translators.
    """

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def get_deployment_binding(self) -> StorageDeploymentBinding:
        """Return secret-free storage desired state for compilation.

        Returns:
            StorageDeploymentBinding containing protocol, endpoint roles,
            warehouse location, bucket requirements, credential references,
            capabilities, provisioning intent, and runtime FileIO facts.
        """
        pass

    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO:
        """Create PyIceberg FileIO instance for direct runtime use.

        This method remains useful for direct PyIceberg integrations. It is not
        the source of Helm, Polaris, dbt, or Dagster deployment config.
        """
        pass
```

Legacy helper methods for dbt, Dagster, or chart fragments may exist during
migration, but the target architecture is typed deployment bindings plus
consumer-owned translators. They are not the semantic contract.

## Reference Implementations

| Plugin | Description | Self-Hosted |
|--------|-------------|-------------|
| `MinIOStoragePlugin` | Self-hosted S3-compatible storage (on-premises, multi-cloud) | Yes |
| `GCSPlugin` | Google Cloud Storage | No |
| `AzureBlobPlugin` | Azure Blob Storage | No |

## Related Documents

- [ADR-0036: Storage Plugin Interface](../adr/0036-storage-plugin-interface.md)
- [Plugin Architecture](../plugin-system/index.md)
- [CatalogPlugin](catalog-plugin.md) - For catalog-storage coordination
- [Plugin Composition Uplift Tracker](../plugin-composition-uplift-tracker.md)
