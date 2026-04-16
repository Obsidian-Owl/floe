# Context: E2E Production Bugfixes

baselineCommit: 2593bf1adccff0813cb47c38c0c847474d2e071e

## Key File Paths

### Bug 1: Code generator template

- **Template**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - `generate_entry_point_code()` method
  - `_export_dbt_to_iceberg()` template: lines 1215-1294
  - `_load_iceberg_resources()` template: lines 1205-1212 (correct pattern to follow)
  - Iceberg helpers section: lines 1188-1296

- **Polaris plugin connect()**: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py:220-293`
  - Builds OAuth2 credential at line 241: `credential = f"{client_id}:{client_secret}"`
  - Sets scope at lines 260-262
  - Returns PyIceberg `Catalog` object at line 293

- **Config injection pattern (T2)**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:96-114`
  - `registry.get()` + `registry.configure()` + `type(plugin)(config=validated_config)`

- **Registry API**: `packages/floe-core/src/floe_core/plugin_registry.py`
  - `get_registry()` → `PluginRegistry`
  - `registry.get(PluginType, name)` → plugin instance
  - `registry.configure(PluginType, name, config_dict)` → validated config or None

- **Generated definitions.py**: `demo/customer-360/definitions.py`, etc.
  - `_load_iceberg_resources()`: lines 33-44 (uses try_create_iceberg_resources — correct)
  - `_export_dbt_to_iceberg()`: lines 55-146 (uses direct load_catalog — broken)
  - Both are generated from the template in plugin.py

- **Compiled artifacts**: `demo/*/compiled_artifacts.json`
  - `plugins.catalog.config` = `{"uri": ..., "warehouse": ..., "oauth2": {"client_id": ..., "client_secret": ..., "token_url": ...}}`

### Bug 2: S3StoragePlugin tracer_name

- **S3 plugin**: `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py`
  - Missing `tracer_name` property
  - Base class default returns `None` at `packages/floe-core/src/floe_core/plugin_metadata.py:200`

- **Polaris tracer_name (reference)**: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py:138-145`
  - `TRACER_NAME = "floe_catalog_polaris"` (module-level constant)
  - Property returns `TRACER_NAME`

- **Instrumentation audit**: `packages/floe-core/src/floe_core/telemetry/audit.py:46-89`
  - `verify_plugin_instrumentation()` checks `plugin.tracer_name is None`
  - Returns warnings list

- **Governance test**: `tests/e2e/test_governance_enforcement_e2e.py:346-348`
  - Asserts `result.warning_count == 0`

## Gotchas

1. Template uses double-brace escaping (`{{}}`) for Python f-string literals in the generated code
2. The template imports are at lines 1299-1347 — new imports needed by the template code must be added to the import section
3. `connect()` accepts a `config: dict[str, Any]` parameter for additional config (e.g., S3 prefixed keys)
4. The Polaris plugin's `connect()` doesn't set a default scope when `oauth2.scope` is None — PyIceberg falls back to `scope=catalog` which Polaris rejects. The `_export_dbt_to_iceberg` fix should pass `scope=PRINCIPAL_ROLE:ALL` via the config dict if not configured.
5. Storage config needs to be passed as S3-prefixed keys: `{"s3.endpoint": ..., "s3.access-key-id": ...}` etc.
