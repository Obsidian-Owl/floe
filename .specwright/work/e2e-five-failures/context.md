# Context: E2E Five Failures

## Research Findings

### F1: test_trigger_asset_materialization — dbt schema mismatch

**Root cause**: The test materializes only `stg_crm_customers` via `assetSelection`.
With `@dbt_assets`, Dagster maps each dbt node to a separate asset. Selecting ONE
staging model causes Dagster to run `dbt build --select stg_crm_customers`, which
skips seed dependencies (`raw_customers`). The staging model references
`{{ ref('raw_customers') }}` which should exist in `main_raw` schema (DuckDB
`:memory:` default `main` + seed `+schema: raw` = `main_raw`). Seeds were never
materialized, so the schema doesn't exist.

**Files**:
- `tests/e2e/test_compile_deploy_materialize_e2e.py:471-604` — test code
- `demo/customer-360/definitions.py:26-37` — `@dbt_assets` with `dbt build`
- `demo/customer-360/dbt_project.yml:11-13` — `seeds: +schema: raw`
- `demo/customer-360/profiles.yml` — DuckDB `:memory:`
- `demo/customer-360/models/staging/stg_crm_customers.sql` — `ref('raw_customers')`

**Fix approach**: Include seed assets in the materialization selection, or materialize
all assets in the code location (drop `assetSelection` filter).

### F2: test_iceberg_tables_exist_after_materialization — cascade from F1

Direct consequence of F1. Materialization failed, so no Iceberg tables created.
No separate fix needed — fixing F1 resolves F2.

### F3: test_pip_audit_clean — stale package lockfile

**Root cause**: `packages/floe-core/uv.lock` pins `cryptography==46.0.5` with
CVE `GHSA-m959-cc7f-wv43`. The root `uv.lock` was updated to 46.0.6 in PR #213,
but package-level lockfiles were not refreshed.

**Files**:
- `packages/floe-core/uv.lock` — stale cryptography version
- Other package lockfiles may also be stale

**Fix approach**: Run `uv lock` in each package directory, or add a CI check that
validates all lockfiles are in sync.

### F4: test_openlineage_four_emission_points — missing START events

**Root cause**: Multi-layer issue:
1. Demo `definitions.py` passes `None` to `try_create_lineage_resource()`, resulting
   in `NoOpLineageResource` that discards all events silently
2. The `@dbt_assets` decorator from dagster-dbt handles asset execution — it calls
   `dbt.cli(["build"]).stream()` which does NOT invoke the platform's custom
   `lineage.emit_start()` / `lineage.emit_complete()` code
3. The custom emission code lives in `_create_asset_for_transform()` in
   `plugin.py:556-616`, but this function is NOT used by demo definitions

**Files**:
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:556-616`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py:387-419`
- `demo/*/definitions.py` — `try_create_lineage_resource(None)`
- `tests/e2e/test_observability.py:950-1022`

**Fix approach**: This is a production code issue. The Dagster-dbt integration
needs either:
(a) A custom dagster-dbt event handler that emits OpenLineage events, or
(b) Configuration of the Marquez/OpenLineage endpoint in definitions so the
    lineage resource is real (not NoOp), plus hooking into dagster-dbt's event stream

### F5: test_all_pods_ready — completed pods not filtered

**Root cause**: `check_all_pods_ready()` uses JSONPath to get ALL pods' Ready
conditions, including completed Dagster run pods (phase=Succeeded) which have
`Ready=False`. The test doesn't exclude completed jobs.

**Files**:
- `tests/e2e/test_platform_bootstrap.py:114-131` — broken function
- `tests/e2e/test_helm_upgrade_e2e.py:189-191` — correct pattern (skips Succeeded)
- `tests/e2e/test_platform_deployment_e2e.py:142-143` — correct pattern

**Fix approach**: Switch from JSONPath to JSON parsing, filter out `Succeeded` pods.
Pattern already exists in two other test files.
