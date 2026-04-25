# Alpha Spine Closure Design

Status: Draft for user review
Date: 2026-04-26
Author: Codex

## Summary

The remaining alpha failures no longer look like stale image handling,
hardcoded demo configuration, or train-network instability. The local runtime
path now reaches dbt successfully, then fails while exporting to Iceberg through
Polaris because the catalog points at missing object-store metadata. That makes
the catalog/object-store lifecycle the central spine for closure.

The design is to close issues in dependency order:

1. Make Iceberg catalog/object-store state deterministic and recoverable.
2. Make resource sizing manifest-driven so runtime stability is configured, not
   patched by chart overrides.
3. Validate OpenLineage and Marquez after materialization is stable.
4. Validate DevPod/Hetzner only after local runtime behavior and branch/source
   selection are deterministic.

## Goals

- Recover or fail clearly when Polaris has stale table metadata that references
  missing S3/MinIO metadata files.
- Make reset semantics atomic across catalog and object storage for test/demo
  runs.
- Ensure runtime resource presets are part of an explicit configuration
  contract instead of ignored manifest extras.
- Prove OpenLineage lifecycle events through the same Dagster runtime path that
  writes Iceberg tables.
- Make DevPod/Hetzner validation run the intended source branch and fail with
  actionable diagnostics when platform readiness times out.

## Non-Goals

- Replace Polaris, PyIceberg, Dagster, or Marquez.
- Add broad retries around deterministic product failures.
- Treat a successful dbt run as sufficient alpha evidence.
- Build a general-purpose data repair tool outside the demo/test lifecycle.
- Reopen the broader Dagster path-collapse design unless implementation exposes
  a direct conflict.

## Architecture

The closure path keeps the existing four-layer model:

```text
manifest.yaml + floe.yaml
  -> CompiledArtifacts
  -> Dagster runtime loader
  -> dbt execution
  -> Iceberg export via Polaris + object storage
  -> OpenLineage emission
  -> Marquez validation
```

The critical boundary is between the Iceberg catalog and object storage. The
catalog is the source of table identity and current metadata location. Object
storage is the source of the referenced Iceberg metadata and data files. A table
reference is healthy only when both sides agree. A catalog table whose metadata
location no longer exists must not be treated as an ordinary existing table.

## Components

### Catalog Health And Recovery

Add an explicit stale-table classification at the Iceberg lifecycle boundary.
When loading an existing table fails because the catalog metadata location
points to a missing object-store file, classify that as `stale_table_metadata`.

The runtime should handle that state by mode:

- `strict`: fail before export with a clear precondition error.
- `repair`: drop/recreate the broken table registration, then continue.
- `reset`: clear demo/test catalog and object-store state before running.

The default for alpha demo/test validation should be deterministic reset before
the run, plus repair for individual stale table references detected during
export. Production defaults should prefer strict unless a platform manifest or
runtime profile explicitly enables repair.

### Manifest-Driven Runtime Resources

`demo/manifest.yaml` currently contains `resource_presets`, while
`PlatformManifest` ignores it as an unknown field. That is a configuration
contract gap.

The design is to model resource presets explicitly in the platform deployment
configuration contract, then pass selected presets into Helm values generation.
If `resource_presets` is intended to be top-level manifest configuration, add it
to `PlatformManifest`. If it belongs to deployment-specific Helm config, remove
it from the demo manifest and move it to the existing Helm configuration schema.

The implementation plan should choose one owner and remove the ignored-field
state. Silent acceptance with a warning is not acceptable for runtime resources
that decide whether Dagster daemon stays alive.

### Lineage Validation

OpenLineage and Marquez validation should run after Iceberg materialization has
a stable success path. The lineage proof must assert both emission and Marquez
visibility using the namespace and job name produced by the runtime, not a
hardcoded expectation that can drift from event identity.

The validation should capture:

- OpenLineage START event.
- OpenLineage COMPLETE or FAIL event.
- Job namespace and job name used in emitted events.
- Marquez API visibility for that exact namespace/job pair.

### DevPod/Hetzner Validation

DevPod validation must run the intended source branch or commit. The current
failure applied Flux resources from a different branch, so it cannot prove or
disprove local changes.

The design is to make branch/source selection explicit in the DevPod runner,
record it in validation output, and fail early if the remote Flux source does
not match the requested branch or commit.

## Data Flow

1. Compile manifest and floe product configuration into `CompiledArtifacts`.
2. Load Dagster definitions from compiled artifacts.
3. Before materialization, run demo/test reset if selected.
4. During Iceberg export, load or create table through the Iceberg lifecycle
   boundary.
5. If a table reference is stale, classify the condition and apply the selected
   runtime mode.
6. Assert expected Iceberg tables exist after dbt reports success.
7. Emit OpenLineage events from the same runtime execution.
8. Query Marquez using the emitted namespace/job identity.
9. For DevPod, verify remote source identity before waiting for platform
   readiness.

## Error Handling

- Missing object-store metadata referenced by Polaris is a structured stale
  metadata error, not a generic dbt or PyIceberg failure.
- Failed repair must include table identifier, metadata location, selected mode,
  and original exception class.
- Ignored resource preset configuration must become either a schema validation
  error or a modeled field.
- Marquez 404 must report the namespace/job pair that was queried and the
  namespace/job pair observed in emitted events, when available.
- DevPod readiness timeout must include Flux source branch/commit, HelmRelease
  status, and relevant pod/container diagnostics.

## Testing

### Unit

- Iceberg lifecycle classifies missing metadata-location failures as stale table
  metadata.
- Repair mode calls catalog drop/recreate only for stale metadata, not arbitrary
  load failures.
- Strict mode raises a clear precondition error.
- Manifest or Helm schema rejects/accepts `resource_presets` according to the
  chosen ownership model.
- Marquez query helper uses emitted OpenLineage namespace/job identity.

### Integration

- Polaris + MinIO stale metadata repro: create table registration, remove
  referenced metadata, then verify reset/repair behavior.
- Dagster runtime materialization: dbt succeeds and expected Iceberg tables
  exist.
- Dagster daemon resource rendering: selected preset appears in rendered Helm
  values/manifests.

### E2E

- Demo run completes from manifest/floe configuration through Dagster, dbt,
  Iceberg, OpenLineage, and Marquez.
- Re-running demo after reset is deterministic.
- DevPod/Hetzner records and validates the source branch/commit before platform
  readiness wait.

## Implementation Order

1. Write a failing stale-table metadata regression test around the Iceberg
   lifecycle/catalog boundary.
2. Implement stale metadata classification and selected reset/repair behavior.
3. Add post-dbt Iceberg table existence assertions to demo/E2E validation.
4. Resolve `resource_presets` ownership and propagate selected presets into
   rendered runtime resources.
5. Update lineage validation to query Marquez from emitted event identity.
6. Make DevPod branch/source selection explicit and captured in diagnostics.
7. Run local Kind demo/E2E, then DevPod/Hetzner, then CI-aligned gates.

## Acceptance Criteria

- A stale Polaris table pointer to missing S3/MinIO metadata is reproduced by a
  test and no longer fails as an unexplained downstream export error.
- Demo/test reset clears catalog and object storage consistently or fails before
  materialization begins.
- dbt success without expected Iceberg tables is treated as a validation
  failure.
- Runtime resources are manifest/deployment-schema driven; no ignored
  `resource_presets` field remains in the demo path.
- Marquez validation uses the namespace/job identity emitted by OpenLineage.
- DevPod/Hetzner validation proves which branch or commit was deployed.
- Remaining failures, if any, are categorized as catalog lifecycle, resource
  rendering, lineage identity, DevPod source/readiness, or external transient.

## Risks

- PyIceberg and Polaris may not expose enough detail to distinguish missing
  metadata files from other bad-request failures without message inspection.
  Mitigation: wrap the lowest boundary where the metadata-location failure is
  observable and preserve the original exception.
- Repair mode could hide destructive behavior if enabled broadly. Mitigation:
  default production behavior to strict and require explicit demo/test repair or
  reset mode.
- Resource presets could belong in deployment configuration rather than platform
  manifests. Mitigation: decide ownership before implementation and remove the
  ignored field either way.
- Lineage validation may still fail after catalog repair due naming mismatch.
  Mitigation: query Marquez using emitted event identity before asserting
  product-level expectations.

## Open Decisions For Planning

- Whether stale table repair belongs in `floe-iceberg`, the Polaris catalog
  plugin, or demo/test reset orchestration.
- Whether `resource_presets` is a `PlatformManifest` field or Helm deployment
  configuration only.
- Whether demo/test reset should default to purge table metadata only, purge
  object storage prefixes too, or recreate the full namespace.
