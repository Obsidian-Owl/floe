# Provider Compatibility Spike Design

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Branch: `main`
Status: Approved design

## Purpose

Validate whether Floe's merged plugin binding and composition model is
provider-neutral enough to support additional storage and catalog providers
without weakening the architecture constraints that now protect the alpha
runtime path.

This is an architecture validation spike, not a provider implementation
project. It should produce a provider compatibility matrix, classify gaps, and
define one live-service validation proof. It should not build production AWS,
Glue, Nessie, GCS, or Azure support as part of the spike itself.

The spike must preserve these rules:

- Capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin compatibility.
- Plugins do not know another plugin's concrete implementation details.
- `CompiledArtifacts` remains secret-free.
- Runtimes and renderers consume resolved deployment/runtime bindings.
- Compatibility layers are introduced or retained only when the evidence proves
  they are needed.

## Success Criteria

The spike is complete when it answers these questions with code and runtime
evidence references:

1. Which provider combinations are already expressible by the current model?
2. Which combinations need new capability or requirement dimensions?
3. Which combinations need new typed deployment or runtime binding fields?
4. Which combinations need provider plugin implementation but no model change?
5. Which combinations need runtime or renderer translation work?
6. Which combinations should remain deferred until a concrete composition path
   exists?
7. Which live-service proof should be implemented first?

The first live proof should target AWS S3 plus AWS Glue if credentials and
cleanup controls are available. Nessie plus MinIO is the fallback because it
exercises catalog variation while reusing the known storage lane.

## Implemented System Map

The spike starts from the implemented `main` system, not from historical plans.

Current composition contracts:

- `packages/floe-core/src/floe_core/composition/models.py`
  - `CapabilitySet`
  - `RequirementSet`
  - `PluginCapabilities`
  - `PluginRequirements`
  - `CompositionIssue`
  - `CompositionValidationResult`
- `packages/floe-core/src/floe_core/composition/resolver.py`
  - Validates storage, catalog, secrets, identity, and ingestion compatibility.
  - Emits operator-facing `COMPOSITION_*` diagnostics where covered by the
    public taxonomy.

Current typed deployment and runtime bindings:

- `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
  - `StorageDeploymentBinding`
  - `CatalogDeploymentBinding`
  - `IngestionDeploymentBinding`
  - `RuntimeCatalogConnection`
  - `CredentialRef`
  - `StorageCredentialBinding`
  - `DeploymentConfig`
- `packages/floe-core/src/floe_core/runtime_catalog_connection.py`
  - Derives a neutral `RuntimeCatalogConnection` from storage and catalog
    deployment bindings.
- `packages/floe-iceberg/src/floe_iceberg/runtime_catalog.py`
  - Translates `RuntimeCatalogConnection` into PyIceberg connection config.

Current provider implementations and consumers:

- `plugins/floe-storage-minio`
  - Emits `StorageDeploymentBinding`.
  - Provides the known-good S3-compatible storage baseline.
- `plugins/floe-catalog-polaris`
  - Declares storage requirements.
  - Translates storage binding into `CatalogDeploymentBinding`.
- `plugins/floe-compute-duckdb`
  - Augments dbt profiles from compiled deployment projections.
- `plugins/floe-ingestion-dlt`
  - Declares storage/catalog requirements.
  - Emits `IngestionDeploymentBinding` from composed storage and catalog
    bindings.
- `plugins/floe-orchestrator-dagster`
  - Consumes `RuntimeCatalogConnection` for Dagster/Iceberg runtime paths.
- `packages/floe-core/src/floe_core/cli/helm/generate.py`
  - Renders platform Helm values from deployment bindings.

Known-good baseline:

- MinIO plus Polaris is the control path for the spike.
- The current remote DevPod/Hetzner lane validates the merged runtime path and
  separates infrastructure failures from product failures.

Known compatibility and cleanup constraints:

- Deprecated helper APIs must not be used as new cross-plugin contracts.
- Provider-specific fields belong in provider-owned bindings unless they are
  stable cross-provider concepts.
- Protocol-level S3-compatible settings must stay distinct from the removed
  legacy Floe storage plugin type `s3`.

## Provider Matrix

The spike must evaluate providers before implementation. Each row should carry a
decision, required evidence, and next action.

Initial matrix rows:

| Provider combination | Purpose | Expected disposition |
| --- | --- | --- |
| MinIO + Polaris | Known-good baseline | Level 3 control path |
| AWS S3 + AWS Glue | First preferred live proof | Primary compatibility target |
| AWS S3 + Polaris or Iceberg REST | Native cloud storage with existing REST catalog style | Matrix target, live proof optional |
| MinIO + Nessie | Fallback live proof with catalog variation | Fallback compatibility target |
| AWS S3 + Nessie | Combined native storage and non-AWS catalog variation | Second-wave target |
| GCS + future catalog | Pressure test for neutral storage concepts | Design-only unless product trigger exists |
| Azure Blob or ADLS + future catalog | Pressure test for neutral identity and endpoint concepts | Design-only unless product trigger exists |
| Hive catalog | Legacy catalog pressure test | Defer unless a concrete deployment path exists |

Each row must record:

- Storage provider.
- Catalog provider.
- Runtime consumers.
- Table format.
- Deployment ownership.
- Credential model.
- Identity model.
- Endpoint shape.
- Warehouse ownership.
- Server-side storage access requirement.
- Runtime projection needs.
- Renderer projection needs.
- Secret-free proof.
- Live proof requirements.
- Cleanup requirements.

## Gap Classification

Each provider gap must be classified into exactly one primary category:

| Category | Meaning | Example action |
| --- | --- | --- |
| No change | Current model already expresses the provider path | Add or identify validation evidence |
| Capability-only gap | Resolver needs another compatibility dimension | Add capability and requirement fields |
| Typed binding gap | Current bindings cannot carry required secret-free state | Add neutral or provider-owned binding fields |
| Provider plugin gap | Model is sufficient, but provider plugin does not exist | Plan provider implementation separately |
| Runtime translator gap | Binding exists, but runtime library translation is missing | Add translator tests and implementation plan |
| Renderer gap | Deployment output cannot be generated from bindings yet | Add renderer contract work |
| Live validation gap | Static evidence is sufficient for design, but real service proof is missing | Define live lane and resource cleanup |
| Out of scope | Provider path lacks a concrete composition trigger | Record deferral reason |

Decision rules:

- If a provider requires only different constants or endpoint values, do not add
  a new abstraction.
- If two or more providers need the same concept, consider a neutral binding
  field.
- If only one provider needs a concept, keep it under that provider's binding.
- If a provider needs raw credential values in `CompiledArtifacts`, reject the
  design.
- If runtime code must rediscover plugin config to execute, the design is
  incomplete.
- If one plugin must inspect another plugin's class or config shape, reject the
  approach.

## Live-Service Validation Plan

The spike should define, but not yet implement, one live-service validation lane.

### Preferred Lane: AWS S3 Plus AWS Glue

This lane proves native cloud storage and managed catalog compatibility.

Required live resources:

- Dedicated S3 bucket or prefixed test warehouse.
- Glue database/catalog namespace.
- IAM role, workload identity, or secret-backed credentials scoped to the test.
- Temporary Iceberg test table or namespace.
- DevPod/Hetzner workspace for the remote Floe validation environment.

Required product proof:

- Floe compiles a provider selection into secret-free `CompiledArtifacts`.
- Resolver accepts a valid AWS S3 plus Glue combination.
- Resolver rejects incompatible credential, identity, or storage access modes.
- Runtime config is derived from typed bindings.
- PyIceberg or the selected runtime creates, lists, reads, or writes an Iceberg
  table through Glue and S3.
- Logs and artifacts do not contain raw credentials.

Required cleanup proof:

- DevPod workspace is deleted.
- Hetzner servers, volumes, SSH keys, load balancers, and floating IPs are
  directly inventoried and removed if current-run resources remain.
- AWS S3 test objects and buckets or prefixes are deleted.
- Glue databases, tables, and temporary catalog resources are deleted.
- IAM test roles, policies, access keys, or session resources are verified
  removed or confirmed external and reusable.

### Fallback Lane: Nessie Plus MinIO

This lane proves catalog variation while avoiding cloud IAM and AWS billing
surface area.

Required proof:

- Nessie declares catalog/storage requirements that compose with MinIO.
- Typed catalog binding captures the Nessie endpoint and Iceberg runtime needs.
- Runtime config is derived from deployment bindings.
- Iceberg table create/read/write succeeds against Nessie and MinIO.
- No raw credentials appear in compiled artifacts or logs.
- DevPod/Hetzner resources are cleaned up with direct provider inventory.

## Validation Lanes

The spike should define evidence for five validation lanes.

### Static Lane

Required evidence:

- Resolver tests for compatible and incompatible provider combinations.
- Schema tests for any proposed capability or binding changes.
- Secret-free contract tests for compiled artifacts.
- Search evidence that runtime/renderers are not rediscovering plugin config.

### Renderer Lane

Required evidence:

- Generated deployment values are derived from typed bindings.
- Provider-specific deployment fields live under provider-owned projections.
- Helm or renderer output references secrets by name/key only.
- No renderer consults raw plugin config to make compatibility decisions.

### Runtime Lane

Required evidence:

- `RuntimeCatalogConnection` or the relevant typed binding translates to
  PyIceberg, Dagster, dlt, and dbt inputs where applicable.
- Missing optional provider fields degrade explicitly rather than falling back
  to deprecated helper APIs.
- Runtime translators do not accept raw secret material.

### Live Lane

Required evidence:

- Real provider service calls succeed.
- The exact runtime artifact used in the live call is preserved.
- Product failures, provider failures, and infra failures are classified
  separately.
- The lane records concrete resource names and cleanup status.

### Cleanup Lane

Required evidence:

- Direct inventory is used for every billable provider involved.
- Current-run resources are identified by unique run name or prefix.
- Cleanup is verified after tool-level deletion.
- Any intentionally retained external resource is named and justified.

## Failure Classification

Live validation must classify failures before recommending fixes.

| Classification | Meaning |
| --- | --- |
| Product failure | Floe resolver, binding, runtime translation, renderer, or plugin behavior is wrong |
| Provider failure | Cloud or catalog provider rejects auth, permissions, region, endpoint, warehouse, or API usage |
| Infrastructure failure | DevPod, Hetzner, Kind, Flux, network, or provisioning fails before product validation |
| Cleanup failure | Billable or test resources remain after the run |
| Tooling warning | Non-fatal wrapper or tunnel behavior occurs after artifacts and cleanup prove the result |

## Security Requirements

The spike must not weaken existing secret handling.

- `CompiledArtifacts` must not contain raw access keys, secret keys, client
  secrets, OAuth tokens, passwords, or bearer tokens.
- Credentials must be represented as `CredentialRef`, environment variable
  names, workload identity references, or provider-managed identity metadata.
- Live-service logs must be scanned or reviewed for raw credential exposure.
- Provider cleanup commands must not print secret values.
- Any proposed AWS lane must prefer temporary or least-privilege credentials.

## Out Of Scope

- Full AWS S3 storage plugin implementation.
- Full AWS Glue catalog plugin implementation.
- Full Nessie, GCS, Azure, or Hive support.
- Compatibility shims without evidence.
- Removing existing compatibility APIs during the spike design.
- Mutating retired feature worktrees.
- Treating historical plans or specs as current behavior.
- Adding raw secret values to compiled artifacts, generated Helm values, logs,
  or runtime config.

## Recommended Outcome

Proceed with a contract-first provider compatibility spike:

1. Complete the provider matrix against the implemented binding/composition
   model.
2. Classify each gap with the gap taxonomy above.
3. Recommend the first implementation unit.
4. Define the first live validation lane.
5. Use AWS S3 plus AWS Glue as the preferred live target if credentials and
   cleanup guardrails are available.
6. Use Nessie plus MinIO as the fallback live target if AWS access is not
   available or not safe to use for the first proof.

The next step after this spec is an implementation plan for the spike artifacts:
the matrix document, evidence-gathering commands, and live validation runbook.
