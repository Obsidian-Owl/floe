# Plan: E2E Platform Gaps (Epic 15)

> Implementation plan with task breakdown, file change map, and architecture decisions.

## Architecture Decisions

### AD-1: Polaris API Verification (not kubectl wait)

Bootstrap jobs have `hook-delete-policy: before-hook-creation,hook-succeeded` — successful
jobs are deleted before `kubectl wait` can observe them. Gate on the Polaris management
API directly: `GET /api/management/v1/catalogs/floe-e2e`.

### AD-2: Tests Align to Chart Labels

Chart label `app.kubernetes.io/component: otel` is source of truth for deployed infrastructure.
Tests align to chart labels, not the other direction. This prevents chart changes that
would affect all environments.

### AD-3: Inline Pre-Manifest Enforcement

Stage 4 (ENFORCE) cannot run full post-dbt enforcement because dbt manifest doesn't exist yet.
Implement minimal pre-manifest enforcement: plugin instrumentation audit + spec-level policy
checks. Capture as `EnforcementResultSummary` and pass to `build_artifacts()`.

### AD-4: constraint-dependencies for CVE Bumps

Use `constraint-dependencies` (list under `[tool.uv]`) for transitive dependency CVE bumps.
This sets minimum version floors without forcing exact resolution. Do NOT use
`override-dependencies` or table syntax.

### AD-5: Dagster 2.x Full Audit

All 13 source files in floe-orchestrator-dagster must be audited for Dagster 2.x compatibility.
Not just GraphQL queries and sensors — every import must be verified.

---

## WU-1: Polaris Bootstrap + MinIO Bucket Reliability

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T1 | Add catalog verification step to bootstrap job (GET management API after POST) | `charts/floe-platform/templates/job-polaris-bootstrap.yaml` | WU1-AC1 |
| T2 | Add MinIO bucket verification to bootstrap job | `charts/floe-platform/templates/job-polaris-bootstrap.yaml` | WU1-AC2 |
| T3 | Factor token acquisition into reusable shell helper | `testing/ci/polaris-auth.sh` (new) | WU1-AC4 |
| T4 | Replace `kubectl wait` with Polaris API readiness check in wait-for-services.sh | `testing/ci/wait-for-services.sh` | WU1-AC3 |
| T5 | Add `pending-upgrade` detection + rollback to Helm upgrade test | `tests/e2e/test_helm_upgrade_e2e.py` | WU1-AC5 |
| T6 | Add session-scoped Helm health check fixture to conftest | `tests/e2e/conftest.py` | WU1-AC6 |
| T7 | Ensure `floe-iceberg` bucket in values-test.yaml MinIO provisioning | `charts/floe-platform/values-test.yaml` | WU1-AC7 |

### File Change Map

```
charts/floe-platform/templates/job-polaris-bootstrap.yaml  [EDIT] T1, T2
charts/floe-platform/values-test.yaml                      [EDIT] T7
testing/ci/polaris-auth.sh                                 [NEW]  T3
testing/ci/wait-for-services.sh                            [EDIT] T4
tests/e2e/test_helm_upgrade_e2e.py                         [EDIT] T5
tests/e2e/conftest.py                                      [EDIT] T6
```

### Commit Strategy

1. `feat(helm): harden polaris bootstrap with API verification` (T1, T2, T7)
2. `feat(ci): add polaris API readiness gate to wait-for-services` (T3, T4)
3. `fix(e2e): add helm stuck release recovery` (T5, T6)

---

## WU-2: Cube Multi-Arch + Pod Scheduling

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T8 | Add multi-arch Cube Store build job to nightly.yml | `.github/workflows/nightly.yml` | WU2-AC1 |
| T9 | Add image override support to Cube Store StatefulSet template | `charts/floe-platform/charts/cube/templates/statefulset-cube-store.yaml` | WU2-AC4 |
| T10 | Configure Cube Store in values-test.yaml: enable, image override, resource tuning | `charts/floe-platform/values-test.yaml` | WU2-AC2, WU2-AC3 |
| T11 | Add rollback xfail markers on Cube Store-dependent tests (if image unavailable) | `tests/e2e/test_platform_deployment_e2e.py` or relevant | WU2-AC5 |

### File Change Map

```
.github/workflows/nightly.yml                                          [EDIT] T8
charts/floe-platform/charts/cube/templates/statefulset-cube-store.yaml [EDIT] T9
charts/floe-platform/values-test.yaml                                  [EDIT] T10
tests/e2e/test_platform_deployment_e2e.py                              [EDIT] T11
```

### Commit Strategy

1. `feat(ci): add multi-arch cube store build to nightly` (T8)
2. `feat(helm): enable cube store with image override and resource tuning` (T9, T10)
3. `test(e2e): add cube store rollback xfail markers` (T11)

---

## WU-3: Dagster 2.x SDK Migration (Full Audit)

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T12 | Bump dagster SDK constraint to `>=2.0.0,<3.0.0` | `plugins/floe-orchestrator-dagster/pyproject.toml` | WU3-AC1 |
| T13 | Verify dagster-dbt and dagster-dlt compatibility; update constraints if needed | `plugins/floe-orchestrator-dagster/pyproject.toml` | WU3-AC2 |
| T14 | Run `uv lock` and resolve transitive dependency conflicts | `uv.lock` | WU3-AC2 |
| T15 | Audit all 13 source files for Dagster 2.x import compatibility | All 13 files in `src/floe_orchestrator_dagster/` | WU3-AC3, WU3-AC7, WU3-AC8, WU3-AC9 |
| T16 | Migrate GraphQL queries in E2E test: `repositoriesOrError` / `RepositoryConnection` | `tests/e2e/test_compile_deploy_materialize_e2e.py` | WU3-AC4 |
| T17 | Fix sensor: add explicit `job` or `asset_selection` parameter | `plugins/floe-orchestrator-dagster/src/.../sensors.py` | WU3-AC5 |
| T18 | Fix sensor unit test to match new sensor signature | `plugins/floe-orchestrator-dagster/tests/unit/test_health_sensor.py` | WU3-AC6 |
| T19 | Run full plugin unit test suite and fix remaining failures | All plugin test files | WU3-AC10 |

### File Change Map

```
plugins/floe-orchestrator-dagster/pyproject.toml                [EDIT] T12, T13
uv.lock                                                        [REGEN] T14
plugins/floe-orchestrator-dagster/src/.../plugin.py             [AUDIT/EDIT] T15
plugins/floe-orchestrator-dagster/src/.../io_manager.py         [AUDIT/EDIT] T15
plugins/floe-orchestrator-dagster/src/.../resources/dbt_resource.py  [AUDIT/EDIT] T15
plugins/floe-orchestrator-dagster/src/.../assets/ingestion.py   [AUDIT/EDIT] T15
plugins/floe-orchestrator-dagster/src/.../sensors.py            [EDIT] T17
plugins/floe-orchestrator-dagster/src/.../tracing.py            [AUDIT] T15
plugins/floe-orchestrator-dagster/src/.../assets/semantic_sync.py    [AUDIT] T15
plugins/floe-orchestrator-dagster/src/.../resources/ingestion.py     [AUDIT] T15
plugins/floe-orchestrator-dagster/src/.../resources/iceberg.py       [AUDIT] T15
plugins/floe-orchestrator-dagster/src/.../resources/semantic.py      [AUDIT] T15
plugins/floe-orchestrator-dagster/src/.../resources/__init__.py      [AUDIT] T15
plugins/floe-orchestrator-dagster/src/.../assets/__init__.py         [AUDIT] T15
tests/e2e/test_compile_deploy_materialize_e2e.py                [EDIT] T16
plugins/floe-orchestrator-dagster/tests/unit/test_health_sensor.py   [EDIT] T18
```

### Commit Strategy

1. `feat(dagster): bump SDK to 2.x, resolve dependencies` (T12, T13, T14)
2. `refactor(dagster): audit and fix all 2.x import compatibility` (T15)
3. `fix(dagster): add sensor job target, fix GraphQL queries` (T16, T17, T18)
4. `test(dagster): fix remaining plugin unit tests for 2.x` (T19)

---

## WU-4: OTel Pipeline + Label Alignment

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T20 | Fix pod label selector in test_observability.py: `component=otel` | `tests/e2e/test_observability.py` | WU4-AC1 |
| T21 | Verify/add Jaeger exporter config in OTel Collector configmap | `charts/floe-platform/templates/configmap-otel.yaml` | WU4-AC2 |
| T22 | Verify/enable Jaeger OTLP receiver in values-test.yaml | `charts/floe-platform/values-test.yaml` | WU4-AC3 |
| T23 | Add or fix trace roundtrip verification test (OTel -> Jaeger API query) | `tests/e2e/test_observability.py` or `test_observability_roundtrip_e2e.py` | WU4-AC4 |
| T24 | Ensure OTel tracer provider initialized in E2E conftest | `tests/e2e/conftest.py` | WU4-AC5 |

### File Change Map

```
tests/e2e/test_observability.py                        [EDIT] T20, T23
charts/floe-platform/templates/configmap-otel.yaml     [EDIT] T21
charts/floe-platform/values-test.yaml                  [EDIT] T22
tests/e2e/conftest.py                                  [EDIT] T24
tests/e2e/test_observability_roundtrip_e2e.py          [EDIT] T23
```

### Commit Strategy

1. `fix(helm): ensure OTel collector exports to Jaeger` (T21, T22)
2. `fix(e2e): align OTel label selector and add tracer provider setup` (T20, T24)
3. `test(e2e): fix trace roundtrip verification` (T23)

---

## WU-5: dbt Demo Product Pipeline

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T25 | Audit each dbt test: classify as DuckDB-only or Iceberg-dependent | `tests/e2e/test_data_pipeline.py`, `tests/e2e/test_dbt_lifecycle_e2e.py` | WU5-AC4 |
| T26 | Verify each demo product has valid DuckDB profiles.yml | `demo/*/profiles.yml` | WU5-AC1 |
| T27 | Fix path resolution in DuckDB-only dbt E2E tests | `tests/e2e/test_dbt_lifecycle_e2e.py`, `tests/e2e/test_data_pipeline.py` | WU5-AC3 |
| T28 | Fix dbt invocation sequence: seed -> run -> test | Test files | WU5-AC2 |
| T29 | Mark Iceberg-dependent tests with xfail (until WU-1 verified) | Test files | WU5-AC5 |

### File Change Map

```
demo/customer-360/profiles.yml       [VERIFY/EDIT] T26
demo/iot-telemetry/profiles.yml      [VERIFY/EDIT] T26
demo/financial-risk/profiles.yml     [VERIFY/EDIT] T26
tests/e2e/test_dbt_lifecycle_e2e.py  [EDIT] T25, T27, T28, T29
tests/e2e/test_data_pipeline.py      [EDIT] T25, T27, T28, T29
```

### Commit Strategy

1. `fix(demo): verify dbt profiles and fix path resolution` (T26, T27)
2. `fix(e2e): fix dbt lifecycle test sequence and classify dependencies` (T25, T28, T29)

---

## WU-6: Plugin Registry + Compilation Pipeline

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T30 | Replace hardcoded `13` with `len(PluginType)` in plugin count assertion | `tests/e2e/test_plugin_system.py` | WU6-AC1 |
| T31 | Add `ALERT_CHANNEL: AlertChannelPlugin` to PLUGIN_ABC_MAP | `tests/e2e/test_plugin_system.py` | WU6-AC2 |
| T32 | Verify AlertChannelPlugin importable from floe_core.plugins | Package imports | WU6-AC3 |
| T33 | Update test_plugin_system.py module docstring: "14 plugin types" | `tests/e2e/test_plugin_system.py` | WU6-AC8 |
| T34 | Implement inline pre-manifest enforcement in Stage 4 (stages.py) | `packages/floe-core/src/floe_core/compilation/stages.py` | WU6-AC4 |
| T35 | Pass enforcement_result to build_artifacts() in Stage 6 | `packages/floe-core/src/floe_core/compilation/stages.py` | WU6-AC5 |
| T36 | Add unit test: compilation produces non-None enforcement_result | `packages/floe-core/tests/unit/test_compilation_enforcement.py` (new or existing) | WU6-AC6 |
| T37 | Remove xfail marker from test_compiled_artifacts_enforcement E2E test | `tests/e2e/test_compile_deploy_materialize_e2e.py` | WU6-AC7 |

### File Change Map

```
tests/e2e/test_plugin_system.py                                  [EDIT] T30, T31, T33
packages/floe-core/src/floe_core/compilation/stages.py           [EDIT] T34, T35
tests/e2e/test_compile_deploy_materialize_e2e.py                  [EDIT] T37
packages/floe-core/tests/unit/test_compilation_enforcement.py     [NEW or EDIT] T36
```

### Commit Strategy

1. `fix(core): implement inline enforcement in compilation Stage 4` (T34, T35)
2. `test(core): add enforcement result compilation test` (T36)
3. `fix(e2e): update plugin count to 14, add ALERT_CHANNEL to ABC map` (T30, T31, T32, T33)
4. `test(e2e): remove enforcement xfail, validate enforcement result` (T37)

---

## WU-7: Secrets Verification + CVE Bumps

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T38 | Run bandit on identified test files, verify clean | `packages/floe-core/tests/unit/` (6 files) | WU7-AC1 |
| T39 | Add constraint-dependencies to root pyproject.toml | `pyproject.toml` | WU7-AC2, WU7-AC5 |
| T40 | Run `uv lock` to regenerate lock file | `uv.lock` | WU7-AC3 |
| T41 | Verify CVE resolution via pip-audit or uv audit | N/A (verification only) | WU7-AC4 |

### File Change Map

```
pyproject.toml  [EDIT] T39
uv.lock         [REGEN] T40
```

### Commit Strategy

1. `fix(security): add constraint-dependencies for CVE bumps` (T39, T40)
2. Verification tasks T38, T41 produce no file changes (audit-only)

---

## WU-8: Polaris Health Check + Final Verification

### Tasks

| # | Task | Files | AC |
|---|------|-------|----|
| T42 | Change Polaris health check to `/q/health/ready` on port 8182 in test_platform_bootstrap.py | `tests/e2e/test_platform_bootstrap.py` | WU8-AC1 |
| T43 | Update conftest.py Polaris readiness fixture to use management endpoint | `tests/e2e/conftest.py` | WU8-AC2 |
| T44 | Add port-forward for Polaris management port 8182 to test-e2e.sh (if missing) | `testing/ci/test-e2e.sh` | WU8-BC1 |
| T45 | Audit all xfail markers: remove from tests that now pass | All E2E test files | WU8-AC3 |
| T46 | Run `pytest --strict-markers` to verify no xpass | N/A (verification) | WU8-AC4 |
| T47 | Full E2E suite run: verify 0 FAILED, 0 ERROR | N/A (verification) | WU8-AC5 |
| T48 | Ensure all remaining xfail tests have justification in docstring + tracking reference | E2E test files | WU8-AC6 |

### File Change Map

```
tests/e2e/test_platform_bootstrap.py  [EDIT] T42
tests/e2e/conftest.py                 [EDIT] T43
testing/ci/test-e2e.sh                [EDIT] T44
tests/e2e/*.py                        [AUDIT/EDIT] T45, T48
```

### Commit Strategy

1. `fix(e2e): use Polaris management health endpoint` (T42, T43, T44)
2. `fix(e2e): remove resolved xfail markers, document remaining` (T45, T48)
3. Final verification (T46, T47) produces no commits — it's the acceptance gate

---

## Dependency Order

```
Phase 1 (parallel):
  WU-1  ────────┐
  WU-2  ────────┤
  WU-3  ────────┤
  WU-5 (DuckDB) ┤
  WU-6  ────────┤
  WU-7  ────────┘

Phase 2 (after WU-1):
  WU-4  ────────┐
  WU-5 (Iceberg)┘

Phase 3 (after all):
  WU-8 (final verification)
```

## Total Task Count

| WU | Tasks | New Files |
|----|-------|-----------|
| WU-1 | 7 (T1-T7) | 1 (`polaris-auth.sh`) |
| WU-2 | 4 (T8-T11) | 0 |
| WU-3 | 8 (T12-T19) | 0 |
| WU-4 | 5 (T20-T24) | 0 |
| WU-5 | 5 (T25-T29) | 0 |
| WU-6 | 8 (T30-T37) | 0-1 (enforcement test) |
| WU-7 | 4 (T38-T41) | 0 |
| WU-8 | 7 (T42-T48) | 0 |
| **Total** | **48** | **1-2** |

## Risk Mitigations

| Risk | Mitigation | Fallback |
|------|-----------|----------|
| Dagster 2.x breaks imports | Full audit of all 13 files in T15 | Pin working version combo, document constraint |
| dagster-dbt incompatible | Check PyPI before bumping (T13) | Pin `dagster-dbt<next_breaking` |
| Multi-arch build fails | Nightly-only build (T8) | Disable Cube Store + xfail (T11) |
| Bootstrap race condition | API verification, not job status (T4) | N/A — this IS the mitigation |
| OTel traces not visible | Explicit tracer provider in conftest (T24) | Check collector config, verify exporter chain |
