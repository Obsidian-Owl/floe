# Context: E2E Test Stability Fixes

## Research Findings

### Diagnostic Run (2026-03-30)
- **Result**: 203 passed, 12 failed, 15 errors, 1 xfailed (70 min)
- **Infrastructure**: Hetzner DevPod (ccx33), Kind cluster, SSH tunnels
- **Branch**: main @ 26878b3

### Issue 1: floe-iceberg missing from Docker image

**Files**:
- `docker/dagster-demo/Dockerfile` (lines 57-103): `FLOE_PLUGINS` build arg lists packages to install
- Current list: `floe-core floe-orchestrator-dagster floe-compute-duckdb floe-dbt-core floe-lineage-marquez`
- Missing: `floe-iceberg` — needed because `floe_orchestrator_dagster.resources.iceberg` imports `floe_iceberg.IcebergTableManager`
- All 3 demo products (`customer-360`, `iot-telemetry`, `financial-risk`) fail to load

**Import chain**: `definitions.py` → `try_create_iceberg_resources()` → `from floe_iceberg import IcebergTableManager`

### Issue 2: Polaris plugin config schema mismatch

**Files**:
- `demo/manifest.yaml` (lines 44-51): Uses `credential: demo-admin:demo-secret`
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/config.py` (lines 92-161): Requires `oauth2: OAuth2Config` object, forbids extra fields
- `OAuth2Config` requires: `client_id`, `client_secret`, `token_url`

**Error**: `{'field': 'oauth2', 'message': 'Field required'}, {'field': 'credential', 'message': 'Extra inputs are not permitted'}`

**Decision needed**: Update manifest to match plugin schema, OR add backward compat to plugin. The plugin is correct (OAuth2 is the right abstraction); the manifest is stale.

### Issue 3: dbt profile path assertion

**File**: `tests/e2e/test_compile_deploy_materialize_e2e.py` (lines 217-252)
- Asserts: `dev_output["path"].startswith("/tmp/")`
- Actual: `:memory:` (valid DuckDB in-memory target)
- The assertion was written when profiles used filesystem paths; `:memory:` was introduced later

### Issue 4: IPv6 kubeconfig (already fixed in working tree)

**File**: `scripts/devpod-sync-kubeconfig.sh` (line 92)
- Was: `server: https://localhost:${LOCAL_API_PORT}`
- Now: `server: https://127.0.0.1:${LOCAL_API_PORT}`
- macOS resolves `localhost` to `[::1]` (IPv6) but SSH tunnel binds IPv4 only

### Issue 5: manifest.json gitignore noise

**Files**:
- `.gitignore` (lines 89-97): Carve-out for `demo/*/target/manifest.json`
- `docker/dagster-demo/Dockerfile` (lines 163-176): Regenerates manifests inside container via `dbt parse`
- Manifests contain timestamps, UUIDs, absolute paths that change on every `dbt parse`
- The carve-out is no longer needed — Dockerfile handles it

### Issue 6: check-e2e-ports.sh hook wrong ports

**File**: `.claude/hooks/check-e2e-ports.sh`
- Checks Dagster on port 3000, but `test-e2e.sh` uses 3100
- Checks Marquez on port 5000, but `test-e2e.sh` uses 5100
- Missing: OTel (4317)

### Issue 7: cryptography CVE

- `cryptography==46.0.5` has `GHSA-m959-cc7f-wv43`, fix in 46.0.6
- Transitive dependency via PyOpenSSL/pyiceberg
- `test_pip_audit_clean` fails

### Deferred: OpenLineage parentRun facet

- `test_openlineage_four_emission_points` fails: no parentRun facet in Marquez runs
- This is production code in `floe_orchestrator_dagster.lineage_extraction`
- Needs its own design — touches lineage emission architecture

### Deferred: Port-forward stability

- Polaris port-forward died mid-run causing 18 test failures
- Root cause was SSH tunnel conflict (tunnels held 8181/8182 when test-e2e.sh tried port-forwards)
- Resolved by running `make test-e2e` without pre-existing tunnels
- Watchdog already handles transient port-forward deaths

## Gotchas

- `demo/manifest.yaml` is consumed by the compiler which passes config dicts to plugin registry → Pydantic validation. Must match exact schema.
- `PolarisCatalogConfig` has `extra="forbid"` — any unknown field causes validation error
- The Polaris test instance uses simple credentials (`demo-admin:demo-secret`), not a real OAuth2 token endpoint. Need to check if `token_url` can point to Polaris's built-in token endpoint.
- `floe-iceberg` depends on `pyiceberg`, `pyarrow`, etc. — adds to Docker image size but these are already transitive deps
