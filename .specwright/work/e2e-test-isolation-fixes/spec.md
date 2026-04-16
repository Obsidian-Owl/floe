# Spec: E2E Test Isolation Fixes

## Goal

Eliminate all 48 E2E test failures caused by profile isolation test pollution and hardcoded NoOp lineage resource.

---

## Task 1: Fix profile isolation test pollution

### AC-1.1: Profile isolation tests use tmp_path, not source tree

The three test methods in `tests/e2e/test_profile_isolation.py` that create `generated_profiles/` directories (`test_uses_generated_profiles_when_dir_exists`, `test_project_dir_always_passed_separately`, `test_run_dbt_uses_product_name_from_project_dir`) MUST create profile directories under `tmp_path`, not under `Path(__file__).parent`.

**Verification**: No occurrence of `Path(__file__).parent / "generated_profiles"` remains in the three test method bodies.

### AC-1.2: Profile isolation tests monkeypatch dbt_utils.__file__

Each of the three tests MUST monkeypatch `dbt_utils.__file__` so that `run_dbt()`'s `Path(__file__).parent / "generated_profiles"` resolves to the `tmp_path`-based directory.

**Verification**: Each test accepts `monkeypatch` fixture and calls `monkeypatch.setattr(dbt_utils, "__file__", ...)`.

### AC-1.3: No shutil.rmtree on source tree paths

None of the three test methods may contain `shutil.rmtree()` calls targeting paths under `Path(__file__).parent`. The `finally` cleanup blocks are removed.

**Verification**: `grep -n "shutil.rmtree" tests/e2e/test_profile_isolation.py` returns zero matches that reference `e2e_dir` (the old source-tree path variable).

### AC-1.4: All three tests still pass

The rewritten tests continue to validate the same behavior:
- `test_uses_generated_profiles_when_dir_exists`: Asserts `--profiles-dir` contains `generated_profiles`
- `test_project_dir_always_passed_separately`: Asserts `--project-dir` differs from `--profiles-dir`
- `test_run_dbt_uses_product_name_from_project_dir`: Asserts `--profiles-dir` ends with product name

**Verification**: `uv run pytest tests/e2e/test_profile_isolation.py::TestRunDbtProfilesDir -v` passes all three.

### AC-1.5: Profile isolation tests don't interfere with session fixture

After the fix, running the full E2E suite no longer shows 44+ `test_dbt_e2e_profile.py` failures caused by missing `generated_profiles/` files.

**Verification**: The `generated_profiles/` directory created by the `dbt_e2e_profile` session fixture survives through the entire test session.

---

## Task 2: Template generates lazy lineage resource

### AC-2.1: Template generates _load_lineage_resource() helper

When `lineage_enabled=True`, `generate_entry_point_code()` generates a `_load_lineage_resource()` function that:
- Reads `compiled_artifacts.json`
- Returns `LineageResource(emitter=create_emitter(...))` when `observability.lineage` is true and `lineage_endpoint` is set
- Returns `NoOpLineageResource()` when lineage is not configured or on any error
- Logs failures at WARNING level

**Verification**: Generated `definitions.py` contains the `_load_lineage_resource` function definition.

### AC-2.2: Template uses lazy initialization (no thread at import)

The generated code uses a lazy accessor pattern:
- `_LINEAGE_RESOURCE` initialized to `None` at module level (no `LineageResource()` call at import)
- `_get_lineage_resource()` creates the resource on first call and caches it
- Asset function body uses `lineage = _get_lineage_resource()`

**Verification**: `import definitions` does NOT spawn any daemon threads. Thread creation only occurs when the asset function is executed.

### AC-2.3: Graceful degradation to NoOp

If `compiled_artifacts.json` is missing, `observability.lineage` is false, `lineage_endpoint` is empty, `LineageResource` import fails, or `create_emitter` raises, `_load_lineage_resource()` returns `NoOpLineageResource()`.

**Verification**: Remove `compiled_artifacts.json` temporarily → `_get_lineage_resource()` returns `NoOpLineageResource` without raising.

### AC-2.4: Imports for LineageResource are inside try/except

The `from floe_orchestrator_dagster.resources.lineage import LineageResource` and `from floe_core.lineage.emitter import create_emitter` imports are inside the `_load_lineage_resource()` function's try/except block, not at module level.

**Verification**: Generated `definitions.py` does NOT have top-level imports for `LineageResource` or `create_emitter`.

---

## Task 3: Regenerate demo definitions

### AC-3.1: Demo definitions.py files use lazy lineage pattern

All three demo `definitions.py` files (`customer-360`, `iot-telemetry`, `financial-risk`) are regenerated with the new lazy lineage resource pattern.

**Verification**: Each file contains `_get_lineage_resource()` function and `lineage = _get_lineage_resource()` in the asset body.

### AC-3.2: Unit tests still pass after regeneration

The existing unit test suite passes with the regenerated definitions.

**Verification**: `make test-unit` passes.
