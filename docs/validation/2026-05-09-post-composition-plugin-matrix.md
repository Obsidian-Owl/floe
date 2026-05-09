# Post-Composition Plugin Composability Matrix

Date: 2026-05-09
Repo: /Users/dmccarthy/Projects/floe
Status: In progress

## Level Definitions

| Level | Meaning | Required evidence |
| --- | --- | --- |
| 0 | Discoverable plugin only | Entry point, metadata, config schema |
| 1 | Declares capabilities and requirements | PluginCapabilities, PluginRequirements, compatibility tests |
| 2 | Emits or consumes typed bindings | Contract model, schema tests, no raw secrets |
| 3 | Has deployment/runtime translators validated by resolver | Resolver tests, generated deployment binding, renderer tests, runtime evidence where applicable |

## Decisions

| Plugin family | Current level | Target level | Decision | Composition trigger | Evidence | Follow-up |
| --- | --- | --- | --- | --- | --- | --- |
| Storage / MinIO | Not assessed | Not assessed | Not assessed | Current Iceberg runtime path | Not recorded | Not recorded |
| Catalog / Polaris | Not assessed | Not assessed | Not assessed | Current Iceberg runtime path | Not recorded | Not recorded |
| Compute / DuckDB | Not assessed | Not assessed | Not assessed | dbt/storage runtime path | Not recorded | Not recorded |
| DBT / Core and Fusion | Not assessed | Not assessed | Not assessed | dbt SQL compilation and runtime packaging | Not recorded | Not recorded |
| Orchestrator / Dagster | Not assessed | Not assessed | Not assessed | runtime execution and Iceberg writer handoff | Not recorded | Not recorded |
| Iceberg package | Not assessed | Not assessed | Not assessed | platform-owned Iceberg write semantics | Not recorded | Not recorded |
| Ingestion / dlt | Not assessed | Not assessed | Not assessed | landing/quarantine/checkpoint/raw bucket needs | Not recorded | Not recorded |
| Secrets / Kubernetes and Infisical | Not assessed | Not assessed | Not assessed | credential binding and secret refs | Not recorded | Not recorded |
| Identity / Keycloak | Not assessed | Not assessed | Not assessed | workload identity and credential modes | Not recorded | Not recorded |
| RBAC / Kubernetes | Not assessed | Not assessed | Not assessed | workload identity and generated access policy | Not recorded | Not recorded |
| Network security / Kubernetes | Not assessed | Not assessed | Not assessed | plugin endpoints and identity bindings | Not recorded | Not recorded |
| Telemetry backends | Not assessed | Not assessed | Not assessed | backend deployment topology or auth | Not recorded | Not recorded |
| Lineage backend / Marquez | Not assessed | Not assessed | Not assessed | endpoint/auth/deployment wiring | Not recorded | Not recorded |
| Quality / dbt and GX | Not assessed | Not assessed | Not assessed | compute/storage runtime needs | Not recorded | Not recorded |
| Semantic layer / Cube | Not assessed | Not assessed | Not assessed | compute/catalog/storage runtime consumption | Not recorded | Not recorded |
| Alert channels | Not assessed | Not assessed | Not assessed | user-facing alert delivery composition | Not recorded | Not recorded |
