# E2E Test Error Report

**Date**: 2026-02-23
**Branch**: `fix/e2e-infra-blockers`
**Cluster**: Kind `floe-test` (K8s v1.29.0)

### Run History

| Run | Passed | Failed | Errors | Fix Applied |
|-----|--------|--------|--------|-------------|
| 1 | 87 | 33 | 21 | Baseline (no MinIO bucket, no Polaris catalog) |
| 2 | 86 | 34 | 21 | MinIO bucket + Polaris catalog manually created |
| 3 | **90** | **46** | **5** | PyIceberg from git main (PUT HttpMethod fix, PR #3010) |

**Current Results (Run 3)**: 90 passed, 46 failed, 5 errors, 1 xfailed (142 total)

---

## Summary by Root Cause

| # | Root Cause | Tests Affected | Severity |
|---|-----------|----------------|----------|
| 1 | PyIceberg + Polaris 1.2.0 protocol incompatibility | 16 ERRORs | **Critical** |
| 2 | Polaris bootstrap hook failure (in helm_workflow tests) | 5 ERRORs | High |
| 3 | dbt seed/run failures (DuckDB/Polaris connectivity) | 14 FAILEDs | High |
| 4 | Dagster GraphQL API field requirements | 1 FAILED | Medium |
| 5 | Polaris config endpoint requires auth (1.2.0 change) | 3 FAILEDs | Medium |
| 6 | Pod label mismatch (name vs component) | 1 FAILED | Low |
| 7 | Marquez instability / port-forward issues | 4 FAILEDs | Medium |
| 8 | Observability not implemented (OTel/OpenLineage gaps) | 5 FAILEDs | Expected |
| 9 | Governance checks (secrets, vulnerabilities) | 3 FAILEDs | Medium |
| 10 | Helm upgrade schema validation | 1 FAILED | Low |
| 11 | Dagster workspace ConfigMap structure | 1 FAILED | Medium |
| 12 | Dagster sensor definition error | 1 FAILED | Medium |

---

## Category 1: PyIceberg + Polaris 1.2.0 Protocol Incompatibility (16 ERRORs)

### Error
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ConfigResponse
endpoints
  Value error, 'PUT' is not a valid HttpMethod
```

### Root Cause
Polaris 1.2.0-incubating returns an endpoint configuration that includes HTTP methods
(e.g., `PUT`, `DELETE`) in the `/api/catalog/v1/config` response. The installed version
of PyIceberg (`pyiceberg` in the workspace) has a `ConfigResponse` Pydantic model that
only recognizes `GET`, `POST`, `HEAD` as valid `HttpMethod` enum values. When Polaris
returns `PUT` endpoints, PyIceberg's strict Pydantic validation rejects the response.

This is a **version compatibility issue** between:
- **Polaris 1.2.0-incubating** (Iceberg REST Catalog spec with extended endpoints)
- **PyIceberg** (older version with restrictive HttpMethod enum)

### Affected Tests (16)
- `test_compile_deploy_materialize_e2e.py::test_polaris_catalog_accessible`
- `test_compile_deploy_materialize_e2e.py::test_iceberg_tables_exist_after_materialization`
- `test_data_pipeline.py::test_dbt_seed_loads_data` (x3 products)
- `test_data_pipeline.py::test_medallion_layers`
- `test_data_pipeline.py::test_iceberg_tables_created`
- `test_data_pipeline.py::test_incremental_model_merge`
- `test_data_pipeline.py::test_data_retention_enforcement`
- `test_data_pipeline.py::test_snapshot_expiry_enforcement`
- `test_multi_product_isolation_e2e.py::test_polaris_namespace_isolation`
- `test_schema_evolution.py::test_polaris_namespace_isolation`
- `test_schema_evolution.py::test_iceberg_schema_evolution`
- `test_schema_evolution.py::test_iceberg_partition_evolution`
- `test_schema_evolution.py::test_data_retention_cleanup`
- `test_schema_evolution.py::test_snapshot_expiry`

### Version Details
- **PyIceberg installed**: 0.11.0 (latest PyPI release)
- **PyIceberg HttpMethod enum**: `GET`, `HEAD`, `POST`, `DELETE` (missing `PUT`)
- **Polaris 1.2.0**: Returns endpoints with `PUT` method in config response
- **Fix**: [PR #3010](http://www.mail-archive.com/commits@iceberg.apache.org/msg21822.html)
  merged to PyIceberg `main` on 2026-02-18, but **not yet released** to PyPI

### Fix Options
1. **Install PyIceberg from git** (temporary):
   `pip install git+https://github.com/apache/iceberg-python.git@main`
2. **Wait for PyIceberg 0.11.1+** release with the fix
3. **Monkey-patch HttpMethod enum** in conftest.py as workaround:
   ```python
   from pyiceberg.catalog.rest import HttpMethod
   HttpMethod._value2member_map_["PUT"] = HttpMethod("PUT")
   ```

### Stack Trace Location
`tests/e2e/conftest.py:449` → `pyiceberg.catalog.rest.__init__.py:623`

---

## Category 2: Polaris Bootstrap Hook Failure (5 ERRORs)

### Error
```
Failed: Platform deployment failed: Error: failed post-install: 1 error occurred:
    * job floe-platform-polaris-bootstrap failed: BackoffLimitExceeded
```

### Root Cause
The `test_helm_workflow.py` tests perform their own `helm upgrade --install` in a
temporary namespace. The Polaris bootstrap Helm hook (`post-install,post-upgrade`)
runs as a Job that:
1. Waits for Polaris to be healthy
2. Verifies MinIO bucket exists
3. Creates the `floe-e2e` catalog

The hook fails because within the test's fresh Helm install:
- MinIO provisioning job may not complete before the bootstrap hook runs
- The `curlimages/curl:8.5.0` image may need pulling (not pre-loaded in Kind)
- The bootstrap has a `backoffLimit: 3` with 5-second waits, which may be
  insufficient for slower CI environments

### Affected Tests (5)
- `test_helm_workflow.py::TestHelmWorkflow::test_platform_deployed`
- `test_helm_workflow.py::TestHelmWorkflow::test_polaris_accessible`
- `test_helm_workflow.py::TestHelmWorkflow::test_postgresql_accessible`
- `test_helm_workflow.py::TestCodeLocationRegistration::test_dagster_workspace_configmap`
- `test_helm_workflow.py::TestJobExecution::test_job_template_rendered`

### Fix Options
1. Pre-load `curlimages/curl:8.5.0` into Kind cluster
2. Increase bootstrap job timeout and backoff limit
3. Add MinIO bucket creation as a separate Helm hook with lower weight

---

## Category 3: dbt Seed/Run Failures (14 FAILEDs)

### Error
```
subprocess.CalledProcessError: Command '['dbt', 'seed', '--project-dir',
  '/workspace/demo/customer-360', '--profiles-dir', '/workspace/demo/customer-360']'
  returned non-zero exit status 1.
```

### Root Cause
The dbt tests try to run `dbt seed` and `dbt run` from the **host** against the
demo products. These commands need to connect to DuckDB with Iceberg/Polaris catalog
integration. The failures cascade from:
1. Polaris client fails (Category 1 — PyIceberg incompatibility)
2. dbt-iceberg adapter can't connect to catalog
3. All dbt operations fail

Additionally, the demo `profiles.yml` may reference K8s-internal hostnames that aren't
resolvable from the test host.

### Affected Tests (14)
- `test_data_pipeline.py::test_pipeline_execution_order` (x3 products)
- `test_data_pipeline.py::test_dbt_tests_pass` (x3 products)
- `test_data_pipeline.py::test_data_quality_checks` (x3 products)
- `test_data_pipeline.py::test_pipeline_retry`
- `test_dbt_lifecycle_e2e.py::test_dbt_seed`
- `test_dbt_lifecycle_e2e.py::test_dbt_run`
- `test_dbt_lifecycle_e2e.py::test_dbt_test`

### Fix
Resolve Category 1 first (PyIceberg/Polaris compatibility). The dbt tests should
then work once the Polaris catalog is accessible.

---

## Category 4: Dagster GraphQL API Field Requirements (1 FAILED)

### Error
```
Dagster GraphQL returned 500: Variable '$executionParams' got invalid value;
Field 'repositoryName' of required type 'String!' was not provided.
Field 'repositoryLocationName' of required type 'String!' was not provided.
```

### Root Cause
The test `test_trigger_asset_materialization` sends a GraphQL mutation to trigger
asset materialization but doesn't include the required `repositoryName` and
`repositoryLocationName` fields in the `executionParams.selector`.

This is a **test code bug** — the GraphQL API requires these fields to identify
which code location contains the assets.

### Affected Tests (1)
- `test_compile_deploy_materialize_e2e.py::test_trigger_asset_materialization`

### Fix
Update the test to include `repositoryName` and `repositoryLocationName` in the
GraphQL mutation parameters. These should reference the demo code locations defined
in `values-test.yaml` (e.g., `customer-360`, `iot-telemetry`, `financial-risk`).

---

## Category 5: Polaris Config Endpoint Requires Auth (3 FAILEDs)

### Error
```
Polaris /api/catalog/v1/config returned 401
```

### Root Cause
Tests access `http://localhost:8181/api/catalog/v1/config` without authentication.
Polaris 1.2.0-incubating requires OAuth2 authentication for this endpoint.

The management health endpoint (`/q/health/ready` on port 8182) does NOT require
auth and works correctly.

### Affected Tests (3)
- `test_platform_deployment_e2e.py::test_polaris_health`
- `test_service_failure_resilience_e2e.py::test_polaris_pod_restart_detected`
- `test_helm_upgrade_e2e.py::test_helm_upgrade_succeeds` (partially)

### Fix
Update tests to either:
1. Use the management health endpoint (port 8182, `/q/health/ready`) for health checks
2. Add OAuth2 authentication to test requests

---

## Category 6: Pod Label Mismatch (1 FAILED)

### Error
```
Missing required platform services: {'polaris', 'postgresql'}
Deployed: {'cube', 'minio', 'dagster', 'jaeger', 'otel', 'floe-platform'}
```

### Root Cause
The test `test_all_pods_ready` discovers services by `app.kubernetes.io/name` label.
However, Polaris and PostgreSQL pods have:
- `app.kubernetes.io/name: floe-platform` (parent chart name)
- `app.kubernetes.io/component: polaris` / `postgresql`

The test expects `app.kubernetes.io/name` to be `polaris` or `postgresql`, but the
Helm chart sets it to the parent chart name (`floe-platform`).

### Affected Tests (1)
- `test_platform_bootstrap.py::test_all_pods_ready`

### Fix Options
1. Update test to also check `app.kubernetes.io/component` label
2. Update chart templates to set `app.kubernetes.io/name` to the component name

---

## Category 7: Marquez Instability (4 FAILEDs)

### Error
```
Service marquez:5000 not available in floe-test
httpx.RemoteProtocolError: Server disconnected without sending a response.
Timeout waiting for Marquez lineage API after 90.0s
```

### Root Cause
The Marquez pod has experienced multiple restarts (7+ in the test run). This causes:
1. Port-forward connections to drop
2. Health checks to timeout
3. API calls to get disconnected responses

The instability may be caused by:
- Insufficient memory for Marquez
- PostgreSQL connection issues during Marquez startup
- Marquez init failing to create its schema in the shared PostgreSQL

### Affected Tests (4)
- `test_observability.py::test_openlineage_events_in_marquez`
- `test_observability.py::test_trace_lineage_correlation`
- `test_observability.py::test_marquez_lineage_graph`
- `test_platform_deployment_e2e.py::test_marquez_health`

### Fix
1. Investigate Marquez pod restarts (check logs for OOM or DB connection errors)
2. Consider giving Marquez its own database or init schema job
3. Increase Marquez memory limits

---

## Category 8: Observability Not Implemented (5 FAILEDs)

### Error
```
OBSERVABILITY GAP: Compilation produces no log output.
TRACE GAP: No floe-specific attributes found in trace spans.
EMISSION GAP: No OpenLineage jobs found after compilation.
Timeout waiting for Jaeger traces to appear after 10.0s
No compilation traces found in Jaeger after 30s.
```

### Root Cause
These tests validate that the platform emits OTel traces and OpenLineage events during
compilation and pipeline execution. This functionality is **not yet implemented** —
the compilation pipeline doesn't instrument with OTel spans or emit OpenLineage events.

### Affected Tests (5)
- `test_observability.py::test_structured_logs_with_trace_id`
- `test_observability.py::test_trace_content_validation`
- `test_observability.py::test_openlineage_four_emission_points`
- `test_observability.py::test_compilation_emits_otel_spans`
- `test_observability_roundtrip_e2e.py::test_compilation_generates_traces`

### Fix
Implement OTel instrumentation and OpenLineage event emission in the compilation
pipeline. This is tracked as a future feature, not a bug.

---

## Category 9: Governance Checks (3 FAILEDs)

### Errors
1. **Hardcoded secrets** (10 found): Values files contain test passwords
2. **pip-audit vulnerabilities**: Known CVEs in dependencies
3. **Governance enforcement**: Compilation validation issue

### Root Cause
1. `values-test.yaml` contains hardcoded passwords for test environments
   (e.g., `floe-test-password-1234`, `minioadmin123`, `demo-secret`).
   The governance test scans for these patterns.
2. Known dependency vulnerabilities exist (tracked in `pyproject.toml`
   `[tool.uv-secure.vulnerability_criteria]`)
3. The governance enforcement test expects compilation to validate models
   but the compilation may not produce model-level validation

### Affected Tests (3)
- `test_governance.py::test_secrets_not_hardcoded`
- `test_governance.py::test_pip_audit_clean`
- `test_governance.py::test_governance_enforcement_via_compilation`

### Fix
1. Use `# pragma: allowlist secret` on test values or update test to exclude
   `values-test.yaml`
2. Update dependencies or add vulnerability ignores
3. Review governance enforcement compilation logic

---

## Category 10: Helm Upgrade Schema Validation (1 FAILED)

### Error
```
Helm upgrade failed: UPGRADE FAILED: values don't meet the specifications of
the schema(s) in the following chart(s)
```

### Root Cause
The Helm upgrade test modifies values and attempts an upgrade, but the modified
values fail the Dagster subchart's JSON schema validation. The main Helm install
uses `--skip-schema-validation` but the test may not pass this flag.

### Affected Tests (1)
- `test_helm_upgrade_e2e.py::test_helm_upgrade_succeeds`

### Fix
Pass `--skip-schema-validation` in the test's helm upgrade command, or fix the
values to pass the Dagster subchart schema.

---

## Category 11: Dagster Workspace ConfigMap (1 FAILED)

### Error
```
Workspace ConfigMap missing module path for customer-360
```

### Root Cause
The test `test_three_products_visible_in_dagster` checks the Dagster workspace
ConfigMap for module paths. The ConfigMap structure may not match what the test
expects because the workspace is configured via `externalConfigmap` in
`values-test.yaml`.

### Affected Tests (1)
- `test_demo_mode.py::test_three_products_visible_in_dagster`

### Fix
Review the workspace ConfigMap template and ensure it generates entries matching
the code locations defined in `values-test.yaml`.

---

## Category 12: Dagster Sensor Definition Error (1 FAILED)

### Error
```
dagster._core.errors.DagsterInvalidDefinitionError: No job was provided to SensorDefinition.
```

### Root Cause
The test `test_auto_trigger_sensor_e2e` tries to create a `SensorDefinition` without
providing the required `job` parameter. This is a **test code bug** — the Dagster API
requires a job reference when constructing sensors.

### Affected Tests (1)
- `test_data_pipeline.py::test_auto_trigger_sensor_e2e`

### Fix
Update the test to provide a valid job reference when creating the SensorDefinition.

---

## Infrastructure Issues Resolved (Pre-Test)

The following issues were resolved before the E2E test run:

| # | Issue | Resolution |
|---|-------|------------|
| 1 | `uv export --all-packages` includes local paths | Added `grep -v '^\.\/'` filter |
| 2 | `FLOE_PLUGINS` ARG empty in Docker stage 2 | Re-declared with default value |
| 3 | `dagster-webserver` not installed | Added separate `pip install` step |
| 4 | `dagster-daemon` not a PyPI package | Removed (bundled with dagster) |
| 5 | `dagster-k8s` version mismatch | Removed (not needed in-container) |
| 6 | dagster version conflict (1.12.14 vs 1.12.15) | Pinned `dagster==1.12.14` |
| 7 | Cube Store image 403 (private registry) | Changed to `cubejs/cubestore` |
| 8 | `dagster-postgres` missing | Added to Dockerfile pip install |
| 9 | Dagster pods OOMKilled (512Mi) | Increased to 1536Mi |
| 10 | SQLAlchemy 2.1.0b1 psycopg3 NOTIFY bug | Pinned `sqlalchemy>=2.0,<2.1` |
| 11 | Non-root port 80 bind failure | Changed service port to 3000 |
| 12 | Readiness probe wrong port | Added explicit probe config |
| 13 | DAGSTER_HOME permission denied | Created dir + chown in Dockerfile |
| 14 | Port-forward 3000:80 → 3000:3000 | Updated test-e2e.sh |
| 15 | MinIO bucket not provisioned | Manually created via mc client |
| 16 | Polaris catalog not bootstrapped | Manually created via REST API |

---

## Recommended Priority Order

1. **Category 1** (PyIceberg/Polaris compat) — Blocks 16 tests, cascades to Category 3
2. **Category 2** (Bootstrap hook) — Fix provisioning to make it self-healing
3. **Category 7** (Marquez stability) — Investigate and fix restarts
4. **Category 4, 5, 6** (Test code fixes) — Quick wins
5. **Category 8** (Observability) — Feature implementation, not bug fixes
6. **Category 9** (Governance) — Policy decisions
