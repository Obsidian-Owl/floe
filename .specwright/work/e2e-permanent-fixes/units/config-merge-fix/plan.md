# Plan: Config Merge Fix (Unit 7)

## Task Breakdown

### Task 1: Remove `table-default.s3.endpoint` from Polaris bootstrap (AC-1)

Remove the `table-default.s3.endpoint` property from the bootstrap job template. Keep `s3.endpoint` (catalog-level) and `storageConfigInfo.endpoint` (storage config).

**File change map:**
- MODIFY `charts/floe-platform/templates/job-polaris-bootstrap.yaml` (remove table-default.s3.endpoint line)

**Acceptance criteria:** AC-1

### Task 2: Add client endpoint override in Polaris catalog plugin (AC-5)

Add a post-table-load hook in the Polaris catalog plugin that re-applies the client-side `s3.endpoint` to the table's FileIO properties, ensuring client config always wins.

**File change map:**
- MODIFY `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` (add endpoint override after table load)

**Acceptance criteria:** AC-5

### Task 3: Helm unit tests for bootstrap validation (AC-4)

Add/update helm unittest that asserts `table-default.s3.endpoint` is NOT present in the rendered bootstrap job.

**File change map:**
- MODIFY or CREATE `charts/floe-platform/tests/` (helm unittest file for bootstrap job)

**Acceptance criteria:** AC-4

### Task 4: Contract test for endpoint preservation (AC-3)

Contract test tracing S3 endpoint from CompiledArtifacts through PolarisCatalogPlugin.connect() config dict.

**File change map:**
- CREATE `tests/contract/test_s3_endpoint_preservation.py`

**Acceptance criteria:** AC-3

### Task 5: Integration test — client endpoint survives table load (AC-2)

Integration test connecting to real Polaris, loading a table, and asserting the FileIO uses the client endpoint.

**File change map:**
- CREATE `plugins/floe-catalog-polaris/tests/integration/test_s3_endpoint_integrity.py`

**Acceptance criteria:** AC-2

## Task Dependencies

```
Task 1 (remove table-default) ──┐
                                 ├──► Task 3 (Helm unit tests)
Task 2 (client override)  ──────┤
                                 ├──► Task 4 (contract test)
                                 └──► Task 5 (integration test)
```

Tasks 1 and 2 are independent. Tasks 3-5 depend on both.

## As-Built Notes

### Implementation Decisions

1. **Helm template fix (Task 1)**: Removed all 5 `table-default.s3.*` properties from `job-polaris-bootstrap.yaml` — endpoint, path-style-access, access-key-id, secret-access-key, region. Kept catalog-level `s3.endpoint` and `storageConfigInfo` for Polaris server-side access.

2. **Plugin endpoint override (Task 2)**: Added `load_table_with_client_endpoint()` method to `PolarisCatalogPlugin` rather than monkey-patching `_fetch_config`. The method loads a table normally, then re-applies the stored client `s3.endpoint` to `table.io.properties`. The `connect()` method stores `s3.endpoint` from the config dict in `_client_s3_endpoint`.

3. **Error handling**: `load_table_with_client_endpoint()` raises `CatalogUnavailableError` when called without a prior `connect()`. When no client endpoint was stored (`_client_s3_endpoint is None`), server endpoint is left untouched.

### Actual File Paths

- `charts/floe-platform/templates/job-polaris-bootstrap.yaml` — table-default removal
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` — endpoint override method
- `plugins/floe-catalog-polaris/tests/unit/test_client_endpoint_override.py` — 6 unit tests (AC-5)
- `charts/floe-platform/tests/bootstrap_job_test.yaml` — 2 regression tests (AC-4)
- `tests/contract/test_s3_endpoint_preservation.py` — 4 contract tests (AC-3)
- `plugins/floe-catalog-polaris/tests/integration/test_s3_endpoint_integrity.py` — 2 integration tests (AC-2)

### Plan Deviations

- None. All 5 tasks implemented as planned.
