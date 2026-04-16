# Context: OpenLineage Facet Key + Template Lineage

baselineCommit: f1f1e25c00fe64845da9166b06c9b4654670bd8d

## Problem
1. `lineage_extraction.py:240` uses `"parentRun"` facet key but OpenLineage spec uses `"parent"`
2. Template-generated `definitions.py` asset function doesn't declare `lineage` parameter and never calls `emit_start()`/`emit_complete()`

## Key Files
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py:240` — `"parentRun"` key
- `plugins/floe-orchestrator-dagster/tests/unit/test_lineage_extraction.py:502-598` — unit tests assert `"parentRun"`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1317-1363` — template generation
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1344` — asset function signature (no lineage param)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1160-1162` — lineage_resource wired but unused
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:556-618` — dynamic path (full lineage)
- `tests/e2e/test_observability.py:1085-1095` — E2E test checks both `"parentRun"` and `"parent"` (defensive)
- `demo/customer-360/definitions.py:148-162` — current generated output (no lineage)

## Technical Facts
- OpenLineage spec renamed `"parentRun"` → `"parent"` for the facet key
- Marquez stores whatever key arrives — E2E test already checks both keys
- Template asset function: `def {safe_name}_dbt_assets(context, dbt: DbtCliResource)`
- Dynamic path takes: `lineage: LineageResource` and calls emit_start/emit_complete
- The template should add a simplified lineage wrapper, NOT replicate the full 62-line dynamic path
- Template already wires lineage resource via `try_create_lineage_resource(None)` in defs
- lineage_enabled is a boolean computed from whether lineage plugins are configured
- Generated definitions.py files are checked into git under `demo/*/definitions.py`

## Gotchas
- Unit tests for lineage_extraction assert `"parentRun"` — must update in sync
- PR must regenerate demo definitions via `floe compile --generate-definitions`
- Template is f-string Python code inside Python — careful with escaping
- The simplified template lineage should just call emit_start before dbt.cli and emit_complete after — no per-model extraction (that's the dynamic path's job)
