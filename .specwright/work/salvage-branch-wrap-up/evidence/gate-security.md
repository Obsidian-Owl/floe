# Gate: Security

**Status**: WARN
**Timestamp**: 2026-04-13T19:25:00+10:00

## Findings

### BLOCK: B1 — Hardcoded MinIO credentials bypass centralized source (CWE-798)
- **File**: `tests/e2e/dbt_utils.py:129-132`
- **Issue**: `os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")` bypasses `get_minio_credentials()` which is already imported
- **Fix**: Replace with `access_key, secret_key = get_minio_credentials()`

### WARN: W1 — Unvalidated POLARIS_HOST env var in kubectl subprocess (CWE-78 partial)
- **File**: `tests/e2e/tests/test_polaris_jdbc_durability.py:101-116`
- **Issue**: `POLARIS_HOST` used without DNS label validation in `deploy_ref`
- **Mitigated by**: `shell=False`, namespace-scoped RBAC

### WARN: W2 — Assertion exposes full namespace list (CWE-209)
- **File**: `tests/e2e/tests/test_polaris_jdbc_durability.py:168-171`
- **Issue**: Failed assertion leaks all Polaris namespaces to CI artifacts

### WARN: W3 — pods/exec granted without documented justification (CWE-269)
- **File**: `charts/floe-platform/templates/tests/rbac-standard.yaml:39`

### WARN: W4 — readOnlyRootFilesystem: false (CWE-732)
- **File**: `charts/floe-platform/templates/tests/_test-job.tpl:81`

### WARN: W5 — events create verb not needed for tests (CWE-269)
- **File**: `charts/floe-platform/templates/tests/rbac-standard.yaml:45`

### INFO: I1 — Namespace drop uses debug-level logging (CWE-390)
- **File**: `tests/e2e/dbt_utils.py:180-181`

### INFO: I2 — catalogName default "floe-e2e" is environment-specific
- **File**: `charts/floe-platform/values.yaml:338`
