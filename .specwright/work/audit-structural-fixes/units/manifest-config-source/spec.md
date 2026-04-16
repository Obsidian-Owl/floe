# Spec — Unit 2: Manifest Config Source of Truth

## Overview

Eliminate config value hardcoding in test infrastructure by creating a manifest
extractor. All configurable values in `test-e2e.sh` and `conftest.py` derive
from `demo/manifest.yaml`.

## Acceptance Criteria

### AC-1: Manifest extractor outputs shell-evaluable config

A script `testing/ci/extract-manifest-config.py` MUST read `demo/manifest.yaml`
and output shell-evaluable `export VAR='value'` lines for all config values
used by test infrastructure.

**Verifiable conditions:**

1. Script accepts manifest path as argument: `python3 extract-manifest-config.py demo/manifest.yaml`
2. Output is valid shell: `eval "$(python3 ...)"` sets environment variables.
3. Exports: `MANIFEST_BUCKET`, `MANIFEST_REGION`, `MANIFEST_PATH_STYLE_ACCESS`,
   `MANIFEST_WAREHOUSE`, `MANIFEST_OAUTH_CLIENT_ID`, `MANIFEST_OAUTH_SCOPE`.
4. Values match `demo/manifest.yaml` content exactly.
5. Script fails with clear error if `plugins.storage` or `plugins.catalog` is missing.
6. Script fails with clear error if manifest file not found.
7. Single-quoted output prevents shell injection.

### AC-2: test-e2e.sh reads config from manifest

`testing/ci/test-e2e.sh` MUST source the manifest extractor and use its output
as defaults instead of hardcoded values.

**Verifiable conditions:**

1. `test-e2e.sh` calls `eval "$(python3 ... extract-manifest-config.py ...)"` early in execution.
2. `MINIO_BUCKET` defaults to `${MANIFEST_BUCKET}` (not `floe-iceberg`).
3. `POLARIS_CATALOG` defaults to `${MANIFEST_WAREHOUSE}` (not hardcoded).
4. `POLARIS_CLIENT_ID` defaults to `${MANIFEST_OAUTH_CLIENT_ID}` (not hardcoded).
5. Catalog creation JSON uses `MANIFEST_REGION` and `MANIFEST_PATH_STYLE_ACCESS`
   instead of hardcoded `'us-east-1'` and `'true'`.
6. Environment variable overrides (`MINIO_BUCKET=custom ./test-e2e.sh`) still work.
7. Changing `bucket: floe-data` in manifest.yaml → test-e2e.sh uses `floe-data`.

### AC-3: conftest.py derives credential defaults from manifest

`tests/e2e/conftest.py` MUST read credential defaults from `demo/manifest.yaml`
instead of hardcoding `demo-admin:demo-secret` and `PRINCIPAL_ROLE:ALL`.

**Verifiable conditions:**

1. A `_read_manifest_config()` helper reads `demo/manifest.yaml`.
2. Default `POLARIS_CREDENTIAL` is derived from manifest `oauth2.client_id` and `oauth2.client_secret`.
3. Default OAuth `scope` is derived from manifest `oauth2.scope`.
4. Environment variable overrides still take precedence.
5. If manifest is not found, falls back to current defaults with a warning.
