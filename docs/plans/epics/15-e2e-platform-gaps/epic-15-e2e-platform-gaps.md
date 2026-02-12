# Epic 15: E2E Test Infrastructure & Platform Gaps

> **Audience**: floe platform contributors and maintainers
>
> **Purpose**: Fix the 7 independent root causes behind 61 E2E test failures (41 FAILED + 20 ERROR) discovered during the test hardening audit (Epic 14)

## Summary

The February 2026 E2E test run on branch `audit/test-hardening-wu1` revealed **7 independent root causes** that cascade into 61 failures across 137 collected tests. The failures cluster into three tiers: infrastructure bootstrap (Polaris, Cube, Helm), platform wiring (OTel, Dagster GraphQL, dbt), and code hygiene (plugin registry, secrets, CVEs).

71 tests pass, 5 xfail as expected, and the remaining 61 are real failures that must be fixed.

## Status

- [x] Root cause analysis complete
- [ ] Linear project created
- [ ] Tasks generated
- [ ] Implementation started
- [ ] Tests passing (target: 0 FAILED, 0 ERROR)
- [ ] Complete

**Linear Project**: [Epic 15: E2E Test Infrastructure & Platform Gaps](https://linear.app/obsidianowl/project/epic-15-e2e-test-infrastructure-and-platform-gaps-fee2596b0f75)

**Audit Reference**: `/tmp/floe-e2e-latest.log` (2026-02-12), `test-logs/` pod logs

---

## Root Cause Summary

| RC | Title | Severity | Tests Affected | Category |
|----|-------|----------|----------------|----------|
| RC-1 | Polaris bootstrap — warehouse `floe-e2e` not created | BLOCKER | 15 | Infra |
| RC-2 | Cube pods stuck Pending in Kind cluster | BLOCKER | 9 | Infra |
| RC-3 | Helm release stuck in `pending-upgrade` | BLOCKER | 5 | Infra |
| RC-4 | OTel pipeline — host compilation can't reach K8s collectors | HIGH | 10 | Platform |
| RC-5 | Dagster GraphQL API — `repositoryLocationsOrError` removed | HIGH | 4 | Platform |
| RC-6 | dbt runs fail for demo products | HIGH | 8 | Platform |
| RC-7 | `ALERT_CHANNEL` plugin type not in `PLUGIN_ABC_MAP` | MEDIUM | 4 | Code |
| RC-8 | `compile_pipeline()` produces `governance=None` | MEDIUM | 3 | Code |
| RC-9 | 10 hardcoded secrets in unit test files | MEDIUM | 1 | Hygiene |
| RC-10 | pip-audit CVEs (diskcache, pillow) | MEDIUM | 1 | Hygiene |
| RC-11 | Dagster `SensorDefinition` requires explicit `job` in 2.x | LOW | 1 | Platform |

**Deduplicated**: 7 independent root causes; remaining are cascading failures.

---

## Requirements

### Tier 1: Infrastructure Bootstrap (BLOCKER)

| Requirement ID | Description | Root Cause | Priority |
|----------------|-------------|------------|----------|
| 15-FR-001 | Polaris bootstrap job must create `floe-e2e` warehouse | RC-1 | BLOCKER |
| 15-FR-002 | Cube API and Cube Store pods must schedule in Kind | RC-2 | BLOCKER |
| 15-FR-003 | Helm release must reach `deployed` state before tests run | RC-3 | BLOCKER |
| 15-FR-004 | MinIO `floe-iceberg` bucket must be auto-created by bootstrap | RC-1 | BLOCKER |

### Tier 2: Platform Wiring (HIGH)

| Requirement ID | Description | Root Cause | Priority |
|----------------|-------------|------------|----------|
| 15-FR-005 | OTel traces from compilation must reach Jaeger via port-forward | RC-4 | HIGH |
| 15-FR-006 | OTel Collector pod labels must match test expectations (`app.kubernetes.io/component=opentelemetry-collector`) | RC-4 | HIGH |
| 15-FR-007 | Dagster GraphQL queries must use current API (`repositoriesOrError`, not `repositoryLocationsOrError`) | RC-5 | HIGH |
| 15-FR-008 | `dbt run` must succeed for all 3 demo products (customer-360, iot-telemetry, financial-risk) | RC-6 | HIGH |
| 15-FR-009 | Dagster `SensorDefinition` must provide explicit `job` parameter | RC-11 | LOW |

### Tier 3: Code & Hygiene (MEDIUM)

| Requirement ID | Description | Root Cause | Priority |
|----------------|-------------|------------|----------|
| 15-FR-010 | `PLUGIN_ABC_MAP` must include `ALERT_CHANNEL`; plugin tests must expect 14 types | RC-7 | MEDIUM |
| 15-FR-011 | `compile_pipeline()` must pass `enforcement_result` to `build_artifacts()` (stages.py:368) | RC-8 | MEDIUM |
| 15-FR-012 | `governance` field must be populated in `CompiledArtifacts` for demo specs | RC-8 | MEDIUM |
| 15-FR-013 | Replace hardcoded secrets in 6 unit test files with env vars / fixtures | RC-9 | MEDIUM |
| 15-FR-014 | Update `diskcache` and `pillow` to patched versions (GHSA-w8v5-vhqr-4h9v, GHSA-cfh3-3jmp-rvhc) | RC-10 | MEDIUM |
| 15-FR-015 | Polaris health check endpoint must handle auth (401 on `/api/catalog/v1/config`) | RC-1 | MEDIUM |

---

## Detailed Root Cause Analysis

### RC-1: Polaris Bootstrap — Warehouse `floe-e2e` Not Found

**Error**: `pyiceberg.exceptions.RESTError: NotFoundException: Unable to find warehouse floe-e2e`

**Affected tests** (15): All of `test_data_pipeline.py` (8), `test_schema_evolution.py` (6), `test_multi_product_isolation_e2e.py` (1), plus `test_polaris_catalog_accessible` (1 ERROR).

**Analysis**: The Polaris bootstrap job (`floe-platform-polaris-bootstrap`) runs at Helm install but may fail silently or not create the expected warehouse. The `floe-iceberg` MinIO bucket is also missing — same bootstrap gap.

**Fix direction**: Investigate bootstrap job logs, ensure warehouse + bucket creation is idempotent and verified.

---

### RC-2: Cube Pods Stuck Pending in Kind

**Error**: `resource not ready, name: floe-e2e-cube-api, kind: Deployment, status: InProgress`

**Affected tests** (9): `test_helm_workflow.py` (5 ERROR — fixture-level Helm deploy timeout), `test_platform_deployment_e2e.py` (2), `test_platform_bootstrap.py` (1), `test_plugin_system.py` (1 — Cube health check `MagicMock < float`).

**Analysis**: Cube API and Cube Store pods can't schedule. Likely resource constraints in Kind (CPU/memory limits) or missing image pull. The `MagicMock < float` error in plugin health checks suggests the Cube plugin falls back to a mock when the real service is unavailable.

**Fix direction**: Check Cube resource requests vs Kind node capacity. May need to reduce Cube resource requests for CI or add node resources.

---

### RC-3: Helm Release Stuck in `pending-upgrade`

**Error**: `Helm release status is 'pending-upgrade'`, `another operation (install/upgrade/rollback) is in progress`

**Affected tests** (5): All 4 `test_helm_upgrade_e2e.py` tests + `test_helm_release_deployed`.

**Analysis**: A previous Helm operation didn't complete cleanly. The release is stuck and the upgrade test can't proceed. Revision 1 has status `failed`.

**Fix direction**: Test setup should detect stuck releases and reset them. Consider `helm rollback` or `helm uninstall --wait` + fresh install in test fixture.

---

### RC-4: OTel Pipeline Not Producing Data

**Errors**: No traces in Jaeger, no jobs in Marquez, no OTel Collector pods found with expected labels, compilation produces no log output.

**Affected tests** (10): All 8 `test_observability.py` tests, `test_observability_roundtrip_e2e.py` (1), `test_demo_mode.py::test_jaeger_traces_for_all_products` (1).

**Analysis**: Multiple issues:
1. **Label mismatch**: Tests look for `app.kubernetes.io/component=opentelemetry-collector` but actual pods use different labels
2. **Host-to-K8s gap**: Compilation runs on host with OTel SDK pointed at `localhost:4317` — requires port-forward to be active AND the SDK to actually emit spans during test execution
3. **Marquez**: No OpenLineage events because no pipeline actually runs (no code locations loaded)

**Fix direction**: Fix pod label selectors, ensure OTel SDK is configured with the port-forwarded endpoint during test runs, verify collector→Jaeger forwarding.

---

### RC-5: Dagster GraphQL API Breaking Change

**Error**: `Cannot query field 'repositoryLocationsOrError' on type 'Query'. Did you mean 'repositoriesOrError'?`

**Affected tests** (4): `test_dagster_code_locations_loaded`, `test_dagster_assets_visible` (cascading), `test_three_products_visible_in_dagster`, `test_jaeger_traces_for_all_products` (cascading).

**Analysis**: Dagster 2.x removed `repositoryLocationsOrError` and `RepositoryLocationConnection`. The correct fields are now `repositoriesOrError` and `RepositoryConnection`.

**Fix direction**: Update GraphQL queries in test files and any shared helpers.

---

### RC-6: dbt Runs Fail for Demo Products

**Error**: `dbt run --project-dir demo/iot-telemetry` returns exit status 1.

**Affected tests** (8): `test_data_pipeline.py` (6 — pipeline_execution_order, dbt_tests_pass, data_quality_checks for iot-telemetry and financial-risk), `test_dbt_lifecycle_e2e.py` (2 — test_dbt_run, test_dbt_test).

**Analysis**: dbt can't connect to Iceberg tables. Cascades from RC-1 (Polaris warehouse missing) — dbt profiles reference the Polaris catalog which doesn't have the `floe-e2e` warehouse. May also be missing `profiles.yml` generation.

**Fix direction**: Fixing RC-1 should unblock most of these. Verify dbt profiles point to correct catalog endpoint.

---

### RC-7: ALERT_CHANNEL Plugin Type Missing

**Error**: `Expected 13 plugin types, found 14. Missing: {PluginType.ALERT_CHANNEL}`

**Affected tests** (4): All `test_plugin_system.py` tests.

**Analysis**: `PluginType` enum was extended with `ALERT_CHANNEL` but `PLUGIN_ABC_MAP` and test expectations still reference 13 types.

**Fix direction**: Add `ALERT_CHANNEL` ABC to `PLUGIN_ABC_MAP`, update test assertions from 13 to 14.

---

### RC-8: governance=None in CompiledArtifacts

**Error**: `artifacts.governance is not None` assertion fails — `governance=None` in compiled output.

**Affected tests** (3): `test_security_event_logging`, `test_governance_enforcement_via_compilation`, and related xfails.

**Analysis**: Known pipeline bug — `compile_pipeline()` runs the ENFORCE stage but doesn't pass `enforcement_result` to `build_artifacts()` (stages.py:368). The `governance` field also isn't populated.

**Fix direction**: Fix `build_artifacts()` in stages.py to accept and include both `enforcement_result` and `governance` config.

---

### RC-9: Hardcoded Secrets in Unit Tests

**Error**: `Found 10 hardcoded secrets` across 6 test files.

**Files**:
- `packages/floe-core/tests/unit/oci/test_auth.py` (3)
- `packages/floe-core/tests/unit/oci/test_pull_golden.py` (1)
- `packages/floe-core/tests/unit/oci/test_client.py` (1)
- `packages/floe-core/tests/unit/lineage/test_transport.py` (1)
- `packages/floe-core/tests/unit/lineage/test_emitter.py` (1)
- `packages/floe-core/tests/unit/governance/test_secrets.py` (4)

**Fix direction**: Replace with `os.environ.get()` fallbacks or test fixtures.

---

### RC-10: Dependency CVEs

| Package | Version | Advisory | Fix Version |
|---------|---------|----------|-------------|
| `diskcache` | 5.6.3 | GHSA-w8v5-vhqr-4h9v | TBD |
| `pillow` | 11.3.0 | GHSA-cfh3-3jmp-rvhc | 12.1.1 |

**Fix direction**: Bump versions in `pyproject.toml` / `uv.lock`.

---

### RC-11: Dagster SensorDefinition API Change

**Error**: `DagsterInvalidDefinitionError: No job was provided to SensorDefinition.`

**Analysis**: Dagster 2.x requires `job` parameter for `SensorDefinition`. Test constructs a sensor without it.

**Fix direction**: Add `job` parameter to sensor definition in test.

---

## Cascade Map

```
RC-1 (Polaris bootstrap) ──► RC-6 (dbt fails — no catalog)
                           ──► RC-12 (MinIO bucket missing)
                           ──► RC-13 (Polaris 401)

RC-2 (Cube pods)          ──► RC-3 (Helm stuck — timeout waiting for Cube)

RC-5 (Dagster GraphQL)    ──► test_dagster_assets_visible (no locations = no assets)
                           ──► test_demo_mode (no locations = no products)
                           ──► RC-4 partial (no pipeline runs = no traces)
```

**Fixing RC-1 + RC-2 would resolve ~29 of 61 failures (48%).**
**Fixing RC-1 + RC-2 + RC-5 would resolve ~41 of 61 failures (67%).**

---

## Implementation Order

```
Phase 1 (BLOCKERS — unblocks 48% of failures):
  15-FR-001  Polaris bootstrap + warehouse creation
  15-FR-002  Cube pod scheduling in Kind
  15-FR-003  Helm release state management
  15-FR-004  MinIO bucket auto-creation

Phase 2 (HIGH — unblocks 85% of failures):
  15-FR-007  Dagster GraphQL API migration
  15-FR-005  OTel collector label fix + port-forward wiring
  15-FR-006  OTel Collector label alignment
  15-FR-008  dbt demo product profiles

Phase 3 (MEDIUM — remaining 15%):
  15-FR-010  ALERT_CHANNEL plugin registration
  15-FR-011  enforcement_result pipeline fix (stages.py:368)
  15-FR-012  governance field population
  15-FR-013  Hardcoded secrets cleanup
  15-FR-014  Dependency CVE bumps

Phase 4 (LOW):
  15-FR-009  SensorDefinition job parameter
  15-FR-015  Polaris auth for health check
```

---

## Non-Functional Requirements

| NF | Description |
|----|-------------|
| NF-1 | All E2E tests run via `make test-e2e` |
| NF-2 | Zero `pytest.skip()` — tests FAIL when infra missing |
| NF-3 | No custom test infrastructure — use real platform deployment |
| NF-4 | All tests have `@pytest.mark.requirement()` traceability |
| NF-5 | Target: 0 FAILED, 0 ERROR in E2E suite |

---

## Architecture References

- **Test Hardening Audit**: `.specwright/work/test-hardening-audit/evidence/`
- **E2E Test Log**: `/tmp/floe-e2e-latest.log` (2026-02-12)
- **Pod Logs**: `test-logs/` directory
- **Pipeline Bug**: `packages/floe-core/src/floe_core/stages.py:368`
- **Dagster GraphQL**: Migration from `repositoryLocationsOrError` to `repositoriesOrError`
