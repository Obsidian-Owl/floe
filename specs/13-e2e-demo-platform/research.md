# Research: Epic 13 - E2E Platform Testing & Live Demo

## Prior Decisions (from Agent Memory)

- ADR-0017: K8s-native testing (Kind cluster for all integration/E2E)
- ADR-0039: Multi-environment promotion (dev→staging→prod)
- ADR-0040: Artifact immutability and GC (OCI registry-level)
- Epic 8C clarification: Promotion envs as K8s namespaces in single Kind cluster

## Key Findings

### E2E Test Infrastructure (PARTIALLY IMPLEMENTED)

| Component | Status | Location |
|-----------|--------|----------|
| Helm workflow test | Complete | `tests/e2e/test_helm_workflow.py` |
| Demo flow test | Skeleton (pytest.fail) | `tests/e2e/test_demo_flow.py` |
| E2E conftest | Complete | `tests/e2e/conftest.py` |
| E2E test runner | Complete | `testing/ci/test-e2e.sh` |
| IntegrationTestBase | Complete | `testing/base_classes/integration_test_base.py` |
| Makefile target | Complete | `make test-e2e` |

### Compilation Pipeline (6 STAGES, NOT 13)

The spec referenced "13-step compilation pipeline" but actual implementation has 6 stages:
`LOAD → VALIDATE → RESOLVE → ENFORCE → COMPILE → GENERATE`

**Decision**: Update spec to reference 6-stage pipeline. The "13 steps" was from early design docs.

### Plugin System (13 TYPES, NOT 12)

Actual plugin types in `PluginType` enum: COMPUTE, ORCHESTRATOR, CATALOG, STORAGE, TELEMETRY_BACKEND, LINEAGE_BACKEND, DBT, SEMANTIC_LAYER, INGESTION, SECRETS, IDENTITY, QUALITY, RBAC (+ NETWORK_SECURITY in some contexts)

**Decision**: Use 13 as the authoritative count from `plugin_types.py`.

### Marquez (EXISTS BUT DISABLED)

- Plugin: `plugins/floe-lineage-marquez/` (OpenLineage HTTP transport)
- Helm config: `charts/floe-platform/values.yaml` lines 463-497, `marquez.enabled: false`
- Image: `marquezproject/marquez:0.49.0`
- Integration tests: `packages/floe-core/tests/integration/test_lineage_integration.py` (6 working tests)

**Decision**: Enable Marquez in values.yaml for E2E/demo. Infrastructure already exists.

### Artifact Promotion (FULLY IMPLEMENTED - Epic 8C)

- Controller: `packages/floe-core/src/floe_core/oci/promotion.py`
- Schemas: `packages/floe-core/src/floe_core/schemas/promotion.py`
- CLI: `floe platform promote/rollback/status/lock`
- Gates: policy check, security scan, signature verification

**Decision**: E2E tests validate existing promotion system, no new code needed.

### Seed Data (NOT IMPLEMENTED)

No seed CSV files exist anywhere in the codebase. dbt project config supports seeds but none created.

**Decision**: Create seed CSVs for 3 data products in `demo/` directory structure.

### Sensors (NOT IMPLEMENTED)

No Dagster sensor definitions exist. Only schedules via `DagsterOrchestratorPlugin.schedule_job()`.

**Decision**: Add sensor for auto-trigger-on-health (new ABC method + Dagster implementation).

### Data Retention/Cleanup (PARTIAL)

- Iceberg snapshot expiry exists: `_snapshot_manager.py` with `expire_snapshots()`
- No time-based data deletion (row-level retention)
- No scheduled cleanup jobs

**Decision**: For demo mode, implement Iceberg snapshot expiry as Dagster sensor + time-based cleanup via dbt model with `DELETE WHERE timestamp < now() - interval '1 hour'`.

### Multi-Environment Namespaces (AD-HOC)

Currently hardcoded `floe-dev`, `floe-test` in Makefile. No systematic env→namespace mapping.

**Decision**: Create namespace manager for E2E tests. Promotion E2E deploys to `floe-dev`, `floe-staging`, `floe-prod` namespaces within Kind cluster.

## Alternatives Considered

| Decision | Chosen | Rejected | Reason |
|----------|--------|----------|--------|
| Lineage viz | Dagster UI + Marquez | Dagster UI only | User chose both; Marquez already in Helm chart |
| Environments | K8s namespaces | Separate clusters | Too heavy for local testing; single Kind sufficient |
| Seed data scale | Configurable (default small) | Fixed large | User requested configurability |
| Schedule testing | Auto-trigger + 10-min recurring | Config validation only | User wants live running demo |
| Data retention | 1-hour with Iceberg expiry | No retention | Prevents unbounded growth in demos |
