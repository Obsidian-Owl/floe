# Test Quality Gate Report

**Work Unit**: e2e-test-stability
**Timestamp**: 2026-03-31T11:25:00Z
**Verdict**: WARN

## Changed Test Files

Only 2 test files changed (assertion modifications):
- `tests/e2e/test_compile_deploy_materialize_e2e.py:239`
- `tests/e2e/test_dbt_e2e_profile.py:550-551`

## Findings

### INFO: Assertion widening in test_compile_deploy_materialize_e2e.py:239
- **What**: Path assertion widened from `startswith("/tmp/")` to also accept `:memory:`
- **Justification**: Conftest at `tests/e2e/conftest.py:1132` now generates `:memory:` profiles. Test docstring updated. Surrounding assertions (type, threads, memory_limit) unchanged and strong.
- **Mutation resistance**: PASS — five simultaneous field checks prevent hardcoded returns.

### WARN: Assertion widening in test_dbt_e2e_profile.py:551
- **What**: Demo profile isolation test now accepts `:memory:` paths, but demo profiles never use `:memory:` (they use `/tmp/*.duckdb`).
- **Impact**: If E2E profile leaks into demo directory with `:memory:` path but without `attach` block, the overwrite goes undetected.
- **Compensating control**: The `attach` check at line 556-558 catches the current E2E profile shape (E2E profiles always include `attach`).
- **Risk**: LOW — fragile to future E2E profile changes that omit `attach`.
- **Recommended action**: Consider reverting to `startswith("/tmp/")` for this specific test since demo source profiles always use `/tmp/` paths.

## Dimensions

| Dimension | Status |
|-----------|--------|
| Assertion strength | WARN (one test weakened) |
| Boundary coverage | PASS |
| Mock discipline | PASS (E2E tests, no mocks) |
| Error paths | PASS |
| Mutation resistance | PASS |
