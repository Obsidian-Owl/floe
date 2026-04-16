# Plan: E2E Zero Failures

## Task Breakdown

### T1: Create S3StoragePlugin package structure

**ACs**: AC-1, AC-2

Create `plugins/floe-storage-s3/` following the convention of `plugins/floe-catalog-polaris/`.

**File change map**:
- CREATE `plugins/floe-storage-s3/pyproject.toml` — package metadata + entry point
- CREATE `plugins/floe-storage-s3/src/floe_storage_s3/__init__.py` — public exports
- CREATE `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py` — `S3StoragePlugin` class
- CREATE `plugins/floe-storage-s3/src/floe_storage_s3/config.py` — `S3StorageConfig` model

**Plugin structure reference** (from `plugins/floe-catalog-polaris/`):
```
plugins/floe-storage-s3/
├── pyproject.toml
├── src/
│   └── floe_storage_s3/
│       ├── __init__.py
│       ├── plugin.py      # S3StoragePlugin(StoragePlugin)
│       └── config.py       # S3StorageConfig(BaseModel)
└── tests/
    └── unit/
        └── test_plugin.py
```

**Entry point** in `pyproject.toml`:
```toml
[project.entry-points."floe.storage"]
s3 = "floe_storage_s3.plugin:S3StoragePlugin"
```

**S3StorageConfig fields**:
```python
class S3StorageConfig(BaseModel):
    endpoint: str                              # e.g. http://floe-platform-minio:9000
    bucket: str                                # e.g. floe-data
    region: str = "us-east-1"
    path_style_access: bool = True
    access_key_id: SecretStr | None = None     # Falls back to AWS_ACCESS_KEY_ID env
    secret_access_key: SecretStr | None = None # Falls back to AWS_SECRET_ACCESS_KEY env
```

**S3StoragePlugin method signatures**:
```python
class S3StoragePlugin(StoragePlugin):
    def __init__(self, config: S3StorageConfig | None = None) -> None: ...
    # StoragePlugin ABC (5 abstract methods):
    def get_pyiceberg_fileio(self) -> FileIO: ...
    def get_warehouse_uri(self, namespace: str) -> str: ...
    def get_dbt_profile_config(self) -> dict[str, Any]: ...
    def get_dagster_io_manager_config(self) -> dict[str, Any]: ...
    def get_helm_values_override(self) -> dict[str, Any]: ...
    # PluginMetadata override (NOT in StoragePlugin ABC, but required for
    # registry.configure() to validate config — default returns None which
    # skips validation):
    def get_config_schema(self) -> type[BaseModel]: ...
    # PluginMetadata abstract properties: name, version, floe_api_version
```

**Note**: `__init__` accepts `config=None` so the PluginLoader can instantiate
without MagicMock. When `config` is None, methods should raise a clear error
("Plugin not configured — call with config parameter").

### T2: Fix plugin config injection in create_iceberg_resources

**ACs**: AC-3

The current code calls `registry.get()` which instantiates the plugin with MagicMock
config (via `loader.py:171`), then `registry.configure()` validates config but doesn't
push it to the plugin instance. The cached plugin in `_loaded` retains MagicMock config.

**File change map**:
- EDIT `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`

**Approach**: After `registry.configure()` validates config, re-instantiate the plugin
with the real config using `type()` to get the class. No private attribute mutation.

```python
# Current (broken — plugin has MagicMock config):
storage_plugin = registry.get(PluginType.STORAGE, storage_ref.type)
if storage_ref.config:
    registry.configure(PluginType.STORAGE, storage_ref.type, storage_ref.config)

# Fixed — re-instantiate with validated config:
storage_plugin = registry.get(PluginType.STORAGE, storage_ref.type)
if storage_ref.config:
    validated_config = registry.configure(
        PluginType.STORAGE, storage_ref.type, storage_ref.config
    )
    if validated_config is not None:
        storage_plugin = type(storage_plugin)(config=validated_config)
```

**IMPORTANT**: Apply the same fix to `catalog_plugin` (lines 99-103). The catalog
plugin has the same MagicMock config issue — it just hasn't surfaced because the
STORAGE error blocks first. Both must be fixed to reach AC-8.

### T3: Update test_plugin_system.py

**ACs**: AC-4

**File change map**:
- EDIT `tests/e2e/test_plugin_system.py`

Changes:
1. Remove `PluginType.STORAGE` from `CONFIG_ONLY_TYPES` (line 77-81)
2. Update `test_storage_config_via_manifest()` to verify registry discovery works
3. If `CONFIG_ONLY_TYPES` becomes empty, remove the frozenset and simplify
   `test_all_plugin_types_discoverable()`

### T4: Update Docker image

**ACs**: AC-5

**File change map**:
- EDIT `docker/dagster-demo/Dockerfile` — add `floe-storage-s3` to `FLOE_PLUGINS`

The `FLOE_PLUGINS` ARG is a space-separated list. Add `floe-storage-s3` to the default value.

### T5: Create Helm version-aware upgrade helper

**ACs**: AC-6

**File change map**:
- EDIT `testing/fixtures/helm.py` — add `get_helm_upgrade_flags()` function
- EDIT `tests/e2e/test_helm_upgrade_e2e.py` — use helper for flag selection

**Helper signature**:
```python
def get_helm_upgrade_flags() -> list[str]:
    """Return Helm upgrade flags appropriate for the installed version.

    Helm v4+: ["--rollback-on-failure", "--wait"]
    Helm v3:  ["--atomic"]
    """
```

**Detection**: Run `helm version --short`, parse major version from output like `v4.1.3`.
Default to v3 flags on detection failure (safer/more compatible).

### T6: Extract and xfail parentRun assertion

**ACs**: AC-7

**File change map**:
- EDIT `tests/e2e/test_observability.py`

Extract the parentRun facet check (lines 1077-1114) from
`test_openlineage_four_emission_points` into a new test:

```python
@pytest.mark.e2e
@pytest.mark.requirement("FR-040")
@pytest.mark.xfail(
    strict=True,
    reason="parentRun facet emission not yet implemented in LineageResource",
)
def test_openlineage_parent_run_facet(self, ...) -> None:
    """Test that per-model events carry parentRun facet (AC-6)."""
    ...
```

The original test retains AC-1 through AC-5 assertions (emission points, job/run
existence, event types, durations).

**Verification step**: Before extracting, confirm the test actually fails at the
parentRun assertion (line 1106) and not earlier. If it fails earlier, adjust
the extraction scope accordingly.

**Tracking**: Create a GitHub issue for the parentRun feature gap so the xfail
can be removed when OpenLineage emission is implemented.

### T7: Run full E2E suite on DevPod

**ACs**: AC-8

- Start DevPod: `make devpod-start` (or verify already running)
- Rebuild Docker image with `--no-cache` (per P70)
- Install `floe-storage-s3` in dev environment: `uv pip install -e plugins/floe-storage-s3`
- Run: `make test-e2e`
- Verify: 0 failures, all xfails use strict=True

## Architecture Notes

- The S3StoragePlugin is a thin wrapper — it constructs PyIceberg's `FsspecFileIO`
  with S3 config and generates warehouse URIs. No complex logic.
- Credentials: S3 access keys are read from env vars (`AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`). In the demo K8s environment, MinIO sets these via
  env vars in the Dagster deployment. The config model has optional `SecretStr`
  fields as override.
- The config injection fix (T2) also benefits the catalog plugin which has
  the same MagicMock config issue — it just hasn't surfaced because the
  STORAGE error blocks first.

## As-Built Notes

### T1: S3StoragePlugin
- Created `plugins/floe-storage-s3/` with pyproject.toml, config.py, plugin.py, __init__.py
- Had to create `README.md` (hatchling requires it for build)
- 23 unit tests covering metadata, config validation, and all 5 ABC methods
- `_require_config()` helper raises RuntimeError with clear message when unconfigured

### T2: Config injection fix
- Applied re-instantiation to both catalog and storage plugins in `iceberg.py`
- Pattern: `type(plugin)(config=validated_config)` — clean, no private attribute access
- Pyright flags `No parameter named "config"` because `type()` returns generic type — runtime correct

### T3: CONFIG_ONLY_TYPES
- Set `CONFIG_ONLY_TYPES = frozenset()` (empty) rather than removing the attribute
  to avoid breaking any external references
- Updated assertion messages and log labels
- Added registry.get() verification to test_storage_config_via_manifest

### T4: Docker image
- Added COPY and FLOE_PLUGINS entries in both Stage 1 (export) and Stage 2 (build)

### T5: Helm flags
- Helper uses `helm version --short`, parses "v4.1.3" format
- Falls back to v3 `--atomic` on any detection failure
- Import moved inside test function to avoid import at module level

### T6: parentRun xfail
- New test `test_openlineage_parent_run_facet` is self-contained — queries Marquez independently
- Original test loses AC-6 marker, retains AC-5 and FR-041
- xfail uses strict=True per Constitution V
