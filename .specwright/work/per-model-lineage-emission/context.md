# Context: Per-Model Lineage Emission

## Problem

`test_openlineage_four_emission_points` expects 4 emission points:
1. Pipeline START (compile_pipeline level) — **implemented** at `stages.py:341`
2. Pipeline COMPLETE — **implemented** at `stages.py:608`
3. Per-dbt-model START — **missing**
4. Per-dbt-model COMPLETE — **missing**

The test checks Marquez for jobs with `dbt`, `model.`, `stg_`, or `mart_` in the name.
Currently only pipeline-level jobs (`customer-360`) exist in `floe.compilation` namespace.

## Key Files

- `packages/floe-core/src/floe_core/compilation/stages.py` — `compile_pipeline()`, lines 246-633
  - Emitter created at line 329: `create_sync_emitter(_lineage_config, default_namespace="floe.compilation")`
  - Pipeline START at line 341
  - `transforms.models` available after line 380 (from `resolve_transform_compute()`)
  - Model iteration for enforcement at line 525 (governance only)
  - Pipeline COMPLETE at line 608
- `packages/floe-core/src/floe_core/lineage/emitter.py` — `SyncLineageEmitter` class, lines 195-314
  - `emit_start(job_name, ...)` returns `UUID`
  - `emit_complete(run_id, job_name, ...)`
  - `emit_fail(run_id, job_name, error_message, ...)`
- `packages/floe-core/src/floe_core/compilation/resolver.py` — `resolve_transform_compute()` returns transforms with `.models` list
- `tests/e2e/test_observability.py:889-1022` — test expectations

## Emitter API

```python
emitter.emit_start(job_name="model.floe.stg_crm_customers") -> UUID
emitter.emit_complete(run_id, "model.floe.stg_crm_customers")
```

The emitter is already in scope inside `compile_pipeline()` where `transforms.models` is iterated.

## Test Matching Logic

```python
has_dbt_model_job = any(
    "dbt" in name.lower() or "model." in name.lower()
    or "stg_" in name.lower() or "mart_" in name.lower()
    for name in job_names
)
```

Job name format `model.floe.{model.name}` (already used at line 526) matches `"model."` check.

## Gotchas

- CWE-532: All emission error handling must log `type(exc).__name__` only (constitution S-VI)
- Non-blocking: emission failures must not abort compilation
- Each model emit is a separate try/except (one model failure doesn't block others)
- Pipeline-level run_id should be passed as parent via ParentRunFacet (optional but good practice)
