# Wiring Gate Evidence

**Branch**: `feat/e2e-production-fixes`
**Date**: 2026-03-27
**Gate**: wiring
**Status**: PASS

---

## 1. Git Diff Review

Changed files (15 total):
- `.gitignore` — un-ignore `demo/*/target/manifest.json`
- `Makefile` — add `check-manifests` target
- `charts/floe-jobs/templates/cronjob.yaml` — structured dbt args from values
- `charts/floe-jobs/templates/job.yaml` — structured dbt args from values
- `charts/floe-jobs/values-test.yaml` — rename `jobDefaults` -> `defaults`
- `charts/floe-jobs/values.yaml` — decompose `dbt.args` into `profilesDir`/`projectDir`/`target`/`debug`
- `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` — parameterise `activeDeadlineSeconds`
- `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` — add custom activeDeadlineSeconds test
- `charts/floe-platform/values-test.yaml` — set `activeDeadlineSeconds: 600`
- `charts/floe-platform/values.yaml` — add `preUpgradeCleanup.activeDeadlineSeconds` field
- `demo/customer-360/target/manifest.json` — committed dbt manifest
- `demo/financial-risk/target/manifest.json` — committed dbt manifest
- `demo/iot-telemetry/target/manifest.json` — committed dbt manifest
- `pyproject.toml` — add GHSA-gc5v-m9x4-r6x2 to pip-audit ignore list
- `tests/e2e/test_observability.py` — use Marquez events API for START/COMPLETE validation

---

## 2. Import Consistency

No new Python modules or moved code. The only Python change is in `tests/e2e/test_observability.py` which adds a `marquez_client.get()` call using the already-imported `marquez_client` fixture. No import changes needed.

**Verdict**: PASS

---

## 3. Values.yaml <-> Template Consistency

### floe-jobs chart

| values.yaml key | Template consumption | Status |
|---|---|---|
| `defaults.*` (renamed from `jobDefaults`) | `job.yaml`, `cronjob.yaml` — 60+ references to `.Values.defaults.*` | PASS |
| `dbt.profilesDir` | `job.yaml:60`, `cronjob.yaml:70` — `{{ .Values.dbt.profilesDir \| default "/etc/dbt" }}` | PASS |
| `dbt.projectDir` | `job.yaml:62`, `cronjob.yaml:72` — `{{ .Values.dbt.projectDir \| default "/dbt" }}` | PASS |
| `dbt.target` | `job.yaml:63-65`, `cronjob.yaml:73-75` — conditional `--target` | PASS |
| `dbt.debug` | `job.yaml:67-68`, `cronjob.yaml:77-78` — conditional `--debug` | PASS |
| `dbt.args` (escape hatch) | `job.yaml:53-55`, `cronjob.yaml:63-65` — `if .Values.dbt.args` takes priority | PASS |

Helm template rendering verified:
```
helm template test-jobs charts/floe-jobs -f charts/floe-jobs/values-test.yaml
```
Produces correct args: `["run", "--profiles-dir", "/dbt/profiles", "--project-dir", "/dbt", "--target", "test", "--debug"]`

### floe-platform chart

| values.yaml key | Template consumption | Status |
|---|---|---|
| `postgresql.preUpgradeCleanup.activeDeadlineSeconds` | `pre-upgrade-statefulset-cleanup.yaml:74` — `{{ .Values.postgresql.preUpgradeCleanup.activeDeadlineSeconds \| default 300 }}` | PASS |

Helm template rendering verified:
```
helm template test-platform charts/floe-platform -f charts/floe-platform/values-test.yaml
```
Produces `activeDeadlineSeconds: 600` in hook Job.

### values-test.yaml key alignment

`charts/floe-jobs/values-test.yaml`:
- `defaults` key: PASS (matches `values.yaml` key, renamed from `jobDefaults` in this PR)
- `dbt.projectDir`, `dbt.profilesDir`, `dbt.target`, `dbt.debug`: PASS (match new values.yaml keys)

Pre-existing orphan keys in values-test.yaml not consumed by templates:
`dlt`, `cronJobs`, `iceberg`, `podSecurityContext`, `securityContext` -- these exist only as documentation/future-use overrides and are harmless (Helm ignores unknown values).

`charts/floe-platform/values-test.yaml`:
- `postgresql.preUpgradeCleanup.activeDeadlineSeconds: 600`: PASS (matches new values.yaml key)

**Verdict**: PASS

---

## 4. Test <-> Code Alignment

### Helm unit tests (floe-platform)
- `hook-pre-upgrade_test.yaml` — existing test renamed to "should set default activeDeadlineSeconds" + new test "should allow custom activeDeadlineSeconds via values"
- Both tests target `pre-upgrade-statefulset-cleanup.yaml:74` which was changed from hardcoded `300` to parameterised value
- All 143 helm unit tests pass

### E2E observability test
- `test_observability.py` lines 1011-1043 — changed from checking run states (which collapse per-model START into terminal COMPLETED) to querying Marquez events API (`/api/v1/events/lineage`) for individual `eventType` fields
- This tests the actual code path changed in the parent branch (`feat/per-model-lineage-emission`) where per-model START/COMPLETE events are emitted synchronously
- Fallback to run-state checking if events API unavailable (older Marquez)
- Variable scoping is safe: `event_types` only referenced when `events_response.status_code == 200` (Python conditional expression is lazy)

**Verdict**: PASS

---

## 5. Config Consistency

### .gitignore <-> Makefile
- `.gitignore` un-ignores `demo/*/target/manifest.json` using the `!dir/`, `dir/*`, `!dir/file` pattern
- `Makefile` `check-manifests` target uses `git diff --exit-code demo/*/target/manifest.json` to detect staleness
- Three manifest files are tracked by git: `demo/{customer-360,financial-risk,iot-telemetry}/target/manifest.json`

### pyproject.toml
- New vulnerability `GHSA-gc5v-m9x4-r6x2` added to `ignore_vulnerabilities` with documented rationale (requests pinned by datacontract-cli)

**Verdict**: PASS

---

## Findings Summary

- [INFO] `charts/floe-jobs/values-test.yaml` contains 5 orphan top-level keys (`dlt`, `cronJobs`, `iceberg`, `podSecurityContext`, `securityContext`) not defined in `values.yaml` and not consumed by any template. Pre-existing, harmless, but could be cleaned up for clarity.
- [INFO] `charts/floe-jobs` has no helm unit tests (`helm unittest` reports 0 test suites). The dbt args decomposition is verified by template rendering but has no automated regression test.
- [INFO] The E2E test change relies on Marquez `/api/v1/events/lineage` endpoint availability. Fallback to run-state checking is implemented for older Marquez versions.

---

## Verification Commands Run

```bash
git diff main...HEAD --stat                    # 15 files changed
helm template test-jobs charts/floe-jobs -f charts/floe-jobs/values-test.yaml  # Renders correctly
helm template test-platform charts/floe-platform -f charts/floe-platform/values-test.yaml  # Renders correctly
helm unittest charts/floe-platform             # 143 passed, 0 failed
helm unittest charts/floe-jobs                 # 0 tests (no test suites)
git ls-files demo/*/target/manifest.json       # 3 files tracked
```

---

GATE: wiring
STATUS: PASS
FINDINGS:
- [INFO] values-test.yaml for floe-jobs has 5 orphan keys (dlt, cronJobs, iceberg, podSecurityContext, securityContext) not in values.yaml — pre-existing, harmless
- [INFO] floe-jobs chart has no helm unit tests for the new dbt args decomposition — verified by template rendering only
- [INFO] E2E observability test has graceful fallback for older Marquez without events API
