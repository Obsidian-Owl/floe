# Storage Composition Research Brief

Date: 2026-05-07
Scope: Immediate Floe storage-side closeout for MinIO, Polaris, compiled
deployment bindings, plugin composition, bucket requirements, and follow-on
plugin uplift.

## Findings

### Polaris + MinIO Requires Explicit S3-Compatible Storage Configuration

Confidence: HIGH

Apache Polaris treats MinIO as S3-compatible storage. MinIO-backed catalogs must
set an explicit S3 endpoint so Polaris and clients do not default to AWS S3.
Polaris also distinguishes the endpoint returned to clients from the internal
endpoint the Polaris server uses. For MinIO and other non-AWS S3-compatible
stores, path-style access and no-STS behavior are first-class catalog creation
inputs.

Sources:

- https://polaris.apache.org/in-dev/unreleased/getting-started/creating-a-catalog/s3/catalog-minio/
- https://polaris.apache.org/in-dev/unreleased/getting-started/minio/
- https://polaris.apache.org/in-dev/unreleased/command-line-interface/

Implication for Floe:

Polaris-specific fields such as `storageConfigInfo`, `endpointInternal`,
`pathStyleAccess`, `stsUnavailable`, and allowed locations should be owned by
the Polaris catalog plugin, not by the MinIO storage plugin or Helm shell.

### Polaris Helm Already Exposes Storage Secret References

Confidence: HIGH

The Apache Polaris Helm values reference includes `storage.secret.*` fields for
storage credential secrets. That supports the Floe direction of passing
credential references rather than raw credential values.

Source:

- https://polaris.apache.org/in-dev/unreleased/helm-chart/reference/

Implication for Floe:

`CompiledArtifacts` should stay secret-free. Deployment bindings should carry
Secret references and the renderer should map those references to the chart's
credential surface.

### Iceberg REST Catalog Exists To Reduce Catalog/Client Compatibility Pain

Confidence: HIGH

Apache Iceberg describes REST catalog as a common API created to address the
practical problem of many clients needing many catalog-specific integrations.
The spec also calls out secure sharing through credential vending or remote
signing.

Source:

- https://iceberg.apache.org/rest-catalog-spec/

Implication for Floe:

Floe should avoid recreating an N x M coupling matrix between storage, catalog,
compute, and orchestrator plugins. A composition resolver plus plugin-owned
translation preserves the same compatibility goal at the Floe plugin layer.

### PyIceberg Supports Explicit S3-Compatible FileIO Properties

Confidence: HIGH

PyIceberg supports configuration through files, environment variables, and
Python properties. S3-compatible object stores are configured through explicit
S3 endpoint and FileIO/catalog properties.

Source:

- https://py.iceberg.apache.org/configuration/

Implication for Floe:

The neutral storage binding should include endpoint roles, region, path-style
access, URI scheme, and credential refs. Consumer plugins can translate those
facts into PyIceberg, dbt, Dagster, or catalog-specific config.

### Secret References Are The Correct Kubernetes Boundary

Confidence: HIGH

Kubernetes Secrets can be consumed by pods through Secret references and
`secretKeyRef` environment variables.

Source:

- https://kubernetes.io/docs/concepts/configuration/secret/

Implication for Floe:

Storage credentials should remain references in artifacts and deployment
bindings. Tests should assert that raw secret strings are absent.

### Helm Values Are Render Inputs, Not The Semantic Contract

Confidence: HIGH

Helm values are chart defaults and override layers used by template rendering.

Source:

- https://helm.sh/docs/chart_template_guide/values_files/

Implication for Floe:

Helm values are a renderer output for Floe's current Kubernetes chart. They
should not be the architecture's source of storage/catalog truth.

### Bucket Requirements Must Be Modeled Explicitly

Confidence: HIGH

S3 buckets carry requirements beyond name and URI: naming, region, versioning,
lifecycle, encryption, Object Lock, retention, tags, object keys/prefixes, and
access controls.

Source:

- https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html

Implication for Floe:

The storage binding should model bucket requirements now, even if MinIO alpha
only provisions warehouse and artifacts buckets with simple defaults. Future
S3/GCS/Azure and enterprise deployments will need explicit create/verify/manual
policies.

## Validated Design Direction

Floe should add a composition compatibility layer, not a backwards
compatibility layer.

The correct immediate design is:

```text
StoragePlugin emits neutral storage binding.
CatalogPlugin declares storage requirements and translates storage into catalog deployment.
Compute/dbt and Orchestrator/Dagster consume runtime storage bindings.
CompositionResolver validates selected plugins before rendering deployment values.
Helm renders resolved deployment bindings only.
```

This keeps plugin ownership narrow:

- Storage owns storage facts.
- Catalog owns catalog bootstrap and server-side storage integration.
- Compute owns compute runtime profile translation.
- Orchestrator owns pod/runtime wiring.
- Helm owns rendering, not compatibility decisions.
