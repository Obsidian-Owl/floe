# Storage Composition Closeout Design

Status: Approved for planning
Date: 2026-05-07
Author: Codex

## Summary

Floe should finish the storage-side MinIO work by replacing the remaining
chart-driven storage coupling with a composition model:

```text
selected plugins
  -> plugin capabilities and requirements
  -> composition resolver
  -> neutral storage binding
  -> consumer-owned deployment/runtime bindings
  -> Helm/Kubernetes rendering
```

The strict `floe-storage-minio` rename remains correct. The missing piece is
not a backwards-compatibility alias. The missing piece is a small,
typed compatibility layer in `floe-core` that validates whether selected
plugins compose and routes storage facts to the plugin that owns each
translation.

For this storage closeout, the immediate priority is the Iceberg runtime path:
storage, catalog, compute/dbt, orchestrator/Dagster, deployment rendering, and
credential binding. Broader plugin adoption is tracked separately so this PR
does not become a platform-wide rewrite.

## Research Validation

The redesign is based on current Floe code and official upstream contracts:

- Apache Polaris documents MinIO-backed catalog creation as S3 storage with an
  explicit endpoint. It also distinguishes `endpoint` for clients from
  `endpointInternal` for Polaris server-side access, supports path-style access,
  allowed locations, region, and no-STS behavior.
  Source: https://polaris.apache.org/in-dev/unreleased/getting-started/creating-a-catalog/s3/catalog-minio/
- Apache Polaris Helm exposes storage credential secret references under
  `storage.secret.*`, confirming that storage credentials are a deployment
  concern and should be referenced, not copied into semantic artifacts.
  Source: https://polaris.apache.org/in-dev/unreleased/helm-chart/reference/
- Apache Iceberg's REST catalog exists to reduce client/catalog compatibility
  problems and supports secure table sharing with credential vending or remote
  signing.
  Source: https://iceberg.apache.org/rest-catalog-spec/
- PyIceberg supports S3-compatible storage through explicit endpoint and
  FileIO/catalog properties, including S3 endpoint and path-style settings.
  Source: https://py.iceberg.apache.org/configuration/
- Kubernetes supports secret consumption through Secret references and
  `secretKeyRef`, which matches Floe's secret-free compiled artifact contract.
  Source: https://kubernetes.io/docs/concepts/configuration/secret/
- Helm values are chart inputs and override layers. They are useful deployment
  renderings but should not be the semantic platform contract.
  Source: https://helm.sh/docs/chart_template_guide/values_files/
- S3 bucket requirements are larger than a name list: naming rules, region,
  versioning, lifecycle, encryption, Object Lock, retention, tags, and access
  posture all matter for future cloud and enterprise storage plugins.
  Source: https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html

## Current Problem

The current branch has made good progress:

- The alpha storage implementation has been strictly renamed to
  `floe-storage-minio`.
- `CompiledArtifacts.deployment.storage` exists and is secret-free.
- `floe helm generate --artifact` derives MinIO and Polaris chart values from
  the compiled storage binding.
- dbt and Dagster paths consume compiled storage projections in places.

The architecture is still incomplete:

- `StorageDeploymentBinding` is too narrow. It has `provider`, endpoint,
  credentials, `dbt`, and `dagster`, but no protocol, bucket requirements,
  capability surface, or catalog-neutral composition contract.
- `MinIOStoragePlugin` still emits Polaris-shaped Helm values. That makes the
  storage plugin aware of a catalog plugin's deployment surface.
- `job-polaris-bootstrap.yaml` still assembles `storageConfigInfo` in Helm
  shell from `polaris.storage.s3.*`. That leaves Helm as a storage integration
  brain.
- Polaris server-side storage configuration is being patched through env vars,
  but the remote DevPod lane still fails at table creation because the selected
  env surfaces do not match the actual upstream integration boundary.
- Compatibility is implicit in chart values and tests instead of explicit in a
  resolver that can fail fast.

The failure mode is architectural: Floe has plugin discovery, but it does not
yet have a first-class composition layer for cross-plugin contracts.

## Goals

- Keep the strict MinIO rename with no compatibility alias.
- Make `CompiledArtifacts.deployment.storage` the neutral storage contract.
- Add composition resolver primitives in `floe-core` for capabilities,
  requirements, validation, and typed binding handoff.
- Move Polaris-specific storage translation out of MinIO and Helm.
- Keep secrets out of compiled artifacts and generated docs.
- Model bucket requirements explicitly enough for MinIO now and S3/GCS/Azure
  later.
- Keep compile side-effect free: compile validates and emits desired state;
  deploy/render steps create or verify live infrastructure.
- Update architecture docs so the implemented direction and target state agree.
- Add a tracking document for plugin-family uplift after the storage PR.

## Non-Goals

- Do not add a `storage.type: s3` alias.
- Do not ship native AWS S3, GCS, Azure, Glue, Nessie, or Hive in this work.
- Do not uplift every plugin category in this PR.
- Do not make Helm values the canonical storage API.
- Do not create a universal adapter that hides incompatibilities.
- Do not perform live MinIO, Polaris, Kubernetes, or cloud API calls during
  compile.

## Architecture Decision

Use a composition resolver plus typed adapter contracts.

### Core Composition Primitives

```python
class PluginCapabilities(BaseModel):
    plugin_type: str
    plugin_name: str
    capabilities: dict[str, Any]


class PluginRequirements(BaseModel):
    plugin_type: str
    plugin_name: str
    requirements: dict[str, Any]


class CompositionIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    plugins: list[str]


class CompositionValidationResult(BaseModel):
    valid: bool
    issues: list[CompositionIssue]
```

The resolver lives in `floe-core` because plugin compatibility is a platform
contract, not a chart behavior. It must be deterministic and side-effect free.

### Neutral Storage Binding

```python
class StorageDeploymentBinding(BaseModel):
    provider: Literal["minio"]
    protocol: Literal["s3-compatible", "s3", "gcs", "azure-blob"]
    endpoint: StorageServiceEndpoint
    warehouse: StorageWarehouse
    allowed_locations: list[str]
    buckets: list[StorageBucketRequirement]
    credentials: StorageCredentialBinding
    capabilities: StorageCapabilities
    provisioning: StorageProvisioningIntent
    runtime: StorageRuntimeBinding
```

Rules:

- `provider == "minio"` and `protocol == "s3-compatible"` for alpha.
- `endpoint` has explicit roles: client workload endpoint, internal service
  endpoint, external endpoint, region, and path-style access.
- `credentials` uses refs only: Kubernetes Secret, environment, workload
  identity, or none.
- `buckets` declares desired state. Compile never creates buckets.
- `capabilities` declares facts such as path-style support, STS availability,
  credential modes, and supported URI schemes.
- `runtime` exposes storage-owned FileIO/dbt/Dagster-neutral facts, not
  catalog-owned deployment config.

### Consumer-Owned Translation

Storage plugins emit neutral storage facts. Consumer plugins translate those
facts into their own deployment/runtime shapes.

```python
class CatalogPlugin:
    def get_storage_requirements(self) -> PluginRequirements:
        ...

    def build_catalog_deployment(
        self,
        storage: StorageDeploymentBinding,
    ) -> CatalogDeploymentBinding:
        ...
```

For Polaris + MinIO, `PolarisCatalogPlugin` owns:

- `storageConfigInfo.storageType == "S3"`
- `default-base-location`
- `allowedLocations`
- `endpoint` and `endpointInternal`
- `pathStyleAccess`
- `stsUnavailable`
- Polaris/Helm storage secret references
- bootstrap payload shape

For a future catalog:

- Glue can reject `protocol == "s3-compatible"` and require native `s3` plus
  workload identity.
- Nessie can accept MinIO if it supports client-side S3-compatible FileIO
  rather than Polaris-style server-side storage configuration.
- Hive can declare whether it needs server-side storage access or only
  warehouse URI and client FileIO configuration.

Adding a catalog should require implementing the catalog plugin's requirements
and translator, not editing the MinIO plugin.

## Compatibility Rules

The resolver must fail early for incompatible selections.

Examples:

```text
catalog=glue, storage=minio
  -> error: Glue requires protocol=s3 and AWS identity. Got s3-compatible.

catalog=polaris, storage=minio
  -> valid when endpoint.internal_url, path_style_access=true,
     sts_supported=false, allowed_locations includes warehouse, and
     credentials are reference-backed.

catalog=polaris, storage=minio, credentials=none
  -> error: Polaris requires server-side storage credentials or a supported
     credential vending/workload identity mode.
```

Compatibility checks are not a migration layer. They are explicit proof that
the selected plugin graph can produce a deployable platform.

## Bucket Requirements

Bucket requirements should be modeled now because users will need more than
one storage location:

- Warehouse bucket for Iceberg table data and metadata.
- Artifacts bucket for compiled artifacts, dbt outputs, release evidence, logs,
  and run metadata.
- Landing/raw bucket or prefix for ingestion.
- Quarantine bucket or prefix for rejected records.
- Checkpoint bucket or prefix for streaming and ingestion state.
- Export bucket or prefix for downstream delivery.
- Environment, domain, or product separation by bucket or prefix.
- Pre-existing enterprise buckets that must be verified but not created.
- Versioning, lifecycle, encryption, object lock, retention, tags, and
  identity-scoped access.

Alpha defaults:

```text
warehouse bucket: floe-iceberg, create-if-missing
artifact bucket: floe-artifacts, create-if-missing
provisioning mode: helm-job
versioning/encryption/lifecycle: modeled but not enforced for MinIO alpha
```

## Deployment Flow

```text
manifest.yaml
  plugins.storage.type: minio
  plugins.catalog.type: polaris

compile
  resolve plugins
  build neutral storage binding
  ask catalog plugin for storage requirements
  run composition resolver
  emit CompiledArtifacts.deployment.storage
  emit CompiledArtifacts.deployment.catalog

helm generate
  read deployment bindings
  render chart-compatible values
  do not rediscover storage config

helm install/upgrade
  create MinIO buckets through bucket-init job
  bootstrap Polaris using catalog-owned deployment binding
  mount/pass storage credentials through Secret refs
```

## Architecture Document Updates Required

The PR must update these documents:

- `docs/architecture/adr/0036-storage-plugin-interface.md`: replace
  consumer-specific storage plugin methods as the target model with neutral
  storage binding plus composition resolver.
- `docs/architecture/interfaces/storage-plugin.md`: document
  `get_deployment_binding()` as the primary compile-time method and move
  dbt/Dagster/Helm methods to compatibility/deprecation notes.
- `docs/architecture/interfaces/catalog-plugin.md`: add catalog storage
  requirements and catalog deployment binding translation.
- `docs/architecture/plugin-system/interfaces.md`: align plugin interface
  summary with composition levels and typed adapter contracts.
- `docs/architecture/opinionation-boundaries.md`: clarify that storage is
  pluggable through neutral bindings and that catalog/storage compatibility is
  validated by `floe-core`.
- `docs/contracts/compiled-artifacts.md`: document `deployment.storage` and
  `deployment.catalog` as deployment bindings.
- `docs/architecture/plugin-composition-uplift-tracker.md`: track follow-on
  adoption for all plugin categories.

## Testing And Acceptance

Acceptance gates:

- Schema tests for neutral storage binding, bucket requirements, credential
  refs, capabilities, and side-effect-free serialization.
- Unit tests for `MinIOStoragePlugin.get_deployment_binding()`.
- Unit tests for `PolarisCatalogPlugin.build_catalog_deployment(storage)`.
- Composition resolver tests for valid Polaris+MinIO and invalid Glue+MinIO
  style cases.
- Helm generation tests proving values come from deployment bindings, not from
  raw `plugins.storage.config`.
- Chart tests proving Polaris bootstrap consumes generated catalog deployment
  config and storage Secret refs.
- Contract tests proving dbt, Dagster, PyIceberg, and Polaris agree on endpoint,
  warehouse, bucket, region, path-style access, and credential refs.
- Security tests proving compiled artifacts and generated values contain no raw
  MinIO, AWS, Polaris, or OAuth secret values.
- DevPod + Hetzner remote E2E proving data lands in MinIO and direct provider
  cleanup is verified after the run.

## Risks

- The resolver can become a giant universal abstraction. Keep it limited to
  capabilities, requirements, and compatibility issues.
- The storage binding can become too broad. Model stable object-storage
  concepts, not every provider-specific knob.
- Existing tests assert `polaris.storage.s3.*` chart values. Those tests need
  to move up to generated deployment bindings rather than preserve the chart as
  the semantic source of truth.
- Polaris' upstream config surface is evolving. Use official CLI/Helm/API
  fields where available and keep Polaris-specific decisions inside the Polaris
  plugin.

## Success Criteria

- MinIO storage remains strict with no S3 alias.
- `CompiledArtifacts.deployment.storage` is neutral, secret-free, and capable
  enough for future storage backends.
- `CompiledArtifacts.deployment.catalog` contains Polaris-owned deployment and
  bootstrap config derived from the neutral storage binding.
- `floe helm generate` renders storage and catalog values from deployment
  bindings.
- MinIO no longer emits Polaris-specific storage config.
- Helm no longer constructs semantic `storageConfigInfo` from independent chart
  values.
- A new catalog plugin can be added by declaring storage requirements and
  implementing catalog-owned translation, without changing MinIO.
- The storage PR includes architecture doc updates and the plugin uplift tracker.
