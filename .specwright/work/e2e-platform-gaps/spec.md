# Spec: E2E Platform Gaps (Epic 15)

> Testable acceptance criteria for 8 work units. Target: 0 FAILED, 0 ERROR.

## Non-Functional Requirements (ALL Work Units)

| ID | Criterion | Verification |
|----|-----------|-------------|
| NF-1 | All E2E tests run via `make test-e2e` | `make test-e2e` exits 0 |
| NF-2 | Zero `pytest.skip()` in any changed test file | `rg "pytest\.skip\(" tests/e2e/` returns empty |
| NF-3 | No custom test infrastructure beyond Kind cluster | No new Docker images, no sidecar containers in test code |
| NF-4 | Every test function has `@pytest.mark.requirement()` | `uv run python -m testing.traceability --all --threshold 100` passes |
| NF-5 | Final suite result: 0 FAILED, 0 ERROR | `make test-e2e` summary line shows `0 failed, 0 error` |
| NF-6 | All changed Python files pass `mypy --strict` | `uv run mypy --strict <changed_files>` exits 0 |
| NF-7 | All changed Python files pass `ruff check` | `uv run ruff check <changed_files>` exits 0 |
| NF-8 | No `time.sleep()` in test code | `rg "time\.sleep\(" tests/` returns empty |

---

## WU-1: Polaris Bootstrap + MinIO Bucket Reliability

**Root causes**: RC-1, RC-3
**Unblocks**: WU-4, WU-5 (Iceberg tests), WU-8

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU1-AC1 | Bootstrap job verifies catalog existence via `GET /api/management/v1/catalogs/floe-e2e` after creation | Read bootstrap job YAML: verification step exists after POST, uses management API with bearer token, exits 1 on failure |
| WU1-AC2 | Bootstrap job verifies MinIO bucket `floe-iceberg` accessibility via S3 HEAD request or `mc ls` | Read bootstrap job YAML: bucket check exists, exits 1 on failure |
| WU1-AC3 | `wait-for-services.sh` gates on Polaris API catalog existence (not `kubectl wait` on job) | Read script: contains `curl` or equivalent polling `GET /api/management/v1/catalogs/floe-e2e` with token auth, not `kubectl wait --for=condition=complete job/polaris-setup` |
| WU1-AC4 | Token acquisition is factored into a reusable shell function in `testing/ci/` | Read `wait-for-services.sh` or new helper: function `get_polaris_token()` or equivalent exists, used by both wait script and bootstrap verification |
| WU1-AC5 | `test_helm_upgrade_e2e.py` detects and recovers from `pending-upgrade`, `pending-install`, and `failed` Helm release states before attempting upgrade | Read test file: status check exists before upgrade, rollback logic for stuck states |
| WU1-AC6 | Session-scoped fixture in `conftest.py` checks Helm release health before E2E suite starts | Read `conftest.py`: session fixture calls `helm status` and recovers if stuck |
| WU1-AC7 | `values-test.yaml` explicitly includes `floe-iceberg` in MinIO bucket provisioning list | Read `values-test.yaml`: `buckets` list contains `floe-iceberg` |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU1-BC1 | Bootstrap catalog already exists (409 response) | Job treats 409 as success, exits 0 |
| WU1-BC2 | Polaris not ready within 300s | Init container times out, job fails, Helm retries per `backoffLimit` |
| WU1-BC3 | MinIO bucket does not exist | Bootstrap job exits 1, Helm retries |
| WU1-BC4 | Token acquisition fails (bad credentials) | Bootstrap exits 1 with descriptive error to stderr |
| WU1-BC5 | Helm release in `pending-upgrade` state | E2E conftest fixture runs `helm rollback`, logs recovery action |

---

## WU-2: Cube Multi-Arch + Pod Scheduling

**Root cause**: RC-2
**Unblocks**: WU-8

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU2-AC1 | GitHub Actions workflow (nightly.yml) builds multi-arch Cube Store image for `linux/amd64` and `linux/arm64` | Read `nightly.yml`: job with `docker/build-push-action`, `platforms: linux/amd64,linux/arm64`, pushes to `ghcr.io/obsidian-owl/cube-store` |
| WU2-AC2 | `values-test.yaml` enables Cube Store with overridden image repository pointing to multi-arch build | Read `values-test.yaml`: `cube.cubeStore.enabled: true`, `cube.cubeStore.image.repository: ghcr.io/obsidian-owl/cube-store` |
| WU2-AC3 | Cube resource requests in `values-test.yaml` fit within Kind single-node capacity: API 50m/128Mi, Store 100m/256Mi | Read `values-test.yaml`: resource values match or are lower |
| WU2-AC4 | Cube Store StatefulSet template supports `image.repository` and `image.tag` override via values | Read `statefulset-cube-store.yaml`: image field uses `.Values.cubeStore.image.repository` and `.tag` |
| WU2-AC5 | Rollback path exists: if multi-arch image unavailable, `cubeStore.enabled: false` and Cube Store-dependent tests use `@pytest.mark.xfail(reason="ARM64 image pending", strict=False)` | Read values and test files: xfail markers reference ARM64 image |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU2-BC1 | Multi-arch build fails in nightly | Cube Store disabled in test values, xfail markers on dependent tests, other tests unaffected |
| WU2-BC2 | Kind node has insufficient resources for Cube Store | Pod stays Pending; reduced resource requests prevent this |
| WU2-BC3 | Cube Store image tag mismatch | StatefulSet uses explicit tag from values, not `latest` |

---

## WU-3: Dagster 2.x SDK Migration (Full Audit)

**Root causes**: RC-5, RC-11
**Unblocks**: WU-8

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU3-AC1 | `plugins/floe-orchestrator-dagster/pyproject.toml` specifies `dagster>=2.0.0,<3.0.0` | Read `pyproject.toml`: dependency constraint matches |
| WU3-AC2 | `dagster-dbt` and `dagster-dlt` version constraints are compatible with Dagster 2.x (verified via `uv lock` success) | `uv lock` exits 0 with no resolution conflicts |
| WU3-AC3 | All 13 source files in `src/floe_orchestrator_dagster/` pass import verification against Dagster 2.x API | `uv run python -c "import floe_orchestrator_dagster"` succeeds; `uv run pytest plugins/floe-orchestrator-dagster/ -x` passes |
| WU3-AC4 | GraphQL query in `test_compile_deploy_materialize_e2e.py` uses Dagster 2.x schema: `repositoriesOrError` with `RepositoryConnection` (not `repositoryLocationsOrError`) | Read test file lines 180-231: old query names absent, new query names present |
| WU3-AC5 | `health_check_sensor` in `sensors.py` has explicit `job` or `asset_selection` parameter | Read `sensors.py`: `@sensor()` decorator or function call includes target parameter |
| WU3-AC6 | Sensor unit test (`test_health_sensor.py`) validates sensor with correct target parameter | Read test file: test creates sensor with job/asset_selection, evaluates successfully |
| WU3-AC7 | `ConfigurableIOManager` import in `io_manager.py` verified to exist in Dagster 2.x | Import test passes; if moved, import path updated |
| WU3-AC8 | `ConfigurableResource` import in `dbt_resource.py` verified to exist in Dagster 2.x | Import test passes; if moved, import path updated |
| WU3-AC9 | `DagsterDltTranslator` import in `assets/ingestion.py` verified compatible with Dagster 2.x | Import test passes; if API changed, usage updated |
| WU3-AC10 | Full plugin unit test suite passes: `uv run pytest plugins/floe-orchestrator-dagster/ -x` | Exit code 0, 0 failures |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU3-BC1 | `dagster-dbt` not yet compatible with Dagster 2.x | Pin working version combination, document constraint in pyproject.toml comment |
| WU3-BC2 | GraphQL 2.x response shape differs from 1.x beyond field names | Test updated to handle actual 2.x response structure (verified by introspection or docs) |
| WU3-BC3 | Sensor without `job` param silently creates no-op sensor | Test asserts sensor yields `RunRequest` when evaluated, not empty |

---

## WU-4: OTel Pipeline + Label Alignment

**Root cause**: RC-4
**Depends on**: WU-1 (Polaris for full stack)

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU4-AC1 | `test_observability.py` pod label selector uses `app.kubernetes.io/component=otel` (matching chart label in `configmap-otel.yaml:13`) | Read test file: selector string matches chart label exactly |
| WU4-AC2 | OTel Collector config (`configmap-otel.yaml`) includes Jaeger exporter with OTLP gRPC endpoint | Read configmap: `exporters.otlp/jaeger` or equivalent with Jaeger service endpoint |
| WU4-AC3 | `values-test.yaml` enables Jaeger OTLP receiver | Read values: Jaeger receiver configuration present and enabled |
| WU4-AC4 | E2E test verifies trace data flows from OTel Collector to Jaeger: query `GET /api/traces?service=floe-platform` returns at least one trace | Read test: Jaeger API query exists, asserts `data` array is non-empty |
| WU4-AC5 | OTel tracer provider is initialized during E2E test execution (not just production) | Read `conftest.py`: session fixture sets up `TracerProvider` with OTLP exporter pointing to `localhost:4317` |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU4-BC1 | Jaeger not receiving traces | Test fails with descriptive message including Jaeger API response |
| WU4-BC2 | OTel Collector pod not ready | Test waits via polling (no `time.sleep`), fails after timeout |
| WU4-BC3 | No traces with service name `floe-platform` | Test fails, does not fall back to asserting `is not None` on empty response |

---

## WU-5: dbt Demo Product Pipeline

**Root cause**: RC-6
**Depends on**: WU-1 (Iceberg tests only; DuckDB tests are independent)

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU5-AC1 | Each demo product (`customer-360`, `iot-telemetry`, `financial-risk`) has a valid `profiles.yml` with DuckDB target | Read each `demo/*/profiles.yml`: contains `type: duckdb` with valid path |
| WU5-AC2 | DuckDB-only E2E tests pass: `dbt seed` -> `dbt run` -> `dbt test` sequence completes for each demo product | `uv run pytest tests/e2e/test_dbt_lifecycle_e2e.py -x` passes (DuckDB tests) |
| WU5-AC3 | Path resolution from pytest working directory to demo product dbt projects works correctly | Tests use `project_root` fixture to resolve paths, not hardcoded relative paths |
| WU5-AC4 | Tests classified as DuckDB-only vs Iceberg-dependent: each test function has a docstring stating its dependency | Read test files: docstrings on each test state "DuckDB-only" or "Requires Polaris/Iceberg" |
| WU5-AC5 | Iceberg-dependent tests are marked with `@pytest.mark.xfail` until WU-1 is verified, then markers are removed | Read test files: xfail markers present with reason referencing RC-1/WU-1 |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU5-BC1 | dbt seed data missing | Test fails with descriptive error pointing to seed data location |
| WU5-BC2 | DuckDB file locked by another process | Test fails with clear error, not silent hang |
| WU5-BC3 | profiles.yml has wrong target | dbt fails with profile error; test captures and reports |

---

## WU-6: Plugin Registry + Compilation Pipeline

**Root causes**: RC-7, RC-8

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU6-AC1 | `test_plugin_system.py` line 108 uses `len(PluginType)` instead of hardcoded `13` | Read test file: assertion is `assert len(PluginType) == len(PluginType)` replaced with dynamic check, or assertion removed in favor of iterating all enum members |
| WU6-AC2 | `PLUGIN_ABC_MAP` in `test_plugin_system.py` contains entry `PluginType.ALERT_CHANNEL: AlertChannelPlugin` | Read test file: map has 14 entries, ALERT_CHANNEL maps to `AlertChannelPlugin` from `floe_core.plugins.alert_channel` |
| WU6-AC3 | `AlertChannelPlugin` is importable from `floe_core.plugins` package | `uv run python -c "from floe_core.plugins.alert_channel import AlertChannelPlugin"` succeeds |
| WU6-AC4 | Stage 4 (ENFORCE) in `stages.py` produces an `EnforcementResultSummary` from pre-manifest policy checks (plugin instrumentation audit + spec-level policies) | Read `stages.py` lines 320-337: code creates `EnforcementResultSummary` with `passed`, `error_count`, `warning_count`, `policy_types_checked`, `enforcement_level` fields populated |
| WU6-AC5 | `build_artifacts()` call in Stage 6 (`stages.py` line 368) passes `enforcement_result` kwarg | Read `stages.py` line 368: `build_artifacts(... enforcement_result=enforcement_result ...)` |
| WU6-AC6 | `CompiledArtifacts.enforcement_result` is populated (not None) after compilation of any demo product | Unit test: compile `demo/customer-360/floe.yaml`, assert `artifacts.enforcement_result is not None`, assert `artifacts.enforcement_result.passed is True` (warn mode), assert `len(artifacts.enforcement_result.policy_types_checked) > 0` |
| WU6-AC7 | E2E test `test_compiled_artifacts_enforcement` in `test_compile_deploy_materialize_e2e.py` passes (currently xfail with `strict=True`) | Remove xfail marker; test passes: `artifacts.enforcement_result is not None` and `artifacts.enforcement_result.passed is True` |
| WU6-AC8 | Test docstring at `test_plugin_system.py` line 1 updated from "13 plugin types" to "14 plugin types" | Read module docstring: says "14" not "13" |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU6-BC1 | Plugin has no OTel instrumentation | Enforcement produces warning (not error) in warn mode, `passed` is True |
| WU6-BC2 | Governance config missing from spec | Enforcement uses default level (`warn`), still produces result |
| WU6-BC3 | `enforcement_result` field is None in CompiledArtifacts | Test FAILS (not softened to `is not None` check) — enforcement must always run |

---

## WU-7: Secrets Verification + CVE Bumps

**Root causes**: RC-9, RC-10

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU7-AC1 | `bandit -r packages/floe-core/tests/unit/ -ll` reports 0 high-severity findings | Bandit exit code 0, output shows no HIGH or CRITICAL issues |
| WU7-AC2 | Root `pyproject.toml` `[tool.uv]` section contains `constraint-dependencies` list with `diskcache>=5.6.4` and `pillow>=12.1.1` (or later safe versions) | Read `pyproject.toml`: `constraint-dependencies` is a list (not a table), contains both entries |
| WU7-AC3 | `uv lock` succeeds after adding constraint dependencies | `uv lock` exits 0 |
| WU7-AC4 | `uv run pip-audit` or equivalent shows no known CVEs for `diskcache` and `pillow` | Audit output shows these packages at safe versions |
| WU7-AC5 | Syntax is `constraint-dependencies` (list under `[tool.uv]`), NOT `override-dependencies` or `[tool.uv.constraint-dependencies]` table | Read `pyproject.toml`: verify exact syntax matches uv documentation |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU7-BC1 | Bandit flags a false positive | Investigate pattern; if truly false positive, add `# nosec` with justification comment |
| WU7-BC2 | `constraint-dependencies` causes resolution conflict | Investigate which package pins the vulnerable version; escalate if direct dep |
| WU7-BC3 | New CVE disclosed for another transitive dep | Add to `constraint-dependencies` list; do not create separate override mechanism |

---

## WU-8: Polaris Health Check + Final Verification

**Root cause**: RC-1 residual
**Depends on**: All other WUs

### Acceptance Criteria

| ID | Criterion | How We KNOW It Works |
|----|-----------|---------------------|
| WU8-AC1 | `test_platform_bootstrap.py` Polaris health check uses management endpoint `/q/health/ready` on port 8182 (not `/api/catalog/v1/config` on 8181 which requires auth) | Read test file: health URL is `http://localhost:8182/q/health/ready` |
| WU8-AC2 | `conftest.py` Polaris readiness fixture uses management health endpoint | Read conftest: Polaris health check fixture uses port 8182 `/q/health/ready` |
| WU8-AC3 | All previously-xfail tests that now pass have `xfail` markers removed | `rg "xfail" tests/e2e/` — only tests with genuine remaining infrastructure gaps retain xfail |
| WU8-AC4 | Running `pytest --strict-markers tests/e2e/` produces no unexpected xpass warnings | pytest output shows 0 xpass |
| WU8-AC5 | Full E2E suite result: 0 FAILED, 0 ERROR | `make test-e2e` summary: 0 failed, 0 error |
| WU8-AC6 | Every remaining xfail test has a code comment or docstring explaining WHY it's expected to fail, with a reference to a tracking issue or work unit | Read each xfail test: reason string references issue ID or WU |

### Boundary Conditions

| ID | Condition | Expected Behavior |
|----|-----------|------------------|
| WU8-BC1 | Polaris management port (8182) not port-forwarded | Add port-forward to `test-e2e.sh`: `svc/floe-platform-polaris 8182:8182` |
| WU8-BC2 | xfail test unexpectedly passes (xpass) | Remove xfail marker; test is now a real passing test |
| WU8-BC3 | Some tests still fail after all WUs | Investigate root cause; do NOT mark as xfail without tracking issue |

---

## Work Unit Lifecycle

Each work unit follows:
```
/sw-build → /sw-verify → /sw-ship
```

Expected cycle:
```
WU-1: Polaris Bootstrap + MinIO        → /sw-build → /sw-verify → /sw-ship
WU-2: Cube Multi-Arch                  → /sw-build → /sw-verify → /sw-ship
WU-3: Dagster 2.x SDK Migration        → /sw-build → /sw-verify → /sw-ship
WU-4: OTel Pipeline + Labels           → /sw-build → /sw-verify → /sw-ship
WU-5: dbt Demo Product Pipeline        → /sw-build → /sw-verify → /sw-ship
WU-6: Plugin Registry + Pipeline       → /sw-build → /sw-verify → /sw-ship
WU-7: Secrets Verification + CVE       → /sw-build → /sw-verify → /sw-ship
WU-8: Polaris Health + Final Verify    → /sw-build → /sw-verify → /sw-ship
```

## Parallelism

WU-1, WU-2, WU-3, WU-5 (DuckDB), WU-6, WU-7 can all proceed in parallel.
WU-4 waits for WU-1. WU-5 (Iceberg) waits for WU-1. WU-8 waits for all others.
