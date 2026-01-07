# floe Architecture Summary

This document summarizes the architectural redesign of floe with a platform enforcement model.

## Executive Summary

floe has been redesigned with a **four-layer architecture** and **platform enforcement model** that:

1. **Separates platform configuration from pipeline code**
2. **Enforces guardrails at compile time**
3. **Uses a plugin system for flexibility**
4. **Stores immutable platform artifacts in OCI registries**

## Key Architectural Decisions

### Organizational Patterns

floe supports two organizational patterns:

| Pattern | Configuration Model | Use Case |
|---------|-------------------|----------|
| **Centralized** | Platform → Pipeline (2-file) | Traditional centralized data team |
| **Data Mesh** | Enterprise → Domain → Product (3-tier) | Federated domain ownership |

For Data Mesh, the configuration hierarchy extends:
- **Enterprise Platform**: Global governance, approved plugins
- **Domain Platform**: Domain-specific choices, domain namespace
- **Data Products**: Input/output ports, SLAs, data contracts

### Composability Principle

floe is built on **composability** as a core architectural principle (ADR-0037):

- **Plugin Architecture > Configuration Switches**: Extensibility via entry points (`floe.computes`, `floe.orchestrators`, etc.), not if/else config
- **Interface > Implementation**: Define ABCs (ComputePlugin, TelemetryBackendPlugin, LineageBackendPlugin), not concrete classes
- **Progressive Disclosure**: Point to detailed docs, don't duplicate content
- **Opt-in Complexity**: Start simple (2-tier), scale to Data Mesh (3-tier) without rewrites

**11 Plugin Types** enable flexibility while maintaining enforced standards (see [plugin-system/index.md](plugin-system/index.md) for canonical registry):
- Compute, Orchestrator, Catalog, Storage, TelemetryBackend, LineageBackend
- DBT, Semantic Layer, Ingestion, Data Quality, Secrets, Identity

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins.

**See**: [ADR-0037: Composability Principle](adr/0037-composability-principle.md)

### Four-Layer Architecture

```
Layer 4: DATA (Ephemeral Jobs)
    │ Owner: Data Engineers
    │ K8s: Jobs (run-to-completion)
    │ Config: floe.yaml
    ▼
Layer 3: SERVICES (Long-lived)
    │ Owner: Platform Engineers
    │ K8s: Deployments, StatefulSets
    │ Deploy: floe platform deploy
    ▼
Layer 2: CONFIGURATION (Enforcement)
    │ Owner: Platform Engineers
    │ Storage: OCI Registry (immutable)
    │ Config: platform-manifest.yaml
    ▼
Layer 1: FOUNDATION (Framework Code)
    │ Owner: floe Maintainers
    │ Distribution: PyPI, Helm
```

### Two-File Configuration Model

| File | Owner | Purpose |
|------|-------|---------|
| `platform-manifest.yaml` | Platform Team | Define guardrails (rarely changes) |
| `floe.yaml` | Data Engineers | Define pipelines (changes frequently) |

### Opinionation Boundaries

**ENFORCED (Non-negotiable):**
- Apache Iceberg (table format)
- OpenTelemetry (observability)
- OpenLineage (data lineage)
- dbt (transformation)
- Kubernetes-native (deployment)

**PLUGGABLE (Platform Team selects once):**
- Compute: DuckDB, Spark, Snowflake, Databricks, BigQuery
- Orchestration: Dagster, Airflow, Prefect
- Catalog: Polaris, AWS Glue, Hive
- Storage: S3, GCS, Azure Blob, MinIO
- Observability Backend: Jaeger, Datadog, Grafana Cloud, AWS X-Ray
- Semantic Layer: Cube, dbt Semantic Layer, None
- Ingestion: dlt, Airbyte
- Secrets: K8s Secrets, External Secrets Operator, Vault, Infisical
- Identity: Keycloak, Dex, Authentik, Okta, Auth0

## Documentation Structure

### ADRs Created/Amended

| ADR | Title | Action |
|-----|-------|--------|
| ADR-0008 | Repository Split | **AMENDED**: Added plugin architecture + API versioning |
| ADR-0010 | Target-Agnostic Compute | **AMENDED**: Added ComputePlugin interface |
| ADR-0012 | Data Classification Governance | **AMENDED**: Added quality gates section |
| ADR-0016 | Platform Enforcement Architecture | **AMENDED**: Added four-layer details + OCI storage |
| ADR-0017 | K8s Testing Infrastructure | Existed (created in previous session) |
| ADR-0018 | Opinionation Boundaries | **AMENDED**: Added plugin vs configuration decision criteria |
| ADR-0019 | Platform Services Lifecycle | **NEW**: Long-lived vs ephemeral |
| ADR-0020 | Ingestion Plugins | **NEW**: dlt + Airbyte |
| ADR-0021 | Data Architecture Patterns | **NEW**: Medallion, Kimball, Data Vault |
| ADR-0035 | Observability Plugin Interface | **NEW**: Pluggable observability backends (Jaeger, Datadog, Grafana Cloud) |
| ADR-0036 | Storage Plugin Interface | **NEW**: PyIceberg FileIO pattern for S3, GCS, Azure, MinIO |
| ADR-0037 | Composability Principle | **NEW**: Core architectural principle for plugin design |
| ADR-0038 | Data Mesh Architecture | **NEW**: Unified Manifest schema, 3-tier inheritance |

### Architecture Documents Created

| Document | Purpose |
|----------|---------|
| `four-layer-overview.md` | Comprehensive layer diagram and details |
| `platform-enforcement.md` | How platform constraints are enforced |
| `platform-services.md` | Layer 3 services (orchestrator, catalog, etc.) |
| `plugin-system/` | Plugin structure and discovery |
| `interfaces/` | Abstract Base Classes for all plugins |
| `opinionation-boundaries.md` | What's enforced vs pluggable |
| `platform-artifacts.md` | OCI registry storage model |

## Key Interfaces

floe defines **11 plugin interfaces** (ABCs) for extensibility (see [plugin-system/index.md](plugin-system/index.md) for canonical registry):

| Plugin Type | Purpose | Entry Point | ADR |
|-------------|---------|-------------|-----|
| `ComputePlugin` | Where dbt transforms execute | `floe.computes` | ADR-0010 |
| `OrchestratorPlugin` | Job scheduling and execution | `floe.orchestrators` | ADR-0033 |
| `CatalogPlugin` | Iceberg table catalog | `floe.catalogs` | ADR-0008 |
| `StoragePlugin` | Object storage (S3, GCS, Azure, MinIO) | `floe.storage` | ADR-0036 |
| `TelemetryBackendPlugin` | OTLP telemetry backends (traces, metrics, logs) | `floe.telemetry_backends` | ADR-0035 |
| `LineageBackendPlugin` | OpenLineage backends (data lineage) | `floe.lineage_backends` | ADR-0035 |
| `DBTPlugin` | dbt compilation environment (local/fusion/cloud) | `floe.dbt` | ADR-0043 |
| `SemanticLayerPlugin` | Business intelligence API | `floe.semantic_layers` | ADR-0001 |
| `IngestionPlugin` | Data loading from sources | `floe.ingestion` | ADR-0020 |
| `SecretsPlugin` | Credential management | `floe.secrets` | ADR-0023/0031 |
| `IdentityPlugin` | User authentication (OIDC) | `floe.identity` | ADR-0024 |

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins. DataQualityPlugin (Great Expectations, Soda) is documented in ADR-0044.

**See**: [interfaces/](interfaces/index.md) for complete ABC definitions with method signatures

### Example: ComputePlugin

```python
class ComputePlugin(ABC):
    def generate_dbt_profile(self, config: ComputeConfig) -> dict
    def get_required_dbt_packages(self) -> list[str]
    def validate_connection(self, config: ComputeConfig) -> ConnectionResult
    def get_resource_requirements(self, workload_size: str) -> ResourceSpec
```

### Example: TelemetryBackendPlugin and LineageBackendPlugin

Observability uses two independent plugins (ADR-0035):

```python
class TelemetryBackendPlugin(ABC):
    """Configure OTLP backends for traces, metrics, logs."""
    def get_otlp_exporter_config(self) -> dict[str, Any]
    def get_helm_values_override(self) -> dict[str, Any]

class LineageBackendPlugin(ABC):
    """Configure OpenLineage backends for data lineage."""
    def get_transport_config(self) -> dict[str, Any]
    def get_namespace_mapping(self) -> dict[str, str]
```

### Example: StoragePlugin

```python
class StoragePlugin(ABC):
    def get_pyiceberg_fileio(self) -> FileIO
    def get_warehouse_uri(self, namespace: str) -> str
    def get_dbt_profile_config(self) -> dict[str, Any]
    def get_dagster_io_manager_config(self) -> dict[str, Any]
    def get_helm_values_override(self) -> dict[str, Any]
```

## Repository Structure

```
floe/
├── floe-core/           # Schemas, interfaces, enforcement engine
├── floe-cli/            # CLI for Platform Team and Data Team
├── floe-dbt/            # ENFORCED: dbt framework; runtime PLUGGABLE (ADR-0043)
├── floe-iceberg/        # ENFORCED: Iceberg utilities
│
├── plugins/             # ALL PLUGGABLE COMPONENTS (11 plugin types)
│   ├── floe-compute-duckdb/
│   ├── floe-compute-spark/
│   ├── floe-compute-snowflake/
│   ├── floe-orchestrator-dagster/
│   ├── floe-orchestrator-airflow/
│   ├── floe-catalog-polaris/
│   ├── floe-catalog-glue/
│   ├── floe-storage-s3/
│   ├── floe-storage-minio/
│   ├── floe-storage-gcs/
│   ├── floe-observability-jaeger/
│   ├── floe-observability-datadog/
│   ├── floe-semantic-cube/
│   ├── floe-ingestion-dlt/
│   ├── floe-secrets-eso/
│   ├── floe-secrets-infisical/
│   └── floe-identity-keycloak/
│
├── charts/
│   ├── floe-platform/   # Meta-chart for platform services
│   └── floe-jobs/       # Base chart for pipeline jobs
│
└── docs/
```

## CLI Commands

### Platform Team

```bash
floe platform compile     # Validate and build artifacts
floe platform test        # Run policy tests
floe platform publish     # Push to OCI registry
floe platform deploy      # Deploy services to K8s
floe platform status      # Check service health
```

### Data Team

```bash
floe init --platform=v1.2.3  # Pull platform artifacts
floe compile                  # Validate against platform
floe run                      # Execute pipeline
floe test                     # Run dbt tests
```

## Consolidation Achieved

The documentation was consolidated to reduce complexity:

- **4 existing ADRs amended** (vs creating separate overlapping ADRs)
- **4 new ADRs created** (only for truly distinct decisions)
- **Reduced from 10 planned ADRs to 8 actual ADRs**
- **Cross-references maintained** between all documents

## Data Mesh Resources

For Data Mesh support, floe introduces additional resource types:

| Resource | Owner | Purpose |
|----------|-------|---------|
| `EnterpriseManifest` | Central Platform Team | Global governance, approved plugins |
| `DomainManifest` | Domain Platform Team | Domain-specific choices |
| `DataProduct` | Product Team | Input/output ports, SLAs |
| `DataContract` | Auto-generated | Cross-domain data sharing contracts |

See [ADR-0021: Data Architecture Patterns](adr/0021-data-architecture-patterns.md) for full Data Mesh documentation.

## Documents Updated for Data Mesh Support

The following documents have been updated to support the Data Mesh architecture pattern:

### Runtime Documentation

| Document | Changes |
|----------|---------|
| `04-building-blocks.md` | Added Data Mesh schemas, CLI commands, three-tier config model |
| `05-runtime-view.md` | Added Data Mesh workflows (product registration, contracts, lineage) |
| `06-deployment-view.md` | Added Data Mesh topology, domain namespaces, multi-cluster patterns |
| `07-crosscutting.md` | Updated configuration hierarchy for federated governance |

### Architecture Documentation

| Document | Changes |
|----------|---------|
| `four-layer-overview.md` | Added Data Mesh layer extension diagram |
| `platform-enforcement.md` | Added three-tier enforcement model, data contracts |
| `ADR-0021` | Comprehensive Data Mesh architecture (already existed) |

### Contracts

| Document | Changes |
|----------|---------|
| `compiled-artifacts.md` | Added `domain_context` and `data_product` fields |

## Next Steps (Implementation Phase)

1. Implement floe-core schemas (Pydantic models)
2. Implement plugin interfaces (ABCs)
3. Create default plugins (DuckDB, Dagster, Polaris, Cube, dlt)
4. Create Helm charts for platform deployment
5. Implement CLI commands
6. Create integration tests using K8s (ADR-0017)
7. Implement Data Mesh resource types (EnterpriseManifest, DomainManifest, DataProduct, DataContract)
8. Implement cross-domain data contract validation
9. Implement federated lineage with domain-qualified namespaces

## Related Documents

- [ADR Index](adr/index.md) - All Architecture Decision Records
- [Architecture Index](index.md) - All architecture documentation
- [Guides](../guides/index.md) - Implementation guides (Arc42)
- [Contracts](../contracts/index.md) - Interface contracts
