# Plan: E2E Test Stability — Round 2

## Task Order

Tasks 1-7 are code changes (independent, any order). Task 8 is validation (depends on all prior tasks).

Recommended order groups coupled fixes first:

1. **T1**: Add floe-iceberg to Dockerfile (Fix 1)
2. **T2**: Update manifest.yaml OAuth2 config (Fix 2)
3. **T3**: Fix dbt profile path assertions (Fix 3)
4. **T4**: Commit IPv4 kubeconfig fix (Fix 4 — already in working tree)
5. **T5**: Clean up gitignore + remove tracked manifests (Fix 5)
6. **T6**: Fix check-e2e-ports.sh port numbers (Fix 6)
7. **T7**: Fix cryptography CVE (Fix 7)
8. **T8**: Run E2E tests on DevPod (validation)

## File Change Map

| Task | File | Change Type |
|------|------|-------------|
| T1 | `docker/dagster-demo/Dockerfile` | Edit (2 lines) |
| T2 | `demo/manifest.yaml` | Edit (replace 1 line with 4) |
| T3 | `tests/e2e/test_compile_deploy_materialize_e2e.py` | Edit (line 239) |
| T3 | `tests/e2e/test_dbt_e2e_profile.py` | Edit (line 550) |
| T4 | `scripts/devpod-sync-kubeconfig.sh` | Already done (line 92) |
| T5 | `.gitignore` | Edit (remove lines 90-97) |
| T5 | `demo/*/target/manifest.json` | git rm --cached |
| T6 | `.claude/hooks/check-e2e-ports.sh` | Edit (ports array) |
| T7 | `.vuln-ignore` OR lockfiles | Edit |
| T8 | (no code changes) | DevPod E2E run |

## Task Details

### T1: Add floe-iceberg to Dockerfile

**Spec**: AC-1.1, AC-1.2, AC-1.3

**File**: `docker/dagster-demo/Dockerfile`

Change 1 — Add COPY line after line 98 (after `floe-lineage-marquez`):
```dockerfile
COPY packages/floe-iceberg /build/packages/floe-iceberg
```

Change 2 — Update FLOE_PLUGINS ARG at line 103:
```dockerfile
ARG FLOE_PLUGINS="floe-core floe-orchestrator-dagster floe-compute-duckdb floe-dbt-core floe-lineage-marquez floe-iceberg"
```

**Pattern**: Follows existing COPY + ARG pattern on lines 93-103.

### T2: Update manifest.yaml OAuth2 config

**Spec**: AC-2.1, AC-2.2

**File**: `demo/manifest.yaml` (lines 49-51)

Replace:
```yaml
      credential: demo-admin:demo-secret  # pragma: allowlist secret
```

With:
```yaml
      oauth2:
        client_id: demo-admin
        client_secret: demo-secret  # pragma: allowlist secret
        token_url: http://floe-platform-polaris:8181/api/catalog/v1/oauth/tokens
```

**Schema reference**: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/config.py`
- `PolarisCatalogConfig.oauth2: OAuth2Config` (required)
- `OAuth2Config.client_id: str`, `client_secret: SecretStr`, `token_url: str`
- `PolarisCatalogConfig` has `extra="forbid"` — no unknown fields allowed

### T3: Fix dbt profile path assertions

**Spec**: AC-3.1, AC-3.2

**File 1**: `tests/e2e/test_compile_deploy_materialize_e2e.py:239`

Replace:
```python
        assert dev_output["path"].startswith("/tmp/"), (
            f"DuckDB path must be under /tmp/ for container writability, got {dev_output['path']}"
        )
```

With assertion that accepts both `/tmp/` and `:memory:`.

**File 2**: `tests/e2e/test_dbt_e2e_profile.py:550`

Replace:
```python
        assert demo_dev.get("path", "").startswith("/tmp/"), (
            f"Demo profile for '{product}' was modified: path is "
            f"'{demo_dev.get('path')}', expected '/tmp/*.duckdb'."
        )
```

With assertion that accepts both `/tmp/` and `:memory:`.

### T4: Commit IPv4 kubeconfig fix

**Spec**: AC-4.1

**File**: `scripts/devpod-sync-kubeconfig.sh:92`

Already changed in working tree. Just needs to be committed on the feature branch.

### T5: Clean up gitignore and remove tracked manifests

**Spec**: AC-5.1, AC-5.2

**File 1**: `.gitignore` — Remove lines 90-97 (the three-line carve-out for demo manifests).
Keep the `target/` line on 89.

**File 2**: Run `git rm --cached` on any tracked `demo/*/target/manifest.json` files.

### T6: Fix check-e2e-ports.sh port numbers

**Spec**: AC-6.1, AC-6.2, AC-6.3

**File**: `.claude/hooks/check-e2e-ports.sh` (lines 20-27)

Update the PORTS associative array:
```bash
declare -A PORTS=(
  [Polaris]=8181
  [Polaris-mgmt]=8182
  [Dagster]=3100
  [MinIO]=9000
  [Jaeger]=16686
  [Marquez]=5100
  [OTel-gRPC]=4317
)
```

**Source of truth**: `scripts/devpod-tunnels.sh` lines 29-36.

### T7: Fix cryptography CVE

**Spec**: AC-7.1

**Preferred approach**: Add to `.vuln-ignore` with review date, since `cryptography`
is a transitive dependency and bumping requires `uv lock --upgrade-package cryptography`
across multiple lockfiles which may pull in other changes.

```
# cryptography 46.0.5 — GHSA-m959-cc7f-wv43, fix in 46.0.6. Review by 2026-04-30.
GHSA-m959-cc7f-wv43
```

**Alternative** (if straightforward): `uv lock --upgrade-package cryptography` in
affected lockfile directories. Only if it doesn't cascade to other dependency changes.

### T8: Run E2E tests on DevPod

**Spec**: AC-8.1, AC-8.2, AC-8.3, AC-8.4

**Procedure**:
1. `devpod up floe` — start DevPod workspace
2. Push branch to remote, pull on DevPod (or sync working tree)
3. `make build-demo-image` — rebuild Docker image with floe-iceberg
4. `kind load docker-image floe-dagster-demo:latest --name floe` — load into Kind
5. Restart Dagster deployments to pick up new image
6. `make test-e2e` — run full E2E suite
7. Verify: >=215 passed, <=1 failed (OpenLineage parentRun)
8. Verify: all 3 code locations load in Dagster UI

**No code changes** — this is a validation task only.

## Branch Strategy

Per `config.git`:
- Branch: `feat/e2e-test-stability`
- Base: `main`
- One commit per task (T1-T7), T8 produces no commits
