# Assumptions: E2E Production Bugfixes

## A1: Catalog plugin connect() returns usable PyIceberg Catalog

- **Category**: technical
- **Status**: VERIFIED
- **Evidence**: `plugin.py:293` returns `self._catalog` which is the result of `load_catalog("polaris", **catalog_config)`. The returned object supports `create_namespace()`, `load_table()`, `create_table()` and table `overwrite()`/`append()` — exactly what `_export_dbt_to_iceberg()` needs.

## A2: Plugin imports available in Docker image

- **Category**: integration
- **Status**: VERIFIED
- **Evidence**: The generated `definitions.py` already imports `from floe_orchestrator_dagster.resources.iceberg import try_create_iceberg_resources` and `from floe_core.schemas.compiled_artifacts import CompiledArtifacts` — both from the plugin system. Adding `from floe_core.plugin_registry import get_registry` and `from floe_core.plugin_types import PluginType` uses the same packages already installed.

## A3: Generated definitions.py files are recompiled before E2E tests

- **Category**: environmental
- **Status**: ACCEPTED
- **Rationale**: `make compile-demo` runs as part of `make build-demo-image`, and the E2E test flow includes image rebuild. The `make test-e2e` target also calls the ensure-ready script. Additionally, `make demo` explicitly calls `compile-demo` before building.

## A4: Polaris scope default of PRINCIPAL_ROLE:ALL is correct

- **Category**: technical
- **Status**: VERIFIED
- **Evidence**: All integration tests and the Polaris plugin's own test fixtures use `PRINCIPAL_ROLE:ALL`. PyIceberg's default `scope=catalog` is rejected by Polaris with `invalid_scope`. The Polaris REST API requires scopes in `PRINCIPAL_ROLE:<role>` format.
