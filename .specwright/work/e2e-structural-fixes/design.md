# Design: E2E Structural Fixes (Revised)

## Problem

91 of ~230 E2E tests fail (50 failed + 41 errors). Root cause analysis reveals
three distinct failure categories:

| Category | Count | Root Cause |
|----------|-------|-----------|
| **Infrastructure connectivity** | 41 errors | Port-forwards/SSH tunnels died mid-run; Dagster and Marquez unreachable |
| **Compilation fixture** | 6 failed | `tests/conftest.py:124-126` hardcodes `localhost:5100` and `localhost:4317` in `compiled_artifacts()` fixture — unreachable from in-cluster test pod |
| **Cascading from compilation** | ~15 failed | Tests depend on successful compilation (profile validation, enforcement, serialization) |
| **Profile isolation** | 3 failed | `test_demo_profile_untouched_during_session` — profile file mutation |
| **Charts dir missing** | 5 errors | `test_helm_workflow.py` + `test_governance.py` assume `charts/` exists relative to CWD |
| **Other/unknown** | ~21 failed | Tests in modules after 44% mark (log truncated); likely cascade from infrastructure death |

## What's Already Done (shipped on main)

These fixes from prior work units are confirmed in the current codebase:

1. **K8sRunLauncher image** — `values-test.yaml:110-118` and `values-demo.yaml:78-86`
   already set `image.repository: floe-dagster-demo`, `tag: latest`, `pullPolicy: Never`.
   Confirmed: `test_trigger_asset_materialization` PASSED in latest run.

2. **E2E conftest ServiceEndpoint** — `tests/e2e/conftest.py:1035` uses
   `ServiceEndpoint("otel-collector-grpc").url` and line 1038 uses
   `ServiceEndpoint('marquez').url`. All E2E fixture endpoints are resolved dynamically.

3. **E2E Job definition** — `testing/k8s/jobs/test-e2e.yaml` already has full env var set:
   `POLARIS_HOST`, `MINIO_HOST`, `MARQUEZ_HOST`, `DAGSTER_HOST`, `OTEL_HOST`,
   `INTEGRATION_TEST_HOST=k8s`, and all credential references.

4. **Test container image** — `testing/Dockerfile` has uv, kubectl, helm, dbt.

5. **pytest-rerunfailures** — `conftest.py:pytest_configure` configures retries for
   infrastructure exceptions (`ConnectionError`, `TimeoutError`, `PollingTimeoutError`).

## What Still Needs Fixing

### Fix 1: Root conftest hardcoded endpoints (6+ failures, 2 lines)

**Problem**: `tests/conftest.py:124-126` — the `compiled_artifacts()` fixture hardcodes:
```python
os.environ["OPENLINEAGE_URL"] = "http://localhost:5100/api/v1/lineage"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4317"
```

This fixture is used by `test_compile_deploy_materialize_e2e.py` (6 tests),
`test_governance_enforcement_e2e.py` (2 tests), `test_multi_product_isolation_e2e.py`
(3 tests), and `test_observability_roundtrip_e2e.py` (1 test). Total: **12+ tests blocked**.

**Fix**: Use `ServiceEndpoint` with env var fallback, matching the pattern already used
in `tests/e2e/conftest.py`:
```python
from testing.fixtures.services import ServiceEndpoint

marquez_url = ServiceEndpoint("marquez").url
os.environ["OPENLINEAGE_URL"] = f"{marquez_url}/api/v1/lineage"
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ServiceEndpoint("otel-collector-grpc").url
```

Also fix error message strings in `test_observability.py` (4 occurrences) and
`test_platform_bootstrap.py` (1 occurrence) that reference `localhost:5100`/`localhost:4317`
in user-facing messages — these should use the resolved endpoint for accurate diagnostics.

### Fix 2: In-cluster test orchestration script (41+ failures eliminated)

**Problem**: No `make test-e2e-cluster` target or orchestration script exists. The
infrastructure is ready (Dockerfile, Job manifests, RBAC) but there's no way to
actually run E2E tests in-cluster.

**Deliverables**:

1. **`testing/ci/test-e2e-cluster.sh`** — orchestration script:
   - Build test runner image: `docker build -t floe-test-runner:latest -f testing/Dockerfile .`
   - Load into Kind: `kind load docker-image floe-test-runner:latest`
   - Delete previous Job (idempotency): `kubectl delete job floe-e2e-test --ignore-not-found -n floe-test`
   - Submit Job: `kubectl apply -f testing/k8s/jobs/test-e2e.yaml -n floe-test`
   - Wait for completion: `kubectl wait --for=condition=complete job/floe-e2e-test -n floe-test --timeout=3600s`
   - Extract results: `kubectl logs job/floe-e2e-test -n floe-test` + `kubectl cp` for JUnit XML
   - Cleanup: delete Job on success

2. **`Makefile` target**: `test-e2e-cluster` calling the script

3. **Job manifest updates**:
   - Ensure PVC `test-artifacts` is created (add PVC manifest if missing)
   - Mount project source (charts/, demo/) via init container or baked into image

### Fix 3: Charts directory access for in-cluster tests (10 files, 5+ failures)

**Problem**: 10 E2E test files reference `charts/` directory via `_find_chart_root()`
or similar patterns. Inside a container, the repo checkout may not include `charts/`.

**Files affected**: `test_helm_workflow.py`, `test_governance.py`, `test_platform_deployment_e2e.py`,
`test_data_pipeline.py`, `test_demo_mode.py`, `test_observability.py`, `test_platform_bootstrap.py`,
`test_compile_deploy_materialize_e2e.py`, `test_schema_evolution.py`, `test_helm_upgrade_e2e.py`

**Fix options** (ranked):

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A (recommended)** | Bake full repo checkout into test image | Simple, no runtime mounts | Image larger (~50MB), needs rebuild on chart changes |
| B | Mount charts via hostPath + Kind extra mounts | No image rebuild | Kind-specific, won't work on GHA without modification |
| C | Skip chart-dependent tests in-cluster | Simplest | Reduces coverage |

**Recommended**: Option A — the `testing/Dockerfile` already does `COPY . /app` for the
full workspace. The issue is that `_find_chart_root()` in `test_governance.py:849-855`
uses `Path(__file__).parent` traversal to find `charts/` relative to the repo root.
Inside the container, `__file__` resolves differently.

The fix: ensure `WORKDIR /app` in the test image and set `project_root` fixture to `/app`.
The `_find_chart_root()` pattern already walks up from `__file__` to find `charts/` — it
just needs the repo structure to be present at the expected relative path.

### Fix 4: Profile isolation (3 failures)

**Problem**: `test_demo_profile_untouched_during_session` fails for all 3 demo products.
This test verifies that E2E test runs don't mutate the on-disk `profiles.yml` files.

**Root cause**: The compilation fixture or dbt invocation writes back to `profiles.yml`.
This is a real bug — compilation should not modify source files.

**Fix**: Investigate whether `compile_pipeline()` or `dbt parse` modifies `profiles.yml`
and make the operation read-only. If dbt requires writing, use a temp directory.

## Approach — Phased

### Phase 1: Fix 1 + Fix 4 (smallest diff, biggest test impact)

- Fix root conftest hardcoded endpoints (2 functional lines + 5 error messages)
- Investigate and fix profile isolation (3 failures)
- **Expected result**: 12+ compilation tests pass, 3 profile tests pass

### Phase 2: Fix 3 + Fix 2 (in-cluster enablement)

- Verify charts directory accessible in test image (may already work)
- Create orchestration script and Makefile target
- Validate full E2E suite runs in-cluster
- **Expected result**: 41+ infrastructure errors eliminated

### Validation

1. Run E2E suite host-based → confirm Fix 1 + Fix 4 reduce failures
2. Run E2E suite in-cluster → confirm all infrastructure errors eliminated
3. Compare host vs in-cluster results → same test outcomes

## Blast Radius

### Modules/files touched

| File | Change | Propagation |
|------|--------|-------------|
| `tests/conftest.py` | Replace 2 hardcoded endpoints with ServiceEndpoint | **Adjacent** — all tests using `compiled_artifacts()` fixture |
| `tests/e2e/test_observability.py` | Fix 4 error message strings | **Local** — cosmetic |
| `tests/e2e/test_platform_bootstrap.py` | Fix 1 error message string | **Local** — cosmetic |
| `testing/ci/test-e2e-cluster.sh` | New file | **Local** — additive |
| `Makefile` | New target `test-e2e-cluster` | **Local** — additive |
| `testing/k8s/` | PVC manifest if needed | **Local** |

### What this design does NOT change

- Host-based `make test-e2e` flow (backward compatible)
- Port-forward scripts, SSH tunnel management
- Production Helm values
- Test assertions (only infrastructure resolution)
- Demo data products or compiled artifacts
- CI pipeline (GitHub Actions) — future work
- K8sRunLauncher config (already done)
- E2E conftest.py ServiceEndpoint usage (already done)

## Risks

| Risk | Mitigation |
|------|-----------|
| ServiceEndpoint import fails in root conftest | Add conditional import with localhost fallback |
| Charts dir not at expected path inside container | Verify `testing/Dockerfile` COPY includes charts/ |
| Profile isolation fix may require dbt behavior change | Investigate before implementing; may need temp dir pattern |
| Job idempotency — stale Jobs block resubmission | Script deletes previous Job before applying |
| PVC may not exist | Script creates PVC or uses emptyDir with kubectl logs extraction |

## WARNs from Critic Review

1. **Charts directory scope**: 10 files reference `charts/`, not just 1. Design now accounts for all 10.
2. **Already-done fixes**: Design revised to clearly separate shipped work from proposed work.
3. **Orchestration script detail**: Job lifecycle (delete → apply → wait → extract) now specified.
4. **Root conftest vs E2E conftest**: The blocker is `tests/conftest.py`, not `tests/e2e/conftest.py`.
