# Spec: Per-Model Lineage Emission

## Description

Add per-dbt-model OpenLineage START/COMPLETE emission inside `compile_pipeline()`,
completing the 4 required emission points. The emitter and model list are already
in scope — this adds a loop with two emit calls per model.

## Acceptance Criteria

### AC-1: Per-model START and COMPLETE events emitted during compilation

For each model in `transforms.models`, `compile_pipeline()` emits a START event
followed by a COMPLETE event using the `SyncLineageEmitter`.

**Testable conditions:**
- After `compile_pipeline()` runs, Marquez has jobs with `model.` in the name
  in the `floe.compilation` namespace.
- Each model job has both a START (RUNNING/NEW) and COMPLETE state.
- The number of model jobs matches `len(transforms.models)`.

### AC-2: Job name format uses `model.floe.{model.name}`

Per-model job names follow the `model.floe.{name}` convention (consistent with
enforcement code at `stages.py:526`).

**Testable conditions:**
- Unit test: mock the emitter, call `compile_pipeline()`, verify `emit_start`
  was called with `job_name` matching `model.floe.{name}` for each model.
- Job names match the E2E test's `"model."` check pattern.

### AC-3: Per-model emission failures are non-blocking

A failure emitting for one model must not prevent emission for other models or
abort compilation. Failures are logged with `type(exc).__name__` only (CWE-532).

**Testable conditions:**
- Unit test: configure emitter to raise on one specific model's emit_start,
  verify compilation still succeeds and other models still emit.
- Log output contains `lineage_model_emit_failed` with model name but no
  exception details.

### AC-4: `test_openlineage_four_emission_points` passes

The existing E2E test validates all 4 emission points (pipeline START/COMPLETE +
model START/COMPLETE) without modification.

**Testable conditions:**
- `test_openlineage_four_emission_points` passes against the live Marquez instance.
- `has_dbt_model_job` assertion succeeds (jobs with `model.` found).
- `has_pipeline_job` assertion succeeds (pipeline-level jobs found).
- Both START and COMPLETE run states present.
