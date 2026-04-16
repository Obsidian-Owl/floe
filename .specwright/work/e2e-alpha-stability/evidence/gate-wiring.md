# Gate: Wiring

**Status**: BLOCK
**Timestamp**: 2026-03-28T04:45:00Z

## Results

- Import resolution: PASS
- Circular imports: PASS
- Cross-package boundaries: PASS
- Test tier placement: PASS
- Helm values/template consistency: PASS
- Shell script quality: PASS
- Demo profiles consistency: PASS
- Mock fixture compatibility: **BLOCK**

## Findings

| Severity | Count |
|----------|-------|
| BLOCK | 1 |
| WARN | 0 |
| INFO | 0 |

### BLOCK-1: Mock fixture incompatible with production code change

- **Production**: `plugin.py:585` — `dagster_parent_id = UUID(context.run.run_id)`
- **Test**: `test_asset_lineage_emission.py:108-120` — `mock_context.run.run_id` is MagicMock
- **Impact**: 9 tests silently pass wrong code path (exception swallowed)
- **Fix**: Set `mock_context.run.run_id = str(uuid4())` in fixture
