# Spec: In-Cluster Infrastructure

## Overview

Build the K8s infrastructure for running E2E tests as in-cluster Jobs:
Job definitions, RBAC, Dockerfile changes, CI script extension, and
GitHub Actions workflow. Depends on Unit 1 (test-portability) being complete.

## Acceptance Criteria

### AC-1: E2E Job definition in test-runner.yaml

A new Job definition `floe-test-e2e` exists in `testing/k8s/jobs/test-runner.yaml`:
- `namespace: floe-test`
- `serviceAccountName: e2e-test-runner`
- `INTEGRATION_TEST_HOST: "k8s"`
- `TEST_PATH: "tests/e2e/"`
- `TEST_ARGS: "-m 'not destructive' --junitxml=/artifacts/e2e-results.xml"`
- Volume mount for `/artifacts` using PVC `test-artifacts`
- All service connection env vars (matching integration Job pattern)
- `restartPolicy: Never`
- `backoffLimit: 0`

**Verification**: `kubectl apply --dry-run=client -f testing/k8s/jobs/test-runner.yaml` succeeds.
The Job excludes destructive tests via the `-m 'not destructive'` marker filter.

### AC-2: Destructive E2E Job definition in test-runner.yaml

A new Job definition `floe-test-e2e-destructive` exists:
- `serviceAccountName: e2e-destructive-runner`
- `TEST_PATH: "tests/e2e/"`
- `TEST_ARGS: "-m destructive --junitxml=/artifacts/e2e-destructive-results.xml"`
- Same PVC volume mount
- Same service connection env vars

**Verification**: `kubectl apply --dry-run=client` succeeds. The Job runs ONLY
destructive tests via the `-m destructive` marker filter.

### AC-3: Standard E2E ServiceAccount and Role

File `testing/k8s/rbac/e2e-test-runner.yaml` contains:
- `ServiceAccount` named `e2e-test-runner` in `floe-test` namespace
- `Role` with all dagster Role permissions PLUS:
  - `pods/exec` subresource (create verb)
  - `secrets` (get, list, watch)
- `RoleBinding` connecting the SA to the Role

**Verification**: `kubectl apply --dry-run=client` succeeds. The Role does NOT
include secrets CRUD or deployment/statefulset delete.

### AC-4: Destructive E2E ServiceAccount and Role

File `testing/k8s/rbac/e2e-destructive-runner.yaml` contains:
- `ServiceAccount` named `e2e-destructive-runner` in `floe-test` namespace
- `Role` with all standard E2E permissions PLUS:
  - `secrets` (get, list, watch, create, update, delete)
  - `deployments` (get, list, patch, delete)
  - `statefulsets` (get, list, patch, delete)
  - `pods` delete
- `RoleBinding` connecting the SA to the Role

**Boundary**: Namespace-scoped Role, NOT ClusterRole. Blast radius limited to `floe-test`.

**Verification**: `kubectl apply --dry-run=client` succeeds.

### AC-5: PVC manifest for artifact storage

File `testing/k8s/pvc/test-artifacts.yaml` contains:
- `PersistentVolumeClaim` named `test-artifacts` in `floe-test` namespace
- `accessModes: [ReadWriteOnce]`
- `resources.requests.storage: 100Mi`
- No `storageClassName` (uses Kind default `local-path`)

**Verification**: PVC can be created in Kind cluster. Survives pod termination.

### AC-6: Helm CLI in testing Dockerfile

`testing/Dockerfile` installs Helm 3 CLI:
- Installed alongside existing kubectl
- Pinned to a specific version (e.g., `v3.14.0`)
- Verified via `helm version` in the built image

**Boundary**: No other Dockerfile changes. Same base image, same ENTRYPOINT.

### AC-7: Destructive test markers

Tests that mutate cluster state are marked with `@pytest.mark.destructive`:
- `tests/e2e/test_helm_upgrade_e2e.py`: `test_helm_upgrade_succeeds`,
  `test_no_crashloopbackoff_after_upgrade`, `test_services_healthy_after_upgrade`,
  `test_helm_history_shows_revisions` (class-level marker on `TestHelmUpgrade`)
- `tests/e2e/test_service_failure_resilience_e2e.py`: `test_minio_pod_restart_detected`,
  `test_polaris_pod_restart_detected`, `test_compilation_during_service_outage`
  (class-level marker on `TestServiceFailureResilience`)
- `tests/e2e/conftest.py`: `destructive` marker registered in `pytest_configure`

**Verification**: `pytest --collect-only -m destructive tests/e2e/` shows only the
7 destructive tests. `pytest --collect-only -m 'not destructive' tests/e2e/`
shows all other E2E tests.

### AC-8: test-integration.sh supports E2E path

`testing/ci/test-integration.sh` accepts parameters to run E2E tests:
- `TEST_SUITE` env var (default: `integration`) selects which Job to run
- Script parameterization includes: `JOB_NAME` selection, manifest paths, and
  pre-apply steps (RBAC, PVC) based on `TEST_SUITE` value
- When `TEST_SUITE=e2e`: applies E2E RBAC + PVC manifests, then applies and monitors
  `floe-test-e2e` Job from `test-runner.yaml`
- When `TEST_SUITE=e2e-destructive`: applies destructive RBAC, monitors
  `floe-test-e2e-destructive` Job
- JUnit XML extraction from PVC after Job completes (when PVC exists)
- Exit code reflects Job pass/fail status

**Note**: The existing script hardcodes `JOB_NAME="floe-test-integration"` and applies
the full `test-runner.yaml`. Parameterization requires changing `JOB_NAME` selection
and adding conditional pre-apply steps. The `kubectl apply -f test-runner.yaml` is
idempotent so applying all Jobs is acceptable; only the monitored Job matters.

**Boundary**: Integration test path (`TEST_SUITE=integration`) is unchanged.

### AC-9: Weekly CI workflow E2E job

`.github/workflows/weekly.yml` has a new `e2e-tests` job:
- Runs after Kind cluster is set up (same infrastructure as `integration-tests`)
- Executes `testing/ci/test-integration.sh` with `TEST_SUITE=e2e`
- Then executes with `TEST_SUITE=e2e-destructive` (sequential, after standard E2E)
- Uploads JUnit XML as GitHub Actions artifact
- Collects pod logs on failure (same pattern as integration-tests job)

**Boundary**: Does not modify existing `integration-tests` job.

## Design Reference

`.specwright/work/e2e-in-cluster-ci/design.md` — Sections 1, 3, 4, 5, 6

## Risk Notes

- Kind `local-path-provisioner` PVC creation can take 10-30s — CI must wait
- `kind load docker-image` for 500MB+ image adds 2-5 min to CI — accepted
- Helm install in Dockerfile adds ~50MB to image size — accepted
