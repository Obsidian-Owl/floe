# Opinionation Boundaries

This document defines what is enforced vs pluggable in floe.

## Core Principle

floe balances strong opinions with flexibility:

- **ENFORCED**: Core platform identity, non-negotiable standards
- **PLUGGABLE**: Platform Team selects once, Data Engineers inherit

## ENFORCED Components

These standards define floe and cannot be changed:

| Component | Standard | Rationale |
|-----------|----------|-----------|
| **Table Format** | Apache Iceberg | Open, multi-engine, ACID, time-travel |
| **Telemetry** | OpenTelemetry | Vendor-neutral industry standard |
| **Data Lineage** | OpenLineage | Industry standard for lineage |
| **Deployment** | Kubernetes-native | Portable, declarative infrastructure |
| **Configuration** | Declarative YAML | Explicit over implicit |
| **Transformation** | dbt-centric | "dbt owns SQL" - proven, target-agnostic |

### Why These Are Enforced

**Apache Iceberg**
- Provides open table format foundation
- Enables multi-engine access (Spark, Trino, DuckDB)
- ACID transactions and time-travel
- Swapping for Delta Lake would fragment the ecosystem

**OpenTelemetry**
- Vendor-neutral observability
- Single SDK for traces, metrics, logs
- W3C standard propagation
- Custom telemetry would create lock-in

**OpenLineage**
- Industry standard for data lineage
- Automatic propagation through pipeline
- Integrates with Dagster, dbt, Spark
- Custom lineage would limit interoperability

**Kubernetes-native**
- Portable across cloud providers
- Declarative infrastructure
- Standard for container orchestration
- Supporting Docker Compose creates testing parity issues

**dbt-centric**
- Proven transformation layer
- Handles SQL dialect translation
- Large ecosystem of packages
- Building custom SQL handling duplicates effort

## PLUGGABLE Components

Platform Team selects these once in `manifest.yaml`:

| Component | Alpha-Supported Default | Implemented Alternatives | Planned Or Ecosystem Examples |
| --- | --- | --- | --- |
| Compute | DuckDB | None validated as an alpha product path | Spark, Snowflake, Databricks, BigQuery, Redshift |
| Orchestration | Dagster | None validated as an alpha product path | Airflow 3.x, Prefect, Argo Workflows |
| Catalog | Polaris | None validated as an alpha product path | AWS Glue, Hive Metastore, Nessie |
| Storage | S3-compatible object storage through the implemented storage plugin; demo uses MinIO | S3-compatible backends where configured and validated by the platform team | GCS, Azure Blob, provider-native object storage |
| Telemetry Backend | Jaeger and console telemetry plugins | OTLP-compatible backends through standard OpenTelemetry configuration | Datadog, Grafana Cloud, AWS X-Ray |
| Lineage Backend | Marquez | None validated as an alpha product path | Atlan, OpenMetadata, Egeria |
| dbt Runtime | dbt Core | dbt Fusion plugin exists as an implementation path requiring explicit validation | dbt Cloud |
| Semantic Layer | Cube reference implementation | None validated as an alpha product path | dbt Semantic Layer |
| Ingestion | dlt plugin primitive | None validated as a full product path | Airbyte-style integrations |
| Data Quality Framework | dbt expectations and Great Expectations plugin primitives | None validated as a full product path | Soda, custom |
| Secrets | Kubernetes Secrets and Infisical plugin primitives | None validated as a full product path | Vault, External Secrets Operator |

### Why These Are Pluggable

**Compute**
- Organizations have existing investments
- Different scale requirements (DuckDB vs Spark)
- Cost considerations (self-hosted vs cloud)
- All compute targets produce Iceberg tables (enforced)

**Orchestration**
- Many organizations already use Airflow
- Different feature requirements
- Operational familiarity matters
- All orchestrators emit OpenLineage (enforced)

**Catalog**
- Cloud provider preferences (AWS → Glue)
- Existing infrastructure investments
- Different feature requirements
- All catalogs support Iceberg (enforced)

**Ingestion**
- Different connector requirements
- Existing Airbyte deployments
- Scale and complexity tradeoffs
- All ingestion writes to Iceberg (enforced)

**Storage**
- Cloud provider preferences (AWS S3 vs GCP GCS vs Azure Blob)
- Data sovereignty requirements (on-prem MinIO, NetApp)
- Multi-cloud strategies (S3 + GCS for disaster recovery)
- Cost optimization (MinIO vs cloud object storage)
- All storage via PyIceberg FileIO (enforced)

**Telemetry Backend**
- Existing telemetry investments (Datadog APM, Grafana Cloud)
- Cost considerations (self-hosted Jaeger vs SaaS backends)
- Feature requirements (APM, distributed tracing, alerting, metrics visualization)
- Compliance needs (data residency for telemetry data)
- All telemetry via OpenTelemetry + OTLP Collector (enforced)

**Lineage Backend**
- Existing lineage investments (Atlan, OpenMetadata)
- Cost considerations (self-hosted Marquez vs SaaS data catalogs)
- Feature requirements (impact analysis, column-level lineage, data governance)
- Integration with existing data catalogs (Atlan, Collibra)
- All lineage via OpenLineage HTTP transport (enforced)

**Data Quality Framework**
- Different quality check requirements (statistical vs rule-based)
- Existing Great Expectations or Soda investments
- Feature requirements (expectation suites vs YAML checks)
- Integration preferences (Python API vs CLI)
- All quality plugins via DataQualityPlugin interface (enforced)
- dbt tests remain enforced (wrapped by DBTExpectationsPlugin for unified scoring)

## Decision Matrix

### When to ENFORCE

| Criteria | Example |
|----------|---------|
| Core platform identity | Iceberg table format |
| Cross-cutting concern | OpenTelemetry observability |
| Industry standard | OpenLineage lineage |
| Deployment model | Kubernetes-native |
| Significant re-architecture to swap | dbt transformation |

### When to make PLUGGABLE

| Criteria | Example |
|----------|---------|
| Multiple valid options exist | Compute: DuckDB vs Snowflake |
| Organization already has choice | Orchestration: existing Airflow |
| Different scale requirements | Spark vs DuckDB |
| Cloud provider preference | AWS Glue vs Polaris |
| Cost considerations | Managed vs self-hosted |

## Configuration Example

```yaml
# manifest.yaml (Platform Team)
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: "1.0.0"
  scope: enterprise

plugins:
  # PLUGGABLE: Platform Team selects
  compute: snowflake          # Their choice
  orchestrator: dagster       # Default
  catalog: glue               # AWS preference
  storage: s3                 # Cloud storage
  observability: datadog      # Existing investment
  semantic_layer: cube        # Default
  ingestion: dlt              # Default

# ENFORCED: Cannot change
# - Iceberg (all tables are Iceberg)
# - OpenTelemetry (all telemetry via OTel)
# - OpenLineage (all lineage via OpenLineage)
# - dbt (all transforms via dbt)
# - K8s (all deployment via K8s)
```

```yaml
# floe.yaml (Data Team)
apiVersion: floe.dev/v1
kind: DataProduct
metadata:
  name: customer-analytics
  version: "1.0"

platform:
  ref: oci://registry.acme.com/floe-platform:v1.2.3

# Data engineers ONLY define transforms
# They inherit all plugin choices
transforms:
  - type: dbt      # ENFORCED: must use dbt
    path: models/
```

## Anti-Patterns

### DO: Allow Approved Per-Transform Compute Selection

Platform Engineers approve compute targets and choose defaults. Data Engineers may select compute per transform only from that approved list.

```yaml
plugins:
  compute:
    approved:
      - name: duckdb
      - name: spark
    default: duckdb
```

```yaml
transforms:
  - type: dbt
    path: models/staging
    compute: spark
  - type: dbt
    path: models/marts
    compute: duckdb
```

### DON'T: Use Unapproved Compute

```yaml
transforms:
  - type: dbt
    path: models/marts
    compute: unapproved-snowflake-account
```

### DON'T: Create Per-Environment Compute Drift

```yaml
environments:
  development:
    compute: duckdb
  production:
    compute: snowflake
```

## Consistency Guarantees

Because core components are enforced:

| Guarantee | How |
|-----------|-----|
| All tables are Iceberg | Enforced table format |
| All telemetry is OTel | Enforced observability |
| All lineage is OpenLineage | Enforced lineage |
| All transforms use dbt | Enforced transformation |
| All deployment is K8s | Enforced infrastructure |

This enables:
- Multi-engine queries (any engine can read Iceberg)
- Unified observability (single dashboard for all pipelines)
- Complete lineage (end-to-end data flow visibility)
- Consistent testing (K8s in CI matches production)

## Related Documents

- [ADR-0018: Opinionation Boundaries](adr/0018-opinionation-boundaries.md) - Decision criteria
- [ADR-0037: Composability Principle](adr/0037-composability-principle.md) - Plugin vs configuration
- [ADR-0035: Telemetry and Lineage Backend Plugins](adr/0035-observability-plugin-interface.md) - TelemetryBackendPlugin + LineageBackendPlugin
- [ADR-0036: Storage Plugin Interface](adr/0036-storage-plugin-interface.md) - StoragePlugin
- [ADR-0038: Data Mesh Architecture](adr/0038-data-mesh-architecture.md) - Three-tier inheritance
- [Four-Layer Overview](four-layer-overview.md)
- [Platform Enforcement](platform-enforcement.md)
- [Plugin Architecture](plugin-system/index.md)
