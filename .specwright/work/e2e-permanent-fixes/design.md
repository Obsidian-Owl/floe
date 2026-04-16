# Design: E2E Permanent Fixes (Revised — Option B)

## Revision History

- **v1** (2026-04-05): Original design — 4 independent fixes targeting symptoms
- **v2** (2026-04-06): **PIVOT to Option B** — replace code generation with runtime loader. Research revealed 96% boilerplate in generated files, module-load-time crashes, and systemic UX issues across the platform. The original 4 fixes addressed symptoms; this revision addresses root causes.

## Problem (Revised)

The original design identified 4 categories of E2E failure. Deeper analysis reveals these are **symptoms of one architectural problem**: the code generation approach in `generate_entry_point_code()` produces 187-line `definitions.py` files where **96% is identical boilerplate** that:

1. **Crashes at module-load time** — `_load_iceberg_resources()` is called at module scope (line 184 of generated code), which eagerly connects to Polaris. If Polaris isn't ready → `DagsterImportError` kills ALL code locations.

2. **Silently degrades** — `_export_dbt_to_iceberg()` returns silently when DuckDB file is missing, `compiled_artifacts.json` is absent, or catalog config is invalid. User's data never reaches Iceberg with no error in the UI.

3. **Creates maintenance burden** — Every data product gets a copy of the same Iceberg export logic, DuckDB handling, SQL identifier validation, and resource wiring. Bug in one → bug in all, but fixes require regeneration.

4. **Diverges from the dynamic path** — `plugin.py` has TWO asset creation paths: `create_definitions()` (lines 183-287, correct) and `generate_entry_point_code()` (lines 1100-1406, generates brittle files). They handle errors differently, wire resources differently, and evolve independently.

### Broader Platform UX Issues (Research Findings)

Deep research revealed additional systemic issues beyond code generation:

| Issue | Severity | Evidence |
|---|---|---|
| **No scaffolding** — 11 manual steps to add a data product | HIGH | No `floe scaffold` command exists |
| **Inconsistent error handling** — `try_create_ingestion_resources()` returns `{}` silently; `try_create_iceberg_resources()` re-raises | HIGH | ingestion.py:122-130 vs iceberg.py:193-198 |
| **Docker build fragility** — manual COPY lines per plugin, hardcoded version ARGs | HIGH | Dockerfile lines 94-100, 122-129 |
| **Triple compilation** — `dbt compile` on host, `dbt parse` in Docker, manifest rebuilt 3x | MEDIUM | Makefile:338, Dockerfile:177-179 |
| **No ownership clarity** — users can't tell which files are generated vs authored | MEDIUM | No `.gitignore` or README in demo products |
| **Config read 3x** — `compiled_artifacts.json` parsed at compile-time, module-load, and runtime | MEDIUM | definitions.py lines 48, 69, 77 |

## Approach: Runtime Loader (Option B)

Replace the 187-line generated `definitions.py` with a **thin runtime loader** — a ~10-line file that delegates all resource wiring to the existing `create_definitions()` method (plugin.py:183-287), which already handles everything correctly.

### What Changes

**Before** (generated, 187 lines, 96% boilerplate):
```python
# AUTO-GENERATED — 24 imports, 6 helper functions, inline Iceberg export...
from floe_core.plugin_registry import get_registry
from floe_core.schemas.compiled_artifacts import CompiledArtifacts
# ... 180 more lines of duplicated logic
defs = Definitions(
    assets=[customer_360_dbt_assets],
    resources={
        "dbt": DbtCliResource(...),
        **try_create_lineage_resource(None),   # module-load crash risk
        **_load_iceberg_resources(),            # module-load crash risk
    },
)
```

**After** (runtime loader, ~15 lines, zero boilerplate):
```python
"""Dagster definitions for customer-360 data product."""
from pathlib import Path
from floe_orchestrator_dagster.loader import load_product_definitions

PROJECT_DIR = Path(__file__).parent

defs = load_product_definitions(
    product_name="customer-360",
    project_dir=PROJECT_DIR,
)
```

### How It Works

A new module `floe_orchestrator_dagster.loader` provides `load_product_definitions()`:

1. **Reads** `compiled_artifacts.json` from `project_dir` (fail-fast if missing)
2. **Validates** via `CompiledArtifacts.model_validate_json()` (existing Pydantic schema)
3. **Creates dbt asset** using `@dbt_assets` decorator from dagster-dbt, with `DbtProject` and manifest from `project_dir/target/manifest.json` — matching the current generated code pattern, NOT the `create_definitions()` per-model `@asset` path
4. **Wires resources** using the same `try_create_*_resources()` factories — but called inside `ResourceDefinition` generator wrappers in the loader, so connections are deferred to Dagster resource initialization (after module import completes)
5. **Wires Iceberg export** as a call at the end of the `@dbt_assets` function body (after `yield from dbt.cli(["build"]).stream()`), parameterized with `product_name` and `project_dir`
6. **Wires lineage** using the same `emit_start`/`emit_complete` pattern from the generated code, with `TraceCorrelationFacetBuilder` from the dynamic path for proper OTel integration
7. **Returns** `Definitions` object with all resources and assets

### Critical Architecture Note: Two dbt Asset Paths

The codebase has **two different dbt-to-Dagster integration paths**:

| Path | Location | Pattern | Use Case |
|---|---|---|---|
| **Dynamic** | `create_definitions()` → `create_assets_from_transforms()` (plugin.py:417-578) | Per-model `@asset` + `dbt.run_models(select=model_name)` | Programmatic use (SDK, tests) |
| **Generated** | `definitions.py` templates (plugin.py:1100-1406) | Single `@dbt_assets(manifest=...)` + `dbt.cli(["build"]).stream()` | Dagster workspace deployment |

The runtime loader replaces the **generated path** — it uses `@dbt_assets` (matching generated code), NOT `create_definitions()` (which uses per-model `@asset`). The dynamic path remains unchanged for SDK/programmatic use.

### Why This Works

- **`@dbt_assets` is the correct pattern** — provides manifest-aware asset graph, streaming execution, and dagster-dbt metadata integration
- **Resource factories already exist** — `try_create_iceberg_resources()`, `try_create_lineage_resource()`, etc. are called from within `ResourceDefinition` generator wrappers in the loader to defer connections
- **Dagster workspace.yaml doesn't change** — still loads `customer_360.definitions:defs`
- **Dagster resource lifecycle** — ResourceDefinition generators are called at Dagster startup (after module import), not during Python import. This is the window where K8s services are ready. Module import happens first (just function definitions, no connections), then Dagster initializes resources (connections happen here)

### Key Design Decisions

**D-8: Deferred resource connections via ResourceDefinition generators in the loader**

The resource factory functions (`try_create_iceberg_resources()`, etc.) remain unchanged — they still connect eagerly when called. The change is **where they are called**: instead of at module scope in `definitions.py`, they are called inside `ResourceDefinition` generator functions in the loader. This means connections happen during Dagster resource initialization, not during Python module import.

```python
# In loader.py — resource factory called inside generator, not at module scope
def _lazy_iceberg_resources(plugins, governance):
    def _resource_fn(_init_context):
        resources = try_create_iceberg_resources(plugins, governance=governance)
        yield resources.get("iceberg")
    return ResourceDefinition(resource_fn=_resource_fn)
```

**Important timing distinction:**
- Module import: `definitions.py` is imported by Dagster → `load_product_definitions()` runs → reads `compiled_artifacts.json` → defines `@dbt_assets` function → creates `Definitions(resources={...})` with `ResourceDefinition` objects (no connections yet)
- Dagster startup: Dagster calls each `ResourceDefinition`'s `_resource_fn` → connections happen here → services should be ready

**D-9: Iceberg export as parameterized function, called in asset body**

The 84-line `_export_dbt_to_iceberg()` is extracted to `floe_orchestrator_dagster.export.iceberg.export_dbt_to_iceberg(context, product_name, project_dir, artifacts_path)`. It is called at the end of the `@dbt_assets` function body (after `yield from dbt.cli(["build"]).stream()`), parameterized with the product name and project directory. This is NOT a Dagster hook — it is a direct function call in the asset body, same pattern as the current generated code.

```python
# In loader.py — asset function body
@dbt_assets(manifest=manifest_path, project=dbt_project, name=asset_name)
def _dbt_asset_fn(context, dbt: DbtCliResource):
    # lineage start
    yield from dbt.cli(["build"], context=context).stream()
    # lineage complete
    export_dbt_to_iceberg(context, product_name=safe_name, project_dir=project_dir,
                          artifacts_path=artifacts_path)
```

Product-specific constants (`DUCKDB_PATH`, `product_namespace`) are derived from `product_name` parameter:
- `duckdb_path = f"/tmp/{safe_name}.duckdb"`
- `product_namespace = safe_name`

**D-10: `generate_entry_point_code()` retained but simplified**

The method still exists for `floe compile --generate-definitions`. It generates the thin loader pattern instead of the 187-line file. The `compile --generate-definitions` command becomes optional — not required for deployment.

**D-11: Loader is a NEW canonical `@dbt_assets` path, NOT a delegate to `create_definitions()`**

`create_definitions()` (plugin.py:183-287) uses per-model `@asset` — a fundamentally different asset creation strategy. The loader does NOT delegate to it. Instead, the loader is the new canonical implementation of the `@dbt_assets` pattern, consolidating what was previously template-generated code into a proper module.

The two paths remain:
- `create_definitions()` — per-model `@asset`, for SDK/programmatic use
- `load_product_definitions()` — `@dbt_assets`, for Dagster workspace deployment

**D-12: Lineage emission matches dynamic path quality**

The generated code had a simplified lineage pattern (bare `emit_start`/`emit_complete` with generic exception catching). The loader adopts the dynamic path's higher-quality pattern from plugin.py:553-578: `TraceCorrelationFacetBuilder`, `emit_fail` on error, fallback `uuid4()` run ID.

## Files Changed

| File | Change | Blast Radius |
|---|---|---|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py` | **NEW** — runtime loader (~180 lines): `@dbt_assets` creation, resource wiring, lineage hooks | Local — new module, no existing code modified |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/__init__.py` | **NEW** — package init | Local |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` | **NEW** — `export_dbt_to_iceberg()` parameterized with product_name, project_dir, artifacts_path | Local — consolidates 3 identical copies |
| `demo/customer-360/definitions.py` | **SIMPLIFIED** — 187 lines → ~15 lines | Local — same `defs` variable, same Dagster discovery |
| `demo/iot-telemetry/definitions.py` | **SIMPLIFIED** — same as above | Local |
| `demo/financial-risk/definitions.py` | **SIMPLIFIED** — same as above | Local |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | **MODIFIED** — `generate_entry_point_code()` simplified to emit thin loader | Adjacent — affects `floe compile --generate-definitions` output |
| `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py` | **NEW** — unit tests for runtime loader | Local |
| `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py` | **NEW** — unit tests for extracted Iceberg export | Local |
| `plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_lineage.py` | **MODIFIED** — update assertions for new generated output | Local |

### Files NOT Changed

- **`charts/floe-platform/templates/configmap-dagster-workspace.yaml`** — still loads `customer_360.definitions:defs`
- **`charts/floe-platform/values-test.yaml`** — code locations unchanged
- **`docker/dagster-demo/Dockerfile`** — still COPYs demo products, still runs `dbt parse`. `floe_orchestrator_dagster` is already pip-installed in the image (Stage 2 installs all workspace packages).
- **`CompiledArtifacts` schema** — unchanged
- **Plugin ABCs/registry** — unchanged
- **Resource factory functions** — unchanged (called from within loader wrappers, not modified)
- **`create_definitions()`** — unchanged (per-model `@asset` path remains for SDK use)

## Integration Points

- The runtime loader calls existing `try_create_*_resources()` functions inside `ResourceDefinition` generators — factories unchanged, connection timing changed
- Dagster workspace.yaml discovery unchanged — same module path, same `defs` attribute
- `compiled_artifacts.json` is still the sole contract — loaded once during `load_product_definitions()` call (module scope), parsed into Pydantic model, passed to resource factories
- `@dbt_assets` uses `manifest.json` from `project_dir/target/` — same as current generated code
- `floe_orchestrator_dagster` must be installed in the Python environment — already the case in the Docker image (Dockerfile Stage 2)

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Dagster module discovery requires `defs` at module level | `load_product_definitions()` returns `Definitions` at module scope — Dagster discovers it identically |
| `create_definitions()` may have untested paths when called from loader context | Existing unit + integration tests already cover this method; add loader-specific tests |
| Simplified `generate_entry_point_code()` breaks existing unit tests | Update `test_code_generator_lineage.py` to match new output format |
| Iceberg export extraction may miss edge cases from template | Extract verbatim from existing generated code — same logic, single location |
| Users with custom `definitions.py` modifications lose changes | `definitions.py` is marked AUTO-GENERATED — custom modifications were never supported |

## Blast Radius

### Modules this design touches

| Module | Scope | Failure Propagation |
|---|---|---|
| `floe_orchestrator_dagster.loader` (NEW) | New module | Local — isolated, no existing deps |
| `floe_orchestrator_dagster.export.iceberg` (NEW) | Extracted from template | Local — consolidates copies |
| `demo/*/definitions.py` | Simplified | Local — same Dagster discovery |
| `plugin.py` (template section only) | Modified | Adjacent — affects future `floe compile` output |
| Unit tests | Updated | Local |

### What this design does NOT change

- No changes to `FloeSpec`, `CompiledArtifacts`, or any Pydantic schema
- No changes to plugin lifecycle, registry, or ABCs
- No changes to Dagster workspace.yaml or Helm chart templates
- No changes to Docker build process
- No changes to `create_definitions()` core method
- No changes to resource factory functions
- No changes to K8s architecture or deployment topology

## Alternatives Considered

### Option A: Fix code generation templates (original design v1)
- Addresses symptoms (facet key, lineage calls) but not root cause
- Still leaves 96% boilerplate duplication
- Still crashes at module-load time
- Still diverges dynamic and generated paths
- **Rejected:** polishing a fundamentally flawed approach

### Option C: Full dynamic loader with no definitions.py
- Dagster discovers code locations via a custom `dagster.yaml` with `python_module` pointing to a generic loader
- No per-product `definitions.py` at all — loader discovers products from directory structure
- **Deferred:** More elegant but larger blast radius (changes Dagster discovery mechanism, Helm templates, Docker layout). Option B achieves the same reliability with minimal change.

## Critic Feedback

### Round 1 — specwright-architect (v1 design)

**Verdict:** REJECTED (3 BLOCKs)

**BLOCK 1 (RESOLVED):** `create_definitions()` uses per-model `@asset`, not `@dbt_assets`. Design revised: loader implements `@dbt_assets` directly, does NOT delegate to `create_definitions()`.

**BLOCK 2 (RESOLVED):** D-11 was "keep create_definitions() as core engine." Revised to: "Loader is NEW canonical @dbt_assets path."

**BLOCK 3 (RESOLVED):** Iceberg export had product-specific constants. Design revised: extracted function parameterized with `product_name`, `project_dir`, `artifacts_path`.

### Round 2 — specwright-architect (v2 design)

**Verdict:** APPROVED — All dimensions ≥4/5, no BLOCKs.

**Scores:** Correctness 4/5, Completeness 4/5, Risk 4/5, Blast Radius 5/5, Integration 4/5.

**WARN 1 (ACKNOWLEDGED):** `ResourceDefinition` wrapper may yield `None` if Iceberg creation fails. Implementation must guard: fail-fast (raise) instead of yielding `None`.

**WARN 2 (ACKNOWLEDGED):** `emit_fail` is unreachable in the pseudocode — `yield from dbt.cli().stream()` unwinds on error without exception handling. Implementation must add `try/except` around `yield from` + Iceberg export for `emit_fail`.

**WARN 3 (ACKNOWLEDGED):** Lineage transport initialization is partially eager (emitter created outside generator). Acceptable since NoOp is default when no backend configured. Document in implementation comments.

**INFO 1:** `DbtProject.__init__` at module scope matches existing behavior — not a regression.

**INFO 2:** Extracted Iceberg export could accept parsed `CompiledArtifacts` object instead of re-reading file. Simplification to apply during implementation.
