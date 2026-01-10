"""Plugin type ABCs for the floe platform.

This module provides abstract base classes (ABCs) for all pluggable component
types in the floe platform. Each ABC defines the interface that concrete
plugin implementations must satisfy.

Plugin Categories (12 types):
    Compute: Database execution engines (DuckDB, Snowflake, BigQuery)
    Orchestrator: Workflow schedulers (Dagster, Airflow)
    Catalog: Iceberg catalog providers (Polaris, AWS Glue, Hive)
    Storage: Object storage backends (S3, GCS, MinIO)
    Telemetry: Observability backends (Jaeger, Datadog, Grafana)
    Lineage: Data lineage backends (Marquez, Atlan, DataHub)
    DBT: dbt execution environments (local, fusion, cloud)
    Semantic: Business intelligence layers (Cube, dbt Semantic Layer)
    Ingestion: Data loading tools (dlt, Airbyte)
    Secrets: Credential managers (Vault, AWS Secrets Manager)
    Identity: Authentication providers (OAuth2, OIDC)
    Quality: Data quality validators (Great Expectations, Soda, dbt-expectations)

Example:
    >>> from floe_core.plugins import ComputePlugin, CatalogPlugin
    >>> from floe_core.plugins import ComputeConfig, IngestionResult

See Also:
    - docs/architecture/plugin-system/interfaces.md: Full interface specification
    - PluginMetadata: Base class with common plugin attributes
"""

from __future__ import annotations

# Catalog plugin
from floe_core.plugins.catalog import (
    Catalog,
    CatalogPlugin,
)

# Compute plugin
from floe_core.plugins.compute import (
    CatalogConfig,
    ComputeConfig,
    ComputePlugin,
    ConnectionResult,
    ResourceSpec,
)

# DBT plugin
from floe_core.plugins.dbt import (
    DBTPlugin,
    DBTRunResult,
    LintResult,
)

# Identity plugin
from floe_core.plugins.identity import (
    IdentityPlugin,
    TokenValidationResult,
    UserInfo,
)

# Ingestion plugin
from floe_core.plugins.ingestion import (
    IngestionConfig,
    IngestionPlugin,
    IngestionResult,
)

# Lineage plugin
from floe_core.plugins.lineage import LineageBackendPlugin

# Orchestrator plugin
from floe_core.plugins.orchestrator import (
    Dataset,
    OrchestratorPlugin,
    TransformConfig,
    ValidationResult,
)
from floe_core.plugins.orchestrator import ResourceSpec as OrchestratorResourceSpec

# Quality plugin
from floe_core.plugins.quality import (
    QualityCheckResult,
    QualityPlugin,
    QualitySuiteResult,
)

# Secrets plugin
from floe_core.plugins.secrets import SecretsPlugin

# Semantic layer plugin
from floe_core.plugins.semantic import SemanticLayerPlugin

# Storage plugin
from floe_core.plugins.storage import (
    FileIO,
    StoragePlugin,
)

# Telemetry plugin
from floe_core.plugins.telemetry import TelemetryBackendPlugin

__all__ = [
    # Catalog
    "Catalog",
    "CatalogPlugin",
    # Compute
    "CatalogConfig",
    "ComputeConfig",
    "ComputePlugin",
    "ConnectionResult",
    "ResourceSpec",
    # DBT
    "DBTPlugin",
    "DBTRunResult",
    "LintResult",
    # Identity
    "IdentityPlugin",
    "TokenValidationResult",
    "UserInfo",
    # Ingestion
    "IngestionConfig",
    "IngestionPlugin",
    "IngestionResult",
    # Lineage
    "LineageBackendPlugin",
    # Orchestrator
    "Dataset",
    "OrchestratorPlugin",
    "OrchestratorResourceSpec",
    "TransformConfig",
    "ValidationResult",
    # Quality
    "QualityCheckResult",
    "QualityPlugin",
    "QualitySuiteResult",
    # Secrets
    "SecretsPlugin",
    # Semantic
    "SemanticLayerPlugin",
    # Storage
    "FileIO",
    "StoragePlugin",
    # Telemetry
    "TelemetryBackendPlugin",
]
