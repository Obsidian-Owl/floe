# dlt Ingestion Composition Uplift Design

## Context

The dlt ingestion E2E work was built before the storage and catalog composition
refactor landed on `main`. After syncing, the branch still passes focused tests,
but its runtime wiring now duplicates platform storage and catalog facts under
the ingestion-owned catalog fallback config.

That duplication conflicts with the new composability layer:

- Storage plugins emit a neutral `StorageDeploymentBinding`.
- Catalog plugins declare storage requirements and translate neutral storage
  state into catalog-owned deployment bindings.
- Renderers and runtimes consume resolved deployment bindings rather than
  rediscovering plugin config.
- `CompiledArtifacts` stays secret-free.

The ingestion uplift should bring dlt to the same model. Data engineers should
continue to declare source intent in `floe.yaml`; platform engineers should
configure storage, catalog, credentials, retry defaults, and plugin selection
once in `manifest.yaml`.

## Current Impact

The synced branch has three architectural debts:

1. `floe-core` validates dlt destination readiness by requiring
   ingestion-owned catalog fallback config with catalog URI, warehouse, and
   bucket settings. Those values now already exist in storage and catalog
   deployment bindings.
2. Dagster ingestion source construction derives filesystem access from
   ingestion-owned `catalog_config`, so source reads know too much about the
   destination catalog shape.
3. `floe-ingestion-dlt` builds the dlt filesystem destination and temporary
   PyIceberg environment directly from raw `catalog_config`, coupling dlt to
   Polaris/MinIO field names and forcing duplicate demo manifest config.

The result is functional but not simple: platform engineers must keep storage,
catalog, and ingestion destination settings synchronized manually. Data
engineers remain shielded from most wiring, but the platform surface has drifted
away from Floe's "choose once, compose everywhere" target.

## Official Source Alignment

The design was validated against current official dlt documentation:

- dlt filesystem source supports remote object stores and local files, and
  natively supports CSV, JSONL, and Parquet readers.
  Source: https://dlthub.com/docs/dlt-ecosystem/verified-sources/filesystem/basic
- dlt's filesystem destination supports S3-compatible storage such as MinIO via
  an endpoint URL plus credentials, and supports JSONL, Parquet, CSV, and
  Iceberg table format outputs.
  Source: https://dlthub.com/docs/dlt-ecosystem/destinations/filesystem
- dlt Iceberg writes use PyIceberg catalog configuration. For REST catalogs,
  dlt needs catalog URI/type/warehouse and may also need storage properties when
  credentials are not vended by the catalog.
  Source: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
- dlt resolves configuration from environment variables, config files, vaults,
  custom providers, and defaults, with environment variables taking priority.
  Source: https://dlthub.com/docs/general-usage/credentials/setup

These docs support the uplift rather than contradicting it. dlt still needs the
same runtime facts, but Floe should render those facts from its composed
platform binding instead of asking platform engineers to retype them under the
ingestion plugin.

## Goals

- Remove duplicated dlt destination catalog/storage config from the demo and
  target platform manifests.
- Make dlt consume secret-free runtime bindings derived from
  `CompiledArtifacts.deployment.storage` and
  `CompiledArtifacts.deployment.catalog`.
- Preserve the data engineer surface in `floe.yaml`: source name, source type,
  format, path or prefix, destination table, write mode, schema contract, and
  optional cursor/primary key.
- Keep dlt implementation details behind the `floe-ingestion-dlt` plugin.
- Keep catalog-specific translation owned by the catalog plugin, storage facts
  owned by the storage plugin, and dlt-specific environment/rendering owned by
  the dlt plugin.
- Extend E2E coverage for realistic object-store ingestion paths across CSV,
  JSONL, and Parquet, including common ingestion failures.

## Non-Goals

- Do not design Airbyte composition in this slice. The contract should not block
  Airbyte later, but the concrete translator is dlt-only.
- Do not move raw source declarations out of `floe.yaml`.
- Do not migrate Customer 360 dbt models to read the dlt-loaded raw Iceberg
  tables in this slice. The demo can stay CSV-backed for dbt while ingestion E2E
  proves raw table loading.
- Do not create buckets or mutate infrastructure during compilation.
- Do not inline raw secrets in `CompiledArtifacts`, Helm values, tests, or demo
  manifests.

## Recommended Approach

Adopt a full composition uplift for ingestion.

Floe should add an ingestion runtime binding that is derived during compile from
the selected storage, catalog, and ingestion plugins. The dlt plugin should
translate that binding into dlt filesystem source config, dlt filesystem
destination kwargs, and PyIceberg/dlt environment variables at runtime.

This is more work than a small adapter around the existing `catalog_config`, but
it matches the storage/catalog refactor and removes the source of drift. It also
gives platform engineers one place to reason about storage/catalog credentials,
bucket purposes, endpoints, and path-style behavior.

Rejected alternatives:

- Keep `catalog_config` and document it as duplication. This is quickest, but it
  preserves platform tech debt and makes every new storage or catalog plugin
  also update dlt-specific config examples.
- Copy storage/catalog fields into ingestion config during compile. This reduces
  manifest duplication but still makes ingestion config the runtime truth and
  encourages downstream code to couple to provider-specific fields.

## User Experience

For data engineers, the experience should remain:

```yaml
ingestion:
  sources:
    - name: raw_customers
      source_type: filesystem
      format: csv
      path: landing/customer_360/customers/*.csv
      destination_table: customer_360_raw.raw_customers
      write_mode: replace
      schema_contract: evolve
```

They should not choose a bucket, endpoint, catalog URI, warehouse, credential
source, PyIceberg property, dlt destination type, or Dagster resource key.

For platform engineers, the experience should become:

```yaml
plugins:
  catalog:
    type: polaris
    config:
      uri: http://floe-platform-polaris:8181/api/catalog
      warehouse: floe-demo
      oauth2:
        client_id: demo-admin
        client_secret_ref: polaris-demo-secret
        scope: PRINCIPAL_ROLE:ALL
  storage:
    type: minio
    config:
      endpoint: http://floe-platform-minio:9000
      bucket: floe-iceberg
      artifact_bucket: floe-artifacts
      region: us-east-1
      path_style_access: true
      credential_secret_name: floe-platform-minio-credentials
      credential_secret_namespace: floe-system
  ingestion:
    type: dlt
    version: 0.1.0
    config:
      retry_config:
        max_retries: 3
        initial_delay_seconds: 1.0
```

This makes the simplification explicit: the ingestion plugin selects behavior,
not infrastructure wiring.

## Composition Contract

Add a typed ingestion deployment/runtime binding under
`CompiledArtifacts.deployment`:

```python
class IngestionRuntimeBinding(BaseModel):
    source_filesystem: dict[str, Any]
    destination_filesystem: dict[str, Any]
    iceberg_catalog_env: dict[str, str]
    env_refs: dict[str, str]

class DltIngestionBinding(BaseModel):
    plugin_name: str
    destination: Literal["filesystem"]
    table_format: Literal["iceberg"]
    source_filesystem: dict[str, Any]
    destination_filesystem: dict[str, Any]
    iceberg_catalog_env: dict[str, str]
    env_refs: dict[str, str]

class IngestionDeploymentBinding(BaseModel):
    provider: Literal["dlt"]
    dlt: DltIngestionBinding
```

The concrete field names can be tightened during implementation, but the
boundary is fixed:

- `source_filesystem` is what the Dagster source-construction layer needs to
  enumerate landed files. It is derived from storage bucket requirements and
  source paths.
- `destination_filesystem` is what dlt's filesystem destination needs for
  Iceberg writes.
- `iceberg_catalog_env` is the secret-free catalog and PyIceberg environment
  fragment dlt needs at run time.
- `env_refs` maps logical dlt/PyIceberg secret keys to runtime environment
  variables or Kubernetes Secret references.

`CompiledArtifacts.deployment` should then become:

```python
class DeploymentConfig(BaseModel):
    storage: StorageDeploymentBinding | None = None
    catalog: CatalogDeploymentBinding | None = None
    ingestion: IngestionDeploymentBinding | None = None
```

All ingestion deployment fragments need the same secret-free validation used by
storage runtime bindings. Credential material must appear as references only.

## Composition Requirements

The composition resolver should be extended beyond storage-to-catalog checks so
ingestion plugins can declare what they need from the selected platform:

```python
class DltCompositionRequirements(BaseModel):
    storage_protocols: list[str] = ["s3-compatible", "s3"]
    storage_credential_modes: list[str] = [
        "kubernetes-secret",
        "environment",
        "workload-identity",
    ]
    catalog_kinds: list[str] = ["iceberg-rest"]
    table_formats: list[str] = ["iceberg"]
```

The exact implementation can reuse `PluginRequirements` or add a typed
ingestion-specific requirement model. The behavior is the important part:

- dlt should reject a deployment with no storage binding when filesystem source
  or destination paths need object storage.
- dlt should reject a deployment with no catalog binding when product ingestion
  writes to Iceberg.
- dlt should accept MinIO plus Polaris because MinIO provides S3-compatible
  storage and Polaris provides a REST Iceberg catalog.
- future ingestion plugins should add requirements without changing MinIO,
  Polaris, or Dagster internals.

## Ownership Rules

- Storage owns bucket URIs, endpoint URLs, region, path-style behavior, storage
  capabilities, and credential refs.
- Catalog owns REST catalog URI, warehouse, OAuth/scope shape, catalog-specific
  storage projection, and catalog compatibility requirements.
- Ingestion owns dlt-specific translation into source config, destination kwargs,
  table format, loader behavior, and temporary environment setup.
- Dagster owns scheduling and asset construction, but consumes the compiled dlt
  binding rather than reconstructing storage or catalog config.
- Helm and run launchers own projection into Kubernetes env vars and Secret refs;
  they do not decide which bucket or catalog to use.

## Compile-Time Flow

1. Resolve plugins from `manifest.yaml`.
2. Build storage deployment binding.
3. Validate storage/catalog composition and build catalog deployment binding.
4. If product ingestion exists, validate that the selected ingestion plugin can
   consume the selected storage/catalog composition.
5. Ask the ingestion plugin to build its secret-free deployment binding from
   storage, catalog, and ingestion plugin config.
6. Store the result in `CompiledArtifacts.deployment.ingestion`.
7. Store product source declarations in
   `CompiledArtifacts.plugins.ingestion.config.sources` without destination
   infrastructure details.

If ingestion is selected without compatible storage or catalog, compilation
should fail with an ownership-directed error. For example: "dlt Iceberg
ingestion requires a storage binding with an S3-compatible warehouse bucket and
a catalog binding that exposes a REST Iceberg catalog."

## Runtime Flow

The Dagster runtime should load compiled artifacts and pass both:

- source declarations from `plugins.ingestion.config.sources`
- dlt runtime binding from `deployment.ingestion.dlt`

Source construction should combine the data engineer's source path with the
platform landing or warehouse bucket selected by the binding. For object-store
E2E, prefer a first-class `landing` bucket requirement when available. Until the
storage plugin emits landing buckets, MinIO's warehouse bucket can serve as the
alpha default with an explicit `landing/` prefix.

`DltIngestionPlugin.create_pipeline()` should receive the dlt binding rather
than raw `catalog_config`. It should create a dlt pipeline with filesystem
destination kwargs and retain only the resolved, secret-free environment
fragment needed by `run()`.

`DltIngestionPlugin.run()` should apply the dlt/PyIceberg environment inside the
existing temporary environment context, resolving secret values only from
runtime env refs. It should not read raw secret values from compiled artifacts.

## Realistic User Ingestion Cases

The E2E matrix should model what users are likely to see in landed-file
pipelines:

- CSV with headers, quoted delimiters, nullable fields, and type drift.
- JSONL with nested fields, malformed line handling, and empty-file behavior.
- Parquet with typed columns and schema mismatch.
- Missing object prefix or no matching files.
- Duplicate rerun with `replace` to prove idempotent raw table behavior.
- Credential, endpoint, and catalog reachability failures routed as platform
  configuration failures.
- Bad namespace or missing write grant routed as destination failures.

Customer 360 can stay the readable demo and use CSV. The broader CSV, JSONL,
and Parquet matrix belongs in platform E2E because its job is to prove ingestion
capability, not demo storytelling.

## Test Strategy

Unit tests:

- `floe-core` rejects ingestion workloads when dlt has no compatible
  storage/catalog binding.
- `floe-core` no longer requires ingestion-owned catalog fallback config when
  storage and catalog composition are present.
- `CompiledArtifacts.deployment.ingestion` rejects raw credential-looking
  fields.
- dlt plugin renders expected source filesystem config, destination filesystem
  kwargs, and PyIceberg/dlt environment from typed bindings.
- Dagster ingestion assets consume the compiled ingestion binding instead of
  `catalog_config`.

Contract tests:

- Core-to-ingestion contract includes source declarations plus
  `deployment.ingestion`.
- Storage/catalog/ingestion composition compatibility errors include actionable
  plugin refs.
- Demo compiled artifacts contain no duplicated ingestion `catalog_config`.

E2E tests:

- Customer 360 demo path remains CSV and proves the simple product workflow.
- Platform ingestion matrix covers CSV, JSONL, and Parquet from MinIO/S3
  landing prefixes into Polaris-backed Iceberg tables.
- Edge cases assert clean data-product vs platform-failure ownership.
- Live E2E reports infrastructure unavailability separately from product
  regressions.

## Migration

1. Add the new binding models as additive fields. Existing compiled artifacts
   remain readable.
2. Build the dlt binding when storage, catalog, and dlt are selected.
3. Teach Dagster and `floe-ingestion-dlt` to prefer
   `deployment.ingestion.dlt`.
4. Keep `catalog_config` as a temporary compatibility fallback with a warning.
5. Update demo manifest to remove the ingestion-owned catalog fallback config.
6. Remove the fallback and its tests after the demo/E2E path is proven from
   deployment bindings.

The implementation plan should include the fallback removal in the same work
unit sequence, not leave it as untracked debt.

## Open Design Decisions

- Whether to model a `landing` bucket in the MinIO storage plugin immediately or
  default to `warehouse/landing/` for alpha. Recommendation: add the bucket
  purpose now if the implementation is small; otherwise make the alpha fallback
  explicit and test it.
- Whether catalog OAuth refs need a first-class `CatalogCredentialBinding`
  before dlt consumes catalog auth. Recommendation: use existing secret-free
  catalog deployment fields if sufficient, but do not pass raw OAuth secrets
  through ingestion config.
- Whether dlt binding dict fragments should be fully typed before implementation
  or start as secret-validated maps. Recommendation: type the stable concepts
  now and keep only genuinely dlt-specific passthroughs as validated maps.

## Success Criteria

- Platform engineers configure storage and catalog once.
- Data engineers do not see dlt destination, PyIceberg, MinIO, or Polaris
  wiring in `floe.yaml`.
- Demo `manifest.yaml` no longer duplicates catalog/storage settings under
  ingestion.
- Focused unit and contract tests pass.
- CSV, JSONL, and Parquet E2E paths prove real dlt, real MinIO/S3-compatible
  storage, and real Polaris-backed Iceberg writes when local infrastructure is
  available.
- Any environment-gated E2E failure is reported as infrastructure-gated, not as
  product validation.
