# 04. Building Blocks (C4 Level 2)

This document describes the container view—the packages that comprise floe, organized into a four-layer architecture.

---

## 1. Four-Layer Architecture

floe uses a four-layer architecture separating framework code, platform configuration, services, and pipeline jobs.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: DATA LAYER (Ephemeral Jobs)                                        │
│  Owner: Data Engineers | Lifecycle: Run-to-completion (K8s Jobs)            │
│  • dbt run pods, pipeline executions, quality check jobs                    │
│  • Inherits all platform constraints (cannot override)                      │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ Connects to
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: PLATFORM SERVICES (Long-lived)                                     │
│  Owner: Platform Team | Lifecycle: Always running (Deployments/StatefulSets)│
│  • Orchestrator services (Dagster webserver, daemon, PostgreSQL)            │
│  • Catalog services (Polaris server)                                        │
│  • Semantic layer (Cube server, Redis)                                      │
│  • Observability (OTLP Collector, Prometheus, Grafana)                      │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ Configured by
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: PLATFORM CONFIGURATION (Enforcement)                               │
│  Owner: Platform Team | Lifecycle: Versioned artifacts in OCI Registry      │
│  • manifest.yaml → immutable policies                              │
│  • Governance, naming conventions, quality gates                            │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ Built on
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: FOUNDATION (Framework Code - Open Source)                          │
│  Owner: floe Maintainers | Lifecycle: PyPI/Helm releases            │
│  • floe-core, floe-cli, floe-dbt, floe-iceberg                              │
│  • plugins/* (11 plugin types: compute, orchestrator, catalog, storage,     │
│              telemetry, lineage, dbt, semantic layer, ingestion, quality,   │
│              secrets, identity - ADR-0037)                                  │
│  • charts/* (Helm charts for platform deployment)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Package Structure

```
floe/
│
├── floe-core/                           # FOUNDATION: Schemas, interfaces, enforcement
├── floe-cli/                            # CLI for Platform Team and Data Team
├── floe-dbt/                            # ENFORCED: dbt framework (compilation environment pluggable)
├── floe-iceberg/                        # ENFORCED: Iceberg utilities (not pluggable)
│
├── plugins/                             # PLUGGABLE: 11 plugin types (ADR-0037)
│   ├── floe-compute-duckdb/            # Compute plugins
│   ├── floe-compute-spark/
│   ├── floe-compute-snowflake/
│   ├── floe-orchestrator-dagster/      # Orchestration plugins
│   ├── floe-orchestrator-airflow/
│   ├── floe-catalog-polaris/           # Catalog plugins
│   ├── floe-catalog-glue/
│   ├── floe-storage-s3/                # Storage plugins (ADR-0036)
│   ├── floe-storage-minio/
│   ├── floe-storage-gcs/
│   ├── floe-telemetry-jaeger/          # Telemetry backend plugins (ADR-0035)
│   ├── floe-telemetry-datadog/
│   ├── floe-lineage-marquez/           # Lineage backend plugins (ADR-0035)
│   ├── floe-lineage-atlan/
│   ├── floe-dbt-local/                 # DBT plugins (ADR-0043)
│   ├── floe-dbt-fusion/
│   ├── floe-semantic-cube/             # Semantic layer plugins
│   ├── floe-ingestion-dlt/             # Ingestion plugins
│   ├── floe-quality-great-expectations/ # Data quality plugins (ADR-0044)
│   ├── floe-quality-soda/
│   ├── floe-secrets-infisical/         # Secrets plugins (ADR-0031)
│   ├── floe-secrets-eso/
│   └── floe-identity-keycloak/         # Identity plugins (ADR-0024)
│
├── charts/
│   ├── floe-platform/                  # Meta-chart: assembles plugin charts
│   └── floe-jobs/                      # Base chart for pipeline job execution
│
└── docs/
```

### Package Dependencies

```
                         ┌─────────────┐
                         │  floe-cli   │
                         └──────┬──────┘
                                │
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
        ┌───────────┐    ┌───────────┐    ┌───────────┐
        │ floe-core │    │ floe-dbt  │    │floe-iceberg│
        │(interfaces│    │(ENFORCED) │    │(ENFORCED)  │
        │ + schemas)│    └───────────┘    └───────────┘
        └─────┬─────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌─────────┐      ┌──────────┐
│plugins/*│      │ charts/* │
│(via ABC)│      │          │
└─────────┘      └──────────┘
```

---

## 3. floe-core

The foundation package defining schemas, plugin interfaces, and the enforcement engine.

### 3.1 Responsibilities

| Responsibility | Description |
|----------------|-------------|
| Schema definition | `Manifest` (Platform Team) and `DataProduct` (Data Team) |
| Plugin interfaces | Abstract Base Classes for all pluggable components |
| Enforcement engine | Validates data products against manifest constraints |
| Plugin registry | Discovers and loads plugins via entry points |
| Compilation | `DataProduct` → `CompiledArtifacts` |

### 3.2 Key Schemas (Unified 2-Type Model)

floe uses only **two configuration types**:

```python
# floe_core/schemas/manifest.py
class Manifest(BaseModel):
    """Unified configuration scope - enterprise or domain level."""
    apiVersion: str = "floe.dev/v1"
    kind: Literal["Manifest"] = "Manifest"
    metadata: ManifestMetadata
    scope: Literal["enterprise", "domain"]  # Determines tier
    parent: ManifestRef | None = None       # Required for domain scope
    plugins: PluginConfig | None = None
    approved_plugins: ApprovedPlugins | None = None  # Only for enterprise
    data_architecture: DataArchitectureConfig | None = None
    governance: GovernanceConfig | None = None
    services: ServiceDeployment | None = None

# floe_core/schemas/data_product.py
class DataProduct(BaseModel):
    """Unit of deployment - what data engineers create."""
    apiVersion: str = "floe.dev/v1"
    kind: Literal["DataProduct"] = "DataProduct"
    metadata: ProductMetadata
    platform: ManifestRef | None = None   # For centralized mode
    domain: ManifestRef | None = None     # For Data Mesh mode
    transforms: list[TransformConfig]     # dbt models
    schedule: ScheduleConfig | None = None
    # Optional: Data Mesh contracts
    output_ports: list[OutputPort] | None = None
    input_ports: list[InputPort] | None = None
```

See [ADR-0021](../architecture/adr/0021-data-architecture-patterns.md) and [Contracts](../contracts/index.md) for full schema definitions.

### 3.3 Plugin Interfaces (ABCs)

floe defines **11 plugin interfaces** for extensibility (see [plugin-system/index.md](../architecture/plugin-system/index.md) for canonical registry):

| Plugin Type | Entry Point | Purpose | ADR |
|-------------|-------------|---------|-----|
| ComputePlugin | `floe.computes` | Where dbt transforms execute | ADR-0010 |
| OrchestratorPlugin | `floe.orchestrators` | Job scheduling and execution | ADR-0033 |
| CatalogPlugin | `floe.catalogs` | Iceberg table catalog | ADR-0008 |
| StoragePlugin | `floe.storage` | Object storage (S3, GCS, Azure, MinIO) | ADR-0036 |
| TelemetryBackendPlugin | `floe.telemetry_backends` | OTLP telemetry backends (traces, metrics, logs) | ADR-0035 |
| LineageBackendPlugin | `floe.lineage_backends` | OpenLineage backends (data lineage) | ADR-0035 |
| DBTPlugin | `floe.dbt` | dbt compilation environment (local/fusion/cloud) | ADR-0043 |
| SemanticLayerPlugin | `floe.semantic_layers` | Business intelligence API | ADR-0001 |
| IngestionPlugin | `floe.ingestion` | Data loading from sources | ADR-0020 |
| SecretsPlugin | `floe.secrets` | Credential management | ADR-0023/0031 |
| IdentityPlugin | `floe.identity` | User authentication (OIDC) | ADR-0024 |

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins. DataQualityPlugin (Great Expectations, Soda) is documented in ADR-0044.

**Example Interfaces:**

```python
# floe_core/interfaces/compute.py
class ComputePlugin(ABC):
    """Interface for compute engines where dbt transforms execute."""
    name: str
    is_self_hosted: bool  # True=DuckDB/Spark, False=Snowflake/BigQuery

    @abstractmethod
    def generate_dbt_profile(self, config: ComputeConfig) -> dict: ...

    @abstractmethod
    def get_required_dbt_packages(self) -> list[str]: ...

# floe_core/interfaces/storage.py (NEW - ADR-0036)
class StoragePlugin(ABC):
    """Interface for object storage backends."""
    @abstractmethod
    def get_pyiceberg_fileio(self) -> FileIO: ...

    @abstractmethod
    def get_warehouse_uri(self, namespace: str) -> str: ...

# floe_core/interfaces/telemetry.py (ADR-0035)
class TelemetryBackendPlugin(ABC):
    """Interface for OTLP telemetry backends."""
    @abstractmethod
    def get_otlp_exporter_config(self) -> dict[str, Any]: ...

# floe_core/interfaces/lineage.py (ADR-0035)
class LineageBackendPlugin(ABC):
    """Interface for OpenLineage backends."""
    @abstractmethod
    def get_transport_config(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_namespace_mapping(self) -> dict[str, str]: ...

# floe_core/interfaces/orchestrator.py
class OrchestratorPlugin(ABC):
    """Interface for orchestration platforms."""
    @abstractmethod
    def create_definitions(self, artifacts: CompiledArtifacts) -> Any: ...

# floe_core/interfaces/catalog.py
class CatalogPlugin(ABC):
    """Interface for Iceberg catalogs."""
    @abstractmethod
    def connect(self, config: dict) -> Catalog: ...
```

**See**: [interfaces/](../architecture/interfaces/index.md) for complete ABC definitions

### 3.4 Enforcement Engine

```python
# floe_core/enforcement/validator.py
class DataProductValidator:
    """Validates DataProduct against Manifest constraints."""

    def validate(self, product: DataProduct, manifest: Manifest) -> list[ValidationError]:
        errors = []
        errors.extend(self._validate_naming(product, manifest))
        errors.extend(self._validate_quality_gates(product, manifest))
        errors.extend(self._validate_classification(product, manifest))
        return errors

    def _validate_naming(self, product, manifest) -> list[ValidationError]:
        """Enforce naming conventions (e.g., bronze_*, silver_*, gold_*)."""
        ...
```

---

## 4. floe-cli

CLI for both Platform Team and Data Team operations.

### Platform Team Commands (Centralized)

```bash
floe platform compile         # Validate manifest, build artifacts
floe platform publish v1.2.3  # Push to OCI registry
floe platform deploy          # Deploy services to K8s
floe platform status          # Check service health
```

### Data Team Commands (Centralized)

```bash
floe init --platform=v1.2.3   # Pull platform artifacts
floe compile                  # Validate against platform constraints
floe run                      # Execute pipeline
floe test                     # Run dbt tests
```

### Data Mesh Commands

For federated Data Mesh deployments:

```bash
# Platform Team (compiles any Manifest - enterprise or domain)
floe platform compile         # Compile Manifest (scope determines behavior)
floe platform publish v1.0.0  # Push to OCI registry
floe platform deploy          # Deploy platform services

# Data Product Team
floe init --platform=v1.0.0   # Initialize with centralized manifest
floe init --domain=sales:v2.0 # Initialize with domain manifest
floe compile                  # Validate against inherited constraints
floe run                      # Execute pipeline

# Discovery Commands
floe products list            # List data products
floe products describe sales.customer-360
floe contracts list           # List data contracts
```

---

## 5. Enforced Packages (Not Pluggable)

### 5.1 floe-dbt

dbt framework integration. **Not pluggable** (framework enforced; compilation environment pluggable via DBTPlugin)** - dbt is the enforced transformation standard.

| Responsibility | Description |
|----------------|-------------|
| Profile generation | Generate `profiles.yml` from compute plugin |
| Execution wrapper | Run dbt commands with proper configuration |
| OpenLineage emission | Emit lineage events during execution |

### 5.2 floe-iceberg

Apache Iceberg utilities. **Not pluggable** - Iceberg is the enforced table format.

| Responsibility | Description |
|----------------|-------------|
| Table management | Create/manage Iceberg tables |
| Compaction | Manage data file compaction |
| Time travel | Snapshot management |

---

## 6. Plugin Packages

Each plugin is self-contained with Python code and optional Helm chart.

### 6.1 Plugin Structure

```
plugins/floe-orchestrator-dagster/
├── src/
│   ├── __init__.py
│   └── plugin.py              # Implements OrchestratorPlugin ABC
├── chart/                     # Helm chart (if service deployment needed)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
└── pyproject.toml             # Entry point registration
```

### 6.2 Entry Point Registration

```toml
# pyproject.toml
[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterPlugin"

[project.entry-points."floe.charts"]
dagster = "floe_orchestrator_dagster:chart"
```

### 6.3 Available Plugins

floe supports **11 plugin types** (see [plugin-system/index.md](../architecture/plugin-system/index.md) for canonical registry):

| Category | Default | Alternatives | ADR |
|----------|---------|--------------|-----|
| **Compute** | DuckDB | Spark, Snowflake, Databricks, BigQuery | ADR-0010 |
| **Orchestration** | Dagster | Airflow 3.x | ADR-0033 |
| **Catalog** | Polaris | AWS Glue, Hive Metastore, Nessie | ADR-0008 |
| **Storage** | S3 | GCS, Azure Blob, MinIO | ADR-0036 |
| **Telemetry Backend** | Jaeger | Datadog, Grafana Cloud, AWS X-Ray | ADR-0035 |
| **Lineage Backend** | Marquez | Atlan, OpenMetadata | ADR-0035 |
| **DBT** | dbt-core (local) | dbt Fusion, dbt Cloud | ADR-0043 |
| **Semantic Layer** | Cube | dbt Semantic Layer, None | ADR-0001 |
| **Ingestion** | dlt | Airbyte (external) | ADR-0020 |
| **Secrets** | K8s Secrets | External Secrets Operator, Vault, Infisical | ADR-0023/0031 |
| **Identity** | Keycloak | Dex, Authentik, Okta, Auth0, Azure AD | ADR-0024 |

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins. DataQualityPlugin (Great Expectations, Soda) is documented in ADR-0044.

---

## 7. Charts

### 7.1 floe-platform

Meta-chart that assembles selected plugin charts based on `manifest.yaml`.

```yaml
# charts/floe-platform/Chart.yaml
dependencies:
  - name: floe-orchestrator-dagster
    condition: plugins.orchestrator.type == "dagster"
  - name: floe-catalog-polaris
    condition: plugins.catalog.type == "polaris"
```

### 7.2 floe-jobs

Base chart for pipeline job execution (dbt runs, quality checks).

---

## 8. Configuration Models

floe uses a **unified 2-type model** supporting all deployment patterns.

### 8.1 The Two Types

| Kind | Purpose | Owner |
|------|---------|-------|
| **`Manifest`** | Configuration scope (enterprise or domain level) | Platform Team |
| **`DataProduct`** | Unit of deployment (transforms, schedules, ports) | Data Team |

### 8.2 Deployment Modes

| Mode | Files | Use Case |
|------|-------|----------|
| **Simple** | Just `floe.yaml` (DataProduct) | Getting started, prototyping |
| **Centralized** | `manifest.yaml` + `floe.yaml` | Platform Team defines guardrails |
| **Data Mesh** | Enterprise manifest + Domain manifest + `floe.yaml` | Federated domain ownership |

### 8.3 Inheritance via `parent:` Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MANIFEST (scope: enterprise)                                                │
│  Owner: Central Platform Team                                                │
│  No parent: - this is the root                                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │ inherits via parent:
                ┌───────────────────────┴───────────────────────┐
                ▼                                               ▼
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│  MANIFEST (scope: domain)          │       │  MANIFEST (scope: domain)          │
│  parent: ref to enterprise         │       │  parent: ref to enterprise         │
│  Owner: Domain Platform Team       │       │  Owner: Domain Platform Team       │
│  Example: Sales Domain             │       │  Example: Marketing Domain         │
└───────────────────────────────────┬┘       └┬──────────────────────────────────┘
                                    │         │
                ┌───────────────────┴───┐     │
                ▼                       ▼     ▼
        ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
        │  DATAPRODUCT   │       │  DATAPRODUCT   │       │  DATAPRODUCT   │
        │  customer-360  │       │  pipeline-x    │       │  campaign      │
        │                │       │                │       │                │
        │  domain: ref   │       │  domain: ref   │       │  domain: ref   │
        │  to sales      │       │  to sales      │       │  to marketing  │
        └───────────────┘       └───────────────┘       └───────────────┘
```

**Key Principle**: Data engineers inherit platform constraints—they cannot override compute target, governance policies, or naming conventions.

See [ADR-0021: Data Architecture Patterns](../architecture/adr/0021-data-architecture-patterns.md) and [Contracts](../contracts/index.md) for full documentation.

---

## 9. Package Summary

| Package | Purpose | Pluggable? |
|---------|---------|------------|
| floe-core | Schemas, interfaces, enforcement | No (foundation) |
| floe-cli | CLI commands | No (foundation) |
| floe-dbt | dbt integration | No (enforced) |
| floe-iceberg | Iceberg utilities | No (enforced) |
| plugins/floe-compute-* | Compute engines | Yes |
| plugins/floe-orchestrator-* | Orchestration | Yes |
| plugins/floe-catalog-* | Iceberg catalogs | Yes |
| plugins/floe-semantic-* | Semantic layer | Yes |
| plugins/floe-ingestion-* | Data ingestion | Yes |
| plugins/floe-secrets-* | Secrets management | Yes |
