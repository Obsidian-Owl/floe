"""Plugin type ABCs and registry components for the floe platform.

This module provides:
1. Abstract base classes (ABCs) for all pluggable component types
2. Registry components for plugin discovery, loading, and lifecycle management

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

Registry Components (Epic 12B US4):
    PluginDiscovery: Entry point scanning for installed plugins
    PluginLoader: Lazy loading and caching of plugin instances
    PluginLifecycle: Activation, shutdown, and health check management
    DependencyResolver: Topological sorting of plugin dependencies

Example:
    >>> from floe_core.plugins import ComputePlugin, CatalogPlugin
    >>> from floe_core.plugins import ComputeConfig, IngestionResult
    >>> from floe_core.plugins import PluginDiscovery, PluginLoader

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
    DBTCompilationError,
    DBTError,
    DBTExecutionError,
    DBTPlugin,
    DBTRunResult,
    LintResult,
    LintViolation,
)

# Registry components (Epic 12B US4 - God Module Decomposition)
from floe_core.plugins.dependencies import DependencyResolver
from floe_core.plugins.discovery import PluginDiscovery

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
from floe_core.plugins.lifecycle import (
    DEFAULT_HEALTH_CHECK_TIMEOUT,
    DEFAULT_LIFECYCLE_TIMEOUT,
    PluginLifecycle,
)

# Lineage plugin
from floe_core.plugins.lineage import LineageBackendPlugin
from floe_core.plugins.loader import PluginLoader

# Network Security plugin (Epic 7C)
from floe_core.plugins.network_security import NetworkSecurityPlugin

# Orchestrator plugin
from floe_core.plugins.orchestrator import (
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
    "LintViolation",
    "DBTError",
    "DBTCompilationError",
    "DBTExecutionError",
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
    # Network Security (Epic 7C)
    "NetworkSecurityPlugin",
    # Orchestrator
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
    # Registry components (Epic 12B US4)
    "DependencyResolver",
    "PluginDiscovery",
    "PluginLoader",
    "PluginLifecycle",
    "DEFAULT_LIFECYCLE_TIMEOUT",
    "DEFAULT_HEALTH_CHECK_TIMEOUT",
]
