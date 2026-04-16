# Spec — Unit 3: E2E Test Optimization

## Overview

Reduce E2E suite runtime from ~73 minutes to ~15 minutes by replacing redundant
dbt invocations with module-scoped fixtures and moving non-E2E tests to unit directories.

## Acceptance Criteria

### AC-1: Module-scoped dbt fixtures replace per-test seed/run

A `dbt_pipeline_result` fixture in `tests/e2e/conftest.py` MUST run `dbt seed` +
`dbt run` once per product per test module, shared by all read-only tests.

**Verifiable conditions:**

1. `dbt_pipeline_result` fixture is `scope="module"`.
2. Fixture runs `dbt seed` followed by `dbt run` for the parametrized product.
3. Fixture uses a module-unique Iceberg namespace suffix to prevent cross-module pollution.
4. Fixture yields and cleans up namespace in `finally` block.
5. Tests that previously called `run_dbt(["seed"], ...)` inline now use the fixture.
6. Total `dbt seed` invocations in **read-only** test methods reduced from 7+ to 0
   (all handled by fixture). Mutating tests retain their own calls per AC-2.
7. Total `dbt run` invocations for read-only tests reduced from 8+ to 0 (fixture handles).

### AC-2: Mutating tests use function-scoped fixtures

Tests that MUTATE table state (incremental merge, schema evolution, failure injection)
MUST use function-scoped fixtures with throwaway namespaces, NOT the shared module fixture.

**Verifiable conditions:**

1. `test_incremental_merge_behavior` uses a function-scoped fixture (own namespace).
2. `test_pipeline_failure_recording` and `test_pipeline_retry_from_failure` use function-scoped fixtures.
3. Mutating tests do not affect read-only tests within the same module.
4. All existing test assertions are preserved — no assertion weakening.

### AC-3: Non-E2E tests relocated to package-level unit directories

Tests that do NOT require K8s infrastructure MUST be moved from `tests/e2e/` to
appropriate package-level `tests/unit/` directories.

**Verifiable conditions:**

1. ~~`test_profile_isolation.py` moved to `packages/floe-dbt/tests/unit/`.~~ (descoped — depends on E2E conftest fixtures)
2. ~~`test_dbt_e2e_profile.py` moved to `packages/floe-dbt/tests/unit/`.~~ (descoped — depends on E2E conftest fixtures)
3. `test_plugin_system.py` moved to `packages/floe-core/tests/unit/plugins/`.
4. Moved tests pass in `make test-unit` (no K8s dependency).
5. Moved tests have correct imports (no broken imports from E2E conftest).
6. `tests/e2e/` no longer contains moved files.
7. No test assertions weakened or removed.

### AC-4: E2E suite runtime reduction

The E2E test suite MUST complete significantly faster due to reduced dbt cycles
and fewer tests.

**Verifiable conditions:**

1. `test_data_pipeline.py` has ≤3 `dbt seed` invocations in test method bodies (mutating tests only).
2. `test_data_pipeline.py` has 0 `dbt run` invocations in read-only test methods (via fixture).
3. 10 non-E2E tests (`test_plugin_system.py`) relocated from the E2E suite.
4. `grep -c "run_dbt\(\[.seed.\]"` returns 0 in **read-only** test methods (mutating tests retain own calls per AC-2).

## WARNs from Design Review

1. Failure-path tests (bad model, retry) need their own dbt invocations — they cannot
   share the happy-path fixture. These are function-scoped by nature.
2. `dbt_utils.py` may need to move to `testing/` if relocated tests import from it.
   Assess during implementation.
