# Gate: Tests

**Status**: BLOCK
**Timestamp**: 2026-03-28T04:45:00Z

## Results

- Unit tests (root): 186/186 passed (6.90s)
- Contract tests: 860/860 passed, 1 xfailed (6.97s)
- Plugin unit tests (floe-orchestrator-dagster): 22/31 passed, **9 FAILED** (0.59s)
- Helm unit tests: 142/142 passed

## Findings

| Severity | Count |
|----------|-------|
| BLOCK | 1 |
| WARN | 0 |
| INFO | 0 |

### BLOCK-1: 9 lineage emission unit tests fail

- **File**: `plugins/floe-orchestrator-dagster/tests/unit/test_asset_lineage_emission.py`
- **Root cause**: `plugin.py:585` changed to `UUID(context.run.run_id)` but mock fixture
  `context.run.run_id` returns MagicMock (not UUID string). `ValueError` silently caught
  by `except Exception` at line 594, preventing `extract_dbt_model_lineage` from being called.
- **Failed tests**: TestExtractAndEmitLineageEvents (7 tests) + TestLineageFailureDoesNotBlockDbt (2 tests)
- **Fix**: Update `mock_context` fixture: `context.run.run_id = str(uuid4())`
