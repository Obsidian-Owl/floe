# Context: E2E Zero Failures

## Key File Paths

### Group A: STORAGE:s3 Plugin

- **StoragePlugin ABC**: `packages/floe-core/src/floe_core/plugins/storage.py:56-204`
  - 5 abstract methods: `get_pyiceberg_fileio()`, `get_warehouse_uri()`,
    `get_dbt_profile_config()`, `get_dagster_io_manager_config()`, `get_helm_values_override()`
  - `FileIO` protocol at line 31 (PyIceberg-compatible)
- **Plugin types**: `packages/floe-core/src/floe_core/plugin_types.py:50`
  - `PluginType.STORAGE = "floe.storage"` (entry point group)
- **Plugin discovery**: `packages/floe-core/src/floe_core/plugins/discovery.py`
- **Plugin loader**: `packages/floe-core/src/floe_core/plugins/loader.py:122`
  - Raises `PluginNotFoundError` when entry point is None
- **Plugin errors**: `packages/floe-core/src/floe_core/plugin_errors.py:85`
  - `"Plugin not found: {plugin_type.name}:{name}"`
- **Runtime usage**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`
  - Line 110: `registry.get(PluginType.STORAGE, storage_ref.type)` — WHERE IT FAILS
  - Line 114: `registry.configure(PluginType.STORAGE, storage_ref.type, storage_ref.config)`
  - Line 127-131: `IcebergTableManager(catalog_plugin=..., storage_plugin=...)`
- **Demo manifest storage config**: `demo/manifest.yaml:56-63`
  ```yaml
  storage:
    type: s3
    config:
      endpoint: http://floe-platform-minio:9000
      bucket: floe-data
      region: us-east-1
      path_style_access: true
  ```
- **Test plugin system**: `tests/e2e/test_plugin_system.py:73-181`
  - `CONFIG_ONLY_TYPES = frozenset({PluginType.STORAGE})` at line 77 — MUST BE REMOVED
  - `test_storage_config_via_manifest()` at line 154 — needs update
- **Existing plugin examples** (follow same structure):
  - `plugins/floe-catalog-polaris/` — CatalogPlugin implementation
  - `plugins/floe-compute-duckdb/` — ComputePlugin implementation
- **Docker image**: `docker/dagster-demo/Dockerfile`
  - Line 57: `FLOE_PLUGINS` ARG
  - Line 104: Plugin install loop
- **PluginMetadata base**: `packages/floe-core/src/floe_core/plugin_metadata.py`

### Group B: Helm Version Compatibility

- **Test using --rollback-on-failure**: `tests/e2e/test_helm_upgrade_e2e.py:107`
- **CI Helm version**: `.github/workflows/helm-ci.yaml` — pinned to `v4.1.3`
- **Pattern P69**: `.specwright/patterns.md` — `--rollback-on-failure` does NOT imply `--wait` in v4
- **Existing helm helper**: `testing/fixtures/helm.py` — has `recover_stuck_helm_release()`
- **conftest.py**: `tests/e2e/conftest.py` — `run_helm()` function
- **setup-cluster.sh**: `testing/k8s/setup-cluster.sh:259-268` — uses `--wait` only (no rollback flag)

### Group C: OpenLineage parentRun

- **Failing test**: `tests/e2e/test_observability.py:886-1114`
  - `test_openlineage_four_emission_points()` — parentRun facet validation at lines 1077-1114
- **Facet builder**: `packages/floe-core/src/floe_core/lineage/facets.py:211-263`
  - `ParentRunFacetBuilder.from_parent()` — builds the facet structure
- **Lineage extraction**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py:216-220`
  - Creates parentRun facet from parent_run_id
- **Marquez API**: `GET /api/v1/namespaces/{ns}/jobs/{job}/runs`

## Gotchas

1. **Docker build cache (P70)**: Must use `--no-cache` when adding `floe-storage-s3` to `FLOE_PLUGINS`
2. **Plugin structure convention**: All plugins follow `src/{name}/plugin.py` + `pyproject.toml` with entry points
3. **PyIceberg FileIO**: The StoragePlugin's `get_pyiceberg_fileio()` must return an object satisfying the `FileIO` protocol — typically `pyiceberg.io.fsspec.FsspecFileIO` with S3 config
4. **S3 config keys**: PyIceberg uses specific key names: `s3.endpoint`, `s3.access-key-id`, `s3.secret-access-key`, `s3.region`, `s3.path-style-access`
5. **Helm v3 `--atomic` implies `--wait`**: When falling back to v3, `--atomic` is sufficient (no separate `--wait` needed)
6. **xfail strict=True (Constitution V)**: All xfails MUST be strict — unexpected pass is a test failure

## Prior Work Units

This is the 20th E2E-related work unit. Key predecessors:
- `e2e-test-stability` (just shipped): Fixed 27 failures, exposed these 10
- `e2e-alpha-stability`: Fixed Polaris OAuth2, DuckDB path assertions
- `e2e-production-fixes`: Fixed Dagster GraphQL, pod label discovery
- `openlineage-observability-fixes`: Fixed OTel/lineage wiring
