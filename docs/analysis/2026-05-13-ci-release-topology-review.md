# CI Release Topology Review

Date: 2026-05-13

## Summary

CI must keep fast PR confidence separate from release and live-provider confidence. The alpha release gate depends on the release manifest, so workflow package lists, artifact counts, version checks, and evidence requirements must be manifest-driven.

## Workflow Classification

| Workflow | Class | Alpha action |
|---|---|---|
| `ci.yml` | Fast PR | Keep required for PRs; add manifest validation as a fast structural check. |
| `e2e.yml` | Live validation | Activate through manual dispatch, merge queue, `run-e2e` label, or infrastructure path changes. |
| `release.yml` | Release | Validate manifest and attach release evidence before GitHub Release creation. |
| `pypi-publish.yml` | Release | Build/publish only manifest packages. |
| `helm-release.yaml` | Release | Enforce manifest Helm policy. |
| `helm-ci.yaml` | Merge confidence | Keep chart lint/render/schema validation. |
| `weekly.yml` | Scheduled maintenance | Keep expensive compatibility and dependency drift work scheduled. |
| `security.yml` | Scheduled/security | Keep separate from package publish. |
| `codspeed.yml` | Scheduled/performance | Keep performance signal non-blocking for alpha unless regressions are release-scoped. |

## Required Changes

- Add a fast manifest validation job to `ci.yml`.
- Activate `e2e.yml` only through explicit triggers and path-sensitive changes.
- Upload E2E artifacts on every live-validation run.
- Make release workflows fail before publish when manifest validation fails.
- Keep AWS live provider validation out of default PR CI and inside release or explicit manual lanes.

## Failure Taxonomy

| Class | Meaning | Release behavior |
|---|---|---|
| Product failure | Floe contract/runtime behavior failed | Blocks release. |
| Infrastructure failure | DevPod, Hetzner, Kind, GitHub Actions, or provider capacity failed before product assertion | Rerun allowed after infra evidence is recorded. |
| Credential/setup failure | Required AWS/DevPod/Hetzner setup missing or invalid | Blocks live gate until setup is fixed. |
| Cleanup failure | Product test passed but provider resources remain | Blocks release until cleanup proof is recorded. |
