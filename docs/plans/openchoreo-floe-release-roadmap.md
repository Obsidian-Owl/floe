# OpenChoreo Floe Release Roadmap

Date: 2026-04-30

## Recommendation

Treat OpenChoreo as a future optional platform-control integration for Floe, not as a replacement for Floe's compiler, plugin system, data contracts, dbt/Iceberg semantics, OpenTelemetry, OpenLineage, or orchestrator plugins.

## Adoption Thesis

The long-term value of OpenChoreo is net removal or simplification of Floe-owned platform lifecycle glue while preserving Floe's data-platform vision. Adoption is only justified if OpenChoreo lets Floe stop owning selected Kubernetes application-lifecycle concerns, not if it adds a second platform control plane beside existing Helm, GitOps, RBAC, network, secrets, observability, and CI glue.

Floe should continue to own:

- Data semantics in `floe.yaml`.
- Platform selection and governance in `manifest.yaml`.
- `CompiledArtifacts` and generated runtime contracts.
- dbt, Iceberg, OpenTelemetry emission, OpenLineage emission, and policy enforcement.

OpenChoreo may become valuable where it can own or standardize generated platform-control surfaces:

- Project, component, workload, environment, release, and workflow lifecycle.
- Authz, secret-reference, and gateway-facing deployment adapters.
- Platform observability presentation around signals emitted by Floe workloads.

## Glue Removal Ledger

Track adoption against concrete deletion or simplification targets. A future implementation plan should update this ledger with measured file, command, and operational changes before recommending anything beyond an experimental generator.

| Floe-Owned Surface | Current Role | OpenChoreo Replacement Hypothesis | Required Proof | Target Outcome |
| --- | --- | --- | --- | --- |
| `charts/floe-jobs` | Generic Job/CronJob wrapper for data-product runtimes. | Generated `Component`, `Workload`, and `ReleaseBinding` resources can replace selected job chart wrappers for OpenChoreo-enabled deployments. | Customer 360 resources validate against installed OpenChoreo CRDs and run against compiled Floe artifacts. | Shrink or remove the OpenChoreo-enabled path through `charts/floe-jobs`; keep the default non-OpenChoreo path. |
| `charts/floe-platform` service lifecycle templates | Owns long-lived platform service deployments, values, tests, hooks, RBAC, network policy, and secrets wiring. | OpenChoreo can own selected platform application lifecycle concerns while Floe keeps service-specific configuration and data-platform contracts. | A real cluster proof shows OpenChoreo deployment lifecycle replaces a named subset of Helm templates without weakening governance. | Delete or simplify the named Helm template/value/test subset that OpenChoreo replaces. |
| Flux/GitOps examples and deployment bootstrap | Demonstrates promotion and reconciliation paths for platform and job charts. | OpenChoreo `Environment`, `DeploymentPipeline`, and `ReleaseBinding` resources can absorb some release/promotion glue. | A promotion proof shows generated release bindings preserve Floe OCI/GitOps provenance and rollback expectations. | Reduce duplicate Flux-specific examples for OpenChoreo users; keep core OCI/GitOps concepts where still required. |
| RBAC and network deployment glue | Generates Kubernetes access and traffic controls from Floe governance. | OpenChoreo authz and gateway/network resources can become generated adapters from Floe policy. | Contract tests prove no policy weakening and no environment-specific policy moves into `floe.yaml`. | Keep Floe policy source; delete or reduce only deployment adapter code that OpenChoreo fully replaces. |
| Secrets deployment glue | Maps Floe secret references to runtime Kubernetes/external secret surfaces. | OpenChoreo `SecretReference` can be emitted from Floe secret references without exposing raw values. | Tests prove generated resources contain references only and work with the selected secret backend. | Keep Floe secret ownership; simplify deployment-specific secret manifests for OpenChoreo-enabled paths. |
| CI and diagnostics around platform lifecycle | Validates Helm rendering, cluster setup, service readiness, and failure diagnostics. | Some Helm-focused checks can move to OpenChoreo CRD/render/server validation for the optional path. | CI has a dedicated OpenChoreo validation lane with useful diagnostics and a stable local reproduction path. | Reduce duplicated Helm lifecycle checks for OpenChoreo-enabled deployments, not the default path. |

## Release Slice 1: Research Preview

Goal: Publish the integration boundary and generated-resource proof as documentation.

Scope:

- Document Floe-to-OpenChoreo ownership boundaries.
- Document generated resource examples for Customer 360.
- Document install-footprint and operational risks.
- Publish the glue-removal ledger as the measurable adoption thesis.
- Keep OpenChoreo out of the default Floe runtime path.

Exit criteria:

- Platform teams can understand where OpenChoreo fits.
- Data engineers do not need to learn OpenChoreo CRDs.
- No Floe runtime behavior changes.
- The next implementation plan has explicit deletion or simplification targets.

## Release Slice 2: Experimental Generator

Goal: Add an opt-in generator that emits OpenChoreo resources from Floe artifacts and proves whether generated intent can replace a named slice of Floe-owned lifecycle glue.

Candidate scope:

- Add a command or plugin-owned utility that reads `floe.yaml` and `CompiledArtifacts`.
- Emit `Project`, `Component`, `Workload`, `SecretReference`, and `ReleaseBinding` YAML.
- Add contract tests proving no raw secrets and no environment-specific fields enter `floe.yaml`.
- Add a deletion-impact report showing which Floe chart, GitOps, RBAC, network, secrets, or CI files become unnecessary for OpenChoreo-enabled deployments.
- Add docs for platform teams using OpenChoreo.

Exit criteria:

- Generated resources validate against OpenChoreo CRDs.
- Floe remains source of truth for data semantics.
- OpenChoreo integration is disabled by default.
- The generator identifies at least one concrete lifecycle surface that can be removed or materially simplified if Release Slice 3 succeeds.

## Release Slice 3: Platform-Control Integration

Goal: Validate OpenChoreo as a platform-control option in a real K8s test environment and remove or simplify the lifecycle glue proven redundant by the generator slice.

Candidate scope:

- Add an integration test path for OpenChoreo CRD server-side validation.
- Replace or simplify a named subset of Floe Helm/GitOps deployment glue for OpenChoreo-enabled deployments.
- Evaluate observability surface integration without replacing Floe telemetry or lineage emission.
- Evaluate authz, network, and secret adapters against Floe governance.
- Update CI and diagnostics so OpenChoreo-enabled deployments are validated through OpenChoreo resource acceptance and runtime behavior, not duplicate Helm lifecycle checks.

Exit criteria:

- OpenChoreo removes or materially simplifies at least one Floe-owned platform lifecycle responsibility named in the glue-removal ledger.
- The PR includes a before/after maintenance delta: files removed, files simplified, validation commands changed, and responsibilities moved to OpenChoreo.
- No default Floe deployment behavior changes for users who do not opt in.
- Operational footprint and upgrade path are documented.
- ADR is accepted before GA commitment.

## Non-Adoption Boundary

Do not make OpenChoreo mandatory unless a future proof shows it substantially simplifies platform operations for teams that choose it. The default Floe experience should remain usable without OpenChoreo.
