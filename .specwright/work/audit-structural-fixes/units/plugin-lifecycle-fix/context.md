# Context — Unit 1: Plugin Lifecycle Fix

baselineCommit: e1dbdb3f64b2fec5574b3c006645173418fc5800

## Summary

Add `configure()` method to `PluginMetadata` ABC, replace reflection-based config push,
add guards in plugin `connect()` methods, and make `try_create_iceberg_resources()`
fail-fast when configured plugins fail.

## Key Files

### Must Modify

- `packages/floe-core/src/floe_core/plugin_metadata.py` — ABC: add `__init__`, `configure()`, `is_configured`
- `packages/floe-core/src/floe_core/plugin_registry.py:330-334` — replace `hasattr`+`_config` with `plugin.configure()`
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` — `super().__init__()` + guard in `connect()`
- `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py` — `super().__init__()` + guard in access methods
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:187-197` — fail-fast raise

### Must Update (super().__init__())

11 plugins with custom `__init__`:
- `plugins/floe-catalog-polaris/` — `__init__(self, config: PolarisCatalogConfig)`
- `plugins/floe-storage-s3/` — `__init__(self, config: S3StorageConfig | None = None)`
- `plugins/floe-secrets-infisical/` — `__init__(self, config: InfisicalSecretsConfig)`
- `plugins/floe-secrets-k8s/` — `__init__(self, config: K8sSecretsConfig | None = None)`
- `plugins/floe-identity-keycloak/` — `__init__(self, config: KeycloakIdentityConfig)`
- `plugins/floe-semantic-cube/` — `__init__(self, config: CubeSemanticConfig)`
- `plugins/floe-ingestion-dlt/` — `__init__(self)` (no config param)
- `plugins/floe-alert-slack/` — `__init__(self, *, webhook_url="",...)`
- `plugins/floe-alert-alertmanager/` — `__init__(self, *, api_url="",...)`
- `plugins/floe-alert-email/` — `__init__(self, *, smtp_host="",...)`
- `plugins/floe-alert-webhook/` — `__init__(self, *, webhook_url="",...)`

### Must Update (tests)

- `packages/floe-core/tests/unit/test_plugin_registry.py` — ~40 inline PluginMetadata subclasses
- `packages/floe-core/tests/contract/test_plugin_abc_contract.py` — ABC contract tests
- `packages/floe-core/tests/unit/test_plugin_metadata_tracer.py` — tracer tests
- `tests/contract/test_floe_core_public_api.py` — public API contract tests
- `tests/e2e/test_plugin_system.py` — plugin system tests (will be moved in Unit 3)

## Gotchas

- Intermediate ABCs (CatalogPlugin, StoragePlugin, ComputePlugin, etc.) do NOT define
  `__init__` — they inherit from PluginMetadata and will get the new `__init__` automatically.
- Alert plugins use keyword args (`*, webhook_url=""`) not `config` param — they'll
  call `super().__init__()` but don't set `self._config` in their `__init__`.
- `loader.py:164-170` fallback `plugin_class(config=None)` — plugin `__init__` must handle
  `config=None` param AND call `super().__init__()`.
- `PluginConfigurationError` import needed in plugin files that add guards.
