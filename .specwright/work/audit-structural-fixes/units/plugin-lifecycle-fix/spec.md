# Spec — Unit 1: Plugin Lifecycle Fix

## Overview

Close the unsafe config window in the plugin lifecycle by adding `configure()` to
the ABC, replacing reflection-based config push, adding guards in `connect()`,
and making `try_create_iceberg_resources()` fail-fast when configured plugins fail.

## Acceptance Criteria

### AC-1: PluginMetadata ABC declares _config and configure()

`PluginMetadata.__init__()` MUST initialize `self._config: BaseModel | None = None`.
`PluginMetadata.configure(config)` MUST set `self._config = config`.
`PluginMetadata.is_configured` property MUST return `self._config is not None`.

**Verifiable conditions:**

1. `PluginMetadata.__init__` exists and sets `self._config = None`.
2. `configure()` is a concrete (not abstract) method that accepts `BaseModel | None`.
3. `is_configured` is a property that returns `bool`.
4. A freshly instantiated plugin has `is_configured == False`.
5. After `plugin.configure(SomeConfig(...))`, `is_configured == True`.
6. After `plugin.configure(None)`, `is_configured == False`.

### AC-2: Registry uses configure() instead of reflection

`plugin_registry.py` configure() method MUST call `plugin.configure(validated_config)`
instead of `if hasattr(plugin, "_config"): plugin._config = validated_config`.

**Verifiable conditions:**

1. No `hasattr(plugin, "_config")` in `plugin_registry.py`.
2. No direct `plugin._config = ` assignment in `plugin_registry.py`.
3. `plugin.configure(validated_config)` is called after validation succeeds.
4. Existing configure() tests still pass (config validation, error conversion, etc.).

### AC-3: All plugins with __init__ call super().__init__()

Every plugin subclass that defines `__init__` MUST call `super().__init__()` as
its first statement. Plugins that accept `config` in `__init__` retain this for
direct instantiation (e.g., in tests), but the `__init__`-provided config is
treated as an initial value that `configure()` may later override. The precedence
rule is: **last write wins** — `configure()` is always called after `__init__`
in the registry path, so it always takes precedence. Direct instantiation with
`config=` is a convenience for tests and standalone usage only.

**Verifiable conditions:**

1. All 11 plugins with custom `__init__` call `super().__init__()`.
2. Plugins that accept `config` in `__init__` set `self._config = config` AFTER `super().__init__()`.
3. Direct instantiation: `PolarisCatalogPlugin(config=real_config)` results in `is_configured == True`.
4. Registry path: `loader` creates with `config=None`, then `registry.configure()` pushes real config.
   After both calls, `plugin._config` is the registry-provided config (configure wins over __init__).
5. All existing plugin unit tests pass.
6. `loader.py` `plugin_class(config=None)` fallback still works.

### AC-4: connect() guards against unconfigured state

Polaris `connect()` and S3 storage access methods MUST raise `PluginConfigurationError`
when `self._config is None`.

**Verifiable conditions:**

1. `PolarisCatalogPlugin.connect()` raises `PluginConfigurationError` when `_config is None`.
2. `S3StoragePlugin.get_pyiceberg_fileio()` raises `PluginConfigurationError` when `_config is None`.
3. Error message includes plugin name and "not configured".
4. When `_config` is set (via `configure()`), `connect()` proceeds normally.

### AC-5: try_create_iceberg_resources() fails fast when configured

When `plugins.catalog` AND `plugins.storage` are both configured but
`create_iceberg_resources()` raises, the exception MUST propagate (re-raise).
When either is `None`, the function MUST return `{}` silently (existing behavior).

**Verifiable conditions:**

1. `try_create_iceberg_resources()` with `catalog=None` returns `{}` (no exception).
2. `try_create_iceberg_resources()` with `storage=None` returns `{}` (no exception).
3. `try_create_iceberg_resources()` with both configured but failing raises the original exception.
4. The `logger.exception()` call before re-raise includes "catalog and storage ARE configured"
   (the re-raised exception itself keeps its original message).
5. No `return {}` after the `except Exception` block when both are configured.

### AC-6: Test plugins in test files updated

All inline `PluginMetadata` subclasses in test files MUST work with the new ABC
`__init__`. Tests that directly construct plugins MUST still pass.

**Verifiable conditions:**

1. `test_plugin_registry.py` — all ~40 inline plugin classes work with new ABC.
2. `test_plugin_abc_contract.py` — contract tests pass.
3. `test_floe_core_public_api.py` — public API tests pass.
4. `make test-unit` passes with zero failures in plugin-related tests.
5. Zero `TypeError: __init__() missing` errors from plugin instantiation in test output.
6. New test: calling `connect()` after `configure(None)` on a previously-configured plugin
   raises `PluginConfigurationError` (config reset edge case).
