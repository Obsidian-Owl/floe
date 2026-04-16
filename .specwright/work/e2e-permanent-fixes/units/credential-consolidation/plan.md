# Plan: Credential Consolidation (Unit 8)

## Task Breakdown

### Task 1: Create centralized credentials module (AC-2)

Create `testing/fixtures/credentials.py` with `get_minio_credentials()`, `get_polaris_credentials()`, `get_polaris_endpoint()`. Read from env vars first, fallback to manifest.yaml.

**File change map:**
- CREATE `testing/fixtures/credentials.py`
- CREATE `testing/tests/unit/test_credentials.py`

**Acceptance criteria:** AC-2

### Task 2: Update Python test fixtures to use centralized module (AC-3)

Replace all hardcoded credentials in conftest.py files and test utilities with imports from the centralized module.

**File change map:**
- MODIFY `tests/e2e/conftest.py`
- MODIFY `tests/e2e/dbt_utils.py`
- MODIFY `testing/fixtures/minio.py`
- MODIFY `packages/floe-iceberg/tests/integration/conftest.py`
- MODIFY `plugins/floe-orchestrator-dagster/tests/integration/conftest.py`
- MODIFY `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py`

**Acceptance criteria:** AC-3

### Task 3: Update CI scripts to use manifest extraction (AC-4)

Replace hardcoded credentials in CI scripts with `extract-manifest-config.py` output.

**File change map:**
- MODIFY `testing/ci/test-e2e.sh`
- MODIFY `testing/ci/wait-for-services.sh`
- MODIFY `testing/ci/polaris-auth.sh`
- MODIFY `testing/ci/extract-manifest-config.py` (add credential exports if missing)

**Acceptance criteria:** AC-4

### Task 4: Synchronize Helm values with manifest (AC-5)

Ensure all Helm values files use credential values matching manifest.yaml. Add `--set` override documentation.

**File change map:**
- MODIFY `charts/floe-platform/values-test.yaml`
- MODIFY `charts/floe-platform/values-dev.yaml`
- MODIFY `charts/floe-platform/values-demo.yaml`

**Acceptance criteria:** AC-5

### Task 5: Contract test for no hardcoded credentials (AC-6)

Create contract test that scans executable code for hardcoded credential patterns.

**File change map:**
- CREATE `tests/contract/test_no_hardcoded_credentials.py`

**Acceptance criteria:** AC-6, AC-1

## Task Dependencies

```
Task 1 (centralized module) ──► Task 2 (update fixtures)
                               ──► Task 5 (contract test)
Task 3 (CI scripts) ── independent
Task 4 (Helm values) ── independent
```

Task 1 first. Tasks 2-4 can be parallel after Task 1. Task 5 last (validates all changes).

## As-Built Notes

### Implementation Decisions

1. **Credentials module (Task 1)**: Created `testing/fixtures/credentials.py` with `_read_manifest()` helper that safely parses manifest YAML, returning empty dict on any failure (missing file, invalid YAML, wrong structure). Empty env vars (whitespace-only) are treated as unset via `_env_or_none()`.

2. **MinIO credentials source**: MinIO credentials (`minioadmin`/`minioadmin`) are NOT in the manifest — they're MinIO's factory defaults. The credentials module uses hardcoded defaults for MinIO (matching factory settings), while Polaris credentials fall through to manifest.yaml. Env vars `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` always take priority.

3. **Fixture refactoring (Task 2)**: Updated 6 files. `MinIOConfig` in `minio.py` now calls `get_minio_credentials()` in default_factory lambdas. Integration conftest files changed parameter defaults from hardcoded strings to `None` with credential resolution in the function body.

4. **CI scripts (Task 3)**: Removed hardcoded credential defaults. `polaris-auth.sh` now fails-fast if `POLARIS_CLIENT_ID` or `POLARIS_CLIENT_SECRET` are not set (from env vars or `MANIFEST_OAUTH_CLIENT_ID`). MinIO credentials derive from `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.

5. **Helm values (Task 4)**: No changes needed. Helm values already match `demo/manifest.yaml` for Polaris credentials. MinIO root credentials are Helm subchart config (not manifest). Values are `--set` overridable by Helm design.

6. **Contract test (Task 5)**: Self-contained scanner that walks Python files and checks for `minioadmin`, `demo-admin`, `demo-secret` patterns. Excludes comment lines, `pragma: allowlist secret` lines, the credentials module itself, and known test expectation files. 17 tests including regression tests for scanner accuracy.

### Actual File Paths

- `testing/fixtures/credentials.py` — centralized module (32 unit tests)
- `testing/tests/unit/test_credentials.py` — unit tests for credentials module
- `testing/fixtures/minio.py` — updated to use credentials module
- `tests/e2e/conftest.py` — updated to use credentials module
- `tests/e2e/dbt_utils.py` — updated to use credentials module
- `packages/floe-iceberg/tests/integration/conftest.py` — updated
- `plugins/floe-orchestrator-dagster/tests/integration/conftest.py` — updated
- `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py` — updated
- `testing/ci/polaris-auth.sh` — removed hardcoded defaults
- `testing/ci/wait-for-services.sh` — removed hardcoded defaults
- `testing/ci/test-e2e.sh` — removed hardcoded defaults
- `tests/contract/test_no_hardcoded_credentials.py` — contract test (17 tests)

### Plan Deviations

- Task 4 (Helm values): No changes needed — values already consistent with manifest.
