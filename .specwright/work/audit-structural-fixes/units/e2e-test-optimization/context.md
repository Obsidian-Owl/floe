# Context — Unit 3: E2E Test Optimization

baselineCommit: e1dbdb3f64b2fec5574b3c006645173418fc5800

## Summary

Reduce E2E suite runtime from ~73 minutes to ~15 minutes by:
1. Replacing redundant per-test `dbt seed` + `dbt run` with module-scoped fixtures
2. Moving 48 non-E2E tests out of `tests/e2e/` to package-level unit directories

## Key Files

### Must Modify
- `tests/e2e/test_data_pipeline.py` (1163 lines) — refactor to use shared fixtures
- `tests/e2e/conftest.py` — add module-scoped `dbt_pipeline_result` fixture

### Must Move
- `tests/e2e/test_profile_isolation.py` (472 lines) → `packages/floe-dbt/tests/unit/`
- `tests/e2e/test_dbt_e2e_profile.py` (733 lines) → `packages/floe-dbt/tests/unit/`
- `tests/e2e/test_plugin_system.py` (799 lines) → `packages/floe-core/tests/unit/`

### Reference
- `tests/e2e/dbt_utils.py` — `run_dbt()` and `_purge_iceberg_namespace()` helpers

## Current State

### dbt Invocations in test_data_pipeline.py
- 7 `dbt seed` calls at lines: 228, 286, 377, 459, 545, 609, 664, 774, 1087
- 8 `dbt run` calls at lines: 291, 378, 460, 546, 610, 665, 729, 785, 1088
- Parametrized across 3 products (`ALL_PRODUCTS`) = ~24 full cycles

### Test Classification
- `test_profile_isolation.py` — tests file I/O on profiles.yml (no K8s)
- `test_dbt_e2e_profile.py` — tests dbt profile generation (no K8s)
- `test_plugin_system.py` — tests plugin discovery/loading (no K8s)
- Total: ~48 tests adding ~15-20 min to E2E runtime

## Isolation Strategy

- Each product writes to its own Iceberg namespace
- Module-unique namespace suffix prevents cross-module contamination
- Read-only tests share the fixture; mutating tests (incremental merge, schema evolution)
  get their own function-scoped fixture with throwaway namespace
- `yield` + `finally` cleanup purges namespace after module completes

## Gotchas
- `test_data_pipeline.py` has tests for FAILURE paths (bad model, retry) that need
  separate dbt runs — these cannot share the "happy path" fixture
- Moved test files may import from `tests/e2e/conftest.py` — check for dependency on
  E2E-scoped fixtures before moving
- `dbt_utils.py` is in `tests/e2e/` — moved files that import from it need path adjustment
  or the module needs to move to `testing/` shared directory
