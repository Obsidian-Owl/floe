# Enterprise Operating Model Docs Design

Status: Approved direction for implementation planning
Date: 2026-05-01
Author: Codex

## Summary

Floe should document a recommended enterprise operating model, not a narrow
demo workflow and not a fully prescribed delivery platform. Major
organizations already have source control, CI/CD, artifact registries,
approval workflows, deployment tooling, identity, and change-management
processes. Floe should guide how those systems interact with Floe contracts.

The corrected model is:

- Platform Engineers publish governed Floe platform environments.
- Data Engineers build data product repositories against those environments.
- CI compiles, validates, packages, and publishes runtime artifacts.
- Deployment happens through the organization's approved path, such as GitOps,
  CI deployment, release trains, or service catalog workflows.
- Floe owns the configuration contracts, compiled artifacts, policy checks,
  runtime wiring, lineage, and telemetry expectations.
- Floe does not require a specific Git provider, CI runner, registry, cloud,
  approval tool, or GitOps controller.

Customer 360 remains the advanced end-to-end proof. It should not be the first
teaching path for new users. The first-use docs should teach a smaller
"hello data product" lifecycle from scratch.

## Goals

- Publish a clear recommended enterprise operating model for Floe.
- Explain how Platform Engineers and Data Engineers interact through contracts,
  not manually shared endpoint lists.
- Replace vague "hand endpoints/config to Data Engineers" language with a
  Platform Environment Contract.
- Separate current alpha-supported behavior from target-state practice.
- Make Dagster the recommended alpha runtime spine for data product deployment.
- Present `floe-jobs` as an implemented lower-level primitive until it has a
  complete self-service data product workflow.
- Correct opinionation boundaries so implemented defaults, implemented
  alternatives, and planned integrations are labeled distinctly.
- Correct compute anti-patterns so approved per-transform compute is allowed,
  while unapproved per-product compute and per-environment compute drift remain
  forbidden.
- Redesign first-platform and first-data-product guides around building new
  artifacts, not only inspecting Customer 360.
- Add validation guardrails so public docs do not drift back into unsupported
  defaults, unsupported provider coupling, or unsupported lifecycle commands.

## Non-Goals

- Build new data product deployment features in this docs pass.
- Require a specific enterprise SCM, registry, CI/CD, approval, or GitOps
  product.
- Claim that packaged self-service data product deployment commands exist if
  they are still planned.
- Reclassify every target-state ADR as alpha-supported.
- Remove Customer 360 from the docs. It remains the advanced proof and release
  validation story.
- Convert `floe-jobs` into the primary product workflow without implementation
  work and E2E validation.

## Current Implementation Truth

The current repository supports these relevant primitives:

- `floe platform deploy` deploys the platform chart to Kubernetes.
- `floe platform compile` compiles a Floe data product spec and platform
  manifest into `CompiledArtifacts` and can generate Dagster `definitions.py`.
- The Customer 360 release-validation path builds a Dagster demo image,
  installs the platform chart with demo values, starts port-forwards, triggers
  the Dagster run, and validates evidence.
- `charts/floe-jobs` can render Kubernetes Jobs and CronJobs for dbt,
  ingestion, and custom jobs. It can discover platform Polaris and OTel
  endpoints from `platform.servicePrefix` and `platform.namespace`.
- Root data-team commands such as `floe compile`, `floe run`, and packaged
  self-service product deployment remain planned or stubbed.

This means the docs should not imply that Data Engineers can already run a
complete polished `floe product deploy` or `floe run` workflow. The alpha docs
should teach the available Dagster-centered path and clearly identify lower
level primitives.

## Enterprise Roles

### Platform Engineers

Platform Engineers own platform environments. They decide which platform
capabilities are available, how they are deployed, and how Data Engineers are
allowed to consume them.

Responsibilities:

- Deploy and operate Floe platform services on Kubernetes.
- Publish platform manifests and environment contracts.
- Approve plugin implementations and default settings.
- Configure namespaces, RBAC, service accounts, network policy, secrets,
  storage, catalog, lineage, telemetry, and runtime services.
- Provide CI/CD templates or deployment handoff patterns.
- Define promotion and approval gates with governance teams.
- Operate the shared platform and investigate platform-wide failures.

### Data Engineers

Data Engineers own data product source and behavior. They should not need to
know every service endpoint by hand, but they do need to know which platform
environment their product targets and what the environment contract allows.

Responsibilities:

- Create and maintain data product repositories.
- Define `floe.yaml`, dbt models, tests, seeds, contracts, metadata, schedules,
  and optional approved compute selection.
- Run local or CI validation before review.
- Produce product artifacts through Floe compilation.
- Deploy through the organization's approved release path.
- Validate product outputs, lineage, traces, and business metrics.
- Troubleshoot product-specific failures before escalating platform issues.

### Governance, Security, And Release Teams

These teams may not use Floe directly every day, but the docs should recognize
their role in enterprise adoption.

Responsibilities:

- Define required approvals.
- Define policy severity and exception handling.
- Control access to production environments.
- Review promotion evidence.
- Audit lineage, data contracts, and operational controls.

## Platform Environment Contract

The Platform Environment Contract replaces the informal idea of "handing
endpoints to Data Engineers". It is the stable contract a Data Engineer or CI
pipeline uses to target a Floe environment.

It should include:

- Environment name and purpose, such as `dev`, `staging`, or `prod`.
- Platform manifest reference or OCI artifact reference.
- Kubernetes namespace and release naming conventions.
- Approved plugin selections and defaults.
- Approved per-transform compute choices, if more than one compute target is
  available.
- Runtime spine, with Dagster recommended for the alpha path.
- Required service account, RBAC, and namespace boundaries.
- Secret reference conventions, not raw secrets.
- Artifact and image registry naming conventions.
- Observability and lineage contracts, such as OpenTelemetry and OpenLineage
  expectations.
- Promotion gates and required validation evidence.
- Operational contact and escalation path.

This contract can be stored as YAML, generated documentation, a platform repo
artifact, an internal developer portal entry, or an OCI artifact. Floe should
not require one enterprise implementation, but the docs should show a concrete
reference shape.

## Recommended Data Product Lifecycle

The enterprise lifecycle should be documented as a sequence that can map onto
many organizations' tooling.

1. Platform Engineer publishes or updates a Platform Environment Contract.
2. Data Engineer creates a data product repository from a template or guide.
3. Data Engineer writes `floe.yaml`, dbt models, tests, seeds, and contracts.
4. Local validation checks syntax and product-level rules where possible.
5. Pull request triggers CI.
6. CI runs dbt checks, Floe compilation, policy enforcement, contract checks,
   and docs/artifact validation.
7. CI builds a runtime artifact, typically a container image containing product
   code, compiled artifacts, dbt project files, and Dagster definitions for the
   recommended alpha runtime spine.
8. CI publishes artifacts to the organization's registry.
9. Release workflow requests approval according to the target environment.
10. Deployment happens through the organization's approved path.
11. Dagster or the selected runtime launches work on Kubernetes.
12. Runtime emits OpenLineage and OpenTelemetry evidence.
13. Data Engineer validates outputs and business metrics.
14. Platform Engineer and governance teams use the same evidence for support,
    audit, and promotion decisions.

## Deployment Patterns

### Recommended Alpha Pattern: Dagster Runtime Artifact

Dagster should be documented as the recommended alpha data product deployment
spine because the current Customer 360 runtime path already proves this shape.

Reference flow:

1. Compile the data product with Floe.
2. Generate a thin Dagster definitions shim from compiled artifacts.
3. Build a product runtime image.
4. Publish the image to the organization's registry.
5. Deploy or update the Dagster code location through the organization-approved
   deployment path.
6. Dagster runs product work through Kubernetes and emits lineage and telemetry.

The docs should call out what Floe standardizes:

- How product configuration is compiled.
- What artifact contract the runtime reads.
- How lineage and telemetry are expected to appear.
- How governance and validation evidence are collected.

The docs should also call out what the organization supplies:

- Registry.
- CI pipeline.
- Approval workflow.
- Deployment mechanism.
- Production access controls.

### Lower-Level Primitive: `floe-jobs`

`floe-jobs` should be documented as an implemented Helm primitive for teams
that need Kubernetes Job or CronJob wrappers. It should not be the main
self-service story until there is a complete, validated product deployment
workflow around it.

Appropriate positioning:

- Use for dbt, dlt, or custom jobs when your platform team has approved this
  deployment style.
- Use `platform.servicePrefix` and `platform.namespace` for service discovery.
- Keep it as an advanced or reference deployment option in the docs.
- Do not imply it replaces the recommended Dagster runtime path for alpha.

### Organization-Specific Handoffs

The docs should show examples, not mandates:

- GitOps handoff: CI opens or updates a GitOps PR containing image tag and
  values changes.
- CI deploy handoff: CI runs an approved deployment job after approval.
- Service catalog handoff: CI publishes artifact metadata and requests platform
  deployment.
- Release train handoff: product artifacts are promoted in scheduled batches.

All examples should point back to the same Floe contracts.

## Opinionation Boundaries Corrections

The public opinionation page should distinguish these states:

- Enforced standards: Iceberg, dbt-centric transformation, OpenTelemetry,
  OpenLineage, Kubernetes, declarative configuration.
- Alpha-supported defaults: implemented and validated default path.
- Implemented alternatives: code exists, but may require explicit validation for
  the user workflow.
- Planned or ecosystem examples: useful direction, not current product support.

Specific corrections:

- Do not list Datadog or Atlan as current defaults.
- Do not list cloud provider storage as a default unless it is actually the
  documented alpha default. S3-compatible storage exists as a plugin primitive,
  but the alpha guide should not imply every S3 production path is validated.
- Do not list unimplemented integrations as available alternatives without a
  planned or example label.
- The plugin catalog should be the implementation-truth source for current
  entry point categories and implemented reference plugins.
- Opinionation docs may mention target-state integrations, but only in a
  clearly labeled "planned or possible integrations" section.

## Compute Selection Policy

The current anti-pattern section is wrong if it forbids Data Engineers from
selecting compute per transform. Floe's schema and README already describe
approved per-transform compute selection.

Correct policy:

- Platform Engineers approve compute targets and choose defaults.
- Data Engineers may select compute per transform only from the approved list.
- Each transform should use the same compute choice across environments unless
  the platform contract defines an intentional, governed migration.
- Per-environment compute drift is still an anti-pattern.
- Arbitrary Data Engineer-selected compute outside the platform-approved list
  is still an anti-pattern.

Examples:

- Good: platform approves `duckdb` and `spark`; a data product uses `spark` for
  heavy staging and `duckdb` for a small mart.
- Bad: data product points one transform at an unapproved Snowflake account.
- Bad: development uses DuckDB while production uses Snowflake for the same
  transform without a governed migration contract.

## First-Use Documentation Model

### First Platform: Build A Minimal Platform

The Platform Engineer guide should teach how to build and validate a new
minimal Floe platform. It should not primarily point to Customer 360.

Required story:

1. Choose evaluation or real Kubernetes deployment.
2. Create/select a minimal platform values file.
3. Choose alpha-supported defaults.
4. Render the Helm chart.
5. Install the platform.
6. Verify Dagster, Polaris, MinIO, Marquez, Jaeger, OTel, and any enabled
   semantic/query service.
7. Publish a Platform Environment Contract for Data Engineers.
8. Optionally run Customer 360 as an advanced proof.

### First Data Product: Build A Hello Product

The Data Engineer guide should teach building a new minimal product from
scratch. It should not start by inspecting Customer 360.

Reference example: `hello-orders`.

Suggested contents:

- One seed file with a few orders.
- One staging model.
- One mart model with a simple business metric.
- `schema.yml` tests.
- `floe.yaml`.
- Platform reference.
- Floe compile output.
- Runtime artifact packaging step for Dagster.
- Deployment handoff example.
- Run and validation steps.
- Lineage and trace inspection.

Customer 360 should be linked afterward as: "Now run the full business demo."

## Documentation Deliverables

Add or rewrite these public docs:

- Recommended Enterprise Operating Model.
- Platform Environment Contract.
- Platform Engineers: Build Your First Platform.
- Data Engineers: Build Your First Data Product.
- Data Product Runtime Artifacts.
- Deployment Patterns.
- Promotion, Approvals, And Governance.
- Opinionation Boundaries.
- Plugin Catalog cross-links.

Update these existing docs:

- Platform Engineer index and first-platform guide.
- Data Engineer index and first-data-product guide.
- Customer 360 guide, to position it as advanced proof.
- Capability status, to label current and planned deployment features.
- README snippets that mention multi-compute and plugin alternatives.

## Validation Strategy

Docs validation should prevent the same drift from recurring.

Recommended guardrails:

- Public docs cannot call Datadog, Atlan, cloud storage, or other unvalidated
  integrations "default" unless capability status marks them alpha-supported.
- Public docs cannot forbid approved per-transform compute selection.
- Public docs cannot present `floe compile`, `floe run`, or
  `floe product deploy` as current unless implementation status changes.
- Public docs cannot make Customer 360 the first required data product path.
- Public docs must distinguish Dagster recommended alpha runtime from
  `floe-jobs` lower-level primitive.
- Public docs must not require DevPod or Hetzner outside contributor and
  release-validation pages.
- Source-doc checks should validate Starlight-published docs, not only old
  Markdown paths.

## Open Decisions For Implementation Planning

These decisions should be made before the implementation plan:

- Whether to create a checked-in `examples/hello-orders` data product or only
  document file snippets.
- Whether the hello product should be runnable through the existing Dagster
  image path immediately, or documented as the target shape with current alpha
  limitations.
- Whether to add a concrete Platform Environment Contract YAML example under
  `examples/` or keep it as documentation only.
- Whether the docs should expose `floe-jobs` in first-use guides or reserve it
  for advanced deployment patterns.
- Whether README should keep target-state multi-compute examples while clearly
  labeling implementation status, or move them into architecture docs.

## Acceptance Criteria

- A new reader understands how Platform Engineers and Data Engineers collaborate
  through contracts, not manual endpoint sharing.
- The first Platform Engineer guide creates a new platform path rather than
  only pointing to Customer 360.
- The first Data Engineer guide creates a new minimal data product rather than
  only inspecting Customer 360.
- Customer 360 is presented as an advanced proof and release-validation demo.
- Opinionation boundaries match current implementation status and capability
  labels.
- Compute anti-patterns match the approved per-transform compute model.
- Deployment docs explain Dagster as the recommended alpha runtime spine and
  `floe-jobs` as a lower-level primitive.
- Validation prevents unsupported defaults and unsupported lifecycle commands
  from returning to public docs.
