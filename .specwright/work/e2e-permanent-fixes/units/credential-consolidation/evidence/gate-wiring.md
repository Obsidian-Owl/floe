# Gate: Wiring — credential-consolidation

**Status**: PASS
**Timestamp**: 2026-04-06T18:17:00Z

## Results

- **Module imports**: All 3 functions resolve and return correct values
- **Consumer wiring**: 6 consumer files import from `testing.fixtures.credentials`
  - `tests/e2e/conftest.py` → get_minio_credentials, get_polaris_credentials
  - `tests/e2e/dbt_utils.py` → get_minio_credentials, get_polaris_credentials
  - `testing/fixtures/minio.py` → get_minio_credentials
  - `packages/floe-iceberg/tests/integration/conftest.py` → get_minio_credentials
  - `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py` → get_minio_credentials
  - `plugins/floe-orchestrator-dagster/tests/integration/conftest.py` → get_minio_credentials, get_polaris_credentials
- **Default values**: Match manifest.yaml (demo-admin, demo-secret, Polaris URI)

## Findings

None.
