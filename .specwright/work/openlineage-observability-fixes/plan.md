# Plan: OpenLineage Observability Fixes

## Architecture Decisions

- Follow the OTel pattern: env var override for endpoint configuration
- `OPENLINEAGE_URL` is the standard OpenLineage env var (matches spec)
- Env var takes priority over manifest config (same as `OTEL_EXPORTER_OTLP_ENDPOINT`)
- Empty string env var treated as absent (consistent with OTel behavior)
- Test fixtures use save/restore pattern (same as existing OTel env vars)

## Task Breakdown

### Task 1: Add `OPENLINEAGE_URL` env var override to `_build_lineage_config()`

**Files changed:**
- `packages/floe-core/src/floe_core/compilation/stages.py` — `_build_lineage_config()` function

**Signature change:**
```python
# In _build_lineage_config(), after reading lineage config from manifest:
# Check OPENLINEAGE_URL env var override (same pattern as OTEL_EXPORTER_OTLP_ENDPOINT)
```

**Unit test file:**
- `packages/floe-core/tests/unit/test_lineage_config.py` (new or extend existing)

**Test cases:**
- Env var set → uses env var URL
- Env var unset → uses manifest URL
- Env var empty string → uses manifest URL
- Lineage disabled → returns None regardless of env var
- Manifest has no observability config → returns None regardless of env var

**AC coverage:** AC-1, AC-6

### Task 2: Set `OPENLINEAGE_URL` in E2E test fixtures

**Files changed:**
- `tests/e2e/conftest.py` — `seed_observability()` fixture
- `tests/conftest.py` — `compiled_artifacts()` fixture

**Changes in `seed_observability()`:**
- Save `OPENLINEAGE_URL` before mutation
- Set `OPENLINEAGE_URL=http://localhost:5100/api/v1/lineage`
- Restore in `finally` block (same pattern as OTel env vars)

**Changes in `compiled_artifacts()`:**
- Set `OPENLINEAGE_URL=http://localhost:5100/api/v1/lineage` before `compile_pipeline()`
- Derive `OTEL_SERVICE_NAME` from spec path (product directory name)
- Restore/remove both env vars after compilation

**AC coverage:** AC-2, AC-3

### Task 3: Verify all 5 E2E tests pass

**No code changes** — this is a verification task.

- Run `make test-e2e` or the specific observability test files
- Confirm all 5 tests pass
- If `test_structured_logs_with_trace_id` still fails, investigate structlog
  `cache_logger_on_first_use` and add diagnostic logging

**AC coverage:** AC-4, AC-5

## File Change Map

| File | Change Type | Scope |
|------|-------------|-------|
| `packages/floe-core/src/floe_core/compilation/stages.py` | Modify | Add env var check in `_build_lineage_config()` |
| `packages/floe-core/tests/unit/test_lineage_config.py` | Create/Modify | Unit tests for env var override |
| `tests/e2e/conftest.py` | Modify | `seed_observability()` — add `OPENLINEAGE_URL` save/set/restore |
| `tests/conftest.py` | Modify | `compiled_artifacts()` — add `OPENLINEAGE_URL` + `OTEL_SERVICE_NAME` |

## Dependencies

- Task 1 must complete before Task 3 (production code needed for tests to pass)
- Task 2 must complete before Task 3 (fixtures needed for E2E tests)
- Tasks 1 and 2 are independent of each other
