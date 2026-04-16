# Spec: Unit 2 — OpenLineage parentRun Wiring

## Acceptance Criteria

### AC-1: Per-model lineage events use Dagster run ID as parent

`extract_dbt_model_lineage()` receives `UUID(context.run.run_id)` (the Dagster orchestrator run UUID) as its `parent_run_id` parameter, not the asset-level OpenLineage UUID from `lineage.emit_start()`.

**How to verify**: Read `plugin.py` at the call site. The second argument to `extract_dbt_model_lineage()` must be derived from `context.run.run_id`, not from `run_id` (the `emit_start()` return value).

### AC-2: Asset lifecycle events unchanged

`lineage.emit_start()`, `lineage.emit_fail()`, and `lineage.emit_complete()` continue to use the asset-level `run_id` (from `emit_start()`). Only `extract_dbt_model_lineage()` uses the Dagster run ID.

**How to verify**: No changes to `emit_start`, `emit_fail`, or `emit_complete` calls. Only the `extract_dbt_model_lineage` call changes.

### AC-3: Code comment explains dual-ID pattern

A comment at the call site explains why two different UUIDs are used:
- Asset-level OL UUID for lifecycle (start/fail/complete)
- Dagster run UUID for parent lineage (per-model events)

**How to verify**: Comment present near the modified line.

### AC-4: UUID conversion is safe under exception handler

The `UUID(context.run.run_id)` conversion is within the existing `try/except Exception` block (lines 581-588), so a malformed run ID would be logged as a warning, not crash the asset.

**How to verify**: The modified code is inside the existing try block. No new exception handling added.

### AC-5: Ruff E501 compliance

All modified or added lines are within the 100-character line length limit.

**How to verify**: `ruff check plugin.py` passes with no E501 errors on the modified lines.
