# Customer 360 Validation

## Automated Evidence

Platform Engineers and Data Engineers use this page to validate an already deployed Floe platform and Customer 360 data product. Start from the service URLs, run evidence, and platform access method provided for your environment, then run the checks described below.

Floe Contributors use `make demo` only in the remote release-validation workflow. In that contributor lane, run the Customer 360 evidence gate after `make demo` and after `make demo-customer-360-run` has completed:

```bash
make demo-customer-360-validate
```

The command loads its default evidence plan from `demo/customer-360/validation.yaml`. The manifest defines service URLs, expected platform pods, and argv-list commands for Dagster, storage, Marquez, Jaeger, and business metric checks.

The current alpha business/query proof is command-based against the generated Iceberg mart. Cube is charted but disabled by default and is not part of the Customer 360 alpha gate unless your platform enables it.

Use `FLOE_DEMO_VALIDATION_MANIFEST=/path/to/validation.yaml` for a different platform shape. Individual command overrides are also available, for example `FLOE_DEMO_LINEAGE_CHECK_COMMAND`, `FLOE_DEMO_STORAGE_CHECK_COMMAND`, `FLOE_DEMO_CUSTOMER_COUNT_COMMAND`, and `FLOE_DEMO_LIFETIME_VALUE_COMMAND`.

Expected evidence keys:

- `platform.ready`
- `dagster.customer_360_run`
- `storage.customer_360_outputs`
- `observability.logs.status`
- `observability.logs.count`
- `observability.metrics.status`
- `observability.metrics.count`
- `observability.traces.status`
- `observability.traces.count`
- `observability.lineage.status`
- `observability.lineage.count`
- `observability.run_id`
- `lineage.marquez_customer_360`
- `tracing.jaeger_customer_360`
- `business.customer_count`
- `business.total_lifetime_value`

Expected successful runner evidence:

```text
status=PASS
dagster.run_id=<run-id>
dagster.job_name=customer_360
```

Expected successful validation evidence:

```text
status=PASS
evidence.business.customer_count=<non-negative integer>
evidence.business.total_lifetime_value=<non-negative decimal>
evidence.dagster.customer_360_run=true
evidence.lineage.marquez_customer_360=true
evidence.observability.lineage.status=pass
evidence.observability.lineage.count=<positive integer>
evidence.observability.logs.status=pass
evidence.observability.logs.count=<positive integer>
evidence.observability.metrics.status=pass
evidence.observability.metrics.count=<positive integer>
evidence.observability.run_id=<same run id>
evidence.observability.traces.status=pass
evidence.observability.traces.count=<positive integer>
evidence.platform.ready=true
evidence.storage.customer_360_outputs=true
evidence.tracing.jaeger_customer_360=true
```

The evidence maps to the release surfaces as follows:

- Business evidence comes from querying the generated Customer 360 mart metrics.
- Dagster evidence proves the configured `customer-360` run completed.
- Log evidence proves the log backend has structured records for the product and run ID.
- Metric evidence proves Prometheus-compatible series exist for the product, status, and plugin.
- Lineage evidence proves Marquez has product run evidence and model/table run evidence linked to that run.
- Storage evidence proves the expected Iceberg output table is readable.
- Tracing evidence proves Jaeger contains Customer 360 run traces by service, product, and run ID.

## Manual UI Inspection

| Service | Check | Pass Criteria |
| --- | --- | --- |
| Dagster | Open run history | Latest Customer 360 run succeeded |
| MinIO | Open object browser | Customer 360 output objects are visible |
| Loki-compatible API | Query logs by product and run ID | Logs include `customer-360` and the current `dagster.run_id` |
| Prometheus-compatible API | Query `floe_asset_materializations_total` by `floe_product_name`, `floe_status`, and `floe_plugin_name` | Fresh samples exist for `customer-360` with `floe_status="success"` |
| Marquez | Search Customer 360 namespace/job and model/table jobs | Product run evidence exists, and model/table runs carry `ParentRunFacet` linkage to the product/Dagster run |
| Jaeger | Search service `customer-360` with tags `floe.product.name` and `floe.run.id`, then inspect model/table spans | Trace exists for the current run and includes runtime/plugin spans plus `floe.table.name` or dbt model evidence for `mart_customer_360` |
| Polaris | Open catalog API/UI path | Customer 360 tables are registered |

If your platform provisions Grafana, use the same Loki and Prometheus queries
through Grafana. The contributor `make demo` lane exposes Loki and Prometheus
direct API endpoints by default, not a Grafana UI.

Useful manual queries:

```text
{job=~".+"} |= "customer-360" |= "<dagster.run_id>"
```

```promql
floe_asset_materializations_total{
  floe_product_name="customer-360",
  floe_status="success",
  floe_plugin_name=~".+"
}
```

Jaeger API query shape:

```text
service=customer-360
tags={"floe.product.name":"customer-360","floe.run.id":"<dagster.run_id>"}
```

After finding the run trace, inspect spans for `floe.table.name=mart_customer_360`
or equivalent dbt model span evidence for `mart_customer_360`.

Marquez evidence must include both the product job run, usually
`namespace=customer-360 job=customer-360`, and model/table run records for
`mart_customer_360` whose `ParentRunFacet` points at the same Dagster run ID.

## Failure Classification

Use the validator status to decide where to debug first:

| Status | Meaning | First action |
| --- | --- | --- |
| `backend_unreachable` | The backend API, service URL, tunnel, or collector path is unavailable | Check service pods, URLs, and port-forwards before rerunning the product |
| `no_fresh_evidence` | The backend is reachable but returned no records for the expected product/run/table | Confirm the run ID and that the relevant signal exporter is enabled |
| `stale_evidence` | Records exist only outside the freshness window | Trigger a new Customer 360 run and validate against the new run ID |
| `wrong_context` | Records exist but match another product, run, or table | Check `FLOE_DEMO_RUN_ID`, the validation manifest, and service URLs |
| `product_failure` | Evidence shows the Customer 360 run or model/table execution failed | Debug Dagster/dbt/storage output before investigating observability backends |

## Related Guides

- [Customer 360 Golden Demo](customer-360.md)
- [Validate your platform](../platform-engineers/validate-platform.md)
- [Validate your data product](../data-engineers/validate-data-product.md)
- [DevPod contributor workspace](../contributing/devpod-hetzner.md)
- [Contributor troubleshooting](../contributing/troubleshooting.md)
