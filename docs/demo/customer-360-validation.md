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

The default manifest uses the `floe-dev` namespace. DevPod/Flux release
validation may deploy the same platform shape to `floe-test`; in that case run
the validator with:

```bash
FLOE_DEMO_NAMESPACE=floe-test make demo-customer-360-validate
```

`FLOE_DEMO_NAMESPACE` changes the platform readiness namespace. Commands that
embed a namespace in their argv list, such as the storage and business metric
`kubectl exec` checks in the default manifest, must also be overridden for the
live namespace:

```bash
export FLOE_DEMO_NAMESPACE=floe-test
export FLOE_DEMO_STORAGE_CHECK_COMMAND='kubectl exec -n floe-test deployment/floe-platform-dagster-webserver -- python -m floe_orchestrator_dagster.validation.iceberg_outputs --artifacts-path /app/demo/customer_360/compiled_artifacts.json --expected-table mart_customer_360 --recovery-mode repair'
export FLOE_DEMO_CUSTOMER_COUNT_COMMAND='kubectl exec -n floe-test deployment/floe-platform-dagster-webserver -- python /app/demo/customer_360/scripts/customer360_metric.py --source iceberg --artifacts-path /app/demo/customer_360/compiled_artifacts.json customer-count'
export FLOE_DEMO_LIFETIME_VALUE_COMMAND='kubectl exec -n floe-test deployment/floe-platform-dagster-webserver -- python /app/demo/customer_360/scripts/customer360_metric.py --source iceberg --artifacts-path /app/demo/customer_360/compiled_artifacts.json total-lifetime-value'
make demo-customer-360-validate
```

Command override values are shell command strings parsed into argv by the
validator. They are not JSON or YAML argv arrays.

Current validator output keys, including alpha compatibility keys:

- `platform.ready`
- `dagster.customer_360_run`
- `run_control.namespace`
- `run_control.runtime_context`
- `run_control.dagster.status`
- `run_control.dagster.job_name`
- `run_control.dagster.api_reachable`
- `storage.customer_360_outputs`
- `storage.iceberg.customer_360_outputs`
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

New validator work should prefer the evidence key families defined in
[Observability Attributes Contract](../contracts/observability-attributes.md).

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
evidence.run_control.dagster.api_reachable=true
evidence.run_control.dagster.job_name=customer_360
evidence.run_control.dagster.status=pass
evidence.run_control.namespace=floe-dev
evidence.run_control.runtime_context=local
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
evidence.storage.iceberg.customer_360_outputs=true
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

## Manual Inspection

| Service | Alpha classification | Check | Pass criteria |
| --- | --- | --- | --- |
| Dagster | UI and API | Open run history or query GraphQL runs | Latest Customer 360 run succeeded and carries the expected product/run context |
| MinIO | UI and API | Open object browser or query the configured object store | Customer 360 output data and Iceberg metadata objects are visible |
| Marquez | API/admin only in the current Floe chart | Query namespace, jobs, runs, datasets, and lineage API endpoints | Product run evidence exists, model/table runs exist, and `ParentRunFacet` linkage points at the product/Dagster run |
| Loki | API-only | Query `/ready` and `/loki/api/v1/query_range` by product and run ID | Logs include `customer-360` and the current `dagster.run_id` |
| Prometheus | API and optional UI | Query `floe_asset_materializations_total` by `floe_product_name`, `floe_status`, and `floe_plugin_name` | Fresh samples exist for `customer-360` with `floe_status="success"` |
| Grafana | Optional UI | Inspect only if the platform provisions curated dashboards backed by the active datasource | Panels shown in the alpha demo use validated Loki or Prometheus queries and are not empty because of datasource drift |
| Jaeger | UI and API | Search service `customer-360` with tags `floe.product.name` and `floe.run.id`, then inspect model/table spans | Trace exists for the current run and includes runtime/plugin spans plus `floe.table.name` or dbt model evidence for `mart_customer_360` |
| Polaris | API, UI when provisioned by the selected catalog profile | Query the catalog for Customer 360 tables | Customer 360 tables are registered |
| Cube | Not currently part of the default alpha proof | Validate only when the semantic layer is enabled for the platform | Semantic queries prove access to Customer 360 metrics, not only process health |

Root `/` returning `404` is not a failure for API-only alpha surfaces when the
documented health and query endpoints pass. This is expected for the current
Floe chart Marquez deployment and for Loki. The contributor `make demo` lane
exposes Loki and Prometheus direct API endpoints by default; Grafana is a
curated presentation surface only when the platform provisions validated
dashboards.

Useful manual queries:

```text
{service_name=~".+"} |= "customer-360" |= "<dagster.run_id>"
```

Loki API examples:

```bash
curl -fsS http://localhost:3101/ready
curl -fsS 'http://localhost:3101/loki/api/v1/query_range' \
  --get \
  --data-urlencode 'query={service_name=~".+"} |= "customer-360" |= "<dagster.run_id>"' \
  --data-urlencode 'limit=20' | jq .
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

Marquez API examples:

```bash
curl -fsS http://localhost:5100/api/v1/namespaces/customer-360/jobs | jq .
curl -fsS http://localhost:5100/api/v1/namespaces/customer-360/jobs/customer-360/runs | jq .
curl -fsS http://localhost:5100/api/v1/namespaces/customer-360/datasets | jq .
curl -fsS 'http://localhost:5100/api/v1/lineage?nodeId=dataset:customer-360:customer_360.main.mart_customer_360&depth=3' | jq .
```

## Failure Classification

Use the validator status or expanded alpha failure class to decide where to
debug first. The current validator emits the existing runtime statuses; new
validator work should use the full alpha class set below.

| Status | Meaning | First action |
| --- | --- | --- |
| `backend_unreachable` | The backend API, service URL, tunnel, or collector path is unavailable | Check service pods, URLs, and port-forwards before rerunning the product |
| `no_fresh_evidence` | The backend is reachable but returned no records for the expected product/run/table | Confirm the run ID and that the relevant signal exporter is enabled |
| `stale_evidence` | Records exist only outside the freshness window | Trigger a new Customer 360 run and validate against the new run ID |
| `wrong_context` | Records exist but match another product, run, or table | Check `FLOE_DEMO_RUN_ID`, the validation manifest, and service URLs |
| `product_failure` | Evidence shows the Customer 360 run or model/table execution failed | Debug Dagster/dbt/storage output before investigating observability backends |
| `platform_service_failure` | A required platform service is deployed but unhealthy or returning service-level errors | Check the service pod logs, readiness, and backend-specific health endpoint |
| `dashboard_datasource_drift` | Grafana panel queries fail or return empty results through the configured datasource | Compare the panel datasource with the backend API that returns live evidence |
| `contract_gap` | The current runtime or backend cannot produce a required alpha evidence family yet | Track the missing signal as an implementation gap instead of treating the product run as failed |

## Related Guides

- [Customer 360 Golden Demo](customer-360.md)
- [Validate your platform](../platform-engineers/validate-platform.md)
- [Validate your data product](../data-engineers/validate-data-product.md)
- [DevPod contributor workspace](../contributing/devpod-hetzner.md)
- [Contributor troubleshooting](../contributing/troubleshooting.md)
