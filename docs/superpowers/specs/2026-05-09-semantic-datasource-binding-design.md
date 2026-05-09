# Semantic Datasource Binding Design

Date: 2026-05-09
Status: Draft for review

## Goal

Replace static Cube datasource Helm values with a typed datasource binding
derived from compute, catalog, and storage projections.

Semantic layer plugins should receive one resolved datasource deployment
binding. They should not rediscover compute, catalog, or storage plugin config,
and they should not depend on compute-plugin duck typing as the runtime
contract.

## Current Trigger

Cube uses static Helm override values while compute/catalog/storage projections
exist elsewhere.

The current code proves the trigger is real:

```bash
rg -n "class SemanticLayerPlugin|def get_datasource_config|def get_helm_values_override|CUBEJS_DB_TYPE|CUBEJS_DB_NAME|get_cube_datasource_config" \
  packages/floe-core/src/floe_core/plugins/semantic.py \
  plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py \
  plugins/floe-semantic-cube/tests/unit/test_plugin.py \
  plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
```

Evidence from that search:

- `SemanticLayerPlugin.get_datasource_config(compute_plugin)` takes a compute
  plugin instance instead of a resolved datasource binding.
- `CubeSemanticPlugin.get_datasource_config()` uses `getattr()` to discover a
  compute-specific `get_cube_datasource_config()` method and falls back to a
  generic config.
- `DuckDBComputePlugin.get_cube_datasource_config()` can emit Cube-compatible
  DuckDB config and optional Iceberg attachment SQL from a catalog config.
- `CubeSemanticPlugin.get_helm_values_override()` currently renders static
  Helm environment values: `CUBEJS_DB_TYPE=duckdb` and
  `CUBEJS_DB_NAME=<configured database>`.
- Cube unit tests currently assert the static Helm override shape, including
  `CUBEJS_DB_NAME`.

## Target Contract

Semantic layer plugins consume a datasource deployment binding and do not
rediscover compute, catalog, or storage plugin config.

The target public shape is:

- `floe-core` owns a secret-free semantic datasource binding under the compiled
  deployment contract.
- Composition derives the binding from selected compute, catalog, storage,
  secrets, and identity projections after resolver validation.
- Semantic plugins consume the binding for runtime/Helm rendering.
- Compute plugins may contribute compute-owned datasource fragments, but those
  fragments must be part of the typed binding, not discovered by calling
  compute-specific methods from the semantic plugin.
- Catalog/storage connection facts must arrive as deployment projections, such
  as Iceberg REST URI, warehouse, storage endpoint, region, path-style access,
  credential refs, and env refs.

The preferred model is an additive binding:

```python
class SemanticDatasourceBinding(BaseModel):
    provider: str
    engine: str
    database_name: str
    catalog_name: str | None = None
    warehouse: str | None = None
    catalog_uri: str | None = None
    storage_endpoint: str | None = None
    region: str | None = None
    path_style_access: bool | None = None
    init_sql: list[str] = Field(default_factory=list)
    env_refs: dict[str, str] = Field(default_factory=dict)
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
```

The exact class and field names can change during implementation. The key
contract is that semantic renderers receive a typed datasource deployment
binding, not a compute plugin instance or a plugin config bag.

## Composition Constraints

- Capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin contracts.
- Semantic plugins must not import concrete compute, catalog, or storage
  implementation modules.
- `CompiledArtifacts` must remain secret-free; datasource credentials are
  `CredentialRef` or env ref handles only.
- Helm renderers consume resolved deployment bindings.
- Cube remains the first implementation proof, but the binding must be usable
  by a future dbt Semantic Layer plugin.

## Level Target

Current level: Level 0. Cube is discoverable and functional, but datasource
deployment is still static Helm override plus duck-typed compute discovery.

Target level: Level 2. Semantic rendering consumes a typed datasource binding
derived by composition. Level 3 can follow after resolver tests prove semantic
datasource requirements across multiple compute/catalog/storage combinations.

## Compatibility Retirement

Legacy surface: `SemanticLayerPlugin.get_helm_values_override()` and
`CubeSemanticPlugin.get_helm_values_override()` currently expose Helm values as
plugin-owned static config.

Retirement rule:

- Keep the method only as a compatibility wrapper while Cube migrates.
- Add a new binding-aware render path first.
- Update Cube tests so Helm values are rendered from
  `SemanticDatasourceBinding`.
- Add compatibility tests that fail if Cube reintroduces static
  `CUBEJS_DB_TYPE` / `CUBEJS_DB_NAME` values without reading the binding.
- Remove or quarantine the old static override after all first-party renderers
  use the binding-aware path.

## Acceptance Evidence

- Schema tests cover semantic datasource binding.
- Cube tests prove Helm values are rendered from the binding.
- Compatibility tests prevent static plugin-config rediscovery.
- Search evidence shows semantic layer code no longer uses `getattr()` on a
  compute plugin as the primary datasource contract.
- Secret-free compiled artifact tests cover datasource credential refs and env
  refs.

## Non-Goals

- Do not change Cube schema generation from dbt manifests.
- Do not make Cube responsible for storage or catalog plugin configuration.
- Do not remove the old Helm override before a binding-aware replacement is
  tested.
- Do not add raw database passwords, OAuth client secrets, tokens, or access
  keys to semantic deployment bindings.
