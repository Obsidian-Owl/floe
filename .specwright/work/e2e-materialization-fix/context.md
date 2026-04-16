# Context: E2E Materialization Fix

## Key File Paths

### Fix 1: Helm flag
- `tests/e2e/test_helm_upgrade_e2e.py:106` — `--atomic` flag in helm upgrade command
- `.github/workflows/helm-ci.yaml:439` — `--atomic` in CI install step

### Fix 2: CVE
- `.vuln-ignore:32` — add after the last entry

### Fix 3: DbtProject
- `demo/customer-360/definitions.py:17,28` — import and `@dbt_assets(project=...)` parameter
- `demo/financial-risk/definitions.py:17,28` — same
- `demo/iot-telemetry/definitions.py:17,28` — same
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1179,1189` — code generator template

## Research Brief
- `.specwright/research/dagster-materialization-failure-20260328.md` — full investigation with live debugging results

## Live Debugging Evidence

### Error 1 (before job_image fix):
```
CheckError: Value in Mapping mismatches expected type for key dagster/image.
Expected value of type <class 'str'>. Got value None of type <class 'NoneType'>.
```
This was fixed by PR #211 + proper Dagster subchart extraction.

### Error 2 (after job_image fix, current root cause):
```
ParameterCheckError: Param "dbt_project" is not a DbtProject.
Got DbtCliResource(project_dir='/app/demo/customer_360', ...)
which is type <class 'dagster_dbt.core.resource.DbtCliResource'>.
```
Stack trace: `dagster_dbt/asset_utils.py:548` → `dagster_shared/check/functions.py:694`

## Gotchas

1. `DbtProject` does NOT respect `DBT_PROFILES_DIR` env var — must pass `profiles_dir` explicitly (dagster-io/dagster#26504)
2. The `demo/*/definitions.py` files say "AUTO-GENERATED" — the code generator at `plugin.py:1175-1211` must also be updated or the fix will be overwritten
3. `--rollback-on-failure` implies `--wait` in Helm v4, so the separate `--wait` flag can be removed
4. The Dagster subchart must be properly extracted from `.tgz` before `helm template` works locally — `charts/floe-platform/charts/dagster/` needs `Chart.yaml`

## Helm Version Confirmation
- Local: `helm version --short` → `v4.0.4+g8650e1d`
- CI: `azure/setup-helm@v4` (confirmed in `.github/workflows/helm-ci.yaml:46`)
- Both use Helm v4 — `--rollback-on-failure` is correct
