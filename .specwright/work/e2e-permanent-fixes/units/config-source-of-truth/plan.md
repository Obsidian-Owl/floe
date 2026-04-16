# Plan: Config Single Source of Truth

## Tasks

### Task 1: Add S3 endpoint extraction to extract-manifest-config.py
Add extraction of `plugins.storage.config.endpoint` as `MANIFEST_S3_ENDPOINT`.

**File change map:**
| File | Change |
|---|---|
| `testing/ci/extract-manifest-config.py` | Add S3 endpoint extraction |

### Task 2: Replace hardcoded MINIO_ENDPOINT in test-e2e.sh
Replace the hardcoded `MINIO_ENDPOINT = 'http://floe-platform-minio:9000'` in the catalog creation Python block with the extracted manifest value.

**File change map:**
| File | Change |
|---|---|
| `testing/ci/test-e2e.sh:458-486` | Use `MANIFEST_S3_ENDPOINT` variable instead of hardcoded endpoint |

### Task 3: Remove fallback values in conftest.py
Replace the warning+fallback pattern with a clear error when manifest is missing.

**File change map:**
| File | Change |
|---|---|
| `tests/e2e/conftest.py:54-71` | Remove fallback dict, raise error on missing manifest |

### Task 4: Align manifest warehouse with values-test.yaml
Check if `demo/manifest.yaml` warehouse matches `values-test.yaml` catalogName. Update whichever is the derived value to match the source of truth.

**File change map:**
| File | Change |
|---|---|
| `demo/manifest.yaml` | May need warehouse alignment |
| `charts/floe-platform/values-test.yaml` | May need catalogName alignment |
