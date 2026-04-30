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
