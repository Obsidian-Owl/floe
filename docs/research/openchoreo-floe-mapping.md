# Floe to OpenChoreo Mapping

Date: 2026-04-30

## Purpose

Map Floe's data-platform concepts to OpenChoreo resources and identify the ownership boundary for each concept.

## Concept Mapping

| Floe Concept | Current Owner | Candidate OpenChoreo Resource | Proposed Owner After Adoption | Boundary Decision |
| --- | --- | --- | --- | --- |
| Data product metadata from `floe.yaml` | Floe | `Project`, `Component` | Floe source of truth; OpenChoreo generated view | Generate OpenChoreo resources from Floe metadata. |
| Data product runtime container | Floe charts/runtime image | `Workload` | Floe builds image/artifacts; OpenChoreo may deploy wrapper | OpenChoreo can wrap the container only after Floe compilation and image build. |
| Schedule from `floe.yaml` | Floe orchestrator plugin | Component type config or `ReleaseBinding` environment config | Floe remains schedule source; OpenChoreo receives generated config | Schedule must originate in Floe and remain environment-agnostic unless promotion config overrides it. |
| Environment promotion | Floe OCI/GitOps model | `Environment`, `DeploymentPipeline`, `ReleaseBinding` | Floe defines promotion policy; OpenChoreo may execute release binding | Candidate for simplification if ReleaseBinding can consume Floe artifacts cleanly. |
| Platform plugins | Floe `manifest.yaml` | No direct equivalent | Floe | Must remain Floe-owned. |
| Compiled artifacts | Floe compiler | Artifact consumed by `Workload` | Floe | Must remain Floe-owned. |
| dbt and Iceberg semantics | Floe/dbt/Iceberg | No direct equivalent | Floe | Must remain Floe-owned. |
| RBAC | Floe governance and K8s plugins | OpenChoreo authz resources | Floe policy source; OpenChoreo adapter possible | Candidate adapter only if generated from Floe governance and audited. |
| Network policy | Floe network plugin | OpenChoreo gateway/network resources | Floe policy source; OpenChoreo adapter possible | Candidate adapter only if generated from Floe governance and audited. |
| Secrets | Floe secrets plugin | `SecretReference` | Floe secret reference source; OpenChoreo deployment adapter possible | Candidate adapter only if no raw secrets enter generated resources. |
| Telemetry | Floe OpenTelemetry | OpenChoreo observability plane | Floe emits signals; OpenChoreo may view signals | OpenChoreo can be a surface, not the signal owner. |
| Lineage | Floe OpenLineage | No direct replacement | Floe | Must remain Floe-owned. |

## Integration Shape Assessment

| Shape | Description | Position | Evidence |
| --- | --- | --- | --- |
| A | OpenChoreo as optional platform control plane around Floe outputs | Preferred proof target | Preserves Floe's data semantics and lets OpenChoreo own project/component/release surfaces. |
| B | OpenChoreo as deployment backend for selected Floe workloads/services | Secondary future target | Could reduce Helm/GitOps glue, but requires stronger proof of operational value. |
| C | OpenChoreo as `OrchestratorPlugin` | Rejected as initial approach | OpenChoreo is a broad platform control plane; Floe's orchestrator interface expects workflow engines such as Dagster, Airflow, or Prefect. |

## Generated Resource Strategy

The first useful integration slice would generate OpenChoreo intent resources from Floe inputs:

1. Read `floe.yaml` and `CompiledArtifacts`.
2. Emit a `Project` for the data product domain or product grouping.
3. Emit a `Component` for each deployable Floe runtime unit.
4. Emit a `Workload` pointing to the Floe runtime image and compiled artifact path.
5. Emit a `ReleaseBinding` per promoted environment from Floe promotion data.
6. Emit `SecretReference` resources only when the source is a Floe `SecretReference` or plugin-owned secret reference, never from raw secret values.

Data engineers should continue editing Floe files. Platform engineers may inspect or approve generated OpenChoreo resources.

## Customer 360 Proof Mapping

Source Floe product: `demo/customer-360/floe.yaml`

Generated OpenChoreo resources:

| Resource | Source Fields | Purpose | Boundary |
| --- | --- | --- | --- |
| `Project/customer-360` | `metadata.name`, `metadata.description`, `metadata.labels` | Groups the data product in OpenChoreo UX. | Generated view of Floe metadata. |
| `Component/customer-360` | Product name, schedule/resource intent | Represents the deployable scheduled data-product runtime. | Generated wrapper around Floe runtime. |
| `Workload/customer-360-workload` | Runtime image and compiled artifact paths | Points OpenChoreo at the Floe runtime unit. | Floe owns image and artifact contract. |
| `SecretReference/customer-360-runtime-secrets` | Secret reference names only | Demonstrates possible external-secret adapter shape. | No raw secrets allowed. |
| `ReleaseBinding/customer-360-development` | Schedule and environment binding | Demonstrates promotion/deployment binding outside `floe.yaml`. | Environment binding remains outside data engineer config. |

Proof finding:

The mapping is feasible as a generated-resource strategy if OpenChoreo accepts this resource shape after CRD validation. It does not require changing Floe's data contracts or `CompiledArtifacts`.
