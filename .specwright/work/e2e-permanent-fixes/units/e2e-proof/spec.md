# Spec: E2E Proof (Unit 9)

## Acceptance Criteria

### AC-1: Thin loader happy path — data reaches Iceberg

Deploy demo with thin `definitions.py` (from unit 5). Materialize all assets. Verify data reaches Iceberg tables with correct row counts.

**How to verify:** E2E test: deploy demo pipeline to Kind → trigger materialization → poll for completion → query Iceberg tables via PyIceberg → assert row counts match expected values (not `> 0`, exact counts). Assert pipeline status is SUCCESS in Dagster.

### AC-2: Loud failure on Polaris down — pipeline FAILS with clear error

With Polaris configured but unreachable, pipeline materialization MUST fail with a clear error message visible in Dagster logs.

**How to verify:** E2E test: deploy demo → scale Polaris to 0 replicas → wait for pod termination → trigger materialization → assert pipeline status is FAILED → assert Dagster logs contain `"iceberg_creation_failed"` or equivalent structured error key.

### AC-3: Loud failure on misconfigured ingestion — error propagates

With ingestion plugin configured but broken, pipeline MUST fail (not silently succeed).

**How to verify:** E2E test: deploy with intentionally broken ingestion config → trigger pipeline → assert failure propagates → assert error message is actionable.

### AC-4: No module-load crash with Polaris offline during Dagster startup

Dagster webserver MUST start and load code locations even when Polaris is offline during startup. Resource initialization failure happens at materialization time, not import time.

**How to verify:** E2E test: scale Polaris to 0 → restart Dagster webserver → assert webserver starts → assert code locations load → assert `dagster asset list` returns expected assets → trigger materialization → assert FAILS with clear error (not import crash).

### AC-5: S3 endpoint preserved through config chain

After deploying with manifest-defined S3 endpoint, PyIceberg FileIO uses the manifest endpoint for all S3 operations. No K8s-internal hostname corruption.

**How to verify:** E2E test: deploy demo → materialize → query Iceberg table → inspect FileIO properties → assert `s3.endpoint` matches manifest value. Alternatively: verify data is accessible from test runner using manifest endpoint (proves endpoint wasn't corrupted).

### AC-6: No hardcoded credentials in deployed test environment

All credentials in the deployed Kind cluster match `demo/manifest.yaml`. No credential drift between Python fixtures, Helm values, and CI scripts.

**How to verify:** E2E test: read manifest credentials → compare with K8s secret values → compare with Python fixture values → assert all match. Zero drift.

### AC-7: All prior E2E tests still pass (regression)

All existing E2E tests in `tests/e2e/` MUST pass after units 5-8 changes. No regressions.

**How to verify:** `make test-e2e` passes with zero failures, zero skips.
