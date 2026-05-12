# AWS S3 and Glue Provider Design

Date: 2026-05-12
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `feat/aws-provider-design`
Status: Draft for review

## Purpose

Design native AWS S3 storage and AWS Glue catalog support against Floe's
implemented composition model before starting plugin implementation, live AWS
validation, AWS DevPod work, or `floe-bootstrap` IAM hardening.

The merged AWS account scaffold prepares a low-cost validation substrate. It
does not implement provider plugins. This design defines the missing provider
contracts and the worktree sequencing needed to implement them without
weakening composability.

## Current System Map

The current trunk already has the composition foundation needed for a native
provider slice:

- `CapabilitySet`, `RequirementSet`, `PluginCapabilities`, and
  `PluginRequirements` live in `floe-core`.
- `CompositionResolver` validates storage, catalog, ingestion, secrets, and
  identity compatibility from declared capabilities and requirements.
- `StorageDeploymentBinding` is the secret-free storage contract emitted by
  `floe-storage-minio`.
- `CatalogDeploymentBinding` is the secret-free catalog contract currently used
  by Polaris.
- `RuntimeCatalogConnection` is derived from deployment bindings and translated
  by `floe-iceberg` into PyIceberg connection config.
- `CompiledArtifacts` rejects raw credential material in runtime/catalog/storage
  fragments.
- Helm/renderers consume deployment bindings rather than rediscovering plugin
  config.

The missing pieces are explicit in the provider compatibility gap ledger:

- No `floe-storage-aws-s3` package or `floe.storage` entry point exists.
- No `floe-catalog-glue` package or `floe.catalogs` entry point exists.
- Glue catalog runtime projection is not proven from
  `RuntimeCatalogConnection`.
- AWS credential and identity modes need resolver proof.

## Design Options Considered

### Option A: Implement S3 and Glue as thin config shims

This would add provider packages that mostly translate manifest values directly
to PyIceberg config and live AWS calls.

Pros:

- Fastest first live test.
- Minimal core schema changes.

Cons:

- Runtime code would be tempted to rediscover plugin config.
- Glue-specific facts would not be visible in `CompiledArtifacts`.
- IAM and secret behavior would be harder to validate statically.

Decision: reject. It moves too much integration knowledge into runtime code.

### Option B: Add a broad provider abstraction layer

This would introduce a generalized cloud provider model for AWS, GCP, Azure,
IAM, endpoints, catalogs, and object storage.

Pros:

- Could support future clouds in one conceptual model.
- Might reduce future schema churn.

Cons:

- Overgeneralizes before GCS and Azure have concrete product paths.
- Risks a leaky abstraction that hides real provider differences.
- Delays the first AWS proof.

Decision: reject for this slice. Use GCS and Azure as pressure tests, not scope.

### Option C: Provider-owned bindings on top of current neutral contracts

AWS S3 emits the existing neutral `StorageDeploymentBinding` with native `s3`
protocol and AWS credential/identity modes. Glue declares storage requirements
and emits a provider-owned catalog binding plus runtime properties sufficient
for PyIceberg Glue.

Pros:

- Preserves the current composition model.
- Keeps provider-specific Glue details in the Glue plugin.
- Keeps `CompiledArtifacts` secret-free while making runtime facts explicit.
- Lets the resolver reject MinIO plus Glue and accept AWS S3 plus Glue.
- Gives IAM hardening a concrete action inventory after plugin design.

Cons:

- Requires a small core contract extension for Glue catalog binding.
- Requires careful runtime translator tests to avoid accidental REST-only bias.

Decision: use Option C.

## Architecture

The target flow is:

```text
manifest plugin selections
  -> AWS S3 plugin config validation
  -> S3 StorageDeploymentBinding
  -> Glue storage requirements
  -> CompositionResolver validation
  -> Glue CatalogDeploymentBinding
  -> RuntimeCatalogConnection
  -> PyIceberg Glue catalog config
  -> live S3 + Glue validation
```

No plugin may inspect another plugin's concrete class or config model. The Glue
plugin receives only `StorageDeploymentBinding` and its own config. The S3
plugin does not know Glue exists.

## AWS S3 Storage Plugin

Package:

- `plugins/floe-storage-aws-s3`
- Module: `floe_storage_aws_s3`
- Entry point: `aws-s3 = "floe_storage_aws_s3.plugin:AwsS3StoragePlugin"`
- Plugin type: `floe.storage`

Configuration model:

- `bucket`: existing warehouse bucket name.
- `warehouse_prefix`: warehouse prefix, default `warehouse/`.
- `artifact_bucket`: optional artifact bucket. Defaults to `bucket`.
- `artifact_prefix`: default `artifacts/`.
- `region`: AWS region.
- `endpoint_override`: optional. Only for localstack or non-standard S3
  endpoints; unset for real AWS.
- `path_style_access`: default `false`.
- `credential_mode`: one of `environment`, `workload-identity`, or
  `kubernetes-secret`.
- `credential_secret_name`, `credential_secret_namespace`,
  `access_key_secret_key`, `secret_key_secret_key`, and
  `session_token_secret_key`: required only for `kubernetes-secret`.
- `service_account_ref`: required only for `workload-identity`.
- `create_policy`: default `must-exist`.
- `sts_supported`: default `true`.

Deployment binding:

- `provider = "aws-s3"`.
- `protocol = "s3"`.
- `endpoint.region = region`.
- `endpoint.warehouse_path = s3://<bucket>/<warehouse_prefix>`.
- `endpoint.internal_url` and `endpoint.external_url` use the AWS regional S3
  endpoint when `endpoint_override` is unset, and the override when set.
- `warehouse.uri = s3://<bucket>/<warehouse_prefix>`.
- `allowed_locations` includes the warehouse URI and optional artifact URI.
- `buckets` declares warehouse and artifact requirements with `must-exist` by
  default. Compile does not create buckets.
- `capabilities.protocols = ["s3"]`.
- `capabilities.credential_modes` mirrors the configured supported mode and may
  include `environment` and `workload-identity` in tests where both are valid.
- `capabilities.identity_modes` includes `aws-irsa` and `aws-pod-identity` when
  workload identity is configured.
- `capabilities.sts_supported = true`.
- `capabilities.path_style_access = false` for native AWS by default.
- `provisioning.enabled = false`, `mode = "external"`,
  `default_create_policy = "must-exist"`.
- `runtime.pyiceberg_properties` carries non-secret S3 properties only:
  `s3.region`, optional `s3.endpoint`, and optional
  `s3.path-style-access`.
- `runtime.env_refs` carries AWS credential variable names for environment
  mode only. It never carries values.

The plugin should retain legacy abstract methods such as
`get_dbt_profile_config()` and `get_dagster_io_manager_config()` for interface
compliance, but new consumers must use `get_deployment_binding()`.

## AWS Glue Catalog Plugin

Package:

- `plugins/floe-catalog-glue`
- Module: `floe_catalog_glue`
- Entry point: `glue = "floe_catalog_glue.plugin:GlueCatalogPlugin"`
- Plugin type: `floe.catalogs`

Configuration model:

- `region`: AWS region.
- `catalog_id`: optional AWS account/catalog ID.
- `warehouse`: optional warehouse URI override. Defaults to the composed
  storage warehouse URI.
- `database_prefix`: optional prefix for Floe-created test namespaces.
- `endpoint_override`: optional Glue endpoint for tests or local emulation.
- `credential_mode`: one of `environment`, `workload-identity`, or
  `kubernetes-secret`.
- `skip_archive`: default `true`, matching PyIceberg Glue behavior unless a
  future requirement proves otherwise.
- `max_retries` and `retry_mode`: optional PyIceberg Glue client settings.

Storage requirements:

- `protocols = ["s3"]`.
- `credential_modes` includes the configured AWS credential mode.
- `identity_modes` includes `aws-irsa` and `aws-pod-identity` when configured
  for workload identity.
- `requires_server_side_storage_access = true`.
- `supports_path_style_access = false` for real AWS S3.
- `supports_no_sts = false` unless a specific non-STS path is proven.

Catalog capabilities for peer consumers:

- `catalog_providers = ["glue"]`.
- `table_formats = ["iceberg"]`.

Deployment binding:

Add a provider-owned Glue binding to `CompiledArtifacts`:

```python
class GlueCatalogDeploymentBinding(BaseModel):
    catalog_name: NonEmptyString = "glue"
    region: NonEmptyString
    warehouse: NonEmptyString
    catalog_id: NonEmptyString | None = None
    database_prefix: NonEmptyString | None = None
    endpoint: NonEmptyString | None = None
    skip_archive: bool = True
    max_retries: int | None = None
    retry_mode: NonEmptyString | None = None
    credential_refs: dict[str, CredentialRef] = Field(default_factory=dict)
    properties: dict[str, str] = Field(default_factory=dict)
```

Extend `CatalogDeploymentBinding` with:

```python
glue: GlueCatalogDeploymentBinding | None = None
```

Provider validation requires `provider == "glue"` to include `glue` details.
Existing Polaris validation remains unchanged.

Runtime projection:

`build_runtime_catalog_connection()` must recognize `catalog.glue` and produce
a `RuntimeCatalogConnection` that contains enough information for PyIceberg
Glue without reading the original manifest or plugin config. Required
properties:

- `type = "glue"`.
- `warehouse = <s3 warehouse uri>`.
- `glue.region = <region>`.
- `glue.id = <catalog_id>` when set.
- `glue.endpoint = <endpoint_override>` when set.
- `glue.skip-archive = "true"` or `"false"`.
- `glue.max-retries` and `glue.retry-mode` when set.
- client credential property names only when using environment references.

The runtime translator in `floe-iceberg` must preserve those properties and
must not assume all catalogs are Iceberg REST catalogs. The live implementation
must verify the exact PyIceberg property names against the installed
`pyiceberg.catalog.glue` constants before coding.

## Core Contract Changes

The first implementation branch should own shared contracts only:

- Add `GlueCatalogDeploymentBinding`.
- Extend `CatalogDeploymentBinding` validation.
- Add schema and serialization tests proving Glue bindings are secret-free.
- Add runtime connection tests for Glue.
- Add resolver tests:
  - AWS S3 plus Glue succeeds.
  - MinIO plus Glue fails on protocol.
  - AWS S3 plus Glue fails when credential modes do not overlap.
  - Workload identity mode requires a compatible identity provider when no
    non-identity credential mode overlaps.
  - dlt or other ingestion consumers see Glue as an Iceberg-capable catalog
    only if they require the right catalog provider. If existing ingestion
    requires `iceberg-rest`, the AWS Glue path should fail until ingestion
    explicitly supports `glue`.

Do not widen `CompiledArtifacts` with raw provider config dumps. Add only the
typed Glue binding and runtime properties needed by consumers.

## Live AWS Validation

Live validation happens after plugin contracts and package tests pass. It uses
the existing `infra/aws-provider-tests` scaffold but does not let that scaffold
define product contracts.

Required live proof:

- Compile a manifest selecting `aws-s3` and `glue`.
- Confirm `CompiledArtifacts` has no raw credential values.
- Confirm resolver accepts the AWS S3 plus Glue combination.
- Confirm PyIceberg can connect to Glue using config derived from
  `RuntimeCatalogConnection`.
- Create/list/drop a Glue namespace under the test prefix.
- Write/read/delete at least one Iceberg table or metadata object under the
  test S3 run prefix if PyIceberg support is complete in the slice.
- Run readiness before the live test and cleanup after the live test.
- Record S3 object inventory and Glue database inventory after cleanup.

The first live run should use environment credentials from the local
`floe-aws-bootstrap` profile only as a sandbox proof. Kubernetes IRSA or AWS
Pod Identity should be validated in a later AWS DevPod target once plugin
contracts are stable.

## Bootstrap IAM Sequencing

Do not narrow `floe-bootstrap` before the plugin contract exists. Narrowing it
too early would hard-code assumptions from infrastructure scaffolding instead
of actual plugin/runtime behavior.

After S3 and Glue plugins define and validate their required AWS actions, issue
#331 should scope `floe-bootstrap` to:

- OpenTofu management of the provider-test scaffold.
- S3 bucket and object operations under the test bucket/prefix.
- Glue database and table operations under the `floe_provider_*` namespace.
- Budget read/write operations for the sandbox budget.
- IAM policy management only for the provider-test policy.

Runtime tests should eventually use a separate test principal or role, not the
bootstrap identity.

## Worktree Execution Plan

Use `main` as trunk only. Branches should land in this order:

1. `feat/aws-provider-design`
   - Owns this design document.
   - No production code.

2. `feat/aws-provider-core-contracts`
   - Owns `floe-core` and `floe-iceberg` contract/runtime projection changes.
   - Adds resolver, schema, and runtime translator tests.
   - Merges before plugin implementation branches.

3. `feat/storage-aws-s3`
   - Owns `plugins/floe-storage-aws-s3`.
   - Adds package unit tests and plugin entry point.
   - Does not edit root workspace metadata until integration.

4. `feat/catalog-glue`
   - Owns `plugins/floe-catalog-glue`.
   - Adds package unit tests and plugin entry point.
   - Does not edit root workspace metadata until integration.

5. `feat/aws-provider-live-validation`
   - Registers both plugins in workspace metadata.
   - Adds cross-package contract tests and live AWS validation docs.
   - Uses `infra/aws-provider-tests` readiness and cleanup scripts.

6. `feat/aws-bootstrap-scope`
   - Owns #331 IAM hardening.
   - Uses evidence from the plugin and live validation branches to narrow
     `floe-bootstrap`.

Run at most two plugin implementation sessions in parallel after core
contracts merge: one for S3 and one for Glue. Keep core contracts, integration,
live validation, and IAM hardening sequential.

## Testing Strategy

Static and unit evidence:

- Plugin config validation tests for all credential modes.
- Entry point discovery tests for both packages.
- Resolver tests for valid and invalid AWS S3 plus Glue combinations.
- `CompiledArtifacts` schema tests for Glue binding serialization and
  secret-free validation.
- Runtime translator tests for PyIceberg Glue config.
- Package tests proving `get_deployment_binding()` emits only refs and
  non-secret properties.

Contract evidence:

- Core-to-storage contract for `aws-s3`.
- Core-to-catalog contract for `glue`.
- Cross-plugin compilation test for `aws-s3` plus `glue`.
- Negative compilation test for `minio` plus `glue`.

Live evidence:

- AWS readiness script passes before validation.
- PyIceberg/Glue namespace or table lifecycle succeeds against live AWS.
- Cleanup script passes after validation.
- S3 and Glue inventories are empty for the run prefix after cleanup.

CI and local validation:

- `make test-unit` or targeted package/unit equivalents.
- `uv run pytest packages/floe-core/tests/unit/composition -q`.
- `uv run pytest packages/floe-core/tests/unit/schemas -q` focused to changed
  schema tests.
- `uv run pytest packages/floe-iceberg/tests/unit/test_runtime_catalog.py -q`.
- Package unit tests for each new plugin.
- Docs validation for design and validation artifacts.

## Out Of Scope

- AWS DevPod or EKS deployment target.
- Full Kubernetes IRSA validation.
- GCS, Azure, Nessie, or Hive implementation.
- Glue crawlers, Glue jobs, Lake Formation, and S3 Tables.
- Destroying or recreating the AWS provider-test scaffold.
- Compatibility aliases for the removed legacy `s3` storage plugin identity.
- Any path that places AWS access keys, secret keys, session tokens, OAuth
  tokens, or credential values in `CompiledArtifacts`.

## Approval Gate

Implementation should not start until this design is reviewed and approved.
After approval, create a dedicated plan for the core contract branch before
opening the S3 and Glue plugin worktrees.
