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

Create a **StoragePlugin interface** that emits a neutral, secret-free storage
deployment binding for pluggable object storage backends and still supports
direct PyIceberg FileIO use where runtime code needs it.

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
StoragePlugin emits neutral StorageDeploymentBinding.
CatalogPlugin declares storage requirements and translates storage into CatalogDeploymentBinding.
Compute and orchestrator plugins consume runtime storage facts.
floe-core validates compatibility through the composition resolver.
Helm renders resolved deployment bindings.
```

Legacy helper methods can remain during migration, but they are not the
semantic contract.

### StoragePlugin Interface

```python
from abc import ABC, abstractmethod
from pyiceberg.io import FileIO
from floe_core.schemas.compiled_artifacts import StorageDeploymentBinding


class StoragePlugin(ABC):
    """Plugin interface for object storage backends.

    Storage plugins own provider facts only:
    - protocol and endpoint roles
    - warehouse and bucket requirements
    - credential references
    - capabilities and provisioning intent
    - neutral runtime fragments for consumers to translate
    """

    name: str                 # e.g., "minio", "gcs", "azure"
    version: str              # Plugin version (semver)
    floe_api_version: str     # Supported floe-core API version

    @abstractmethod
    def get_deployment_binding(self) -> StorageDeploymentBinding:
        """Return secret-free storage desired state for compilation."""
        pass

    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO:
        """Create PyIceberg FileIO instance for direct runtime use."""
        pass
```

This is the target semantic interface. During migration, the live ABC may still
include legacy abstract helpers for dbt, Dagster, warehouse URI, and Helm
fragments so existing plugins instantiate cleanly. Those helpers are
compatibility surface only; new integration logic should use
`get_deployment_binding()` and consumer-owned translators.

Provider-specific consumer projections are owned by the consumer. Polaris, for
example, translates MinIO's neutral binding into `storageConfigInfo`, endpoint
fields, path-style access, STS semantics, allowed locations, and Kubernetes
Secret references. Helm renders that resolved binding; it does not reconstruct
semantic storage facts from raw chart credentials or legacy plugin config.

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

# Compiler discovers plugin and invokes:
# 1. get_deployment_binding() -> neutral storage desired state
# 2. composition resolver -> storage/catalog compatibility validation
# 3. catalog translator -> catalog-owned deployment binding
# 4. Helm/runtime renderers -> generated config from typed bindings
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
truth. This excerpt shows the public plugin shape: MinIO emits S3-compatible
provider facts and credential references, not Polaris bootstrap JSON or raw
credential values.

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

    def get_deployment_binding(self) -> StorageDeploymentBinding:
        """Return secret-free MinIO deployment binding for compiled artifacts."""
        config = self._require_config()
        return StorageDeploymentBinding(
            provider="minio",
            protocol="s3-compatible",
            endpoint=StorageServiceEndpoint(
                internal_url=config.endpoint,
                external_url=config.external_endpoint or config.endpoint,
                region=config.region,
                warehouse_path=f"s3://{config.bucket}",
                path_style_access=config.path_style_access,
            ),
            warehouse=StorageWarehouse(uri=f"s3://{config.bucket}", bucket=config.bucket),
            allowed_locations=[f"s3://{config.bucket}"],
            buckets=[
                StorageBucketRequirement(
                    name=config.bucket,
                    uri=f"s3://{config.bucket}",
                    purpose="warehouse",
                    create_policy="create-if-missing",
                )
            ],
            credentials=StorageCredentialBinding(
                mode="kubernetes-secret",
                secret_ref=KubernetesSecretRef(
                    name=config.credential_secret_name,
                    namespace=config.credential_secret_namespace,
                    keys={
                        "accessKeyId": config.access_key_secret_key,
                        "secretAccessKey": config.secret_key_secret_key,
                    },
                ),
            ),
            capabilities=StorageCapabilities(
                protocols=["s3-compatible"],
                credential_modes=["kubernetes-secret"],
                sts_supported=False,
                path_style_access=config.path_style_access,
            ),
            provisioning=StorageProvisioningIntent(
                enabled=True,
                mode="helm-job",
                default_create_policy="create-if-missing",
            ),
            runtime=StorageRuntimeBinding(
                pyiceberg_properties={
                    "s3.endpoint": config.endpoint,
                    "s3.region": config.region,
                    "s3.path-style-access": str(config.path_style_access).lower(),
                },
                env_refs={
                    "accessKeyId": "AWS_ACCESS_KEY_ID",
                    "secretAccessKey": "AWS_SECRET_ACCESS_KEY",
                },
            ),
            dbt=DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
            ),
            dagster=DagsterStorageBinding(
                resource_key="minio_storage",
                asset_io_manager_key="iceberg_io_manager",
            ),
        )
```

The `dbt` and `dagster` fields are currently required schema fields for
secret-free runtime identity hints. They are not permission for storage plugins
to own dbt profile generation or Dagster resource construction; those consumers
translate the compiled binding.

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
from pyiceberg.io.pyarrow import PyArrowFileIO
from floe_core.plugins import StoragePlugin
from floe_core.schemas.compiled_artifacts import StorageDeploymentBinding


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

    def get_deployment_binding(self) -> StorageDeploymentBinding:
        """Return secret-free GCS desired state.

        A real implementation would declare GCS protocol/capability facts and
        workload identity or Secret references. Catalog plugins would translate
        those facts into catalog-specific deployment config.
        """
        ...
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
# dbt profiles.yml (dbt/compute integration derives filesystem config
# from the compiled storage binding)
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
            filesystems:  # Derived from the compiled storage binding
              s3:
                key_id: ${AWS_ACCESS_KEY_ID}
                secret: ${AWS_SECRET_ACCESS_KEY}
                region: us-east-1
```

### Dagster Integration

```python
# Dagster definitions consume the compiled storage binding.
from dagster import Definitions
from dagster_iceberg import IcebergIOManager

defs = Definitions(
    assets=assets,
    resources={
        "io_manager": IcebergIOManager(
            catalog_uri="http://polaris:8181",
            warehouse="s3://floe-warehouse/bronze",
            storage_options=artifacts.deployment.storage.runtime.pyiceberg_properties,
        )
    },
)
```

### PyIceberg Catalog Integration

```python
# Catalog loading consumes catalog-owned deployment/runtime config.
from pyiceberg.catalog import load_catalog

catalog = load_catalog(
    "polaris",
    type="rest",
    uri="http://polaris:8181",
    warehouse=artifacts.deployment.catalog.polaris.default_base_location,
    **artifacts.deployment.storage.runtime.pyiceberg_properties,
)
```

## Testing Strategy

### Unit Tests (Mock Plugin)

```python
# tests/unit/test_storage_plugin.py
from unittest.mock import Mock
from floe_core.plugins import StoragePlugin
from floe_core.schemas.compiled_artifacts import StorageDeploymentBinding


def test_compiler_with_mock_storage():
    """Test compiler with mocked storage plugin."""
    mock_plugin = Mock(spec=StoragePlugin)
    mock_plugin.get_deployment_binding.return_value = StorageDeploymentBinding(...)

    compiler = Compiler(storage_plugin=mock_plugin)
    artifacts = compiler.compile(spec)

    assert artifacts.deployment.storage is not None
    mock_plugin.get_deployment_binding.assert_called_once()
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
storage = storage_plugin.get_deployment_binding()
catalog = catalog_plugin.build_catalog_deployment(storage)
deployment = DeploymentConfig(storage=storage, catalog=catalog)
```

## Security Considerations

### Credential Management

- **AWS**: Use IAM roles (preferred) or access keys (K8s Secrets)
- **GCP**: Use Workload Identity (preferred) or service account JSON (K8s Secrets)
- **Azure**: Use Managed Identity (preferred) or SAS tokens (K8s Secrets)
- **MinIO**: Use K8s Secret references in compiled artifacts and chart values
  (NOT raw credential values)

### Access Control

- **Bucket policies**: Restrict access to specific prefixes (e.g., `/warehouse/bronze/*`)
- **Network policies**: K8s NetworkPolicy restricts storage access to authorized pods
- **Encryption**: Use server-side encryption (SSE-S3, SSE-KMS, etc.)

### Audit Logging

- **S3**: Enable CloudTrail for access logging
- **GCS**: Enable Cloud Audit Logs
- **Azure**: Enable Storage Analytics logging

## Relationship with Table Operations (IcebergTableManager)

**Important clarification**: `StoragePlugin` handles neutral storage desired
state and direct **FileIO** access, NOT Iceberg table operations or
catalog-specific deployment JSON.

Table operations (create_table, evolve_schema, write_data, manage_snapshots) are handled by `IcebergTableManager`, an **internal utility class** in `floe-iceberg` package (Epic 4D).

```
┌─────────────────────┐     ┌─────────────────────┐
│   StoragePlugin     │     │   CatalogPlugin     │
│ (neutral binding)   │     │ (catalog binding)   │
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
- StoragePlugin already provides storage bindings and FileIO for data access

See: Epic 4D (Storage Plugin) specification for full details.

## Open Questions

### Q: Can we use multiple storage backends per platform (multi-cloud)?

**A:** Not in initial implementation. One plugin per platform. Future: Support multiple plugins with namespace-to-storage mapping.

### Q: How do we handle storage-specific features (S3 Transfer Acceleration)?

**A:** Backend-specific features belong in capabilities or provider-owned
binding fields when they affect composition. Extra provider methods can exist
for direct advanced use, but they are not the cross-plugin contract.

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
