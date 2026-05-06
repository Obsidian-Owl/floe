# ADR-0036: Storage Plugin Interface

## Status

Accepted

## Context

floe uses **Apache Iceberg** as the enforced table format (ADR-0005). Iceberg tables require object storage (S3, GCS, Azure Blob, etc.) for data files and metadata.

### The Problem: Hardcoded Storage Configuration

Current implementations assume specific storage backends:

```python
# Hardcoded S3 assumption
catalog = load_catalog(
    "polaris",
    warehouse="s3://my-bucket/warehouse"  # S3-specific
)
```

**Issues with this approach:**
1. **Cloud provider lock-in**: S3 syntax doesn't work for GCS (`gs://`) or Azure (`abfss://`)
2. **Credential management**: Different auth for AWS (IAM), GCS (service account), Azure (SAS)
3. **Testing complexity**: Cannot easily swap MinIO for local evaluation and a validated cloud object-storage backend for production
4. **Enterprise requirements**: Some organizations require specific storage (on-prem, multi-cloud)

### Organizations Have Different Storage Needs

| Organization Type | Storage Backend | Rationale |
|-------------------|----------------|-----------|
| **AWS-first** | S3 | Native AWS integration, lowest latency |
| **GCP-first** | GCS | Native GCP integration, existing buckets |
| **Azure-first** | Azure Blob | Native Azure integration, compliance |
| **Local development** | MinIO | S3-compatible, runs in Kind cluster |
| **Multi-cloud** | Multiple (S3 + GCS) | Disaster recovery, vendor diversification |
| **On-premises** | S3-compatible (NetApp, Dell) | Data sovereignty, compliance |

**Requirement:** Storage backends must be **pluggable**, not hardcoded paths.

### PyIceberg FileIO Pattern

PyIceberg (the Python library for Iceberg) uses the **FileIO** pattern for storage abstraction:

```python
from pyiceberg.io import FileIO

class FileIO(ABC):
    """Abstract base class for file I/O operations."""

    @abstractmethod
    def new_input(self, path: str) -> InputFile:
        """Create input file for reading."""
        pass

    @abstractmethod
    def new_output(self, path: str) -> OutputFile:
        """Create output file for writing."""
        pass
```

**Implementations:**
- `S3FileIO` - AWS S3 (boto3)
- `GCSFileIO` - Google Cloud Storage (gcs-python)
- `AzureFileIO` - Azure Blob Storage (azure-storage-blob)
- `LocalFileIO` - Local filesystem (testing)

**This is the pattern we should follow.**

## Decision

Create **StoragePlugin interface** that wraps PyIceberg FileIO for pluggable storage backends.

### 2026-05 Composition Update

The target interface is now a neutral storage deployment binding plus
composition resolver, not storage-owned projections for every consumer.

The original interface correctly identified the storage plugin boundary, but
methods such as `get_dbt_profile_config()`, `get_dagster_io_manager_config()`,
and `get_helm_values_override()` encourage storage plugins to know too much
about compute, orchestration, catalog, and deployment renderers. That creates an
N x M coupling problem as new catalogs and storage backends are added.

The revised rule is:

```text
StoragePlugin emits StorageDeploymentBinding.
CatalogPlugin declares storage requirements and emits CatalogDeploymentBinding.
Compute and orchestrator plugins consume runtime storage facts.
floe-core validates compatibility through the composition resolver.
Helm renders resolved deployment bindings.
```

Legacy helper methods can remain during migration, but they are not the
semantic contract.

### StoragePlugin Interface

```python
from abc import ABC, abstractmethod
from typing import Any
from pyiceberg.io import FileIO


class StoragePlugin(ABC):
    """Plugin interface for storage backends.

    Wraps PyIceberg FileIO pattern to provide:
    - PyIceberg-compatible FileIO instance
    - Credential management
    - Helm values for deploying storage services (if self-hosted)

    Plugin Lifecycle:
    1. Discovered via entry point: floe.storage
    2. Instantiated by PluginRegistry
    3. Invoked during compilation (generates dbt profiles, Dagster IOManager config)
    4. Invoked during deployment (generates Helm values for MinIO, etc.)
    """

    # Plugin metadata
    name: str                 # e.g., "minio", "gcs", "azure"
    version: str              # Plugin version (semver)
    floe_api_version: str     # Supported floe-core API version

    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO:
        """Create PyIceberg FileIO instance for this storage backend.

        Returns:
            FileIO instance (S3FileIO, GCSFileIO, AzureFileIO, etc.)

        Example (MinIO using S3 protocol):
            from pyiceberg.io.pyarrow import PyArrowFileIO
            return PyArrowFileIO(
                {
                    "s3.endpoint": "https://s3.amazonaws.com",
                    "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID"),
                    "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                }
            )

        Example (MinIO):
            return PyArrowFileIO(
                {
                    "s3.endpoint": "http://minio:9000",
                    "s3.access-key-id": "minioadmin",
                    "s3.secret-access-key": "minioadmin",
                    "s3.path-style-access": "true",  # MinIO requires path-style
                }
            )
        """
        pass

    @abstractmethod
    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for Iceberg catalog.

        Args:
            namespace: Catalog namespace (e.g., "bronze", "silver", "gold")

        Returns:
            Storage URI for warehouse location

        Example (S3):
            "s3://my-bucket/warehouse/bronze"

        Example (GCS):
            "gs://my-bucket/warehouse/bronze"

        Example (Azure):
            "abfss://container@account.dfs.core.windows.net/warehouse/bronze"

        Example (MinIO):
            "s3://warehouse/bronze"  # Path-style, no bucket in URI
        """
        pass

    @abstractmethod
    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt profile configuration for this storage backend.

        For dbt-duckdb with Polaris plugin, this provides the 'filesystems'
        config that tells DuckDB how to access Iceberg data files.

        Returns:
            Dictionary with storage-specific config for dbt profiles.yml

        Example (S3):
            {
                "filesystems": {
                    "s3": {
                        "key_id": "${env:AWS_ACCESS_KEY_ID}",
                        "secret": "${env:AWS_SECRET_ACCESS_KEY}",
                        "region": "us-east-1"
                    }
                }
            }

        Example (GCS):
            {
                "filesystems": {
                    "gcs": {
                        "credential": "${env:GOOGLE_APPLICATION_CREDENTIALS}"
                    }
                }
            }
        """
        pass

    @abstractmethod
    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager configuration.

        For Dagster's Iceberg IOManager, this provides storage-specific
        configuration.

        Returns:
            Dictionary with storage config for Dagster IOManager

        Example (S3):
            {
                "storage_options": {
                    "aws_access_key_id": "${env:AWS_ACCESS_KEY_ID}",
                    "aws_secret_access_key": "${env:AWS_SECRET_ACCESS_KEY}",
                    "region_name": "us-east-1"
                }
            }
        """
        pass

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying storage services.

        For self-hosted storage (MinIO), this provides Helm chart values.
        For cloud storage (S3, GCS, Azure), this returns empty dict.

        Returns:
            Helm values dictionary for storage chart.
            Empty dict if storage is external (cloud).

        Example (MinIO self-hosted):
            {
                "minio": {
                    "enabled": true,
                    "mode": "standalone",
                    "rootUser": "minioadmin",
                    "rootPassword": "minioadmin",
                    "persistence": {
                        "enabled": true,
                        "size": "10Gi"
                    }
                }
            }

        Example (S3 cloud):
            {}  # No services to deploy
        """
        pass

    def validate_credentials(self) -> bool:
        """Validate storage credentials are configured.

        Optional method. Plugins can override to check credentials
        before deployment (e.g., verify AWS_ACCESS_KEY_ID).

        Returns:
            True if credentials valid, False otherwise.
        """
        return True  # Default: no validation
```

### Plugin Registration

```python
# pyproject.toml for the implemented floe-storage-minio plugin
[project.entry-points."floe.storage"]
minio = "floe_storage_minio.plugin:MinIOStoragePlugin"
```

### Platform Configuration

```yaml
# manifest.yaml
plugins:
  storage: minio  # Plugin name (discovered via entry points)

# Compiler discovers plugin and invokes methods:
# 1. get_pyiceberg_fileio() → creates FileIO for PyIceberg catalog
# 2. get_warehouse_uri("bronze") → generates "s3://bucket/warehouse/bronze"
# 3. get_dbt_profile_config() → adds filesystems config to dbt profiles.yml
# 4. get_dagster_io_manager_config() → adds storage_options to IOManager
```

## Consequences

### Positive

- **Composability** - Storage backends are plugins, not hardcoded paths (ADR-0037)
- **PyIceberg alignment** - Follows industry-standard FileIO pattern
- **Cloud portability** - Same code works on AWS, GCP, Azure, on-prem
- **Testing efficiency** - Swap MinIO for local evaluation and a validated cloud object-storage backend for production
- **Credential security** - Centralized credential management per backend
- **Multi-cloud support** - Future: Multiple storage plugins per platform

### Negative

- **Abstraction overhead** - More files/classes than hardcoded URIs
- **Plugin development** - Requires implementing ABC for each backend
- **FileIO complexity** - PyIceberg FileIO API has learning curve
- **Initial setup** - Must install plugin package (e.g., `pip install floe-storage-minio`)

### Neutral

- **Implemented storage plugin** - `floe-storage-minio` supports MinIO using S3-compatible protocol settings
- **Provider-native plugins** - GCS or Azure plugins are future/provider-specific extensions, not alpha-shipped packages
- **Migration path** - Existing hardcoded URIs can coexist during transition

## Implementation Details

### Reference Implementation Excerpt: MinIOStoragePlugin

The production implementation in `plugins/floe-storage-minio` is the source of
truth. This excerpt shows the public plugin shape and S3-compatible runtime
configuration methods that architecture consumers depend on.

```python
# floe-storage-minio/src/floe_storage_minio/plugin.py
from typing import Any
from pydantic import BaseModel
from floe_core.plugin_errors import PluginConfigurationError
from floe_core.plugins import StoragePlugin
from floe_storage_minio.config import MinIOStorageConfig


class MinIOStoragePlugin(StoragePlugin):
    """Storage plugin for MinIO."""

    def __init__(self, config: MinIOStorageConfig | None = None) -> None:
        """Initialize MinIO storage plugin with validated config."""
        super().__init__()
        self._config = config

    @property
    def name(self) -> str:
        return "minio"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    @property
    def description(self) -> str:
        return "MinIO object storage plugin for Iceberg data"

    @property
    def tracer_name(self) -> str:
        return "floe.storage.minio"

    def get_config_schema(self) -> type[BaseModel]:
        return MinIOStorageConfig

    def _get_pyiceberg_s3_properties(self) -> dict[str, str]:
        config = self._require_config()
        return {
            "s3.endpoint": config.endpoint,
            "s3.region": config.region,
            "s3.path-style-access": str(config.path_style_access).lower(),
        }

    def _require_config(self) -> MinIOStorageConfig:
        if self._config is None:
            raise PluginConfigurationError(
                "minio",
                [{"field": "_config", "message": "Plugin 'minio' not configured"}],
            )
        return self._config

    def get_pyiceberg_fileio(self):
        """Create PyIceberg FileIO for MinIO using S3-compatible keys."""
        from pyiceberg.io.fsspec import FsspecFileIO

        return FsspecFileIO(properties=self._get_pyiceberg_s3_properties())

    def get_pyiceberg_catalog_config(self) -> dict[str, Any]:
        """Return PyIceberg catalog config for S3-backed table loading."""
        return self._get_pyiceberg_s3_properties()

    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate S3-compatible warehouse URI."""
        config = self._require_config()
        return f"s3://{config.bucket}/{namespace}/"

    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt-duckdb S3-compatible filesystem config."""
        config = self._require_config()
        return {
            "s3_region": config.region,
            "s3_endpoint": config.endpoint,
            "s3_path_style_access": config.path_style_access,
            "s3_access_key_id": '{{ env_var("AWS_ACCESS_KEY_ID") }}',
            "s3_secret_access_key": '{{ env_var("AWS_SECRET_ACCESS_KEY") }}',
        }

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager S3-compatible config."""
        config = self._require_config()
        return {
            "bucket": config.bucket,
            "endpoint_url": config.endpoint,
            "region_name": config.region,
            "path_style_access": config.path_style_access,
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        """Return Helm overrides; the platform chart deploys MinIO."""
        return {}
```

### MinIO Configuration Example

MinIO uses the implemented `MinIOStoragePlugin` with a MinIO endpoint and
path-style access. The plugin keeps S3-compatible protocol settings for
PyIceberg and runtime integrations.

```yaml
plugins:
  storage:
    type: minio
    config:
      endpoint: http://floe-platform-minio:9000
      bucket: floe-data
      region: us-east-1
      path_style_access: true
```

### Future Provider-Native Example: GCSPlugin

```python
# floe-storage-gcs/src/floe_storage_gcs/plugin.py
from __future__ import annotations

import os
from typing import Any
from pyiceberg.io.pyarrow import PyArrowFileIO
from floe_core.plugins import StoragePlugin


class GCSPlugin(StoragePlugin):
    """Storage plugin for Google Cloud Storage."""

    name = "gcs"
    version = "0.1.0"
    floe_api_version = "2.0.0"

    def __init__(self, bucket: str = "floe-warehouse", project: str | None = None):
        """Initialize GCS plugin.

        Args:
            bucket: GCS bucket name
            project: GCP project ID (optional, uses default if not set)
        """
        self.bucket = bucket
        self.project = project or os.getenv("GCP_PROJECT", "")

    def get_pyiceberg_fileio(self) -> PyArrowFileIO:
        """Create PyIceberg FileIO for GCS."""
        return PyArrowFileIO(
            {
                "gcs.project-id": self.project,
                "gcs.oauth2.token-provider-type": "service-account",
                "gcs.oauth2.service-account-file": os.getenv(
                    "GOOGLE_APPLICATION_CREDENTIALS", ""
                ),
            }
        )

    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate GCS warehouse URI."""
        return f"gs://{self.bucket}/warehouse/{namespace}"

    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt-duckdb GCS filesystems config."""
        return {
            "filesystems": {
                "gcs": {
                    "credential": "${env:GOOGLE_APPLICATION_CREDENTIALS}",
                }
            }
        }

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager GCS config."""
        return {
            "storage_options": {
                "token": "${env:GOOGLE_APPLICATION_CREDENTIALS}",
            }
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        """No services to deploy for GCS (cloud)."""
        return {}  # External cloud storage

    def validate_credentials(self) -> bool:
        """Validate GCP credentials are set."""
        return "GOOGLE_APPLICATION_CREDENTIALS" in os.environ
```

## Decision Criteria: When to Create Plugin vs Configuration

Per ADR-0037 (Composability Principle):

| Scenario | Decision | Rationale |
|----------|----------|-----------|
| Multiple storage backends exist | **Plugin** ✅ | S3, GCS, Azure, MinIO all valid |
| Organization may swap storage | **Plugin** ✅ | Start with MinIO for local evaluation, then validate the chosen S3-compatible cloud backend |
| Storage requires different credentials | **Plugin** ✅ | AWS IAM ≠ GCS service account ≠ Azure SAS |
| Storage-specific features | **Plugin** ✅ | S3 Transfer Acceleration, GCS lifecycle policies |

**Not configuration because:**
- Storage URIs differ (`s3://` vs `gs://` vs `abfss://`)
- Credential mechanisms differ (IAM vs service account vs SAS)
- PyIceberg FileIO implementations differ (S3FileIO vs GCSFileIO)

## Integration with Other Components

### dbt Integration

```yaml
# dbt profiles.yml (generated by compiler via StoragePlugin)
floe:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: /tmp/floe.duckdb
      plugins:
        - module: dbt_duckdb_polaris
          config:
            catalog:
              uri: http://polaris:8181
            filesystems:  # From StoragePlugin.get_dbt_profile_config()
              s3:
                key_id: ${AWS_ACCESS_KEY_ID}
                secret: ${AWS_SECRET_ACCESS_KEY}
                region: us-east-1
```

### Dagster Integration

```python
# Dagster definitions (generated by compiler via StoragePlugin)
from dagster import Definitions
from dagster_iceberg import IcebergIOManager

defs = Definitions(
    assets=assets,
    resources={
        "io_manager": IcebergIOManager(
            catalog_uri="http://polaris:8181",
            warehouse="s3://floe-warehouse/bronze",
            storage_options={  # From StoragePlugin.get_dagster_io_manager_config()
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "region_name": "us-east-1",
            },
        )
    },
)
```

### PyIceberg Catalog Integration

```python
# Catalog loading (generated by compiler via StoragePlugin)
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "polaris",
    type="rest",
    uri="http://polaris:8181",
    warehouse=storage_plugin.get_warehouse_uri("bronze"),  # "s3://bucket/warehouse/bronze"
    io_impl=storage_plugin.get_pyiceberg_fileio(),  # S3FileIO instance
)
```

## Testing Strategy

### Unit Tests (Mock Plugin)

```python
# tests/unit/test_storage_plugin.py
from unittest.mock import Mock
from floe_core.plugins import StoragePlugin


def test_compiler_with_mock_storage():
    """Test compiler with mocked storage plugin."""
    mock_plugin = Mock(spec=StoragePlugin)
    mock_plugin.get_warehouse_uri.return_value = "s3://test-bucket/warehouse/bronze"
    mock_plugin.get_dbt_profile_config.return_value = {"filesystems": {"s3": {}}}

    compiler = Compiler(storage_plugin=mock_plugin)
    artifacts = compiler.compile(spec)

    assert artifacts.dbt_profiles["floe"]["outputs"]["dev"]["plugins"]
    mock_plugin.get_warehouse_uri.assert_called_once_with("bronze")
```

### Integration Tests (Real Plugin)

```python
# tests/integration/test_minio_plugin.py
from floe_storage_minio import MinIOStoragePlugin
from floe_storage_minio.config import MinIOStorageConfig


def test_minio_plugin_generates_valid_fileio():
    """Test MinIOStoragePlugin generates valid PyIceberg FileIO."""
    plugin = MinIOStoragePlugin(
        config=MinIOStorageConfig(endpoint="http://minio:9000", bucket="warehouse")
    )
    fileio = plugin.get_pyiceberg_fileio()

    assert fileio is not None
    assert fileio.properties["s3.endpoint"] == "http://minio:9000"
    assert fileio.properties["s3.path-style-access"] == "true"
```

## Anti-Patterns

### DON'T: Hardcode storage URIs

```python
# ❌ ANTI-PATTERN: Hardcoded S3, won't work for GCS
warehouse = "s3://my-bucket/warehouse"
```

### DON'T: Use if/else for storage backends

```python
# ❌ ANTI-PATTERN: Coupled to core
def get_warehouse_uri(storage_type: str) -> str:
    if storage_type == "minio":
        return "s3://bucket/warehouse"
    elif storage_type == "gcs":
        return "gs://bucket/warehouse"
    # Every new backend requires core changes
```

### DO: Use plugin interface with PyIceberg FileIO

```python
# ✅ CORRECT: Composable, extensible
storage_plugin = registry.discover("floe.storage")["minio"]
fileio = storage_plugin.get_pyiceberg_fileio()
warehouse = storage_plugin.get_warehouse_uri("bronze")
```

## Security Considerations

### Credential Management

- **AWS**: Use IAM roles (preferred) or access keys (K8s Secrets)
- **GCP**: Use Workload Identity (preferred) or service account JSON (K8s Secrets)
- **Azure**: Use Managed Identity (preferred) or SAS tokens (K8s Secrets)
- **MinIO**: Use K8s Secrets for credentials (NOT environment variables in production)

### Access Control

- **Bucket policies**: Restrict access to specific prefixes (e.g., `/warehouse/bronze/*`)
- **Network policies**: K8s NetworkPolicy restricts storage access to authorized pods
- **Encryption**: Use server-side encryption (SSE-S3, SSE-KMS, etc.)

### Audit Logging

- **S3**: Enable CloudTrail for access logging
- **GCS**: Enable Cloud Audit Logs
- **Azure**: Enable Storage Analytics logging

## Relationship with Table Operations (IcebergTableManager)

**Important clarification**: `StoragePlugin` handles **FileIO** (object storage access), NOT Iceberg table operations.

Table operations (create_table, evolve_schema, write_data, manage_snapshots) are handled by `IcebergTableManager`, an **internal utility class** in `floe-iceberg` package (Epic 4D).

```
┌─────────────────────┐     ┌─────────────────────┐
│   StoragePlugin     │     │   CatalogPlugin     │
│  (FileIO: S3/GCS)   │     │  (Polaris catalog)  │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           └───────────┬───────────────┘
                       │
                       ▼
           ┌─────────────────────┐
           │  IcebergTableManager│
           │  (internal utility) │
           │  - create_table()   │
           │  - evolve_schema()  │
           │  - write_data()     │
           │  - manage_snapshots()│
           └─────────────────────┘
```

**Why IcebergTableManager is NOT a plugin:**
- Iceberg is **enforced** (ADR-0005), not pluggable
- Table operations are Iceberg-specific, no need for abstraction
- CatalogPlugin already returns PyIceberg Catalog for table registration
- StoragePlugin already provides FileIO for data access

See: Epic 4D (Storage Plugin) specification for full details.

## Open Questions

### Q: Can we use multiple storage backends per platform (multi-cloud)?

**A:** Not in initial implementation. One plugin per platform. Future: Support multiple plugins with namespace-to-storage mapping.

### Q: How do we handle storage-specific features (S3 Transfer Acceleration)?

**A:** Plugin can include extra methods beyond ABC for backend-specific features. Core uses only ABC methods. Users access plugin directly for advanced features.

### Q: What about custom S3-compatible storage (NetApp, Dell EMC)?

**A:** Implement StoragePlugin interface with S3-compatible FileIO. Register via entry points. No core changes needed.

## References

- [ADR-0005: Apache Iceberg Table Format](0005-iceberg-table-format.md) - Iceberg as enforced standard
- [ADR-0037: Composability Principle](0037-composability-principle.md) - Plugin architecture rationale
- [plugin-system/](../plugin-system/index.md) - Plugin patterns
- [interfaces/storage-plugin.md](../interfaces/storage-plugin.md) - StoragePlugin ABC definition
- [Epic 4D: Storage Plugin](../../../specs/4d-storage-plugin/spec.md) - IcebergTableManager specification
- **Industry References:**
  - [PyIceberg FileIO Documentation](https://py.iceberg.apache.org/api/#fileio)
  - [AWS S3 with Iceberg](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-iceberg-how-iceberg-works.html)
  - [GCS with Iceberg](https://cloud.google.com/blog/products/data-analytics/query-apache-iceberg-tables-in-bigquery)
  - [MinIO Deployment](https://min.io/docs/minio/kubernetes/upstream/index.html)
