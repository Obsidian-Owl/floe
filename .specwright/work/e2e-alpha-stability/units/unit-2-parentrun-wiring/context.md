# Context: Unit 2 — OpenLineage parentRun Wiring

## Scope

Fix the parent run ID passed to `extract_dbt_model_lineage()` in `plugin.py`. One-line caller fix.

## Files to modify

| File | Change |
|------|--------|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | Line ~582: pass `UUID(context.run.run_id)` instead of `run_id` |

## Key references

- `plugin.py:554-565` — `run_id` assigned from `lineage.emit_start()` (asset-level OL UUID)
- `plugin.py:582-584` — call site to fix
- `plugin.py:587-588` — `except Exception` handler (catches UUID conversion errors)
- `lineage_extraction.py:176` — parameter named `parent_run_id` (confirms semantics)
- `facets.py:228-263` — `ParentRunFacetBuilder.from_parent()` (correctly implemented)
- OpenLineage ParentRunFacet spec: parent = orchestrator run, not sibling asset event

## Dual-ID pattern (architect WARN-2)

The asset-level OL UUID (`run_id` from `emit_start()`) tracks the start/fail/complete lifecycle.
The Dagster run UUID (`context.run.run_id`) is the parent for per-model lineage events.
These are different concepts — add a comment explaining this at the call site.

## E2E test fixed

- #3: `test_openlineage_four_emission_points` — validates parentRun facet via Marquez events API

## Ruff compliance

- Import `from uuid import UUID as _UUID` — use alias to avoid shadowing any existing `UUID` usage
- Line length: ensure the modified lines stay under E501 limit
