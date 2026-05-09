# dlt Ingestion API Cleanup and Stabilization Design

## Context

The dlt ingestion branch has moved toward Floe's composability model: storage
and catalog plugins emit typed deployment bindings, and dlt receives the
runtime facts it needs through `CompiledArtifacts.deployment.ingestion.dlt`.

One compatibility path remains too visible to leave behind:
`IngestionPlugin.get_destination_config(catalog_config)`. It appears in the
public ingestion ABC, contract tests, golden interface regression, architecture
docs, and dlt tests. Runtime code no longer needs this method when the compiled
runtime binding is present. Keeping it would preserve the old idea that
ingestion owns catalog and storage wiring.

The goal of this cleanup is to make the architecture honest: dlt should be a
consumer of composed storage/catalog bindings, not a second place to configure
catalog destination settings.

## Official dlt Alignment

The design was validated against current official dlt documentation:

- dlt filesystem source supports local and remote filesystems and natively
  supports CSV, JSONL, and Parquet readers.
  Source: https://dlthub.com/docs/dlt-ecosystem/verified-sources/filesystem/basic
- dlt Iceberg writes are implemented through the filesystem destination plus
  PyIceberg catalog configuration.
  Source: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
- dlt can resolve configuration and secrets from environment variables, with
  environment variables taking priority over lower-priority providers.
  Source: https://dlthub.com/docs/general-usage/credentials/setup
- dlt schema contracts distinguish `tables`, `columns`, and `data_type`, so
  Floe can allow initial table creation while freezing later column/type drift.
  Source: https://dlthub.com/docs/general-usage/schema-contracts
- DuckDB's Iceberg extension supports attaching Iceberg REST catalogs and then
  using normal SQL operations such as `SELECT` against catalog tables.
  Source: https://duckdb.org/docs/stable/core_extensions/iceberg/iceberg_rest_catalogs

These docs support a binding-driven runtime contract. Floe still has to provide
dlt with filesystem destination kwargs and PyIceberg catalog environment, but
those facts should be projected from platform-owned bindings rather than
accepted as ingestion-owned `catalog_config`.

## Goals

- Remove `IngestionPlugin.get_destination_config(catalog_config)` from the
  ingestion plugin public contract.
- Keep `CompiledArtifacts.deployment.ingestion.dlt` as the only dlt
  destination/runtime contract.
- Delete dlt plugin helpers and tests whose only purpose is catalog-shaped
  destination config translation.
- Rewrite integration and E2E fixtures so they build or consume
  compiled-style runtime bindings instead of ad hoc `catalog_config`.
- Update architecture docs, ADR/interface snippets, and golden interface tests
  so the documented API matches the implemented composability model.
- Strengthen E2E coverage around realistic file ingestion formats and failure
  modes without making the demo migrate away from CSV.
- Validate that Floe's generated dbt/DuckDB runtime can discover and query the
  Iceberg raw tables written by dlt without data engineers writing custom
  DuckDB attach SQL or dlt-specific Python code.
- Promote dlt-created raw tables into the same platform state model used by
  dbt outputs: data contracts, catalog validation, observability, lineage,
  freshness, quality, and demo evidence should be able to reason about them.

## Non-Goals

- Do not redesign Airbyte in this slice. The generic ingestion contract should
  not block Airbyte later, but this cleanup only hardens dlt.
- Do not remove or change `SinkConnector.get_source_config(catalog_config)`.
  Reverse ETL source configuration is a separate contract and should be handled
  in a dedicated follow-up if needed.
- Do not move product ingestion source declarations out of `floe.yaml`.
- Do not place raw credentials into compiled artifacts, tests, Helm values, or
  demo manifests.
- Do not make Polaris purge support a prerequisite for E2E cleanup.

## Recommended Approach

Perform full API cleanup now.

`IngestionPlugin` should expose:

- `is_external`
- `create_pipeline(config)`
- `run(pipeline, **kwargs)`
- `get_composition_requirements()`
- `build_deployment_binding(storage=..., catalog=...)`

It should not expose `get_destination_config(catalog_config)`. Destination
configuration is no longer a plugin API method because it encourages consumers
to pass raw catalog/storage dictionaries into ingestion plugins. The supported
path is:

```text
manifest.yaml storage/catalog/ingestion selections
  -> composition resolver
  -> CompiledArtifacts.deployment.storage
  -> CompiledArtifacts.deployment.catalog
  -> CompiledArtifacts.deployment.ingestion.dlt
  -> Dagster runtime binding
  -> DltIngestionPlugin.create_pipeline/run
```

This is intentionally a breaking cleanup on the in-repo alpha plugin API. It
removes the ambiguity before external plugin authors depend on the stale
contract.

## Component Changes

### floe-core

- Remove `get_destination_config()` from `IngestionPlugin`.
- Update ingestion ABC docstrings to describe deployment binding generation
  instead of destination config generation.
- Update contract tests that assert the ingestion plugin method set.
- Regenerate or edit the golden plugin interface fixture so it no longer lists
  `get_destination_config` for `IngestionPlugin`.
- Keep `IngestionConfig.runtime_binding` as the runtime handoff point.
- Keep compile-time stripping/rejection tests for ingestion-owned
  `catalog_config` so old manifest snippets cannot silently reintroduce the
  stale path.

### floe-ingestion-dlt

- Remove `DltIngestionPlugin.get_destination_config()`.
- Remove catalog-shaped helper methods that exist only for that method, such as
  `_bucket_url()` when no remaining runtime path uses it.
- Keep `_destination_config_from_binding()` and
  `_temporary_runtime_binding_environment()` as the only dlt destination wiring
  path.
- Ensure `create_pipeline()` fails clearly when a configured pipeline lacks a
  runtime binding.
- Ensure `run()` fails clearly when the pipeline was not created with a runtime
  binding.
- Keep runtime binding normalization for mapping and Pydantic-model callers.
- Keep schema contract mapping that allows initial table creation while freezing
  column and data type changes for `schema_contract: freeze`.

### floe-orchestrator-dagster

- Continue passing `deployment.ingestion.dlt.model_dump(mode="python")` into
  ingestion assets.
- Continue building filesystem sources from `runtime_binding.source_filesystem`.
- Do not read `plugins.ingestion.config.catalog_config`.
- Preserve direct executable source support for unit tests where it remains a
  useful local helper, as long as configured dlt pipelines still require a
  runtime binding.

### dbt and DuckDB Pickup

The dlt cleanup is not complete unless transformed dbt models can consume the
Iceberg raw tables that dlt wrote. The proof point is not that dbt can read CSV
seeds; it is that Floe's generated dbt runtime can attach/query the same
Polaris + MinIO/S3 Iceberg catalog used by dlt.

Current Floe pieces already point in this direction:

- `floe-storage-minio` emits dbt profile fragments for S3 endpoint, region,
  path-style access, and runtime credential env refs.
- `floe-compute-duckdb` supports DuckDB profile generation and ships an
  Iceberg-compatible dbt table materialization.
- `DuckDBComputePlugin.get_catalog_attachment_sql()` knows how to build DuckDB
  Iceberg attach SQL from catalog configuration.

The stabilization should close the remaining validation gap:

- compiled `dbt_profiles` must contain enough DuckDB/Iceberg configuration to
  attach the Polaris REST catalog and reach MinIO/S3 through env refs;
- dbt source declarations should be able to reference dlt raw Iceberg tables as
  normal sources, for example `{{ source('bronze', 'raw_transactions') }}`;
- no data engineer should have to write custom `INSTALL iceberg`, `LOAD
  iceberg`, `ATTACH`, PyIceberg config, or dlt runtime code in a model.

If the current generated profile cannot do this, the implementation plan should
add the smallest compiler/plugin projection that makes it true. The ownership
boundary stays the same: storage and catalog provide the facts, compute/dbt
translate them into dbt/DuckDB runtime configuration, and data products consume
tables declaratively.

### Platform State Consumers

dlt raw tables should not be invisible side effects. Once Floe declares an
ingestion source and dlt writes its destination Iceberg table, that table is
platform state. Any Floe surface that answers "what data exists, is it healthy,
where did it come from, and can downstream systems rely on it?" needs a clear
path to see ingestion outputs.

The cleanup should introduce or validate a single compiled representation for
ingestion output tables. It does not need a large new abstraction, but it does
need a stable place where these facts can be derived:

- source name and source type
- logical destination table and physical Iceberg identifier
- file format and source path/prefix, sanitized for public metadata
- write mode and schema contract
- freshness or load timestamp field when available
- primary key and cursor field when configured
- quality tier or default raw/bronze tier when applicable

That state should feed the following consumers:

- **Data contracts**: ODCS contracts and schema drift checks should be able to
  reference raw ingestion tables, not only final dbt marts. Contract validation
  should compare expected columns/types against the actual Iceberg table schema
  when a raw table contract is declared.
- **Catalog validation**: `expected_iceberg_tables()` should be able to validate
  dlt raw tables as expected outputs, either by default for ingestion-focused
  validation or by explicit expected-table arguments.
- **dbt**: raw tables should be consumable as dbt sources through generated
  profile/catalog configuration.
- **Lineage**: ingestion assets should emit lineage or metadata that connects
  source path/source type to the raw Iceberg table, then dbt lineage should
  connect raw sources to downstream transform outputs.
- **Observability**: ingestion spans and run metadata should include stable
  source and destination identifiers, row counts, bytes written, duration,
  schema contract mode, and failure category without secrets or PII.
- **Quality and freshness**: raw-table checks should have a place to hang simple
  expectations such as non-empty loads, expected minimum rows, freshness based
  on `_loaded_at` or configured cursor fields, and schema drift.
- **Demo evidence**: Customer 360 validation should be able to prove both raw
  ingestion tables and final mart tables, while the main demo can remain
  CSV-backed until we intentionally migrate the transform models.

This is the key simplification: platform state should be generated from
`floe.yaml` source declarations and composed platform bindings. Data engineers
should not duplicate raw table metadata across bespoke observability, lineage,
quality, and dbt configuration files.

### Tests and Fixtures

- Rewrite dlt integration and format-matrix E2E helpers to use a binding-shaped
  fixture. If tests need host-reachable endpoints, rewrite the compiled binding
  to host endpoints in one explicit helper rather than introducing
  `catalog_config`.
- Remove unit tests that only validate `get_destination_config()`.
- Replace any retained behavior with runtime-binding tests:
  - destination filesystem kwargs come from `destination_filesystem`
  - source filesystem kwargs come from `source_filesystem`
  - PyIceberg and dlt env values come from `iceberg_catalog_env` and `env_refs`
  - raw secrets are rejected from compiled binding fragments
- Keep tests proving old ingestion `catalog_config` is not emitted into
  compiled artifacts.
- Update E2E failure assertions for realistic ingestion behavior:
  - missing object path returns a failed ingestion result
  - malformed CSV and malformed JSONL fail with useful source context
  - unsupported file format fails before runtime execution
  - path traversal or absolute local paths are rejected
  - schema freeze rejects added columns or type drift on the second load
  - CSV, JSONL, and Parquet happy paths all use the same runtime-binding path
- Add a dbt pickup validation that proves a dlt-written Iceberg table can be
  queried through Floe's generated dbt/DuckDB runtime configuration. A narrow
  smoke model or query is enough; the Customer 360 demo may stay CSV-backed for
  its main walkthrough.
- Add a contract test for compiled demo artifacts showing dbt profile output
  contains the storage/catalog projection needed for DuckDB Iceberg access,
  while keeping credentials as env refs.
- Add contract/schema tests proving compiled ingestion outputs are available to
  platform state consumers without duplicating `catalog_config`.
- Add catalog validation coverage for raw ingestion destination tables.
- Add observability/trace assertions for dlt runs that use fresh run
  attribution and include destination table, schema contract, row/byte counts,
  duration, and failure category.
- Add lineage validation that distinguishes source-to-raw ingestion lineage from
  raw-to-model dbt lineage, while proving both can share the same table
  identity.
- Add data contract or drift-validation coverage for at least one raw table
  contract, using the actual Iceberg table schema rather than only YAML shape.

### Docs

- Update `docs/architecture/interfaces/ingestion-plugin.md` and plugin-system
  interface snippets to remove `get_destination_config(catalog_config)`.
- Update ADR-0020 or add an amendment note explaining that ingestion
  destination wiring moved from catalog dictionaries to compiled deployment
  bindings.
- Update any older dlt ingestion plan/spec text that still describes
  `catalog_config` as an active path, or mark it as superseded by this cleanup.
- Keep docs focused on the user experience: platform engineers choose storage,
  catalog, and ingestion once in `manifest.yaml`; data engineers declare source
  intent in `floe.yaml`.
- Document the dbt pickup path: dlt writes raw Iceberg tables, Floe composes the
  dbt/DuckDB catalog access, and data engineers use dbt source/ref patterns
  rather than integration code.
- Document the platform state path for raw ingestion tables: data contracts,
  quality/freshness checks, lineage, observability, and validation evidence all
  derive from the same compiled ingestion output facts.

## User Experience Impact

For data engineers, there should be no new surface area. They continue to
declare:

```yaml
ingestion:
  sources:
    - name: raw_transactions
      source_type: filesystem
      format: csv
      path: landing/customer_360/transactions/*.csv
      destination_table: customer_360_raw.raw_transactions
      write_mode: replace
      schema_contract: evolve
```

For platform engineers, the improvement is removal of duplicate wiring. They
select storage, catalog, and dlt once in `manifest.yaml`; Floe composes the
runtime binding. There is no second ingestion `catalog_config` block to keep in
sync with Polaris and MinIO.

For plugin authors, the contract becomes clearer: ingestion plugins declare
requirements and build deployment bindings from typed peer-plugin bindings.
They do not expose raw catalog dictionary translators as part of the public
ingestion API.

For analytics engineers, the important simplification is that ingestion and
transformation meet at the Iceberg catalog boundary. Once dlt has loaded a raw
table, dbt should see it as a normal table/source through the generated Floe
profile and platform bindings.

For governance and operations users, the simplification is that raw tables are
not second-class data. The same platform evidence model should answer whether a
raw table exists, matches its contract, is fresh enough, has lineage, emitted
metrics, and can be consumed downstream.

## Risks and Mitigations

- Risk: Removing an ABC method is a breaking contract change.
  Mitigation: This is still alpha in-repo API cleanup, and keeping the method
  would preserve a known leaky abstraction.
- Risk: `SinkConnector` still mentions `catalog_config`, making searches look
  noisy.
  Mitigation: Treat reverse ETL as out of scope and document why it remains.
- Risk: E2E host-reachable endpoint rewrites could become another compatibility
  layer.
  Mitigation: Keep endpoint rewriting in test-only helpers that operate on the
  compiled binding shape.
- Risk: Polaris cleanup can fail when purge is disabled.
  Mitigation: E2E cleanup should delete test data through object-store cleanup
  and tolerate namespace/table cleanup limits without hiding product failures.

## Validation Plan

Local validation:

1. Reference search proving no active ingestion API/docs/tests still require
   `get_destination_config(catalog_config)`.
2. Focused ingestion ABC, compiled-artifacts, composition, dlt, and Dagster
   ingestion unit tests.
3. Ingestion contract tests and golden regression tests.
4. E2E test collection for Customer 360 and the dlt format matrix.
5. Full dlt plugin unit suite.
6. dbt pickup smoke: compile or run a minimal dbt model/query that reads a
   dlt-written Iceberg raw table through generated Floe profile/catalog
   configuration.
7. Platform state smoke: validate a raw dlt destination table through catalog
   validation, data-contract/schema validation where configured, observability
   attributes, and lineage/freshness evidence.
8. Ruff and mypy for touched packages.

Remote validation:

1. Run the real DevPod + Hetzner lane.
2. Report bootstrap, platform, developer, and destructive lanes separately.
3. Separate product failures from infra/service availability failures.
4. Verify direct Hetzner cleanup after the run: servers, volumes, load
   balancers, floating IPs, and SSH keys.

## Acceptance Criteria

- `IngestionPlugin` no longer declares `get_destination_config`.
- Golden plugin interface regression no longer lists
  `IngestionPlugin.get_destination_config`.
- `DltIngestionPlugin` has no `get_destination_config` method.
- No production/runtime dlt ingestion path reads
  `plugins.ingestion.config.catalog_config`.
- Demo compiled artifacts contain no ingestion `catalog_config`.
- dlt pipeline creation and execution require runtime binding.
- CSV, JSONL, and Parquet E2E paths exercise the same runtime-binding contract.
- A dbt pickup smoke proves DuckDB/dbt can query at least one dlt-written raw
  Iceberg table through generated Floe platform configuration.
- Data engineers do not need custom SQL attach statements, Python hooks, or
  dlt-specific model code to consume the raw Iceberg tables.
- Compiled artifacts expose ingestion output table state in a form that data
  contracts, catalog validation, dbt pickup, observability, lineage, quality,
  and freshness checks can consume.
- At least one raw dlt table is validated as platform state: table exists in the
  catalog, schema can be checked against a contract or declared shape, lineage
  connects source to raw table, and observability reports current-run ingestion
  metrics.
- Common ingestion failure paths produce explicit failed results or validation
  errors.
- Docs and ADR/interface snippets describe deployment bindings rather than raw
  catalog dictionary translators.
- Remote validation evidence and cleanup state are reported honestly.
