# Integration Criteria — Audit Structural Fixes

After all 3 units are built, these structural connections must exist:

- [ ] IC-1: `packages/floe-core/src/floe_core/plugin_metadata.py` exports `configure()` method and `is_configured` property on `PluginMetadata` ABC
- [ ] IC-2: `packages/floe-core/src/floe_core/plugin_registry.py` calls `plugin.configure(validated_config)` — no `hasattr(plugin, "_config")` or direct `plugin._config =` assignment exists
- [ ] IC-3: All 11 plugin `__init__` methods in `plugins/*/src/*/plugin.py` call `super().__init__()`
- [ ] IC-4: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` `connect()` imports and raises `PluginConfigurationError` when `self._config is None`
- [ ] IC-5: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py` `try_create_iceberg_resources()` has `raise` (not `return {}`) in the except block
- [ ] IC-6: `testing/ci/test-e2e.sh` sources `testing/ci/extract-manifest-config.py` and uses `MANIFEST_*` variables as defaults
- [ ] IC-7: `testing/ci/extract-manifest-config.py` reads from the path passed as argv[1] and outputs `export MANIFEST_BUCKET=...` etc.
- [ ] IC-8: `tests/e2e/conftest.py` contains a `dbt_pipeline_result` fixture with `scope="module"`
- [ ] IC-9: `tests/e2e/test_data_pipeline.py` does NOT contain inline `run_dbt(["seed"], ...)` calls in test methods (only in fixtures)
- [ ] IC-10: `tests/e2e/test_profile_isolation.py`, `test_dbt_e2e_profile.py`, `test_plugin_system.py` do NOT exist in `tests/e2e/`
