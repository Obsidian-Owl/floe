# Plugin Interfaces

This document describes all plugin interface ABCs.

## ComputePlugin

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

## OrchestratorPlugin

```python
class OrchestratorPlugin(ABC):
    """Interface for orchestration platforms (Dagster, Airflow, etc.)."""

    name: str
    version: str
    floe_api_version: str

    @abstractmethod
    def create_definitions(self, artifacts: CompiledArtifacts) -> Any:
        """Generate orchestrator-specific definitions from compiled artifacts.

        For Dagster: Returns Dagster Definitions object
        For Airflow: Returns DAG object
        """
        pass

    @abstractmethod
    def create_assets_from_transforms(self, transforms: list[TransformConfig]) -> list:
        """Create orchestrator assets from dbt transforms.

        For Dagster: Returns list of @asset decorated functions
        For Airflow: Returns list of tasks
        """
        pass

    @abstractmethod
    def get_helm_values(self) -> dict[str, Any]:
        """Return Helm chart values for deploying orchestration services.

        Returns:
            Dictionary matching Helm chart schema with resource
            requests/limits and service configuration.
        """
        pass

    @abstractmethod
    def validate_connection(self) -> ValidationResult:
        """Test connectivity to orchestration service.

        Returns:
            ValidationResult with success status and actionable error messages.
            Must complete within 10 seconds.
        """
        pass

    @abstractmethod
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s ResourceRequirements for orchestration workloads.

        Args:
            workload_size: "small", "medium", "large"

        Returns:
            ResourceSpec with CPU/memory requests and limits.
        """
        pass

    @abstractmethod
    def emit_lineage_event(
        self,
        event_type: str,
        job: str,
        inputs: list[Dataset],
        outputs: list[Dataset]
    ) -> None:
        """Emit OpenLineage event for data lineage tracking.

        Args:
            event_type: "START" | "COMPLETE" | "FAIL"
            job: Job name (e.g., "dbt_run")
            inputs: Input datasets
            outputs: Output datasets
        """
        pass

    @abstractmethod
    def schedule_job(self, job_name: str, cron: str, timezone: str) -> None:
        """Schedule a job for recurring execution.

        Args:
            job_name: Name of the job to schedule
            cron: Cron expression (e.g., "0 8 * * *")
            timezone: IANA timezone (e.g., "America/New_York")
        """
        pass
```

**Entry points:**
```toml
[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterPlugin"
airflow = "floe_orchestrator_airflow:AirflowPlugin"
```

**Requirements Traceability:** REQ-021 to REQ-030 (OrchestratorPlugin Standards)

## CatalogPlugin

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

## SemanticLayerPlugin

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

## IngestionPlugin

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

## DBTPlugin

Per ADR-0043, dbt **execution environment** (WHERE dbt compiles) is pluggable, while dbt **framework** (SQL transformation DSL) is enforced:

```python
class DBTRunResult(BaseModel):
    """Result of a dbt command execution."""
    success: bool
    manifest_path: Path
    run_results_path: Path
    catalog_path: Path | None = None
    execution_time_seconds: float
    models_run: int
    tests_run: int
    failures: int
    metadata: dict[str, Any] = {}

class DBTPlugin(ABC):
    """Interface for dbt compilation environment plugins.

    Responsibilities:
    - Compile dbt projects (Jinja -> SQL)
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
        full_refresh: bool = False,
    ) -> DBTRunResult:
        """Execute dbt models.

        Returns:
            DBTRunResult with success status and executed model count
        """
        pass

    @abstractmethod
    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult:
        """Execute dbt tests.

        Returns:
            DBTRunResult with pass/fail status and test results
        """
        pass

    @abstractmethod
    def lint_project(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        fix: bool = False,
    ) -> LintResult:
        """Lint SQL files with dialect-aware validation.

        Args:
            fix: If True, auto-fix issues (if linter supports it)

        Returns:
            LintResult with all detected linting issues

        Raises:
            DBTLintError: If linting process fails (not if SQL has issues)
        """
        pass

    @abstractmethod
    def get_manifest(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt manifest.json (filesystem or API)."""
        pass

    @abstractmethod
    def get_run_results(self, project_dir: Path) -> dict[str, Any]:
        """Retrieve dbt run_results.json."""
        pass

    @abstractmethod
    def supports_parallel_execution(self) -> bool:
        """Indicate whether runtime supports parallel execution."""
        pass

    @abstractmethod
    def supports_sql_linting(self) -> bool:
        """Indicate whether this compilation environment provides SQL linting."""
        pass

    @abstractmethod
    def get_runtime_metadata(self) -> dict[str, Any]:
        """Return runtime-specific metadata for observability."""
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
- **LocalDBTPlugin** (Epic 3): dbt-core via dbtRunner, SQLFluff linting
- **FusionDBTPlugin** (Epic 3): dbt Fusion CLI, built-in static analysis
- **CloudDBTPlugin** (Epic 8+): dbt Cloud API (deferred)

**Requirements Traceability:** REQ-086 to REQ-095 (DBT Runtime Plugin), REQ-096 to REQ-100 (SQL Linting)

**See**: [interfaces/dbt-plugin.md](../interfaces/dbt-plugin.md) for canonical interface definition, [ADR-0043](../adr/0043-dbt-plugin.md) for architecture rationale.

## DataQualityPlugin

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

## TelemetryBackendPlugin

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

## LineageBackendPlugin

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

## StoragePlugin

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

## Related Documents

- [Plugin Architecture Overview](index.md)
- [Discovery and Registry](discovery.md)
- [Lifecycle and Versioning](lifecycle.md)
- [Integration Patterns](integration-patterns.md)
