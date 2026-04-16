# Design: E2E Zero Failures

## Problem

The E2E test suite has 10 remaining failures after the `e2e-test-stability` work unit
(which fixed 27 failures). These 10 fall into three root-cause categories:

| Group | Failures | Root Cause |
|-------|----------|------------|
| A | 7 | `Plugin not found: STORAGE:s3` — no storage plugin implementation exists |
| B | 2 | `--rollback-on-failure` unknown flag — Helm v3/v4 incompatibility on DevPod |
| C | 1 | OpenLineage parentRun facet — feature not yet implemented |

Goal: 0 failures, 0 unexpected xfails.

## Approach

### Group A: Create `floe-storage-s3` Plugin (7 tests)

**Root cause**: The `demo/manifest.yaml` declares `storage.type: s3`, and the runtime
code in `floe_orchestrator_dagster/resources/iceberg.py:110` calls
`registry.get(PluginType.STORAGE, "s3")`. No plugin is registered for this entry point.

Previously masked by the floe_iceberg import error — fixing that import exposed this.

**Design decision**: Create a `floe-storage-s3` plugin rather than making storage
config-only. Rationale:

1. The `StoragePlugin` ABC already exists with 5 well-defined abstract methods
2. The runtime code path (`create_iceberg_resources`) expects a plugin instance
3. Constitution Principle II (Plugin-First Architecture) mandates entry-point discovery
4. The `CONFIG_ONLY_TYPES` designation in `test_plugin_system.py` was a premature
   workaround because no plugin existed — it contradicts the runtime code path
5. Other pluggable types (Catalog, Compute) all have concrete implementations

**Implementation**:
- Create `plugins/floe-storage-s3/` with standard plugin structure
- Implement `StoragePlugin` ABC: `get_pyiceberg_fileio()`, `get_warehouse_uri()`,
  `get_dbt_profile_config()`, `get_dagster_io_manager_config()`, `get_helm_values_override()`
- Register entry point: `floe.storage = { s3 = "floe_storage_s3.plugin:S3StoragePlugin" }`
- Update `test_plugin_system.py`: remove STORAGE from `CONFIG_ONLY_TYPES`
- Update `test_storage_config_via_manifest` to also verify registry discovery

**Integration**:
- `iceberg.py:110` already calls `registry.get(PluginType.STORAGE, "s3")` — no changes needed
- `iceberg.py:114` configures the plugin with `storage_ref.config` — plugin must accept
  S3 config (endpoint, bucket, region, path_style_access)
- Docker image: `floe-storage-s3` must be included in `FLOE_PLUGINS`

### Group B: Helm Version-Aware Upgrade Helper (2 tests)

**Root cause**: `test_helm_upgrade_e2e.py:107` uses `--rollback-on-failure` which is
Helm v4+ only. CI pins Helm v4.1.3, but the DevPod may have Helm v3.

**Implementation**:
- Create a `testing/fixtures/helm.py` helper function that detects Helm major version
- If Helm v4+: use `--rollback-on-failure --wait`
- If Helm v3: use `--atomic` (which implies `--wait`)
- Update `test_helm_upgrade_e2e.py` and `conftest.py::run_helm` to use this helper
- Also update `testing/k8s/setup-cluster.sh` if it uses version-specific flags

### Group C: OpenLineage parentRun xfail (1 test)

**Root cause**: `test_observability.py::test_openlineage_four_emission_points` validates
that per-model dbt lineage events carry a parentRun facet. The compilation pipeline
doesn't emit these events yet — this is a planned feature, not a bug.

**Implementation**:
- Add `@pytest.mark.xfail(strict=True, reason="OpenLineage parentRun facet emission not yet implemented — tracked as feature work")` to the specific test
- Per Constitution V: "strict=True" is mandatory (unexpected pass surfaces as failure)
- This xfail should be tracked and removed when the feature is implemented

### Supplementary: Docker Image Update

The `floe-storage-s3` plugin needs to be included in the demo Docker image:
- Add `floe-storage-s3` to `FLOE_PLUGINS` in `docker/dagster-demo/Dockerfile`
- Rebuild image on DevPod with `--no-cache` (per P70)

### Final Validation Task

After all fixes: run full E2E suite on DevPod to confirm 0 failures.

## Blast Radius

| Module/File | Scope | Propagation |
|-------------|-------|-------------|
| `plugins/floe-storage-s3/` (NEW) | local | New package, no existing code touched |
| `docker/dagster-demo/Dockerfile` | adjacent | Adding plugin to image; existing plugins unaffected |
| `tests/e2e/test_plugin_system.py` | local | Removing CONFIG_ONLY workaround |
| `tests/e2e/test_helm_upgrade_e2e.py` | local | Flag compatibility only |
| `testing/fixtures/helm.py` | local | New helper; existing tests opt-in |
| `tests/e2e/test_observability.py` | local | Adding xfail marker |

**What this does NOT change**:
- floe-core schemas or compilation pipeline
- Existing plugin implementations (catalog, compute, orchestrator)
- Helm chart templates
- Demo product configurations (floe.yaml, manifest.yaml)
- CI workflows

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| S3 plugin config doesn't match what iceberg.py expects | Medium | Read existing config schema; unit test with demo manifest config |
| Removing CONFIG_ONLY exposes other discovery gaps | Low | Only STORAGE was in CONFIG_ONLY; other types already have plugins |
| Helm version detection edge cases | Low | Simple major version check; fallback to v4 behavior |
| New plugin not installed in Docker image | Medium | P70: use `--no-cache`; verify with `pip list` |

## Critic Findings

### WARN-1: Plugin Config Lifecycle

`registry.configure()` validates config and stores it in the registry but does NOT
inject it into the plugin instance. The plugin receives config at `__init__` time
(see `PolarisCatalogPlugin.__init__(config: PolarisCatalogConfig)`). The PluginLoader
may instantiate the plugin with a `MagicMock()` config if `__init__` requires a config
parameter.

**Resolution for plan phase**: Follow the CatalogPlugin pattern:
- `S3StoragePlugin.__init__(self, config: S3StorageConfig | None = None)` — accept optional config
- Store as `self._config`
- All methods access `self._config`
- `registry.configure()` validates but the actual config injection may need
  to happen via a separate `plugin.set_config()` call or by re-instantiating

### WARN-2: S3 Credentials Source

`demo/manifest.yaml` has endpoint/bucket/region/path_style_access but no access_key_id
or secret_access_key. PyIceberg's FileIO requires these.

**Resolution for plan phase**: In the demo K8s environment, MinIO credentials are set
via environment variables (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) or the MinIO defaults
(`minioadmin`/`minioadmin`). The plugin should read credentials from environment when
not present in config.

### WARN-3: xfail Scope

The test `test_openlineage_four_emission_points` spans lines 886-1114. Only the parentRun
facet assertion (lines 1077-1114) may fail. xfailing the whole test could mask earlier
assertion regressions.

**Resolution for plan phase**: Check whether the test fails at parentRun specifically or
earlier. If only parentRun, consider splitting the test or using a conditional xfail.

### INFO Notes

- Storage plugin structure must follow existing conventions (see `plugins/floe-catalog-polaris/`)
- `SecretStr` should be used for any credential fields in the config model
- The xfail should reference a tracking issue for removal when feature is implemented
- Docker `FLOE_PLUGINS` is a space-separated list in the ARG directive
