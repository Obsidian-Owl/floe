# Test Quality Audit: runtime-loader

**Date**: 2026-04-06
**Gate**: gate-tests
**Files audited**: 5 (132 tests total)

## Summary

| Severity | Count |
|----------|-------|
| BLOCK    | 0     |
| WARN     | 7     |
| INFO     | 6     |

**Overall**: PASS with warnings. No blocking issues. Test suite is strong overall with good assertion specificity, thorough error paths, and proper side-effect verification. Warnings are minor gaps in boundary coverage and mock discipline.

---

## Findings

### File 1: test_loader.py (21 tests)

**F1 - WARN** | test_loader.py:376-387 | Category: assertion-strength
`test_resources_are_deferred_not_eager` uses a heuristic check (`forbidden_types` name substring match) rather than asserting a specific expected type. A resource named `MyConnectionHelper` would falsely trigger this, while a raw socket connection without "Connection" in the class name would pass. Acceptable for a structural guard, but fragile.

**F2 - INFO** | test_loader.py:496-515 | Category: mutation-resistance
`test_dbt_assets_calls_emit_start_before_build` sets up `side_effect` for ordering verification AFTER the first invocation, then re-executes. The first invocation's ordering is not actually verified -- only the second run's ordering is checked. A mutation that calls emit_start after dbt on the first invocation but before on subsequent invocations would pass. The re-execution approach works but is unusual and could confuse maintainers.

**F3 - WARN** | test_loader.py:632-667 | Category: assertion-strength
`test_dbt_assets_uses_trace_correlation_facet` has a complex conditional assertion on lines 658-667 that checks kwargs or positional args. The assertion `if call_kwargs.kwargs.get("run_facets"):` silently passes when `run_facets` is an empty dict or None (falls through to `elif`/`else`). If the function passes `run_facets={}`, this test would fail at `pytest.fail()` which IS correct -- but the multi-branch logic is fragile and hard to reason about.

**F4 - INFO** | test_loader.py:670-703 | Category: side-effect
`test_dbt_assets_emit_start_uses_fallback_uuid_on_failure` properly verifies that `emit_complete` receives a UUID fallback. Strong test -- verifies both that dbt proceeds and the fallback run_id type.

### File 2: test_export_iceberg.py (14 tests)

**F5 - WARN** | test_export_iceberg.py:47 | Category: boundary
`EXPECTED_DUCKDB_PATH` is hardcoded to `/tmp/{SAFE_NAME}.duckdb`. This couples the test to the implementation's use of `/tmp/`. If the implementation changes to use `tempfile.gettempdir()` (which may differ on some platforms), this test would break. Not a quality issue per se, but a maintenance risk.

**F6 - WARN** | test_export_iceberg.py:596-608 | Category: assertion-strength
`test_export_skips_unsafe_identifiers` asserts `context.log.warning.call_count >= 3` for 3 unsafe identifiers. The `>= 3` is slightly weak -- could pass if only 3 are logged but an implementation logs extra spurious warnings. An exact count assertion (`== 3`) would be stronger, but this is acceptable since the implementation might legitimately log additional warnings (e.g., for the schema name too).

**F7 - INFO** | test_export_iceberg.py:163-829 | Category: side-effect
Strong side-effect verification throughout. Every test that expects Iceberg writes verifies `mock_catalog.create_table.assert_called_once()`, `mock_iceberg_table.append.assert_called_once()`, `mock_existing_table.overwrite.assert_called_once()`, `mock_conn.close.assert_called_once()`. No accomplishment-simulator risk.

**F8 - INFO** | test_export_iceberg.py:284-335 | Category: mutation-resistance
`test_export_does_not_read_artifacts_from_disk` uses `side_effect=AssertionError(...)` on `Path.read_text` and `CompiledArtifacts.model_validate_json` -- any disk read would immediately fail the test. Excellent mutation resistance.

### File 3: test_code_generator_iceberg.py (88 tests)

**F9 - INFO** | test_code_generator_iceberg.py:1-548 | Category: mutation-resistance
Parametrized tests over `OLD_PATTERNS_FORBIDDEN` (15 symbols x 4 flag combos = 60 tests) provide strong coverage against regression to the old template. `test_different_product_names_produce_different_code` explicitly guards against hardcoded product names. `test_exact_functional_lines` is the strongest mutation-resistance test -- it verifies the exact functional lines of generated code.

**F10 - WARN** | test_code_generator_iceberg.py:183-187 | Category: assertion-strength
`test_product_name_in_docstring` has an unusual assertion: `assert name in code.split('"""')[1] if '"""' in code else name in code[:200]`. The ternary makes this assert `True` when `'"""'` is present and the name is in the docstring, but when `'"""'` is absent it checks `name in code[:200]` which produces a bool that is always truthy (non-empty string in first 200 chars). The logic is correct in practice (generated code always has `"""`), but the fallback branch is effectively a no-op assertion.

**F11 - WARN** | test_code_generator_iceberg.py:83-548 | Category: boundary
No test for empty product name (`""`), product name with spaces, or product name with adversarial characters (e.g., quote-injection payloads). The template does string interpolation into Python code -- if the product name contained Python string escape sequences or quote characters, the generated code could be malformed or exploitable. The `test_product_name_with_dots` tests some special chars but not adversarial ones. This is a boundary gap, though mitigated if callers validate product names upstream.

### File 4: test_loader_integration.py (6 tests)

**F12 - WARN** | test_loader_integration.py:57-123 | Category: mutation-resistance
All 6 integration tests are structural: they verify `isinstance`, key presence (`"dbt" in resources`), and `len(assets) >= 1`. None verify the actual asset names, resource types, or configuration values from the demo artifacts. A loader that returns a hardcoded `Definitions(assets=[DummyAsset()], resources={"dbt": ..., "lineage": ...})` would pass all 6 tests. The unit tests cover specifics, so these integration tests serve as smoke tests -- acceptable for that role, but could be stronger by asserting at least one expected asset key path from the demo.

### File 5: test_runtime_loader_e2e.py (3 tests)

**F13 - INFO** | test_runtime_loader_e2e.py:56-161 | Category: side-effect
E2E tests query real Dagster GraphQL API and verify `loadStatus == "LOADED"` and asset discovery. `test_thin_definitions_are_deployed` reads actual deployed files and verifies content. Strong for E2E scope.

---

## Dimension Summary

### 1. Assertion Strength: GOOD
- Most assertions use exact value comparison (`== expected_path`, `== expected_namespace`)
- Side-effect methods properly use `assert_called_once()`, `assert_not_called()`
- Minor weakness: integration tests use structural assertions only (F12)
- Minor weakness: one heuristic-based assertion (F1)

### 2. Boundary Coverage: GOOD with gaps
- Empty/missing file cases tested (missing artifacts, missing DuckDB)
- Invalid JSON tested
- Unsafe SQL identifiers tested (injection attempts)
- Empty tables tested
- **Gap**: No adversarial product name test in code generator (F11)
- **Gap**: No test for product name with spaces or quote characters

### 3. Mock Discipline: STRONG
- Mocks are used only at package boundaries (duckdb, pyiceberg, plugin_registry)
- Integration tests use real artifacts, no mocks
- E2E tests use real Dagster API
- Every MagicMock has corresponding `assert_called*()` verification
- No import-satisfying-only mocks detected

### 4. Error Paths: STRONG
- Missing artifacts file: `FileNotFoundError` tested
- Invalid JSON: parse error tested
- DuckDB missing: graceful skip with warning tested
- No catalog configured: graceful skip tested
- `emit_start` failure: fallback UUID tested
- `emit_fail` failure: original error propagation tested
- DuckDB connection close on error: tested
- Iceberg factory exception propagation: tested

### 5. Side-Effect Verification: STRONG
- `lineage.emit_start.assert_called_once()` -- verified
- `lineage.emit_complete.assert_called_once()` -- verified
- `lineage.emit_fail.assert_called_once()` -- verified
- `lineage.emit_complete.assert_not_called()` on failure -- verified
- `mock_export.assert_called_once()` / `assert_not_called()` -- verified
- `mock_catalog.create_namespace.assert_called_once_with(SAFE_NAME)` -- verified
- `mock_iceberg_table.append.assert_called_once()` -- verified
- `mock_conn.close.assert_called_once()` -- verified

### 6. Mutation Resistance: GOOD
- Hardcoded return values would fail: tests verify specific derived values (paths, namespaces)
- Different product names tested to catch hardcoding
- Exact functional line matching in code generator
- Old pattern parametrized tests catch template regression
- **Gap**: Integration tests could pass with a trivial hardcoded implementation (F12)

---

## Verdict: PASS

No BLOCK findings. The test suite demonstrates strong quality across all dimensions. The 7 WARN findings are minor and do not indicate structural weakness. The most actionable improvement would be adding adversarial product name boundary tests in the code generator (F11).
