# Plan: flux-test-fixtures

**Unit**: 2 of 3
**Parent**: flux-gitops-implementation

## Task Breakdown

### Task 1: Create testing/fixtures/flux.py with flux_suspended fixture

**Files:**
- CREATE `testing/fixtures/flux.py` — `flux_suspended` fixture + helper functions

**Acceptance criteria covered:** AC-1, AC-2, AC-7, AC-8

**Approach:**
- Module structure: `is_flux_managed()` helper, `suspend_helmrelease()`, `resume_helmrelease()`, `flux_suspended` fixture
- `is_flux_managed(name, namespace)` → bool via `kubectl get helmrelease` returncode
- `flux_suspended` uses `request.addfinalizer()` (not try/finally) per D10
- All subprocess calls: `capture_output=True, text=True`, log failures via structlog
- No Flux Python imports — CLI-only interaction
- Tests: unit tests for graceful degradation (mock subprocess), integration test for real suspend/resume

### Task 2: Add crash recovery and smoke check to conftest.py

**Files:**
- MODIFY `tests/e2e/conftest.py` — Add suspended-check at session start, add Flux controller smoke check

**Acceptance criteria covered:** AC-3, AC-4

**Approach:**
- Add `_recover_suspended_helmreleases()` function called before `helm_release_health()`
- Add `_check_flux_controllers()` to infrastructure smoke check (after existing checks)
- Both functions check for Flux existence first (graceful degradation)
- Smoke check: `kubectl get pods -n flux-system -l app={controller}` with jsonpath
- Tests: integration test with real cluster, unit test mocking subprocess

### Task 3: Wire flux_suspended into helm_upgrade tests and update helm.py

**Files:**
- MODIFY `tests/e2e/test_helm_upgrade_e2e.py` — Add `flux_suspended` fixture parameter to destructive tests
- MODIFY `testing/fixtures/helm.py` — Add Flux delegation path to `recover_stuck_helm_release()`

**Acceptance criteria covered:** AC-5, AC-6

**Approach:**
- `test_helm_upgrade_e2e.py`: add `flux_suspended` as a fixture parameter to test functions that call helm directly
- `helm.py`: add Flux check at top of `recover_stuck_helm_release()` — if managed, `flux reconcile --with-source` and return early
- Import `is_flux_managed` from `testing.fixtures.flux`
- Tests: integration test verifying Flux delegation path

## File Change Map

| File | Action | Lines Changed (est.) |
|------|--------|---------------------|
| `testing/fixtures/flux.py` | CREATE | ~120 |
| `tests/e2e/conftest.py` | MODIFY | +45 |
| `tests/e2e/test_helm_upgrade_e2e.py` | MODIFY | +5 |
| `testing/fixtures/helm.py` | MODIFY | +20 |

## Dependencies

- Unit 1 (flux-kind-install) must be complete — Flux controllers and HelmRelease CRDs must exist in the cluster for integration tests

## Risks

- conftest.py is 1469 lines — changes must be surgical and well-placed
- test_helm_upgrade_e2e.py fixture dependencies must not break existing test parametrization
- helm.py is shared infrastructure — Flux path must not break non-Flux environments

## As-Built Notes

### Deviations from Plan

1. **Task 1**: Used `logging` (stdlib) instead of `structlog` — matches existing `testing/fixtures/` convention. `flux_suspended` is a plain function (not `@pytest.fixture` decorated) to allow direct invocation in tests; pytest 9 blocks direct calls to fixture-decorated functions.

2. **Task 2**: `_recover_suspended_flux()` is a plain function, not directly a fixture. A thin wrapper `_recover_suspended_flux_session()` is the actual `@pytest.fixture(scope="session", autouse=True)`. `helm_release_health` depends on the wrapper via parameter `_recover_suspended_flux_session: None`. The structural test's regex matches `"_recover_suspended_flux"` as a substring of the wrapper parameter name.

3. **Task 3**: `recover_stuck_helm_release()` uses `subprocess.run` directly (not `helm_runner`) for kubectl and flux commands, as `helm_runner` is only for helm CLI. `--with-source` was dropped per spec revision (WARN-13). `flux_suspended` import in test_helm_upgrade_e2e.py requires `# noqa: F401` and `# noqa: F811` due to ruff's fixture import pattern detection.

### Test Counts

| Task | Tests Written | Tests Passing |
|------|--------------|---------------|
| Task 1 | 44 | 44 |
| Task 2 | 32 | 32 |
| Task 3 | 27 | 27 |
| **Total** | **103** | **103** |

### Files Changed (Actual)

| File | Action | Lines Changed |
|------|--------|--------------|
| `testing/fixtures/flux.py` | CREATE | 172 |
| `tests/unit/test_flux_fixtures.py` | CREATE | ~550 |
| `tests/e2e/conftest.py` | MODIFY | +98 |
| `tests/unit/test_flux_conftest.py` | CREATE | ~1000 |
| `tests/e2e/test_helm_upgrade_e2e.py` | MODIFY | +3 |
| `testing/fixtures/helm.py` | MODIFY | +25 |
| `tests/unit/test_helm_upgrade_flux.py` | CREATE | ~350 |
| `tests/unit/test_helm_flux_delegation.py` | CREATE | ~850 |
