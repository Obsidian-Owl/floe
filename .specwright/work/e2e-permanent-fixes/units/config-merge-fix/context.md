# Context: Config Merge Fix (Unit 7)

## Key File Paths

### The 6-Layer Config Merge Chain
1. `demo/manifest.yaml:56-63` — defines `plugins.storage.config.endpoint`
2. `charts/floe-platform/templates/job-polaris-bootstrap.yaml:206-235` — sets `s3.endpoint`, `table-default.s3.endpoint`, and `storageConfigInfo.endpoint` (3 copies!)
3. `charts/floe-platform/templates/configmap-polaris.yaml:22-29` — `quarkus.s3.endpoint-override`
4. Polaris server returns `table-default.s3.endpoint` in table metadata
5. `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py:263-299` — builds catalog config for PyIceberg
6. PyIceberg `_fetch_config` merges: `server_defaults < client_props < server_overrides`

### Root Cause
- Bootstrap sets `table-default.s3.endpoint` = K8s-internal hostname
- PyIceberg treats `table-default.*` as server overrides (highest priority)
- Client-side `s3.endpoint` is silently replaced
- Result: S3 operations use K8s-internal hostname, fails from outside cluster

### Config Files
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/config.py:92-161` — PolarisCatalogConfig (no table-default handling)
- `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py:167-190` — S3 plugin builds FileIO with s3.endpoint
- `packages/floe-iceberg/manager.py:190-218` — Manager connects to catalog

### Test Evidence
- `tests/e2e/test_data_pipeline.py:165-205` — documents the bug and workaround
- `testing/ci/tests/test_e2e_sh_manifest_wiring.py` — tests manifest wiring for S3 config

## Gotchas
- `table-default.s3.endpoint` in bootstrap is CORRECT for Polaris server-side S3 access (Polaris itself needs to reach MinIO inside K8s). The fix is to NOT propagate it to table metadata.
- `s3.endpoint` (catalog-level, without `table-default.` prefix) is also used by Polaris but does NOT override PyIceberg client config
- The Polaris REST API returns table-default properties in the `config` field of the table response — PyIceberg applies these as overrides
- Removing `table-default.s3.endpoint` means Polaris tables won't have a default S3 endpoint in their metadata — clients MUST provide it via catalog config
- The floe catalog plugin already passes `s3.endpoint` in catalog config (Layer 5) — removing the server override means this client config will be used
