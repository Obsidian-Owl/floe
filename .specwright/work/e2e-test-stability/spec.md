# Spec: E2E Test Stability — Round 2

## Summary

Seven targeted fixes to eliminate 27 E2E test failures (12 failed + 15 errors)
identified in the 2026-03-30 diagnostic run, plus E2E validation.

---

## Task 1: Add floe-iceberg to Dagster demo Docker image

### AC-1.1: COPY line added for floe-iceberg source tree
The Dockerfile stage 2 includes `COPY packages/floe-iceberg /build/packages/floe-iceberg`
alongside the other package/plugin COPY lines (after line 98).

### AC-1.2: FLOE_PLUGINS includes floe-iceberg
The `FLOE_PLUGINS` ARG on line 103 includes `floe-iceberg` in the space-separated list.

### AC-1.3: Docker build succeeds
`docker build -f docker/dagster-demo/Dockerfile .` completes without errors
(the existing `pip check` at line ~132 validates no dependency conflicts).

---

## Task 2: Update demo manifest.yaml to OAuth2 config format

### AC-2.1: credential field replaced with oauth2 block
`demo/manifest.yaml` catalog config replaces `credential: demo-admin:demo-secret` with:
```yaml
oauth2:
  client_id: demo-admin
  client_secret: demo-secret  # pragma: allowlist secret
  token_url: http://floe-platform-polaris:8181/api/catalog/v1/oauth/tokens
```

### AC-2.2: Config passes PolarisCatalogConfig validation
`PolarisCatalogConfig(**config)` succeeds without `ValidationError` where `config`
is the `plugins.catalog.config` dict from the updated manifest.

---

## Task 3: Fix dbt profile path assertions to accept `:memory:`

### AC-3.1: test_compile_deploy_materialize_e2e.py assertion updated
Line 239 accepts both `/tmp/` paths and `:memory:` as valid DuckDB targets.

### AC-3.2: test_dbt_e2e_profile.py assertion updated
Line 550 accepts both `/tmp/` paths and `:memory:` as valid DuckDB targets.

---

## Task 4: Commit IPv4 kubeconfig fix

### AC-4.1: devpod-sync-kubeconfig.sh uses 127.0.0.1
Line 92 sed replacement writes `server: https://127.0.0.1:${LOCAL_API_PORT}`,
not `localhost`.

*(Already done in working tree — this task is just ensuring the change is on the branch.)*

---

## Task 5: Clean up gitignore and remove tracked manifests

### AC-5.1: Gitignore carve-out removed
Lines 90-97 of `.gitignore` (the `!demo/*/target/` / `demo/*/target/*` /
`!demo/*/target/manifest.json` three-line carve-out) are removed. The `target/`
ignore on line 89 covers all target directories including demo ones.

### AC-5.2: Tracked manifest files removed from git
`git rm --cached demo/*/target/manifest.json` removes any currently tracked
manifest files from the index (files stay on disk but are no longer tracked).

---

## Task 6: Fix check-e2e-ports.sh port numbers

### AC-6.1: Dagster port updated
Port check for Dagster changed from 3000 to 3100.

### AC-6.2: Marquez port updated
Port check for Marquez changed from 5000 to 5100.

### AC-6.3: OTel port added
Port check for OTel gRPC added at port 4317.

---

## Task 7: Fix cryptography CVE

### AC-7.1: GHSA-m959-cc7f-wv43 resolved
Either:
- (a) `uv lock --upgrade-package cryptography` bumps to >=46.0.6 across all lockfiles, OR
- (b) `GHSA-m959-cc7f-wv43` added to `.vuln-ignore` with a review date comment

The E2E `test_pip_audit_clean` test must pass with whichever approach is used.

---

## Task 8: Run E2E tests on DevPod to validate all fixes

### AC-8.1: DevPod started and cluster healthy
`devpod up floe` succeeds, Kind cluster is running, all platform pods are Ready.

### AC-8.2: Demo image rebuilt with fixes
`make build-demo-image` (or equivalent Docker build inside DevPod) completes
using the updated Dockerfile with floe-iceberg included.

### AC-8.3: E2E test suite passes
`make test-e2e` runs the full E2E suite. The 27 previously failing tests
(12 failed + 15 errors from diagnostic run) now pass. At most 1 known
failure remains (the deferred OpenLineage parentRun facet test).

### AC-8.4: All 3 demo code locations load
Dagster code server loads `customer-360`, `iot-telemetry`, and `financial-risk`
without import errors or config validation errors.

---

## Deferred (out of scope)

- **OpenLineage parentRun facet**: Production code in `floe_orchestrator_dagster.lineage_extraction`.
  1 test failure expected. Needs its own `/sw-design`.
