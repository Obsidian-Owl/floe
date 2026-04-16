# Plan: E2E Test Isolation Fixes

## Task Breakdown

### Task 1: Fix profile isolation test pollution

**Files to modify:**
- `tests/e2e/test_profile_isolation.py` — rewrite 3 test methods in `TestRunDbtProfilesDir` class

**Change map:**
1. `test_uses_generated_profiles_when_dir_exists` (line 120-165):
   - Add `monkeypatch` parameter
   - Replace `e2e_dir = Path(__file__).parent / "generated_profiles" / "customer-360"` with `gen_dir = tmp_path / "generated_profiles" / "customer-360"`
   - Add `monkeypatch.setattr(dbt_utils, "__file__", str(tmp_path / "dbt_utils.py"))`
   - Remove `finally: shutil.rmtree(e2e_dir)` block
   - Flatten try/finally into straight-line code

2. `test_project_dir_always_passed_separately` (line 222-263):
   - Same pattern as above

3. `test_run_dbt_uses_product_name_from_project_dir` (line 265-299):
   - Same pattern, product name is `iot-telemetry`

**Assertions unchanged** — only the file creation/cleanup paths change.

### Task 2: Template generates lazy lineage resource

**Files to modify:**
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` — `generate_entry_point_code()` method

**Change map:**
1. In the imports section of the template (around line 1210-1230):
   - Keep `NoOpLineageResource` import
   - Do NOT add `LineageResource` or `create_emitter` to top-level imports (they go inside `_load_lineage_resource()`)

2. In `lineage_setup` string (around line 1331-1334):
   - Replace `"\n\n_LINEAGE_RESOURCE = NoOpLineageResource()\n"` with the lazy loading pattern:
     - `_load_lineage_resource()` function definition
     - `_LINEAGE_RESOURCE: Any = None` module-level cache
     - `_get_lineage_resource()` accessor function

3. In the asset function body (around line 1347):
   - Change `lineage = _LINEAGE_RESOURCE` to `lineage = _get_lineage_resource()`

**Template string construction notes:**
- The lineage_setup string is an f-string inserted into the generated code
- Curly braces for dict literals need double-escaping: `{{` / `}}`
- String quotes inside the template need careful escaping

### Task 3: Regenerate demo definitions

**Files to modify:**
- `demo/customer-360/definitions.py` (auto-generated)
- `demo/iot-telemetry/definitions.py` (auto-generated)
- `demo/financial-risk/definitions.py` (auto-generated)

**Method:** Run `floe compile` for each demo product, or directly invoke `DagsterOrchestratorPlugin.generate_entry_point_code()` to regenerate. Alternatively, manually apply the same template output.

**Verification:** `make test-unit` to confirm no regressions.

## Dependency Order

```
Task 1 (profile isolation) ─── independent
Task 2 (template change) ────► Task 3 (regenerate demos)
```

Tasks 1 and 2 are independent and can be built in either order. Task 3 depends on Task 2.

## Risk Mitigation

- **f-string escaping**: Template strings with nested braces are error-prone. Build the `lineage_setup` string carefully, test by generating a definitions.py and verifying it parses.
- **monkeypatch scope**: `monkeypatch` is function-scoped by default — changes are auto-reverted after each test. No cleanup needed.
