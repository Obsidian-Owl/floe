# Customer 360 Validation

## Automated Evidence

The automated Customer 360 validation command is introduced by release hardening before alpha tagging. Until that command exists, use this page as the evidence checklist for the golden demo.

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
