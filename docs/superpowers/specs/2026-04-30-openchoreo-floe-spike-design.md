# OpenChoreo Fit and Adoption Spike Design

Date: 2026-04-30

Status: Approved for planning

## Purpose

Assess whether OpenChoreo should be considered for a future Floe release, and if so, define a bounded tech spike that can validate architectural fit, developer experience improvements, adoption complexity, and roadmap impact.

This is a gated design. It does not assume adoption. The first output is a recommendation. A runnable proof only follows if the recommendation finds plausible architectural alignment.

## Source Context

Floe is currently designed as an internal data platform with a four-layer architecture:

1. Foundation: Python packages, plugin interfaces, Helm/chart assets.
2. Configuration: immutable platform artifacts and manifests.
3. Services: long-lived Kubernetes services such as Dagster, Polaris, Cube, telemetry, lineage, storage, secrets, identity, RBAC, and network controls.
4. Data: ephemeral jobs and data-product workloads driven by `floe.yaml` and compiled artifacts.

Floe's critical contracts remain `manifest.yaml`, `floe.yaml`, `CompiledArtifacts`, the plugin interfaces, dbt, Iceberg, OpenTelemetry, OpenLineage, and compile-time governance.

OpenChoreo is an Apache-2.0 Kubernetes internal developer platform. Current upstream signals checked during scoping:

- Repository: https://github.com/openchoreo/openchoreo
- Documentation: https://openchoreo.dev/docs/
- Quick start: https://openchoreo.dev/docs/getting-started/quick-start-guide/
- Concepts: https://openchoreo.dev/docs/concepts/developer-abstractions/
- Runtime model: https://openchoreo.dev/docs/concepts/runtime-model/
- Latest observed release line during scoping: `v1.0.1-hotfix.1`, published 2026-04-16, with `v1.0.0` released 2026-03-22.

OpenChoreo's visible integration surface is a Kubernetes control plane with CRDs and APIs for projects, components, workloads, component types, traits, environments, data planes, workflow planes, workflows, workflow runs, release bindings, observability, authz, and secret references.

## Recommendation Gate

The first phase produces one of three recommendations:

- Adopt candidate: OpenChoreo aligns with Floe's architecture and is worth a proof spike.
- Watch candidate: OpenChoreo has promising ideas, but adoption should wait for stability, missing capabilities, or clearer ownership boundaries.
- Reject candidate: OpenChoreo duplicates or conflicts with Floe's platform model enough that adoption is unlikely to simplify Floe.

The recommendation must be explicit about confidence, evidence, unknowns, and the next action.

## Working Hypotheses

H1: OpenChoreo can improve Floe's developer experience by exposing higher-level project, component, environment, workflow, and observability abstractions around Floe data products.

H2: OpenChoreo can simplify Floe's physical architecture by taking ownership of some Kubernetes lifecycle concerns that Floe currently handles through Helm, GitOps examples, RBAC generation, network policy generation, and deployment glue.

H3: Floe should keep ownership of data-specific semantics: platform/data-product configuration, plugin selection, compiled artifact contracts, dbt compilation, Iceberg tables, OpenLineage events, quality gates, and governance enforcement.

H4: OpenChoreo is not a direct replacement for Floe's `OrchestratorPlugin`. It is closer to a platform/developer-experience control plane. A viable integration point is likely a deployment or platform-control layer around Floe rather than a Dagster/Airflow substitute.

H5: Adoption is only valuable if a Floe data product can be represented in OpenChoreo without breaking Floe's downward-only configuration flow or forcing data engineers to work directly with low-level OpenChoreo CRDs.

## Non-Goals

- Do not replace dbt, Iceberg, OpenLineage, OpenTelemetry, or Floe's compiled artifact contract.
- Do not redesign Floe's plugin system during the spike.
- Do not migrate existing Floe charts or runtime services unless the proof shows a concrete simplification.
- Do not accept OpenChoreo as a new mandatory dependency without proving developer and platform-operator value.
- Do not treat a successful local install as sufficient evidence for adoption.

## Approach

### Phase 1: Triage and Recommendation

Research OpenChoreo against Floe's target architecture and classify fit across these dimensions:

- Domain fit: platform control plane, developer portal, deployment lifecycle, workflow execution, observability, authz, and secrets.
- Boundary fit: what OpenChoreo should own, what Floe must continue to own, and where contracts would cross.
- Physical architecture fit: CRDs, controllers, runtime planes, Helm/GitOps compatibility, namespace and environment model, RBAC, network policies, and secret references.
- Developer experience fit: whether a data engineer can stay in `floe.yaml` and Floe commands while gaining a clearer portal/API experience.
- Operational fit: install footprint, dependencies, failure modes, upgrade model, security posture, and compatibility with Floe's K8s-native test strategy.
- Maturity fit: release cadence, version stability, API stability, documentation quality, active issues, and likely roadmap risk.

### Phase 2: Hypothesis-Driven Tech Spike

If Phase 1 recommends an adopt candidate, run a bounded proof focused on mapping a Floe data product to OpenChoreo resources.

The proof should attempt to model:

- A Floe data product as an OpenChoreo `Project` plus one or more `Component` resources.
- A compiled Floe product runtime as an OpenChoreo `Workload` or generated component release artifact.
- Floe environment promotion as OpenChoreo environment and release binding concepts, without placing environment-specific details in `floe.yaml`.
- Floe secrets as OpenChoreo `SecretReference` or as an explicitly rejected overlap if it weakens Floe's secret model.
- Floe operational surfaces through OpenChoreo observability APIs only if they can preserve OpenTelemetry and OpenLineage ownership.

The proof should use the smallest local setup that can validate CRD shape, generated resources, and operator workflow. A full production-grade deployment is out of scope.

### Phase 3: Roadmap and ADR Evidence

If the proof validates the hypotheses, produce release-planning evidence:

- Recommended adoption pattern.
- Required Floe package/plugin/interface changes.
- Required charts/GitOps changes.
- Required docs and UX changes.
- Migration story for existing Floe users.
- ADR candidates with decision scope and evidence.
- Release roadmap slices, with the first releasable increment clearly separated from later portal/control-plane work.

## Candidate Integration Shapes

### Shape A: OpenChoreo as Optional Platform Control Plane

Floe compiles data-product and platform artifacts. An optional OpenChoreo integration emits or applies OpenChoreo resources that wrap the runtime workload and release lifecycle.

This is the preferred initial shape to test because it preserves Floe's data semantics and lets OpenChoreo own developer-platform concerns.

### Shape B: OpenChoreo as Deployment Backend

Floe's deployment path targets OpenChoreo resources instead of direct Helm/GitOps resources for some workloads or services. This could reduce Floe-owned Kubernetes glue, but it has higher coupling to OpenChoreo CRDs and controllers.

This should only be considered if Shape A proves too shallow to deliver value.

### Shape C: OpenChoreo as Orchestrator Plugin

OpenChoreo is treated as a Floe `OrchestratorPlugin`.

This is unlikely to be the right abstraction because OpenChoreo is a broader platform control plane, while Floe's orchestrator interface expects workflow engines such as Dagster, Airflow, or Prefect. Keep this as a negative control during assessment.

## Evidence Matrix

| Hypothesis | Evidence Required | Failure Signal |
| --- | --- | --- |
| H1: Better developer experience | Clear mapping from `floe.yaml` to OpenChoreo project/component UX, with less user-facing K8s detail | Data engineers must author OpenChoreo CRDs manually |
| H2: Simpler physical architecture | Identified Floe-owned deployment/RBAC/network/observability glue that OpenChoreo can own without loss | OpenChoreo adds a parallel control plane while Floe keeps all existing glue |
| H3: Floe keeps data semantics | Floe contracts remain the source of truth; OpenChoreo consumes outputs | OpenChoreo requires changing `CompiledArtifacts`, dbt, Iceberg, or governance ownership |
| H4: Correct integration boundary | Adoption path lands outside `OrchestratorPlugin` or only extends it intentionally | OpenChoreo must impersonate Dagster/Airflow semantics |
| H5: Downward config flow preserved | Environment/runtime state enters through existing Floe environment and promotion patterns | Layer 4 workloads modify Layer 2 configuration or `floe.yaml` gains environment credentials |

## Validation Work

The eventual implementation plan should include these work items:

1. Research and score OpenChoreo fit against Floe architecture.
2. Build a small mapping document from Floe concepts to OpenChoreo CRDs.
3. Install or dry-render OpenChoreo locally using upstream quickstart or Helm assets.
4. Generate a minimal OpenChoreo resource set for a representative Floe data product.
5. Validate apply/render behavior in a local Kubernetes cluster if the install footprint is reasonable.
6. Record adoption complexity, blockers, and simplification opportunities.
7. Produce recommendation, roadmap outline, and ADR candidate list.

## Risks

- OpenChoreo may overlap with Floe's existing Helm/GitOps, RBAC, network policy, secret, and observability work without actually reducing Floe complexity.
- OpenChoreo's CRDs may force environment-specific modeling that conflicts with Floe's environment-agnostic `manifest.yaml` and `floe.yaml` rules.
- OpenChoreo may improve application developer workflows more than data-product workflows.
- A local proof may understate production concerns around identity, tenancy, upgrade safety, and multi-cluster operation.
- Adopting a broad control plane can create a larger operational dependency than the value justifies.

## Success Criteria

The spike is successful if it can answer these questions with evidence:

- Should Floe adopt, watch, or reject OpenChoreo for a future release?
- If adoption is recommended, what exact responsibility should OpenChoreo own?
- Which Floe responsibilities become simpler or disappear?
- Which Floe responsibilities must remain unchanged?
- What is the smallest releasable integration slice?
- What ADRs are needed before implementation?

## Deliverables

- `docs/research/openchoreo-floe-triage.md`: recommendation and fit assessment.
- `docs/research/openchoreo-floe-hypotheses.md`: hypothesis matrix with pass/fail evidence.
- `docs/research/openchoreo-floe-mapping.md`: Floe-to-OpenChoreo concept and resource mapping.
- `docs/research/openchoreo-floe-spike-results.md`: proof results, commands, artifacts, blockers, and final recommendation.
- ADR candidate notes under `docs/architecture/adr/` if the spike recommends adoption.
- Roadmap outline under `docs/plans/` if the spike recommends adoption.

## Next Step

After this design is reviewed, create an implementation plan for the triage and spike. The plan should keep Phase 1 independently shippable so the work can stop cleanly if the recommendation is watch or reject.
