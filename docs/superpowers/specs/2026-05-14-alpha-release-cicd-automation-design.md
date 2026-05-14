# Alpha Release CI/CD Automation Design

## Status

Approved design for implementation planning.

Date: 2026-05-14

## Purpose

Correct the alpha release automation model so Floe tags are created only after
all required release gates pass. A failed release candidate must leave no Git
tag, no GitHub Release, and no PyPI publication. Failures from release
preparation and weekly deep validation must create actionable GitHub issues
with logs, classification, and cleanup state.

This design supersedes the manual pre-tag evidence variable flow for normal
alpha releases. It keeps the manifest-driven alpha package cutline already
landed on `main`, but changes release orchestration so the workflow produces
release evidence instead of requiring maintainers to pre-populate repository
variables.

## Current System Map

The merged release model on `origin/main` has these important properties:

- `release/floe-release.yaml` is the release contract.
- The manifest declares `v0.1.0-alpha.1`, Python version `0.1.0a1`, Helm
  version `0.1.0-alpha.1`, 15 published Python packages, and 11 excluded
  packages.
- `.github/workflows/pypi-publish.yml` builds packages from
  `release/floe-release.yaml`; it no longer uses the stale hardcoded 24-package
  array.
- `.github/workflows/release.yml` is still tag-triggered for `v*.*.*`.
- The tag-triggered Release workflow validates the manifest and runs Kind
  integration tests, but it does not run full DevPod+Hetzner E2E or AWS
  S3+Glue live validation.
- The tag-triggered Release workflow currently expects
  `RELEASE_DEVPOD_ARTIFACT`, `RELEASE_AWS_LIVE_RESULT`, and
  `RELEASE_CLEANUP_RESULT` repository variables to exist before creating the
  GitHub Release.
- `.github/workflows/e2e.yml` does not run on every PR. It runs for merge
  queue, manual dispatch, PRs labeled for E2E, or PRs whose changed files match
  the infrastructure filter.
- `.github/workflows/weekly.yml` runs scheduled integration and E2E checks in
  GitHub-hosted Kind, but it does not own the formal release tag or publication
  decision.

The gap is not package scope. The gap is release orchestration: tag creation is
currently the trigger for release work, while the desired model is for tag
creation to be the output of a fully successful release gate.

## Goals

- Do not run long E2E validation on every PR.
- Create a release tag only after every required release gate passes.
- Do not create a GitHub Release until every required release gate passes.
- Do not publish to PyPI unless the tag and GitHub Release were produced by a
  successful release-preparation workflow.
- Keep alpha publication manifest-driven and limited to the 15 packages in
  `release/floe-release.yaml`.
- Automatically produce release evidence during release preparation.
- Automatically create or update GitHub issues for release-gate and weekly
  validation failures.
- Preserve cleanup discipline for DevPod, Hetzner, and AWS resources.
- Keep weekly deep validation as an early-warning lane, not as the formal
  release authority.

## Non-Goals

- Do not publish the 11 packages excluded from the alpha manifest.
- Do not add full E2E to the default PR path.
- Do not make weekly CI create tags, GitHub Releases, or PyPI publications.
- Do not replace the release manifest with workflow-local package arrays.
- Do not require manual repository variables for normal alpha release evidence.
- Do not implement a full release-train platform beyond the alpha gate.
- Do not change plugin contracts or package contents as part of this CI/CD
  control change.

## Recommended Approach

Introduce a manual `Prepare Release` workflow. This workflow is the only path
that creates the alpha release tag.

The maintainer dispatches the workflow with a requested version, for example:

```text
v0.1.0-alpha.1
```

The workflow checks out `origin/main`, validates the requested version against
`release/floe-release.yaml`, runs every required release gate, generates the
release evidence bundle, and only then creates the annotated tag and GitHub
Release. PyPI publication remains downstream of successful release metadata.

This approach avoids failed release tags. If a release candidate fails, the
failure is represented as a GitHub issue and workflow artifact rather than a
published release object.

## Alternatives Considered

### Tag-Triggered Gate With Deferred Publish

Pushing `v0.1.0-alpha.1` could run all gates and publish only if successful.

Pros:

- Conventional Git tag trigger.
- Simple mental model for package publishing.
- Compatible with the current tag-triggered Release workflow shape.

Cons:

- A failed candidate leaves a release tag behind.
- Retagging or deleting tags creates operational ambiguity.
- The user's desired invariant is stricter: no tag until all gates pass.

Decision: rejected for alpha.

### Weekly Evidence Plus Lightweight Tag Gate

Weekly CI could run deep validation and tagging could check that weekly
evidence is recent enough.

Pros:

- Faster release day.
- Lower release-day infrastructure risk.
- Good continuous signal between releases.

Cons:

- Requires freshness and commit-match rules.
- A weekly pass can drift from the exact release SHA.
- It makes the formal release gate dependent on prior workflow state.

Decision: keep weekly as early warning only, not release authority.

### Prepare Release Creates Tag After Success

The release workflow runs first and creates the tag only after every gate
passes.

Pros:

- No failed tags.
- No GitHub Release until all gates pass.
- Release evidence is generated by automation.
- PyPI publication can trust release metadata produced by the gate.
- Long tests stay out of normal PR CI.

Cons:

- Requires GitHub Actions permissions to create annotated tags and releases.
- Requires failure issue automation.
- Requires careful separation between candidate validation and final publish.

Decision: recommended.

## Target Workflow Topology

### Pull Request CI

PRs remain fast by default:

- lint and formatting
- typecheck
- unit tests
- contract tests
- release manifest validation when release files change
- security scan
- docs checks where relevant

Full E2E remains opt-in for PRs through one of:

- `run-e2e` label
- merge queue
- manual dispatch
- infrastructure file filter when intentionally enabled

### Weekly Deep Validation

Weekly CI remains scheduled and manually dispatchable. It should run:

- Kind integration tests
- standard E2E
- destructive E2E after standard E2E success
- AWS S3+Glue live validation when credentials and cost controls are available
- cleanup verification
- dependency audit and security checks

Weekly failures must create or update a GitHub issue. Weekly does not create
tags, GitHub Releases, or PyPI publications.

### Prepare Release

The new release-preparation workflow is manually dispatched by a maintainer. It
takes:

- `version`: required, for example `v0.1.0-alpha.1`
- optional `dry_run`: default `false`; when `true`, run all gates but do not
  create tag, GitHub Release, or trigger PyPI publication

Release preparation runs from `origin/main`, not from a feature branch.

Required jobs:

1. `resolve-candidate`
   - Fetch `origin/main`.
   - Resolve the exact release SHA.
   - Validate clean version input.
   - Validate the requested version matches `release/floe-release.yaml`.
   - Verify no matching local or remote tag already exists.

2. `static-and-contract-gates`
   - Run the CI-equivalent fast checks needed before expensive gates.
   - Validate the release manifest.
   - Verify the alpha package cutline is exactly manifest-driven.
   - Verify no stale hardcoded publish-all package arrays exist in release
     workflows.

3. `package-build-dry-run`
   - Run `testing.release.cli build` for the manifest package set.
   - Assert 15 wheels and 15 sdists for the current alpha manifest.
   - Upload build artifacts for inspection, but do not publish.

4. `kind-integration`
   - Run the current release integration test path.
   - Upload logs and JUnit artifacts.

5. `full-e2e`
   - Run full E2E.
   - Standard E2E must pass before destructive E2E starts.
   - Upload logs, JUnit artifacts, and cluster diagnostics.

6. `aws-live`
   - Run AWS S3+Glue live validation when `require_aws_provider_live` is true.
   - Use configured AWS test-account inputs.
   - Ensure remote environment files are scrubbed and not uploaded.
   - Upload sanitized logs only.

7. `cleanup-verify`
   - Verify DevPod workspace state where DevPod is used.
   - Verify Hetzner current-run servers, volumes, load balancers, floating IPs,
     and SSH keys are absent.
   - Verify AWS S3 run prefix and Glue run database are absent.
   - Fail the release if cleanup fails, even when product tests passed.

8. `release-evidence`
   - Generate `release-evidence.md` from actual workflow results.
   - Include release SHA, manifest path, package cutline, E2E artifact links,
     AWS live result, and cleanup result.
   - Redact credentials and reject publishable evidence containing placeholders.

9. `create-release`
   - Runs only when every prior gate succeeds and `dry_run` is false.
   - Create an annotated tag for the requested version at the validated release
     SHA.
   - Push the tag.
   - Create the GitHub Release with `release-evidence.md`.
   - Upload a `release-metadata` artifact containing tag, SHA, version, and
     manifest package list.

10. `failure-issue`
    - Runs when any gate fails.
    - Creates or updates a GitHub issue.
    - Does not run on successful candidates.

## Failure Issue Behavior

Release-preparation and weekly deep-validation failures should use the same
issue-writing helper.

Issue labels should include:

- `ci-failure`
- `release-gate` or `weekly-validation`
- one or more classification labels:
  - `product-failure`
  - `infrastructure-failure`
  - `credential-setup-failure`
  - `cleanup-failure`
  - `release-tooling-failure`

The issue title should be deterministic enough to deduplicate repeated
failures. Example:

```text
Release gate failed: v0.1.0-alpha.1 full-e2e infrastructure failure
```

The issue body must include:

- workflow run URL
- commit SHA
- requested version, when applicable
- failed gate name
- failure classification
- short log excerpt
- artifact links
- cleanup status
- whether tag, GitHub Release, and PyPI publish were skipped
- next recommended action

When an open issue for the same workflow, version, and gate already exists, the
workflow should add a comment instead of opening a duplicate issue. A later
successful run may comment on the issue with the passing run URL, but it should
not close the issue automatically unless the team explicitly wants that
behavior later.

## Publication Boundary

Alpha publication must remain manifest-driven.

`release/floe-release.yaml` is the only source of truth for Python package
publication. Workflows must not define their own package arrays or expected
counts.

For `v0.1.0-alpha.1`, publication is limited to:

- `floe-core`
- `floe-iceberg`
- `floe-orchestrator-dagster`
- `floe-catalog-polaris`
- `floe-storage-minio`
- `floe-compute-duckdb`
- `floe-dbt-core`
- `floe-ingestion-dlt`
- `floe-telemetry-jaeger`
- `floe-rbac-k8s`
- `floe-network-security-k8s`
- `floe-lineage-marquez`
- `floe-quality-gx`
- `floe-storage-aws-s3`
- `floe-catalog-glue`

The 11 manifest-excluded packages must not be built or published by alpha
release automation.

Regression tests should assert that:

- `pypi-publish.yml` consumes the release metadata and manifest package list.
- No hardcoded publish-all array is present.
- Built wheel and sdist counts derive from manifest publish count.
- Excluded package names do not appear in publish commands.

## PyPI Publish Model

PyPI publishing remains downstream of the successful release gate.

The publish workflow should run from successful `Prepare Release` completion or
from the GitHub Release metadata artifact produced by that workflow. It should:

- download verified release metadata
- check out the verified release SHA, not a mutable tag, for building
- validate the manifest against the release tag
- build only manifest packages
- verify artifact counts against the manifest
- publish only after the GitHub Release exists
- publish through the configured `pypi` environment

The workflow must reject manual publishing. Manual dispatch may remain as a dry
run only.

## Helm Release Model

Helm behavior remains explicit in the release manifest.

For alpha, `helm.alpha_policy: publish` means Helm chart publication is part of
release automation. Helm chart version must match the manifest Helm version and
the requested release version after normalization.

Helm publication should occur only after the same successful release-preparation
gate, not from an independent stale tag path. If separate Helm tags remain for
compatibility, they must be created by automation after the primary release gate
passes and must enforce tag/version parity.

## Evidence Model

The release workflow should generate evidence instead of consuming manually
configured evidence variables.

Evidence must include:

- release SHA
- requested version
- manifest package publish and exclude lists
- CI/static gate results
- package build dry-run result and artifact counts
- Kind integration result
- full E2E result
- AWS S3+Glue result when required
- cleanup verification result
- links to sanitized artifacts

Evidence must not include:

- AWS access keys
- AWS secret keys
- session tokens
- bearer tokens
- remote env files
- kubeconfigs with credentials
- provider secrets

The existing `testing.release.evidence` redaction and publishability checks
should be reused and extended as needed.

## Cleanup Model

Cleanup is a release gate, not a courtesy step.

The release candidate fails if current-run resources remain after cleanup.
Required cleanup checks:

- DevPod workspace inventory
- Hetzner servers
- Hetzner volumes
- Hetzner SSH keys
- Hetzner load balancers
- Hetzner floating IPs
- AWS S3 run prefix
- AWS Glue run database and tables

Failure issue bodies must distinguish product failures from cleanup failures.
If product tests pass but cleanup fails, the issue should state that the product
lane passed and the release remains blocked only by cleanup.

## Security And Permissions

The prepare-release workflow needs explicit permissions:

- `contents: write` to create tags and GitHub Releases
- `actions: read` to collect artifacts and metadata
- `issues: write` to create or update failure issues

AWS credentials must come from existing provider-test configuration and must
not be committed, uploaded, or written into release evidence.

PyPI credentials stay scoped to the `pypi` environment. The long-term target is
trusted publishing/OIDC, but this design does not require that migration before
alpha if the existing token path is otherwise configured.

## Documentation Updates

Update release docs so maintainers do not push tags directly.

Required docs changes:

- `RELEASING.md`
  - Replace direct `git tag` quick start with `gh workflow run prepare-release`.
  - Explain that tags are created only by the successful release workflow.
  - Document failed candidate issue behavior.
  - Document weekly deep-validation issue behavior.

- `.github/CI.md`
  - Add CI lane ownership: PR, merge queue, weekly, prepare release, publish.
  - Explain which lanes run long E2E.

- `docs/releases/v0.1.0-alpha.1-checklist.md`
  - Replace manual evidence variable setup with automated evidence generation.
  - Keep the alpha package cutline explicit.

## Test Strategy

Unit and structural tests should cover workflow behavior without executing
GitHub Actions.

Required tests:

- prepare-release workflow exists and is `workflow_dispatch` only
- prepare-release has no tag trigger
- prepare-release validates manifest version against requested version
- prepare-release creates the tag only in the final success job
- prepare-release creates no GitHub Release before all gate jobs succeed
- prepare-release has a failure issue job with `if: failure()`
- failure issue job has `issues: write`
- PyPI publish consumes release metadata and manifest package list
- PyPI publish cannot publish on manual dispatch
- release/tag workflows cannot publish hardcoded 24-package arrays
- weekly workflow has failure issue handling
- release evidence rejects placeholders and failed statuses
- cleanup verification classifies cleanup failures separately from product and
  infrastructure failures

Live validation of the implementation should use a dry run first, then a real
release-preparation run for alpha.

## Migration Plan

1. Add workflow helper scripts for release candidate resolution, evidence
   aggregation, cleanup verification, and failure issue creation.
2. Add or replace workflow structural tests.
3. Add the new `prepare-release.yml` workflow.
4. Change `release.yml` from tag authority to release creation helper or retire
   it if `prepare-release.yml` owns GitHub Release creation directly.
5. Update `pypi-publish.yml` to trust only successful prepare-release metadata.
6. Update weekly workflow to create or update failure issues.
7. Update release documentation.
8. Run local workflow structural tests and manifest build dry-run.
9. Push a PR and verify normal CI.
10. Run prepare-release with `dry_run: true`.
11. Run prepare-release for `v0.1.0-alpha.1` when dry run and credentials are
    confirmed.

## Open Questions For Implementation

- Whether to keep a separate `release.yml` workflow as a thin GitHub Release
  creator or consolidate release creation into `prepare-release.yml`.
- Whether weekly success should comment on and close prior failure issues or
  only comment with recovery evidence.
- Whether full DevPod+Hetzner E2E should run inside GitHub Actions or through
  an existing remote DevPod wrapper invoked by GitHub Actions.
- Whether Helm charts should be published by the same workflow or by a
  downstream workflow that consumes prepare-release metadata.

## Acceptance Criteria

- Maintainers can no longer accidentally publish alpha by pushing a tag before
  deep gates pass.
- A successful prepare-release run creates the annotated tag and GitHub Release.
- Failed prepare-release runs create no tag, no GitHub Release, and no PyPI
  publication.
- Failed prepare-release and weekly runs create or update GitHub issues with
  logs and failure classification.
- PyPI publishes only the manifest-declared alpha packages.
- Weekly validation remains available as long-running early warning.
- PR CI remains fast by default and does not run full E2E on every PR.
