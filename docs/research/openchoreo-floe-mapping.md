# Floe to OpenChoreo Mapping

Date: 2026-04-30

## Purpose

Map Floe's data-platform concepts to OpenChoreo resources and identify the ownership boundary for each concept.

## Concept Mapping

| Floe Concept | Current Owner | Candidate OpenChoreo Resource | Proposed Owner After Adoption | Boundary Decision |
| --- | --- | --- | --- | --- |
| Data product metadata from `floe.yaml` | Floe | `Project`, `Component` | Floe source of truth; OpenChoreo generated view | Resolved by the proof task |
| Data product runtime container | Floe charts/runtime image | `Workload` | Floe builds image/artifacts; OpenChoreo may deploy wrapper | Resolved by the proof task |
| Schedule from `floe.yaml` | Floe orchestrator plugin | `Component` type config or `ReleaseBinding` environment config | Floe remains schedule source; OpenChoreo may receive generated config | Resolved by the proof task |
| Environment promotion | Floe OCI/GitOps model | `Environment`, `DeploymentPipeline`, `ReleaseBinding` | Floe defines promotion policy; OpenChoreo may execute release binding | Resolved by the proof task |
| Platform plugins | Floe `manifest.yaml` | No direct equivalent | Floe | Must remain Floe-owned |
| Compiled artifacts | Floe compiler | Artifact consumed by `Workload` | Floe | Must remain Floe-owned |
| dbt and Iceberg semantics | Floe/dbt/Iceberg | No direct equivalent | Floe | Must remain Floe-owned |
| RBAC | Floe governance and K8s plugins | OpenChoreo authz resources | Shared only if no policy weakening | Resolved by the proof task |
| Network policy | Floe network plugin | OpenChoreo gateway/network resources | Shared only if no policy weakening | Resolved by the proof task |
| Secrets | Floe secrets plugin | `SecretReference` | Shared only if references preserve runtime secret resolution | Resolved by the proof task |
| Telemetry | Floe OpenTelemetry | OpenChoreo observability plane | Floe emits signals; OpenChoreo may view signals | Resolved by the proof task |
| Lineage | Floe OpenLineage | No direct replacement | Floe | Must remain Floe-owned |

## Integration Shape Assessment

| Shape | Description | Initial Position | Evidence |
| --- | --- | --- | --- |
| A | OpenChoreo as optional platform control plane around Floe outputs | Preferred candidate | Resolved by the proof task |
| B | OpenChoreo as deployment backend for selected Floe workloads/services | Secondary candidate | Resolved by the proof task |
| C | OpenChoreo as `OrchestratorPlugin` | Negative control | Resolved by the proof task |
