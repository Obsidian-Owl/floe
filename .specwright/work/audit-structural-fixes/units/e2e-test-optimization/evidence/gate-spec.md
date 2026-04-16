# Gate: Spec Compliance

**Status**: PASS
**Timestamp**: 2026-04-05T10:30:00Z

## AC-1: Module-scoped dbt fixtures (7 conditions)

| # | Condition | Status |
|---|-----------|--------|
| 1 | scope="module" | MET |
| 2 | runs seed then run | MET |
| 3 | unique namespace suffix | MET |
| 4 | yields + try/finally cleanup | MET |
| 5 | read-only tests use fixture | MET |
| 6 | seed invocations in read-only methods = 0 | MET |
| 7 | run invocations for read-only = 0 | MET |

## AC-2: Mutating tests use function-scoped fixtures (4 conditions)

| # | Condition | Status |
|---|-----------|--------|
| 1 | incremental_merge own calls | MET |
| 2 | failure/retry own calls | MET |
| 3 | no effect on read-only | MET |
| 4 | assertions preserved | MET |

## AC-3: Non-E2E tests relocated (7 conditions, 2 descoped)

| # | Condition | Status |
|---|-----------|--------|
| 1 | test_profile_isolation.py moved | DESCOPED |
| 2 | test_dbt_e2e_profile.py moved | DESCOPED |
| 3 | test_plugin_system.py moved | MET |
| 4 | passes in make test-unit | MET |
| 5 | correct imports | MET |
| 6 | old location removed | MET |
| 7 | no assertions weakened | MET |

## AC-4: Runtime reduction (4 conditions)

| # | Condition | Status |
|---|-----------|--------|
| 1 | seed invocations <= 3 | MET (2) |
| 2 | run invocations for read-only = 0 | MET |
| 3 | 10 non-E2E tests relocated | MET |
| 4 | seed in read-only methods = 0 | MET |
