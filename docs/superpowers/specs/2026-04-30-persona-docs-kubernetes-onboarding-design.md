# Persona-Aligned Docs And Kubernetes Onboarding Design

Status: Approved design for implementation planning
Date: 2026-04-30
Author: Codex

## Summary

Floe documentation must separate product onboarding from contributor release
validation. The alpha docs currently blur those concerns by presenting DevPod
and Hetzner as the first platform path, while also publishing contributor test
strategy under general guides. The corrected model is:

- **Platform Engineers** deploy, configure, secure, upgrade, and validate Floe
  platforms on Kubernetes.
- **Data Engineers** build, validate, deploy, and operate data products on an
  existing Floe platform.
- **Floe Contributors** develop Floe itself, run heavyweight validation, and
  maintain release evidence.

The product deployment promise should be "bring any Kubernetes cluster", not
"use Hetzner". DevPod + Hetzner remains useful for Floe contributors because it
gives us a repeatable high-memory validation lane, but it should not be the
primary product onboarding path.

## Goals

- Make the public docs follow the Floe persona model: Platform Engineers, Data
  Engineers, and Floe Contributors.
- Make Platform Engineer onboarding provider-neutral and centered on an
  existing Kubernetes context.
- Keep cloud-provider examples optional and clearly marked as examples, not
  requirements.
- Move DevPod + Hetzner into contributor and release-validation documentation.
- Fix Starlight heading duplication across generated docs.
- Replace overstated deployment claims with current-state, tested capability
  statements.
- Separate user validation guidance from contributor test strategy.
- Add docs validation rules that prevent the same provider and persona drift
  from returning.

## Non-Goals

- Claim production readiness for every Kubernetes distribution.
- Build and validate full EKS, GKE, AKS, and Hetzner deployment guides in this
  single pass.
- Turn DevPod into a product deployment abstraction.
- Document Data Mesh multi-cluster operations as alpha-supported unless the
  implementation and E2E validation exist.
- Rewrite every deep architecture page before the alpha docs are usable.

## Current-State Assessment

The current docs contain several structural problems:

- `docs/get-started/first-platform.md` is framed as first-platform onboarding
  but requires Hetzner credentials, DevPod, a repo checkout, and
  `make docs-validate`. That is contributor/release-validation behavior.
- `docs/operations/devpod-hetzner.md` is valid operational documentation for
  our remote workspace, but it belongs under Floe contributor documentation.
- `docs/guides/deployment/index.md` lists Docker Compose and Data Mesh as
  deployment options even though Docker Compose is not supported and the Data
  Mesh deployment path is not implemented as documented.
- `docs/guides/deployment/data-mesh.md` references `charts/floe-domain` and
  product-registration commands that are not present as an alpha deployment
  lane.
- `docs/guides/testing/index.md` is a contributor testing strategy page, not a
  Data Engineer or Platform Engineer validation guide.
- `docs-site/scripts/sync-docs.mjs` derives Starlight frontmatter titles from
  Markdown H1 headings but leaves those H1 headings in generated page content,
  causing duplicated page titles.

## Information Architecture

The docs site should be organized around personas first, with Diataxis-style
content types inside each persona path where useful.

### Start Here

Purpose: orient new readers without assuming their role.

Content:

- What Floe is.
- What Floe is not.
- Alpha capability status.
- Persona selector:
  - "I deploy and operate platforms" -> Platform Engineers.
  - "I build data products" -> Data Engineers.
  - "I contribute to Floe" -> Floe Contributors.

### Platform Engineers

Purpose: help someone deploy and operate Floe on their Kubernetes estate.

Content:

- Deploy your first Floe platform.
- Configure a platform manifest.
- Configure secrets, object storage, catalog, observability, and lineage.
- Install with Helm on any conformant Kubernetes cluster.
- Validate platform health and service UIs.
- Run the Customer 360 platform validation path.
- Upgrade, rollback, and troubleshoot.
- Optional cloud examples: EKS first if we validate it, then GKE, AKS, and
  Hetzner as examples.

### Data Engineers

Purpose: help someone use an existing Floe platform to ship data products.

Content:

- Build your first data product.
- Understand `floe.yaml`.
- Validate product configuration.
- Compile and deploy a data product using the supported alpha commands.
- Run a pipeline and inspect outputs.
- Query business results through the semantic/query layer.
- Inspect lineage, traces, and quality signals.
- Troubleshoot product failures without needing contributor tooling.

### Floe Contributors

Purpose: help maintainers and open-source contributors work on Floe itself.

Content:

- Development environment setup.
- DevPod remote workspace.
- DevPod + Hetzner release-validation lane.
- Local Kind development.
- Repository test strategy.
- CI and pre-push hooks.
- Docs authoring and docs validation.
- Release validation checklist.

### Architecture And Reference

Purpose: explain how Floe works and provide precise technical reference.

Content:

- Four-layer model.
- Plugin system.
- Manifest and data product contracts.
- Compiled artifacts.
- Helm values and chart references.
- CLI reference.
- Current vs planned capability matrix.
- Data Mesh architecture clearly labeled as implemented primitives, planned
  operations, or alpha-supported paths.

## Platform Engineer Onboarding

The Platform Engineer golden path should not depend on DevPod. It should assume
only:

- A Kubernetes cluster reachable through the active `kubectl` context.
- Helm installed locally.
- Access to the required secrets or secret-management integration.
- A Floe platform manifest and deployment values.

The guide should be linear and outcome-oriented:

1. Check the active Kubernetes context and cluster prerequisites.
2. Generate or select a minimal alpha platform manifest.
3. Configure storage, catalog, lineage, observability, and secrets.
4. Render and validate Helm values before installation.
5. Install or upgrade Floe with Helm.
6. Wait for platform services to become healthy.
7. Open Dagster, object storage, Polaris, Marquez, Jaeger, and the
   semantic/query endpoint.
8. Run the Customer 360 validation path.
9. Capture the expected validation evidence.
10. Clean up or leave the platform running.

The guide should distinguish clearly between evaluation and real deployment:

- **Evaluation**: local Kind, small resource footprint, non-production
  credentials, fast cleanup.
- **Real Kubernetes deployment**: user-provided cluster, persistent storage,
  explicit secrets, ingress/TLS choices, and durable object storage.
- **Cloud examples**: provider-specific appendices only after each example is
  validated.

## Data Engineer Onboarding

The Data Engineer golden path starts after a Platform Engineer has deployed
Floe. It should not mention DevPod, Hetzner, cluster setup, contributor tests,
or release validation unless linking to contributor docs.

The guide should be linear:

1. Confirm access to a Floe platform.
2. Create or open a data product project.
3. Configure `floe.yaml`.
4. Validate the product contract and product configuration.
5. Compile the product into Floe artifacts.
6. Deploy or run the product using supported alpha commands.
7. Verify data outputs.
8. Query business metrics through the semantic/query layer.
9. Inspect lineage in Marquez and traces in Jaeger.
10. Troubleshoot common Data Engineer failure modes.

This path should use Customer 360 as the first teaching example because it
proves business value, not only infrastructure readiness.

## DevPod Recommendation

DevPod + Hetzner is not fit for purpose as the primary product onboarding path
because it:

- Requires a Floe repository checkout and repo-local `make` targets.
- Requires Hetzner credentials.
- Hides the real deployment contract behind a contributor workspace.
- Couples the first-platform story to our cost choice rather than the user's
  infrastructure.
- Encourages readers to treat release-validation infrastructure as product
  deployment infrastructure.

DevPod should stay, but with a narrower promise:

- **Contributor remote development**: use when local hardware cannot run the
  full stack comfortably.
- **Release validation**: use to produce repeatable high-memory evidence before
  alpha tags.
- **Optional sandbox**: if documented for non-contributors later, it must be
  clearly marked as an evaluation sandbox and must not be required for
  deployment.

The implementation should rename or reframe DevPod docs and Makefile help text
so the provider-specific nature is explicit. Provider variables can remain, but
the docs should not imply that DevPod provider abstraction is the product
deployment model.

## Starlight Heading Design

Starlight renders frontmatter `title` as the page's top-level heading. Our
source docs should keep Markdown H1 headings for GitHub readability, but the
generated Starlight content should not render that same H1 as body content.

The sync pipeline should:

1. Derive `title` from explicit frontmatter title or the first Markdown H1.
2. Add Starlight frontmatter when missing.
3. Remove the first Markdown H1 from generated Starlight content when it matches
   the derived page title.
4. Preserve all H2 and lower headings.
5. Include tests that prove generated pages do not duplicate the title.

This fixes the symptom without forcing every source Markdown file to abandon
standard repository Markdown structure.

## Capability Truth Model

Every deployment and architecture page should state capability level:

- **Alpha-supported**: implemented, documented, and validated in the release
  lane.
- **Implemented primitive**: code or schema exists, but no complete user
  workflow is promised.
- **Example**: provider-specific illustration, not a requirement.
- **Planned**: architectural direction that must not be presented as working
  deployment guidance.

Data Mesh should be treated as implemented primitives plus architecture unless
we add and validate the missing operational pieces. A Data Mesh deployment page
can exist only if it is explicit about this status, or it should move to
architecture/roadmap until the deployment path is real.

## Documentation Quality Gates

Docs validation should prevent the same drift from recurring:

- Generated Starlight pages must not duplicate page titles as first body H1s.
- Public Platform Engineer and Data Engineer docs must not say Hetzner is
  required.
- DevPod + Hetzner language must stay under Floe Contributor or release
  validation sections.
- Deployment docs must not reference missing charts, missing Makefile targets,
  or commands that do not exist.
- Data Mesh operations must not be marked alpha-supported unless linked to
  implementation and validation evidence.
- Internal contributor standards such as `.claude` rules must not be linked as
  user-facing product documentation.

The validation can start as targeted script checks and evolve into richer docs
metadata later.

## Validation Strategy

Implementation should be validated at three levels:

- **Docs build validation**: Starlight sync, navigation validation, and site
  build.
- **Docs content validation**: targeted checks for duplicated headings,
  provider coupling, missing commands, missing charts, and persona drift.
- **Onboarding validation**: dry-run or real walkthrough of the Platform
  Engineer path without DevPod, followed by the Data Engineer Customer 360 path
  against the deployed platform.

The final alpha validation lane can still use DevPod + Hetzner for capacity,
but the commands being validated should reflect product deployment contracts
where possible: Kubernetes context, Helm, manifests, and Floe CLI behavior.

## Rollout Plan

The implementation should proceed in this order:

1. Fix Starlight heading generation and add tests.
2. Restructure navigation around Platform Engineers, Data Engineers, Floe
   Contributors, and Architecture/Reference.
3. Rewrite first-platform onboarding for Platform Engineers using "bring any
   Kubernetes cluster".
4. Move DevPod + Hetzner to contributor/release-validation docs.
5. Split testing docs into Platform/Data Engineer validation and Floe
   Contributor test strategy.
6. Correct deployment docs to remove unsupported Docker Compose, missing
   commands, and overstated Data Mesh operations.
7. Add docs quality gates for provider coupling and capability truth.
8. Run docs validation and capture remaining onboarding gaps as GitHub issues.

## Open Decisions

- Which managed Kubernetes provider should get the first optional cloud example
  after the provider-neutral path is stable? EKS is the recommended first
  candidate because it is common in enterprise environments, but it should not
  block the provider-neutral alpha path.
- Should the docs site show persona sections as top-level navigation, or should
  "Start Here" route users into persona-specific trails while keeping reference
  sections top-level? The recommended implementation is persona sections as
  top-level navigation for alpha clarity.
