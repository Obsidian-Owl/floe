# Spec: Commit dbt Manifests for Docker Build

## Acceptance Criteria

### AC-1: Manifest files are committed to git
- `demo/customer-360/target/manifest.json` exists in git
- `demo/iot-telemetry/target/manifest.json` exists in git
- `demo/financial-risk/target/manifest.json` exists in git
- Each file is valid JSON containing a `"nodes"` key

### AC-2: .gitignore exception allows manifest tracking
- `.gitignore` contains `!demo/*/target/manifest.json`
- `git status` does not show manifest files as untracked after checkout
- Other `target/` contents remain ignored (e.g., `target/run_results.json`)

### AC-3: Docker image contains manifest files
- `docker build` from a git-clean working tree produces an image with manifests at:
  - `/app/demo/customer_360/target/manifest.json`
  - `/app/demo/iot_telemetry/target/manifest.json`
  - `/app/demo/financial_risk/target/manifest.json`

### AC-4: CI staleness gate detects drift
- A Makefile target or CI step runs: `make compile-demo && git diff --exit-code demo/*/target/manifest.json`
- If manifests are stale (models changed but manifests not regenerated), CI fails with a clear message

### AC-5: E2E tests pass (cascading validation)
- `test_dagster_code_locations_loaded` passes (0 of 3 code locations fail)
- `test_dagster_assets_visible` passes (assets > 0)
- `test_trigger_asset_materialization` passes
- `test_iceberg_tables_exist_after_materialization` passes
- `test_auto_trigger_sensor_e2e` passes

## Error Cases
- If a manifest references a model that was deleted, `dbt compile` will fail → CI staleness gate catches this
- If manifest format changes between dbt versions, the `@dbt_assets` decorator will raise → visible as DagsterUserCodeLoadError, same as today but with a clearer fix path
