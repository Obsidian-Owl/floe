# Context: Iceberg Table Purge

baselineCommit: f1f1e25c00fe64845da9166b06c9b4654670bd8d

## Problem
`_purge_iceberg_namespace()` in `tests/e2e/dbt_utils.py` calls `catalog.drop_table(fqn)` which removes the Polaris catalog entry but leaves parquet data and metadata JSON files in MinIO. dbt re-seed encounters stale file references → HTTP 404 errors.

## Key Files
- `tests/e2e/dbt_utils.py:73-108` — `_purge_iceberg_namespace()` (the function to modify)
- `tests/e2e/dbt_utils.py:25-70` — `_get_polaris_catalog()` (provides catalog + S3 config)
- `tests/e2e/tests/test_dbt_pipeline_fixture.py` — static analysis tests for fixture structure

## Technical Facts
- PyIceberg 0.11.0rc2 `RestCatalog.purge_table()` sends `purgeRequested=true` (verified)
- Base `Catalog.purge_table()` is a pass-through to `drop_table()` — only REST catalog does real purge
- Polaris bugs #1195, #1448: server-side purge unreliable for metadata files
- `list_objects_v2` returns max 1000 objects — must paginate with `ContinuationToken`
- httpx IS an explicit dependency; boto3 is transitive only — prefer httpx for S3 API
- MinIO S3 API is compatible with AWS S3 API (ListObjectsV2, DeleteObjects)
- `_get_polaris_catalog()` already has MinIO endpoint in its config (`s3.endpoint`)

## Gotchas
- P26: Purge Iceberg tables via catalog API before dbt seed/run
- Namespace drop after table drops already implemented (PR #227)
- S3 prefix pattern: `{namespace}/{table_name}/` under the bucket configured in Polaris
