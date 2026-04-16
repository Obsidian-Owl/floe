# Spec: E2E Five Failures Fix

## AC-1: Materialization test runs full dbt build (F1/F2)

**Given** the `test_trigger_asset_materialization` test in `test_compile_deploy_materialize_e2e.py`
**When** it launches a Dagster run via GraphQL `launchRun` mutation
**Then** the `assetSelection` parameter is NOT included in the selector
**And** the run materializes ALL assets in the job (seeds, staging, marts)
**And** the `seed_observability` fixture in `conftest.py` also omits `assetSelection`
**And** unused `asset_path` variables are removed or prefixed with `_`

**Boundary**: If `_discover_repository_for_asset` return value changes shape, the
test must still construct a valid `selector` with only `repositoryName`,
`repositoryLocationName`, and `pipelineName`.

## AC-2: Package lockfiles have no known CVEs (F3)

**Given** the `test_pip_audit_clean` E2E test scans all `uv.lock` files
**When** `packages/floe-core/uv.lock` is regenerated via `uv lock`
**Then** `cryptography` resolves to `>=46.0.6` (fixing `GHSA-m959-cc7f-wv43`)
**And** all other package-level lockfiles are audited and refreshed if stale

**Boundary**: Only lockfiles that exist and contain stale cryptography are updated.
No dependency additions or removals beyond what `uv lock` resolves.

## AC-3: Pod readiness check excludes completed jobs (F5)

**Given** the `test_all_pods_ready` test in `test_platform_bootstrap.py`
**When** completed Dagster run pods exist in the namespace (phase=Succeeded)
**Then** those pods are excluded from the readiness check
**And** the check passes when all Running pods are Ready
**And** the implementation uses JSON parsing (not JSONPath) consistent with
`test_helm_upgrade_e2e.py:180-199` and `test_platform_deployment_e2e.py:140-155`

**Boundary**: Pods with phase `Failed` or `Pending` must NOT be excluded — only
`Succeeded` is skipped.

## AC-4: OpenLineage START emission gap logged as backlog item (F4)

**Given** the `test_openlineage_four_emission_points` test correctly surfaces a
production gap (missing `RunEvent.START` events)
**When** this work unit ships
**Then** a GitHub issue is created with label `specwright-backlog` describing the gap
**And** the test assertion is NOT weakened
**And** the issue references: orchestrator plugin emission code path, demo definitions
NoOp lineage resource, and the test file + line number
