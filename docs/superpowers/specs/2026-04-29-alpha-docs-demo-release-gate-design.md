# Alpha Docs, Demo, And Release Gate Design

Status: Draft for user review
Date: 2026-04-29
Author: Codex

## Summary

Floe should not tag `v0.1.0-alpha.1` until the release is understandable,
demonstrable, and operationally repeatable. The current engineering spine is
substantially healthier, but alpha readiness still needs three coordinated
workstreams:

1. Documentation site and documentation standards.
2. Customer 360 golden demo user experience.
3. Release readiness and risk closure.

The recommended approach is a lightweight docs-as-code site using MkDocs
Material, with Customer 360 as the golden demo. This gives users a browsable
entry point, gives contributors clear technical references, and creates a
single evidence-backed release gate before tagging alpha.

## Goals

- Provide a browsable documentation site with clear user and contributor paths.
- Establish documentation standards that keep guides, references, and technical
  architecture in sync with future changes.
- Make Customer 360 the golden alpha demo for proving business value across the
  platform.
- Give users a guided way to open and inspect Dagster, MinIO, Marquez, Jaeger,
  and the semantic/query layer.
- Validate business outcomes, not just Kubernetes readiness.
- Close or explicitly classify the remaining release risks before tagging.
- Produce repeatable Devpod + Hetzner validation evidence for the alpha stack.

## Non-Goals

- Build a custom marketing website before alpha.
- Replace the existing Markdown documentation corpus.
- Make every existing demo equally polished for alpha.
- Close all known post-alpha architecture debt before `v0.1.0-alpha.1`.
- Claim production readiness.
- Support arbitrary platform/plugin combinations in the golden demo.

## Workstream 1: Documentation Site And Standards

### Recommendation

Use MkDocs Material for alpha documentation.

MkDocs fits the current repository because the documentation is already
Markdown-heavy, and the immediate need is discoverability, navigation, search,
and consistent structure. A custom React or Docusaurus site can come later if
Floe needs a richer marketing surface. Plain Markdown in the repository is no
longer enough because users need guided journeys and contributors need stable
technical references.

### Information Architecture

The docs site should have these top-level sections:

- **Start Here**: what Floe is, when to use it, architecture in one page, and
  alpha limitations.
- **Get Started**: deploy your first Floe Platform, configure your first
  platform manifest, build your first data product, and run the Customer 360
  demo.
- **Demo**: Customer 360 tour, service access, validation checklist, expected
  UI states, and troubleshooting.
- **Concepts**: four-layer model, `manifest.yaml` vs `floe.yaml`, plugin
  boundaries, compiled artifacts, governance, lineage, and observability.
- **Operations**: Devpod + Hetzner, Helm, CI/E2E validation, troubleshooting,
  reset semantics, and release validation.
- **Reference**: schemas, CLI commands, chart values, plugin interfaces,
  compiled artifact contract, and service ports.
- **Contributing**: repository structure, test standards, docs standards,
  architecture boundaries, PR checklist, and release checklist.

### Documentation Standards

Every important user-facing change should update at least one of these:

- Guide: when user behavior changes.
- Reference: when schema, CLI, chart, or API behavior changes.
- Troubleshooting: when a failure mode is discovered or fixed.
- Architecture: when package boundaries, contracts, or plugin responsibilities
  change.
- Release notes: when behavior is noteworthy but not a permanent guide topic.

Documentation should be validated in CI with:

- docs site build.
- link checking for internal links where practical.
- navigation coverage for all alpha-critical pages.
- markdown linting if it does not create excessive churn.

## Workstream 2: Customer 360 Golden Demo UX

### Golden Demo Scope

Customer 360 is the alpha demo. Other demos can remain as examples, but they
should not block the first alpha unless they are part of the Customer 360
validation path.

The Customer 360 demo should prove:

- Platform services deploy successfully.
- Dagster can run the Customer 360 pipeline.
- dbt transformations produce business-facing marts.
- Iceberg tables and/or object-store outputs exist after materialization.
- MinIO shows expected data artifacts.
- OpenLineage events are emitted.
- Marquez shows the Customer 360 lineage graph.
- Jaeger shows traces for the demo execution path.
- A semantic or query layer returns a business metric.

### User Experience

The demo should have a single guided path:

1. Prepare the Devpod + Hetzner environment.
2. Deploy the Floe platform.
3. Build and load the demo runtime image if needed.
4. Run the Customer 360 data product.
5. Open service UIs.
6. Validate the expected business outputs.
7. Reset and rerun deterministically.

The guide should include:

- exact commands.
- expected duration.
- expected service URLs and port-forward commands.
- credentials or credential lookup instructions.
- expected UI states for each service.
- expected output tables, jobs, lineage entries, traces, and query results.
- troubleshooting for the known failure classes discovered during hardening.

### Validation Command

Add or harden a demo validation command that checks outcomes rather than only
pod readiness. It should validate:

- Kubernetes deployment health.
- service reachability.
- Dagster run status.
- expected Customer 360 outputs.
- object-store artifacts.
- OpenLineage/Marquez visibility.
- Jaeger trace visibility where feasible.
- semantic/query endpoint response where feasible.

The command should print a concise evidence summary that can be copied into the
release validation record.

## Workstream 3: Release Readiness And Risk Closure

### Alpha Blockers

The alpha tag is blocked until:

- Documentation site exists, builds in CI, and contains the required user and
  contributor journeys.
- Customer 360 golden demo guide and validation checklist exist.
- Customer 360 demo validation passes on Devpod + Hetzner.
- #271 is closed: pinned GitHub Actions are upgraded or explicitly proven
  Node.js 24-compatible.
- #197 is closed or proven irrelevant to the blessed Devpod + Hetzner path.
- Final release validation evidence is captured.
- #263 is either closed or explicitly documented as known post-alpha
  architecture debt that does not contradict the alpha promise.

### Release-Reviewed Non-Blockers

Issue #263, Dagster importing `floe-iceberg` internals, should be treated as
release-reviewed architecture debt unless the alpha promise includes running
Dagster without Iceberg installed. The Customer 360 alpha stack requires
Iceberg, so this coupling is acceptable for alpha if it is documented and kept
tracked.

### Time-Based CI Risk

Issue #271 should be closed before alpha. Node.js 20 action deprecation is
time-based, externally imposed release risk. The work is bounded and improves
future CI reliability.

### Deployment Portability Risk

Issue #197 should be treated as alpha-blocking for a Devpod + Hetzner release
path unless investigation proves the hardcoded `KUBECONFIG_PATH` does not
affect current commands. Hardcoded workspace-specific paths undermine the
repeatability of the exact validation lane the alpha depends on.

## Architecture

The release gate keeps the existing four-layer model and adds documentation and
demo evidence around it:

```text
Docs Site
  -> User journey: platform deploy
  -> User journey: Customer 360 data product
  -> Technical reference: contracts, charts, plugins

Customer 360 Demo
  -> manifest.yaml + floe.yaml
  -> CompiledArtifacts
  -> Dagster run
  -> dbt transformations
  -> Iceberg/Object storage
  -> OpenLineage events
  -> Marquez lineage
  -> Jaeger traces
  -> Semantic/query proof

Release Gate
  -> Docs build
  -> Demo validation
  -> CI/security checks
  -> Devpod + Hetzner evidence
  -> Known-risk classification
```

Documentation should explain the platform without becoming a second source of
truth for schemas or generated reference material. Where possible, reference
pages should point to schema definitions, generated examples, or validated
fixtures.

## Components

### Docs Site

New docs infrastructure should include:

- `mkdocs.yml` with explicit navigation.
- Material theme configuration.
- docs build command.
- CI check for docs build.
- contribution guidance for docs updates.

The site should reuse existing docs by reorganizing and linking them rather
than rewriting everything before alpha.

### Customer 360 Demo Guide

The guide should be the primary user-facing alpha walkthrough. It should live
under the docs site and link to the demo source files.

It should include service inspection sections for:

- Dagster: run status, assets/jobs, materialization evidence.
- MinIO: buckets/objects that prove data was written.
- Marquez: namespace/job/dataset lineage for Customer 360.
- Jaeger: traces for runtime execution.
- Semantic/query layer: business metric query.

### Demo Validation Tooling

Validation should be executable and evidence-oriented. It can start as a shell
or Python command if it follows existing repository patterns, but it should have
a stable invocation documented in the guide.

The output should distinguish:

- platform readiness failure.
- demo execution failure.
- data output failure.
- lineage failure.
- tracing failure.
- semantic/query failure.
- external transient.

### Release Checklist

Add a release checklist that records:

- commit SHA.
- CI run links.
- Helm CI run links.
- Devpod + Hetzner validation run.
- Customer 360 evidence summary.
- security scan status.
- open release-reviewed issues.
- known alpha limitations.

## Data Flow

1. User enters through the docs site.
2. User follows the platform deployment guide.
3. User follows the Customer 360 demo guide.
4. Demo configuration compiles into `CompiledArtifacts`.
5. Dagster runs the Customer 360 pipeline.
6. dbt builds Customer 360 models.
7. Outputs are written to storage/Iceberg.
8. OpenLineage emits runtime events.
9. Marquez displays lineage for the emitted namespace/job/datasets.
10. Jaeger displays traces for the runtime path.
11. Semantic/query layer returns a business-facing result.
12. Validation command captures the evidence summary.
13. Release checklist links the evidence before tagging.

## Error Handling And Troubleshooting

Documentation and validation should make failures actionable:

- If a service UI cannot be opened, show the exact port-forward and pod/service
  diagnostics to check.
- If Dagster fails, link to run logs and the expected diagnostics command.
- If data is missing from MinIO/Iceberg, distinguish dbt success from storage
  materialization success.
- If Marquez has no lineage, report emitted OpenLineage namespace/job identity
  and the Marquez query used.
- If Jaeger has no traces, report collector status and expected service/span
  identifiers.
- If a semantic query fails, report endpoint status and the exact query.
- If Devpod/Hetzner validation fails, include remote source branch/commit and
  kubeconfig path diagnostics.

## Testing And Validation

### Documentation

- Docs site builds locally.
- Docs site builds in CI.
- Required alpha pages are present in navigation.
- Internal links for alpha-critical pages are validated where practical.

### Demo

- Customer 360 demo validation command passes locally where feasible.
- Customer 360 demo validation command passes in Devpod + Hetzner.
- Manual UI inspection confirms Dagster, MinIO, Marquez, Jaeger, and
  semantic/query proof.
- Demo reset and rerun are deterministic enough for release validation.

### Release Gate

- #271 closed and CI still green.
- #197 closed or documented as irrelevant with evidence.
- #263 release posture documented in release notes or closed.
- Full CI green on `main`.
- Helm CI green on `main`.
- Final Devpod + Hetzner validation evidence recorded.

## Implementation Order

1. Create docs site infrastructure with MkDocs Material and CI docs build.
2. Define docs standards and release documentation checklist.
3. Create the Customer 360 demo guide skeleton and service inspection map.
4. Harden or add Customer 360 demo validation command.
5. Fill the demo guide with validated commands, service URLs, expected UI
   states, and business outcomes.
6. Close #271 by upgrading pinned GitHub Actions.
7. Close or resolve #197 for the Devpod + Hetzner path.
8. Add release checklist and alpha release notes skeleton, including #263
   classification if still open.
9. Run final Devpod + Hetzner validation and capture evidence.
10. Tag `v0.1.0-alpha.1` only after all alpha blockers are satisfied.

## Acceptance Criteria

- `mkdocs build` or equivalent docs build command passes.
- Docs CI blocks broken docs builds.
- Docs site navigation includes Start Here, Get Started, Demo, Concepts,
  Operations, Reference, and Contributing.
- Customer 360 has a complete golden demo guide.
- The demo guide explains how to inspect Dagster, MinIO, Marquez, Jaeger, and
  the semantic/query layer.
- Customer 360 validation checks business outcomes, data outputs, lineage, and
  observability evidence.
- #271 is closed.
- #197 is closed or explicitly proven non-blocking for Devpod + Hetzner.
- #263 is either closed or documented as a known post-alpha architecture debt.
- Final Devpod + Hetzner validation passes and is linked from release evidence.
- Alpha is not tagged until the above criteria are met.

## Risks

- MkDocs setup could become a documentation migration project. Mitigation:
  reorganize only alpha-critical paths first; leave deep legacy docs linked but
  not fully rewritten.
- Demo validation could overreach into brittle UI automation. Mitigation:
  automate API/CLI checks and keep manual UI inspection as checklist evidence
  for alpha.
- Semantic/query proof may expose an incomplete semantic layer path. Mitigation:
  classify it as an alpha blocker only if Floe’s alpha promise includes semantic
  consumption; otherwise document the limitation clearly.
- #263 could become blocking if the alpha promise changes to support Dagster
  without Iceberg installed. Mitigation: make the release promise explicit in
  release notes.
- External CI/cache/dependency outages can still cause transient failures.
  Mitigation: rerun once, classify transients, and track recurring failures as
  GitHub issues.

## Open Decision

The current recommendation is that semantic/query proof is part of the Customer
360 alpha demo because it demonstrates business value rather than just pipeline
execution. If the implementation shows the semantic layer is not mature enough,
the release team must either fix it before alpha or explicitly narrow the alpha
promise and document semantic consumption as a known limitation.
