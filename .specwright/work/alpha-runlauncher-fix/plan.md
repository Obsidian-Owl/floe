# Plan: Alpha RunLauncher Fix

## Task Breakdown

### Task 1: Extract and verify Dagster subchart run launcher template

**Pre-requisite for all other tasks.** Extract `dagster-1.12.17.tgz` and verify:
- `_run-launcher.tpl` uses `hasKey $k8sRunLauncherConfig "image"` for `job_image`
- `imagePullPolicy` is read as a sibling key: `$k8sRunLauncherConfig.imagePullPolicy`
- `dagster.externalImage.name` formats as `repository:tag`
- Document exact line numbers for context.md accuracy

**AC**: AC-1, AC-2, AC-3 (prerequisite verification)

### Task 2: Add run launcher image to values-test.yaml

Add `image:` block and `imagePullPolicy: Never` under `dagster.runLauncher.config.k8sRunLauncher`.

```yaml
# Under dagster.runLauncher.config.k8sRunLauncher (existing section):
  runLauncher:
    type: K8sRunLauncher
    config:
      k8sRunLauncher:
        # Image for run worker pods (MUST match webserver/daemon image)
        image:
          repository: floe-dagster-demo
          tag: latest
        imagePullPolicy: Never
        envConfigMaps: []
        envSecrets: []
```

Note: `values-test.yaml` currently has NO `runLauncher` section — it inherits from base `values.yaml`.
The full section must be added because we need `imagePullPolicy: Never` (base defaults to `Always`).

**AC**: AC-1
**Files**: `charts/floe-platform/values-test.yaml`

### Task 3: Add commented image documentation to base values.yaml

Add commented-out `image:` block and set `imagePullPolicy: Always` explicitly.

```yaml
# Under dagster.runLauncher.config.k8sRunLauncher (lines 190-201):
      k8sRunLauncher:
        # Image for run worker pods — MUST be set in environment overrides.
        # Use the same image as dagsterWebserver/dagsterDaemon to ensure
        # code locations and dbt project are available in run pods.
        # image:
        #   repository: ""
        #   tag: ""
        imagePullPolicy: Always
        envConfigMaps: []
```

**AC**: AC-2
**Files**: `charts/floe-platform/values.yaml`

### Task 4: Add run launcher image to values-dev.yaml and values-demo.yaml

**values-dev.yaml**: Add `image:` block with `floe-dagster-demo:latest` and
`imagePullPolicy: Never`.

**values-demo.yaml**: Add `image:` block with `floe-dagster-demo:latest` and
`imagePullPolicy: Never` (consistent with existing webserver/daemon `pullPolicy: Never`
in demo — both use Kind with pre-loaded images).

**AC**: AC-3
**Files**: `charts/floe-platform/values-dev.yaml`, `charts/floe-platform/values-demo.yaml`

### Task 5: Fix snake_case key and add image placeholder in prod/staging

Fix `run_launcher` → `runLauncher` in both files. Add commented-out `image:` block.

```yaml
# values-prod.yaml and values-staging.yaml:
  runLauncher:
    type: K8sRunLauncher
    config:
      k8sRunLauncher:
        # REQUIRED: Set image for run worker pods.
        # Must match your dagsterWebserver/dagsterDaemon image.
        # image:
        #   repository: "your-registry/floe-dagster"
        #   tag: "your-version"
        imagePullPolicy: Always
        resources:
          ...existing resources...
```

Also correct `.vuln-ignore` comment.

**AC**: AC-4, AC-5
**Files**: `charts/floe-platform/values-prod.yaml`, `charts/floe-platform/values-staging.yaml`, `.vuln-ignore`

### Task 6: Add Helm unit test for run launcher image

Create `charts/floe-platform/tests/dagster_run_launcher_test.yaml`:

```yaml
suite: dagster run launcher image config
templates:
  - charts/dagster/templates/configmap-instance.yaml
tests:
  - it: should render job_image when image is configured
    set:
      dagster.enabled: true
      dagster.runLauncher.type: K8sRunLauncher
      dagster.runLauncher.config.k8sRunLauncher.image.repository: floe-dagster-demo
      dagster.runLauncher.config.k8sRunLauncher.image.tag: latest
    asserts:
      - contains:
          path: data
          content:
            job_image
```

The exact assertion structure depends on how helm-unittest accesses the Dagster
subchart's rendered configmap. Implementation should verify with `helm template`
first, then write the assertion.

**AC**: AC-6
**Files**: `charts/floe-platform/tests/dagster_run_launcher_test.yaml`

## File Change Map

| File | Change Type | Lines Affected |
|------|------------|---------------|
| `charts/floe-platform/values-test.yaml` | ADD section | After line 113 (dagster section) |
| `charts/floe-platform/values.yaml` | MODIFY | Lines 190-201 |
| `charts/floe-platform/values-dev.yaml` | MODIFY | Lines 44-54 |
| `charts/floe-platform/values-demo.yaml` | MODIFY | Lines 78-89 |
| `charts/floe-platform/values-prod.yaml` | MODIFY | Lines 72-81 |
| `charts/floe-platform/values-staging.yaml` | MODIFY | Lines 70-79 |
| `.vuln-ignore` | MODIFY | Line 29 |
| `charts/floe-platform/tests/dagster_run_launcher_test.yaml` | CREATE | New file |

## Dependencies

```
Task 1 (verify subchart) → Task 2 (test values)
                         → Task 3 (base values)
                         → Task 4 (dev/demo values)
                         → Task 5 (prod/staging + vuln-ignore)
Task 2 → Task 6 (helm unittest — needs test values to validate against)
```

Tasks 2-5 are independent of each other (can be parallelized after Task 1).
Task 6 depends on Task 2 (needs the test values to verify rendering).

## As-Built Notes

### Discovered Behavior: Dagster JSON Schema requires pullPolicy inside image block

The Dagster subchart's `values.schema.json` validates that the `image` object includes
a `pullPolicy` field, even though the template code at `_run-launcher.tpl` ignores it
(using only `imagePullPolicy` as a sibling). Without `pullPolicy` inside `image:`,
`helm template` fails schema validation with: `missing property 'pullPolicy'`.

**Resolution**: Added `pullPolicy: Never` inside each `image:` block alongside the
sibling `imagePullPolicy: Never`. The template uses the sibling key; the schema requires
the nested one. Both must be present.

### Discovered Behavior: values-demo.yaml global.environment validation

The demo values file uses `global.environment: demo` which is not in the schema's
allowed values (`dev`, `qa`, `staging`, `prod`, `test`). This is a pre-existing issue
unrelated to this work unit. `helm template` with demo values requires `--set
global.environment=dev` to bypass schema validation.

### Plan Deviations

- **Task 1** was completed during design phase (subchart template extraction). No
  separate commit needed.
- **pullPolicy added to image block** in all values files (not in original plan) —
  required by Dagster schema validation.
- **Demo imagePullPolicy changed** from `IfNotPresent` (original plan) to `Never`
  (corrected during spec review to match existing demo convention).

### Actual File Changes

| File | Commit |
|------|--------|
| `charts/floe-platform/values-test.yaml` | `cd5e4e0` |
| `charts/floe-platform/values.yaml` | `bafe533` |
| `charts/floe-platform/values-dev.yaml` | `3ae9e68` |
| `charts/floe-platform/values-demo.yaml` | `3ae9e68` |
| `charts/floe-platform/values-prod.yaml` | `20210dc` |
| `charts/floe-platform/values-staging.yaml` | `20210dc` |
| `.vuln-ignore` | `20210dc` |
| `charts/floe-platform/tests/dagster_run_launcher_test.yaml` | `d4ec10f` |
