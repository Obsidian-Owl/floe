# Spec: Config Single Source of Truth

## Acceptance Criteria

### AC-1: test-e2e.sh reads S3 endpoint from manifest
The Polaris catalog creation in `testing/ci/test-e2e.sh` MUST read the S3 endpoint from manifest config via `extract-manifest-config.py`, not hardcode `MINIO_ENDPOINT = 'http://floe-platform-minio:9000'`.

**How to verify:** No hardcoded `http://floe-platform-minio:9000` string literal in the catalog creation Python block. The endpoint value comes from an extracted manifest variable.

### AC-2: extract-manifest-config.py exports S3 endpoint
`testing/ci/extract-manifest-config.py` MUST extract the storage S3 endpoint from `plugins.storage.config.endpoint` and export it as `MANIFEST_S3_ENDPOINT`.

**How to verify:** Script outputs `MANIFEST_S3_ENDPOINT=...` line. The value matches `demo/manifest.yaml` `plugins.storage.config.endpoint`.

### AC-3: conftest.py fails on missing manifest
`tests/e2e/conftest.py` `_read_manifest_config()` MUST raise an error (via `pytest.fail` or exception) when the manifest file is not found, instead of silently falling back to hardcoded values.

**How to verify:** The fallback dict and `warnings.warn` path are removed. A missing manifest causes a clear error message.

### AC-4: conftest.py warehouse matches manifest
The warehouse value used by E2E test fixtures MUST come from the manifest, not a hardcoded fallback. When manifest says `floe-e2e`, tests use `floe-e2e`. When it says `floe-demo`, tests use `floe-demo`.

**How to verify:** No hardcoded `"floe-e2e"` warehouse string in `_read_manifest_config()` fallback. The value is always read from manifest YAML.

### AC-5: Manifest and values-test.yaml catalog name aligned
`demo/manifest.yaml` `plugins.catalog.config.warehouse` MUST match `charts/floe-platform/values-test.yaml` `polaris.bootstrap.catalogName`. If they differ, one must be updated to match the other.

**How to verify:** Both files contain the same warehouse/catalog name string.
