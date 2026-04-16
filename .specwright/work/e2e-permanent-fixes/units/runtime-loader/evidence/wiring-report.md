# Wiring Report: runtime-loader

**Gate**: gate-wiring
**Unit**: runtime-loader (5 of 9)
**Branch**: feat/e2e-production-bugfixes
**Baseline**: f1f1e25c00fe64845da9166b06c9b4654670bd8d
**Date**: 2026-04-06

---

## Summary: PASS

All changed files are properly wired. No dead code, no orphaned files, no unused exports.

---

## Check 1: loader.py exports `load_product_definitions`

**Result**: PASS

- `loader.py:29` defines `def load_product_definitions(product_name, project_dir) -> Definitions`
- Imported by all 3 demo definitions.py files:
  - `demo/customer-360/definitions.py:13`
  - `demo/financial-risk/definitions.py:13`
  - `demo/iot-telemetry/definitions.py:13`
- Imported by unit tests: `tests/unit/test_loader.py:41`
- Imported by integration tests: `tests/integration/test_loader_integration.py:25`
- Referenced in E2E tests: `tests/e2e/test_runtime_loader_e2e.py:145` (string check)
- Referenced in plugin.py template: `plugin.py:1144` (generated code string)

## Check 2: export/iceberg.py exports `export_dbt_to_iceberg`

**Result**: PASS

- `export/iceberg.py:28` defines `def export_dbt_to_iceberg(context, product_name, project_dir, artifacts) -> None`
- Imported by `loader.py:24`: `from floe_orchestrator_dagster.export.iceberg import export_dbt_to_iceberg`
- Called in `loader.py:106` inside the `_dbt_assets_fn` body
- Imported by unit tests: `tests/unit/test_export_iceberg.py:39`
- loader.py unit tests mock it: `tests/unit/test_loader.py:52` via `_EXPORT_FN`

## Check 3: export/__init__.py is a proper package init

**Result**: PASS (INFO)

- `export/__init__.py` contains module docstring and `from __future__ import annotations` (3 lines)
- Does not re-export anything -- this is correct since consumers import directly from `export.iceberg`
- Two files import from the subpackage: `loader.py` and `test_export_iceberg.py`, both using `from floe_orchestrator_dagster.export.iceberg import ...`
- The `__init__.py` is required for Python package discovery; it is not orphaned

## Check 4: Demo definitions.py import consistency

**Result**: PASS

All 3 demo products follow the identical thin-shim pattern:

| Product | Import | Call |
|---------|--------|------|
| customer-360 | `from floe_orchestrator_dagster.loader import load_product_definitions` | `load_product_definitions("customer-360", PROJECT_DIR)` |
| financial-risk | `from floe_orchestrator_dagster.loader import load_product_definitions` | `load_product_definitions("financial-risk", PROJECT_DIR)` |
| iot-telemetry | `from floe_orchestrator_dagster.loader import load_product_definitions` | `load_product_definitions("iot-telemetry", PROJECT_DIR)` |

Each file is 17 lines. The pattern matches what `generate_entry_point_code()` produces (plugin.py:1132-1149).

## Check 5: Dead code in plugin.py

**Result**: PASS

- **Old 187-line template removed**: The diff shows 259 lines removed from `generate_entry_point_code()` (the inline template with `_export_dbt_to_iceberg`, `_load_iceberg_resources`, `_is_safe_identifier` etc.), replaced by a 45-line thin shim generator.
- **No remnant functions**: AST scan of plugin.py found no functions containing "export", "template", or "old" in their names (only `_create_iceberg_resources` at line 289, which is called at line 243 -- not dead code).
- **No dead imports**: The old inline template required `import re` and built complex string interpolation; the new method has no such imports.
- **`lineage_enabled` / `iceberg_enabled` params retained**: These are kept for backward compatibility with callers but documented as no-ops. This is intentional (not dead code) -- the loader handles feature detection at runtime via `compiled_artifacts.json`.
- **plugin.py total**: 1165 lines. The `generate_entry_point_code` method spans lines 1100-1165 (66 lines including docstring and file-write logic).

## Cross-Unit Wiring

**Result**: N/A (not final unit)

Units 6-9 are still planned. Cross-unit integration verification will occur at final ship. The runtime-loader unit's public API (`load_product_definitions`, `export_dbt_to_iceberg`) is consumed by:
- Demo products (definitions.py files)
- Unit/integration/E2E tests
- Code generator in plugin.py

No upstream units import from loader.py or export/iceberg.py, so no cross-unit regression risk.

---

## Findings

| Severity | File:Line | Description |
|----------|-----------|-------------|
| -- | -- | No findings. All wiring checks pass. |
