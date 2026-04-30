# Customer 360 Validation

## Automated Evidence

Run the Customer 360 evidence gate after `make demo` and after `make demo-customer-360-run` has completed:

```bash
make demo-customer-360-validate
```

The command loads its default evidence plan from `demo/customer-360/validation.yaml`. The manifest defines service URLs, expected platform pods, and argv-list commands for Dagster, storage, Marquez, Jaeger, and business metric checks.

Use `FLOE_DEMO_VALIDATION_MANIFEST=/path/to/validation.yaml` for a different platform shape. Individual command overrides are also available, for example `FLOE_DEMO_LINEAGE_CHECK_COMMAND`, `FLOE_DEMO_STORAGE_CHECK_COMMAND`, `FLOE_DEMO_CUSTOMER_COUNT_COMMAND`, and `FLOE_DEMO_LIFETIME_VALUE_COMMAND`.

Expected evidence keys:

- `platform.ready`
- `dagster.customer_360_run`
- `storage.customer_360_outputs`
- `lineage.marquez_customer_360`
- `tracing.jaeger_customer_360`
- `business.customer_count`
- `business.total_lifetime_value`

Expected successful runner evidence:

```text
status=PASS
dagster.run_id=<run-id>
dagster.job_name=customer-360
```

Expected successful validation evidence:

```text
status=PASS
evidence.business.customer_count=<non-negative integer>
evidence.business.total_lifetime_value=<non-negative decimal>
evidence.dagster.customer_360_run=true
evidence.lineage.marquez_customer_360=true
evidence.platform.ready=true
evidence.storage.customer_360_outputs=true
evidence.tracing.jaeger_customer_360=true
```

The evidence maps to the release surfaces as follows:

- Business evidence comes from querying the generated Customer 360 mart metrics.
- Dagster evidence proves the configured `customer-360` run completed.
- Lineage evidence proves Marquez has Customer 360 namespace/job/dataset records.
- Storage evidence proves the expected Iceberg output table is readable.
- Tracing evidence proves Jaeger contains Customer 360 run traces.

## Manual UI Inspection

| Service | Check | Pass Criteria |
| --- | --- | --- |
| Dagster | Open run history | Latest Customer 360 run succeeded |
| MinIO | Open object browser | Customer 360 output objects are visible |
| Marquez | Search Customer 360 namespace/job | Lineage graph has Customer 360 datasets |
| Jaeger | Search Floe/Dagster service | Trace exists for Customer 360 run |
| Polaris | Open catalog API/UI path | Customer 360 tables are registered |

## Related Guide

- [Customer 360 Golden Demo](customer-360.md)
- [DevPod + Hetzner operations](../operations/devpod-hetzner.md)
