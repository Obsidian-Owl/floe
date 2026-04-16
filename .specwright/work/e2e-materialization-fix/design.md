# Design: E2E Materialization Fix

## Problem

Asset materialization fails in E2E tests due to three stacked issues:

1. **Helm v4 `--atomic` deprecation** — `test_helm_upgrade_e2e.py` uses deprecated `--atomic` flag, causing helm upgrade to fail and SSH tunnels to collapse, cascading ~69 test failures
2. **CVE in cryptography 46.0.5** — `test_pip_audit_clean` fails on `GHSA-m959-cc7f-wv43`
3. **`@dbt_assets(project=DbtCliResource(...))` type mismatch** — `dagster-dbt` expects `DbtProject`, not `DbtCliResource`, causing `ParameterCheckError` at materialization time

## Approach

Direct, minimal fixes at the point of failure. No architectural changes.

### Fix 1: Helm flag replacement (INFRA)

Replace `--atomic` with `--rollback-on-failure` in:
- `tests/e2e/test_helm_upgrade_e2e.py` (test code)
- `.github/workflows/helm-ci.yaml` (CI pipeline)

CI uses `azure/setup-helm@v4` which installs Helm v4 — `--rollback-on-failure` is the correct replacement. It also implies `--wait`, so the separate `--wait` flag can be removed.

### Fix 2: CVE ignore (INFRA)

Add `GHSA-m959-cc7f-wv43` to `.vuln-ignore` with comment noting cryptography 46.0.6 has the fix. Add review-by date for tracking.

### Fix 3: DbtProject type fix (PRODUCTION)

Three layers to fix:
1. **Demo definitions** (`demo/*/definitions.py`) — change `project=DbtCliResource(...)` to `project=DbtProject(..., profiles_dir=...)`
2. **Code generator** (`plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1179-1189`) — update the template to import and use `DbtProject`
3. **profiles_dir** — must be passed explicitly because `DbtProject` does not respect `DBT_PROFILES_DIR` env var (dagster-io/dagster#26504)

### What is NOT changed

- Helm chart templates (subchart rendering is correct when properly extracted from `.tgz`)
- Dagster subchart `.tgz` archive
- Polaris bootstrap script (the "Entity ALL" error was stale, from 2026-03-14)
- E2E test assertions (no weakening)
- No new dependencies

## Blast Radius

| Module | Files | Scope | Propagation |
|--------|-------|-------|-------------|
| E2E test infra | `test_helm_upgrade_e2e.py` | Local | None — test only |
| CI pipeline | `helm-ci.yaml` | Local | CI only |
| Security config | `.vuln-ignore` | Local | Scan only |
| Demo definitions | `demo/*/definitions.py` (3 files) | Adjacent | Dagster asset loading, K8s run workers |
| Code generator | `plugin.py` (1 file) | Adjacent | Future `floe compile --generate-definitions` runs |

**Does NOT change**: Helm chart templates, Dagster subchart, Polaris config, E2E test assertions, any Python package code.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `DbtProject` constructor signature different in pinned dagster-dbt version | LOW | Verified via live debugging — `DbtProject(project_dir=..., profiles_dir=...)` is the correct signature |
| `--rollback-on-failure` not available in CI Helm | LOW | CI uses `azure/setup-helm@v4` (Helm v4); local confirmed with `helm version --short` → v4.0.4 |
| Code generator not tested | MEDIUM | No existing test for generated content; adding one would be good but is out of scope for this fix |

## Integration Points

1. **Dagster subchart template** reads `image` from values via `hasKey $k8sRunLauncherConfig "image"` — PR #211 fixed the values, this fix addresses the code-level type mismatch
2. **`floe compile --generate-definitions`** writes `demo/*/definitions.py` — generator template must match the manual fix

## WARNs from Architect Review

- **W1**: CVE ignore should include review-by date for consistency — ACCEPTED, will add
- **W2**: No test for code generator output — NOTED, out of scope (tracked as backlog item)
