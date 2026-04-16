# Plan: In-Cluster Infrastructure

## Task Breakdown

### Task 1: Add destructive test markers

**AC coverage**: AC-7

**Changes**:
- Register `destructive` marker in `tests/e2e/conftest.py` `pytest_configure`
- Add `@pytest.mark.destructive` to `TestHelmUpgrade` class in `test_helm_upgrade_e2e.py`
- Add `@pytest.mark.destructive` to pod-kill tests in `test_service_failure_resilience_e2e.py`

**File change map**:
| File | Action | Scope |
|------|--------|-------|
| `tests/e2e/conftest.py` | Edit | Add marker registration |
| `tests/e2e/test_helm_upgrade_e2e.py` | Edit | Add `@pytest.mark.destructive` |
| `tests/e2e/test_service_failure_resilience_e2e.py` | Edit | Add `@pytest.mark.destructive` |

### Task 2: Create RBAC manifests

**AC coverage**: AC-3, AC-4

**Changes**:
- Create `testing/k8s/rbac/e2e-test-runner.yaml` (SA + Role + RoleBinding)
- Create `testing/k8s/rbac/e2e-destructive-runner.yaml` (SA + Role + RoleBinding)

**File change map**:
| File | Action | Scope |
|------|--------|-------|
| `testing/k8s/rbac/e2e-test-runner.yaml` | Create | Full file |
| `testing/k8s/rbac/e2e-destructive-runner.yaml` | Create | Full file |

### Task 3: Create PVC manifest and add E2E Job definitions

**AC coverage**: AC-1, AC-2, AC-5

**Changes**:
- Create `testing/k8s/pvc/test-artifacts.yaml`
- Add `floe-test-e2e` Job to `test-runner.yaml`
- Add `floe-test-e2e-destructive` Job to `test-runner.yaml`

**File change map**:
| File | Action | Scope |
|------|--------|-------|
| `testing/k8s/pvc/test-artifacts.yaml` | Create | Full file |
| `testing/k8s/jobs/test-runner.yaml` | Edit | Append 2 Job definitions |

### Task 4: Add Helm CLI to Dockerfile

**AC coverage**: AC-6

**Changes**:
- Add Helm 3 CLI download and install step to `testing/Dockerfile`

**File change map**:
| File | Action | Scope |
|------|--------|-------|
| `testing/Dockerfile` | Edit | Add helm install step |

### Task 5: Extend test-integration.sh for E2E

**AC coverage**: AC-8

**Changes**:
- Add `TEST_SUITE` env var support (default: `integration`)
- Add E2E path: apply RBAC, PVC, E2E Job
- Add destructive path: apply destructive RBAC, destructive Job
- Add PVC-based JUnit XML extraction

**File change map**:
| File | Action | Scope |
|------|--------|-------|
| `testing/ci/test-integration.sh` | Edit | Add E2E/destructive paths |

### Task 6: Add E2E job to weekly CI workflow

**AC coverage**: AC-9

**Changes**:
- Add `e2e-tests` job to `.github/workflows/weekly.yml`
- Run standard E2E then destructive E2E sequentially
- Upload JUnit XML artifacts
- Collect logs on failure

**File change map**:
| File | Action | Scope |
|------|--------|-------|
| `.github/workflows/weekly.yml` | Edit | Add e2e-tests job |

## Task Order

```
Task 1 ─┐
Task 2 ─┼─ (independent)
Task 3 ─┤  (depends on Task 2 for SA names)
Task 4 ─┘
Task 5 ──── (depends on Tasks 1-4 for manifests)
Task 6 ──── (depends on Task 5 for script)
```

Effective order: [1, 2] → 3 → 4 → 5 → 6

## Verification Strategy

- Tasks 1-4: `kubectl apply --dry-run=client` for YAML validation
- Task 4: `docker build` + `docker run --rm <image> helm version`
- Task 5: Script linting (`shellcheck`) + dry-run with `DRY_RUN=true`
- Task 6: `act` local GitHub Actions runner or manual workflow dispatch
- Full validation: Run `TEST_SUITE=e2e testing/ci/test-integration.sh` against Kind cluster

## As-Built Notes

### Plan Deviations

1. **E2E Jobs in separate file** (Task 3): Created `testing/k8s/jobs/test-e2e.yaml` instead of
   appending to `test-runner.yaml`. The existing file had duplicate YAML patterns that made
   editing error-prone. Separate file also simplifies CI script manifest selection (`JOB_MANIFEST`
   variable per suite).

2. **E2E workflow uses separate Kind cluster** (Task 6): `e2e-tests` job creates its own Kind cluster
   (`floe-e2e`) since it has `needs: [integration-tests]` — the integration job destroys its
   cluster on completion. Alternative was sharing the cluster, but `needs` prevents this.

### Implementation Decisions

- Destructive markers applied at class level (not method level) since all methods in both
  `TestHelmUpgrade` and `TestServiceFailureResilience` are destructive.
- Helm 3.14.0 pinned in Dockerfile (per P68 pattern — pin exact tool version).
- PVC `ReadWriteOnce` is correct since standard and destructive Jobs run sequentially
  (destructive only starts after standard completes).
- `SKIP_BUILD=true` for destructive run in weekly.yml — reuses image from standard run.
  The E2E workflow uses `needs: [integration-tests]` so integration tests must pass first.

### Actual File Paths

| Planned | Actual |
|---------|--------|
| `testing/k8s/jobs/test-runner.yaml` (append) | `testing/k8s/jobs/test-e2e.yaml` (new file) |
| All other paths | As planned |
