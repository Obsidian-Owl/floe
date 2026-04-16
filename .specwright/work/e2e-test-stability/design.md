# Design: E2E Test Stability — Round 2

## Overview

Seven targeted fixes to resolve the remaining 27 test failures (12 failed + 15 errors)
from the diagnostic run on 2026-03-30. Each fix addresses a distinct root cause identified
in the diagnostic report. Together they eliminate all non-deferred failures.

## Approach

Fix the highest-impact issues first. Three categories:

1. **Production config bugs** (Fix 1, Fix 2): Missing package + stale config — 6+ tests each
2. **Test/infra correctness** (Fix 3, Fix 4, Fix 6): Overly strict assertions, wrong constants
3. **Hygiene** (Fix 5, Fix 7): Gitignore cleanup, CVE bump

## Fixes

### Fix 1: Add floe-iceberg to Dagster demo Docker image

**Files changed**:
- `docker/dagster-demo/Dockerfile` (2 changes):
  - Add `COPY packages/floe-iceberg /build/packages/floe-iceberg` after line 98
  - Add `floe-iceberg` to the `FLOE_PLUGINS` ARG on line 103

**Why**: All 3 demo products import `floe_iceberg.IcebergTableManager` via
`floe_orchestrator_dagster.resources.iceberg`. Without the package, all code
locations fail to load → 6 test failures.

**Risk**: LOW. The pyproject.toml is already COPY'd (line 33) for lockfile
verification. Adding the source tree and plugin entry is the intended pattern
per the comment on line 90-92.

### Fix 2: Update demo manifest.yaml Polaris config to OAuth2 format

**Files changed**:
- `demo/manifest.yaml`: Replace `credential: demo-admin:demo-secret` with:
  ```yaml
  oauth2:
    client_id: demo-admin
    client_secret: demo-secret
    token_url: http://floe-platform-polaris:8181/api/catalog/v1/oauth/tokens
  ```

**Why**: `PolarisCatalogConfig` has `extra="forbid"` and requires `oauth2: OAuth2Config`.
The `credential` field is not in the schema → validation error → all code locations fail.

**Token URL**: Confirmed from `testing/ci/polaris-auth.sh` which uses
`$polaris_url/api/catalog/v1/oauth/tokens` with `grant_type=client_credentials`.
This is Polaris's built-in OAuth2 endpoint — no external IdP needed.

**Risk**: MEDIUM. The OAuth2 flow must work with the demo Polaris instance.
The `polaris-auth.sh` script confirms it does. The token_url uses the
in-cluster hostname (`floe-platform-polaris`) which is correct for the
Kind cluster deployment.

### Fix 3: Fix dbt profile path assertion to accept `:memory:`

**Files changed** (2 files):
- `tests/e2e/test_compile_deploy_materialize_e2e.py:239`
- `tests/e2e/test_dbt_e2e_profile.py:550`

Both assertions: `assert path.startswith("/tmp/")` →
`assert path.startswith("/tmp/") or path == ":memory:"`

**Why**: DuckDB `:memory:` is a valid target that doesn't need filesystem access.
The assertion was written when profiles used filesystem paths. The conftest
(line 1132) now generates `:memory:` profiles.

**Risk**: LOW. `:memory:` is semantically correct — it's more permissive than
`/tmp/` for container environments since it needs no volume mount.

### Fix 4: Use 127.0.0.1 in devpod-sync-kubeconfig.sh

**Files changed**:
- `scripts/devpod-sync-kubeconfig.sh:92` (already done in working tree)

**Why**: macOS resolves `localhost` to `[::1]` (IPv6) but SSH tunnels bind
IPv4 only → K8s API unreachable.

**Risk**: LOW. Strictly more correct for SSH tunnel targets.

### Fix 5: Gitignore demo manifest.json files

**Files changed**:
- `.gitignore`: Remove the `!demo/*/target/manifest.json` carve-out (lines ~89-97)
- Remove tracked `demo/*/target/manifest.json` files from git

**Why**: The Dockerfile regenerates manifests inside the container via `dbt parse`
(lines 163-176). Committed manifests contain timestamps, UUIDs, and host-absolute
paths that create noisy diffs on every build.

**Risk**: LOW. The carve-out was needed before the Dockerfile regenerated them.
Now it's unnecessary and creates git noise.

### Fix 6: Fix check-e2e-ports.sh hook port numbers

**Files changed**:
- `.claude/hooks/check-e2e-ports.sh`: Update port checks:
  - Dagster: 3000 → 3100
  - Marquez: 5000 → 5100
  - Add: OTel gRPC 4317

**Source of truth**: `scripts/devpod-tunnels.sh` lines 29-36 defines the
canonical port mappings.

**Risk**: LOW. Developer guardrail only — no production impact.

### Fix 7: Bump cryptography for CVE fix

**Files changed**:
- Add `cryptography>=46.0.6` to constraints or pin in relevant pyproject.toml
- OR add CVE to `.vuln-ignore` with review date (if CVE doesn't apply)

**Preferred**: Bump the constraint. Per constitution Principle VI (Security First):
"Update within 7 days of CVE disclosure."

**Risk**: LOW. Minor version bump of a transitive dependency.

## Blast Radius

| Fix | Modules/Files Touched | Failure Scope | Does NOT Change |
|-----|----------------------|---------------|-----------------|
| 1 | Dockerfile | Local (build) | Plugin code, tests |
| 2 | demo/manifest.yaml | Local (config) | Plugin code, schema |
| 3 | 2 test files | Local (tests) | Production code |
| 4 | 1 shell script | Local (infra) | K8s config, tests |
| 5 | .gitignore + tracked files | Local (repo) | Build, tests |
| 6 | 1 hook script | Local (DX) | Build, tests, CI |
| 7 | pyproject.toml/constraints | Local (deps) | Application code |

**Systemic risk**: None. All fixes are isolated to their respective domains.
No fix crosses package boundaries or changes public APIs.

## Deferred Items

1. **OpenLineage parentRun facet** — Production code in `floe_orchestrator_dagster.lineage_extraction`.
   Needs its own design touching lineage emission architecture. 1 test failure.

2. **Port-forward stability** — Root cause was SSH tunnel conflict, not watchdog logic.
   Resolved by running `make test-e2e` without pre-existing tunnels. The existing
   watchdog handles transient deaths. No code change needed.

## Integration Points

- Fix 1 + Fix 2 are coupled: both must land for demo code locations to load successfully.
  Fix 1 alone still fails (config validation). Fix 2 alone still fails (missing module).
- Fix 3 is independent but will only be testable once Fix 1+2 land (test needs code
  locations to load).
- Fixes 4-7 are fully independent.

## Risk Assessment

**Main risk**: Fix 2 (OAuth2 config). Mitigated by:
- `testing/ci/polaris-auth.sh` confirms the token endpoint works
- The Polaris Helm chart deploys with default credentials matching `demo-admin:demo-secret`
- The token URL uses the standard Polaris REST API path

**Validation strategy**: After all fixes, rebuild the demo image and re-run the E2E
suite on the DevPod. Expected result: 27 fewer failures (12 failed + 15 errors resolved),
leaving only the deferred OpenLineage parentRun facet test.
