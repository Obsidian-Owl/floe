# Context: Config Single Source of Truth

baselineCommit: f1f1e25c00fe64845da9166b06c9b4654670bd8d

## Problem
Config values are defined in `manifest.yaml` then independently redefined in test infrastructure. `test-e2e.sh` hardcodes `MINIO_ENDPOINT = 'http://floe-platform-minio:9000'`. `conftest.py` has fallback `warehouse: "floe-e2e"` that may diverge from manifest.

## Key Files
- `testing/ci/test-e2e.sh:458-486` — hardcoded MINIO_ENDPOINT and table-default.* properties
- `testing/ci/extract-manifest-config.py:43-60` — extracts manifest values to env vars
- `tests/e2e/conftest.py:36-97` — `_read_manifest_config()` with fallback values
- `demo/manifest.yaml:44-63` — canonical config source
- `charts/floe-platform/values-test.yaml:155-168` — bootstrap catalog config

## Technical Facts
- `extract-manifest-config.py` already extracts bucket, region, path_style_access — but NOT S3 endpoint
- `conftest.py:_read_manifest_config()` already reads from manifest — but has fallback to hardcoded values
- `floe-e2e` catalog name appears in 19 files — do NOT rename, instead ensure manifest matches
- Manifest `warehouse: floe-demo` vs values-test `catalogName: "floe-e2e"` — need alignment
- `table-default.s3.endpoint` in test-e2e.sh is the K8s-internal MinIO hostname — this IS correct for in-cluster use, but should come from manifest storage config, not be hardcoded

## Gotchas
- The manifest storage.config.endpoint IS a K8s hostname (`http://floe-platform-minio:9000`) — so extracting it from manifest gives the same value, but through the right channel
- Changing fallback behavior in conftest.py affects all E2E tests — fail-fast is better than wrong-values
- `_manifest_cfg` is computed at module import time — import failure = conftest load failure = all E2E tests skip
