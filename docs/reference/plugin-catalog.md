# Plugin Catalog

This page is the canonical public reference for Floe plugin categories.

Implementation truth comes from `floe_core.plugin_types.PluginType`. The current implementation defines 14 plugin categories. `PluginType.LINEAGE` is a code alias for `PluginType.LINEAGE_BACKEND` and is not an extra category.

| Category | Entry point group | Current alpha status | Owner |
| --- | --- | --- | --- |
| `COMPUTE` | `floe.computes` | DuckDB reference implementation; other engines are pluggable. | Platform team selects; compute plugin executes dbt work. |
| `ORCHESTRATOR` | `floe.orchestrators` | Dagster reference implementation. | Platform team selects; orchestrator owns scheduling and runs. |
| `CATALOG` | `floe.catalogs` | Polaris reference implementation. | Platform team selects; catalog plugin owns Iceberg catalog integration. |
| `STORAGE` | `floe.storage` | MinIO and cloud object storage integrations. | Platform team selects; storage plugin owns object-store access. |
| `TELEMETRY_BACKEND` | `floe.telemetry_backends` | Jaeger and OTLP-compatible backends. | Platform team selects; OpenTelemetry owns trace semantics. |
| `LINEAGE_BACKEND` | `floe.lineage_backends` | Marquez and compatible lineage services. | Platform team selects; OpenLineage owns lineage semantics. |
| `DBT` | `floe.dbt` | dbt Core first, with runtime abstraction for other dbt runtimes. | dbt owns SQL compilation; the plugin owns runtime packaging. |
| `SEMANTIC_LAYER` | `floe.semantic_layers` | Cube reference implementation. | Platform team selects; semantic plugin owns metrics API integration. |
| `INGESTION` | `floe.ingestion` | dlt and Airbyte-style ingestion integrations. | Data product team configures sources within platform-approved plugins. |
| `SECRETS` | `floe.secrets` | Kubernetes and external secret backends. | Platform team owns credential backend and secret references. |
| `IDENTITY` | `floe.identity` | OIDC-compatible providers. | Platform team owns identity provider integration. |
| `QUALITY` | `floe.quality` | Great Expectations, Soda, and dbt-expectations style integrations. | Platform team sets standards; data products attach checks. |
| `RBAC` | `floe.rbac` | Namespace and service-account isolation for platform workloads. | Platform team owns generated access-control policy. |
| `ALERT_CHANNEL` | `floe.alert_channels` | Slack, webhook, and email-style delivery targets. | Platform team owns delivery backends; policy events trigger alerts. |

Use this page when writing public documentation about plugin counts. Architecture decision records may preserve historical counts in version or history sections, but current product docs should refer to the implementation truth here.
