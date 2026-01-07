# ADR-0018: Opinionation Boundaries

## Status

Accepted

## Context

floe must balance two competing needs:

1. **Strong opinions** - Make it easy to get started with proven defaults
2. **Flexibility** - Allow organizations to use their existing infrastructure

Without clear boundaries, this creates confusion:
- Which components are required vs optional?
- What can Platform Teams customize?
- What do Data Engineers inherit without choice?

## Decision

Define clear opinionation boundaries:

1. **ENFORCED** - Core platform identity, non-negotiable
2. **PLUGGABLE** - Platform Team selects once, Data Engineers inherit

### ENFORCED Components (Non-Negotiable)

These standards define floe's core identity:

| Component | Standard | Rationale |
|-----------|----------|-----------|
| **Table Format** | Apache Iceberg | Open, multi-engine, ACID, time-travel |
| **Telemetry** | OpenTelemetry | Vendor-neutral industry standard |
| **Data Lineage** | OpenLineage | Industry standard for lineage |
| **Deployment** | Kubernetes-native | Portable, declarative infrastructure |
| **Configuration** | Declarative YAML | Explicit over implicit |
| **Transformation** | dbt-centric | "dbt owns SQL" - proven, target-agnostic |

**Why these are enforced:**
- **Iceberg**: Provides the open table format foundation. Without it, multi-engine access and time-travel are not possible.
- **OpenTelemetry/OpenLineage**: Provide consistent observability. Custom formats fragment the ecosystem.
- **Kubernetes**: Provides the deployment abstraction. Supporting Docker Compose creates testing parity issues.
- **dbt**: Provides the transformation layer. Building custom SQL handling duplicates proven tooling.

### PLUGGABLE Components (Platform Team Choice)

Platform Team selects these ONCE in `platform-manifest.yaml`. Data Engineers inherit them:

| Component | Default | Alternatives |
|-----------|---------|--------------|
| **Storage** | MinIO | S3, ADLS2, GCS |
| **Compute** | DuckDB | Spark, Snowflake, Databricks, BigQuery, Redshift |
| **Ingestion** | dlt | Airbyte (external) |
| **Orchestration** | Dagster | Airflow, Prefect, Argo Workflows |
| **Catalog** | Polaris | AWS Glue, Hive Metastore, Nessie |
| **Semantic Layer** | Cube | dbt Semantic Layer, None |
| **Data Quality** | dbt tests | Great Expectations, Soda (future) |
| **Secrets** | K8s Secrets | External Secrets Operator, Vault |
| **Identity** | Keycloak | Dex, Authentik, Zitadel, Okta, Auth0, Azure AD |
| **Telemetry Backend** | OTLP Collector | Datadog, Grafana Cloud |

## Consequences

### Positive

- **Clear boundaries** - Teams know what they can change
- **Consistent foundation** - Iceberg + OTel + OpenLineage everywhere
- **Flexibility where it matters** - Choose your compute, orchestrator
- **Batteries included** - Defaults work out of the box

### Negative

- **Less flexibility** - Cannot swap out Iceberg for Delta Lake
- **Learning curve** - Teams must learn enforced standards
- **Potential lock-in** - Dependent on Iceberg ecosystem

### Neutral

- Plugin system provides escape hatch for most customization needs
- Enforced standards are industry-leading choices
- Platform Team can still customize significantly via plugins

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

### Plugin Interface vs Configuration Switch

**Per ADR-0037 (Composability Principle)**, when making something PLUGGABLE, choose between:
1. **Plugin Interface** (ABC with entry points) - Preferred for extensibility
2. **Configuration Switch** (if/else on config value) - Only for fixed enums

**Decision Tree:**

```
┌────────────────────────────────────────────────────────────────┐
│  Question: How should we make this component pluggable?        │
└─────────────────────────────┬──────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  Multiple implementations      │
              │  exist OR may exist?           │
              └───────────┬───────────────────┘
                          │
              ┌───────────┴──────────┐
              │                       │
             YES                     NO
              │                       │
              ▼                       ▼
    ┌──────────────────┐    ┌──────────────────┐
    │  User needs to    │    │  Fixed set of    │
    │  swap or extend?  │    │  options (enum)? │
    └─────────┬─────────┘    └─────────┬────────┘
              │                        │
     ┌────────┴────────┐      ┌────────┴────────┐
    YES               NO      YES               NO
     │                 │       │                 │
     ▼                 ▼       ▼                 ▼
┌─────────┐     ┌─────────┐ ┌─────────┐   ┌─────────┐
│ PLUGIN  │     │ CONFIG  │ │ CONFIG  │   │ ENFORCE │
│   ✅    │     │   ✅    │ │   ✅    │   │   ✅    │
└─────────┘     └─────────┘ └─────────┘   └─────────┘
```

**Examples:**

| Scenario | Decision | Rationale |
|----------|----------|-----------|
| Observability backends (Jaeger, Datadog) | **Plugin** ✅ | Multiple implementations, users swap backends (ADR-0035) |
| Storage backends (S3, GCS, Azure) | **Plugin** ✅ | Multiple implementations, different credentials (ADR-0036) |
| Compute engines (DuckDB, Snowflake) | **Plugin** ✅ | Multiple implementations, organization choice |
| Environment (dev, staging, prod) | **Configuration** ✅ | Fixed enum, no custom implementations |
| Log level (DEBUG, INFO, WARN) | **Configuration** ✅ | Fixed enum, no custom implementations |
| OpenTelemetry SDK (emission) | **Enforce** ✅ | No alternatives, core platform identity |

**Why Plugin Interface is Preferred:**

1. **Extensibility**: Community can add new implementations without core changes
2. **Testing**: Mock plugin interface in tests (no real services needed)
3. **Composability**: Aligns with ADR-0037 principle of small, interchangeable components
4. **Decoupling**: Core doesn't know about implementation details

**When Configuration is Acceptable:**

1. **Fixed set of values**: Environment (dev/staging/prod), log levels (DEBUG/INFO)
2. **No new implementations expected**: Boolean flags, simple toggles
3. **Trivial logic**: No complex behavior differences between options

**Anti-Pattern: Configuration Switch for Extensible Behavior**

```python
# ❌ BAD: Configuration switch (coupling)
def get_backend(config: dict):
    if config["type"] == "jaeger":
        return JaegerBackend()
    elif config["type"] == "datadog":
        return DatadogBackend()
    # Every new backend requires core changes

# ✅ GOOD: Plugin interface (composable)
registry = PluginRegistry()
backend = registry.discover("floe.observability")[config["type"]]
```

## Plugin Selection Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Platform Team Decision                                                  │
│                                                                          │
│  "We use Snowflake for compute, existing Airflow for orchestration"     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  platform-manifest.yaml                                                  │
│                                                                          │
│  plugins:                                                                │
│    compute:                                                              │
│      type: snowflake    # Pluggable ✓                                   │
│    orchestrator:                                                         │
│      type: airflow      # Pluggable ✓                                   │
│    catalog:                                                              │
│      type: polaris      # Pluggable ✓ (default)                         │
│                                                                          │
│  # ENFORCED (cannot change):                                            │
│  # - Iceberg table format                                               │
│  # - OpenTelemetry observability                                        │
│  # - OpenLineage lineage                                                │
│  # - dbt transformation                                                 │
│  # - Kubernetes deployment                                              │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Data Engineers Inherit                                                  │
│                                                                          │
│  # floe.yaml - Data engineers ONLY define:                              │
│  transforms:                                                             │
│    - type: dbt          # Enforced ✓ (must use dbt)                     │
│      path: models/                                                       │
│                                                                          │
│  # They inherit without choice:                                          │
│  # - Snowflake compute (from platform)                                  │
│  # - Airflow orchestration (from platform)                              │
│  # - Polaris catalog (from platform)                                    │
│  # - Iceberg tables (enforced)                                          │
│  # - OpenTelemetry (enforced)                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Anti-Patterns

### DON'T: Allow Data Engineers to select compute per-pipeline

```yaml
# BAD: Per-pipeline compute selection causes drift
# floe.yaml
transforms:
  - type: dbt
    compute: snowflake  # ❌ Should be inherited from platform
```

### DON'T: Allow per-environment compute targets

```yaml
# BAD: Different compute per environment causes drift
# platform-manifest.yaml
environments:
  development:
    compute: duckdb      # ❌ Causes "works in dev, fails in prod"
  production:
    compute: snowflake   # ❌ Environment drift
```

### DO: Set compute once at platform level

```yaml
# GOOD: Single compute target, no drift
# platform-manifest.yaml
plugins:
  compute:
    type: snowflake  # ✓ Same for dev, staging, prod
```

## References

- [ADR-0037: Composability Principle](0037-composability-principle.md) - Plugin vs configuration decision criteria
- [ADR-0035: Observability Plugin Interface](0035-observability-plugin-interface.md) - ObservabilityPlugin example
- [ADR-0036: Storage Plugin Interface](0036-storage-plugin-interface.md) - StoragePlugin example
- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md)
- [ADR-0008: Repository Split](0008-repository-split.md) - Plugin architecture
- [ADR-0009: dbt Owns SQL](0009-dbt-owns-sql.md) - Enforced transformation
- [ADR-0010: Target-Agnostic Compute](0010-target-agnostic-compute.md) - Pluggable compute
- [03-solution-strategy.md](../../guides/03-solution-strategy.md) - Solution strategy
