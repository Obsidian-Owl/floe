# Gate: Build

**Status**: FAIL
**Timestamp**: 2026-04-13T19:20:00+10:00

## Findings

### B1: Line too long (E501) in dbt_utils.py:145

```
tests/e2e/dbt_utils.py:145:101 — E501 Line too long (102 > 100)
```

Line: `logger.warning("Could not load table %s for S3 location: %s", fqn, type(exc).__name__)`

### B2: Line too long (E501) in test_iceberg_purge.py:309

```
tests/unit/test_iceberg_purge.py:309:101 — E501 Line too long (102 > 100)
```

Line: `f"Expected 2 delete_objects calls (one per page), got {mock_s3.delete_objects.call_count}"`

## Typecheck

**Status**: PASS — `Success: no issues found in 314 source files`
