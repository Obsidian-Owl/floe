# Spec Compliance Gate: e2e-production-fixes

**Date**: 2026-03-27
**Branch**: feat/e2e-production-fixes
**Reviewer**: Specwright Reviewer Agent

---

## Unit 1: Commit dbt Manifests

### AC-1: Manifest files are committed to git — MET
- **Evidence**: All three files exist and are tracked in git:
  - `demo/customer-360/target/manifest.json` (587KB)
  - `demo/iot-telemetry/target/manifest.json` (634KB)
  - `demo/financial-risk/target/manifest.json` (610KB)
- Each contains valid JSON with a `"nodes"` key (verified via `python3 -c "import json; ..."`)

### AC-2: .gitignore exception allows manifest tracking — MET
- **Evidence**: `.gitignore` diff adds three rules:
  - `!demo/*/target/` (un-ignore directory)
  - `demo/*/target/*` (re-ignore contents)
  - `!demo/*/target/manifest.json` (allow manifest)
- This ensures `target/run_results.json` etc. remain ignored

### AC-3: Docker image contains manifest files — MET
- **Evidence**: `docker/dagster-demo/Dockerfile` lines 148-150 copy entire demo directories:
  - `COPY demo/customer-360/ /app/demo/customer_360/`
  - `COPY demo/iot-telemetry/ /app/demo/iot_telemetry/`
  - `COPY demo/financial-risk/ /app/demo/financial_risk/`
- Root `.dockerignore` does NOT exclude `target/` directories
- With manifests committed to git, the directory COPY includes them implicitly
- Note: No explicit `COPY` for manifests was added — the existing directory COPY is sufficient

### AC-4: CI staleness gate detects drift — MET
- **Evidence**: `Makefile` adds `check-manifests` target (line ~347):
  - Runs `git diff --exit-code demo/*/target/manifest.json`
  - Exits 1 with clear error message if manifests are stale
  - Errors redirect to stderr (`>&2`)

### AC-5: E2E tests pass (cascading validation) — NOT VERIFIABLE
- **Evidence**: E2E tests require a running Kind cluster with full platform stack
- Cannot be verified in this review session (no Kind cluster available)
- The code changes are correct and E2E tests would need to be run separately

---

## Unit 2: OpenLineage Test Assertion Fix

### AC-1: Test queries Marquez events API for event types — MET
- **Evidence**: `tests/e2e/test_observability.py` line 1017:
  - `events_response = marquez_client.get("/api/v1/events/lineage", params={"limit": 100})`
  - Line 1019: `events = events_response.json().get("events", [])`
  - Line 1020: `event_types = {e.get("eventType", "").upper() for e in events if e.get("eventType")}`
  - Line 1021: `has_start = "START" in event_types`
  - Line 1022: `has_complete = "COMPLETE" in event_types`

### AC-2: Fallback to run-state check if events API unavailable — MET
- **Evidence**: `tests/e2e/test_observability.py` lines 1023-1026:
  - `else:` block falls back to original `run_states` check when status != 200
  - Preserves backward compatibility with older Marquez versions

### AC-3: Assertion is at least as strong as the original — MET
- **Evidence**: The new check queries actual event types (START, COMPLETE) instead of
  inferring from run states (RUNNING, NEW). This is strictly stronger because:
  - Run states can show COMPLETED without START ever being observed (back-to-back emission)
  - Events API shows individual OpenLineage events with their `eventType` field
  - Error message updated to include `event_types_display` (line 1035)
  - No assertion removed or weakened

---

## Unit 3: Dependency Bump + Helm Hook Deadline

### AC-1: requests upgraded to >=2.33.0 — NOT MET
- **Evidence**: `pyproject.toml` line 26 still declares `"requests>=2.31"`
- The vulnerability GHSA-gc5v-m9x4-r6x2 was added to `ignore_vulnerabilities` instead
- Comment explains: "Fix version 2.33.0 is blocked by datacontract-cli which pins requests<2.33"
- **Assessment**: The spec says `"requests>=2.33.0"` but the implementation chose to
  ignore the CVE instead of bumping. This is a valid engineering decision (documented
  with rationale) but does NOT meet the literal spec criterion.

### AC-3: Hook deadline is configurable via values — MET
- **Evidence**:
  - Template: `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` line 74:
    `activeDeadlineSeconds: {{ .Values.postgresql.preUpgradeCleanup.activeDeadlineSeconds | default 300 }}`
  - `values.yaml` documents parameter under `postgresql.preUpgradeCleanup` with default 300
  - `values-test.yaml` sets `activeDeadlineSeconds: 600` with comment about CI/Kind latency

### AC-4: Helm unit tests updated — MET
- **Evidence**: `charts/floe-platform/tests/hook-pre-upgrade_test.yaml` adds two tests:
  - "should set default activeDeadlineSeconds on hook Job" — asserts 300
  - "should allow custom activeDeadlineSeconds via values" — sets 600, asserts 600
- **Note**: `helm unittest charts/floe-platform` shows 1 test failure, but it is a
  PRE-EXISTING issue (RBAC verbs mismatch in "should grant get and delete on statefulsets")
  not introduced by this branch. The branch only changed `activeDeadlineSeconds`.

---

## Unit 4: dbt Jobs Template Fix

### AC-1: Template constructs args from individual values — MET
- **Evidence**: `charts/floe-jobs/templates/job.yaml` diff shows:
  - `{{- if .Values.dbt.args }}` for override path
  - `{{- else }}` block constructs args from `profilesDir`, `projectDir`, `target`, `debug`
  - Default args render as: `["run", "--profiles-dir", "/etc/dbt", "--project-dir", "/dbt"]`
  - Verified via `helm template` output

### AC-2: dbt.args override takes precedence — MET
- **Evidence**: Template uses `{{- if .Values.dbt.args }}` as the first branch,
  rendering `dbt.args` verbatim when set. The `else` block only activates when
  `dbt.args` is NOT set.

### AC-3: values.yaml uses structured values instead of hardcoded args — MET
- **Evidence**: `charts/floe-jobs/values.yaml` lines 92-100:
  - `args:` is commented out (escape hatch documented)
  - `profilesDir: /etc/dbt` and `projectDir: /dbt` added
  - `target` and `debug` documented as optional

### AC-4: values-test.yaml key mismatch fixed — MET
- **Evidence**: `charts/floe-jobs/values-test.yaml` diff shows `jobDefaults:` renamed to `defaults:`
  matching the schema in `values.yaml`

### AC-5: Both job.yaml and cronjob.yaml templates updated — MET
- **Evidence**: `charts/floe-jobs/templates/cronjob.yaml` contains identical args
  construction logic as `job.yaml` (verified in diff)

### AC-6: Helm unit tests validate args construction — NOT MET
- **Evidence**: No helm unit test files exist in `charts/floe-jobs/tests/`
  (only `templates/tests/test-job.yaml` which is a Helm test hook, not a helm-unittest file)
- The spec requires test cases for default values, custom profilesDir/projectDir,
  dbt.args override, and dbt.target flag

---

## Build Verification

- **Unit tests**: 8840 passed, 1 skipped, 19 warnings (coverage 87.48%) — PASS
- **Helm template render**: `helm template test charts/floe-jobs --set dbt.enabled=true` renders correctly
- **Helm unittest (floe-platform)**: 1 pre-existing failure (RBAC verbs), not introduced by this branch

---

## Summary

| Unit | AC | Status | Notes |
|------|----|--------|-------|
| 1 | AC-1 | MET | All three manifests committed with valid JSON |
| 1 | AC-2 | MET | .gitignore exception correctly structured |
| 1 | AC-3 | MET | Existing COPY includes manifests implicitly |
| 1 | AC-4 | MET | check-manifests Makefile target added |
| 1 | AC-5 | N/A | Requires Kind cluster for E2E verification |
| 2 | AC-1 | MET | Events API query at line 1017 |
| 2 | AC-2 | MET | Fallback at lines 1023-1026 |
| 2 | AC-3 | MET | Stronger check, no assertions weakened |
| 3 | AC-1 | NOT MET | requests still >=2.31, CVE ignored instead |
| 3 | AC-3 | MET | Configurable via values with default 300 |
| 3 | AC-4 | MET | Two test cases for default and custom deadline |
| 4 | AC-1 | MET | Args constructed from structured values |
| 4 | AC-2 | MET | dbt.args override takes precedence |
| 4 | AC-3 | MET | Structured values in values.yaml |
| 4 | AC-4 | MET | jobDefaults -> defaults key fix |
| 4 | AC-5 | MET | Both job.yaml and cronjob.yaml updated |
| 4 | AC-6 | NOT MET | No helm unit tests for floe-jobs args |

