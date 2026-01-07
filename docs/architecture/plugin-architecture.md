# Plugin Architecture

This document describes the plugin system that enables floe's flexibility.

## Overview

floe uses a plugin architecture for all configurable components:

| Plugin Type | Default | Purpose | ADR |
|-------------|---------|---------|-----|
| **Compute** | DuckDB | Where dbt transforms execute | ADR-0010 |
| **Orchestrator** | Dagster | Job scheduling and execution | ADR-0033 |
| **Catalog** | Polaris | Iceberg table catalog | ADR-0008 |
| **Storage** | MinIO (local), S3 (prod) | Object storage for Iceberg data | ADR-0036 |
| **TelemetryBackend** | Jaeger (local), Datadog (prod) | OTLP telemetry backend (traces, metrics, logs) | ADR-0035 |
| **LineageBackend** | Marquez (local), Atlan (prod) | OpenLineage backend (data lineage) | ADR-0035 |
| **DBT** | dbt-core (local) | dbt compilation environment (local/fusion/cloud) | ADR-0043 |
| **Semantic Layer** | Cube | Business intelligence API | ADR-0001 |
| **Ingestion** | dlt | Data loading from sources | ADR-0020 |
| **Secrets** | K8s Secrets | Credential management | ADR-0023/0031 |
| **Identity** | Keycloak | Authentication provider | ADR-0024 |

**Total:** 11 plugin types (per ADR-0037 Composability Principle)

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins. Policy enforcement tooling is provided via DBTPlugin, and rules are configured via platform-manifest.yaml. Data contracts use ODCS v3 as an enforced standard.

> **Canonical Registry**: This table is the authoritative source for plugin type counts and entry points. All documentation references should link here.

### Plugin Type History

| Version | Count | Changes |
|---------|-------|---------|
| floe-core 2.1 | 11 | Moved PolicyEnforcer + DataContract to core modules (not plugins) |
| floe-core 2.0 | 13 | Split ObservabilityPlugin → TelemetryBackendPlugin + LineageBackendPlugin (ADR-0035) |
| floe-core 1.5 | 12 | Added DBTPlugin (ADR-0043) |
| floe-core 1.4 | 11 | Added DataQualityPlugin (ADR-0044) |
| floe-core 1.0 | 11 | Initial plugin architecture |

## Plugin Structure

Each plugin is a self-contained package:

```
plugins/floe-orchestrator-dagster/
├── src/
│   ├── __init__.py
│   └── plugin.py           # DagsterOrchestratorPlugin class
├── chart/                   # Helm chart (if service deployment needed)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── configmap.yaml
├── tests/
│   ├── test_plugin.py
│   └── conftest.py
└── pyproject.toml          # Entry point registration
```

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

## Plugin Interfaces

### ComputePlugin

```python
class ComputePlugin(ABC):
    """Interface for compute engines where dbt transforms execute."""

    name: str
    version: str
    is_self_hosted: bool

    @abstractmethod
    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        """Generate dbt profile.yml configuration."""
        pass

    @abstractmethod
    def get_required_dbt_packages(self) -> list[str]:
        """Return required dbt packages."""
        pass

    @abstractmethod
    def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        """Test connection to compute engine."""
        pass

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements for dbt job pods."""
        pass

    def get_catalog_attachment_sql(
        self, catalog_config: CatalogConfig
    ) -> list[str] | None:
        """Return SQL to attach compute engine to Iceberg catalog.

        For DuckDB: Returns ATTACH statements for Iceberg REST catalog
        For Spark/Snowflake: Returns None (configured differently)
        """
        return None
```

### OrchestratorPlugin

```python
class OrchestratorPlugin(ABC):
    """Interface for orchestration platforms."""

    name: str
    version: str

    @abstractmethod
    def create_definitions(self, artifacts: CompiledArtifacts) -> any:
        """Generate orchestrator-specific definitions."""
        pass

    @abstractmethod
    def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list:
        """Create orchestrator assets from dbt transforms."""
        pass

    @abstractmethod
    def emit_lineage_event(self, event_type: str, job: str, inputs: list, outputs: list):
        """Emit OpenLineage event."""
        pass
```

### CatalogPlugin

```python
class CatalogPlugin(ABC):
    """Interface for Iceberg catalogs."""

    name: str
    version: str

    @abstractmethod
    def connect(self, config: dict) -> Catalog:
        """Connect to catalog and return PyIceberg Catalog."""
        pass

    @abstractmethod
    def create_namespace(self, namespace: str, properties: dict | None = None):
        """Create namespace."""
        pass

    @abstractmethod
    def vend_credentials(self, table_path: str, operations: list[str]) -> dict:
        """Vend short-lived credentials for table access."""
        pass
```

### SemanticLayerPlugin

```python
class SemanticLayerPlugin(ABC):
    """Interface for semantic/consumption layers."""

    name: str
    version: str

    @abstractmethod
    def sync_from_dbt_manifest(self, manifest_path: Path, output_dir: Path) -> list[Path]:
        """Generate semantic models from dbt manifest."""
        pass

    @abstractmethod
    def get_security_context(self, namespace: str, roles: list[str]) -> dict:
        """Build security context for data isolation."""
        pass

    @abstractmethod
    def get_datasource_config(self, compute_plugin: ComputePlugin) -> dict:
        """Generate datasource configuration from compute plugin.

        The semantic layer delegates to the active compute plugin for database
        connectivity, following the platform's plugin architecture (ADR-0032).

        Args:
            compute_plugin: Active ComputePlugin instance

        Returns:
            Datasource configuration dict for the semantic layer

        Example:
            For DuckDB compute:
            {
                "type": "duckdb",
                "url": "/data/floe.duckdb",
                "catalog": "ice"
            }

            For Snowflake compute:
            {
                "type": "snowflake",
                "account": "xxx.us-east-1",
                "warehouse": "compute_wh",
                ...
            }
        """
        pass
```

### IngestionPlugin

```python
class IngestionPlugin(ABC):
    """Interface for data ingestion/EL plugins."""

    name: str
    version: str
    is_external: bool

    @abstractmethod
    def create_pipeline(self, config: IngestionConfig) -> any:
        """Create ingestion pipeline from configuration."""
        pass

    @abstractmethod
    def run(self, pipeline: any, **kwargs) -> IngestionResult:
        """Execute the ingestion pipeline."""
        pass

    @abstractmethod
    def get_destination_config(self, catalog_config: dict) -> dict:
        """Generate destination configuration for Iceberg."""
        pass
```

### DBTPlugin

Per ADR-0043, dbt **execution environment** (WHERE dbt compiles) is pluggable, while dbt **framework** (SQL transformation DSL) is enforced:

```python
class DBTPlugin(ABC):
    """Interface for dbt compilation environment plugins.

    Responsibilities:
    - Compile dbt projects (Jinja → SQL)
    - Execute dbt commands (run, test, snapshot)
    - Provide SQL linting (optional, dialect-aware)

    Note: This plugins WHERE dbt executes (local/cloud/fusion),
    NOT the SQL transformation framework itself (enforced).
    """

    name: str  # e.g., "local", "fusion", "cloud"
    version: str
    floe_api_version: str

    @abstractmethod
    def compile_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
    ) -> Path:
        """Compile dbt project and return path to manifest.json.

        Returns:
            Path to compiled manifest.json (typically target/manifest.json)

        Raises:
            CompilationError: If dbt compilation fails
        """
        pass

    @abstractmethod
    def run_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
        exclude: str | None = None,
    ) -> RunResult:
        """Execute dbt models.

        Returns:
            RunResult with success status and executed model count
        """
        pass

    @abstractmethod
    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> TestResult:
        """Execute dbt tests.

        Returns:
            TestResult with pass/fail status and test results
        """
        pass

    @abstractmethod
    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> ProjectLintResult:
        """Lint SQL files with dialect-aware validation.

        Args:
            fix: If True, auto-fix issues (if linter supports it)

        Returns:
            ProjectLintResult with all detected linting issues

        Raises:
            DBTLintError: If linting process fails (not if SQL has issues)
        """
        pass

    @abstractmethod
    def supports_sql_linting(self) -> bool:
        """Indicate whether this compilation environment provides SQL linting.

        Returns:
            True if lint_project() is functional, False otherwise
        """
        pass
```

**Entry points:**
```toml
[project.entry-points."floe.dbt"]
local = "floe_dbt_local:LocalDBTPlugin"
fusion = "floe_dbt_fusion:FusionDBTPlugin"
cloud = "floe_dbt_cloud:CloudDBTPlugin"
```

**Implementation Priority:**
- **LocalDBTPlugin** (Epic 3): dbt-core via CLI subprocess, SQLFluff linting
- **FusionDBTPlugin** (Epic 3): dbt Fusion via CLI subprocess, built-in static analysis
- **CloudDBTPlugin** (Epic 8+): dbt Cloud API (deferred)

**See ADR-0043** for complete specification, SQL linting requirements (REQ-096 to REQ-100), and implementation examples.

### DataQualityPlugin

Per ADR-0044, data quality frameworks (Great Expectations, Soda, custom) are pluggable through a unified interface. The DataQualityPlugin handles both compile-time validation (config syntax, quality gates) and runtime execution (live data checks, quality scoring).

```python
class DataQualityPlugin(ABC):
    """Unified interface for data quality frameworks.

    Responsibilities:
    - Validate quality check configuration at compile-time (no data access)
    - Enforce quality gate thresholds at compile-time
    - Execute quality checks against live data at runtime
    - Calculate quality scores with configurable weights
    - Provide OpenLineage integration for quality events
    """

    # Plugin metadata
    name: str
    version: str
    floe_api_version: str

    # COMPILE-TIME METHODS (No data access)
    @abstractmethod
    def validate_config(
        self,
        config_path: Path,
        dbt_manifest: dict[str, Any]
    ) -> ValidationResult:
        """Validate quality check configuration syntax."""
        pass

    @abstractmethod
    def validate_quality_gates(
        self,
        manifest: dict[str, Any],
        required_coverage: dict[str, float]
    ) -> ValidationResult:
        """Enforce quality gate thresholds at compile-time."""
        pass

    # RUNTIME METHODS (Require data access)
    @abstractmethod
    def execute_checks(
        self,
        connection: DatabaseConnection,
        expectations: list[QualityExpectation]
    ) -> QualityCheckResult:
        """Execute quality checks against live data."""
        pass

    @abstractmethod
    def calculate_quality_score(
        self,
        check_results: list[QualityCheckResult],
        weights: dict[str, float]
    ) -> float:
        """Calculate overall quality score (0-100) with weighted formula."""
        pass

    # INTEGRATION METHODS
    @abstractmethod
    def get_lineage_emitter(self) -> LineageEmitter:
        """Get OpenLineage emitter for this DQ tool."""
        pass

    @abstractmethod
    def supports_sql_dialect(self, dialect: str) -> bool:
        """Check if DQ tool supports given SQL dialect."""
        pass
```

**Entry points:**
```toml
[project.entry-points."floe.data_quality"]
great_expectations = "floe_dq_great_expectations:GreatExpectationsPlugin"
soda = "floe_dq_soda:SodaPlugin"
dbt_expectations = "floe_dq_dbt:DBTExpectationsPlugin"
custom = "floe_dq_custom:CustomPlugin"
```

**Platform Configuration:**
```yaml
plugins:
  data_quality:
    provider: great_expectations  # Single choice
    config:
      quality_gates:
        bronze: {min_test_coverage: 50%}
        silver: {min_test_coverage: 80%, required_tests: [not_null, unique]}
        gold: {min_test_coverage: 100%, required_tests: [not_null, unique, relationships]}
      weights:
        critical_checks: 3.0
        standard_checks: 1.0
        statistical_checks: 0.5
```

**Usage Timeline:**
1. **Compile-time**: Compiler calls `validate_config()` and `validate_quality_gates()`
2. **Runtime**: ContractMonitor calls `execute_checks()` every 6 hours
3. **Scoring**: `calculate_quality_score()` combines dbt tests + DQ checks with weighted formula

**Implementation Priority:**
- **GreatExpectationsPlugin** (Epic 7): GX Python API wrapper
- **SodaPlugin** (Epic 8+): Soda Core integration
- **DBTExpectationsPlugin** (Epic 8+): Wraps dbt native tests for unified scoring

**See ADR-0044** for complete specification, quality gate requirements (REQ-241-244), and Great Expectations integration (REQ-207, REQ-248).

### TelemetryBackendPlugin

Per ADR-0035, telemetry backends (Jaeger, Datadog, Grafana Cloud) are pluggable for OTLP traces, metrics, and logs. The TelemetryBackendPlugin wraps the three-layer architecture:
- **Layer 1** (Enforced): OpenTelemetry SDK emission
- **Layer 2** (Enforced): OTLP Collector aggregation
- **Layer 3** (Pluggable): Backend storage/visualization

```python
class TelemetryBackendPlugin(ABC):
    """Interface for OTLP telemetry backend plugins.

    Responsibilities:
    - Configure OTLP Collector exporter for backend-specific protocol
    - Provide Helm values for deploying backend services (if self-hosted)
    - Validate connection to backend
    """

    name: str  # e.g., "jaeger", "datadog", "grafana-cloud"
    version: str
    floe_api_version: str

    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]:
        """Generate OTLP Collector exporter configuration.

        Returns:
            Dictionary matching OTLP Collector config schema.
            Must include 'exporters' section with backend-specific config.

        Example (Jaeger):
            {
                "exporters": {
                    "jaeger": {
                        "endpoint": "jaeger:14250",
                        "tls": {"insecure": true}
                    }
                },
                "service": {
                    "pipelines": {
                        "traces": {
                            "receivers": ["otlp"],
                            "processors": ["batch"],
                            "exporters": ["jaeger"]
                        }
                    }
                }
            }
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        Returns:
            Helm values dictionary for backend chart.
            Empty dict if backend is external (SaaS).
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to backend.

        Returns:
            True if connection successful, False otherwise.
        """
        pass
```

**Entry points:**
```toml
[project.entry-points."floe.telemetry_backends"]
jaeger = "floe_telemetry_jaeger:JaegerPlugin"
datadog = "floe_telemetry_datadog:DatadogPlugin"
grafana-cloud = "floe_telemetry_grafana:GrafanaCloudPlugin"
```

**See ADR-0035** for complete specification and reference implementations.

### LineageBackendPlugin

Per ADR-0035, lineage backends (Marquez, Atlan, OpenMetadata) are pluggable for OpenLineage events. The LineageBackendPlugin is architecturally independent from TelemetryBackendPlugin (uses direct HTTP transport, not OTLP Collector).

```python
class LineageBackendPlugin(ABC):
    """Interface for OpenLineage backend plugins.

    Responsibilities:
    - Configure OpenLineage HTTP transport for backend-specific endpoint
    - Define namespace strategy for lineage events
    - Provide Helm values for deploying backend services (if self-hosted)
    - Validate connection to backend
    """

    name: str  # e.g., "marquez", "atlan", "openmetadata"
    version: str
    floe_api_version: str

    @abstractmethod
    def get_transport_config(self) -> dict[str, Any]:
        """Generate OpenLineage HTTP transport configuration.

        Returns:
            Dictionary with 'type' (must be 'http') and endpoint config.

        Example (Marquez):
            {
                "type": "http",
                "url": "http://marquez:5000/api/v1/lineage",
                "timeout": 5.0,
                "endpoint": "api/v1/lineage"
            }
        """
        pass

    @abstractmethod
    def get_namespace_strategy(self) -> dict[str, Any]:
        """Define namespace strategy for lineage events.

        Returns:
            Dictionary with namespace strategy configuration.

        Example (environment-based):
            {
                "strategy": "environment_based",
                "template": "floe-{environment}",
                "environment_var": "FLOE_ENVIRONMENT"
            }
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Generate Helm values for deploying backend services.

        Returns:
            Helm values dictionary for backend chart.
            Empty dict if backend is external (SaaS).
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate connection to backend.

        Returns:
            True if connection successful, False otherwise.
        """
        pass
```

**Entry points:**
```toml
[project.entry-points."floe.lineage_backends"]
marquez = "floe_lineage_marquez:MarquezPlugin"
atlan = "floe_lineage_atlan:AtlanPlugin"
openmetadata = "floe_lineage_openmetadata:OpenMetadataPlugin"
```

**See ADR-0035** for complete specification, split architecture rationale, and reference implementations (JaegerPlugin, MarquezPlugin, DatadogPlugin, AtlanPlugin).

### StoragePlugin

Per ADR-0036, storage backends (S3, GCS, Azure, MinIO) are pluggable via the PyIceberg FileIO pattern:

```python
class StoragePlugin(ABC):
    """Interface for storage backend plugins.

    Wraps PyIceberg FileIO pattern to provide:
    - PyIceberg-compatible FileIO instance
    - Credential management
    - Helm values for deploying storage services (if self-hosted)
    """

    name: str  # e.g., "s3", "gcs", "azure", "minio"
    version: str
    floe_api_version: str

    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO:
        """Create PyIceberg FileIO instance for this storage backend.

        Returns:
            FileIO instance (S3FileIO, GCSFileIO, AzureFileIO, etc.)
        """
        pass

    @abstractmethod
    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for Iceberg catalog.

        Args:
            namespace: Catalog namespace (e.g., "bronze", "silver")

        Returns:
            Storage URI (e.g., "s3://bucket/warehouse/bronze")
        """
        pass

    @abstractmethod
    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Generate dbt profile configuration for this storage backend.

        Returns:
            Dictionary with storage-specific config for dbt profiles.yml
        """
        pass

    @abstractmethod
    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Generate Dagster IOManager configuration.

        Returns:
            Dictionary with storage config for Dagster IOManager
        """
        pass

    @abstractmethod
    def get_helm_values_override(self) -> dict[str, Any]:
        """Generate Helm values for deploying storage services.

        Returns:
            Helm values dictionary for storage chart.
            Empty dict if storage is external (cloud).
        """
        pass
```

**Entry points:**
```toml
[project.entry-points."floe.storage"]
s3 = "floe_storage_s3:S3Plugin"
minio = "floe_storage_minio:MinIOPlugin"
gcs = "floe_storage_gcs:GCSPlugin"
```

**See ADR-0036** for complete specification and PyIceberg FileIO integration examples.

## Plugin API Versioning

```python
# floe_core/plugin_api.py
from typing import Final

FLOE_PLUGIN_API_VERSION: Final[str] = "1.0"
FLOE_PLUGIN_API_MIN_VERSION: Final[str] = "1.0"

@dataclass
class PluginMetadata:
    name: str
    version: str
    floe_api_version: str  # Required
    description: str
    author: str
```

### Compatibility Check

```python
def load_plugin(self, entry_point) -> Plugin:
    plugin_class = entry_point.load()
    metadata = plugin_class.metadata

    if not is_compatible(metadata.floe_api_version, FLOE_PLUGIN_API_MIN_VERSION):
        raise PluginIncompatibleError(
            f"Plugin {metadata.name} requires API v{metadata.floe_api_version}, "
            f"but minimum supported is v{FLOE_PLUGIN_API_MIN_VERSION}"
        )

    return plugin_class()
```

## Plugin CLI Commands

```bash
# List installed plugins
floe plugins list

# Output:
Installed plugins:
  orchestrators:
    - dagster (1.0.0) [default]
    - airflow (1.0.0)
  computes:
    - duckdb (1.0.0) [default]
    - snowflake (1.0.0)
    - spark (1.0.0)
  catalogs:
    - polaris (1.0.0) [default]
    - glue (1.0.0)
  dbt:
    - local (1.0.0) [default]
    - fusion (1.0.0)
  semantic_layers:
    - cube (1.0.0) [default]
    - none (1.0.0)
  ingestion:
    - dlt (1.0.0) [default]
    - airbyte (1.0.0)

# List available (installable) plugins
floe plugins available
```

## Creating a Custom Plugin

### 1. Create Package Structure

```bash
mkdir floe-compute-trino
cd floe-compute-trino
```

### 2. Implement Interface

```python
# src/floe_compute_trino/plugin.py
from floe_core.interfaces.compute import ComputePlugin, ComputeConfig

class TrinoComputePlugin(ComputePlugin):
    name = "trino"
    version = "1.0.0"
    is_self_hosted = True

    metadata = PluginMetadata(
        name="trino",
        version="1.0.0",
        floe_api_version="1.0",
        description="Trino compute plugin for floe",
        author="Your Name",
    )

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "trino",
            "method": "none",
            "host": config.properties.get("host", "trino.default.svc.cluster.local"),
            "port": config.properties.get("port", 8080),
            "catalog": config.properties.get("catalog", "iceberg"),
            "schema": config.properties.get("schema", "default"),
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-trino>=1.7.0"]

    # ... implement other methods
```

### 3. Register Entry Point

```toml
# pyproject.toml
[project.entry-points."floe.computes"]
trino = "floe_compute_trino:TrinoComputePlugin"
```

### 4. Add Helm Chart (if needed)

```yaml
# chart/Chart.yaml
apiVersion: v2
name: floe-compute-trino
version: 1.0.0
description: Trino compute for floe

# chart/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trino-coordinator
# ...
```

### 5. Install and Use

```bash
uv add floe-compute-trino

# platform-manifest.yaml
plugins:
  compute:
    type: trino
    config:
      host: trino.example.com
```

## Compute-Catalog Integration

Some compute engines require explicit SQL statements to connect to the Iceberg catalog before dbt models can execute. The `get_catalog_attachment_sql()` method handles this.

### DuckDB Catalog Integration Example

DuckDB v1.4+ has native Iceberg REST catalog support. The DuckDB plugin generates ATTACH statements that connect to Polaris before model execution:

```python
# floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
from floe_core.interfaces.compute import ComputePlugin, ComputeConfig
from floe_core.interfaces.catalog import CatalogConfig

class DuckDBComputePlugin(ComputePlugin):
    name = "duckdb"
    version = "1.0.0"
    is_self_hosted = True

    def generate_dbt_profile(self, config: ComputeConfig) -> dict:
        return {
            "type": "duckdb",
            "path": config.properties.get("path", "/data/floe.duckdb"),
            "extensions": ["iceberg", "httpfs"],
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-duckdb>=1.9.0"]

    def get_catalog_attachment_sql(
        self, catalog_config: CatalogConfig
    ) -> list[str]:
        """Generate DuckDB SQL to attach to Polaris Iceberg catalog.

        These statements are added as dbt on-run-start hooks.
        DuckDB will use the catalog for all table operations.
        """
        return [
            "LOAD iceberg;",
            """CREATE SECRET IF NOT EXISTS polaris_secret (
                TYPE iceberg,
                CLIENT_ID '{{ env_var("POLARIS_CLIENT_ID") }}',
                CLIENT_SECRET '{{ env_var("POLARIS_CLIENT_SECRET") }}'
            );""",
            f"""ATTACH IF NOT EXISTS '{catalog_config.warehouse}' AS ice (
                TYPE iceberg,
                ENDPOINT '{{{{ env_var("POLARIS_URI") }}}}'
            );"""
        ]

    # ... other methods
```

The floe-dbt package uses these statements to generate dbt project configuration:

```yaml
# Generated dbt_project.yml
on-run-start:
  - "LOAD iceberg;"
  - "CREATE SECRET IF NOT EXISTS polaris_secret (...)"
  - "ATTACH IF NOT EXISTS '...' AS ice (TYPE iceberg, ...)"
```

Models then write directly to the attached Iceberg catalog:

```sql
-- models/gold/customers.sql
{{ config(materialized='iceberg_table') }}

SELECT * FROM {{ ref('silver_customers') }}
-- Creates table: ice.gold.customers
```

## Related Documents

- [ADR-0008: Repository Split](adr/0008-repository-split.md) - Plugin architecture details
- [ADR-0010: Target-Agnostic Compute](adr/0010-target-agnostic-compute.md) - ComputePlugin
- [ADR-0020: Ingestion Plugins](adr/0020-ingestion-plugins.md) - IngestionPlugin
- [ADR-0031: Infisical as Default Secrets Management](adr/0031-infisical-secrets.md) - SecretsPlugin
- [ADR-0032: Semantic Layer Compute Plugin Integration](adr/0032-cube-compute-integration.md) - SemanticLayerPlugin delegation
- [ADR-0033: Target Airflow 3.x](adr/0033-airflow-3x.md) - OrchestratorPlugin for Airflow
- [ADR-0034: dbt-duckdb Iceberg Catalog Workaround](adr/0034-dbt-duckdb-iceberg.md) - ComputePlugin Iceberg integration
- [Interfaces](interfaces/index.md) - Full interface definitions
