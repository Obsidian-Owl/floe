# Context: e2e-test-isolation-fixes

baselineCommit: e1dbdb3f64b2fec5574b3c006645173418fc5800

## Research Findings

### Root Cause A: Profile isolation tests destroy session fixture files

**Files involved:**
- `tests/e2e/test_profile_isolation.py` (lines 133, 165, 235, 263, 278, 299)
- `tests/e2e/conftest.py` (session-scoped `dbt_e2e_profile` fixture, line 1162)
- `tests/e2e/dbt_utils.py` (`run_dbt()` profile resolution, line 152-153)

**Mechanism:**
Three tests create files in the REAL source tree at `Path(__file__).parent / "generated_profiles" / "<product>"`, then `shutil.rmtree()` them in `finally` blocks. This destroys files created by the session-scoped `dbt_e2e_profile` fixture.

Test execution order (alphabetical):
1. `test_compile_deploy_materialize_e2e.py` — PASSES (uses fixture, profiles exist)
2. `test_data_pipeline.py` — first tests PASS (profiles still exist)
3. `test_profile_isolation.py` — **DELETES** `generated_profiles/customer-360/` and `generated_profiles/iot-telemetry/`
4. Remaining `test_data_pipeline.py` tests — FAIL (profiles gone, fallback to demo profiles)
5. `test_dbt_e2e_profile.py` — FAIL (profiles gone)

Wait — actually test_profile_isolation.py runs BEFORE test_data_pipeline.py alphabetically? Let me check. "profile_isolation" < "data_pipeline"? No: "d" < "p", so test_data_pipeline.py runs FIRST. But actually pytest collects test_data_pipeline.py BEFORE test_profile_isolation.py.

Looking at the actual test log ordering:
- test_data_pipeline.py::TestDataPipeline tests run at ~10-19%
- test_profile_isolation.py runs at ~16-18% (interleaved? or after?)

The key evidence: `test_incremental_model_merge` (which is in test_data_pipeline.py) fails at [15%] with `--profiles-dir demo/customer-360` (fallback). This means by the time test_incremental_model_merge runs, the generated_profiles directory is already gone.

Wait — test_profile_isolation.py has tests at the SAME percentage range. Since both files are in the same directory, pytest collects them by filename. "test_data_pipeline.py" < "test_dbt_e2e_profile.py" < "test_profile_isolation.py". So test_data_pipeline runs first! But some of its later tests (test_incremental_model_merge) fail.

Re-checking: could test_profile_isolation tests be interleaved? No — pytest runs all tests from one file before moving to the next (within the same directory).

The actual test execution order from logs:
1. test_asset_discovery.py (0-6%)
2. test_compile_deploy_materialize_e2e.py (6-10%)
3. test_data_pipeline.py (10-19%): seed/run/test tests PASS early, but test_incremental_model_merge at 15% FAILS
4. test_dbt_e2e_profile.py (19-67%): all file-existence tests FAIL
5. test_profile_isolation.py (after profile tests)

This means the profiles are gone BEFORE test_profile_isolation.py runs. Something else is deleting them.

**Alternative hypothesis**: The `dbt_e2e_profile` fixture's cleanup at line 1239 runs when the fixture is first invoked (stale cleanup). But the fixture creates the directory AFTER cleanup (line 1298). The files should exist.

**Most likely cause**: The `run_dbt()` helper's `_purge_iceberg_namespace()` function? No, that purges remote Iceberg tables, not local files.

Actually — re-reading the logs: the `--profiles-dir` fallback to `demo/customer-360` happens for test_incremental_model_merge. But earlier tests like `test_dbt_seed_loads_data[customer-360]` also use `run_dbt()` and they PASS. If those earlier tests also use the fallback, the seed data would go into an in-memory DuckDB and not Iceberg. But the test checks `returncode == 0` which would still pass with the demo profile.

The profile issue only manifests when the test depends on Iceberg tables existing (test_incremental_model_merge tries to read Iceberg row counts, test_data_retention_enforcement tries to access Iceberg tables directly).

**Revised theory**: The generated_profiles MAY have never existed during this test run. The fixture may have errored during the `floe_compute_duckdb` import (line 1272) or the profile writing step, but error handling masks it.

Actually — I just realized: the test log shows `test_fixture_returns_dict_with_all_three_products PASSED [19%]`. The fixture DID yield a dict. But the files may not exist because: the fixture creates files at line 1298-1308, but if `_build_dbt_iceberg_profile()` raises or the write fails, the except at 1309 would cleanup and re-raise (the fixture wouldn't yield). Since it yielded, files WERE created.

Something deleted them between creation and when test_profile_file_exists_on_disk runs.

**Final root cause**: The tests in `test_profile_isolation.py` that create and delete files at `Path(__file__).parent / "generated_profiles" / "customer-360"` (lines 133-165, 235-263, 278-299). Even though these tests run AFTER test_data_pipeline.py in alphabetical order, the damage shows up because:
1. test_data_pipeline.py tests that run early don't depend on Iceberg tables (just dbt returncode)
2. test_profile_isolation.py runs DURING the same pytest session
3. test_dbt_e2e_profile.py runs after test_profile_isolation.py alphabetically ("dbt" < "profile"... wait, "d" < "p" so test_dbt_e2e_profile.py runs BEFORE test_profile_isolation.py)

Actually: "test_dbt_e2e_profile.py" < "test_profile_isolation.py" alphabetically. So test_dbt_e2e_profile runs FIRST, which means the profiles should still exist... Unless they were never created properly.

Let me look at this from the evidence: test_fixture_returns_dict_with_all_three_products PASSED, meaning the fixture yielded paths. But test_profile_file_exists_on_disk FAILED, meaning files don't exist at those paths. The fixture yielded BEFORE test_profile_isolation.py runs (since dbt < profile alphabetically).

**The only explanation**: The files were created by the fixture but something deleted them between test_fixture_returns_dict_with_all_three_products and test_profile_file_exists_on_disk — which are in the SAME test class in the SAME file. This is impossible unless the cleanup happens synchronously between those two tests.

Wait — maybe conftest fixtures from test_profile_isolation.py are being set up/torn down? No, test_profile_isolation.py tests don't share fixtures with test_dbt_e2e_profile.py.

**REAL answer**: I need to check if maybe the session fixture's profile writing silently failed. The paths were created (mkdir) but file writing failed or wrote empty files. Let me check if `_build_dbt_iceberg_profile()` can return empty string.

Looking at the function (conftest.py line 1096-1159): it returns a long f-string. It cannot be empty.

I'm going to design the fix for both scenarios — the profile isolation tests AND a defensive check in the fixture.

### Root Cause B: Template hardcodes NoOpLineageResource

**Files involved:**
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` (line 1334)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py`
- `demo/*/compiled_artifacts.json`

**Mechanism:**
- `compiled_artifacts.json` has `observability.lineage = true` and `observability.lineage_endpoint = "http://floe-platform-marquez:5000/api/v1/lineage"` but `plugins.lineage_backend = null`
- Template always generates `_LINEAGE_RESOURCE = NoOpLineageResource()`
- NoOp discards all events → Marquez never receives parentRun facets
- `test_openlineage_four_emission_points` checks Marquez for parentRun facets → fails

**Required fix:**
- Template should generate a `_load_lineage_resource()` helper that reads compiled_artifacts
- If `observability.lineage` is true and endpoint is set, create real `LineageResource`
- Falls back to `NoOpLineageResource` on any error
- Import `LineageResource` and `create_emitter` conditionally

**Key files for lineage resource creation:**
- `LineageResource` class: `resources/lineage.py:45` — wraps async emitter in daemon thread
- `create_emitter()`: `floe_core/lineage/emitter.py` — creates HTTP transport emitter
- `NoOpLineageResource`: `resources/lineage.py:259` — discards all events

**Gotchas:**
- `LineageResource.__init__` starts a daemon thread — acceptable for module-level singleton
- Need try/except for imports (lineage packages may not be installed)
- Emitter needs transport_config dict: `{"type": "http", "url": "<endpoint>"}`
- Namespace comes from `observability.lineage_namespace` or defaults to "default"
