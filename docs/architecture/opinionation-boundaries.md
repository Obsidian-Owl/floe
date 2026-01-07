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

| Component | Default | Alternatives |
|-----------|---------|--------------|
| **Compute** | DuckDB | Spark, Snowflake, Databricks, BigQuery, Redshift |
| **Orchestration** | Dagster | Airflow 3.x, Prefect, Argo Workflows |
| **Catalog** | Polaris | AWS Glue, Hive Metastore, Nessie |
| **Storage** | MinIO (local), S3 (production)* | GCS, Azure Blob, S3-compatible (NetApp, Dell) |
| **Telemetry Backend** | Jaeger (local), Datadog (production) | Grafana Cloud, AWS X-Ray, custom |
| **Lineage Backend** | Marquez (local), Atlan (production) | OpenMetadata, Egeria, custom |
| **dbt Execution Environment** | dbt-core (local) | dbt Fusion (Rust-based), dbt Cloud (deferred) |
| **Semantic Layer** | Cube | dbt Semantic Layer, None |
| **Ingestion** | dlt | Airbyte (external) |
| **Data Quality Framework** | Great Expectations | Soda, dbt Expectations, custom |
| **Secrets** | K8s Secrets | External Secrets Operator, Vault, Infisical |

**Note:** *MinIO is production-grade for on-premises, data sovereignty, and multi-cloud deployments.

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

### DON'T: Allow Data Engineers to select compute

```yaml
# BAD: Per-pipeline compute selection
transforms:
  - type: dbt
    compute: snowflake  # ❌ Should inherit from platform
```

### DON'T: Allow per-environment compute

```yaml
# BAD: Different compute per environment causes drift
environments:
  development:
    compute: duckdb      # ❌ "Works in dev, fails in prod"
  production:
    compute: snowflake   # ❌ Environment drift
```

### DO: Set compute once at platform level

```yaml
# GOOD: Single compute target, no drift
plugins:
  compute:
    type: snowflake  # ✓ Same for dev, staging, prod
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
