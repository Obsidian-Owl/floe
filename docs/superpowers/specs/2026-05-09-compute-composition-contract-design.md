# Compute Composition Contract Design

Date: 2026-05-09
Status: Draft for review

## Goal

Define resolver-backed deployment-aware compute profile and catalog attachment
behavior.

The contract should make compute uplift explicit instead of relying on the
current DuckDB-specific success path. Compute plugins should declare the
storage and catalog projections they require, and the compiler should validate
those requirements before dbt profile generation.

## Current Trigger

DuckDB profile augmentation already consumes deployment configuration, but
there is no explicit compute composition contract.

The current code proves the trigger is real:

```bash
rg -n "class ComputePlugin|def augment_dbt_profile|DeploymentConfig|IcebergRestCatalogBinding|get_cube_datasource_config" \
  packages/floe-core/src/floe_core/plugins/compute.py \
  packages/floe-core/src/floe_core/compilation/dbt_profiles.py \
  plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py \
  packages/floe-core/tests/unit/compilation/test_dbt_profiles.py \
  plugins/floe-compute-duckdb/tests/unit/test_plugin.py
```

Evidence from that search:

- `ComputePlugin.augment_dbt_profile(profile, deployment)` already documents
  that storage and catalog plugins expose neutral `DeploymentConfig`
  projections that compute plugins may translate into adapter profile fragments.
- `generate_dbt_profiles()` applies storage and catalog dbt profile fragments,
  then calls `plugin.augment_dbt_profile(profile_output, deployment)`.
- `DuckDBComputePlugin.augment_dbt_profile()` reads
  `deployment.catalog.dbt.iceberg_rest` or `deployment.catalog.iceberg_rest`
  and emits DuckDB `extensions`, `secrets`, and `attach` entries.
- DuckDB tests prove neutral catalog binding support, OAuth2 env-ref secret
  handling, generic Iceberg REST binding support, idempotent attachment, and
  rejection of malformed existing `attach` values.
- dbt profile tests prove core delegates the full `DeploymentConfig` to compute
  and keeps generated credentials as env var placeholders.

## Target Contract

Compute plugins declare requirements for catalog/storage profile attachment and
consume typed deployment bindings without reading another plugin's concrete
config.

The target public shape is:

- `floe-core` owns compute composition requirement models and resolver
  validation.
- Compute plugins may declare profile requirements such as `table_formats`,
  `catalog_providers`, `protocols`, `credential_modes`, `identity_modes`,
  path-style-access support, and whether catalog attachment is required for dbt
  profile generation.
- Storage and catalog plugins continue to emit typed deployment bindings,
  including storage dbt fragments and catalog Iceberg REST bindings.
- dbt profile generation passes only the resolved deployment binding set to the
  compute plugin. It must not pass storage or catalog plugin config bags as the
  cross-plugin contract.
- Compute plugins own adapter-specific profile rendering, such as DuckDB
  `attach` entries and DuckDB secret blocks.
- The resolver fails before `CompiledArtifacts` are produced if selected
  storage/catalog plugins cannot satisfy the compute plugin's declared profile
  requirements.

The preferred implementation model is additive:

```python
class ComputeProfileRequirement(BaseModel):
    table_formats: list[str] = Field(default_factory=list)
    catalog_providers: list[str] = Field(default_factory=list)
    protocols: list[str] = Field(default_factory=list)
    credential_modes: list[str] = Field(default_factory=list)
    identity_modes: list[str] = Field(default_factory=list)
    requires_catalog_attachment: bool = False
    requires_storage_profile_fragment: bool = False
    supports_path_style_access: bool | None = None
```

The exact class name can change during implementation, but the ownership must
not: requirement declaration is a resolver input, while adapter-specific dbt
profile materialization remains compute-owned.

## Composition Constraints

- Capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin contracts.
- Compute plugins must not import or inspect concrete storage or catalog plugin
  implementations.
- `CompiledArtifacts` must remain secret-free.
- dbt profile renderers consume resolved deployment bindings and env refs, not
  raw secrets or concrete plugin config.
- DuckDB can remain the first implementation proof, but the contract must be
  usable by future Spark, Snowflake, Databricks, BigQuery, or other compute
  plugins.

## Level Target

Current level: Level 2. DuckDB already consumes typed deployment bindings, but
resolver validation does not yet make compute profile requirements explicit.

Target level: Level 3. Resolver-backed requirements prove the selected compute,
catalog, storage, secrets, and identity projections are compatible before dbt
profiles are rendered.

## Compatibility Retirement

No public compute API must be removed immediately. The compatibility risk is
implicit behavior: `augment_dbt_profile()` currently doubles as both extension
point and undeclared requirement surface.

Retirement rule:

- Keep `augment_dbt_profile()` as the adapter rendering hook.
- Move compatibility assumptions out of the hook and into explicit compute
  requirements.
- Add guard tests that fail if profile generation starts reading
  `artifacts.plugins.storage.config`, `artifacts.plugins.catalog.config`, or a
  concrete plugin config object for cross-plugin attachment behavior.

## Acceptance Evidence

- Resolver tests cover compute requirements.
- dbt profile tests prove deployment-aware profile generation.
- Secret-free binding tests remain green.
- DuckDB tests prove catalog attachment uses typed Iceberg REST deployment
  bindings and env refs.
- Compatibility tests prove compute plugins do not rediscover storage/catalog
  plugin concrete config.

## Non-Goals

- Do not execute SQL in Python to validate dbt profile attachments.
- Do not make storage or catalog plugins render dbt adapter-specific profile
  syntax.
- Do not add raw credential material to `CompiledArtifacts` or dbt profiles.
- Do not make this task implement semantic datasource binding, RBAC policy
  generation, or network policy generation.
