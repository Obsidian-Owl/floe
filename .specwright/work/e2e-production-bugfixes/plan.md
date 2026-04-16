# Plan: E2E Production Bugfixes

## Task Breakdown

### T1: Replace direct load_catalog() with plugin connect() in template

**ACs**: AC-1, AC-2, AC-3, AC-4

**File change map**:
- EDIT `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Template `_export_dbt_to_iceberg()` section (lines ~1215-1294)
  - Template import section (lines ~1299-1347)

**Approach**:

Replace the `load_catalog()` block (lines ~1239-1246) in the `_export_dbt_to_iceberg()`
template with the plugin-based approach. The new template code should:

1. Import `get_registry` and `PluginType` (added to the template import section)
2. Use `registry = get_registry()` to get the plugin registry
3. Use `registry.get(PluginType.CATALOG, catalog_type)` to get the catalog plugin
4. Use `registry.configure(PluginType.CATALOG, catalog_type, catalog_config)` to validate config
5. Re-instantiate with validated config: `type(catalog_plugin)(config=validated_config)`
6. Build S3 config dict from storage_config with `s3.` prefix
7. Call `catalog_plugin.connect(config=s3_config)` to get a PyIceberg `Catalog`

**Template escaping note**: Template uses `{{` / `}}` for literal braces in generated code.
The `f"s3.{{k}}"` pattern is already used in the current template for S3 key prefixing.

**Reference patterns**:
- `_load_iceberg_resources()` template (lines ~1205-1212) — uses `try_create_iceberg_resources()`
- `resources/iceberg.py` T2 pattern (lines ~96-114) — `type(plugin)(config=validated_config)`
- Polaris `connect()` (lines 220-293) — handles OAuth2, scope, retry

### T2: Add tracer_name to S3StoragePlugin

**ACs**: AC-5, AC-6

**File change map**:
- EDIT `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py`

**Approach**:

Add a module-level constant and property override:

```python
TRACER_NAME = "floe.storage.s3"
```

Property on the class:

```python
@property
def tracer_name(self) -> str:
    return TRACER_NAME
```

**Reference**: Polaris plugin pattern at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py:138-145`.

### T3: Recompile demo and verify

**ACs**: AC-3, AC-7

**File change map**:
- REGENERATED `demo/*/definitions.py` (via `make compile-demo`)

**Approach**:

1. Run `make compile-demo` to regenerate all demo product `definitions.py` files
2. Verify the generated files contain the plugin-based approach (no `load_catalog()` in `_export_dbt_to_iceberg`)
3. Verify imports include `get_registry` and `PluginType`
4. Run `make test-unit` to ensure no regressions

## Architecture Notes

- The `connect()` method on the Polaris plugin already handles all OAuth2 complexity:
  credential construction, token URL, scope (`PRINCIPAL_ROLE:ALL`), credential vending,
  and retry logic. Delegating to it eliminates 100% of duplicated connection logic.
- The `config` parameter of `connect()` accepts arbitrary dict entries that get merged
  into the catalog config — S3-prefixed keys pass through directly.
- Template double-brace escaping (`{{`/`}}`) is critical — Python f-string literals
  in generated code must use doubled braces.

## As-Built Notes

### T1: Template fix
- Added `catalog_type` local variable to avoid line-length violation (was >100 chars)
- 18 unit tests in new file `test_code_generator_iceberg.py` covering all 4 ACs
- No deviations from plan

### T2: tracer_name
- Cherry-picked S3StoragePlugin from `feat/e2e-zero-failures` (commit `1eb0eca`) since it hasn't been merged to main
- `TRACER_NAME = "floe.storage.s3"` (dot-separated per Polaris convention, revised from design's `"floe_storage_s3"`)
- 2 new tests added to existing `test_plugin.py`

### T3: Recompile
- `compiled_artifacts.json` files are gitignored — only `definitions.py` committed
- All 3 demo products regenerated successfully
- 522 orchestrator unit tests pass with no regressions
