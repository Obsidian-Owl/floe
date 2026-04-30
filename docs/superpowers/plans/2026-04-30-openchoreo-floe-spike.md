# OpenChoreo Floe Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an evidence-backed adopt, watch, or reject recommendation for OpenChoreo in Floe, and run a bounded proof only if the triage gate finds architectural alignment.

**Architecture:** Treat OpenChoreo as a candidate platform/developer-experience control plane around Floe, not as a replacement for Floe's data semantics. Keep Phase 1 independently shippable; Phase 2 maps the existing `demo/customer-360` data product to OpenChoreo resources; Phase 3 creates roadmap and ADR evidence only if the proof validates adoption.

**Tech Stack:** Floe docs and demo artifacts, Python 3.11 via `uv`, dbt/Floe demo compile path, Kubernetes CLI tools (`kubectl`, `helm`, `k3d` when available), OpenChoreo `release-v1.0` branch and published docs, Markdown research artifacts.

---

## File Structure

- Create `docs/research/openchoreo-floe-triage.md`: recommendation gate output, source facts, scoring, and decision.
- Create `docs/research/openchoreo-floe-hypotheses.md`: hypothesis matrix with evidence, pass/fail status, and confidence.
- Create `docs/research/openchoreo-floe-mapping.md`: Floe concepts mapped to OpenChoreo resources and ownership boundaries.
- Create `docs/research/openchoreo-floe-spike-results.md`: commands run, outputs summarized, blockers, and final spike outcome.
- Create `docs/research/openchoreo-proof/customer-360-openchoreo.yaml`: concrete OpenChoreo resource sketch for the Floe Customer 360 demo.
- Create `docs/plans/openchoreo-floe-release-roadmap.md` only if the proof recommends adoption: release slices and migration path.
- Create `docs/architecture/adr/0048-openchoreo-platform-control-plane.md` only if the proof recommends adoption: proposed ADR for OpenChoreo as an optional Floe platform control plane.

Do not modify Floe runtime code in this spike unless a separate follow-up plan is approved.

---

### Task 1: Create Research Artifact Scaffolding

**Files:**
- Create: `docs/research/openchoreo-floe-triage.md`
- Create: `docs/research/openchoreo-floe-hypotheses.md`
- Create: `docs/research/openchoreo-floe-mapping.md`
- Create: `docs/research/openchoreo-floe-spike-results.md`

- [ ] **Step 1: Create the research directory**

Run:

```bash
mkdir -p docs/research
```

Expected: `docs/research` exists.

- [ ] **Step 2: Create `docs/research/openchoreo-floe-triage.md`**

Write this content:

```markdown
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
| Release maturity |  |  |
| CRD/resource model |  |  |
| Control plane/runtime model |  |  |
| Developer portal/API |  |  |
| Workflow support |  |  |
| Observability support |  |  |
| Authz/secrets support |  |  |
| Install footprint |  |  |

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
```

- [ ] **Step 3: Create `docs/research/openchoreo-floe-hypotheses.md`**

Write this content:

```markdown
# OpenChoreo and Floe Hypotheses

Date: 2026-04-30

## Status Legend

- Pending: evidence has not been collected.
- Pass: evidence supports the hypothesis.
- Partial: evidence supports part of the hypothesis but leaves important risk.
- Fail: evidence contradicts the hypothesis.

## Matrix

| ID | Hypothesis | Evidence Required | Status | Evidence Summary | Confidence |
| --- | --- | --- | --- | --- | --- |
| H1 | OpenChoreo can improve Floe's developer experience by exposing higher-level project, component, environment, workflow, and observability abstractions around Floe data products. | A clear mapping from `floe.yaml` to OpenChoreo project/component UX with less user-facing Kubernetes detail. | Pending | Collected in Task 2 or Task 3 | Low |
| H2 | OpenChoreo can simplify Floe's physical architecture by taking ownership of some Kubernetes lifecycle concerns currently handled through Helm, GitOps examples, RBAC generation, network policy generation, and deployment glue. | Identified Floe-owned responsibilities that OpenChoreo can own without weakening Floe governance. | Pending | Collected in Task 2 or Task 3 | Low |
| H3 | Floe should keep ownership of data-specific semantics: configuration, plugin selection, compiled artifact contracts, dbt, Iceberg, lineage, quality gates, and governance enforcement. | Floe contracts remain source of truth and OpenChoreo consumes generated outputs. | Pending | Collected in Task 2 or Task 3 | Low |
| H4 | OpenChoreo is not a direct replacement for Floe's `OrchestratorPlugin`; it is closer to a platform/developer-experience control plane. | The best integration point lands outside the existing Dagster/Airflow/Prefect orchestrator abstraction. | Pending | Collected in Task 2 or Task 3 | Low |
| H5 | Adoption is only valuable if a Floe data product can be represented in OpenChoreo without breaking downward-only configuration flow or exposing low-level OpenChoreo CRDs to data engineers. | A proof resource set can be generated from existing Floe inputs and environment/promotion data stays outside `floe.yaml`. | Pending | Collected in Task 2 or Task 3 | Low |

## Decision Rule

Recommend the proof spike only if H3 and H4 are Pass or Partial, and at least one of H1 or H2 is Pass or Partial. Recommend watch or reject if H3 or H4 fails.
```

- [ ] **Step 4: Create `docs/research/openchoreo-floe-mapping.md`**

Write this content:

```markdown
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
```

- [ ] **Step 5: Create `docs/research/openchoreo-floe-spike-results.md`**

Write this content:

```markdown
# OpenChoreo and Floe Spike Results

Date: 2026-04-30

## Execution Log

| Task | Command or Action | Result | Evidence |
| --- | --- | --- | --- |
| Triage source capture | Pending | Pending | Pending |
| Floe architecture review | Pending | Pending | Pending |
| Recommendation gate | Pending | Pending | Pending |
| OpenChoreo proof resource generation | Pending | Pending | Pending |
| OpenChoreo render or cluster validation | Pending | Pending | Pending |
| Roadmap and ADR evidence | Pending | Pending | Pending |

## Final Outcome

Outcome: In progress

Recommendation: In progress

Confidence: In progress

## Blockers

No blockers recorded at scaffold time.
```

- [ ] **Step 6: Verify the scaffold files exist**

Run:

```bash
ls docs/research/openchoreo-floe-triage.md \
  docs/research/openchoreo-floe-hypotheses.md \
  docs/research/openchoreo-floe-mapping.md \
  docs/research/openchoreo-floe-spike-results.md
```

Expected: all four paths are printed.

- [ ] **Step 7: Commit the scaffold**

Run:

```bash
git add docs/research/openchoreo-floe-triage.md \
  docs/research/openchoreo-floe-hypotheses.md \
  docs/research/openchoreo-floe-mapping.md \
  docs/research/openchoreo-floe-spike-results.md
git commit -m "docs: scaffold OpenChoreo spike research"
```

Expected: commit succeeds.

---

### Task 2: Capture OpenChoreo Source Facts

**Files:**
- Modify: `docs/research/openchoreo-floe-triage.md`
- Modify: `docs/research/openchoreo-floe-spike-results.md`

- [ ] **Step 1: Clone the OpenChoreo release branch**

Run:

```bash
rm -rf /tmp/openchoreo-floe-source
git clone --depth 1 --branch release-v1.0 https://github.com/openchoreo/openchoreo.git /tmp/openchoreo-floe-source
git -C /tmp/openchoreo-floe-source rev-parse HEAD
```

Expected: clone succeeds and prints a commit SHA.

- [ ] **Step 2: Capture release and repository metadata**

Run:

```bash
curl -fsSL 'https://api.github.com/repos/openchoreo/openchoreo/releases?per_page=5' \
  | rg 'tag_name|published_at|prerelease|draft'
curl -fsSL 'https://api.github.com/repos/openchoreo/openchoreo' \
  | rg 'full_name|description|created_at|updated_at|pushed_at|stargazers_count|forks_count|open_issues_count|license|default_branch'
```

Expected: output includes `v1.0.1-hotfix.1`, release dates, repository description, Apache-2.0 license data, and activity counts.

- [ ] **Step 3: Inventory OpenChoreo CRDs and API types**

Run:

```bash
find /tmp/openchoreo-floe-source/api/v1alpha1 -maxdepth 1 -type f -name '*_types.go' | sort
find /tmp/openchoreo-floe-source/config/crd/bases -maxdepth 1 -type f -name 'openchoreo.dev_*.yaml' | sort
```

Expected: output includes resource types such as `component_types.go`, `workload_types.go`, `workflow_types.go`, `releasebinding_types.go`, `environment_types.go`, `dataplane_types.go`, and their CRD YAML files.

- [ ] **Step 4: Inventory OpenChoreo install surface**

Run:

```bash
find /tmp/openchoreo-floe-source/install -maxdepth 4 -type f \( -name 'Chart.yaml' -o -name 'values.yaml' -o -name 'README.md' \) | sort
sed -n '1,220p' /tmp/openchoreo-floe-source/install/quick-start/README.md
sed -n '1,220p' /tmp/openchoreo-floe-source/install/k3d/single-cluster/README.md
```

Expected: output includes Helm charts for control plane, data plane, observability plane, and workflow plane, plus k3d quick-start prerequisites.

- [ ] **Step 5: Inventory developer and runtime concepts**

Run:

```bash
sed -n '1,220p' /tmp/openchoreo-floe-source/README.md
sed -n '1,240p' /tmp/openchoreo-floe-source/docs/resource-kind-reference-guide.md
sed -n '1,220p' /tmp/openchoreo-floe-source/docs/templating/templating.md
sed -n '1,160p' /tmp/openchoreo-floe-source/samples/from-source/projects/url-shortener/project.yaml
sed -n '1,160p' /tmp/openchoreo-floe-source/samples/from-image/go-greeter-service/greeter-service.yaml
sed -n '1,180p' /tmp/openchoreo-floe-source/samples/from-image/issue-reporter-schedule-task/github-issue-reporter.yaml
```

Expected: output shows the control-plane positioning, resource model, templating model, and sample `Project`, `Component`, `Workload`, `SecretReference`, and `ReleaseBinding` resources.

- [ ] **Step 6: Update `docs/research/openchoreo-floe-triage.md` with OpenChoreo facts**

Replace the `OpenChoreo Snapshot` table with evidence-backed entries. Use this completed structure:

```markdown
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
```

- [ ] **Step 7: Update `docs/research/openchoreo-floe-spike-results.md` execution log**

Replace the first execution row with:

```markdown
| Triage source capture | Cloned `release-v1.0`; inspected release API, CRDs, install charts, docs, and samples. | Complete | OpenChoreo has a broad Kubernetes control-plane surface with `v1alpha1` CRDs and a multi-plane install model. |
```

- [ ] **Step 8: Commit OpenChoreo source facts**

Run:

```bash
git add docs/research/openchoreo-floe-triage.md docs/research/openchoreo-floe-spike-results.md
git commit -m "docs: capture OpenChoreo source facts"
```

Expected: commit succeeds.

---

### Task 3: Capture Floe Architecture Baseline

**Files:**
- Modify: `docs/research/openchoreo-floe-triage.md`
- Modify: `docs/research/openchoreo-floe-spike-results.md`

- [ ] **Step 1: Read Floe architecture and deployment boundaries**

Run:

```bash
sed -n '1,220p' docs/architecture/ARCHITECTURE-SUMMARY.md
sed -n '1,260p' docs/architecture/four-layer-overview.md
sed -n '1,260p' docs/architecture/platform-services.md
sed -n '1,220p' docs/architecture/plugin-system/index.md
sed -n '1,220p' docs/architecture/interfaces/orchestrator-plugin.md
sed -n '1,220p' docs/architecture/opinionation-boundaries.md
```

Expected: output confirms Floe's four-layer model, plugin categories, platform services, enforced technologies, and orchestrator abstraction.

- [ ] **Step 2: Read representative Floe product and platform config**

Run:

```bash
sed -n '1,220p' demo/customer-360/floe.yaml
sed -n '1,260p' demo/manifest.yaml
sed -n '1,220p' docs/contracts/compiled-artifacts.md
```

Expected: output shows a scheduled Customer 360 data product, platform plugin selections, and the compiled artifact contract.

- [ ] **Step 3: Inspect Floe Kubernetes/GitOps surfaces**

Run:

```bash
rg -n 'GitOps|ArgoCD|Flux|NetworkPolicy|RBAC|Secret|OpenTelemetry|OpenLineage|Dagster|Helm' \
  charts docs/architecture docs/guides plugins packages/floe-core/src/floe_core -g '*.md' -g '*.py' -g '*.yaml' \
  | sed -n '1,260p'
```

Expected: output shows Floe already owns Helm charts, GitOps examples, RBAC, network security, Dagster runtime, OpenTelemetry, and OpenLineage integrations.

- [ ] **Step 4: Update `docs/research/openchoreo-floe-triage.md` with Floe fit assessment**

Replace the `Floe Fit Assessment` table with:

```markdown
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
```

- [ ] **Step 5: Update `docs/research/openchoreo-floe-spike-results.md` execution log**

Replace the second execution row with:

```markdown
| Floe architecture review | Inspected architecture summary, platform services, plugin system, orchestrator interface, Customer 360 demo, manifest, and compiled artifact contract. | Complete | Floe's data semantics and compiled artifact handoff must remain Floe-owned; OpenChoreo is only plausible as an optional platform-control layer. |
```

- [ ] **Step 6: Commit Floe baseline facts**

Run:

```bash
git add docs/research/openchoreo-floe-triage.md docs/research/openchoreo-floe-spike-results.md
git commit -m "docs: assess Floe architecture fit for OpenChoreo"
```

Expected: commit succeeds.

---

### Task 4: Complete Recommendation Gate

**Files:**
- Modify: `docs/research/openchoreo-floe-triage.md`
- Modify: `docs/research/openchoreo-floe-hypotheses.md`
- Modify: `docs/research/openchoreo-floe-spike-results.md`

- [ ] **Step 1: Score the fit categories**

In `docs/research/openchoreo-floe-triage.md`, replace the `Scoring` table with:

```markdown
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
| Adoption complexity | -1 | Multi-plane install, `v1alpha1` CRDs, external prerequisites, and overlapping platform controls increase operational complexity. |
| Operational maturity | 0 | `v1.0.x` releases are promising, but current CRDs remain alpha-versioned and the open issue count requires caution. |
| Release roadmap value | 1 | If proof validates generated resources and clear boundaries, OpenChoreo could become a future optional integration for platform teams. |
```

- [ ] **Step 2: Write the recommendation gate**

In `docs/research/openchoreo-floe-triage.md`, replace `Gate Decision` with:

```markdown
## Gate Decision

Decision: Adopt candidate for a bounded proof spike.

Confidence: Medium-low.

Reasoning:

OpenChoreo has plausible architectural alignment as an optional platform-control layer around Floe, especially for project/component/environment abstractions, release binding, workflow-plane integration, and platform observability. It should not replace Floe's data semantics, plugin contracts, dbt/Iceberg/OpenLineage ownership, or the existing orchestrator interface.

The proof spike is justified because the largest unresolved question is practical complexity: whether OpenChoreo can reduce Floe-owned Kubernetes lifecycle glue without adding a parallel platform that keeps all current Floe responsibilities intact.

Next action: Run Phase 2 against `demo/customer-360` and validate generated OpenChoreo resource shape, render behavior, install footprint, and ownership boundaries.
```

- [ ] **Step 3: Update hypothesis statuses**

In `docs/research/openchoreo-floe-hypotheses.md`, replace the `Matrix` table with:

```markdown
## Matrix

| ID | Hypothesis | Evidence Required | Status | Evidence Summary | Confidence |
| --- | --- | --- | --- | --- | --- |
| H1 | OpenChoreo can improve Floe's developer experience by exposing higher-level project, component, environment, workflow, and observability abstractions around Floe data products. | A clear mapping from `floe.yaml` to OpenChoreo project/component UX with less user-facing Kubernetes detail. | Partial | Upstream concepts match a better platform UX, but proof must show Floe can generate the resource set and avoid exposing CRDs to data engineers. | Medium-low |
| H2 | OpenChoreo can simplify Floe's physical architecture by taking ownership of some Kubernetes lifecycle concerns currently handled through Helm, GitOps examples, RBAC generation, network policy generation, and deployment glue. | Identified Floe-owned responsibilities that OpenChoreo can own without weakening Floe governance. | Partial | OpenChoreo overlaps with lifecycle, authz, secrets, observability, and gateways; proof must show simplification rather than duplication. | Low |
| H3 | Floe should keep ownership of data-specific semantics: configuration, plugin selection, compiled artifact contracts, dbt, Iceberg, lineage, quality gates, and governance enforcement. | Floe contracts remain source of truth and OpenChoreo consumes generated outputs. | Pass | The clean boundary is for OpenChoreo to consume Floe outputs; replacing Floe contracts would conflict with target architecture. | High |
| H4 | OpenChoreo is not a direct replacement for Floe's `OrchestratorPlugin`; it is closer to a platform/developer-experience control plane. | The best integration point lands outside the existing Dagster/Airflow/Prefect orchestrator abstraction. | Pass | OpenChoreo's model is broader than workflow orchestration and should be tested as platform-control integration. | High |
| H5 | Adoption is only valuable if a Floe data product can be represented in OpenChoreo without breaking downward-only configuration flow or exposing low-level OpenChoreo CRDs to data engineers. | A proof resource set can be generated from existing Floe inputs and environment/promotion data stays outside `floe.yaml`. | Pending | Requires Phase 2 proof. | Medium-low |
```

- [ ] **Step 4: Update `docs/research/openchoreo-floe-spike-results.md` execution log**

Replace the third execution row with:

```markdown
| Recommendation gate | Scored OpenChoreo against Floe architecture and hypotheses. | Adopt candidate for bounded proof | Proof should test optional platform-control integration, not orchestrator replacement. |
```

- [ ] **Step 5: Commit the gate decision**

Run:

```bash
git add docs/research/openchoreo-floe-triage.md \
  docs/research/openchoreo-floe-hypotheses.md \
  docs/research/openchoreo-floe-spike-results.md
git commit -m "docs: recommend bounded OpenChoreo proof spike"
```

Expected: commit succeeds.

**Gate:** Continue to Task 5 because the recommendation is "Adopt candidate for a bounded proof spike." If a future executor changes the recommendation to watch or reject based on fresher evidence, stop after this commit and summarize why Tasks 5-8 were not run.

---

### Task 5: Complete Floe to OpenChoreo Mapping

**Files:**
- Modify: `docs/research/openchoreo-floe-mapping.md`
- Modify: `docs/research/openchoreo-floe-hypotheses.md`

- [ ] **Step 1: Replace concept mapping with evidence-backed ownership decisions**

In `docs/research/openchoreo-floe-mapping.md`, replace `Concept Mapping` with:

```markdown
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
```

- [ ] **Step 2: Replace integration shape assessment**

In `docs/research/openchoreo-floe-mapping.md`, replace `Integration Shape Assessment` with:

```markdown
## Integration Shape Assessment

| Shape | Description | Position | Evidence |
| --- | --- | --- | --- |
| A | OpenChoreo as optional platform control plane around Floe outputs | Preferred proof target | Preserves Floe's data semantics and lets OpenChoreo own project/component/release surfaces. |
| B | OpenChoreo as deployment backend for selected Floe workloads/services | Secondary future target | Could reduce Helm/GitOps glue, but requires stronger proof of operational value. |
| C | OpenChoreo as `OrchestratorPlugin` | Rejected as initial approach | OpenChoreo is a broad platform control plane; Floe's orchestrator interface expects workflow engines such as Dagster, Airflow, or Prefect. |
```

- [ ] **Step 3: Add resource-generation notes**

Append this section to `docs/research/openchoreo-floe-mapping.md`:

```markdown
## Generated Resource Strategy

The first useful integration slice would generate OpenChoreo intent resources from Floe inputs:

1. Read `floe.yaml` and `CompiledArtifacts`.
2. Emit a `Project` for the data product domain or product grouping.
3. Emit a `Component` for each deployable Floe runtime unit.
4. Emit a `Workload` pointing to the Floe runtime image and compiled artifact path.
5. Emit a `ReleaseBinding` per promoted environment from Floe promotion data.
6. Emit `SecretReference` resources only when the source is a Floe `SecretReference` or plugin-owned secret reference, never from raw secret values.

Data engineers should continue editing Floe files. Platform engineers may inspect or approve generated OpenChoreo resources.
```

- [ ] **Step 4: Update H5 status to Partial**

In `docs/research/openchoreo-floe-hypotheses.md`, update the H5 row status to `Partial` and evidence summary to:

```markdown
Generated-resource mapping appears feasible on paper. The proof manifest must still validate that OpenChoreo accepts the shape without forcing environment-specific fields into `floe.yaml`.
```

- [ ] **Step 5: Commit mapping**

Run:

```bash
git add docs/research/openchoreo-floe-mapping.md docs/research/openchoreo-floe-hypotheses.md
git commit -m "docs: map Floe concepts to OpenChoreo resources"
```

Expected: commit succeeds.

---

### Task 6: Validate OpenChoreo Render and Install Complexity

**Files:**
- Modify: `docs/research/openchoreo-floe-spike-results.md`
- Modify: `docs/research/openchoreo-floe-triage.md`

- [ ] **Step 1: Check local tooling**

Run:

```bash
command -v git
command -v curl
command -v rg
command -v kubectl || true
command -v helm || true
command -v k3d || true
command -v docker || true
```

Expected: `git`, `curl`, and `rg` are present. Record whether `kubectl`, `helm`, `k3d`, and `docker` are present.

- [ ] **Step 2: Build OpenChoreo Helm dependencies when Helm is present**

Run:

```bash
cd /tmp/openchoreo-floe-source
helm dependency build install/helm/openchoreo-control-plane
helm dependency build install/helm/openchoreo-data-plane
helm dependency build install/helm/openchoreo-workflow-plane
helm dependency build install/helm/openchoreo-observability-plane
```

Expected when Helm and network access are available: dependency builds succeed. If a dependency build fails, copy the failing command and the first actionable error line into `docs/research/openchoreo-floe-spike-results.md`.

- [ ] **Step 3: Render OpenChoreo charts when Helm dependencies are available**

Run:

```bash
cd /tmp/openchoreo-floe-source
helm template openchoreo-control-plane install/helm/openchoreo-control-plane \
  --namespace openchoreo-system \
  --values install/k3d/single-cluster/values-cp.yaml \
  > /tmp/openchoreo-control-plane-render.yaml
helm template openchoreo-data-plane install/helm/openchoreo-data-plane \
  --namespace openchoreo-data-plane \
  --values install/k3d/single-cluster/values-dp.yaml \
  > /tmp/openchoreo-data-plane-render.yaml
helm template openchoreo-workflow-plane install/helm/openchoreo-workflow-plane \
  --namespace openchoreo-workflow-plane \
  --values install/k3d/single-cluster/values-wp.yaml \
  > /tmp/openchoreo-workflow-plane-render.yaml
helm template openchoreo-observability-plane install/helm/openchoreo-observability-plane \
  --namespace openchoreo-observability-plane \
  --values install/k3d/single-cluster/values-op.yaml \
  > /tmp/openchoreo-observability-plane-render.yaml
wc -l /tmp/openchoreo-*-render.yaml
```

Expected when charts render: each render file exists and `wc -l` prints line counts. If rendering fails, record the failed chart and error in `docs/research/openchoreo-floe-spike-results.md`.

- [ ] **Step 4: Count install footprint from rendered manifests**

Run:

```bash
rg '^kind: ' /tmp/openchoreo-*-render.yaml | sed 's/.*kind: //' | sort | uniq -c | sort -nr
```

Expected when render files exist: output lists Kubernetes resource kind counts. Use the counts to assess operational footprint.

- [ ] **Step 5: Update spike results with render/install evidence**

Append this section to `docs/research/openchoreo-floe-spike-results.md`, filling in exact observed outcomes:

```markdown
## OpenChoreo Render and Install Complexity

Tool availability:

| Tool | Present | Notes |
| --- | --- | --- |
| kubectl |  |  |
| helm |  |  |
| k3d |  |  |
| docker |  |  |

Helm dependency result:

| Chart | Result | Notes |
| --- | --- | --- |
| openchoreo-control-plane |  |  |
| openchoreo-data-plane |  |  |
| openchoreo-workflow-plane |  |  |
| openchoreo-observability-plane |  |  |

Rendered resource footprint:

| Signal | Result |
| --- | --- |
| Control-plane render line count |  |
| Data-plane render line count |  |
| Workflow-plane render line count |  |
| Observability-plane render line count |  |
| Dominant resource kinds |  |

Assessment:

OpenChoreo has a meaningful install footprint. This does not block adoption, but it means Floe should treat it as an optional platform integration until a platform team explicitly chooses it.
```

- [ ] **Step 6: Update triage adoption complexity evidence**

In `docs/research/openchoreo-floe-triage.md`, refine the `Adoption complexity` scoring evidence with the observed render/install result. Keep the score at `-1` unless the render work shows a smaller footprint than expected.

- [ ] **Step 7: Commit render/install findings**

Run:

```bash
git add docs/research/openchoreo-floe-spike-results.md docs/research/openchoreo-floe-triage.md
git commit -m "docs: record OpenChoreo install complexity"
```

Expected: commit succeeds.

---

### Task 7: Generate and Validate Customer 360 Proof Resources

**Files:**
- Create: `docs/research/openchoreo-proof/customer-360-openchoreo.yaml`
- Modify: `docs/research/openchoreo-floe-mapping.md`
- Modify: `docs/research/openchoreo-floe-hypotheses.md`
- Modify: `docs/research/openchoreo-floe-spike-results.md`

- [ ] **Step 1: Compile the Floe demo artifacts**

Run:

```bash
make compile-demo
ls demo/customer-360/compiled_artifacts.json demo/customer-360/target/manifest.json
```

Expected: demo compilation succeeds and both files exist. If compilation fails, record the command and the error summary in `docs/research/openchoreo-floe-spike-results.md`, then continue with static mapping from `demo/customer-360/floe.yaml`.

- [ ] **Step 2: Create proof directory**

Run:

```bash
mkdir -p docs/research/openchoreo-proof
```

Expected: directory exists.

- [ ] **Step 3: Create `docs/research/openchoreo-proof/customer-360-openchoreo.yaml`**

Write this content:

```yaml
apiVersion: openchoreo.dev/v1alpha1
kind: Project
metadata:
  name: customer-360
  namespace: default
  labels:
    openchoreo.dev/name: customer-360
    floe.dev/domain: retail
    floe.dev/tier: gold
  annotations:
    openchoreo.dev/display-name: Customer 360
    openchoreo.dev/description: Retail customer 360 data product generated from Floe demo metadata.
spec:
  deploymentPipelineRef:
    name: default
---
apiVersion: openchoreo.dev/v1alpha1
kind: Component
metadata:
  name: customer-360
  namespace: default
  labels:
    floe.dev/product: customer-360
    floe.dev/source: demo-customer-360
spec:
  owner:
    projectName: customer-360
  autoDeploy: false
  componentType:
    kind: ClusterComponentType
    name: cronjob/scheduled-task
  parameters:
    successfulJobsHistoryLimit: 3
    failedJobsHistoryLimit: 1
    concurrencyPolicy: Forbid
    backoffLimit: 2
    activeDeadlineSeconds: 3600
    restartPolicy: OnFailure
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 1Gi
---
apiVersion: openchoreo.dev/v1alpha1
kind: Workload
metadata:
  name: customer-360-workload
  namespace: default
  labels:
    floe.dev/product: customer-360
spec:
  owner:
    componentName: customer-360
    projectName: customer-360
  container:
    image: floe-dagster-demo:openchoreo-spike
    env:
      - key: FLOE_PRODUCT
        value: customer-360
      - key: FLOE_ARTIFACTS_PATH
        value: /app/demo/customer-360/compiled_artifacts.json
      - key: FLOE_DBT_PROJECT_DIR
        value: /app/demo/customer-360
      - key: OTEL_SERVICE_NAME
        value: floe-customer-360
---
apiVersion: openchoreo.dev/v1alpha1
kind: SecretReference
metadata:
  name: customer-360-runtime-secrets
  namespace: default
  labels:
    floe.dev/product: customer-360
spec:
  template:
    type: Opaque
    metadata:
      labels:
        floe.dev/product: customer-360
  data:
    - secretKey: polaris-client-secret
      remoteRef:
        key: floe/customer-360/polaris
        property: client_secret
    - secretKey: minio-access-key
      remoteRef:
        key: floe/customer-360/minio
        property: access_key
  refreshInterval: 1h
---
apiVersion: openchoreo.dev/v1alpha1
kind: ReleaseBinding
metadata:
  name: customer-360-development
  namespace: default
  labels:
    floe.dev/product: customer-360
spec:
  owner:
    projectName: customer-360
    componentName: customer-360
  environment: development
  releaseName: customer-360-openchoreo-spike
  # OpenChoreo release-v1.0 renamed the older componentTypeEnvOverrides field to this schema key.
  componentTypeEnvironmentConfigs:
    schedule: "*/10 * * * *"
    resources:
      requests:
        cpu: 250m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 1Gi
```

- [ ] **Step 4: Run YAML and Kubernetes client validation**

Run:

```bash
python - <<'PY'
from pathlib import Path
import yaml

path = Path("docs/research/openchoreo-proof/customer-360-openchoreo.yaml")
docs = list(yaml.safe_load_all(path.read_text()))
assert len(docs) == 5
assert [doc["kind"] for doc in docs] == ["Project", "Component", "Workload", "SecretReference", "ReleaseBinding"]
assert docs[0]["metadata"]["name"] == "customer-360"
assert docs[1]["spec"]["owner"]["projectName"] == "customer-360"
assert docs[2]["spec"]["container"]["env"][0]["value"] == "customer-360"
release_binding = docs[4]["spec"]
assert release_binding["releaseName"] == "customer-360-openchoreo-spike"
assert "componentTypeEnvironmentConfigs" in release_binding
assert "componentTypeEnvOverrides" not in release_binding
print("customer-360-openchoreo.yaml parsed and structure checks passed")
PY
kubectl apply --dry-run=client --validate=false -f docs/research/openchoreo-proof/customer-360-openchoreo.yaml
```

Expected: Python structure checks pass. `kubectl` client dry-run reports resources configured when `kubectl` is available; if no cluster is configured, record the local validation result and the `kubectl` error.

- [ ] **Step 5: Run server dry-run when OpenChoreo CRDs are installed**

Run:

```bash
kubectl get crd projects.openchoreo.dev components.openchoreo.dev workloads.openchoreo.dev releasebindings.openchoreo.dev secretreferences.openchoreo.dev
kubectl apply --server-side --dry-run=server -f docs/research/openchoreo-proof/customer-360-openchoreo.yaml
```

Expected when CRDs are installed: server dry-run accepts the proof resources or returns schema validation errors. Record exact schema errors because they are adoption-complexity evidence.

- [ ] **Step 6: Update mapping with proof findings**

Append this section to `docs/research/openchoreo-floe-mapping.md`:

```markdown
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
```

- [ ] **Step 7: Update hypotheses and spike results**

In `docs/research/openchoreo-floe-hypotheses.md`, update H5 based on validation:

- Use `Pass` if server dry-run accepts the resources or only reports easily fixable field-shape changes.
- Use `Partial` if only static/client validation was possible.
- Use `Fail` if OpenChoreo requires changing Floe source-of-truth ownership.

In `docs/research/openchoreo-floe-spike-results.md`, replace the fourth and fifth execution rows with:

```markdown
| OpenChoreo proof resource generation | Created `docs/research/openchoreo-proof/customer-360-openchoreo.yaml` from `demo/customer-360/floe.yaml` and Floe runtime assumptions. | Complete | Proof includes `Project`, `Component`, `Workload`, `SecretReference`, and `ReleaseBinding`. |
| OpenChoreo render or cluster validation | Ran YAML structure checks and Kubernetes dry-run validation. | Complete | Record whether validation was static/client-only or server-side with installed CRDs. |
```

- [ ] **Step 8: Commit proof resources**

Run:

```bash
git add docs/research/openchoreo-proof/customer-360-openchoreo.yaml \
  docs/research/openchoreo-floe-mapping.md \
  docs/research/openchoreo-floe-hypotheses.md \
  docs/research/openchoreo-floe-spike-results.md
git commit -m "docs: validate Customer 360 OpenChoreo proof mapping"
```

Expected: commit succeeds.

---

### Task 8: Produce Roadmap and ADR Evidence

**Files:**
- Create: `docs/plans/openchoreo-floe-release-roadmap.md`
- Create: `docs/architecture/adr/0048-openchoreo-platform-control-plane.md`
- Modify: `docs/research/openchoreo-floe-spike-results.md`

- [ ] **Step 1: Decide whether roadmap and ADR files should be created**

Read `docs/research/openchoreo-floe-triage.md`, `docs/research/openchoreo-floe-hypotheses.md`, and `docs/research/openchoreo-floe-spike-results.md`.

Create roadmap and ADR files only if:

- H3 and H4 are Pass.
- H5 is Pass or Partial.
- The final recommendation remains adopt candidate.
- The proof did not reveal a fundamental Floe contract conflict.

If any condition fails, skip Steps 2-5 and update `docs/research/openchoreo-floe-spike-results.md` with this final outcome:

```markdown
## Final Outcome

Outcome: Spike complete.

Recommendation: Watch or reject OpenChoreo for now.

Confidence: Medium.

Roadmap and ADR files were not created because the proof did not meet the adoption evidence threshold.
```

- [ ] **Step 2: Create `docs/plans/openchoreo-floe-release-roadmap.md` when adoption remains recommended**

Write this content:

```markdown
# OpenChoreo Floe Release Roadmap

Date: 2026-04-30

## Recommendation

Treat OpenChoreo as a future optional platform-control integration for Floe, not as a replacement for Floe's compiler, plugin system, data contracts, dbt/Iceberg semantics, OpenTelemetry, OpenLineage, or orchestrator plugins.

## Release Slice 1: Research Preview

Goal: Publish the integration boundary and generated-resource proof as documentation.

Scope:

- Document Floe-to-OpenChoreo ownership boundaries.
- Document generated resource examples for Customer 360.
- Document install-footprint and operational risks.
- Keep OpenChoreo out of the default Floe runtime path.

Exit criteria:

- Platform teams can understand where OpenChoreo fits.
- Data engineers do not need to learn OpenChoreo CRDs.
- No Floe runtime behavior changes.

## Release Slice 2: Experimental Generator

Goal: Add an opt-in generator that emits OpenChoreo resources from Floe artifacts.

Candidate scope:

- Add a command or plugin-owned utility that reads `floe.yaml` and `CompiledArtifacts`.
- Emit `Project`, `Component`, `Workload`, `SecretReference`, and `ReleaseBinding` YAML.
- Add contract tests proving no raw secrets and no environment-specific fields enter `floe.yaml`.
- Add docs for platform teams using OpenChoreo.

Exit criteria:

- Generated resources validate against OpenChoreo CRDs.
- Floe remains source of truth for data semantics.
- OpenChoreo integration is disabled by default.

## Release Slice 3: Platform-Control Integration

Goal: Validate OpenChoreo as a platform-control option in a real K8s test environment.

Candidate scope:

- Add an integration test path for OpenChoreo CRD server-side validation.
- Evaluate whether Floe Helm/GitOps deployment glue can be reduced.
- Evaluate observability surface integration without replacing Floe telemetry or lineage emission.
- Evaluate authz, network, and secret adapters against Floe governance.

Exit criteria:

- OpenChoreo removes or simplifies at least one Floe-owned platform lifecycle responsibility.
- Operational footprint and upgrade path are documented.
- ADR is accepted before GA commitment.

## Non-Adoption Boundary

Do not make OpenChoreo mandatory unless a future proof shows it substantially simplifies platform operations for teams that choose it. The default Floe experience should remain usable without OpenChoreo.
```

- [ ] **Step 3: Create `docs/architecture/adr/0048-openchoreo-platform-control-plane.md` when adoption remains recommended**

Write this content:

```markdown
# ADR-0048: OpenChoreo as Optional Platform Control Plane Candidate

Date: 2026-04-30

Status: Proposed

## Context

Floe owns data-platform semantics through `manifest.yaml`, `floe.yaml`, `CompiledArtifacts`, plugin interfaces, dbt, Iceberg, OpenTelemetry, OpenLineage, and compile-time governance. Floe also owns Kubernetes deployment assets through Helm, GitOps examples, RBAC generation, network policy generation, and runtime service charts.

OpenChoreo is an Apache-2.0 Kubernetes internal developer platform with CRDs and APIs for projects, components, workloads, environments, release bindings, workflows, authz, secret references, and observability. It may improve platform developer experience and reduce some Kubernetes lifecycle glue, but it also introduces a broad control plane with operational footprint and overlapping responsibilities.

## Decision

Evaluate OpenChoreo as an optional platform-control integration for Floe. Do not treat OpenChoreo as a replacement for Floe's data contracts, compiler, plugin system, orchestrator plugins, dbt/Iceberg semantics, OpenTelemetry emission, or OpenLineage emission.

The initial integration direction is generated OpenChoreo resources from Floe source-of-truth artifacts:

- `Project` and `Component` from Floe product metadata.
- `Workload` from Floe runtime image and compiled artifact paths.
- `ReleaseBinding` from Floe promotion/environment data.
- `SecretReference` only from secret references, never raw secret values.

## Consequences

Positive:

- Platform teams may gain a richer project/component/environment UX.
- OpenChoreo may eventually reduce Floe-owned Kubernetes lifecycle glue.
- Floe can test adoption without changing the default runtime path.

Negative:

- OpenChoreo adds a broad operational dependency.
- CRDs are currently `v1alpha1`, which requires API-stability caution.
- RBAC, network policy, secrets, and observability overlap must be tightly bounded.

## Guardrails

- Floe remains the source of truth for data-platform semantics.
- Data engineers continue editing Floe files, not OpenChoreo CRDs.
- OpenChoreo integration remains opt-in until a future ADR changes that decision.
- No environment-specific credentials or runtime endpoints are added to `floe.yaml`.
- Generated resources must be validated in CI before any production recommendation.

## Evidence

Evidence is recorded in:

- `docs/research/openchoreo-floe-triage.md`
- `docs/research/openchoreo-floe-hypotheses.md`
- `docs/research/openchoreo-floe-mapping.md`
- `docs/research/openchoreo-floe-spike-results.md`
- `docs/research/openchoreo-proof/customer-360-openchoreo.yaml`
```

- [ ] **Step 4: Update final spike outcome**

In `docs/research/openchoreo-floe-spike-results.md`, replace `Final Outcome` with:

```markdown
## Final Outcome

Outcome: Spike complete.

Recommendation: Adopt OpenChoreo as a future optional platform-control integration candidate, pending a follow-up generator implementation plan and CRD validation path.

Confidence: Medium-low.

Key evidence:

- OpenChoreo aligns best around project, component, workload, release, workflow-plane, authz, secret-reference, and observability surfaces.
- Floe must retain ownership of data semantics, compiled artifacts, dbt, Iceberg, OpenLineage, OpenTelemetry emission, and plugin selection.
- Customer 360 can be represented as generated OpenChoreo intent resources without changing `floe.yaml`.
- Adoption complexity remains material because OpenChoreo introduces a multi-plane control-plane footprint and `v1alpha1` APIs.

Next recommended work:

Create a separate implementation plan for an opt-in OpenChoreo resource generator after ADR review.
```

- [ ] **Step 5: Update execution log roadmap row**

Replace the sixth execution row in `docs/research/openchoreo-floe-spike-results.md` with:

```markdown
| Roadmap and ADR evidence | Created release roadmap and proposed ADR when adoption evidence threshold was met. | Complete | See `docs/plans/openchoreo-floe-release-roadmap.md` and `docs/architecture/adr/0048-openchoreo-platform-control-plane.md`. |
```

- [ ] **Step 6: Commit roadmap and ADR evidence**

Run:

```bash
git add docs/research/openchoreo-floe-spike-results.md \
  docs/plans/openchoreo-floe-release-roadmap.md \
  docs/architecture/adr/0048-openchoreo-platform-control-plane.md
git commit -m "docs: outline OpenChoreo adoption roadmap"
```

Expected: commit succeeds if adoption remained recommended. If roadmap and ADR were skipped, commit only `docs/research/openchoreo-floe-spike-results.md` with message `docs: close OpenChoreo spike without adoption roadmap`.

---

### Task 9: Final Verification and Summary

**Files:**
- Verify: all research, proof, roadmap, and ADR files created by prior tasks

- [ ] **Step 1: Run Markdown and repository checks**

Run:

```bash
git status --short
git log --oneline -n 8
git diff --check HEAD~8..HEAD
rg -n 'TB[D]|TO[D]O|FIXM[E]|placehold[er]|Collected in Task 2 or Task 3|In progress' docs/research/openchoreo-floe-*.md docs/research/openchoreo-proof/customer-360-openchoreo.yaml docs/plans/openchoreo-floe-release-roadmap.md docs/architecture/adr/0048-openchoreo-platform-control-plane.md 2>/dev/null || true
```

Expected: `git diff --check` reports no whitespace errors. The `rg` command should not show unresolved status text in final research files, except files intentionally skipped by the gate should explain the skip in `openchoreo-floe-spike-results.md`.

- [ ] **Step 2: Run focused validation commands**

Run:

```bash
python - <<'PY'
from pathlib import Path
import yaml

proof = Path("docs/research/openchoreo-proof/customer-360-openchoreo.yaml")
if proof.exists():
    docs = list(yaml.safe_load_all(proof.read_text()))
    assert [doc["kind"] for doc in docs] == ["Project", "Component", "Workload", "SecretReference", "ReleaseBinding"]
    print("proof manifest structure verified")
else:
    print("proof manifest not created because the recommendation gate stopped before proof")
PY
```

Expected: prints either `proof manifest structure verified` or the gate-stop explanation.

- [ ] **Step 3: Write final execution summary in the assistant response**

Include:

- Final recommendation: adopt candidate, watch candidate, or reject candidate.
- Confidence level.
- Key evidence from the triage, mapping, proof, and install complexity.
- Files created.
- Validation commands run and whether they passed.
- Any commands that could not run because local tooling was missing.

Do not claim full OpenChoreo runtime adoption is validated unless server-side CRD validation or a local OpenChoreo install actually passed.
