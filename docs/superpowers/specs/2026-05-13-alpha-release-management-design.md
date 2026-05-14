# Alpha Release Management Design

## Status

Approved design for implementation planning.

Date: 2026-05-13

## Purpose

Define the work required to get Floe to an alpha release without publishing an
unsupported package set or relying on stale release assumptions. The alpha
release must be controlled by explicit version, release, distribution, CI, and
validation policy so future tags do not drift from the implemented system.

This design follows the alpha release readiness audit, which concluded that
Floe is not ready to tag until release workflow blockers are fixed.

## Goals

- Publish only packages with proven contract, integration, E2E, or accepted
  live validation evidence.
- Make the alpha package cutline explicit and machine-checkable.
- Use one repo-wide alpha release version for all alpha-published packages.
- Prevent tag workflows from publishing missing, extra, stale, or excluded
  packages.
- Align Python package publication, Helm release policy, GitHub releases, and
  release evidence.
- Review and optimize CI so PR, merge, release, and live-validation lanes have
  clear ownership, useful runtimes, and durable artifacts.
- Preserve the composition architecture: typed bindings, resolver validation,
  secret-free `CompiledArtifacts`, and renderer consumption of resolved
  deployment bindings.

## Non-Goals

- Do not publish packages excluded from the alpha cutline.
- Do not introduce independent per-plugin versioning for alpha.
- Do not adopt a full semantic-release or release-train platform before alpha.
- Do not change plugin contracts unless release validation proves a blocker.
- Do not replace the DevPod+Hetzner live validation lane with local-only
  validation.
- Do not add compatibility layers to cover stale release assumptions unless the
  audit proves they are necessary.

## Approved Direction

Use a manifest-driven release control plane.

A tracked release manifest becomes the source of truth for:

- release train and alpha version
- Python packages to publish
- packages explicitly excluded from alpha
- package caveats that require live or historical evidence
- Helm release policy
- required validation gates
- accepted historical evidence references
- generated evidence bundle expectations

Release workflows and validation scripts must consume or validate against this
manifest. Hardcoded package arrays and artifact counts should be removed or
guarded so they cannot drift from the manifest.

## Version Policy

Floe alpha uses a repo-wide release version.

The public Git tag should use human-readable SemVer pre-release syntax, for
example:

```text
v0.1.0-alpha.1
```

Python packages must use valid PEP 440 normalized versions derived from the tag,
for example:

```text
0.1.0a1
```

Helm chart versions must use the Helm-compatible version selected by the
manifest. If Helm cannot consume the exact Git tag spelling, the manifest must
record the normalized chart version explicitly.

Required invariants:

- The Git tag version, manifest version, Python package versions, and Helm
  chart versions must agree through explicit normalization rules.
- Every alpha-published Python package must declare the expected package
  version at release time.
- Excluded packages must not be published by the alpha tag.
- Previously published versions must not be reused.
- Version validation must fail before build or publish when any package is
  missing, extra, or mismatched.

Independent plugin versioning remains out of scope for alpha and needs a
separate design before adoption.

## Alpha Package Cutline

The alpha cutline is evidence-based. Packages are included only when current
main or accepted post-composition historical evidence proves the package works
through the implemented binding and composition model.

### Alpha Included

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

### Alpha Included With Caveat

These may be published for alpha only if the release gate records the required
root E2E or live-provider evidence:

- `floe-lineage-marquez`
- `floe-quality-gx`
- `floe-storage-aws-s3`
- `floe-catalog-glue`

### Excluded From Alpha

- `floe-alert-slack`
- `floe-alert-email`
- `floe-alert-alertmanager`
- `floe-alert-webhook`
- `floe-identity-keycloak`
- `floe-secrets-infisical`
- `floe-secrets-k8s`
- `floe-semantic-cube`
- `floe-dbt-fusion`
- `floe-telemetry-console`
- `floe-quality-dbt`

Excluded packages can move into a subsequent release only after they have a
concrete composition path and sufficient integration, E2E, or live validation
evidence.

## Release Manifest Model

The manifest should live at `release/floe-release.yaml`. It should be small,
reviewable, deterministic, and express these concepts:

```yaml
release:
  train: alpha
  git_tag: v0.1.0-alpha.1
  python_version: 0.1.0a1
  helm_version: 0.1.0-alpha.1

python_packages:
  publish:
    - path: packages/floe-core
      name: floe-core
      evidence: current-main
    - path: plugins/floe-catalog-glue
      name: floe-catalog-glue
      evidence: aws-live-required
  exclude:
    - path: plugins/floe-alert-slack
      name: floe-alert-slack
      reason: no-composed-alpha-runtime-path

helm:
  alpha_policy: explicit
  charts:
    - charts/floe-platform
    - charts/floe-jobs

validation:
  require_current_main_ci: true
  require_package_build_dry_run: true
  require_full_devpod_e2e: true
  require_aws_provider_live: true
  allow_accepted_historical_evidence: true
```

The manifest must not contain secrets, access keys, or provider credentials.

## Release Gates

### Pre-Tag Gate

Before an alpha tag is pushed:

- Manifest validates successfully.
- Manifest package list exactly matches the approved alpha cutline.
- Excluded packages are absent from publish jobs.
- All alpha-published packages have the expected normalized version.
- Package build dry-run succeeds for every alpha-published package.
- Current `main` CI is green and associated with the intended release SHA.
- Required integration evidence is current or explicitly accepted historical
  evidence.
- Full DevPod+Hetzner E2E passes from current `main`.
- AWS S3+Glue live provider validation passes or has accepted historical
  evidence plus fresh cleanup proof.
- AWS and Hetzner cleanup proof is recorded.
- Helm release policy is explicit: publish, paired tag, manual dispatch, or
  intentionally skipped for the alpha tag.

### Tag-Time Gate

When a release tag is pushed:

- The tag version must match the manifest release version.
- Release workflows must validate the manifest before building artifacts.
- PyPI build and publish jobs must derive package lists and counts from the
  manifest or fail if they still use stale hardcoded counts.
- GitHub Release notes must include the manifest version, package list, Helm
  policy, and evidence bundle reference.
- Helm release behavior must match the manifest policy.

### Post-Tag Gate

After publish:

- Verify the expected alpha package set is installable.
- Verify excluded packages were not published by this tag.
- Verify Helm charts were published or skipped exactly as declared.
- Verify generated evidence artifacts are attached or discoverable.
- Verify no DevPod, Hetzner, AWS S3, or AWS Glue resources remain from release
  validation.

## CI Optimization Workstream

CI must be reviewed as part of alpha readiness because release correctness
depends on the workflow topology, not only on package code.

The review should inventory every workflow, trigger, required check, matrix
lane, cache, artifact, and publishing path. Each lane must be classified by
purpose:

- Fast PR confidence: lint, formatting, typecheck, unit tests, contract tests,
  packaging metadata checks.
- Merge confidence: integration tests, build dry-runs, manifest validation,
  Helm render validation.
- Release confidence: release manifest validation, version normalization,
  exact artifact lists, trusted PyPI publishing, Helm release policy, GitHub
  Release evidence.
- Live validation: DevPod+Hetzner full E2E and AWS S3+Glue provider validation,
  with infrastructure failures separated from product failures.
- Scheduled maintenance: dependency/security scans, compatibility drift checks,
  benchmarks, and other expensive non-release-blocking jobs.

Optimization requirements:

- Remove or justify stale workflows and duplicate jobs.
- Replace hardcoded package counts with manifest-derived checks.
- Ensure required alpha release gates are visible as required checks or
  explicitly documented manual gates.
- Avoid running expensive live-provider work on every PR unless the changed
  paths require it.
- Preserve deep release validation at tag time or pre-tag time.
- Upload durable artifacts for test reports, build outputs, rendered Helm
  manifests, live validation logs, evidence bundles, and cleanup proof.
- Make failure taxonomy explicit for live validation: product failure,
  infrastructure failure, credential/setup failure, or cleanup failure.

The output of this workstream should be a CI map and a concrete optimization
plan before workflow edits begin.

## Workstreams

### 1. Release Manifest And Validator

Create the release manifest and validation command. The validator should check
manifest shape, package paths, package names, package versions, excluded
packages, tag normalization, Helm policy, and required evidence declarations.

### 2. Python Distribution Automation

Refactor PyPI build and publish logic so the alpha package set comes from the
manifest. The workflow must reject missing packages, extra packages, wrong
versions, wrong artifact counts, and excluded package publication.

### 3. Release Validation Automation

Automate the pre-tag release gate. This includes current-main CI confirmation,
package build dry-run, integration evidence checks, DevPod+Hetzner full E2E,
AWS S3+Glue live validation, and cleanup evidence recording.

### 4. Helm Release Policy

Resolve the mismatch between normal Python release tags and Helm release tags.
The alpha release must either publish Helm charts through a declared path or
explicitly skip Helm publication with a documented reason.

### 5. Docs And Maintainer Workflow

Update maintainer-facing docs so release steps match implemented automation.
Docs must cover version normalization, package cutline policy, pre-tag gates,
tag-time behavior, post-tag verification, manual dispatch rules, evidence
artifacts, and rollback/retry guidance.

### 6. CI And Release Workflow Optimization

Perform the full CI review described above, then implement targeted workflow
changes only after the CI map is understood. The goal is a faster, clearer PR
lane and a deeper, harder-to-bypass release lane.

## Evidence Requirements

The alpha release should produce or reference an evidence bundle containing:

- release manifest used for the tag
- package inventory and cutline validation output
- package build dry-run output
- unit, contract, integration, and E2E test summaries
- DevPod+Hetzner full E2E artifact path
- AWS S3+Glue live validation output or accepted historical evidence reference
- AWS cleanup proof for S3 prefixes and Glue databases
- Hetzner cleanup proof for servers, volumes, load balancers, floating IPs,
  SSH keys, and `devpod list`
- Helm lint/render/kubeconform output if Helm is in alpha scope
- PyPI artifact list and post-publish install verification
- explicit list of packages excluded from the tag

Historical evidence may be accepted for alpha only when the manifest records the
artifact reference, the evidence maps to the current composition model, and the
release gate also records fresh cleanup or freshness proof where relevant.

## Documentation Areas To Update

- `RELEASING.md`: release versioning, manifest, package cutline, gates, and tag
  flow.
- `.github/CI.md`: actual workflow topology, required checks, release lanes,
  and Helm tag behavior.
- Package publishing docs: alpha package set, excluded package policy, and
  future inclusion criteria.
- Helm docs: alpha chart release policy and version normalization.
- AWS provider test docs: required account setup, DevPod orchestration, live
  validation, evidence, and cleanup.
- Contributor docs: how contributors know whether a plugin is publishable for a
  given release train.
- Architecture docs where needed: reinforce that release automation consumes
  typed bindings and resolved deployment bindings, not plugin implementation
  details.

## Success Criteria

The alpha release is ready to tag when:

- The release manifest is committed and validates on `main`.
- The PyPI publish workflow can only publish the manifest alpha package set.
- Excluded packages cannot be published accidentally by the alpha tag.
- Version normalization is enforced across Git tag, Python packages, and Helm
  chart policy.
- Current `main` has passing release-required CI.
- Fresh or accepted integration, E2E, and live-provider evidence is recorded.
- DevPod+Hetzner and AWS cleanup evidence is recorded.
- Maintainer docs match the implemented workflow.
- The user can inspect one evidence bundle and understand exactly what was
  released, what was excluded, and why.

## Follow-On Planning Boundary

Implementation planning should split the work into PR-sized phases:

1. Manifest and validator.
2. PyPI workflow refactor and build dry-run validation.
3. CI topology review and optimization plan.
4. Release validation automation and evidence bundle.
5. Helm policy alignment.
6. Docs and maintainer workflow updates.
7. Release candidate validation run.

The release tag should not be created until these phases produce a passing
release gate on current `main`.
