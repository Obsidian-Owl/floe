# Plan: Iceberg Table Purge

## Tasks

### Task 1: Replace drop_table with purge_table and add S3 cleanup
Modify `_purge_iceberg_namespace()` in `tests/e2e/dbt_utils.py`:

1. Change `catalog.drop_table(fqn)` to `catalog.purge_table(fqn)`
2. After purging each table, delete all S3 objects under the table's prefix
3. Use httpx for S3 API calls (ListObjectsV2 + DeleteObjects XML API)
4. Handle pagination with ContinuationToken loop
5. Wrap all cleanup in try/except with logger.warning

**File change map:**
| File | Change |
|---|---|
| `tests/e2e/dbt_utils.py` | Modify `_purge_iceberg_namespace()`: purge_table + S3 cleanup |

**Signatures:**
```python
def _delete_s3_prefix(
    endpoint: str,
    bucket: str,
    prefix: str,
    access_key: str,
    secret_key: str,
    region: str,
) -> None:
    """Delete all objects under an S3 prefix via MinIO-compatible API."""
    ...
```

The S3 connection details come from the same config used in `_get_polaris_catalog()` — the `s3.endpoint`, `s3.access-key-id`, `s3.secret-access-key`, and bucket from the catalog's `default-base-location`.
