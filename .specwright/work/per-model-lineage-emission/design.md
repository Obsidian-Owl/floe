# Design: Per-Model Lineage Emission

## Overview

Add per-dbt-model OpenLineage emission (START/COMPLETE) inside `compile_pipeline()`.
The emitter and model list are already in scope — this is a loop + two emit calls per model.

## Approach

After `transforms = resolve_transform_compute(...)` resolves models (line 380), and before
the GENERATE stage (line 562), iterate `transforms.models` and emit START/COMPLETE for each.

```python
# Per-model lineage emission (non-blocking)
for model in transforms.models:
    model_job_name = f"model.floe.{model.name}"
    try:
        model_run_id = emitter.emit_start(job_name=model_job_name)
        emitter.emit_complete(model_run_id, model_job_name)
    except Exception as _model_err:
        log.warning("lineage_model_emit_failed", model=model.name, error=type(_model_err).__name__)
```

**Why START then immediate COMPLETE**: During compilation, models are resolved but not
executed. The emission records that the model was "compiled" (resolved, validated). The
actual execution happens later at Dagster runtime (which has its own lineage emission).
Compilation-time events are metadata-only — no real I/O or timing to capture.

**Job name format**: `model.floe.{model.name}` reuses the format already at line 526 for
enforcement. This matches the test's `"model."` check.

## Integration Points

- **Emitter**: Already created at line 329, in scope throughout the `try` block
- **Models**: `transforms.models` available after line 380
- **Placement**: After Stage 5 (COMPILE/ENFORCE) but before Stage 6 (GENERATE), alongside
  the existing enforcement model iteration. Or directly after RESOLVE — doesn't matter
  since it's non-blocking metadata emission.

## Blast Radius

| Module | Scope | Propagation |
|--------|-------|-------------|
| `stages.py` | ~8 lines added in model iteration | Local — failure logged, never raises |
| E2E tests | No changes needed | N/A — test already expects this |
| `SyncLineageEmitter` | No changes | N/A |
| `emitter.py` | No changes | N/A |
| Marquez | Receives more events | Local — additional jobs in `floe.compilation` namespace |

**NOT changed**: emitter API, transport layer, manifest schema, test assertions,
Dagster runtime emission, `CompiledArtifacts` contract.

## Alternatives Considered

1. **Emit with ParentRunFacet linking to pipeline run**: More correct OpenLineage semantics
   (model runs are children of pipeline run). Adds ~3 lines for facet construction.
   Slightly overengineered for compilation-time metadata emission — save for when runtime
   lineage needs parent linkage. **Rejected: simplicity.**

2. **Emit inside the RESOLVE stage span**: Would give OTel trace correlation for model
   emissions. But the RESOLVE span is already closed by line 393. Would need restructuring.
   **Rejected: scope creep.**

3. **Skip per-model emission during compilation, only emit at runtime**: This is the current
   state and it's failing the test. The test explicitly requires compilation-time per-model
   emission. **Rejected: test requirement.**

## Risk Assessment

- **Low risk**: Non-blocking emission, failure logged and swallowed
- **No new dependencies**: Uses existing emitter + existing model list
- **No API changes**: Pure addition, no signature changes
- **Performance**: Negligible — N HTTP POSTs for N models, but emitter already does this for
  pipeline START/COMPLETE. In demo there are ~6 models.
