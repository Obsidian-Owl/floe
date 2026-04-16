# Plan: E2E Structural Fixes

## Architecture Decisions

### AD-1: ServiceEndpoint import strategy

Import `ServiceEndpoint` from `testing.fixtures.services` in the root conftest.
The root conftest already uses `from floe_core.compilation.stages import compile_pipeline`,
so importing from `testing.fixtures.services` is consistent.

Conditional import with `localhost` fallback if `testing` package is not available
(protects unit test runs where `testing/` may not be on `PYTHONPATH`).

### AD-2: Orchestration script structure

Shell script following existing patterns in `testing/ci/test-e2e.sh`. Uses `set -euo pipefail`,
`[[` conditionals, stderr for errors. Wraps the Job lifecycle: build → load → delete → apply → wait → extract → report.

### AD-3: Profile isolation verification approach

The `dbt_e2e_profile` fixture already writes to `generated_profiles/` and the
`test_demo_profile_untouched_during_session` test verifies isolation. The `compiled_artifacts()`
fixture calls `compile_pipeline()` which is pure computation (no disk writes to demo/).
Investigation needed: determine if the 3 profile test failures are cascade failures
from compilation errors (AC-1 fix may resolve them) or genuine profile mutation.

## Task Breakdown

### Task 1: Replace hardcoded endpoints in root conftest

**AC**: AC-1 (conditions 1-4)

**Files changed**:

| File | Change |
|------|--------|
| `tests/conftest.py` | Replace lines 124, 126 with `ServiceEndpoint` calls |

**Approach**:
- Add conditional import of `ServiceEndpoint` with `localhost` fallback
- Replace `"http://localhost:5100/api/v1/lineage"` with `f"{ServiceEndpoint('marquez').url}/api/v1/lineage"`
- Replace `"http://localhost:4317"` with `ServiceEndpoint("otel-collector-grpc").url`
- Preserve env var save/restore pattern (lines 118-143)

**Signatures**:

```python
# At top of compiled_artifacts() or module level:
try:
    from testing.fixtures.services import ServiceEndpoint
    _HAS_SERVICE_ENDPOINT = True
except ImportError:
    _HAS_SERVICE_ENDPOINT = False
```

### Task 2: Fix error message strings referencing localhost

**AC**: AC-1 (condition 5)

**Files changed**:

| File | Change |
|------|--------|
| `tests/e2e/test_observability.py` | 4 error messages: `localhost:5100` → resolved endpoint |
| `tests/e2e/test_platform_bootstrap.py` | 2 error messages: `localhost:4317` → resolved endpoint |

**Approach**:
- Import `ServiceEndpoint` (already available in E2E conftest context)
- Replace hardcoded localhost references in error/diagnostic strings

### Task 3: Create in-cluster orchestration script

**AC**: AC-2 (conditions 1-9)

**Files changed**:

| File | Change |
|------|--------|
| `testing/ci/test-e2e-cluster.sh` | New file — Job lifecycle orchestration |
| `Makefile` | New `test-e2e-cluster` target |

**Approach**:

Script structure:
```
#!/usr/bin/env bash
set -euo pipefail

# 1. Build test runner image
# 2. Load into Kind
# 3. Delete previous Job (idempotent)
# 4. Apply Job manifest
# 5. Wait for completion (timeout 3600s)
# 6. Extract logs and JUnit XML
# 7. Report pass/fail
# 8. Cleanup
```

Makefile target:
```makefile
.PHONY: test-e2e-cluster
test-e2e-cluster: ## Run E2E tests in-cluster (Kind Job)
	@./testing/ci/test-e2e-cluster.sh
```

### Task 4: Verify charts directory access in-cluster

**AC**: AC-3 (conditions 1-4)

**Files changed**:

| File | Change |
|------|--------|
| (none — verification task) | Confirm `_find_chart_root()` works with `WORKDIR=/app` |

**Approach**:
- Verify `testing/Dockerfile` line 70 (`COPY charts/ ./charts/`) is present
- Verify `_find_repo_root()` in `test_governance.py` finds `pyproject.toml` via
  `Path(__file__).parent` traversal — inside container, `__file__` is `/app/tests/e2e/test_governance.py`,
  parent traversal reaches `/app/` which has `pyproject.toml`
- If traversal fails: add `PROJECT_ROOT` env var fallback to `_find_repo_root()`
- Run chart-dependent test inside container to confirm

### Task 5: Investigate and verify profile isolation

**AC**: AC-4 (conditions 1-4)

**Files changed**:

| File | Change |
|------|--------|
| (investigation — may require no changes) | |

**Approach**:
- Run `test_demo_profile_untouched_during_session` in isolation to determine if it
  passes when compilation endpoints are correctly resolved (after Task 1)
- If it passes: AC-4 was a cascade failure, no further action
- If it fails: investigate `compile_pipeline()` for disk writes to `demo/*/profiles.yml`
- If writes found: redirect to temp directory

## File Change Map

| File | Tasks | Type |
|------|-------|------|
| `tests/conftest.py` | T1 | Modify (2 lines + import) |
| `tests/e2e/test_observability.py` | T2 | Modify (4 error strings) |
| `tests/e2e/test_platform_bootstrap.py` | T2 | Modify (2 error strings) |
| `testing/ci/test-e2e-cluster.sh` | T3 | New file |
| `Makefile` | T3 | Modify (add target) |
| `tests/e2e/test_governance.py` | T4 | Modify (if needed) |

## Task Order

T1 → T2 → T5 → T3 → T4

Rationale: T1 fixes the root cause for compilation tests. T2 is cosmetic and fast.
T5 must follow T1 to determine if profile failures are cascading. T3 creates the
in-cluster runner. T4 verifies charts access, which can only be confirmed after
T3 provides the in-cluster execution environment.

## As-Built Notes

### Deviations from plan

- **T4**: No code changes needed. Verification confirmed `_find_chart_root()` works
  as-is inside the container. `PROJECT_ROOT` fallback was not required.
- **T5**: No code changes needed. Confirmed `compile_pipeline()` has zero disk writes.
  Profile isolation failures are cascade from compilation endpoint errors (T1 fix).
- **Marquez port**: `ServiceEndpoint("marquez")` defaults to port 5000 (actual service
  port). Host-based runs set `MARQUEZ_PORT=5100` via `test-e2e.sh` (macOS AirPlay
  avoidance). The ImportError fallback uses 5100 to match previous behavior.

### Actual file changes

| File | Change | Commit |
|------|--------|--------|
| `tests/conftest.py` | ServiceEndpoint import + 2 endpoint lines | T1: 47886a7 |
| `tests/e2e/test_observability.py` | 4 error message strings | T2: 55dae25 |
| `tests/e2e/test_platform_bootstrap.py` | 2 error message strings | T2: 55dae25 |
| `testing/ci/test-e2e-cluster.sh` | New file (148 lines) | T3: 5195800 |
| `Makefile` | Added `test-e2e-cluster` target + help text | T3: 5195800 |
| `tests/e2e/test_governance.py` | No changes (verified working) | T4: N/A |
