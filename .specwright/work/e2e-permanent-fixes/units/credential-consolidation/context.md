# Context: Credential Consolidation (Unit 8)

## Key File Paths

### Single Source of Truth
- `demo/manifest.yaml:56-63` — canonical credential definitions
  - `plugins.catalog.config.oauth2.client_id: demo-admin`
  - `plugins.catalog.config.oauth2.client_secret: demo-secret`
  - `plugins.storage.config.endpoint: http://floe-platform-minio:9000`

### Existing Extraction Mechanisms
- `testing/ci/extract-manifest-config.py:43-60` — parses manifest, exports shell vars
- `tests/e2e/conftest.py:54-60` — `_read_manifest_config()` reads manifest in Python

### Files with Hardcoded Credentials (31 total)

**Python Test Fixtures (HIGH priority — executable code):**
- `testing/fixtures/minio.py:46-49` — `minioadmin` hardcoded
- `packages/floe-iceberg/tests/integration/conftest.py` — credentials hardcoded
- `plugins/floe-orchestrator-dagster/tests/integration/conftest.py:19` — `demo-admin:demo-secret`
- `tests/e2e/dbt_utils.py:47` — `demo-admin:demo-secret`
- `tests/e2e/conftest.py` — fallback credentials
- `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py` — test credentials

**CI Scripts (MEDIUM priority):**
- `testing/ci/test-e2e.sh` — mixed (some extracted, some hardcoded)
- `testing/ci/wait-for-services.sh` — hardcoded
- `testing/ci/polaris-auth.sh` — env var with defaults

**Helm Values (LOW priority — intentional defaults):**
- `charts/floe-platform/values-test.yaml`
- `charts/floe-platform/values-dev.yaml`
- `charts/floe-platform/values-demo.yaml`
- `charts/floe-jobs/values-test.yaml`

**K8s Manifests (LOW priority):**
- `testing/k8s/secrets/polaris-secret.yaml`
- `testing/k8s/jobs/test-runner.yaml`
- `testing/k8s/setup-cluster.sh`

**Documentation (informational only — no changes needed):**
- `testing/E2E-ERROR-REPORT.md`
- `docs/audits/test-hardening-audit-2026-02.md`
- Various ADR docs

## Known Drift
From test-hardening audit (2026-02):
- Polaris credential: `demo-admin:demo-secret` in values-test vs `root:secret` in polaris.py:46 — **DRIFT**
- MinIO secret key: `minioadmin123` in values-test vs `minioadmin` in minio.py:49 — **DRIFT**

## Gotchas
- Helm values with hardcoded defaults are INTENTIONAL and correct — they're K8s-native config
- The fix is ensuring Python/shell code reads from manifest or env vars, not duplicating values
- `minioadmin` is MinIO's default root credential — it appears both as access_key and secret_key
- Some test files use credentials for negative testing (invalid creds) — these are NOT part of consolidation
- `# pragma: allowlist secret` comments are bandit suppression — keep them where needed
