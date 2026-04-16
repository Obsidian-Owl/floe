# Plan — Unit 1: Plugin Lifecycle Fix

## Task Breakdown

### Task 1: Add configure() to PluginMetadata ABC

**AC**: AC-1
**Files**:
- `packages/floe-core/src/floe_core/plugin_metadata.py` — add `__init__`, `configure()`, `is_configured`

**Signatures**:
```python
class PluginMetadata(ABC):
    def __init__(self) -> None: ...
    def configure(self, config: BaseModel | None) -> None: ...
    @property
    def is_configured(self) -> bool: ...
```

**Tests**: New tests in `test_plugin_metadata_tracer.py` or new file for configure contract.

### Task 2: Replace reflection in registry configure()

**AC**: AC-2
**Files**:
- `packages/floe-core/src/floe_core/plugin_registry.py` — replace lines 330-334

**Change map**:
- Remove `if hasattr(plugin, "_config"): plugin._config = validated_config`
- Replace with `plugin.configure(validated_config)`

**Tests**: Existing `test_plugin_registry.py` configure tests must pass. Add test
verifying `configure()` is called (not reflection).

### Task 3: Update all plugin __init__ methods

**AC**: AC-3
**Files** (11 plugins):
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py`
- `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py`
- `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py`
- `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py`
- `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- `plugins/floe-alert-slack/src/floe_alert_slack/plugin.py`
- `plugins/floe-alert-alertmanager/src/floe_alert_alertmanager/plugin.py`
- `plugins/floe-alert-email/src/floe_alert_email/plugin.py`
- `plugins/floe-alert-webhook/src/floe_alert_webhook/plugin.py`

**Pattern**: Add `super().__init__()` as first line. For plugins that accept `config`,
set `self._config = config` after super call.

**Tests**: Existing plugin tests must pass. Verify `super().__init__()` is present.

### Task 4: Add connect() guards and fail-fast

**AC**: AC-4, AC-5
**Files**:
- `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` — guard in `connect()`
- `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py` — guard in `get_pyiceberg_fileio()`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py` — fail-fast

**Change map**:
- Polaris `connect()`: add `if self._config is None: raise PluginConfigurationError(...)`
- S3 `get_pyiceberg_fileio()`: same guard
- `try_create_iceberg_resources()`: replace `return {}` with `raise` in except block

**Tests**: New tests for guard behavior. Verify both configured-and-failing (raises)
and not-configured (returns {}) paths.

### Task 5: Update test plugin subclasses

**AC**: AC-6
**Files**:
- `packages/floe-core/tests/unit/test_plugin_registry.py`
- `packages/floe-core/tests/contract/test_plugin_abc_contract.py`
- `packages/floe-core/tests/unit/test_plugin_metadata_tracer.py`
- `tests/contract/test_floe_core_public_api.py`

**Change**: Ensure inline plugin classes work with new ABC `__init__`. Most will
inherit the new `__init__` automatically. Classes that define their own `__init__`
need `super().__init__()`.

**Verification**: `make test-unit` passes.

## File Change Map

| File | Task | Change Type |
|------|------|-------------|
| `plugin_metadata.py` | 1 | Add __init__, configure(), is_configured |
| `plugin_registry.py` | 2 | Replace 3 lines (reflection → method call) |
| 11 plugin files | 3 | Add super().__init__() |
| `polaris/plugin.py` | 4 | Add guard in connect() |
| `s3/plugin.py` | 4 | Add guard in get_pyiceberg_fileio() |
| `iceberg.py` | 4 | Replace return {} with raise |
| 4 test files | 5 | Update inline plugin classes |

## Dependency Order

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 (sequential — each builds on prior)

## As-Built Notes

### Deviations from plan

- **Task 2**: The reflection code (`hasattr(plugin, "_config"): plugin._config = validated_config`) was already removed in a prior commit. The fix became adding `plugin.configure(validated_config)` as a new call rather than replacing existing reflection.
- **Task 4 (AC-5)**: `try_create_iceberg_resources()` already re-raised exceptions. Only the log message needed updating to include "catalog and storage ARE configured".
- **Task 5**: No test plugin subclasses needed changes — the ABC `__init__()` takes no required arguments, so existing test plugins get `_config = None` automatically via Python's MRO. Zero `TypeError` errors.

### Implementation decisions

- **K8s Secrets plugin**: Maintains dual attributes `self._config` (ABC) and `self.config` (legacy public). Both point to the same object. `self.config = self._config` in `__init__` preserves backward compatibility with ~40 references throughout the plugin.
- **S3 `_require_config()`**: Changed from `RuntimeError` to `PluginConfigurationError`. One existing test (`test_methods_raise_without_config`) updated to match.
- **Polaris connect() guard**: Uses lazy import of `PluginConfigurationError` to avoid circular imports.

### Actual file paths

| Task | Files changed |
|------|--------------|
| 1 | `plugin_metadata.py`, `test_plugin_configure_lifecycle.py` (NEW) |
| 2 | `plugin_registry.py`, `test_plugin_registry.py` |
| 3 | 11 plugin `plugin.py` files, `test_plugin_super_init.py` (NEW) |
| 4 | `polaris/plugin.py`, `s3/plugin.py`, `iceberg.py`, `s3/test_plugin.py`, `test_plugin_connect_guards.py` (NEW) |
| 5 | No changes needed |
