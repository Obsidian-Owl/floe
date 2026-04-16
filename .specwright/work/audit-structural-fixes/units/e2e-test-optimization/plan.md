# Plan — Unit 3: E2E Test Optimization

## Task Breakdown

### Task 1: Add module-scoped dbt fixtures to conftest

**AC**: AC-1
**Files**:
- `tests/e2e/conftest.py` — add `dbt_pipeline_result` fixture

**Signatures**:
```python
@pytest.fixture(scope="module")
def dbt_pipeline_result(
    request: pytest.FixtureRequest,
    dbt_e2e_profile: Path,
) -> Generator[tuple[str, Path], None, None]: ...
```

**Tests**: Fixture itself is tested via the E2E tests that use it.

### Task 2: Refactor test_data_pipeline.py to use shared fixtures

**AC**: AC-1, AC-2, AC-4
**Files**:
- `tests/e2e/test_data_pipeline.py` — replace inline dbt calls with fixture usage

**Change map**:
- Read-only test classes: add `dbt_pipeline_result` as fixture parameter, remove inline
  `run_dbt(["seed"], ...)` and `run_dbt(["run"], ...)` calls
- Mutating test classes: create function-scoped fixture variants
- Parametrize at class level: `@pytest.mark.parametrize("dbt_pipeline_result", ALL_PRODUCTS, indirect=True)`
- Preserve all existing assertions

**Tests**: All existing test assertions must pass with same expectations.

### Task 3: Move non-E2E tests to package-level unit directories

**AC**: AC-3
**Files**:
- `tests/e2e/test_profile_isolation.py` → `packages/floe-dbt/tests/unit/test_profile_isolation.py`
- `tests/e2e/test_dbt_e2e_profile.py` → `packages/floe-dbt/tests/unit/test_dbt_e2e_profile.py`
- `tests/e2e/test_plugin_system.py` → `packages/floe-core/tests/unit/test_plugin_system.py`

**Change map**:
- Update imports (remove E2E conftest dependencies)
- Add conftest.py in destination if needed
- Remove files from `tests/e2e/`
- Verify `make test-unit` passes with the moved tests

**Tests**: `make test-unit` includes the moved tests and they pass.

## File Change Map

| File | Task | Change Type |
|------|------|-------------|
| `tests/e2e/conftest.py` | 1 | Add ~30 lines (fixture) |
| `tests/e2e/test_data_pipeline.py` | 2 | Refactor ~1163 lines (remove inline dbt) |
| `tests/e2e/test_profile_isolation.py` | 3 | Move to floe-dbt/tests/unit/ |
| `tests/e2e/test_dbt_e2e_profile.py` | 3 | Move to floe-dbt/tests/unit/ |
| `tests/e2e/test_plugin_system.py` | 3 | Move to floe-core/tests/unit/ |

## Dependency Order

Task 1 → Task 2 (fixture needed before refactoring). Task 3 independent.
