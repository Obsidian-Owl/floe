# Design: In-Cluster E2E Test Execution

## Problem

E2E tests depend on a fragile chain: SSH tunnel → kubectl port-forward → service.
A single tunnel death causes 28+ cascading test failures. This has been the
primary source of instability for weeks, blocking alpha release confidence.

## Solution Overview

**Make in-cluster execution the primary CI path for E2E tests.** Tests run as
a K8s Job inside the Kind cluster where services are reachable via native DNS.
No tunnels, no port-forwards.

The infrastructure already exists — `testing/Dockerfile`, `test-integration.sh`,
`ServiceEndpoint`, and Job manifests. This design extends that pattern to cover
E2E tests and adds structured CI reporting.

Host-based execution (`test-e2e.sh`) remains for interactive development but is
no longer the CI quality gate.

## Approach

### 1. Extend In-Cluster Pattern to E2E Tests

Add an E2E Job definition to `testing/k8s/jobs/test-runner.yaml`:
- Same Dockerfile, same `INTEGRATION_TEST_HOST=k8s`
- Test path: `tests/e2e/` with exclusion of destructive tests
- JUnit XML output to `/artifacts/e2e-results.xml`

### 2. Refactor Hardcoded Localhost References

Full audit of `localhost` in `tests/e2e/*.py` (27 occurrences across 8 files):

| Category | Files | Count | Migration |
|----------|-------|-------|-----------|
| **ServiceEndpoint needed** | `conftest.py:349`, `test_observability.py:542,1164`, `test_observability_roundtrip_e2e.py:180`, `test_platform_deployment_e2e.py:294` | 5 | Replace with `ServiceEndpoint(name).url` or env var fallback |
| **Error messages only** | `test_observability.py:167,289,723,921`, `test_platform_bootstrap.py:534` | 5 | No change needed (string in error msg, not connection) |
| **Docstring/comments** | `test_platform_bootstrap.py:197-202,404,464,507`, `test_promotion.py:65`, `test_platform_deployment_e2e.py:7`, `test_service_failure_resilience_e2e.py:205`, `conftest.py:1030` | 10 | No change needed |
| **Regex pattern** | `test_helm_workflow.py:509` | 1 | No change needed (validating rendered template) |
| **Fixture uses ServiceEndpoint** | `conftest.py` (smoke check) | 1 | Already correct — uses `ServiceEndpoint` |
| **OCI registry** | `test_promotion.py:67` | 1 | Separate concern (OCI, not K8s service) |

**5 functional changes needed** — not 7 as initially estimated.

### 3. Dedicated E2E ServiceAccount

The `dagster` Role only permits: pods (CRUD), jobs (CRUD), configmaps (read),
events (read/create), services (read), PVCs (read). It **lacks**:
- Pod `exec` (needed by tests that run kubectl exec)
- Helm state access (Secrets with `owner: helm` label)

Create a dedicated `e2e-test-runner` ServiceAccount + Role with:
- All `dagster` Role permissions (superset)
- `pods/exec` for tests that exec into pods
- `secrets` read for Helm release state queries (non-destructive only)

### 4. Destructive Test Handling

Destructive tests (`test_helm_upgrade_e2e.py`, `test_service_failure_resilience_e2e.py`)
require elevated RBAC (helm upgrade, pod kills) that should NOT be granted to the
standard E2E runner. Two approaches:

**Chosen approach**: Run destructive tests in a **separate Job** with elevated
`e2e-destructive-runner` ServiceAccount + ClusterRole that adds:
- `secrets` CRUD (Helm release state)
- `deployments`, `statefulsets` patch/delete
- `pods` delete (for kill tests)

Both Jobs run in CI — destructive Job runs **after** the main E2E Job completes.
This satisfies Constitution Principle V ("All E2E tests MUST run in Kubernetes")
while isolating blast radius.

### 5. JUnit XML + Artifact Extraction

**Primary path**: PVC-backed `/artifacts` volume (not emptyDir).
- Pre-create PVC in the test namespace
- Job writes JUnit XML to PVC
- CI extracts via `kubectl cp` from a helper pod that mounts the PVC
- Works even after test pod is evicted/OOM-killed

**Fallback**: `kubectl logs` captures pytest output (already working in
`test-integration.sh`).

### 6. CI Workflow Changes

`weekly.yml` gains an E2E job that:
1. Builds test image + loads to Kind (existing `test-integration.sh` pattern)
2. Applies E2E Job manifest
3. Waits for completion
4. Extracts JUnit XML from PVC
5. Applies destructive Job manifest
6. Waits for completion
7. Uploads JUnit XML as GitHub Actions artifact

### 7. Host-Based Mode (DevPod/Local Dev)

`test-e2e.sh` remains for interactive development. Minimal changes:
- Mark destructive tests with `@pytest.mark.destructive` marker
- `pytest_collection_modifyitems` already moves destructive tests last
- No new features added to `test-e2e.sh` (avoid extending a mode being deprecated for CI)

## Integration Points

| Component | Integration | Direction |
|-----------|------------|-----------|
| `testing/fixtures/services.py` | `ServiceEndpoint` + `INTEGRATION_TEST_HOST` | Consumed by tests (no change) |
| `testing/k8s/jobs/test-runner.yaml` | New E2E + destructive Job definitions | Extended |
| `testing/ci/test-integration.sh` | Reused for image build + Job execution | Extended |
| `tests/e2e/conftest.py` | `@pytest.mark.destructive` marker | Extended |
| `charts/floe-platform/templates/` | New SA + Role for E2E runner | Extended |
| `.github/workflows/weekly.yml` | E2E job using in-cluster pattern | Extended |

## Blast Radius

| Module | Change | Scope | Failure Propagation |
|--------|--------|-------|---------------------|
| `tests/e2e/test_observability*.py` | Replace 3 hardcoded endpoints with ServiceEndpoint | Local | Only affects OTel/Marquez tests |
| `tests/e2e/test_platform_deployment_e2e.py` | Replace 1 hardcoded Marquez URL | Local | Only affects deployment tests |
| `tests/e2e/conftest.py` | Replace 1 hardcoded Dagster URL + add destructive marker | Local | Session fixture, affects all E2E |
| `testing/k8s/jobs/test-runner.yaml` | Add 2 Job definitions | Local | New resources, no existing impact |
| `testing/ci/test-integration.sh` | Support E2E path + JUnit XML flag | Local | Parameterized, no regression |
| `charts/floe-platform/templates/` | New SA + Role (2 new files) | Adjacent | Only affects test namespace |
| `.github/workflows/weekly.yml` | Add E2E job | Adjacent | New job, no existing impact |

**NOT changed**: Production code, Helm chart templates (except new SA),
Kind config, `testing/Dockerfile`, `ServiceEndpoint` class, `test-e2e.sh`

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| In-cluster tests miss port-forward-specific bugs | Low | Low | Host-based mode remains for dev |
| Test image rebuild adds CI time (2-5 min) | Certain | Low | Docker layer caching, kind load |
| PVC artifact extraction fails | Low | Medium | kubectl logs fallback, CI detects missing XML |
| Destructive Job RBAC too broad | Low | Medium | Namespace-scoped Role (not ClusterRole) |
| kind load is slow for large images | Medium | Low | Multi-stage build optimization (future) |

## Alternatives Considered

| Alternative | Why Not |
|-------------|---------|
| **kubefwd** | Requires sudo, still uses K8s API transport (same SPOF), adds dependency |
| **autossh** | Tactical fix — hardens tunnel but doesn't eliminate the fragile architecture |
| **Telepresence** | Invasive (traffic manager sidecar), reliability regressions between versions |
| **Docker network join** | Linux-only, doesn't work on macOS dev machines |
| **Keep host-based for CI** | Root cause of instability — user explicitly rejected tactical fixes |

## WARN: Architect Review Notes

1. **Test image size**: Full monorepo COPY + `kind load` tarball. Accept as known
   cost; multi-stage optimization is a future enhancement.
2. **OTel env var tests**: `test_observability.py:542,1164` intentionally set
   `OTEL_EXPORTER_OTLP_ENDPOINT` to test OTel configuration behavior. These
   must use `ServiceEndpoint` for the URL value but keep the env var pattern.
3. **Pre-mortem**: Destructive tests excluded from CI → regression ships.
   Mitigated by running destructive Job as a separate CI step, not excluding
   from CI entirely.
