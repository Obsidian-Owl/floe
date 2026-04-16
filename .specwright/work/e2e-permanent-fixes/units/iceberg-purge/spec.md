# Spec: Iceberg Table Purge

## Acceptance Criteria

### AC-1: purge_table replaces drop_table
`_purge_iceberg_namespace()` in `tests/e2e/dbt_utils.py` MUST call `catalog.purge_table(fqn)` instead of `catalog.drop_table(fqn)`. This sends `purgeRequested=true` to the Polaris REST API, requesting server-side cleanup of data and metadata files.

**How to verify:** AST or text inspection of `dbt_utils.py` confirms `purge_table` call, no `drop_table` call in the table-dropping loop.

### AC-2: S3 prefix deletion after catalog purge
After calling `purge_table`, the function MUST delete all objects under the table's S3 prefix in MinIO. This is the belt-and-suspenders layer because Polaris purge is unreliable (bugs #1195, #1448).

**How to verify:** The function contains S3 list+delete logic targeting the table's prefix path.

### AC-3: S3 deletion handles pagination
The S3 object listing MUST handle pagination via `ContinuationToken` / `IsTruncated`. A single `list_objects_v2` call returns at most 1000 objects.

**How to verify:** The S3 cleanup code has a loop that checks for truncation and continues with the continuation token.

### AC-4: S3 cleanup uses httpx or existing catalog session
The S3 cleanup MUST NOT add boto3 as an explicit dependency. It MUST use httpx (explicit dep) or the PyIceberg catalog's existing HTTP session for S3 API calls.

**How to verify:** No new boto3 import in `dbt_utils.py`. S3 calls use httpx or equivalent.

### AC-5: Cleanup failures are non-fatal
Both `purge_table` and S3 prefix deletion MUST catch exceptions and log warnings without raising. The function's contract is best-effort cleanup — dbt will create fresh tables regardless.

**How to verify:** All cleanup operations are wrapped in try/except with logging. No unhandled exceptions escape.

### AC-6: Namespace drop preserved
The existing namespace drop after table purge (added in PR #227) MUST be preserved. The sequence is: purge tables → delete S3 prefixes → drop namespace.

**How to verify:** `catalog.drop_namespace(namespace)` call remains after the table purge loop.
