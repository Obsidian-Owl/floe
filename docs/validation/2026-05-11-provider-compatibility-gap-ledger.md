# Provider Compatibility Gap Ledger

Date: 2026-05-11
Repo: `/Users/dmccarthy/Projects/floe`
Purpose: Classify provider compatibility gaps before implementation.

## Gap Categories

| Category | Meaning |
| --- | --- |
| No change | Current model already expresses the provider path |
| Capability-only gap | Resolver needs another compatibility dimension |
| Typed binding gap | Current bindings cannot carry required secret-free state |
| Provider plugin gap | Model is sufficient, but provider plugin does not exist |
| Runtime translator gap | Binding exists, but runtime library translation is missing |
| Renderer gap | Deployment output cannot be generated from bindings yet |
| Live validation gap | Real service proof is missing |
| Out of scope | Provider path lacks a concrete composition trigger |

## Gaps

| Gap | Provider path | Category | Evidence | Recommended next action |
| --- | --- | --- | --- | --- |
| Native AWS S3 storage provider absent | AWS S3 + Glue; AWS S3 + Nessie | Provider plugin gap | Entry point inventory has no `floe-storage-aws-s3` plugin | Design native S3 storage plugin after matrix approval |
| AWS credential and identity modes need proof against resolver | AWS S3 + Glue; AWS S3 + Nessie | Capability-only gap | Current composition model includes credential and identity modes but AWS provider declarations do not exist | Define AWS provider requirements and resolver tests in the first implementation unit |
| Glue catalog binding absent | AWS S3 + Glue | Provider plugin gap | Entry point inventory has no Glue catalog plugin; implementation design must also decide whether Glue needs a provider-owned typed binding | Design Glue catalog provider and binding before implementation |
| PyIceberg Glue translation not proven from `RuntimeCatalogConnection` | AWS S3 + Glue | Runtime translator gap | Current runtime translator handles generic URI/warehouse/S3 properties, not proven Glue catalog properties | Add translator proof or a Glue-specific runtime projection in a follow-up spec |
| Nessie catalog provider absent | MinIO + Nessie; AWS S3 + Nessie | Provider plugin gap | Entry point inventory has no Nessie catalog plugin; implementation design must also decide the Nessie catalog binding shape | Design Nessie catalog provider and binding if selected as fallback live proof |
| GCS and Azure credential/endpoint models are unproven | GCS; Azure | Capability-only gap | No current provider plugin or runtime translation evidence; use these as pressure tests for future binding fields | Keep as design pressure tests, not first implementation |
| Hive lacks concrete alpha path | Hive | Out of scope | No current deployment trigger in the approved spike | Defer until a product path exists |

## Compatibility Helper Decision

Do not use deprecated helper APIs as new provider contracts. New provider work must flow through capabilities, requirements, typed bindings, resolver validation, and runtime/renderer translators.

## Secret-Free Decision

Provider compatibility is invalid if it requires literal credential values,
tokens, client secrets, passwords, or bearer tokens inside `CompiledArtifacts`.

## First Follow-Up Recommendation

Recommend one implementation unit and one live validation lane based on the matrix:

- Primary path: AWS S3 plus AWS Glue provider compatibility design if AWS credentials and cleanup controls are available.
- Fallback path: Nessie plus MinIO provider compatibility design if AWS access is unavailable.
