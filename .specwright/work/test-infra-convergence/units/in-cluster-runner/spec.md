# Spec: In-Cluster Runner as Default Path

## Acceptance Criteria

### AC-1: DevPod-aware image loading

`test-e2e-cluster.sh` MUST auto-detect the execution environment and load the test
runner Docker image accordingly:

- **Local Kind**: If `kind get clusters` lists the target cluster, use
  `kind load docker-image` (current behavior).
- **DevPod**: If `DEVPOD_WORKSPACE` env var is set, use
  `docker save <image> | ssh devpod docker load` pipe to transfer the image.
- **Neither**: Print diagnostic message to stderr and exit non-zero:
  `"ERROR: No Kind cluster or DevPod workspace detected. Run 'make kind-up' or start DevPod."`

The auto-detection MUST be overridable via `IMAGE_LOAD_METHOD` env var with values:
`kind`, `devpod`, `skip` (for CI where image is pre-loaded).

**Boundary conditions**:
- `SKIP_BUILD=true` skips the Docker build but still attempts image loading.
- `IMAGE_LOAD_METHOD=skip` skips both build and load (for pre-loaded images).
- DevPod SSH pipe MUST handle images up to 2GB without timeout.

### AC-2: Full E2E orchestrator

A new script `testing/ci/test-e2e-full.sh` MUST:

1. Run standard E2E tests via `test-e2e-cluster.sh` (non-destructive).
2. Wait for the standard Job to complete and capture its exit code.
3. Ensure the standard test pod is terminated and PVC is released.
4. Run destructive E2E tests via `TEST_SUITE=e2e-destructive test-e2e-cluster.sh`.
5. Capture the destructive suite exit code.
6. Exit with the first non-zero exit code encountered (0 if both pass). If standard
   tests fail, that exit code is used (destructive tests are skipped by default).

The script MUST NOT proceed to destructive tests if standard tests fail, unless
`FORCE_DESTRUCTIVE=true` is set.

**Boundary conditions**:
- If standard tests fail, destructive tests are skipped by default.
- If destructive tests fail, the overall exit code reflects the failure.
- Both suites' artifacts are preserved (no overwriting).

### AC-3: Makefile target convergence

The Makefile MUST be updated so that:

- `make test-e2e` runs the in-cluster runner (via `test-e2e-cluster.sh`), auto-detecting
  Kind vs DevPod environment.
- `make test-e2e-host` runs the legacy host-based port-forward runner
  (formerly `make test-e2e`).
- `make test-e2e-full` runs both standard and destructive suites via `test-e2e-full.sh`.
- The `help` target reflects the updated descriptions.
- `make test-e2e-local` and `make test-e2e-devpod` are removed (subsumed by auto-detect).

### AC-4: Hook update for in-cluster path

`.claude/hooks/check-e2e-ports.sh` MUST:

- Allow `pytest tests/e2e/` when `INTEGRATION_TEST_HOST=k8s` env var is set (indicates
  in-cluster execution — port-forwards are not needed).
- Continue to block direct `pytest tests/e2e/` from host when port-forwards are missing
  and `INTEGRATION_TEST_HOST` is not set.

### AC-5: Destructive test pod cleanup between suites

The orchestrator MUST ensure the standard E2E Job's pod is fully terminated before
starting the destructive suite. This prevents PVC mount conflicts (ReadWriteOnce).

Verification: `kubectl get pods -l test-type=e2e -n floe-test` returns no pods
before the destructive Job is submitted.

### AC-6: Error handling and diagnostics

All scripts MUST:
- Redirect error messages to stderr with `>&2`.
- Use `[[ ]]` for bash conditionals (not `[ ]`).
- Exit with non-zero codes on failure (no silent failures).
- Print a summary line at completion: `"E2E tests PASSED"` or `"E2E tests FAILED"`.

### AC-7: dbt Fusion CLI accessibility

The Dockerfile MUST ensure the `dbt` binary is executable by the non-root `floe`
user (UID 1000). The current symlink from `/root/.local/bin/dbt` to `/usr/local/bin/dbt`
MUST be verified — if the target is not readable by non-root, install dbt to a
shared path instead.
