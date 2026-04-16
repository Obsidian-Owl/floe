# Gate: Tests

**Status**: PASS
**Timestamp**: 2026-04-05T10:20:00Z

## Results

### Relocated test execution
- `packages/floe-core/tests/unit/plugins/test_plugin_system.py`: 9 passed, 1 xfailed
- All 10 tests collected and executed successfully

### AST validation (static analysis)
- Fixture structure (scope, yield, try/finally): PASS
- Read-only tests have no seed/run calls: PASS
- Read-only tests accept dbt_pipeline_result param: PASS
- Mutating tests don't use shared fixture: PASS
- Relocation checks (old removed, new exists, no e2e markers): PASS

### Note on run_dbt(["test"]) calls
Two read-only tests (`test_dbt_tests_pass`, `test_data_quality_checks`) call
`run_dbt(["test"], ...)` — this is `dbt test` (data validation), NOT `dbt seed`
or `dbt run`. This is correct: the fixture handles seed+run, then the test
validates data quality. The wiring tests correctly check only for seed/run calls.
