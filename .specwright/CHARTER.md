# floe Charter

## Identity

**floe** is an open-source data platform framework that transforms YAML configuration into a fully deployed, observable data stack on Kubernetes.

**Problem**: Data teams need orchestration, transformation, cataloging, observability, and governance — but wiring these systems together is undifferentiated toil. Each integration is custom, fragile, and invisible.

**Solution**: Two YAML files (`manifest.yaml` for platform config, `floe.yaml` for pipeline config) compile into a complete, deployable data platform with Dagster, dbt, Iceberg, Polaris, and OpenTelemetry — all wired together automatically.

## Consumers

| Consumer | Interaction | Expectation |
|----------|-------------|-------------|
| **Data Engineers** | Write `floe.yaml`, run `floe compile` | Fast iteration, clear errors, observable pipelines |
| **Platform Engineers** | Write `manifest.yaml`, run `floe deploy` | Governance guardrails, plugin selection, K8s-native |
| **floe Maintainers** | Build framework, plugins, Helm charts | Clean boundaries, testable modules, extensible |

## Architectural Invariants

These will NOT change:

1. **Two-file configuration**: `manifest.yaml` (platform) + `floe.yaml` (pipelines)
2. **CompiledArtifacts as sole contract**: The only bridge between floe-core and all other packages
3. **Plugin-first**: All configurable behavior via entry-point-discovered plugins
4. **Four-layer model**: Foundation → Configuration → Services → Data (config flows DOWN only)
5. **K8s-native deployment**: Helm charts are the deployment mechanism, not scripts
6. **Technology ownership**: dbt=SQL, Dagster=orchestration, Iceberg=storage, Polaris=catalog

## Foundational Technologies

Not up for debate — these define floe:

| Technology | Role | Why Non-Negotiable |
|------------|------|-------------------|
| Apache Iceberg | Table format | ACID, time travel, schema evolution — industry standard |
| OpenTelemetry | Observability | Vendor-neutral traces/metrics/logs — CNCF standard |
| OpenLineage | Data lineage | Vendor-neutral lineage events — LF AI standard |
| dbt | Transformation | SQL-first transforms — dominant in modern data stack |
| Kubernetes | Deployment | Container orchestration — universal infrastructure |
| Pydantic v2 | Validation | Type-safe config with JSON Schema export |

## Pluggable Technologies

Platform Team selects once per deployment:

- **Compute**: DuckDB (default), Snowflake, Spark, BigQuery, Databricks
- **Orchestrator**: Dagster (default), Airflow 3.x, Prefect
- **Catalog**: Polaris (default), AWS Glue, Hive
- **Storage**: S3/MinIO (default), GCS, Azure Blob
- **+ 7 more plugin categories** (identity, secrets, RBAC, alerting, quality, ingestion, semantic)

## Quality Identity

floe is pre-alpha. Quality standards are production-grade because:
- No backwards compatibility debt — break things freely
- Tests are brutal by design — they catch real bugs, not validate mocks
- The constitution is enforced, not aspirational

**Version**: 1.0.0 | **Created**: 2026-02-12
