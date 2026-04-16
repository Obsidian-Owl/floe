# Plan: Unit 2 — OpenLineage parentRun Wiring

## Tasks

1. Add `from uuid import UUID as _UUID` import (if not already present)
2. Before the `extract_dbt_model_lineage()` call, convert Dagster run ID: `dagster_parent_id = _UUID(context.run.run_id)`
3. Pass `dagster_parent_id` instead of `run_id` to `extract_dbt_model_lineage()`
4. Add comment explaining the dual-ID pattern
5. Verify ruff compliance

## File change map

| File | Action | Lines |
|------|--------|-------|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | EDIT — modify call site + add import | ~line 582, imports section |

## Verification

```bash
# Lint check
cd plugins/floe-orchestrator-dagster
uv run ruff check src/floe_orchestrator_dagster/plugin.py

# Confirm change
grep -n "dagster_parent_id\|context.run.run_id" src/floe_orchestrator_dagster/plugin.py
```
