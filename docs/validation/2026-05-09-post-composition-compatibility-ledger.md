# Post-Composition Compatibility And Dead-Code Ledger

Date: 2026-05-09
Repo: /Users/dmccarthy/Projects/floe
Status: In progress

## Disposition Definitions

| Disposition | Meaning |
| --- | --- |
| Keep | Proven live consumer or required public compatibility |
| Temporary migration surface | Still needed, with owner and removal condition |
| Remove | Stale path with no proven live consumer |
| Historical docs only | Valid historical reference, not current behavior |
| Needs design | Potential issue that changes a public contract |

## Ledger

| Surface | Location | Evidence | Disposition | Follow-up |
| --- | --- | --- | --- | --- |
| Old S3 storage plugin alias and package | `plugins/floe-storage-s3`; plugin registry entry point `floe_storage_s3.plugin:S3StoragePlugin`; demo compiled artifacts with `"type": "s3"` | Task 2 baseline already records `tests/contract/test_storage_minio_rename.py` failures and `make test-unit` registry failures; Task 3 targeted search still found `demo/customer-360/compiled_artifacts.json:88`, `demo/iot-telemetry/compiled_artifacts.json:88`, and `demo/financial-risk/compiled_artifacts.json:88` with `"type": "s3"`. | Remove | Replace active demo/generated references with `minio`, remove the stale package/entry point, and regenerate artifacts after strict rename cleanup. |
| Primary Helm deployment binding renderer | `packages/floe-core/src/floe_core/cli/helm/generate.py` | Renderer search found deployment values derived from `StorageDeploymentBinding` and `CatalogDeploymentBinding`: `endpoint_internal`, `storage.endpoint.region`, `polaris.path_style_access`, and `CredentialRef` fields at `generate.py:191` through `:197`. | Keep | Keep as canonical platform Helm rendering path; future renderer work should continue reading resolved deployment bindings. |
| MinIO plugin `get_helm_values_override()` | `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py:397` | Deprecated helper still emits `minio` and `polaris.storage.s3` values directly from plugin config, with a deprecation warning pointing callers to deployment bindings. | Temporary migration surface | Find any live callers beyond unit tests, then remove or quarantine after Helm generation is fully binding-owned. |
| Storage plugin `get_pyiceberg_catalog_config()` runtime method | `packages/floe-core/src/floe_core/plugins/storage.py:118`; `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py:215`; consumers at `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:172`, `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:211`, `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py:125`, and `packages/floe-iceberg/src/floe_iceberg/writer.py:306` | Dagster resource/export/validation paths and the neutral Iceberg writer still call or reflectively probe `storage_plugin.get_pyiceberg_catalog_config()` and merge or overlay binding data, so legacy storage-owned catalog connection config remains live. | Temporary migration surface | Design a binding-first runtime catalog connection contract before removal; do not delete until Dagster resource/export/validation consumers and `floe_iceberg.writer` are migrated. |
| Dagster runtime storage/catalog plugin config fallback | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`; `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` | Runtime/export code configures catalog and storage from `artifacts.plugins.*.config` and then adds compiled binding endpoint data on selected paths. | Needs design | Decide whether runtime should consume only deployment bindings or retain plugin config for plugin startup; document the boundary before code changes. |
| dlt `catalog_config` manifest fallback | `packages/floe-core/src/floe_core/compilation/resolver.py:166`; `plugins/floe-ingestion-dlt/tests/unit/test_config.py:77` | Core rejects `plugins.ingestion.config.catalog_config`, and plugin config tests reject the same stale field. | Keep | Preserve guard until migration away from legacy manifests is complete; it prevents reintroducing ingestion-owned catalog/storage settings. |
| Secret-free deployment binding fields | `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`; `tests/contract/test_storage_binding_security.py` | `CredentialRef` and binding validators keep credential material as references; focused contract test passed with `3 passed`; required secret search produced no `target` JSON/YAML hits. | Keep | Keep contract tests in Task 4+ cleanup so renderer/runtime migrations cannot inline secrets. |
| Cross-plugin concrete imports | `packages`, `plugins` Python sources | Required import search plus targeted review found no source-level concrete storage/catalog plugin import edge outside tests; implementation code uses `floe_core` ABCs/registry and package-internal imports. `floe_iceberg` is used as a public package API by Dagster/core. | Keep | Treat direct concrete plugin imports across plugin packages as disallowed unless explicitly promoted to a public package API. |
