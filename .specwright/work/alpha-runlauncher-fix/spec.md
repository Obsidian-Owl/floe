# Spec: Alpha RunLauncher Fix

## Summary

Configure the Dagster K8sRunLauncher with an explicit `image` across all Helm values
files, fix dormant snake_case key bugs in prod/staging, correct vuln-ignore comment,
and add Helm unit tests for regression prevention.

## Acceptance Criteria

### AC-1: K8sRunLauncher image configured in values-test.yaml

The `values-test.yaml` file MUST include `image.repository` and `image.tag` under
`dagster.runLauncher.config.k8sRunLauncher`, matching the webserver/daemon image
(`floe-dagster-demo:latest`). The `imagePullPolicy` MUST remain `Never` (sibling key,
not nested in `image:` — the Dagster subchart ignores `pullPolicy` inside `image:`).

**How we know it works**: `helm template` with `values-test.yaml` renders a Dagster
instance configmap containing `job_image: "floe-dagster-demo:latest"`.

### AC-2: K8sRunLauncher image documented in base values.yaml

The base `values.yaml` MUST include a commented-out `image:` block under
`dagster.runLauncher.config.k8sRunLauncher` with a comment explaining that
environment overrides MUST set the image. The `imagePullPolicy` key MUST already
be present as `Always` (matching upstream default).

**How we know it works**: `grep -c '# *image:' charts/floe-platform/values.yaml`
returns >0 within the `k8sRunLauncher` section. The comment references "MUST be set
in environment overrides."

### AC-3: K8sRunLauncher image configured in values-dev.yaml and values-demo.yaml

Both files MUST include `image.repository` and `image.tag` under
`dagster.runLauncher.config.k8sRunLauncher`. Both use `floe-dagster-demo:latest`
with `imagePullPolicy: Never` (both environments use Kind with pre-loaded images,
consistent with their existing webserver/daemon `pullPolicy: Never`).

**How we know it works**: `helm template` with each values file renders
`job_image: "floe-dagster-demo:latest"` in the Dagster instance configmap.

### AC-4: snake_case key fixed in values-prod.yaml and values-staging.yaml

Both files MUST use `runLauncher` (camelCase), not `run_launcher` (snake_case).
Both MUST include a commented-out `image:` placeholder with instructions for operators.

**How we know it works**: `grep -c 'run_launcher' values-prod.yaml values-staging.yaml`
returns 0 for both files. `grep -c 'runLauncher' values-prod.yaml values-staging.yaml`
returns >0 for both.

### AC-5: .vuln-ignore comment corrected

The comment on the `GHSA-gc5v-m9x4-r6x2` entry MUST include the fix version
`requests>=2.33.0`. The current comment (`requests 2.32.5`) states the installed
version but not the fix version. Add `Fix: requests>=2.33.0` to the comment.
The ignore entry itself is unchanged.

**How we know it works**: The comment line contains `2.33.0`.

### AC-6: Helm unit test for run launcher image rendering

A `helm unittest` test file MUST verify that the Dagster instance configmap renders
`job_image` when the run launcher image is configured. The test MUST use values
matching the test profile.

**How we know it works**: `helm unittest charts/floe-platform` passes with the new
test included. The test asserts `job_image` is present in the Dagster instance
configmap data. Note: the configmap `data` values are YAML-encoded strings, so
the assertion must use `matchRegex` or string matching against the data key content,
not structured YAML path assertions.
