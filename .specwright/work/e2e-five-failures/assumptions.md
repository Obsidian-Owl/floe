# Assumptions

## A1: @dbt_assets maps each dbt node to a separate Dagster asset
- **Type**: Technical
- **Status**: ACCEPTED (verified in dagster-dbt docs and demo manifest)
- **Impact**: When `assetSelection` targets one model, only that model's dbt command runs
- **Resolution**: Confirmed by the error — `dbt build --select stg_crm_customers` skips seeds

## A2: Removing assetSelection runs all assets in correct dependency order
- **Type**: Technical
- **Status**: ACCEPTED (verified — `dbt build` without `--select` runs seeds→staging→marts)
- **Impact**: Test will take longer but correctly validate the full materialization flow
- **Resolution**: This matches production behavior

## A3: Package lockfiles are independent of root lockfile
- **Type**: Technical
- **Status**: ACCEPTED (verified — `packages/floe-core/uv.lock` has cryptography 46.0.5
  while root has 46.0.6)
- **Impact**: Each package must be individually refreshed
- **Resolution**: Run `uv lock` per package

## A4: OpenLineage START emission is a production code gap, not a test bug
- **Type**: Architectural
- **Status**: ACCEPTED
- **Impact**: F4 test failure is correctly surfacing a real gap
- **Resolution**: Log as backlog item, do not weaken the test
