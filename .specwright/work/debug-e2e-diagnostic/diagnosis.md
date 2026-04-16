# E2E Test Diagnostic Report

**Date**: 2026-03-30
**Branch**: main @ 26878b3
**Infrastructure**: Hetzner DevPod (ccx33), Kind cluster
**Run time**: 70 minutes
**Result**: 203 passed, 12 failed, 15 errors, 1 xfailed

## Category Summary

| Category | Tests | Root Cause | Type |
|----------|-------|------------|------|
| Polaris port-forward drop | 15 errors + 3 failed | kubectl port-forward died mid-run | Infra |
| Dagster code location import | 6 failed | `No module named 'floe_iceberg'` in container | Production |
| dbt profile path assertion | 1 failed | Test expects `/tmp/` path, got `:memory:` | Test |
| OpenLineage parentRun facet | 1 failed | No parentRun facet in Marquez runs | Production |
| CVE in cryptography | 1 failed | cryptography 46.0.5 has GHSA-m959-cc7f-wv43 | Dependency |
| IPv6 kubeconfig regression | (fixed) | `localhost` in kubeconfig, macOS prefers IPv6 | Infra (FIXED) |

---

## Category 1: Polaris Port-Forward Drop (INFRA)

**Tests affected**: 15 ERRORs (test_platform_bootstrap, test_schema_evolution) + 3 FAILEDs (test_multi_product_isolation, test_platform_deployment, test_service_failure_resilience)

**Observed**: All fail with `TCP connection to localhost:8181 failed` / `Connection refused`.

**Root cause**: The Polaris kubectl port-forward process died mid-test run. The watchdog restarted other services but Polaris port-forward was on ports 8181+8182 which had initially conflicted with SSH tunnels. After the SSH tunnels were killed, the kubectl port-forward started but was unstable.

**Evidence**: Port-forward error at test start: `Unable to listen on port 8181/8182: address already in use`. After SSH tunnel cleanup, the port-forward for Polaris was fragile. The watchdog detected dead ports and restarted, but some tests ran during the gap.

**Fix category**: INFRA - improve port-forward lifecycle in `test-e2e.sh`. The SSH tunnel cleanup and port-forward startup should be sequenced with health gates.

---

## Category 2: Dagster Code Location Import Failure (PRODUCTION)

**Tests affected**: 6 tests across test_compile_deploy_materialize_e2e, test_data_pipeline, test_demo_mode

**Observed**:
- `No module named 'floe_iceberg'` when Dagster loads demo code locations
- `Configuration error for plugin 'polaris': [{'field': 'oauth2', 'message': 'Field required'}, {'field': 'credential', 'message': 'Extra inputs are not permitted'}]`
- All 3 code locations (customer-360, iot-telemetry, financial-risk) fail to load

**Root cause**: TWO distinct production bugs:

1. **Missing `floe_iceberg` package in Dagster container**: The demo `definitions.py` files import from `floe_iceberg` but this package is not installed in the `floe-dagster-demo` Docker image. The Dockerfile needs to include floe-iceberg in its pip install.

2. **Polaris plugin config schema change**: The `polaris` plugin's Pydantic model changed field names — `credential` was renamed/removed and `oauth2` is now required. Demo product configs still use the old field names.

**This is NOT a test or infra issue** — this is real production code that would break for any user.

---

## Category 3: dbt Profile Path Assertion (TEST)

**Test**: `test_dbt_profile_correct_for_in_cluster_execution`

**Observed**: `DuckDB path must be under /tmp/ for container writability, got :memory:`

**Root cause**: The test asserts that DuckDB path starts with `/tmp/` for container writability. However, the compiled profile uses `:memory:` which is a valid DuckDB target that doesn't need filesystem access at all. The test assertion is overly strict.

**Fix category**: TEST - the assertion should accept both `/tmp/*` paths AND `:memory:` as valid in-container configurations.

---

## Category 4: OpenLineage parentRun Facet (PRODUCTION)

**Test**: `test_openlineage_four_emission_points`

**Observed**: `PARENT FACET GAP: No Marquez runs contain a valid 'parentRun' facet with a runId. Runs inspected: 294`

**Root cause**: Per-model dbt lineage events are emitted but do NOT include a `parentRun` facet linking them to the parent Dagster asset run. This means lineage graphs in Marquez won't show the dbt→Dagster relationship.

**Fix category**: PRODUCTION - LineageResource needs to pass `parent_run_id` when extracting per-model lineage events.

---

## Category 5: CVE in cryptography (DEPENDENCY)

**Test**: `test_pip_audit_clean`

**Observed**: `cryptography 46.0.5` has `GHSA-m959-cc7f-wv43`, fix available in `46.0.6`

**Fix**: Bump `cryptography` to `>=46.0.6` in `packages/floe-core/pyproject.toml` (or wherever it's pinned). Alternatively, add to `.vuln-ignore` if the CVE doesn't apply (review required).

---

## Category 6: IPv6 Kubeconfig (INFRA - ALREADY FIXED)

**Root cause**: `devpod-sync-kubeconfig.sh` wrote `server: https://localhost:26443` but macOS resolves `localhost` to `[::1]` (IPv6) first. The SSH tunnel only binds IPv4 (`127.0.0.1`).

**Fix applied**: Changed line 92 of `devpod-sync-kubeconfig.sh` to use `127.0.0.1` instead of `localhost`.

**Status**: FIXED in this session. Needs to be committed.

---

## Triage Summary

### Production bugs (DO NOT FIX in this debug session):
1. `floe_iceberg` not installed in Dagster demo image
2. Polaris plugin config schema mismatch (`oauth2` required, `credential` forbidden)
3. OpenLineage parentRun facet missing from per-model events

### Test/infra fixes (CAN fix):
1. **DONE**: IPv6 kubeconfig fix in `devpod-sync-kubeconfig.sh`
2. **TODO**: dbt profile path assertion should accept `:memory:`
3. **TODO**: cryptography CVE bump (or ignore)
4. **TODO**: Port-forward lifecycle improvement (kill SSH tunnels before kubectl port-forwards)
