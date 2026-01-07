# StoragePlugin

**Purpose**: Pluggable object storage backends (S3, GCS, Azure Blob, MinIO)
**Location**: `floe_core/interfaces/storage.py`
**Entry Point**: `floe.storage`
**ADR**: [ADR-0036: Storage Plugin Interface](../adr/0036-storage-plugin-interface.md)

StoragePlugin abstracts object storage using the PyIceberg FileIO pattern. This enables multi-cloud portability, data sovereignty compliance, and hybrid cloud deployments while maintaining consistent Iceberg table access.

**Key Pattern**: PyIceberg FileIO interface for industry-standard storage abstraction

## Interface Definition

```python
from abc import ABC, abstractmethod
from typing import Any
from pyiceberg.io import FileIO

class StoragePlugin(ABC):
    """Plugin interface for object storage backends.

    Storage plugins provide PyIceberg FileIO instances and configuration
    for dbt profiles, Dagster IOManagers, and Helm deployments.
    """

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO:
        """Create PyIceberg FileIO instance for this storage backend.

        Returns:
            Configured PyIceberg FileIO instance with credentials.
            Example for S3:
            S3FileIO(
                properties={
                    "s3.region": "us-east-1",
                    "s3.access-key-id": os.environ["AWS_ACCESS_KEY_ID"],
                    "s3.secret-access-key": os.environ["AWS_SECRET_ACCESS_KEY"]
                }
            )
        """
        pass

    @abstractmethod
    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for the given namespace.

        Args:
            namespace: Iceberg namespace (e.g., "bronze", "silver", "gold")

        Returns:
            Full warehouse URI for the namespace.
            Examples:
            - S3: "s3://my-bucket/warehouse/bronze"
            - GCS: "gs://my-bucket/warehouse/bronze"
            - Azure: "abfss://container@account.dfs.core.windows.net/warehouse/bronze"
            - MinIO: "s3://warehouse/bronze"
        """
        pass

    @abstractmethod
    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt profile storage configuration.

        Returns:
            Dictionary with storage-specific dbt profile config.
            Example for DuckDB + S3:
            {
                "external_location": "s3://my-bucket/warehouse/{namespace}",
                "s3_region": "us-east-1",
                "s3_access_key_id": "${AWS_ACCESS_KEY_ID}",
                "s3_secret_access_key": "${AWS_SECRET_ACCESS_KEY}"
            }
        """
        pass

    @abstractmethod
    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager storage configuration.

        Returns:
            Dictionary with storage config for Dagster IOManager.
            Example for S3:
            {
                "warehouse_location": "s3://my-bucket/warehouse",
                "io_config": {
                    "s3.region": "us-east-1",
                    "s3.access-key-id": "${AWS_ACCESS_KEY_ID}",
                    "s3.secret-access-key": "${AWS_SECRET_ACCESS_KEY}"
                }
            }
        """
        pass

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying storage services.

        Returns:
            Dictionary with Helm chart values for storage services.
            Example for MinIO:
            {
                "minio": {
                    "enabled": true,
                    "mode": "standalone",
                    "persistence": {"size": "100Gi"},
                    "resources": {"requests": {"memory": "4Gi"}}
                }
            }

            For cloud storage (S3, GCS, Azure), returns empty dict
            as no services need deployment.
        """
        pass
```

## Reference Implementations

| Plugin | Description | Self-Hosted |
|--------|-------------|-------------|
| `S3Plugin` | AWS S3 storage (production default) | No |
| `MinIOPlugin` | Self-hosted S3-compatible storage (on-premises, multi-cloud) | Yes |
| `GCSPlugin` | Google Cloud Storage | No |
| `AzureBlobPlugin` | Azure Blob Storage | No |

## Related Documents

- [ADR-0036: Storage Plugin Interface](../adr/0036-storage-plugin-interface.md)
- [Plugin Architecture](../plugin-system/index.md)
- [CatalogPlugin](catalog-plugin.md) - For catalog-storage coordination
