# Assumptions: E2E Structural Fixes

## A1: In-cluster DNS resolution works for all services
- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: `ServiceEndpoint` already supports K8s DNS via `INTEGRATION_TEST_HOST=k8s`.
  Integration tests already use this. E2E tests just need the same env var set.

## A2: Test container can access Kind-loaded images
- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: `kind load docker-image` is already used for the test runner image.
  The dagster-demo image is also loaded this way in `make build-demo-image`.

## A3: kubectl/helm available inside test container
- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: `testing/Dockerfile` already installs kubectl and helm.

## A4: PVC or kubectl logs sufficient for result extraction
- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: `testing/k8s/jobs/test-runner.yaml` already mounts a `test-artifacts` PVC
  and produces JUnit XML at `/artifacts/e2e-results.xml`.

## A5: Dagster demo image tag is deterministic
- **Type**: Clarify
- **Status**: ACCEPTED
- **Rationale**: For Kind, the tag is always `floe-dagster-demo:latest` with
  `imagePullPolicy: Never`. For prod, the tag would be parameterized via
  `--set` or values override. The design uses this pattern.

## A6: Polaris bootstrap credentials are stable
- **Type**: Technical
- **Status**: ACCEPTED (auto-resolved)
- **Evidence**: Bootstrap uses `polaris-admin`/`demo-secret` configured via
  Helm secrets. These don't change between test runs.
