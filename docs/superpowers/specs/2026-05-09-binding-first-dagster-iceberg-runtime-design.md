# Binding-First Dagster/Iceberg Runtime Design

Date: 2026-05-09

Status: Draft for review

## Goal

Migrate Dagster and `floe_iceberg.writer` runtime connection setup from storage-owned catalog config to a neutral runtime input derived from `CompiledArtifacts.deployment`.

The long-term contract is that renderers and runtimes consume resolved deployment bindings. Storage and catalog plugins participate in compilation by emitting or translating deployment bindings, but they do not expose cross-plugin implementation config for other plugins or runtime packages to inspect.

## Current Consumers

The required mapping command was run:

```bash
rg -n "get_pyiceberg_catalog_config|artifacts\.plugins\.(storage|catalog)\.config|StorageDeploymentBinding|CatalogDeploymentBinding|_catalog_connection_config_from_binding" plugins/floe-orchestrator-dagster packages/floe-iceberg packages/floe-core -g '*.py'
```

The live runtime consumers are:

- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`
  - `_catalog_connection_config_from_binding()` currently derives a partial PyIceberg S3 config from `DagsterStorageBinding.resources`.
  - `create_iceberg_resources()` still merges `storage_plugin.get_pyiceberg_catalog_config()` with that binding-derived config before constructing `IcebergTableManagerConfig`.
  - `try_create_iceberg_resources()` passes the compiled Dagster storage projection into the resource factory.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
  - `export_dbt_to_iceberg()` reads `artifacts.plugins.catalog.config` and `artifacts.plugins.storage.config` to configure plugin instances.
  - `_apply_compiled_storage_endpoint()` overlays `artifacts.deployment.storage.endpoint.internal_url` and `.region` onto storage-owned catalog config.
  - The writer is constructed with `catalog_connection_config` after calling `storage_plugin.get_pyiceberg_catalog_config()`.
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/validation/iceberg_outputs.py`
  - `connect_catalog_from_artifacts()` configures catalog/storage plugins, calls `storage_plugin.get_pyiceberg_catalog_config()`, then overlays endpoint and region from `artifacts.deployment.storage`.
- `packages/floe-iceberg/src/floe_iceberg/writer.py`
  - `DefaultIcebergTableWriter._catalog_config()` uses an explicit `catalog_connection_config` when provided.
  - If no explicit config is provided, it reflectively probes the storage plugin for `get_pyiceberg_catalog_config()`.

The schema and plugin contract surfaces found by the same command are:

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - `StorageDeploymentBinding` already carries provider, protocol, endpoint, warehouse, allowed locations, buckets, credential references, runtime, dbt, and dagster projections.
  - `CatalogDeploymentBinding` already carries provider-specific catalog projections including Polaris and Iceberg REST catalog fields.
  - `DeploymentConfig` already exposes `storage`, `catalog`, and `ingestion` under `CompiledArtifacts.deployment`.
- `packages/floe-core/src/floe_core/plugins/storage.py`
  - `StoragePlugin.get_pyiceberg_catalog_config()` is currently documented as an overridable storage-owned PyIceberg catalog config hook.
  - This is the method to remove or quarantine after runtime consumers migrate.
- `packages/floe-core/src/floe_core/plugins/catalog.py`
  - `CatalogPlugin.build_catalog_deployment(storage: StorageDeploymentBinding) -> CatalogDeploymentBinding` already translates neutral storage bindings into catalog-owned deployment config during compilation.
- `packages/floe-core/src/floe_core/cli/helm/generate.py`
  - Helm generation already consumes `StorageDeploymentBinding` and `CatalogDeploymentBinding`, which confirms deployment bindings are not Dagster-only.

The mapped tests that prove the old helper is still coupled into expected behavior include:

- `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`
- `plugins/floe-orchestrator-dagster/tests/unit/test_iceberg_wiring.py`
- `plugins/floe-orchestrator-dagster/tests/unit/test_validation_iceberg_outputs.py`
- `packages/floe-iceberg/tests/unit/test_writer.py`
- `packages/floe-core/tests/unit/compilation/test_storage_deployment_binding.py`
- `packages/floe-core/tests/unit/schemas/test_compiled_artifacts.py`

## Problem

The current runtime path is halfway migrated. It already has secret-free deployment bindings in `CompiledArtifacts.deployment`, but Dagster and the writer still treat `StoragePlugin.get_pyiceberg_catalog_config()` as the base PyIceberg catalog config and then patch in selected deployment fields.

That keeps a storage plugin in the position of describing catalog connection details for another plugin. It also forces runtimes to know which fields to overlay and makes endpoint/warehouse/path-style/credential-reference behavior inconsistent across Dagster resources, Dagster export, validation, and the neutral writer.

## Proposed Contract

Add a neutral runtime catalog connection object derived from `StorageDeploymentBinding` and `CatalogDeploymentBinding`.

The object should be secret-free and suitable as the common runtime input for Dagster and `floe_iceberg.writer`. It carries:

- Catalog endpoint metadata, such as Iceberg REST URI or provider-specific internal endpoint.
- Warehouse metadata, from the catalog binding when catalog-owned and from the storage binding when storage-owned.
- Storage endpoint metadata, including internal object-store endpoint.
- Path-style access, where required by S3-compatible storage.
- Region.
- Credential-reference metadata only, such as secret names, env var names, and credential reference keys.
- Optional catalog properties that have passed the existing compiled-artifact secret scanners.

It must not carry raw access keys, client secrets, tokens, passwords, or any value that would violate the current compiled artifact secret-free guarantees.

An implementation can expose this as a Pydantic model in `floe_core.schemas.compiled_artifacts`, for example:

```python
class RuntimeCatalogConnection(BaseModel):
    catalog_name: NonEmptyString = "iceberg"
    catalog_uri: NonEmptyString | None = None
    warehouse: NonEmptyString | None = None
    storage_endpoint: NonEmptyString | None = None
    region: NonEmptyString | None = None
    path_style_access: bool | None = None
    properties: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
    env_refs: dict[str, NonEmptyString] = Field(default_factory=dict)
```

The exact name can change during implementation, but the ownership must not: this is a compiled deployment/runtime projection, not a method on `StoragePlugin`.

Runtime packages then translate this neutral object into execution-library config:

- Dagster resource construction translates it into `IcebergTableManagerConfig.catalog_connection_config`.
- Dagster export translates it into the `catalog_connection_config` passed to `DefaultIcebergTableWriter`.
- Dagster validation translates it into the config passed to `catalog_plugin.connect()`.
- `DefaultIcebergTableWriter` accepts the already translated connection config or a typed runtime connection object; it does not discover config by probing the storage plugin.

## Ownership

- `floe-core` owns the compiled deployment binding schema and the derivation of a secret-free runtime catalog connection projection from storage and catalog deployment bindings.
- Runtime packages own translation from the neutral projection into execution-library-specific config, such as PyIceberg catalog properties.
- `floe-orchestrator-dagster` owns Dagster resource wiring, export flow, validation entry points, DuckDB table discovery, and Dagster-specific resource construction.
- `floe-iceberg` owns Iceberg table mutation semantics and writer behavior, but it should receive explicit runtime connection input instead of reading storage plugin internals.
- Storage plugins own object-store capabilities, endpoint/warehouse/credential references, and FileIO construction.
- Catalog plugins own catalog deployment translation, catalog connectivity, and catalog-specific projections such as Polaris or Iceberg REST.

No plugin should know another plugin's implementation details. `CompiledArtifacts` remains secret-free. Renderers and runtimes consume resolved deployment bindings.

## Migration Plan

1. Add tests first for the new binding-derived runtime connection contract.
   - Cover storage endpoint, warehouse, path-style access, region, catalog URI, and credential references.
   - Assert raw secret-like values are rejected or absent from compiled artifacts.
   - Assert missing optional deployment fields degrade to explicit `None` or omitted PyIceberg keys, not helper fallbacks.

2. Migrate Dagster resource wiring.
   - Replace `_catalog_connection_config_from_binding(DagsterStorageBinding)` with a helper that consumes the new runtime catalog connection projection.
   - Stop merging `storage_plugin.get_pyiceberg_catalog_config()` into `IcebergTableManagerConfig`.
   - Keep plugin `configure()` calls for validating plugin config and preventing cached state leaks.

3. Migrate Dagster export.
   - Keep `artifacts.plugins.catalog.config` and `artifacts.plugins.storage.config` only for plugin instance validation/configuration.
   - Replace `_apply_compiled_storage_endpoint(storage_plugin.get_pyiceberg_catalog_config(), artifacts)` with runtime connection translation from `artifacts.deployment`.
   - Pass the resulting explicit connection config into `DefaultIcebergTableWriter`.

4. Migrate Dagster validation.
   - Replace `storage_plugin.get_pyiceberg_catalog_config()` plus endpoint overlay with runtime connection translation from deployment bindings.
   - Connect the catalog with the translated config and keep validation failure modes unchanged.

5. Migrate `floe_iceberg.writer`.
   - Make explicit runtime connection input required for production call sites or default to `{}` only when no connection is needed.
   - Remove reflective helper probing from `_catalog_config()`.
   - Update writer tests so they verify explicit config behavior instead of storage-plugin helper discovery.

6. Remove or quarantine `StoragePlugin.get_pyiceberg_catalog_config()` after no production consumer remains.
   - If compatibility is needed for third-party plugins, mark it deprecated and keep it out of first-party runtime paths.
   - Remove first-party tests that assert runtime packages call it.
   - Keep storage-owned FileIO and warehouse APIs intact; only the cross-plugin catalog config helper is retired.

## Acceptance Evidence

The implementation should not be considered complete until these evidence points exist:

- Contract tests derive runtime catalog connection config from `StorageDeploymentBinding` and `CatalogDeploymentBinding`.
- Contract tests prove compiled artifacts remain secret-free when runtime catalog connection metadata is present.
- Dagster resource tests construct `IcebergTableManagerConfig.catalog_connection_config` from deployment bindings without calling `StoragePlugin.get_pyiceberg_catalog_config()`.
- Dagster export tests pass writer connection config from deployment bindings and keep plugin config validation separate from runtime connection translation.
- Dagster validation tests call `catalog_plugin.connect()` with deployment-derived runtime config and do not depend on storage-owned catalog config.
- Writer tests cover explicit connection config and do not use reflective helper probing as the success path.
- A search for first-party production code consumers of `get_pyiceberg_catalog_config()` returns no Dagster or `floe_iceberg.writer` runtime consumers.

## Non-Goals

- Do not change raw secret handling or add secret material to `CompiledArtifacts`.
- Do not make Dagster the owner of Iceberg connection semantics.
- Do not move Iceberg table write policy back into Dagster export code.
- Do not require storage plugins to know catalog plugin internals.
- Do not require catalog plugins to know storage plugin implementation classes.

## Open Design Questions

- Should the neutral runtime catalog connection projection be stored directly under `DeploymentConfig`, or computed by a helper from existing `deployment.storage` and `deployment.catalog` fields?
- Should the PyIceberg translation helper live in `floe-core`, `floe-iceberg`, or `floe-orchestrator-dagster`? The preferred default is `floe-iceberg` if the translation is PyIceberg-specific, with `floe-core` owning only the neutral schema.
- Should deprecated `StoragePlugin.get_pyiceberg_catalog_config()` remain in the ABC through one compatibility release, or be removed as soon as first-party consumers are gone?
