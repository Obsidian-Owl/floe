# OpenChoreo and Floe Triage

Date: 2026-04-30

## Recommendation

Status: Gate complete; bounded proof spike recommended

Decision options:

- Adopt candidate: OpenChoreo aligns with Floe's architecture and is worth a proof spike.
- Watch candidate: OpenChoreo has promising ideas, but adoption should wait for stability, missing capabilities, or clearer ownership boundaries.
- Reject candidate: OpenChoreo duplicates or conflicts with Floe's platform model enough that adoption is unlikely to simplify Floe.

## Sources Checked

| Source | What It Proves | Notes |
| --- | --- | --- |
| https://github.com/openchoreo/openchoreo | Upstream repository, license, activity, releases, CRD source | Task 2 cloned `release-v1.0` at `1a516d5f52c25b3c91a7e48ed55c2173e8edc070` and captured GitHub release/repository API metadata. |
| OpenChoreo source-tree README, docs, install guides, and samples at `release-v1.0` (`1a516d5f52c25b3c91a7e48ed55c2173e8edc070`) | Version-pinned product positioning, resource model, templating model, install surface, and sample resources | Task 2 inspected the pinned source tree rather than treating live published docs as evidence. |
| `docs/architecture/ARCHITECTURE-SUMMARY.md` | Floe target architecture and plugin model | Used to anchor the four-layer model, downward-only configuration flow, and plugin boundary assessment. |
| `docs/architecture/platform-services.md` | Floe long-lived services and ownership | Used to compare OpenChoreo planes against Floe's existing service, Helm, GitOps, RBAC, network, and observability responsibilities. |
| `docs/contracts/compiled-artifacts.md` | Floe cross-package artifact handoff | Used to confirm `CompiledArtifacts` must remain the source-of-truth contract consumed by downstream systems. |
| `docs/architecture/plugin-system/index.md` | Floe plugin model and enforced/pluggable extension boundaries | Used to test whether OpenChoreo fits an existing plugin category or should remain an optional platform-control integration. |
| `docs/architecture/opinionation-boundaries.md` | Floe technology ownership boundaries | Used to confirm dbt, Iceberg, OpenTelemetry, OpenLineage, and governance ownership should remain Floe-owned. |
| `docs/architecture/interfaces/orchestrator-plugin.md` | Floe orchestration boundary | Used to test whether OpenChoreo fits the orchestrator abstraction. |
| `demo/customer-360/floe.yaml` | Representative data-product source | Used for proof mapping. |
| `demo/manifest.yaml` | Representative platform manifest | Used for physical architecture and plugin ownership. |

## OpenChoreo Snapshot

| Dimension | Evidence | Assessment |
| --- | --- | --- |
| Release maturity | Task 2 GitHub API snapshot observed latest release line `v1.0.1-hotfix.1` published 2026-04-16 and `v1.0.0` published 2026-03-22; repository default branch is `main`, license is Apache-2.0, `pushed_at` was 2026-04-29T11:42:27Z, `updated_at` was 2026-04-29T21:58:38Z, with 807 stars, 142 forks, and 192 open issues. The inspected `release-v1.0` source commit was `1a516d5f52c25b3c91a7e48ed55c2173e8edc070`. | Mature enough for a proof spike, but CRDs remain `v1alpha1`, so adoption needs API-stability caution. |
| CRD/resource model | Source includes CRDs/API types for `Project`, `Component`, `Workload`, `ComponentRelease`, `ReleaseBinding`, `RenderedRelease`, `ComponentType`, `ClusterComponentType`, `Trait`, `ClusterTrait`, `Workflow`, `ClusterWorkflow`, `WorkflowRun`, `DeploymentPipeline`, `Environment`, `DataPlane`, `ClusterDataPlane`, `WorkflowPlane`, `ClusterWorkflowPlane`, `ObservabilityPlane`, `ClusterObservabilityPlane`, `ObservabilityAlertRule`, `ObservabilityAlertsNotificationChannel`, `SecretReference`, `AuthzRole`, `AuthzRoleBinding`, `ClusterAuthzRole`, and `ClusterAuthzRoleBinding`. | Rich enough to model platform/developer abstractions around Floe outputs. |
| Control plane/runtime model | Install tree separates control, data, workflow, and observability planes. | Strong conceptual alignment with Floe's platform-services layer, with added operational footprint. |
| Developer/runtime concepts | README and docs position OpenChoreo around project/cell boundaries, components, workloads, endpoints, connections/dependencies, component types, traits, workflows, component releases, release bindings, rendered releases, CEL-based templating, validation/patching, and sample categories for platform configuration, deploy-from-source, and deploy-from-image. | Potential DX value if Floe can generate OpenChoreo resources instead of exposing CRDs directly. |
| Workflow support | Workflow plane chart depends on Argo Workflows; samples include workflow and workflow-run resources. | Useful for build/release workflows, but not a direct dbt/Dagster orchestration replacement. |
| Observability support | Observability plane chart includes logs, metrics, tracing, observer APIs, and authz integration. | Possible platform observability surface, but Floe must retain OpenTelemetry and OpenLineage emission ownership. |
| Authz/secrets support | CRDs and samples include authz roles/bindings and `SecretReference`. | Potential overlap with Floe's identity/secrets/RBAC plugins; requires strict boundary definition. |
| Install footprint | Task 6 local render validation found all requested tools present (`kubectl`, `helm`, `k3d`, `docker`) and verified `release-v1.0` at `1a516d5f52c25b3c91a7e48ed55c2173e8edc070`. Helm dependencies built for control-plane, data-plane, and observability-plane, but workflow-plane failed with `no repository definition for https://argoproj.github.io/argo-helm`. Control, data, and observability renders produced 3,660 total manifest lines; workflow-plane rendered 0 lines because `argo-workflows` was missing. Dominant rendered kinds included 10 `ClusterAuthzRole`, 9 `ClusterAuthzRoleBinding`, 8 `Deployment`, 8 `ServiceAccount`, 7 `ClusterRole`, and 7 `ClusterRoleBinding`. | Adoption complexity is non-trivial; proof should continue with generated-resource validation before any full runtime validation. |

## Floe Fit Assessment

| Dimension | Alignment | Conflict | Decision Impact |
| --- | --- | --- | --- |
| Four-layer architecture | OpenChoreo's control/data/workflow/observability planes could sit around Floe Layer 3 services and Layer 4 workloads. | OpenChoreo is itself a broad control plane, which could blur Floe's Layer 2 configuration and Layer 3 service boundaries. | Fit is plausible only if OpenChoreo consumes Floe outputs instead of becoming the source of data-platform truth. |
| Downward-only configuration flow | OpenChoreo `Project`, `Component`, `Workload`, and `ReleaseBinding` can be generated from Floe data and promotion artifacts. | OpenChoreo environment configs could tempt environment-specific fields back into `floe.yaml`. | Adoption must preserve `manifest.yaml` and `floe.yaml` environment-agnostic rules. |
| Plugin architecture | OpenChoreo can wrap selected deployment/runtime concerns without replacing plugin contracts. | OpenChoreo does not map cleanly to Floe's 11 plugin categories. | Treat it as optional platform-control integration, not as another standard plugin category without further design. |
| CompiledArtifacts contract | OpenChoreo can deploy a workload that consumes `compiled_artifacts.json`. | Any requirement to change `CompiledArtifacts` for OpenChoreo would be high risk. | `CompiledArtifacts` remains the source-of-truth handoff. |
| Dagster/Airflow orchestrator boundary | OpenChoreo workflows can support build/release activity around orchestrators. | It is not a direct replacement for Dagster/Airflow asset scheduling and dbt runtime semantics. | Do not model OpenChoreo as the initial `OrchestratorPlugin`. |
| Helm/GitOps deployment path | OpenChoreo could reduce bespoke app-lifecycle glue if it owns generated runtime resources. | Floe already has Helm/GitOps assets; adding OpenChoreo may duplicate the deployment path. | Proof must identify real simplification before adoption. |
| RBAC and network policy | OpenChoreo has authz and gateway/network concepts that may align with platform controls. | Floe's RBAC and network plugins enforce data-platform governance; overlap may weaken auditability. | Boundary must be explicit and default to Floe ownership. |
| Secrets and identity | OpenChoreo `SecretReference` could interoperate with external-secrets patterns. | Floe secrets and identity plugins already model credential ownership and runtime resolution. | Treat OpenChoreo secrets as a deployment adapter only if it preserves Floe references. |
| OpenTelemetry and OpenLineage | OpenChoreo observability can potentially present signals emitted by Floe workloads. | OpenChoreo observability does not replace Floe's enforced OpenTelemetry and OpenLineage contracts. | OpenChoreo may be a viewer/control surface, not the signal owner. |

## Scoring

Use this scale:

- 2: strong alignment or simplification
- 1: partial alignment with manageable work
- 0: neutral or unclear value
- -1: overlap that increases complexity
- -2: architectural conflict

| Category | Score | Evidence |
| --- | ---: | --- |
| Developer experience | 1 | OpenChoreo offers project/component/environment abstractions and a portal/API surface, but Floe must generate these resources so data engineers stay in Floe UX. |
| Platform simplification | 0 | OpenChoreo may simplify deployment lifecycle, authz, observability, and release binding, but Floe already owns Helm/GitOps/RBAC/network paths. A proof is required. |
| Architecture boundary fit | 1 | OpenChoreo fits better as an optional platform-control layer than as an orchestrator plugin; this preserves Floe's data contracts. |
| Adoption complexity | -1 | Multi-plane install, `v1alpha1` CRDs, external prerequisites, overlapping platform controls, a missing Argo Helm repository dependency for workflow-plane rendering, and 3,660 rendered lines across the three successful plane templates increase operational complexity. |
| Operational maturity | 0 | `v1.0.x` releases are promising, but current CRDs remain alpha-versioned and the open issue count requires caution. |
| Release roadmap value | 1 | If proof validates generated resources and clear boundaries, OpenChoreo could become a future optional integration for platform teams. |

## Gate Decision

Decision: Adopt candidate for a bounded proof spike.

Confidence: Medium-low.

Reasoning:

OpenChoreo has plausible architectural alignment as an optional platform-control layer around Floe, especially for project/component/environment abstractions, release binding, workflow-plane integration, and platform observability. It should not replace Floe's data semantics, plugin contracts, dbt/Iceberg/OpenLineage ownership, or the existing orchestrator interface.

The proof spike is justified because the largest unresolved question is practical complexity: whether OpenChoreo can reduce Floe-owned Kubernetes lifecycle glue without adding a parallel platform that keeps all current Floe responsibilities intact.

Next action: Run Phase 2 against `demo/customer-360` and validate generated OpenChoreo resource shape, render behavior, install footprint, and ownership boundaries.
