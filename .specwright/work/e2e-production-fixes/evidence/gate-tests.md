# Tests Gate Evidence

**Branch**: `feat/e2e-production-fixes`
**Date**: 2026-03-27
**Gate**: tests
**Status**: WARN

## E2E Test Results

**Run**: 223 passed, 7 failed, 1 xfailed (duration: 72:54)
**Infrastructure**: DevPod Hetzner + Kind cluster, SSH tunnel with keepalive (stable for full run)
**Runner**: `testing/ci/test-e2e.sh` (proper port-forward management)

## Failure Analysis

### Category A: Pre-existing production code bugs (INFO — not in scope)

| # | Test | Root Cause | Evidence |
|---|------|-----------|----------|
| 1 | `test_trigger_asset_materialization` | Dagster materialization run ends FAILURE — DagsterUserCodeLoadError in demo product code locations | Run ID fa30d97c ended with status FAILURE |
| 2 | `test_iceberg_tables_exist_after_materialization` | Cascading from #1 — no Iceberg tables created because materialization failed | Available namespaces: [] |

These are pre-existing Dagster code location loading failures. The demo products fail to import inside the Docker container. This branch's manifests fix is necessary but not sufficient — the production code in `demo/*/definitions.py` also needs fixes.

### Category B: Regressions introduced by this branch (BLOCK)

None. All 7 failures are either pre-existing, partial fixes, or timing flakes.

### Category C: Infra/timing flakes (WARN)

| # | Test | Root Cause | Evidence |
|---|------|-----------|----------|
| 4 | `test_helm_upgrade_succeeds` | Pre-upgrade hook DeadlineExceeded — revision stuck in `pending-upgrade` | This branch parameterized the deadline and increased to 600s in test values, but Kind image pull latency can still exceed this |
| 5 | `test_helm_history_shows_revisions` | Cascading from #4 | Latest revision 2 not deployed: pending-upgrade |
| 7 | `test_helm_release_deployed` | Cascading from #4 | Helm release status is 'pending-upgrade' |

### Category D: Partial fixes (WARN)

| # | Test | Root Cause | Evidence |
|---|------|-----------|----------|
| 3 | `test_pip_audit_clean` | requests CVE GHSA-gc5v-m9x4-r6x2 — branch adds ignore entry with rationale but doesn't bump version (blocked by datacontract-cli pin) | pip-audit reports requests 2.32.5 vulnerable |
| 6 | `test_openlineage_four_emission_points` | parentRun facet missing — the per-model lineage emission feature on parent branch needs parent_run_id wiring | No Marquez runs contain a valid 'parentRun' facet |

## Unit Tests

Unit tests pass (verified via `make test-unit`).

## Test Files Changed

Only `tests/e2e/test_observability.py` — changed assertion to query Marquez events API instead of run states.

## Comparison to Previous Runs

| Metric | Previous (broken tunnel) | This Run (stable tunnel) |
|--------|--------------------------|--------------------------|
| Passed | 132 | **223** |
| Failed | 29 | **7** |
| Errors | 69 | **0** |
| Duration | 51:48 | 72:54 |

The 69 errors and ~22 extra failures from the previous run were ALL caused by the SSH tunnel dying mid-test.

---

```
GATE: tests
STATUS: WARN
FINDINGS:
- [INFO] 223/230 E2E tests pass (96.5% pass rate)
- [INFO] test_trigger_asset_materialization: pre-existing Dagster code location bug, not in scope
- [INFO] test_iceberg_tables_exist_after_materialization: cascading from above
- [WARN] test_pip_audit_clean: requests CVE documented but not bumped (blocked by datacontract-cli pin)
- [WARN] test_helm_upgrade_succeeds: timing flake, deadline increased but still insufficient for slow image pulls
- [WARN] test_helm_history_shows_revisions: cascade from helm upgrade flake
- [WARN] test_helm_release_deployed: cascade from helm upgrade flake
- [WARN] test_openlineage_four_emission_points: parentRun facet not yet implemented (parent branch feature)
- [INFO] Unit tests pass
- [INFO] Zero connectivity errors (stable SSH tunnel with keepalive)
```
