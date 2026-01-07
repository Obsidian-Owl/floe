# ADR-R0001: Use Cube for Semantic/Consumption Layer

## Status

Accepted

## Context

floe provides a complete data pipeline stack:

- **Transformation**: dbt for SQL models
- **Orchestration**: Dagster for scheduling and dependencies
- **Storage**: Apache Iceberg for ACID tables
- **Catalog**: Apache Polaris for metadata management

However, the stack lacks a **consumption layer**—an API through which downstream applications, BI tools, and AI agents can query the transformed data. Without this:

1. Users must connect directly to data warehouses, bypassing governance
2. No caching layer means expensive repeated queries
3. No unified API for diverse consumers (REST, GraphQL, SQL)
4. No semantic model to translate business concepts to physical tables
5. AI agents lack a structured interface for data queries

Key requirements for a consumption layer:

- API-first architecture (REST, GraphQL, SQL wire protocol)
- Semantic modeling on top of dbt models
- Caching and pre-aggregations for performance
- Namespace-based row-level security
- Integration with OpenTelemetry and OpenLineage
- Support for AI/agent interfaces (MCP)

Technologies considered:

- **Cube** - Open-source semantic layer, API-first, dbt integration, multi-tenant
- **dbt Semantic Layer (MetricFlow)** - dbt-native, but tightly coupled to dbt Cloud
- **LookML/Looker** - Powerful but proprietary, heavy vendor lock-in
- **Custom API layer** - Full control but significant development effort
- **Trino/Presto** - Query engine, not semantic layer

## Decision

Use **Cube** as the semantic/consumption layer for floe.

Cube will be implemented as the plugin `plugins/floe-semantic-cube/` that:

1. Syncs dbt models to Cube cubes via the `cube_dbt` package
2. Provides REST, GraphQL, and SQL APIs for data consumption
3. Implements caching via Cube Store pre-aggregations
4. Enforces row-level security using namespace context
5. Exposes MCP server interface for AI agent queries
6. Emits OpenLineage events for query lineage

## Consequences

### Positive

- **Complete stack**: floe becomes end-to-end (ingest → transform → store → serve)
- **Native dbt integration**: `cube_dbt` package loads dbt manifest directly
- **Universal APIs**: REST, GraphQL, and Postgres-compatible SQL serve any consumer
- **Performance**: Cube Store pre-aggregations provide sub-second query response
- **Data isolation**: Built-in row-level security with `queryRewrite` and security context
- **AI-ready**: MCP server and AI API enable agent-based analytics
- **Open source**: Cube Core is Apache 2.0 licensed, aligns with floe licensing
- **BI connectivity**: 40+ native integrations (Tableau, Metabase, Superset, etc.)

### Negative

- **Additional complexity**: New component to deploy, configure, monitor
- **Resource requirements**: Cube Store requires persistent storage for pre-aggregations
- **Learning curve**: Team must learn Cube data modeling concepts
- **Versioning**: Must coordinate Cube, dbt, and Dagster versions

### Neutral

- **Cube Cloud available**: Managed option exists if self-hosting becomes burdensome
- **Community Helm charts**: No official Helm chart, but community options exist
- **Instrumentation needed**: OpenTelemetry/OpenLineage integration requires custom work

## Architecture Integration

### Package Structure

```
floe/
├── floe-core/                       # Schema, validation, interfaces (ABCs)
├── floe-cli/                        # Developer CLI
├── floe-dbt/                        # Transformation (enforced)
├── floe-iceberg/                    # Storage (enforced)
│
└── plugins/                         # Pluggable components
    ├── floe-orchestrator-dagster/   # Orchestration
    ├── floe-catalog-polaris/        # Catalog
    └── floe-semantic-cube/          # Consumption (semantic layer)
        ├── src/
        │   ├── plugin.py            # Implements SemanticLayerPlugin ABC
        │   ├── model_sync.py        # Sync dbt models → Cube cubes
        │   ├── security.py          # Row-level security context
        │   └── lineage.py           # OpenLineage emission
        ├── chart/                   # Helm chart for Cube deployment
        └── pyproject.toml           # Entry point registration
```

> **Note:** floe-cube has been renamed to `plugins/floe-semantic-cube/` to follow the plugin pattern established in [04-building-blocks](../../guides/04-building-blocks.md).

### Data Flow

```
floe.yaml + platform-manifest.yaml
    │
    ▼
floe-core (compile, enforce)
    │
    ▼
OrchestratorPlugin (e.g., Dagster) ──► floe-dbt (transform)
    │                                       │
    │                                       ▼
    │                                  dbt models
    │                                       │
    │                                       ▼
    │                             floe-iceberg (store)
    │                                       │
    │                                       ▼
    │                             CatalogPlugin (e.g., Polaris)
    │                                       │
    ▼                                       ▼
SemanticLayerPlugin (e.g., Cube) ◄── dbt manifest.json
    │
    ▼
REST / GraphQL / SQL APIs
    │
    ▼
BI Tools, AI Agents, Applications
```

### Schema Extension

```yaml
# floe.yaml - consumption section
consumption:
  enabled: true
  cube:
    port: 4000
    api_secret_ref: "cube-api-secret"
    pre_aggregations:
      refresh_schedule: "*/30 * * * *"
    security:
      row_level: true
      namespace_column: "namespace"
```

### Deployment Components

| Component | Purpose | Scaling |
|-----------|---------|---------|
| Cube API | Handle incoming queries | Horizontal (2+ replicas) |
| Cube Refresh Worker | Build pre-aggregations | Single replica |
| Cube Store Router | Route queries | Single replica |
| Cube Store Workers | Execute cached queries | Horizontal (2+ replicas) |

## References

- [Cube Documentation](https://cube.dev/docs/product/introduction)
- [Cube + dbt Integration](https://cube.dev/docs/product/data-modeling/recipes/dbt)
- [cube_dbt Package](https://github.com/cube-js/cube_dbt) - Python package for dbt manifest sync
- [cube_dbt Documentation](https://cube.dev/docs/product/data-modeling/reference/cube_dbt)
- [Cube Multitenancy](https://cube.dev/docs/product/configuration/multitenancy)
- [Cube Row-Level Security](https://cube.dev/docs/product/auth/row-level-security)
- [Cube Deployment](https://cube.dev/docs/product/deployment)
- Community Helm Charts (no official chart):
  - [narioinc/cube-helm](https://github.com/narioinc/cube-helm) - Scalable cluster deployment
  - [gadsme/cube](https://artifacthub.io/packages/helm/gadsme/cube) - Artifact Hub
  - [OpstimizeIcarus/cubejs-helm-charts](https://github.com/OpstimizeIcarus/cubejs-helm-charts-kubernetes)
- [ADR-0009: dbt Owns SQL](./0009-dbt-owns-sql.md)
