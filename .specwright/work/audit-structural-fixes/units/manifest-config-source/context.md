# Context — Unit 2: Manifest Config Source of Truth

baselineCommit: e1dbdb3f64b2fec5574b3c006645173418fc5800

## Summary

Eliminate config value hardcoding in test infrastructure. Create a manifest
extractor that `test-e2e.sh` and `conftest.py` use instead of defining their
own values.

## Key Files

### Must Create
- `testing/ci/extract-manifest-config.py` — reads manifest.yaml, outputs shell vars

### Must Modify
- `testing/ci/test-e2e.sh:388,416-418,455-489` — replace hardcoded values with manifest-derived
- `tests/e2e/conftest.py` — replace hardcoded credential/scope defaults

### Source of Truth
- `demo/manifest.yaml` — platform config (bucket, region, warehouse, oauth, endpoints)

## Current Divergences

| Config | manifest.yaml | test-e2e.sh | Line |
|--------|--------------|-------------|------|
| Bucket | `floe-data` | `floe-iceberg` | 388 |
| Region | `us-east-1` | `us-east-1` (hardcoded) | 470,474 |
| path_style_access | `true` | `true` (hardcoded) | 471,475 |
| OAuth scope | `PRINCIPAL_ROLE:ALL` | not passed | — |
| OAuth client_id | `demo-admin` | `demo-admin` (hardcoded) | 417 |

## Legitimate Divergences (NOT config drift)
- S3 endpoint: K8s-internal (`http://floe-platform-minio:9000`) vs port-forwarded (`http://localhost:9000`)
- Polaris URI: K8s-internal vs `localhost:8181`
- These are TRANSPORT differences, not config values

## Gotchas
- `test-e2e.sh` uses env var defaults (`${VAR:-default}`) — extractor vars slot into the default position
- Catalog creation JSON (lines 455-489) builds the payload with Python inline — the manifest-derived
  env vars must be available when this runs
- `conftest.py` credential reading: `os.environ.get("POLARIS_CREDENTIAL", "demo-admin:demo-secret")`
  should become `os.environ.get("POLARIS_CREDENTIAL", f"{manifest_client_id}:{manifest_client_secret}")`
