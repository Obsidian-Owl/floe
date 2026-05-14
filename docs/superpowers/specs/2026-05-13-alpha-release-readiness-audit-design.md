# Alpha Release Readiness Audit Design

## Purpose

This audit determines which Floe packages are allowed into the alpha tagged
release. The release cutline is evidence based: a package ships only when the
current implementation has recent post-composition validation proving it works
through the binding and composition model.

The audit is not a release tag, a publishing run, or a workflow-fix
implementation. It is the design for a rigorous release-readiness review that
produces a go/no-go package cutline and the evidence needed before tagging.

## Source Of Truth

Run the audit from `main` only. Treat current `main` as the implemented system
after the plugin composition and provider validation work has merged.

Recent historical evidence may count when it was captured after the
composition/binding model landed on `main`, especially the PR sequence covering
composition/provider readiness and validation:

- #332 AWS S3 and Glue core composition contracts
- #333 AWS S3 storage plugin
- #334 AWS Glue catalog plugin
- #335 provider validation lane hardening
- #336 AWS provider live validation uplift
- #337 DevPod remote AWS env file scrub

Historical evidence must name the commit, PR, workflow, command, or artifact
that produced it. If evidence cannot be traced, it does not count.

## Release Gate

The alpha release must use an explicit package cutline. The repository may
contain more packages than the alpha release publishes.

Each distributable package receives one decision:

- `Alpha Included`: sufficient direct evidence exists for alpha.
- `Alpha Included with Caveat`: the package is required by the alpha path and
  has meaningful indirect E2E proof, but package-local validation remains thin.
- `Excluded from Alpha`: the package exists in the repo but must not be
  published in the alpha tag.
- `Blocked`: the package is intended for alpha but is missing required evidence
  or release plumbing.

Minimum inclusion evidence:

- package metadata is correct and intentionally included in release config
- public plugin/core contracts are covered
- integration or E2E coverage proves the package works in the composed system
- `CompiledArtifacts` remain secret-free
- capabilities, requirements, typed bindings, and resolver validation own
  cross-plugin contracts
- Helm/renderers consume resolved deployment bindings instead of rediscovering
  plugin config
- no plugin depends on another plugin's implementation details
- release workflow can build and publish exactly the intended package set

Provider packages that depend on real external services require live-service
evidence. For the AWS provider path, S3 and Glue need live AWS validation, not
only mocked or structural tests.

## Workstreams

### 1. Release Artifact Inventory

Map every artifact that a tag could create or imply:

- Python packages under `packages/*` and `plugins/*`
- PyPI publish workflow package list and artifact count assertions
- Helm charts and chart release triggers
- demo/Docker artifacts that alpha users rely on
- release documentation and GitHub workflow documentation
- tag trigger behavior for `v*.*.*`, `helm-v*`, and `charts-v*`

The audit must explicitly reconcile observed repo state with release docs. For
example, current `main` has 26 distributable package projects, while the PyPI
workflow still has a 24-package list. The audit must decide whether that is a
release-blocking mismatch or an intentional alpha exclusion.

### 2. Package Evidence Ledger

Create a package-by-package ledger. For each package, record:

- package path and package name
- version and `floe-core` compatibility constraint
- entry point group and plugin category, if applicable
- whether it appears in the alpha publish list
- direct contract tests
- package-local unit/integration/E2E tests
- root contract/integration/E2E tests that exercise it
- recent CI, PR, DevPod, or live-service evidence
- whether evidence is direct or indirect
- remaining risk and final cutline decision

The ledger is the main audit artifact. It should make it obvious why a package
is included, excluded, or blocked.

### 3. Deep Validation Gate Review

Review whether release automation actually enforces the alpha bar:

- `ci.yml`
- `release.yml`
- `pypi-publish.yml`
- `helm-release.yaml`
- `helm-ci.yaml`
- `weekly.yml`
- pre-push hooks
- DevPod remote validation
- AWS live provider validation

The audit must identify mismatches between comments/docs and executed gates. A
notable current risk is that `release.yml` describes E2E validation but only
runs quick validation plus integration tests. The alpha gate must not rely on
comments that are not backed by workflow steps.

### 4. Composability And Security Review

For alpha-included packages, verify architectural constraints:

- cross-plugin contracts are expressed through capabilities, requirements,
  typed bindings, and resolver validation
- plugins do not know one another's implementation details
- no compatibility path is kept unless the audit proves it is necessary
- stale compatibility code is identified as release debt
- secret values never enter `CompiledArtifacts`
- deployment renderers consume resolved deployment bindings
- live provider credential transfer does not leak into artifacts or durable
  workspace files

This review is evidence based. Findings should cite code, tests, workflows, or
runtime artifacts.

### 5. Runtime Evidence Refresh Plan

Separate accepted historical evidence from fresh current-main evidence.

Historical evidence may count only when it is post-composition and traceable.
Fresh evidence should still be captured where current release confidence
depends on it. Candidate fresh validation:

- current `main` CI status
- local package build dry run for the alpha cutline
- integration tests
- `make test-e2e-full` through the real DevPod + Hetzner lane
- `make devpod-test-aws-provider` for the AWS S3 + Glue provider lane
- AWS cleanup verification after live runs
- DevPod/Hetzner cleanup verification after remote runs

The audit must separate product failures from infrastructure failures. Hetzner
capacity, DevPod tunnel teardown noise, or cloud-provider availability must be
reported differently from Floe regressions.

### 6. Release Readiness Report

After executing the audit, produce a report with:

- final package cutline
- evidence ledger
- release workflow gaps
- blocker list
- excluded-package rationale
- required changes before tagging
- go/no-go recommendation

The report should be suitable for deciding whether to tag alpha or open
specific hardening PRs first.

## Evidence Model

For every package, collect evidence at five levels.

### Static Package Evidence

Inspect `pyproject.toml`, package version, dependency constraints, entry points,
package data, `py.typed`, README, importability, and release inclusion.

### Contract Evidence

Map root and package contract tests proving public APIs, plugin ABC compliance,
typed bindings, compiled artifact schema behavior, secret references, and
cross-package contracts.

### Integration Evidence

Map service-backed or Kubernetes-backed tests proving the package talks to its
real substrate. Examples include Polaris, MinIO via S3-compatible protocol,
Dagster, Helm/Kubernetes, and AWS live services.

### E2E Evidence

Map full workflow proof through the composed system: compile, deploy,
materialize or ingest, observe lineage/telemetry, validate outputs, and handle
destructive or lifecycle paths.

### Release Evidence

Map package build, wheel/sdist count, install smoke, tag workflow behavior,
publish inclusion/exclusion, Helm chart packaging, and current-main CI status.

The audit must not merely count tests. It must record command or workflow run,
commit SHA, package coverage, test file or artifact path, pass/fail/blocked
result, directness of evidence, and remaining risk.

## Initial Cutline Hypothesis

This hypothesis guides the audit but does not decide the release. Packages can
move between buckets when evidence supports the move.

### Likely Alpha Included

- `floe-core`
- `floe-iceberg`
- `floe-orchestrator-dagster`
- `floe-catalog-polaris`
- `floe-storage-minio`
- `floe-compute-duckdb`
- `floe-dbt-core`
- `floe-ingestion-dlt`
- `floe-lineage-marquez`
- `floe-telemetry-jaeger`
- `floe-quality-gx`
- `floe-rbac-k8s`
- `floe-network-security-k8s`

These appear tied to the current demo/platform/E2E paths or have substantial
contract and integration evidence.

### Likely Alpha Included With Provider-Specific Evidence

- `floe-storage-aws-s3`
- `floe-catalog-glue`

These should be included only if the audit accepts the recent live AWS S3 +
Glue evidence and verifies release workflow inclusion.

### Likely Excluded From Alpha Unless Evidence Proves Otherwise

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

These may remain valid repo packages, but alpha release inclusion requires
demonstrated composed runtime value, not just unit tests or plugin
registration.

## Required Audit Outputs

### Alpha Readiness Spec

This document is the design spec for the audit.

### Release Readiness Report

The audit execution should produce a follow-up report under `docs/analysis/`.
The report should include the final cutline, evidence ledger, blockers,
workflow gaps, and go/no-go recommendation.

### Implementation Plan

After this design is approved, create a detailed implementation plan for
executing the audit. The plan may include code or workflow fixes only after the
audit evidence identifies them.

## Out Of Scope

- tagging the alpha release
- publishing packages
- changing release workflows before the audit proves the required change
- adding compatibility layers to make weak packages releasable
- expanding feature scope of excluded plugins
- treating local-only smoke tests as sufficient E2E proof
- mutating active feature worktrees

## Acceptance Criteria

The audit design is complete when it enables an execution plan that can:

1. identify every distributable package and release artifact on current `main`
2. produce a package-by-package alpha decision with traceable evidence
3. verify release workflows publish exactly the intended package cutline
4. distinguish direct, indirect, stale, and missing validation evidence
5. require live evidence for live provider packages
6. separate infrastructure failures from product failures in remote validation
7. identify release-blocking mismatches before any alpha tag is created
