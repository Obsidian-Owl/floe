# 03. Solution Strategy

This document describes the fundamental technology decisions and approaches for floe.

---

## 1. Composability First

### 1.1 Core Architectural Principle

floe is built on **composability** as its foundational principle ([ADR-0037](../architecture/adr/0037-composability-principle.md)):

- **Plugin Architecture > Configuration Switches**: Use entry points for extensibility, not if/else config
- **Interface > Implementation**: Define ABCs (Abstract Base Classes), not concrete classes
- **Progressive Disclosure**: Start simple, opt-in to complexity without rewrites
- **Opt-in Complexity**: 2-tier config (single team) → 3-tier config (Data Mesh) seamlessly

### 1.2 Design Decisions

When adding features, composability guides the decision:

| Scenario | Composable Approach | Anti-Pattern |
|----------|-------------------|--------------|
| Multiple implementations exist | Plugin interface with entry points | if/else configuration switch |
| User needs to swap implementations | ABC with discoverable plugins | Hardcoded concrete classes |
| Scaling from single-team to Data Mesh | Unified Manifest schema with `scope` field | Separate schemas requiring migration |
| Adding observability backends | TelemetryBackendPlugin + LineageBackendPlugin ABCs | Configuration enum of backends |

**Outcome**: 11 plugin types enable flexibility while maintaining enforced standards (see [plugin-system/index.md](../architecture/plugin-system/index.md)).

**See**: [ADR-0037: Composability Principle](../architecture/adr/0037-composability-principle.md) for detailed rationale.

---

## 2. Platform Enforcement Model

### 2.1 Core Principle

floe uses a **platform enforcement architecture** where:
- Platform configuration is **immutable and versioned** - defined once, inherited by all pipelines
- Data engineers **inherit platform guardrails** - they design pipelines, everything else is enforced
- Clear separation between **Platform Team** (define once) and **Data Team** (consume)

### 2.2 Two-File Configuration

| File | Owner | Purpose | Changes |
|------|-------|---------|---------|
| `manifest.yaml` | Platform Team | Define guardrails (plugins, governance, naming) | Rarely (quarterly) |
| `floe.yaml` | Data Engineers | Define pipelines (transforms, schedules) | Frequently (daily) |

### 2.3 Workflow

```
Platform Team                         Data Team
     │                                     │
     ▼                                     ▼
manifest.yaml              floe.yaml (pipelines)
     │                                     │
     ▼                                     ▼
floe platform compile               floe compile
     │                                     │ (validates against platform)
     ▼                                     │
OCI Registry ◄─────────────────────────────┘
(immutable artifacts)
     │
     ▼
floe platform deploy
     │
     ▼
K8s Cluster (services + jobs)
```

### 2.4 Compute Target: Environment-Agnostic

**Key Decision**: Compute target is set ONCE at platform level, inherited by all pipelines, consistent across dev/staging/prod.

- **No per-environment compute targets** - prevents drift between environments
- **DuckDB is a viable production choice** - not just for development
- Data engineers inherit compute - they don't select it

---

## 3. Opinionation Boundaries

### 3.1 Enforced Standards (Non-Negotiable)

These define floe's core identity and are NOT pluggable:

| Component | Standard | Rationale |
|-----------|----------|-----------|
| **Table Format** | Apache Iceberg | Open, multi-engine, ACID, time-travel |
| **Telemetry** | OpenTelemetry | Vendor-neutral industry standard |
| **Data Lineage** | OpenLineage | Industry standard for lineage |
| **Deployment** | Kubernetes-native | Portable, declarative infrastructure |
| **Configuration** | Declarative YAML | Explicit over implicit |
| **Transformation** | dbt-centric | "dbt owns SQL" - proven, target-agnostic |

**Note on dbt**: The dbt **framework** (SQL transformation DSL, models, tests, macros) is enforced as a core standard. The dbt **execution environment** (WHERE dbt compiles and runs) is pluggable via DBTPlugin:
- **LocalDBTPlugin**: dbt-core via CLI subprocess (default)
- **FusionDBTPlugin**: dbt Fusion (Rust-based, 30x faster parsing)
- **CloudDBTPlugin**: dbt Cloud API (deferred to Epic 8+)

Platform teams select the execution environment in `manifest.yaml`. Data engineers use dbt framework features regardless of execution environment. See [ADR-0043](../architecture/adr/0043-dbt-runtime-abstraction.md) for details.

### 3.2 Pluggable Components (Platform Team Choice)

Platform Team selects these ONCE in `manifest.yaml`. Data engineers inherit them:

| Component | Default | Alternatives |
|-----------|---------|--------------|
| **Compute** | DuckDB | Spark, Snowflake, Databricks, BigQuery |
| **dbt Execution Environment** | dbt-core (local) | dbt Fusion (Rust), dbt Cloud (deferred) |
| **Storage** | S3 | GCS, Azure Blob, MinIO |
| **Observability Backend** | Jaeger | Datadog, Grafana Cloud, AWS X-Ray |
| **Ingestion** | dlt | Airbyte (external) |
| **Orchestration** | Dagster | Airflow |
| **Catalog** | Polaris | AWS Glue, Nessie |
| **Semantic Layer** | Cube | None |
| **Secrets** | K8s Secrets | External Secrets Operator, Vault, Infisical |
| **Identity** | Keycloak | Dex, Authentik, Okta, Auth0 |

### 3.3 Plugin Architecture

Each pluggable component implements an Abstract Base Class (ABC) and optionally includes a Helm chart:

```
plugins/floe-orchestrator-dagster/
├── src/                    # Python: implements OrchestratorPlugin ABC
├── chart/                  # Helm: deploys Dagster services (optional)
└── pyproject.toml          # Entry point registration
```

See [04-building-blocks.md](04-building-blocks.md) for full plugin details.

---

## 4. Technology Decisions

### 4.1 Overview

| Component | Technology | Rationale |
|-----------|------------|-----------|
| CLI | Python + Click | Native to data engineering ecosystem |
| Schema | Pydantic | Type-safe validation, JSON Schema generation |
| Orchestration | Dagster | Asset-centric, OpenLineage native |
| Transformation | dbt | Industry standard, target-agnostic |
| Storage | Apache Iceberg | Open table format, multi-engine |
| Catalog | Apache Polaris | REST API, vendor-neutral |
| **Consumption** | **Cube** | **Semantic layer, universal APIs** |
| **Governance** | **dbt meta + policies** | **Classification via dbt, policies via floe.yaml** |
| Observability | OpenTelemetry | Vendor-neutral traces/metrics/logs |
| Lineage | OpenLineage | Industry standard for data lineage |
| Packaging | PyPI + Containers | Hybrid distribution strategy |
| Deployment | Helm | Kubernetes-native |

---

## 2. Language Choice: Python

### 2.1 Decision

Use **Python** for all floe packages.

### 2.2 Rationale

| Factor | Analysis |
|--------|----------|
| **Ecosystem alignment** | Data engineers use Python (dbt, Dagster, Pandas, etc.) |
| **Developer experience** | Users can read, extend, and debug in familiar language |
| **Dependency management** | uv handles transitive dependencies with lockfiles |
| **Dagster integration** | Native Python SDK, asset factory patterns |
| **dbt integration** | dbt-core is Python, adapters are Python |

### 2.3 Trade-offs

| Advantage | Disadvantage |
|-----------|--------------|
| Familiar to users | Slower than compiled languages |
| Rich ecosystem | GIL limits parallelism |
| Easy extension | Type safety requires discipline |
| Rapid development | Runtime errors vs compile-time |

### 2.4 Mitigations

- Use type hints everywhere (`from __future__ import annotations`)
- Run mypy in CI for static type checking
- Use Pydantic for runtime validation
- Profile hot paths and optimize as needed

---

## 3. Schema Strategy: Pydantic + JSON Schema

### 3.1 Decision

Use **Pydantic models** as the source of truth for all schemas, with **JSON Schema** generated for validation and documentation.

### 3.2 Implementation

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

class ComputeTarget(str, Enum):
    DUCKDB = "duckdb"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    POSTGRES = "postgres"

class ComputeConfig(BaseModel):
    """Compute target configuration."""
    target: ComputeTarget = Field(
        description="The compute engine for SQL execution"
    )
    connection_secret_ref: Optional[str] = Field(
        default=None,
        description="Reference to connection credentials secret"
    )

class FloeSpec(BaseModel):
    """Root schema for floe.yaml."""
    name: str = Field(description="Pipeline name")
    version: str = Field(description="Schema version")
    compute: ComputeConfig
    # ... more fields
```

### 3.3 Generated Artifacts

```
floe-core/
├── schemas/
│   ├── floe_spec.py          # Pydantic models (source of truth)
│   ├── compiled_artifacts.py # Output contract
│   └── generated/
│       ├── floe.schema.json  # For IDE support, validation
│       └── artifacts.schema.json
```

### 3.4 Rationale

| Factor | Analysis |
|--------|----------|
| **Native Python** | Pydantic is standard for FastAPI, Dagster, etc. |
| **Runtime validation** | Automatic validation on parse |
| **IDE support** | Type hints provide autocomplete |
| **Human-readable** | JSON files can be inspected, edited |
| **Documentation** | JSON Schema → OpenAPI → docs |

---

## 4. Orchestration: Dagster

### 4.1 Decision

Use **Dagster** for orchestration with **Software-Defined Assets (SDAs)**.

### 4.2 Why Dagster Over Alternatives

| Factor | Dagster | Airflow | Prefect |
|--------|---------|---------|---------|
| **Paradigm** | Asset-centric | Task-centric | Task-centric |
| **Data awareness** | First-class | Bolted-on | Limited |
| **dbt integration** | Native | Via operators | Via tasks |
| **OpenLineage** | Native emission | Requires plugin | Limited |
| **Development UX** | Excellent UI | Basic UI | Good UI |
| **Branch deployments** | Built-in | Manual | Manual |

### 4.3 Asset Factory Pattern

```python
from dagster import asset, AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from floe_core import CompiledArtifacts

def create_assets_from_artifacts(
    artifacts: CompiledArtifacts
) -> list[AssetsDefinition]:
    """Generate Dagster assets from CompiledArtifacts."""

    @dbt_assets(manifest=artifacts.dbt_manifest_path)
    def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
        yield from dbt.cli(["build"], context=context).stream()

    return [dbt_models]
```

### 4.4 Trade-offs

| Advantage | Disadvantage |
|-----------|--------------|
| Asset lineage built-in | Newer, smaller community than Airflow |
| Excellent development UX | Learning curve for asset thinking |
| Native dbt integration | Requires PostgreSQL for production |
| OpenLineage emission | More opinionated than Prefect |

---

## 5. Transformation: dbt

### 5.1 Decision

Use **dbt** for all SQL transformations. **Floe never parses SQL**.

### 5.2 Rationale (ADR-0009)

| Factor | Analysis |
|--------|----------|
| **Industry standard** | 50,000+ teams use dbt |
| **Target-agnostic** | Adapters for every warehouse |
| **Dependency management** | `ref()` handles model ordering |
| **Incremental processing** | `is_incremental()` macro |
| **Testing** | Built-in data tests |
| **Documentation** | Generated docs site |

### 5.3 What dbt Handles

- SQL dialect translation (DuckDB ↔ Snowflake ↔ BigQuery)
- Dependency resolution via `ref()` and `source()`
- Incremental materialization logic
- Data quality tests
- Documentation generation

### 5.4 What Floe Provides

- Profile generation based on compute target
- Environment variable injection
- Integration with Dagster orchestration
- OpenLineage wrapper for lineage events

### 5.5 Profile Generation

```python
def generate_profiles(artifacts: CompiledArtifacts) -> dict:
    """Generate dbt profiles.yml from compiled artifacts."""
    target = artifacts.compute.target

    if target == "duckdb":
        return {
            "floe": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": artifacts.compute.properties.get(
                            "path", "/tmp/floe.duckdb"
                        ),
                    }
                }
            }
        }
    elif target == "snowflake":
        return {
            "floe": {
                "target": "prod",
                "outputs": {
                    "prod": {
                        "type": "snowflake",
                        "account": "{{ env_var('SNOWFLAKE_ACCOUNT') }}",
                        "user": "{{ env_var('SNOWFLAKE_USER') }}",
                        # ... more config
                    }
                }
            }
        }
```

---

## 6. Storage: Apache Iceberg

### 6.1 Decision

Use **Apache Iceberg** as the table format for stored data.

### 6.2 Rationale

| Factor | Analysis |
|--------|----------|
| **Open standard** | Not tied to single vendor |
| **Multi-engine** | Spark, Trino, Flink, DuckDB can all query |
| **ACID transactions** | Reliable concurrent writes |
| **Time travel** | Query historical snapshots |
| **Schema evolution** | Add/rename columns without rewrite |
| **Hidden partitioning** | Users don't manage partitions |

### 6.3 Industry Momentum (2024)

- Snowflake donated Polaris catalog to Apache Foundation
- Databricks acquired Tabular (Iceberg creators)
- Salesforce runs 4M+ Iceberg tables in production
- AWS, GCP, Azure all offer Iceberg support

### 6.4 dbt + Iceberg Integration

dbt 1.9+ supports Iceberg natively:

```sql
-- models/marts/customers.sql
{{ config(
    materialized='incremental',
    file_format='iceberg',
    incremental_strategy='merge',
    unique_key='customer_id'
) }}

SELECT
    customer_id,
    customer_name,
    updated_at
FROM {{ ref('stg_customers') }}
{% if is_incremental() %}
WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
```

---

## 7. Catalog: Apache Polaris

### 7.1 Decision

Use **Apache Polaris** as the default Iceberg catalog.

### 7.2 Rationale

| Factor | Analysis |
|--------|----------|
| **Open source** | Apache Foundation governance |
| **REST API** | Standard Iceberg REST catalog spec |
| **Multi-engine** | Any Iceberg-compatible engine works |
| **RBAC** | Role-based access control |
| **Credential vending** | Secure short-lived credentials |

### 7.3 Alternative Catalogs Supported

| Catalog | Use Case |
|---------|----------|
| **Polaris** | Default, recommended |
| **Hive Metastore** | Legacy Hadoop environments |
| **AWS Glue** | AWS-native deployments |
| **Nessie** | Git-like branching for tables |

### 7.4 Integration Pattern

```python
from pyiceberg.catalog import load_catalog

def get_catalog(artifacts: CompiledArtifacts) -> Catalog:
    """Load Iceberg catalog based on configuration."""
    catalog_config = artifacts.catalog

    if catalog_config.type == "polaris":
        return load_catalog(
            "polaris",
            type="rest",
            uri=catalog_config.uri,
            credential=catalog_config.credential,
        )
    elif catalog_config.type == "glue":
        return load_catalog("glue", type="glue")
```

---

## 8. Consumption: Cube Semantic Layer

### 8.1 Decision

Use **Cube** as the semantic/consumption layer for data access APIs.

### 8.2 Rationale

| Factor | Analysis |
|--------|----------|
| **Universal APIs** | REST, GraphQL, SQL (Postgres wire protocol) |
| **dbt integration** | Native `cube_dbt` package loads dbt models |
| **Caching** | Cube Store pre-aggregations for sub-second queries |
| **Multi-tenancy** | Row-level security via security context |
| **AI-ready** | MCP server for agent integration |
| **Open source** | Cube Core is Apache 2.0 licensed |

### 8.3 Why Cube Over Alternatives

| Factor | Cube | dbt Semantic Layer | Custom API |
|--------|------|-------------------|------------|
| **Licensing** | Apache 2.0 | Cloud-only | N/A |
| **API types** | REST, GraphQL, SQL | SQL only | Custom |
| **dbt integration** | Native | Native | Manual |
| **Caching** | Built-in | None | Build yourself |
| **Development effort** | Configuration | Configuration | Significant |

### 8.4 Integration Architecture

```
dbt models (transformed data)
       │
       ▼
┌─────────────────────────────────────────┐
│           Cube Semantic Layer            │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Data Model (from dbt manifest)  │   │
│  │  • Cubes (entities)               │   │
│  │  • Dimensions (attributes)        │   │
│  │  • Measures (aggregations)        │   │
│  │  • Joins (relationships)          │   │
│  └──────────────────────────────────┘   │
│                  │                       │
│                  ▼                       │
│  ┌──────────────────────────────────┐   │
│  │  Cube Store (Pre-aggregations)   │   │
│  │  • Materialized rollups          │   │
│  │  • Sub-second query response     │   │
│  └──────────────────────────────────┘   │
│                  │                       │
│                  ▼                       │
│  ┌──────────────────────────────────┐   │
│  │  Security Layer                   │   │
│  │  • Row-level security             │   │
│  │  • Tenant isolation               │   │
│  │  • Query rewrite                  │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│              APIs                        │
│                                          │
│  • REST API    → Custom applications    │
│  • GraphQL API → Modern frontends       │
│  • SQL API     → BI tools (Tableau)     │
│  • MCP Server  → AI agents              │
└─────────────────────────────────────────┘
```

### 8.5 dbt Model Sync

```python
from cube_dbt import Dbt

# Load dbt manifest
dbt = Dbt.from_file('./target/manifest.json')

# Filter models tagged for semantic layer
models = dbt.filter(tags=['cube'])

# Generate Cube model definitions
for model in models:
    cube_definition = model.as_cube()
    dimensions = model.as_dimensions()
    # Enrich with measures, joins, pre-aggregations
```

### 8.6 Configuration in floe.yaml

```yaml
consumption:
  enabled: true
  cube:
    port: 4000
    api_secret_ref: "cube-api-secret"
    pre_aggregations:
      refresh_schedule: "*/30 * * * *"
    security:
      row_level: true
      tenant_column: "tenant_id"
```

---

## 9. Observability: OpenTelemetry + OpenLineage

### 9.1 Decision

Use **OpenTelemetry** for traces/metrics/logs and **OpenLineage** for data lineage.

### 9.2 Why Both?

| Concern | Solution | Purpose |
|---------|----------|---------|
| **Request tracing** | OpenTelemetry | Latency, errors, infrastructure |
| **Data lineage** | OpenLineage | What data flowed where, when |

Together they provide complete observability for both debugging AND compliance.

### 9.3 OpenTelemetry Implementation

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def init_tracing(config: ObservabilityConfig) -> TracerProvider:
    """Initialize OpenTelemetry tracing."""
    provider = TracerProvider()

    if config.otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return provider
```

### 9.4 OpenLineage Implementation

```python
from openlineage.client import OpenLineageClient
from openlineage.client.run import RunEvent, RunState, Job, Run

def emit_run_start(
    client: OpenLineageClient,
    job_name: str,
    inputs: list[Dataset],
) -> str:
    """Emit OpenLineage run start event."""
    run_id = str(uuid.uuid4())

    event = RunEvent(
        eventType=RunState.START,
        eventTime=datetime.now(timezone.utc).isoformat(),
        job=Job(namespace="floe", name=job_name),
        run=Run(runId=run_id),
        inputs=inputs,
    )

    client.emit(event)
    return run_id
```

---

## 10. Distribution Strategy: Hybrid

### 10.1 Decision

**Hybrid distribution**: PyPI packages as source of truth, container images for convenience, Helm charts for Kubernetes.

### 10.2 Distribution Layers

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Python Packages (PyPI)                        │
│  • uv add floe-cli floe-core floe-dbt                   │
│  • uv add floe-orchestrator-dagster (plugin)            │
│  • Source of truth for all code                         │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Container Images (GHCR)                       │
│  • ghcr.io/floe/cli:latest                     │
│  • ghcr.io/floe/floe-jobs:latest               │
│  • Built FROM Python packages + plugins                 │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Helm Charts                                   │
│  • floe-platform (meta-chart for services)             │
│  • floe-jobs (base chart for pipeline jobs)            │
│  • Reference container images                           │
└─────────────────────────────────────────────────────────┘
```

### 10.3 Rationale

| User Persona | Preferred Distribution |
|--------------|------------------------|
| Data Engineer (local dev) | PyPI: `uv add floe-cli` |
| Platform Engineer (K8s) | Helm: `helm install floe` |
| Quick evaluation | Container: `docker run ghcr.io/...` |
| Enterprise (air-gapped) | All: internal mirrors + registry |

---

## 11. Extension Strategy

### 11.1 Plugin Architecture

floe uses Python entry points for plugin discovery. Each plugin:
1. Implements an Abstract Base Class (ABC) from `floe-core`
2. Optionally includes a Helm chart for service deployment
3. Registers via `pyproject.toml` entry points

```toml
# plugins/floe-orchestrator-dagster/pyproject.toml
[project.entry-points."floe.orchestrators"]
dagster = "floe_orchestrator_dagster:DagsterPlugin"

[project.entry-points."floe.charts"]
dagster = "floe_orchestrator_dagster:chart"

# plugins/floe-compute-duckdb/pyproject.toml
[project.entry-points."floe.compute"]
duckdb = "floe_compute_duckdb:DuckDBPlugin"
```

### 11.2 Extension Points

| Extension | ABC Interface | Purpose |
|-----------|---------------|---------|
| Compute | `ComputePlugin` | Where dbt transforms execute |
| Orchestration | `OrchestratorPlugin` | Pipeline scheduling and execution |
| Catalog | `CatalogPlugin` | Iceberg catalog implementations |
| Semantic Layer | `SemanticLayerPlugin` | Data consumption APIs |
| Ingestion | `IngestionPlugin` | Data loading (EL) |
| Secrets | `SecretsPlugin` | Credentials management |

See [04-building-blocks.md](04-building-blocks.md) for full interface definitions.

### 11.3 Plugin API Versioning

Plugins declare their API compatibility:

```python
# Plugin metadata
FLOE_PLUGIN_API_VERSION = "1.0"

class DagsterPlugin(OrchestratorPlugin):
    name = "dagster"
    version = "1.0.0"
    floe_api_version = "1.0"  # Checked at load time
```

---

## 12. Governance: Data Classification

### 12.1 Decision

Use **dbt meta tags** as the source of truth for data classification, with **floe.yaml** defining policies for how to handle classified data. See [ADR-0012](../architecture/adr/0012-data-classification-governance.md).

### 12.2 Classification Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA CLASSIFICATION FLOW                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Source: dbt meta tags                                               │    │
│  │                                                                      │    │
│  │  columns:                                                            │    │
│  │    - name: email                                                     │    │
│  │      meta:                                                           │    │
│  │        floe:                                                         │    │
│  │          classification: pii                                         │    │
│  │          pii_type: email                                             │    │
│  │          sensitivity: high                                           │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Compiler: Extract classifications from dbt manifest                 │    │
│  │                                                                      │    │
│  │  column_classifications = {                                          │    │
│  │    "stg_customers": {                                                │    │
│  │      "email": {"classification": "pii", "pii_type": "email", ...}   │    │
│  │    }                                                                 │    │
│  │  }                                                                   │    │
│  └──────────────────────────────────┬──────────────────────────────────┘    │
│                                     │                                        │
│            ┌────────────────────────┼────────────────────────┐              │
│            │                        │                        │              │
│            ▼                        ▼                        ▼              │
│  ┌──────────────────┐    ┌──────────────────┐                              │
│  │  OpenLineage     │    │  Cube Security   │                              │
│  │  Facets          │    │  Rules           │                              │
│  │                  │    │                  │                              │
│  │  Propagate tags  │    │  Auto-generate   │                              │
│  │  with lineage    │    │  queryRewrite    │                              │
│  └──────────────────┘    └──────────────────┘                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Classification Schema

```yaml
# dbt model YAML - classification source of truth
columns:
  - name: customer_id
    meta:
      floe:
        classification: identifier

  - name: email
    meta:
      floe:
        classification: pii
        pii_type: email
        sensitivity: high

  - name: phone
    meta:
      floe:
        classification: pii
        pii_type: phone
        sensitivity: high

  - name: revenue
    meta:
      floe:
        classification: financial
        sensitivity: medium
```

### 12.4 Policy Configuration in floe.yaml

```yaml
governance:
  classification_source: dbt_meta

  policies:
    pii:
      production:
        action: restrict
        requires_role: [data_owner]
      non_production:
        action: synthesize

    financial:
      production:
        action: restrict
      non_production:
        action: mask

    high_sensitivity:
      production:
        action: restrict
        requires_role: [data_owner, compliance]
      non_production:
        action: redact

  emit_classification_lineage: true
```

### 12.5 OpenLineage Classification Facet

```python
# floe_dagster/lineage.py
from openlineage.client.facet import BaseFacet
from dataclasses import dataclass

@dataclass
class ColumnClassification:
    """Classification metadata for a column."""
    classification: str  # pii, financial, identifier, public
    pii_type: str | None  # email, phone, ssn, etc.
    sensitivity: str  # low, medium, high, critical

class FloeClassificationFacet(BaseFacet):
    """Custom OpenLineage facet for data classification."""
    _schemaURL = "https://floe.dev/spec/facets/ClassificationFacet.json"

    columns: dict[str, ColumnClassification]

# Emit with lineage events
def emit_with_classification(
    client: OpenLineageClient,
    model_name: str,
    classifications: dict[str, ColumnClassification],
):
    """Emit lineage event with classification facet."""
    facets = {}
    if classifications:
        facets["floe_classification"] = FloeClassificationFacet(
            columns=classifications
        )

    # Include facets in dataset output
    output = Dataset(
        namespace="floe",
        name=model_name,
        facets=facets,
    )
```
