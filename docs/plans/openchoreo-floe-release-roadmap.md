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
