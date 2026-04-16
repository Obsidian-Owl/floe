# Plan: Per-Model Lineage Emission

## Architecture Decisions

- Emit per-model events inside existing `compile_pipeline()` try block where emitter is in scope
- Place after COMPILE/ENFORCE stage (line ~560) and before GENERATE stage (line 562)
- Use `model.floe.{model.name}` job name format (matches enforcement at line 526)
- Each model gets its own try/except (non-blocking per AC-3)
- CWE-532: log `type(exc).__name__` only in error handler

## Task Breakdown

### Task 1: Add per-model emission loop and unit tests

**Files changed:**
- `packages/floe-core/src/floe_core/compilation/stages.py` — add model emission loop
- `packages/floe-core/tests/unit/test_lineage_config.py` — add unit tests for model emission

**Production code location:** Between enforcement (line ~560) and GENERATE stage (line 562)

**Unit test cases:**
- Emitter receives `emit_start` + `emit_complete` for each model in transforms
- Job names match `model.floe.{model.name}` format
- One model emission failure doesn't block others or abort compilation
- Error log uses `type(exc).__name__` (CWE-532)

**AC coverage:** AC-1, AC-2, AC-3

### Task 2: E2E verification

**No code changes** — verify `test_openlineage_four_emission_points` passes.

**AC coverage:** AC-4

## File Change Map

| File | Change Type | Scope |
|------|-------------|-------|
| `packages/floe-core/src/floe_core/compilation/stages.py` | Modify | ~8 lines: model emission loop after enforcement |
| `packages/floe-core/tests/unit/test_lineage_config.py` | Modify | Add 3-4 unit tests for model emission |

## Dependencies

- Task 1 must complete before Task 2 (production code needed for E2E to pass)

## As-Built Notes

### Plan Deviations

- Tests placed in `packages/floe-core/tests/integration/test_lineage_wiring.py` (integration tier) instead of `test_lineage_config.py` (unit tier). Rationale: tests invoke `compile_pipeline()` with real demo spec files, which is integration-level per project convention P60.
- 6 tests written instead of 3-4 planned: added `test_per_model_complete_uses_same_job_name_as_start` and `test_per_model_emission_uses_run_id_from_start` for stronger coverage of run ID correlation and job name consistency.

### Implementation Decisions

- CWE-532 log test uses structlog `PrintLogger` with `io.StringIO` buffer instead of `caplog` — structlog doesn't propagate to stdlib `logging` by default in this project.
- Production code is 11 lines (not 8 planned) due to multi-line `log.warning()` call for readability.

### Actual File Paths

| File | Change |
|------|--------|
| `packages/floe-core/src/floe_core/compilation/stages.py:562-572` | Per-model emission loop |
| `packages/floe-core/tests/integration/test_lineage_wiring.py` | 6 new tests in `TestPerModelLineageEmission` class |
