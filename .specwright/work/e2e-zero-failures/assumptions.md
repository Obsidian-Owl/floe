# Assumptions: E2E Zero Failures

## A1: S3StoragePlugin Config Schema Matches Manifest

- **Type**: Clarify+Technical
- **Status**: ACCEPTED (auto-resolved)
- **Assumption**: The S3 storage plugin can accept the config keys from `demo/manifest.yaml`
  (endpoint, bucket, region, path_style_access) and map them to PyIceberg FileIO config.
- **Evidence**: The manifest config at `demo/manifest.yaml:56-63` uses standard S3 config
  keys. PyIceberg's FsspecFileIO accepts these via `s3.endpoint`, `s3.access-key-id`, etc.
  The CatalogPlugin (Polaris) follows the same pattern.
- **Resolution**: Verified by reading both the manifest schema and PyIceberg's FileIO config docs.

## A2: DevPod Helm Version Is v3.x

- **Type**: Reference+Technical
- **Status**: ACCEPTED (auto-resolved)
- **Assumption**: The Hetzner DevPod runs Helm v3.x, causing `--rollback-on-failure` to fail.
  CI runs Helm v4.1.3 where the flag works.
- **Evidence**: The 2 test failures report "unknown flag: --rollback-on-failure" which is
  Helm v4+ only. CI workflow pins `v4.1.3`. DevPod provisioning scripts don't pin Helm version.
- **Resolution**: The test helper must detect Helm version rather than assume v4.

## A3: OpenLineage Emission Is Not Implemented

- **Type**: Clarify+Technical
- **Status**: ACCEPTED (auto-resolved)
- **Assumption**: The compilation pipeline does not currently emit OpenLineage events with
  parentRun facets, making the E2E test a known feature gap.
- **Evidence**: E2E error report Category 8 explicitly documents "Observability Not Implemented".
  The test `test_openlineage_four_emission_points` validates per-model parentRun facets
  that require the full materialization pipeline to emit lineage events.
- **Resolution**: xfail with strict=True is appropriate per Constitution V.

## A4: Only STORAGE Is in CONFIG_ONLY_TYPES

- **Type**: Clarify+Technical
- **Status**: ACCEPTED (auto-resolved)
- **Assumption**: Removing STORAGE from `CONFIG_ONLY_TYPES` won't cause discovery failures
  for other plugin types.
- **Evidence**: `test_plugin_system.py:77` shows `CONFIG_ONLY_TYPES = frozenset({PluginType.STORAGE})`.
  Only STORAGE is excluded. All other 13 plugin types already have registered implementations.
- **Resolution**: Only STORAGE needs the new plugin; no other types are affected.
