# Customer 360 Validation

## Automated Evidence

Run the Customer 360 evidence gate after `make demo` and after the Customer 360 run has completed:

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
