# Build Gate Evidence

**Branch**: `feat/e2e-production-fixes`
**Date**: 2026-03-27
**Verdict**: WARN

## 1. Lint Check (ruff)

**Status**: PASS

```
$ uv run ruff check .
All checks passed!
```

No lint errors in any files.

## 2. Type Check (mypy --strict)

**Status**: PASS

Changed Python files:
- `tests/e2e/test_observability.py`

```
$ uv run mypy --strict tests/e2e/test_observability.py
Success: no issues found in 1 source file
```

## 3. Helm Template Validation

**Status**: PASS

Both charts render without errors:
- `helm template test-release ./charts/floe-platform -f ./charts/floe-platform/values-test.yaml` -- OK
- `helm template test-release ./charts/floe-jobs -f ./charts/floe-jobs/values-test.yaml` -- OK

## 4. Helm Unit Tests

### floe-platform

**Status**: WARN (uncommitted local change causes failure; committed code passes)

The committed code on `feat/e2e-production-fixes` passes all 143 Helm unit tests (verified by stashing uncommitted changes and re-running).

An uncommitted local modification to `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` adds `list` and `watch` verbs to the RBAC Role but does not update the corresponding test assertion in `charts/floe-platform/tests/hook-pre-upgrade_test.yaml`. This causes test `"should grant get and delete on statefulsets"` to fail.

**Action required**: If the verbs change is intended for this branch, update the test to expect `["get", "list", "watch", "delete"]` and commit both files together. If not intended, discard the local change.

### floe-jobs

**Status**: PASS

```
Charts:      1 passed, 1 total
Test Suites: 0 passed, 0 total
Tests:       0 passed, 0 total
```

## Uncommitted Changes Detected

The following files have uncommitted modifications:
- `charts/floe-platform/templates/hooks/pre-upgrade-statefulset-cleanup.yaml` (verbs expanded)
- `demo/customer-360/target/manifest.json`
- `demo/financial-risk/target/manifest.json`
- `demo/iot-telemetry/target/manifest.json`

These are NOT part of the branch commits and should be reviewed before any further commits.

---

## Summary

| Check | Status |
|-------|--------|
| Lint (ruff) | PASS |
| Type check (mypy --strict) | PASS |
| Helm template (floe-platform) | PASS |
| Helm template (floe-jobs) | PASS |
| Helm unittest (floe-platform) | WARN (committed code passes; uncommitted change breaks test) |
| Helm unittest (floe-jobs) | PASS |
