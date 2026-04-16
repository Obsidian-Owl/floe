# Spec: E2E Production Bugfixes

## Overview

Fix 2 production code bugs causing 8 E2E test failures (7 from template bug, 1 from missing tracer_name).

## Acceptance Criteria

### AC-1: Code generator template delegates to plugin connect()

The `_export_dbt_to_iceberg()` template in `plugin.py` MUST use the plugin system
(`registry.get()` + `registry.configure()` + `plugin.connect()`) instead of calling
`load_catalog()` directly.

**Verification**: The generated `definitions.py` for any demo product contains NO
direct `load_catalog()` call inside `_export_dbt_to_iceberg()`. Instead it uses
`get_registry()`, `registry.get(PluginType.CATALOG, ...)`, and `plugin.connect()`.

### AC-2: Template passes storage config to connect()

The template MUST pass S3 storage config to the catalog plugin's `connect()` method
via its `config` parameter, using S3-prefixed keys (`s3.endpoint`, `s3.access-key-id`,
etc.).

**Verification**: Generated `_export_dbt_to_iceberg()` constructs the S3 config dict
and passes it as `config=` to `plugin.connect()`.

### AC-3: Template imports updated

The template's import section MUST include all imports required by the plugin-based
approach (`get_registry`, `PluginType`).

**Verification**: `make compile-demo` succeeds without ImportError. The generated
`definitions.py` files have the required imports.

### AC-4: OAuth2 credential construction removed from template

The generated `_export_dbt_to_iceberg()` MUST NOT contain any direct reference to
`credential`, `client_id`, `client_secret`, `token_url`, or `scope` parameter
construction. All OAuth2 handling is delegated to the plugin's `connect()` method.

**Verification**: `grep -c "credential\|client_id\|client_secret\|token_url\|scope"` on
the generated `_export_dbt_to_iceberg()` function returns 0.

### AC-5: S3StoragePlugin has tracer_name property

`S3StoragePlugin` MUST override the `tracer_name` property from `PluginMetadata`,
returning `"floe.storage.s3"` (dot-separated, following Polaris convention
`"floe.catalog.polaris"`). A module-level `TRACER_NAME` constant MUST be defined,
following the Polaris plugin pattern.

**Verification**: `plugin.tracer_name == "floe.storage.s3"` and
`verify_plugin_instrumentation()` returns 0 warnings for the S3 plugin.

### AC-6: Governance enforcement test passes

`test_governance_violations_in_artifacts` MUST pass — `result.warning_count == 0`.

**Verification**: The test passes without modification.

### AC-7: All 7 Dagster/materialization tests pass

The following tests MUST pass without modification:
- `test_dagster_code_locations_loaded`
- `test_dagster_assets_visible`
- `test_trigger_asset_materialization`
- `test_iceberg_tables_exist_after_materialization`
- `test_auto_trigger_sensor_e2e`
- `test_make_demo_completes`
- `test_three_products_visible_in_dagster`

**Verification**: All 7 tests pass. Tests are NOT modified — the production code is fixed.

## Spec Review

Architect review: see plan.md for task breakdown.
