# Observability Attributes Contract

**Version:** 0.1.0

This contract records the observability fields implemented for the alpha path.
Floe emits OpenTelemetry traces, structured logs, Prometheus-compatible metrics,
and OpenLineage events using secret-free Floe context. Backend selection stays
in deployment bindings, the OpenTelemetry Collector configuration, and the
lineage backend plugin; product and plugin code emit portable signals.

## Canonical Floe Context

`floe_core.telemetry.context.ObservabilityContext` is the canonical runtime
context for traces, logs, and metric labels. `to_span_attributes()` emits these
fields when the value is known:

| Attribute | Required when | Description | Example |
| --- | --- | --- | --- |
| `floe.product.name` | Always | Data product name | `customer-360` |
| `floe.product.version` | Always | Data product version | `0.1.0` |
| `floe.environment` | Always | Runtime environment | `demo` |
| `floe.namespace` | Always | Floe/catalog namespace | `customer_360` |
| `floe.run.id` | Runtime run known | Dagster/product run ID | `run-abc123` |
| `floe.asset.key` | Asset known | Dagster asset key | `customer_360.mart_customer_360` |
| `floe.stage` | Stage known | Runtime stage | `dbt` |
| `floe.table.name` | Table known | Logical table name | `mart_customer_360` |
| `floe.plugin.type` | Plugin known | Plugin category | `orchestrator` |
| `floe.plugin.name` | Plugin known | Plugin implementation | `dagster` |
| `floe.lineage.namespace` | Lineage configured | OpenLineage namespace | `customer-360` |
| `floe.status` | Final status known | Bounded result status | `success` |

The implemented context above is the source of truth for Customer 360 proof.
Do not introduce older pipeline, mode, or Dagster-specific aliases in new alpha
evidence.

## Structured Logs

Structured logs must use `ObservabilityContext.to_log_fields()`, which mirrors
the canonical span attributes. Runtime logs for the alpha path include:

- `floe_asset_started`
- `floe_asset_completed`
- `floe_asset_failed`
- `dbt_node_observed`
- `plugin_lifecycle.observed`

Logs must remain secret-free. Do not emit raw credentials, tokens, passwords,
connection strings with userinfo, private keys, or backend secrets. Secret-like
extra attributes are dropped or redacted by the shared context helpers.

## Metrics

Dagster runtime asset envelopes emit the alpha product metrics:

| OpenTelemetry instrument | Prometheus series | Type | Meaning |
| --- | --- | --- | --- |
| `floe.asset.materializations` | `floe_asset_materializations_total` | Counter | Asset completed successfully |
| `floe.asset.failures` | `floe_asset_failures_total` | Counter | Asset failed |

Allowed labels are intentionally bounded:

| OTel label | Prometheus label | Included |
| --- | --- | --- |
| `floe.product.name` | `floe_product_name` | Always |
| `floe.environment` | `floe_environment` | Always |
| `floe.namespace` | `floe_namespace` | Always |
| `floe.stage` | `floe_stage` | When known |
| `floe.plugin.type` | `floe_plugin_type` | When known |
| `floe.plugin.name` | `floe_plugin_name` | When known |
| `floe.status` | `floe_status` | Success/failure/error/skipped |

`floe.run.id`, `floe.asset.key`, and `floe.table.name` are excluded from the
canonical metric label set because they are high-cardinality runtime values.
Backend-specific proof helpers may read an exported `floe_asset_key` label when
present, but new instrumentation should not depend on per-run or per-table
labels for aggregate dashboards.

Customer 360 metric proof queries the Prometheus names by product, status, and
plugin, for example:

```promql
floe_asset_materializations_total{
  floe_product_name="customer-360",
  floe_status="success",
  floe_plugin_name=~".+"
}
```

## OpenLineage Correlation

Customer 360 lineage proof requires two pieces of evidence:

1. Product run evidence in the product lineage namespace/job.
2. Model/table run evidence linked to the product/Dagster run through
   OpenLineage `ParentRunFacet`.

Do not treat a single table event on the product run as complete lineage proof.
Model/table runs must carry a parent run reference to the product run ID, and
the validator classifies evidence against the product, run ID, and target table
context.

## Plugin Lifecycle Telemetry

Plugin lifecycle instrumentation emits spans, logs, and bounded metrics for
startup, shutdown, health checks, and similar lifecycle phases. Lifecycle fields
are:

| Field | Description |
| --- | --- |
| `floe.plugin.type` | Plugin category |
| `floe.plugin.name` | Plugin implementation name |
| `floe.plugin.version` | Plugin package/API version |
| `floe.plugin.floe_api_version` | Floe plugin API compatibility version |
| `floe.plugin.lifecycle.phase` | Lifecycle phase |
| `floe.plugin.lifecycle.status` | Final lifecycle status |
| `floe.error.type` | Sanitized error class when a failure occurs |

Lifecycle metrics are `floe.plugin.lifecycle.duration` and
`floe.plugin.lifecycle.failures`. Allowed labels are plugin type, plugin name,
lifecycle phase, and lifecycle status.

## Security Rules

Never emit:

- raw passwords, tokens, credentials, private keys, or secret values;
- connection URLs containing userinfo credentials;
- full environment dumps;
- unbounded user data, row payloads, or PII;
- high-cardinality metric labels such as run ID, trace ID, span ID, asset key,
  table name, file path, object key, or raw exception message.

When more context is needed, attach sanitized span/log attributes and keep
metric labels bounded.

## Backend Configuration

Floe emits OpenTelemetry and OpenLineage signals. The alpha proof profile wires
those signals through the OpenTelemetry Collector to trace, log, and metric
backends, and through the lineage backend plugin model to Marquez.

Common contributor endpoints are:

| Signal | Backend | Default URL |
| --- | --- | --- |
| Logs | Loki-compatible API | `http://localhost:3101` |
| Metrics | Prometheus-compatible API | `http://localhost:9090` |
| Traces | Jaeger-compatible API | `http://localhost:16686` |
| Lineage | Marquez OpenLineage backend | `http://localhost:5100` |

Production backend choices are platform-owned deployment decisions. Product
code must not couple directly to Loki, Prometheus, Jaeger, Tempo, or Marquez
implementation details.

## Related Documents

- [CompiledArtifacts Contract](./compiled-artifacts.md)
- [Customer 360 Validation](../demo/customer-360-validation.md)
- [Troubleshooting](../contributing/troubleshooting.md)
- [ADR-0006: OpenTelemetry Observability](../architecture/adr/0006-opentelemetry-observability.md)
- [ADR-0007: OpenLineage from Start](../architecture/adr/0007-openlineage-from-start.md)
