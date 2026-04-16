# Design: E2E Test Isolation Fixes

## Overview

Fix 2 root causes that produce 48 E2E test failures:
1. **Profile isolation tests** delete real `generated_profiles/` directory, breaking 47 downstream tests
2. **Template hardcodes NoOpLineageResource**, breaking 1 observability test

## Approach

### Task 1: Fix profile isolation test pollution

**Problem**: 3 tests in `test_profile_isolation.py` create/delete files at the REAL path `Path(__file__).parent / "generated_profiles" / "<product>"` (lines 133, 235, 278). Their `finally` blocks destroy the session-scoped `dbt_e2e_profile` fixture's files.

**Fix**: Rewrite the 3 test methods to:
1. Create the generated profiles directory under `tmp_path` (not `Path(__file__).parent`)
2. Monkeypatch `dbt_utils.__file__` so `run_dbt()`'s `Path(__file__).parent` resolves to `tmp_path`
3. Remove the `finally: shutil.rmtree(e2e_dir)` blocks — `tmp_path` auto-cleans

**Why monkeypatch works**: `run_dbt()` evaluates `Path(__file__).parent` inside the function body (line 152 of `dbt_utils.py`), not at module load time. Monkeypatching `dbt_utils.__file__` before calling `run_dbt()` correctly redirects the path lookup. The test file's own `Path(__file__).parent` is NOT used — we replace it with explicit `tmp_path` references.

**Implementation pattern** (same for all 3 tests):
```python
def test_uses_generated_profiles_when_dir_exists(self, tmp_path, monkeypatch):
    from dbt_utils import run_dbt

    project_dir = tmp_path / "customer-360"
    project_dir.mkdir()

    # Create generated profiles under tmp_path (NOT source tree)
    gen_dir = tmp_path / "generated_profiles" / "customer-360"
    gen_dir.mkdir(parents=True)
    (gen_dir / "profiles.yml").write_text("customer_360:\n  target: e2e\n")

    # Redirect run_dbt()'s Path(__file__).parent to tmp_path
    import dbt_utils
    monkeypatch.setattr(dbt_utils, "__file__", str(tmp_path / "dbt_utils.py"))

    with patch("dbt_utils.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(...)
        run_dbt(["debug"], project_dir)
        # ... assertions unchanged ...
    # No finally cleanup — tmp_path auto-cleans
```

### Task 2: Template generates lazy lineage resource when configured

**Problem**: `plugin.py:1334` always generates `_LINEAGE_RESOURCE = NoOpLineageResource()`. When `compiled_artifacts.json` has `observability.lineage = true` with a Marquez endpoint, the lineage resource should emit real events.

**BLOCK addressed**: `LineageResource.__init__()` starts a daemon thread (line 66-68 of `lineage.py`). Creating it at module load time would spawn threads during `dbt parse`, IDE indexing, test collection, etc. Must defer to first use.

**Fix**: Use lazy initialization pattern. The template generates:

1. A `_load_lineage_resource()` factory (called on first use, not at import):
```python
def _load_lineage_resource():
    """Load lineage resource from compiled_artifacts.json (lazy)."""
    if not ARTIFACTS_PATH.exists():
        return NoOpLineageResource()
    try:
        artifacts = CompiledArtifacts.model_validate_json(ARTIFACTS_PATH.read_text())
        obs = artifacts.observability
        if obs is None or not obs.lineage:
            return NoOpLineageResource()
        endpoint = getattr(obs, 'lineage_endpoint', None)
        transport = getattr(obs, 'lineage_transport', 'http')
        if not endpoint:
            return NoOpLineageResource()
        namespace = getattr(obs, 'lineage_namespace', 'default') or 'default'
        from floe_orchestrator_dagster.resources.lineage import LineageResource
        from floe_core.lineage.emitter import create_emitter
        transport_config = {"type": transport, "url": endpoint}
        emitter = create_emitter(transport_config, namespace)
        return LineageResource(emitter=emitter)
    except Exception:
        logging.getLogger(__name__).warning(
            "lineage_resource_load_failed", exc_info=True,
        )
        return NoOpLineageResource()
```

2. A lazy accessor with module-level cache:
```python
_LINEAGE_RESOURCE: Any = None

def _get_lineage_resource():
    global _LINEAGE_RESOURCE
    if _LINEAGE_RESOURCE is None:
        _LINEAGE_RESOURCE = _load_lineage_resource()
    return _LINEAGE_RESOURCE
```

3. In the asset function body: `lineage = _get_lineage_resource()` (replaces `lineage = _LINEAGE_RESOURCE`)

**Key properties**:
- No daemon thread at import time — `LineageResource` only created on first asset execution
- Imports for `LineageResource` and `create_emitter` are inside the try/except — graceful if packages missing
- `_LINEAGE_RESOURCE` cached after first call — subsequent executions reuse the same resource
- Failures logged at WARNING level per constitution S-VI

**Template changes in `plugin.py`**:
- Add `from typing import Any` to imports (for `_LINEAGE_RESOURCE: Any = None` type hint)
- Replace `lineage_setup` string from `"\n\n_LINEAGE_RESOURCE = NoOpLineageResource()\n"` to the lazy loading pattern above
- Change asset body from `lineage = _LINEAGE_RESOURCE` to `lineage = _get_lineage_resource()`

### Task 3: Regenerate demo definitions

After the template change, regenerate the 3 demo `definitions.py` files to pick up the new lineage resource loading pattern. Without this, the observability test will continue to fail.

## Blast Radius

| Module/File | Scope | Propagation |
|-------------|-------|-------------|
| `tests/e2e/test_profile_isolation.py` | 3 test methods changed | Local — only affects test behavior |
| `plugins/floe-orchestrator-dagster/.../plugin.py` | Template code generation | Adjacent — affects all generated definitions.py |
| `demo/*/definitions.py` | 3 auto-generated files | Local — regenerated from template |

**What this does NOT change:**
- `tests/e2e/conftest.py` (the `dbt_e2e_profile` fixture itself)
- `tests/e2e/dbt_utils.py` (the `run_dbt()` function)
- `tests/e2e/test_data_pipeline.py` (the failing tests themselves)
- `tests/e2e/test_dbt_e2e_profile.py` (the profile validation tests)
- Any production plugin code (except template generation)
- `LineageResource` or `NoOpLineageResource` classes

## Risk Assessment

**Main risk**: Template change could break if `create_emitter` import fails inside `_load_lineage_resource()`. Mitigated: imports inside try/except, falls back to NoOp.

**Secondary risk**: Dagster multiprocess executor reimports modules — each code location load calls `_load_lineage_resource()` once. If Marquez is unreachable, `create_emitter()` might raise immediately. Mitigated: wrapped in try/except.

**Addressed BLOCK (daemon thread)**: `LineageResource` creation deferred to first asset execution via lazy init. No threads spawned during import, `dbt parse`, IDE indexing, or test collection.

## WARN: Test ordering dependency

The profile fixture tests still depend on the session-scoped `dbt_e2e_profile` fixture creating files first. If the fixture itself fails, these tests will still fail. This is acceptable — fixture failures should surface as test errors, not silent fallback to demo profiles.
