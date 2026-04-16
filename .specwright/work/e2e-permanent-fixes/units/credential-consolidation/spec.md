# Spec: Credential Consolidation (Unit 8)

## Acceptance Criteria

### AC-1: All credentials derive from `demo/manifest.yaml` or environment variables

No Python test file, CI script, or fixture MUST contain hardcoded credential values (`minioadmin`, `demo-secret`, `demo-admin`). All MUST read from either:
- `demo/manifest.yaml` (via `_read_manifest_config()` or `extract-manifest-config.py`)
- Environment variables with defaults that match manifest.yaml

**How to verify:** `grep -r "minioadmin\|demo-secret\|demo-admin" --include="*.py" --include="*.sh" tests/ testing/ plugins/` returns zero results in executable code (docs/comments excluded).

### AC-2: Centralized test credentials module

A single module `testing/fixtures/credentials.py` MUST export functions for all test credentials:
- `get_minio_credentials() -> tuple[str, str]` (access_key, secret_key)
- `get_polaris_credentials() -> tuple[str, str]` (client_id, client_secret)
- `get_polaris_endpoint() -> str`

All functions MUST read from environment variables first, falling back to `demo/manifest.yaml`.

**How to verify:** Module exists. Functions return values matching manifest.yaml when no env vars set. Functions return env var values when set.

### AC-3: All test fixtures use centralized credentials module

All conftest.py files and test utilities (`dbt_utils.py`, `minio.py`, etc.) MUST import credentials from `testing/fixtures/credentials.py` instead of hardcoding.

**How to verify:** Grep all conftest.py and fixture files for direct credential strings. Zero results. All import from `credentials.py`.

### AC-4: CI scripts use `extract-manifest-config.py` for credentials

All CI scripts (`test-e2e.sh`, `wait-for-services.sh`, `polaris-auth.sh`) MUST derive credentials from `extract-manifest-config.py` output or environment variables. No hardcoded credential strings.

**How to verify:** Grep CI scripts for hardcoded credentials. Zero results. All use `$MANIFEST_*` or `$POLARIS_*` env vars.

### AC-5: Helm values reference credentials via consistent variable names

Helm values files (`values-test.yaml`, `values-dev.yaml`) MUST use consistent credential variable names that can be overridden via `--set`. The default values MUST match `demo/manifest.yaml`.

**How to verify:** Compare credential values in all Helm values files against manifest.yaml. All match. `helm template --set polaris.oauth2.clientSecret=new-secret` overrides correctly.

### AC-6: Contract test enforces no hardcoded credentials in executable code

A contract test MUST scan all Python files in `tests/`, `testing/`, and `plugins/*/tests/` for hardcoded credential patterns and fail if any are found.

**How to verify:** `pytest tests/contract/test_no_hardcoded_credentials.py` passes. Adding a hardcoded `minioadmin` to any test file causes the test to fail.
