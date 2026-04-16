# Design: E2E Platform Stability Fixes

## Problem

E2E testing on Hetzner DevPod revealed three issues blocking a fully green test suite:

1. **dagster-k8s missing from Docker image** — materializations fail with `ModuleNotFoundError: No module named 'dagster_k8s'` because the Helm chart configures `K8sRunLauncher` but the package isn't installed
2. **bitnami/kubectl:1.32 doesn't exist** — pre-upgrade hook job fails with `ErrImagePull`
3. **No port-forwards inside DevPod** — 84 E2E tests error when run directly via pytest instead of through `testing/ci/test-e2e.sh`

## Approach

Three surgical fixes, each touching 1-2 files. No architectural changes.

### Fix 1: Add dagster-k8s to Dockerfile

Add `dagster-k8s==${DAGSTER_POSTGRES_VERSION}` (0.28.14) to the explicit pip install block in `docker/dagster-demo/Dockerfile`. Update the misleading comment and add to the smoke test import.

### Fix 2: Pin bitnami/kubectl to valid tag

Change `tag: "1.32"` to `tag: "1.32.0"` in `charts/floe-platform/values.yaml` and `values-test.yaml`.

### Fix 3: Make test-e2e work inside DevPod

The `Makefile` `test-e2e` target already supports `KUBECONFIG` override. Inside DevPod, the kubeconfig needs DooD IP rewriting before tests. Add a `test-e2e-devpod` Makefile target that fixes the kubeconfig and invokes the existing test runner.

## Blast Radius

| Module | Scope | What changes | What does NOT change |
|--------|-------|-------------|---------------------|
| `docker/dagster-demo/Dockerfile` | Local | Add 1 pip package + update comment | No base image, no stage structure, no other deps |
| `charts/floe-platform/values.yaml` | Local | kubectl image tag only | No template logic, no other values |
| `charts/floe-platform/values-test.yaml` | Local | kubectl image tag only | Same as above |
| `Makefile` | Local | Add new target | No existing targets changed |

## Verification

After all fixes: rebuild Docker image, redeploy Helm chart, run `make test-e2e` inside DevPod. The materialization test should pass and the 84 port-forward errors should resolve.
