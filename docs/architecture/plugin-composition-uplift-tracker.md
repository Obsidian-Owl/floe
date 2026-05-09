# Plugin Composition Uplift Tracker

Status: Active after MinIO/storage composition landed
Owner: Floe architecture
Last updated: 2026-05-09

## Purpose

This document tracks adoption of Floe's composition model across plugin
families after the MinIO/storage composition work landed. Follow-on
plugin-family uplift is tracked here unless a plugin is required for the
implemented alpha Iceberg runtime path.

The landed work establishes the pattern for MinIO-backed, S3-compatible storage
composition in the Polaris/DuckDB/Dagster alpha path. Other plugins should
adopt the pattern only when they participate in concrete cross-plugin
composition. This prevents a platform-wide rewrite while keeping a clear target
state.

## Composition Levels

| Level | Meaning | Required Evidence |
| --- | --- | --- |
| 0 | Discoverable plugin only | Entry point, metadata, config schema |
| 1 | Declares capabilities and requirements | `PluginCapabilities`, `PluginRequirements`, compatibility tests |
| 2 | Emits or consumes typed bindings | Contract model, schema tests, no raw secrets |
| 3 | Has deployment/runtime translators validated by resolver | Resolver tests, generated deployment binding, renderer tests, E2E where applicable |

## Immediate Priority: Iceberg Runtime Path

| Plugin family | Target level | Status | Scope |
| --- | --- | --- | --- |
| Storage | 3 | Landed for `floe-storage-minio` | Neutral storage binding, bucket requirements, credential refs, capabilities, provisioning intent |
| Catalog | 3 | Landed for Polaris + MinIO | Catalog storage requirements, Polaris deployment binding, bootstrap payload, storage Secret refs |
| Compute / dbt | 3 | Landed for DuckDB/dbt profile path | Runtime storage binding consumption, profile generation, endpoint/credential consistency |
| Orchestrator / Dagster | 2 then 3 | Remaining migration | Dagster still needs binding-first Iceberg writer/runtime ownership cleanup |
| Helm / deployment renderer | 3 | Landed for MinIO/Polaris binding rendering | Render resolved deployment bindings; no semantic storage decisions in templates |
| Secrets / identity | 2 then 3 | Remaining projection work | Credential and workload identity modes are typed; full provider-owned projection still needs implementation |

## Follow-On Plugin Families

| Plugin family | Target level | Trigger for uplift | Notes |
| --- | --- | --- | --- |
| Ingestion | 2 then 3 | Landing, quarantine, checkpoint, or raw bucket requirements become first-class | Should consume storage bucket requirements instead of inventing bucket config |
| Semantic layer | 2 then 3 | Semantic runtime needs compute/catalog/storage binding | Avoid direct compute connection duplication |
| Lineage backend | 1 then 2 | Backend deployment/auth or endpoint wiring becomes plugin-owned | OpenLineage remains enforced standard |
| Telemetry backend | 1 then 2 | OTLP backend deployment topology becomes plugin-owned | OpenTelemetry remains enforced standard |
| Quality | 1 then 2 | Quality plugin needs runtime compute/storage capabilities | dbt tests remain enforced baseline |
| RBAC | 2 then 3 | Workload identities and Secret refs are generated from plugin bindings | Remaining work; should consume declared runtime surfaces |
| Network / pod security | 2 then 3 | Network policy needs service endpoints from plugin deployment bindings | Remaining work; should consume deployment bindings instead of static service names |
| Alert channels | 1 | Alert delivery backends add auth/deployment requirements | Keep low priority until user-facing alerts are implemented |

## Adoption Rules

- A plugin may declare what it needs and translate its own config.
- A plugin must not know every other plugin's implementation details.
- New compatibility should be represented as capabilities and requirements,
  not as chart conditionals.
- New provider-specific fields belong in provider-owned deployment bindings
  unless they are stable cross-provider concepts.
- `CompiledArtifacts` must remain secret-free.
- Helm and other renderers consume resolved deployment bindings; they do not
  rediscover plugin config.

## Landed MinIO/Storage Composition

- `floe-storage-minio` remains strict with no `s3` alias.
- `CompiledArtifacts.deployment.storage` carries neutral storage desired state.
- `CompiledArtifacts.deployment.catalog` carries Polaris-owned deployment and
  bootstrap state.
- Composition resolver validates Polaris + MinIO and rejects incompatible
  catalog/storage selections with actionable errors.
- `floe helm generate` renders from deployment bindings only.
- Architecture docs describe the composition model.
- Raw storage credentials are absent from compiled artifacts and generated
  chart values; Kubernetes Secret refs carry credential identity.
- Remote infrastructure E2E is run, product failures are separated from
  infrastructure failures, and billable resources are directly verified and
  cleaned up.

## Remaining Composition Work

- Credential and identity projection: provider-owned secret and workload
  identity resources need complete translation from typed modes.
- Dagster/Iceberg runtime ownership: orchestrators should delegate table
  mutation to the Iceberg writer contract instead of owning write semantics.
- Semantic datasource binding: semantic plugins should consume compiled
  compute/catalog/storage bindings rather than duplicate connection logic.
- RBAC and network policy generation: policy plugins should consume resolved
  service endpoints, Secret refs, and identity surfaces from deployment
  bindings.

## Future Tracking Items

| ID | Area | Work | Exit Signal |
| --- | --- | --- | --- |
| PCU-001 | Storage | Add native S3 storage plugin design | S3 plugin declares workload identity and bucket verification requirements |
| PCU-002 | Catalog | Add Glue catalog design | Glue rejects incompatible S3-compatible storage and accepts native S3 |
| PCU-003 | Catalog | Add Nessie catalog design | Nessie integration documents server-side vs client-side storage access |
| PCU-004 | Ingestion | Add landing/quarantine/checkpoint bucket requirements | Ingestion consumes storage bucket requirements |
| PCU-005 | Security | Connect credential binding to identity/secrets plugins | Implemented: workload identity and external secret modes are resolver-validated |
| PCU-006 | Network | Generate network policies from deployment bindings | Policies use plugin endpoints rather than static chart service assumptions |
| PCU-007 | Iceberg runtime | Extract writer contract from orchestrator export paths | Dagster and future orchestrators delegate Iceberg table mutation to `floe-iceberg` |
