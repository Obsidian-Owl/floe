# Design: Alpha Stability — K8sRunLauncher Image & Values Hygiene

## Problem Statement

4 of 7 remaining E2E failures trace to a single root cause: the Dagster
K8sRunLauncher has no explicit `image` configuration. When a materialization
is triggered, the run launcher reads `repository_origin.container_image` which
is `None` (because `python_module` code locations run in-process, not as gRPC
servers), causing a `CheckError` before any dbt models execute.

Secondary findings during research:
- `values-prod.yaml` and `values-staging.yaml` use `run_launcher` (snake_case)
  instead of `runLauncher` (camelCase) — silently ignored by the Dagster Helm chart
- `.vuln-ignore` comment states fix version `2.32.6` but no such version exists;
  correct fix is `requests>=2.33.0`

## Approach

**Minimal, targeted Helm values changes** across all environment files. No template
modifications, no production code changes, no new abstractions.

### Task 1: Add K8sRunLauncher image config to values-test.yaml

Set `image.repository: floe-dagster-demo`, `image.tag: latest`, `imagePullPolicy: Never`
under `dagster.runLauncher.config.k8sRunLauncher`. This matches the webserver/daemon
image already configured at lines 71-74.

The Dagster subchart's `_run-launcher.tpl` checks `hasKey $k8sRunLauncherConfig "image"`
and renders `job_image: <repository>:<tag>`. This is the standard, documented approach.

### Task 2: Add K8sRunLauncher image config to values.yaml (base defaults)

Add a commented-out `image:` block with documentation explaining that this MUST be
set in environment overrides. The base values file serves as documentation of available
config.

### Task 3: Add K8sRunLauncher image config to values-dev.yaml and values-demo.yaml

Both currently omit the image. Set to match their respective webserver images.

### Task 4: Fix snake_case key in values-prod.yaml and values-staging.yaml

Fix `run_launcher` → `runLauncher`. Add placeholder `image:` block with comments
directing operators to set their registry/tag.

### Task 5: Correct .vuln-ignore comment

Update the comment on line 29 to reference `2.33.0` as the fix version.

### Task 6: Add Helm unit tests for run launcher image config

Add `helm unittest` tests verifying that the K8sRunLauncher `job_image` is set
in the rendered Dagster configmap for the test values profile.

## Integration Points

- **Dagster subchart** (`_run-launcher.tpl:79-81`): Reads `image.repository` and
  `image.tag` via `hasKey` check. Standard documented interface — no floe templates
  involved.
- **`configmap-dagster-workspace.yaml`**: Unaffected — workspace config is separate
  from run launcher config.
- **E2E tests**: `test_trigger_asset_materialization`, `test_iceberg_tables_exist_*`,
  `test_openlineage_four_emission_points`, `test_jaeger_trace_gap_*` — all should
  pass after the run launcher image is set.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Wrong image for run pods | LOW | HIGH | Use same image as webserver/daemon (proven working) |
| Values override ordering | LOW | MEDIUM | Helm merge is well-defined: values.yaml < values-{env}.yaml |
| Prod/staging key fix breaks deploy | NONE | N/A | The old snake_case key was already silently ignored |

## Blast Radius

**Modules/files touched:**
- `charts/floe-platform/values.yaml:187-201` — LOCAL (add commented image block)
- `charts/floe-platform/values-test.yaml:40-113` — LOCAL (add image to run launcher)
- `charts/floe-platform/values-dev.yaml:44-54` — LOCAL (add image to run launcher)
- `charts/floe-platform/values-demo.yaml:78-89` — LOCAL (add image to run launcher)
- `charts/floe-platform/values-prod.yaml:72-81` — LOCAL (fix key name, add image placeholder)
- `charts/floe-platform/values-staging.yaml:70-79` — LOCAL (fix key name, add image placeholder)
- `.vuln-ignore:29-31` — LOCAL (comment correction)
- `charts/floe-platform/tests/` — LOCAL (new Helm unit test)

**Failure propagation:**
- All changes are to Helm values files (configuration). No template logic changes.
- The Dagster subchart consumes the image field through a documented `hasKey` check.
- If the image is wrong, the symptom is the same as today (run pod fails to start) —
  no new failure modes introduced.

**What this design does NOT change:**
- No floe-platform Helm templates
- No Dagster subchart templates
- No Python production code
- No E2E test code
- No OpenLineage/parentRun code (confirmed working, blocked by this cascade)

## Alternatives Considered

### A: Set DAGSTER_CURRENT_IMAGE env var on webserver/daemon pods

**Rejected.** `DAGSTER_CURRENT_IMAGE` only works on gRPC server pods (official Dagster
docs). Floe uses `python_module` code locations which run in-process. The env var
would have no effect.

### B: Switch to gRPC server code locations

**Rejected.** This would require separate container images per code location, a
`grpc_server` workspace config, and would change the deployment model significantly.
The `python_module` pattern is simpler, works well for demo/alpha, and is the pattern
the existing codebase is built around.

### C: Use Dagster's CeleryK8sRunLauncher instead

**Rejected.** Over-engineered for alpha. CeleryK8sRunLauncher adds a Celery/Redis
dependency for distributed task queuing. K8sRunLauncher is sufficient.

## WARNs from Critic Review

**WARN-1**: The Dagster subchart is packaged as `dagster-1.12.17.tgz`. The template
line numbers cited in context.md (`_run-launcher.tpl:79-81`) were verified from a
prior extraction but are not directly reproducible from `git clone`. Implementation
should extract and verify the `hasKey` check before writing values.

**WARN-2**: `imagePullPolicy` placement may differ between webserver config (nested
inside `image:` block) and run launcher config (potentially a sibling key). The
Dagster subchart templates for webserver vs run launcher may handle this differently.
Implementation should inspect the extracted subchart templates to confirm the correct
YAML nesting before writing values.

**Convergence**: 5/5 Correctness, 4/5 Completeness, 5/5 Risk, 5/5 Simplicity,
4/5 Sustainability. No BLOCKs. APPROVED.
