# Context: In-Cluster Infrastructure (Unit 2)

## Purpose

Build the K8s Job definitions, RBAC, Dockerfile changes, and CI workflow
needed to run E2E tests as in-cluster Jobs. This is the infrastructure
that makes the test portability changes (Unit 1) useful in CI.

## Key Files

### To Modify

| File | Change |
|------|--------|
| `testing/k8s/jobs/test-runner.yaml` | Add E2E + destructive Job definitions |
| `testing/Dockerfile` | Add Helm CLI installation |
| `testing/ci/test-integration.sh` | Parameterize for E2E test path + JUnit XML |
| `.github/workflows/weekly.yml` | Add E2E test job |

### To Create

| File | Purpose |
|------|---------|
| `testing/k8s/rbac/e2e-test-runner.yaml` | ServiceAccount + Role for standard E2E |
| `testing/k8s/rbac/e2e-destructive-runner.yaml` | ServiceAccount + Role for destructive E2E |
| `testing/k8s/pvc/test-artifacts.yaml` | PVC for JUnit XML artifact storage |

### To Modify (Test Code)

| File | Change |
|------|---------|
| `tests/e2e/conftest.py` | Add `@pytest.mark.destructive` marker registration |
| `tests/e2e/test_helm_workflow.py` | Add `@pytest.mark.destructive` to helm upgrade tests |
| `tests/e2e/test_service_failure_resilience_e2e.py` | Add `@pytest.mark.destructive` to pod-kill tests |

## Existing Patterns to Follow

### test-runner.yaml (Integration Job, lines 154-245)
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: floe-test-integration
  namespace: floe-test
spec:
  template:
    spec:
      serviceAccountName: dagster
      containers:
      - name: test-runner
        image: floe-test-runner:latest
        env:
        - name: INTEGRATION_TEST_HOST
          value: "k8s"
        - name: TEST_PATH
          value: "tests/"
        - name: TEST_ARGS
          value: ""
```

### test-integration.sh Pattern
1. Check prerequisites (kubectl, kind)
2. Build Docker image (unless SKIP_BUILD=true)
3. `kind load docker-image` into cluster
4. Delete previous Job if exists
5. `kubectl apply -f` Job manifest
6. `kubectl wait --for=condition=complete` (or `--for=condition=failed`)
7. Stream logs from completed pod
8. Exit with Job's exit code

### Dagster Role (role.yaml)
```yaml
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch", "create", "delete"]
- apiGroups: [""]
  resources: ["pods/log", "pods/status"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get", "list", "watch", "create", "delete", "patch"]
```

## RBAC Requirements

### Standard E2E Runner (superset of dagster Role)
All dagster Role permissions PLUS:
- `pods/exec` — tests that exec into pods
- `secrets` read — Helm release state queries (non-destructive)

### Destructive E2E Runner (elevated)
All standard E2E permissions PLUS:
- `secrets` CRUD — Helm release state management
- `deployments`, `statefulsets` patch/delete — for upgrade tests
- `pods` delete — for kill tests

## Gotchas

1. `kind load docker-image` does full tarball export/import — no layer dedup.
   500MB+ test image. Accept as known cost.
2. `emptyDir` for `/artifacts` in existing Job (line 89-90) — unreliable for
   artifact extraction after pod termination. PVC is the fix.
3. Destructive tests identified (verified grep):
   - `test_helm_upgrade_e2e.py`: `test_helm_upgrade_succeeds`, `test_no_crashloopbackoff_after_upgrade`,
     `test_services_healthy_after_upgrade`, `test_helm_history_shows_revisions`
   - `test_service_failure_resilience_e2e.py`: `test_minio_pod_restart_detected`,
     `test_polaris_pod_restart_detected`, `test_compilation_during_service_outage`
4. Helm 3 is a single ~50MB binary — add to existing Dockerfile, not a separate image.
5. `test-integration.sh` already supports `TEST_PATH` and `TEST_ARGS` env vars —
   parameterization is straightforward.

## PVC Artifact Extraction Pattern

```bash
# Create helper pod mounting the PVC
kubectl run artifact-extractor --image=busybox --restart=Never \
  --overrides='{"spec":{"volumes":[{"name":"artifacts","persistentVolumeClaim":{"claimName":"test-artifacts"}}],"containers":[{"name":"extractor","image":"busybox","command":["sleep","60"],"volumeMounts":[{"name":"artifacts","mountPath":"/artifacts"}]}]}}'

# Copy artifacts out
kubectl cp artifact-extractor:/artifacts/e2e-results.xml ./e2e-results.xml

# Clean up
kubectl delete pod artifact-extractor
```
