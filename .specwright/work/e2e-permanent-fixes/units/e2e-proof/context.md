# Context: E2E Proof (Unit 9)

## Purpose

This unit adds NO production code. It is purely E2E tests proving that units 5-8 have resolved the audit BLOCKERs. Each test maps directly to an audit finding.

## Audit Finding → E2E Test Mapping

| Audit Finding | Test | What it proves |
|---------------|------|----------------|
| DX-001 (generated code is full program) | `test_runtime_loader_e2e.py` | Thin definitions.py works end-to-end |
| DX-002 (two divergent paths) | `test_runtime_loader_e2e.py` | Single loader path produces working pipeline |
| DX-003 (silent failure) | `test_loud_failure_e2e.py` | Pipeline FAILS with clear error when Polaris down |
| CON-001 (inconsistent try_create_*) | `test_loud_failure_e2e.py` | Ingestion errors propagate (not swallowed) |
| DX-004 (S3 endpoint corruption) | `test_s3_endpoint_e2e.py` | Manifest endpoint reaches PyIceberg FileIO |
| DBT-001 (credentials in 31 files) | `test_credential_consistency_e2e.py` | Zero credential drift across all sources |

## Key File Paths

### Existing E2E tests (must not regress)
- `tests/e2e/test_demo_flow.py`
- `tests/e2e/test_data_pipeline.py`
- `tests/e2e/test_compile_deploy_materialize_e2e.py`
- `tests/e2e/test_asset_discovery.py`
- `tests/e2e/test_observability.py`
- 22 more E2E test files

### Test infrastructure
- `tests/e2e/conftest.py` — E2E fixtures, manifest reading
- `tests/e2e/dbt_utils.py` — dbt helper utilities
- `testing/fixtures/services.py` — polling utilities (use instead of sleep)

## Gotchas
- E2E tests run in Kind cluster — need port-forwards for service access
- Always use `make test-e2e` (manages port-forwards and cleanup)
- Polaris scale-down test: must wait for pod termination before testing
- Dagster restart test: must wait for webserver readiness before asset list
- S3 endpoint test: FileIO properties may need to be inspected via PyIceberg API
