# OpenChoreo and Floe Triage

Date: 2026-04-30

## Recommendation

Status: In progress

Decision options:

- Adopt candidate: OpenChoreo aligns with Floe's architecture and is worth a proof spike.
- Watch candidate: OpenChoreo has promising ideas, but adoption should wait for stability, missing capabilities, or clearer ownership boundaries.
- Reject candidate: OpenChoreo duplicates or conflicts with Floe's platform model enough that adoption is unlikely to simplify Floe.

## Sources Checked

| Source | What It Proves | Notes |
| --- | --- | --- |
| https://github.com/openchoreo/openchoreo | Upstream repository, license, activity, releases, CRD source | Record commit and release data during Task 2 |
| https://openchoreo.dev/docs/ | Published docs and current product positioning | Record relevant concept pages during Task 2 |
| `docs/architecture/ARCHITECTURE-SUMMARY.md` | Floe target architecture and plugin model | Record relevant boundaries during Task 3 |
| `docs/architecture/platform-services.md` | Floe long-lived services and ownership | Record overlap during Task 3 |
| `docs/architecture/interfaces/orchestrator-plugin.md` | Floe orchestration boundary | Used to test whether OpenChoreo fits the orchestrator abstraction |
| `demo/customer-360/floe.yaml` | Representative data-product source | Used for proof mapping |
| `demo/manifest.yaml` | Representative platform manifest | Used for physical architecture and plugin ownership |

## OpenChoreo Snapshot

| Dimension | Evidence | Assessment |
| --- | --- | --- |
| Release maturity | Latest observed release line is `v1.0.1-hotfix.1`; `v1.0.0` was released on 2026-03-22; repository uses Apache-2.0. | Mature enough for a proof spike, but CRDs remain `v1alpha1`, so adoption needs API-stability caution. |
| CRD/resource model | Source includes CRDs for `Project`, `Component`, `Workload`, `ComponentType`, `ClusterComponentType`, `Trait`, `ClusterTrait`, `Environment`, `DataPlane`, `WorkflowPlane`, `Workflow`, `ClusterWorkflow`, `WorkflowRun`, `ReleaseBinding`, `RenderedRelease`, authz, observability, and secret references. | Rich enough to model platform/developer abstractions around Floe outputs. |
| Control plane/runtime model | Install tree separates control, data, workflow, and observability planes. | Strong conceptual alignment with Floe's platform-services layer, with added operational footprint. |
| Developer portal/API | README and docs position OpenChoreo as a Kubernetes internal developer platform with CLI/API/UI concepts. | Potential DX value if Floe can generate OpenChoreo resources instead of exposing CRDs directly. |
| Workflow support | Workflow plane chart depends on Argo Workflows; samples include workflow and workflow-run resources. | Useful for build/release workflows, but not a direct dbt/Dagster orchestration replacement. |
| Observability support | Observability plane chart includes logs, metrics, tracing, observer APIs, and authz integration. | Possible platform observability surface, but Floe must retain OpenTelemetry and OpenLineage emission ownership. |
| Authz/secrets support | CRDs and samples include authz roles/bindings and `SecretReference`. | Potential overlap with Floe's identity/secrets/RBAC plugins; requires strict boundary definition. |
| Install footprint | Local guide uses k3d plus multiple charts and prerequisites such as cert-manager, external-secrets, gateway components, Thunder, workflow plane, and observability plane. | Adoption complexity is non-trivial; proof should start with CRD/render validation before full runtime validation. |

## Floe Fit Assessment

| Dimension | Alignment | Conflict | Decision Impact |
| --- | --- | --- | --- |
| Four-layer architecture |  |  |  |
| Downward-only configuration flow |  |  |  |
| Plugin architecture |  |  |  |
| CompiledArtifacts contract |  |  |  |
| Dagster/Airflow orchestrator boundary |  |  |  |
| Helm/GitOps deployment path |  |  |  |
| RBAC and network policy |  |  |  |
| Secrets and identity |  |  |  |
| OpenTelemetry and OpenLineage |  |  |  |

## Scoring

Use this scale:

- 2: strong alignment or simplification
- 1: partial alignment with manageable work
- 0: neutral or unclear value
- -1: overlap that increases complexity
- -2: architectural conflict

| Category | Score | Evidence |
| --- | ---: | --- |
| Developer experience | 0 | Collected in Task 2 or Task 3 |
| Platform simplification | 0 | Collected in Task 2 or Task 3 |
| Architecture boundary fit | 0 | Collected in Task 2 or Task 3 |
| Adoption complexity | 0 | Collected in Task 2 or Task 3 |
| Operational maturity | 0 | Collected in Task 2 or Task 3 |
| Release roadmap value | 0 | Collected in Task 2 or Task 3 |

## Gate Decision

Decision: In progress

Confidence: In progress

Next action: Complete Tasks 2 and 3 before assigning the gate decision.
