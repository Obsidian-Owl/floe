# Storage MinIO Architecture Design

Status: Approved for planning
Date: 2026-05-05
Author: Codex

## Summary

Floe should replace the current S3-compatible storage plugin naming and wiring
with a strict MinIO alpha implementation backed by a generic, deployer-neutral
storage deployment binding in `CompiledArtifacts`.

The binding is the canonical storage contract. It records secret-free desired
state for warehouse locations, bucket requirements, credential references,
consumer-specific projections, provisioning intent, and deployment renderings.
Helm values are a derived rendering for the current `floe-platform` chart, not
the semantic contract itself.

This preserves Floe's composability principles: storage remains a plugin
boundary, `CompiledArtifacts` remains the resolved source of truth, and Helm is
one deployment projection rather than the architecture.

## Problem

The current implementation splits storage truth across several surfaces:

- `demo/manifest.yaml` selects `plugins.storage.type: s3`, even though the
  configured endpoint is MinIO.
- `plugins/floe-storage-s3` is named as an S3 plugin but currently serves the
  MinIO demo path.
- `charts/floe-platform/values.yaml` owns `minio:` and
  `polaris.storage.s3.*` values independently of the storage plugin.
- `floe helm generate --artifact` has a placeholder for extracting plugin values
  from `CompiledArtifacts`, but does not yet do so.
- `PolarisCatalogPlugin` stores and reapplies `s3.endpoint`, which is a
  consumer projection concern rather than Polaris-owned storage truth.

This conflicts with Floe's target architecture. `CompiledArtifacts` should be
the resolved runtime source of truth, and storage is explicitly a pluggable
component under ADR-0036 and ADR-0037.

## Goals

- Strictly rename the alpha storage implementation from S3-compatible to MinIO.
- Add a generic storage deployment binding to `CompiledArtifacts`.
- Treat the typed storage binding as canonical and Helm values as derived
  output.
- Keep compiled artifacts free of raw secrets.
- Generate PyIceberg, Polaris, dbt, Dagster, provisioning, and Helm projections
  from the MinIO storage plugin.
- Keep bucket creation as a deployment/runtime action for alpha while modeling
  bucket requirements in the artifact.
- Shape the alpha contract so future native S3, GCS, Azure, and plugin-owned
  runtime provisioning can reuse it.
- Prove the full path with tests and E2E validation:
  `storage.type: minio` -> compile -> generated Helm values -> deploy ->
  Polaris configured -> data lands in MinIO.

## Non-Goals

- Do not ship a native AWS S3 plugin in alpha.
- Do not provide a `s3` compatibility alias or migration shim. There are no
  consumers to preserve.
- Do not call Kubernetes, MinIO, Polaris, or cloud APIs during compile.
- Do not serialize raw access keys, secret keys, root passwords, client
  secrets, or equivalent secret material in compiled artifacts.
- Do not make Helm chart values the canonical storage contract.
- Do not solve multi-storage mappings for alpha.

## Source Context And Validation

The design was validated against current Floe code and primary external
documentation:

- PyIceberg supports REST catalog configuration and S3-style catalog/FileIO
  properties through config files, environment variables, and Python API
  properties.
  Source: https://py.iceberg.apache.org/configuration/
- Iceberg REST catalog is the integration boundary for REST-compatible query
  engines and secure catalog access.
  Source: https://iceberg.apache.org/rest-catalog-spec/
- Apache Polaris models storage configuration separately for S3, Azure, and
  GCS, including S3 endpoint, internal endpoint, path-style access, allowed
  locations, region, and credential/role configuration.
  Source: https://polaris.apache.org/in-dev/unreleased/command-line-interface/
- Kubernetes supports secret injection through `secretKeyRef` and mounted
  secret volumes, which supports secret-free compiled artifacts.
  Source: https://kubernetes.io/docs/concepts/configuration/secret/
- Helm values are a deployment override/projection mechanism, not a semantic
  platform contract.
  Source: https://helm.sh/docs/v3/chart_template_guide/values_files/
- MinIO bucket creation is idempotently available through the MinIO client.
  Source: https://min.io/docs/minio/linux/reference/minio-mc/mc-mb.html
- S3 bucket concerns such as naming, lifecycle, versioning, encryption, Object
  Lock, and identity-based access are bucket-level requirements that should be
  modeled explicitly for future native cloud plugins.
  Sources:
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-bucket-encryption.html
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html
  - https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html

## Architecture Decision

Use a typed, generic storage deployment binding in `CompiledArtifacts`:

```python
class CompiledArtifacts(BaseModel):
    ...
    deployment: DeploymentConfig | None = None


class DeploymentConfig(BaseModel):
    storage: StorageDeploymentBinding | None = None
```

The storage binding is generic. MinIO is the only alpha implementation:

```python
class StorageDeploymentBinding(BaseModel):
    plugin: PluginRef
    protocol: Literal["s3-compatible", "s3", "gcs", "azure-blob"]
    warehouse: StorageWarehouse
    allowed_locations: list[str]
    buckets: list[StorageBucketRequirement]
    credentials: StorageCredentialBinding
    consumers: StorageConsumerBindings
    provisioning: StorageProvisioningIntent
    renderings: DeploymentRenderings
```

Rules:

- `plugin.type == "minio"` for alpha.
- `protocol == "s3-compatible"` for alpha MinIO.
- The typed storage binding is canonical.
- `renderings.helm["floe-platform"]` is derived from the binding.
- Raw secrets are forbidden anywhere under `deployment.storage`.
- Future native storage plugins extend the same model or add typed variants
  without making Helm values the public contract.

## Strict Rename

The alpha storage implementation becomes MinIO-specific:

- Rename `plugins/floe-storage-s3` to `plugins/floe-storage-minio`.
- Rename import package `floe_storage_s3` to `floe_storage_minio`.
- Rename `S3StoragePlugin` to `MinIOStoragePlugin`.
- Rename `S3StorageConfig` to `MinIOStorageConfig`.
- Rename entry point to:

```toml
[project.entry-points."floe.storage"]
minio = "floe_storage_minio.plugin:MinIOStoragePlugin"
```

- Update manifests to use `plugins.storage.type: minio`.
- Update tests, docs, demo packaging, PyIceberg dependency checks, plugin
  discovery checks, examples, and user-facing text.
- Remove active alpha claims that Floe ships a native S3 plugin.
- Do not keep `s3` as an alias.

The MinIO plugin owns MinIO-specific facts:

- S3-compatible endpoint shape.
- Path-style access.
- Internal Kubernetes service endpoint.
- Bucket defaults.
- MinIO chart values.
- PyIceberg S3-compatible properties.
- Polaris S3-compatible storage projection.
- Future provisioning intent.

## Secret Handling

Compiled artifacts are deployable and auditable, but not secret-bearing.

```python
class StorageCredentialBinding(BaseModel):
    mode: Literal["kubernetes-secret", "environment", "workload-identity", "none"]
    secret_ref: KubernetesSecretRef | None = None
    env_refs: dict[str, str] = {}
    service_account_ref: str | None = None


class KubernetesSecretRef(BaseModel):
    name: str
    namespace: str | None = None
    keys: dict[str, str]
```

Rules:

- `CompiledArtifacts` must not contain raw `accessKey`, `secretKey`,
  `rootPassword`, `clientSecret`, or equivalent values.
- Helm renderings should reference existing or generated secret names instead
  of embedding raw storage credentials.
- Runtime pods and bootstrap jobs consume credentials through Kubernetes Secret
  references or environment references.
- Future native AWS S3 should prefer workload identity or IRSA-style bindings
  over static keys.

## Compilation And Deployment Flow

The compile pipeline resolves and configures the selected storage plugin, then
asks it for the storage deployment binding:

```text
manifest.yaml
  plugins.storage.type: minio
  plugins.storage.config: ...

compile pipeline
  resolve_plugins()
  configure MinIO plugin with manifest config
  MinIOStoragePlugin.get_deployment_binding()
  build CompiledArtifacts.deployment.storage

floe helm generate --artifact target/compiled_artifacts.json
  load CompiledArtifacts
  read deployment.storage.renderings.helm["floe-platform"]
  merge with chart defaults, environment values, and user overrides

helm install/upgrade
  deploy MinIO, Polaris, bucket-init, and bootstrap jobs from generated values
```

Ownership rules:

- Compile validates configuration and emits desired state.
- Compile does not call live infrastructure.
- Helm generation consumes artifacts and does not rediscover storage config
  independently.
- Chart defaults remain safe empty defaults, not the source of MinIO truth.
- Environment values files can still set resource sizing, images, and demo
  topology, but should not redefine the storage contract independently.

## Provisioning And Bucket Requirements

Alpha keeps bucket creation as a deployment/runtime action, but the storage
binding models bucket requirements rather than a bare list of names.

```python
class StorageProvisioningIntent(BaseModel):
    enabled: bool
    mode: Literal["helm-job", "external", "manual", "future-plugin-runtime"]
    default_create_policy: Literal["create-if-missing", "must-exist", "never-create"]
    buckets: list[StorageBucketRequirement]


class StorageBucketRequirement(BaseModel):
    name: str
    uri: str
    purpose: Literal[
        "warehouse",
        "artifacts",
        "landing",
        "quarantine",
        "checkpoints",
        "exports",
    ]
    prefixes: list[str] = []
    create_policy: Literal["create-if-missing", "must-exist", "never-create"]
    required_features: BucketFeatureRequirements
    access: BucketAccessRequirements
    tags: dict[str, str] = {}
```

Alpha MinIO defaults:

- `mode: helm-job`
- `default_create_policy: create-if-missing`
- Required buckets:
  - `floe-iceberg`, purpose `warehouse`
  - `floe-artifacts`, purpose `artifacts`
- Versioning, encryption, object lock, lifecycle, retention, and access
  constraints are modeled as requirements but may be `optional`,
  `platform-default`, or `disabled` for alpha.

Common bucket requirements to support over time:

- Warehouse bucket for Iceberg tables.
- Artifacts bucket for compiled artifacts, dbt outputs, release evidence, logs,
  or run metadata.
- Landing/raw bucket or prefix for ingestion.
- Quarantine bucket or prefix for rejected records.
- Checkpoint bucket or prefix for streaming or ingestion state.
- Export bucket or prefix for downstream delivery.
- Per-environment separation through buckets or prefixes.
- Per-domain or per-product separation through buckets or prefixes.
- Pre-existing enterprise buckets that Floe must verify but not create.
- Versioning, lifecycle, encryption, Object Lock, retention, tags, and
  identity-scoped access.

Rules:

- Compile declares bucket requirements only.
- Compile never creates buckets.
- Helm bucket-init creates missing MinIO buckets idempotently in alpha.
- Native cloud plugins can later use `must-exist` or `never-create`.
- Future `floe platform storage provision` and `floe platform storage verify`
  commands consume the same requirements.

## Consumer Bindings

The storage plugin generates typed consumer projections. Consumers do not
rebuild storage config independently.

```python
class StorageConsumerBindings(BaseModel):
    pyiceberg: PyIcebergStorageBinding
    polaris: PolarisStorageBinding | None = None
    dbt: DbtStorageBinding | None = None
    dagster: DagsterStorageBinding | None = None


class StorageEndpointBinding(BaseModel):
    client_endpoint: str
    internal_endpoint: str | None = None
    external_endpoint: str | None = None
    region: str
    path_style_access: bool


class PyIcebergStorageBinding(BaseModel):
    endpoint: StorageEndpointBinding
    properties: dict[str, str]
    credential_refs: dict[str, CredentialRef]


class PolarisStorageBinding(BaseModel):
    storage_type: Literal["S3", "GCS", "AZURE"]
    default_base_location: str
    allowed_locations: list[str]
    endpoint: StorageEndpointBinding | None = None
    credential_refs: dict[str, CredentialRef]


class DbtStorageBinding(BaseModel):
    profile_fragment: dict[str, Any]
    env_refs: dict[str, str]


class DagsterStorageBinding(BaseModel):
    resources: dict[str, Any]
    env_refs: dict[str, str]
```

Rules:

- MinIO generates all consumer projections.
- PyIceberg, Polaris, dbt, and Dagster receive tool-specific config from
  `deployment.storage.consumers`.
- Consumer projections remain secret-free.
- Endpoint roles are explicit:
  - `client_endpoint`: workload/data pods.
  - `internal_endpoint`: server-side services such as Polaris.
  - `external_endpoint`: optional local/user access.
- Polaris can consume S3-shaped config internally, but it receives that as a
  projection from the MinIO storage binding.
- dbt profile generation merges storage binding output with compute profile
  output.
- Dagster resource creation consumes compiled storage bindings rather than
  re-deriving storage config from plugin refs at runtime.

## Testing And Acceptance

Acceptance gates:

- Unit tests for `MinIOStoragePlugin.get_deployment_binding()`.
- Schema tests for `CompiledArtifacts.deployment.storage`.
- Strict rename tests proving no active alpha path references
  `floe-storage-s3`, `floe_storage_s3`, or `storage.type: s3`.
- Security tests proving compiled artifacts and generated Helm values do not
  contain demo credential strings.
- Helm generation tests proving `floe helm generate --artifact` projects the
  MinIO binding into chart-compatible values.
- Chart tests proving Polaris bootstrap receives storage config from generated
  values and credentials through secret references.
- Contract tests proving dbt, Dagster, PyIceberg, and Polaris consume the same
  endpoint, bucket, and warehouse values from the binding.
- E2E test proving:
  `storage.type: minio` -> compile -> generated Helm values -> deploy ->
  bucket exists -> Polaris catalog uses generated storage config -> data lands
  in MinIO.

Verification tiers:

- Fast unit and contract: schema, plugin binding, no-secret assertions.
- Helm/chart: render and schema validation.
- Integration: local Kind/MinIO/Polaris bootstrap.
- E2E: full demo data path.

## Risks

- The binding can become too broad if it tries to model every cloud storage
  capability immediately. Keep alpha fields focused while leaving room for
  typed feature requirements.
- Derived Helm values can drift from typed binding fields unless generated in
  one place and tested against the canonical binding.
- Removing the `s3` name without an alias is intentionally disruptive. This is
  acceptable because there are no consumers, but tests and docs must be updated
  comprehensively.
- Chart secret handling requires careful migration because existing demo values
  include raw MinIO credentials.
- Dagster and dbt runtime paths currently derive storage config from plugin refs
  or compute config. Moving them to compiled storage bindings changes runtime
  wiring and needs focused contract tests.

## Success Criteria

The design is successful if, after implementation:

- `pip install floe-storage-minio` works.
- `floe-storage-s3` and `storage.type: s3` are absent from active alpha paths.
- `CompiledArtifacts.deployment.storage` is the secret-free source of storage
  truth.
- Helm generation consumes the compiled storage binding and produces chart
  values for MinIO and Polaris.
- Polaris no longer owns independent MinIO endpoint configuration.
- dbt, Dagster, PyIceberg, and Polaris projections agree on endpoint, warehouse,
  bucket, and credential references.
- E2E validation proves data lands in MinIO through the plugin-driven path.

## Next Step

After user review, create an implementation plan. The plan should stage work so
the contract/schema, plugin rename, chart rendering, runtime consumers, and E2E
validation can be reviewed independently.
