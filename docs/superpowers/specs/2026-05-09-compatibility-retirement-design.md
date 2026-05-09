# Compatibility Retirement Design

Date: 2026-05-09
Status: Draft for review

## Goal

Retire deprecated compatibility helpers only after typed replacement contracts and
consumer migrations are proven.

This design keeps the post-composition direction strict: durable structural
contracts replace compatibility layers, compatibility remains only where current
code proves it is still necessary, plugin implementations do not become coupled
to other plugin implementations, `CompiledArtifacts` remains secret-free, and
renderers consume resolved deployment bindings instead of rediscovering raw
plugin config.

## Mapping Command

Current helper surfaces were mapped with:

```bash
rg -n "get_pyiceberg_catalog_config|get_helm_values_override|get_source_config\\(catalog_config|artifacts\\.plugins\\.(storage|catalog)\\.config" packages plugins tests docs -g '*.py' -g '*.md'
```

The search shows four compatibility families still present:

- Storage-owned PyIceberg catalog config remains a live runtime dependency.
- MinIO Helm override remains implemented and tested, but no first-party
  production caller was found beyond ABC or plugin implementation surfaces.
- dlt sink source config still exposes a raw `catalog_config` compatibility API.
- Semantic layer Helm override remains an ABC, Cube implementation, and test
  contract surface.

## Candidate Helpers

- `StoragePlugin.get_pyiceberg_catalog_config()`
- MinIO `get_helm_values_override()`
- dlt sink `get_source_config(catalog_config)`
- Semantic layer `get_helm_values_override()`

## Current Surfaces / Ledger

| Surface | Production consumers | Tests | Docs and plans | Classification |
| --- | --- | --- | --- | --- |
| `StoragePlugin.get_pyiceberg_catalog_config()` | ABC definition at `packages/floe-core/src/floe_core/plugins/storage.py:118`; MinIO implementation at `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py:215`; Dagster runtime calls in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:172`, `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:211`, and `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py:125`; neutral writer reflective probe at `packages/floe-iceberg/src/floe_iceberg/writer.py:306`. | Writer compatibility test at `packages/floe-iceberg/tests/unit/test_writer.py:525`; Dagster export, wiring, and validation tests mock or assert calls in `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`, `plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py`, and `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`; MinIO unit coverage in `plugins/floe-storage-minio/tests/unit/test_plugin.py`. | Compatibility ledger, integration audit, plugin matrix, and binding-first Dagster/Iceberg design under `docs/validation/` and `docs/superpowers/specs/2026-05-09-binding-first-dagster-iceberg-runtime-design.md`. | Keep until runtime consumers migrate. This helper is not removable while Dagster resource/export/validation code or `floe_iceberg.writer` calls or probes it. |
| `artifacts.plugins.storage.config` / `artifacts.plugins.catalog.config` runtime rediscovery | Dagster export still reads `artifacts.plugins.catalog.config` and `artifacts.plugins.storage.config` in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py:177` and `:179`. The integration audit also records resource-path rediscovery from plugin refs. | Contract assertions in `tests/contract/test_storage_binding_security.py:50` and `:51`; Dagster validation tests copy catalog config in `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py:146`. | Runtime migration is called out by the integration audit and binding-first Dagster/Iceberg design. | Guard before removal. Runtime code must consume deployment bindings for connection material and use plugin config only for plugin instance validation while compatibility remains. |
| MinIO `get_helm_values_override()` | Storage ABC helper at `packages/floe-core/src/floe_core/plugins/storage.py:197`; MinIO implementation at `plugins/floe-storage-minio/src/floe_storage_minio/plugin.py:397`; the implementation warns callers that binding-driven Helm rendering is canonical. Required search found no first-party production caller beyond these definition and implementation surfaces. | MinIO unit tests call the helper in `plugins/floe-storage-minio/tests/unit/test_plugin.py:242`, `:354`, and `:426`; test stubs in `packages/floe-iceberg/tests/conftest.py:409` and `packages/floe-iceberg/tests/integration/conftest.py:329`; golden regression scan in `tests/contract/test_golden_regression.py:323`. | Storage architecture docs and ADRs still describe this compatibility surface; compatibility ledger says remove or quarantine after confirming no external API promise and binding-owned Helm generation is canonical. | Candidate for earliest quarantine after tests are moved to the Helm renderer contract. Removal from the public ABC requires an explicit public API compatibility decision or documented deprecation window. No plugin-owned Helm config should remain a renderer input. |
| dlt sink `get_source_config(catalog_config)` | Public sink API in `packages/floe-core/src/floe_core/plugins/sink.py:256`; dlt sink implementation in `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py:1173`. No first-party production call site was found by the required search, but the API still accepts raw catalog config. | Direct unit callers in `plugins/floe-ingestion-dlt/tests/unit/test_dlt_sink_connector.py:188` and `:354`; core signature contract in `packages/floe-core/tests/unit/test_sink_connector.py:227`. | dlt ingestion cleanup docs explicitly preserve the method for now. Compatibility ledger marks it `Needs design`. | Do not remove until the replacement source-read contract is typed. The replacement should be deployment-binding or `CredentialRef` based, not a raw secret-bearing dict. |
| Semantic layer `get_helm_values_override()` | Semantic ABC helper at `packages/floe-core/src/floe_core/plugins/semantic.py:205`; Cube implementation at `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py:222`. | ABC contract tests in `tests/contract/test_semantic_layer_abc.py`; Cube unit tests in `plugins/floe-semantic-cube/tests/unit/test_plugin.py:132` through `:155`. | Semantic datasource binding design in `docs/superpowers/specs/2026-05-09-semantic-datasource-binding-design.md`; older architecture and epic docs still mention Helm override. | Keep until semantic datasource bindings are designed and renderer/runtime tests prove Cube consumes compute/catalog/storage projections rather than static Helm override values. Removal from the public ABC requires the same public API compatibility decision or documented deprecation window as storage Helm overrides. |

## Retirement Rules

1. A helper can be removed from production code only when no production source
   references it.
2. A public ABC helper can be removed only after an explicit public API
   compatibility decision is recorded. If external plugin compatibility is
   uncertain, quarantine the helper behind a deprecation warning or documented
   compatibility window instead of deleting the ABC method.
3. A guard test must fail if renderer/runtime code rediscover plugin config
   instead of consuming deployment bindings.
4. Secret-free compiled artifact tests must pass after removal or quarantine.
5. Remote DevPod runtime validation must pass after the final retirement wave.

## Replacement Contract Requirements

- Runtime catalog connection material must be translated from typed deployment
  bindings, not from `StoragePlugin.get_pyiceberg_catalog_config()`.
- Helm renderers must consume deployment bindings produced by compilation and
  must not call plugin `get_helm_values_override()` methods.
- Source-read configuration for dlt sinks must be typed and secret-reference
  based before `get_source_config(catalog_config)` can be retired.
- Semantic datasource rendering must consume typed compute, catalog, and storage
  projections before semantic Helm overrides can be removed.
- Plugin config may remain available for configuring the plugin instance itself
  during migration, but it cannot be the renderer or runtime source of endpoint,
  credential, bucket, catalog, or datasource facts.

## Guard Tests

- Add Dagster resource/export/validation tests that use storage plugins whose
  `get_pyiceberg_catalog_config()` method raises if called, then prove runtime
  connection config is assembled from deployment bindings.
- Add a neutral Iceberg writer test that passes an explicit typed catalog
  connection input and fails if the writer reflectively probes the storage
  plugin for compatibility config.
- Add Helm renderer tests that fail when storage or semantic renderers call
  plugin `get_helm_values_override()` instead of consuming deployment bindings.
- Keep secret-free compiled artifact tests covering storage credentials and
  deployment bindings after each helper removal.
- Add or preserve negative tests proving raw catalog config cannot carry
  plaintext access keys or secret values into compiled artifacts.

## Retirement Sequence

1. Migrate Dagster runtime and export paths to the binding-first Iceberg runtime
   contract. Verify no production Dagster path calls
   `StoragePlugin.get_pyiceberg_catalog_config()` or depends on
   `artifacts.plugins.storage.config` / `artifacts.plugins.catalog.config` for
   runtime connection facts.
2. Migrate `floe_iceberg.writer` to an explicit typed runtime connection input.
   Remove the reflective storage-plugin probe only after Dagster callers pass
   the typed input.
3. Quarantine MinIO `get_helm_values_override()` after Helm renderer tests prove
   storage deployment values come from bindings. Remove it from the public
   storage ABC only after the public API compatibility decision or deprecation
   window required by the retirement rules.
4. Design and migrate dlt sink source config to a typed binding or
   `CredentialRef`-only contract, then remove `get_source_config(catalog_config)`.
5. Design and migrate semantic datasource bindings, then remove semantic layer
   `get_helm_values_override()` from the Cube path. Remove it from the public
   semantic ABC only after the public API compatibility decision or deprecation
   window required by the retirement rules.
6. Run the full local and remote validation lanes before the final retirement
   wave is declared complete.

## Acceptance Evidence

- Source search shows no production references to removed helpers.
- Public ABC removals cite the API compatibility decision or deprecation window
  that made removal acceptable.
- Guard tests cover renderer/runtime ownership.
- Unit, contract, Helm, and remote runtime lanes pass.
- `CompiledArtifacts` remains secret-free in contract tests after each removal.
- Rendered Helm values and runtime connection config are derived from deployment
  bindings, not rediscovered plugin implementation config.

## Out of Scope

- Do not remove helpers in this design task.
- Do not run the provider compatibility spike.
- Do not widen compiled artifacts with raw secrets.
- Do not couple plugin implementations to each other while replacing the
  compatibility helpers.
