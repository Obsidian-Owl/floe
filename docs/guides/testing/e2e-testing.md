# End-to-End Testing

E2E tests validate complete workflows from CLI commands through full pipeline execution.

---

## E2E Test Structure

```python
# tests/e2e/test_workflows.py
import pytest
import subprocess
from pathlib import Path

class TestCLIWorkflows:
    """End-to-end tests for CLI workflows."""

    def test_init_validate_run_workflow(self, tmp_path):
        """Test complete init → validate → run workflow."""

        # 1. Initialize project
        result = subprocess.run(
            ["floe", "init", "test-project"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        project_path = tmp_path / "test-project"
        assert project_path.exists()

        # 2. Validate configuration
        result = subprocess.run(
            ["floe", "validate"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

        # 3. Run pipeline
        result = subprocess.run(
            ["floe", "run", "--env", "dev"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0

    def test_dev_environment_starts(self, tmp_path, sample_project):
        """Test that dev environment starts correctly."""
        import requests
        import time

        # Start dev environment in background
        proc = subprocess.Popen(
            ["floe", "dev"],
            cwd=sample_project,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for services to start
            time.sleep(30)

            # Check Dagster is accessible
            response = requests.get("http://localhost:3000/health")
            assert response.status_code == 200

        finally:
            proc.terminate()
            proc.wait(timeout=10)
```

---

## E2E Test Environment

E2E tests run in a Kind cluster with the **full stack** deployed:

```yaml
# tests/e2e/test-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: e2e-tests
  namespace: floe-e2e
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: test-runner
          image: ghcr.io/floe/test-runner:latest
          command: ["pytest", "tests/e2e", "-v", "--junitxml=/results/junit.xml"]
          env:
            - name: DAGSTER_HOST
              value: "dagster-webserver.floe-e2e.svc.cluster.local"
            - name: POLARIS_HOST
              value: "polaris.floe-e2e.svc.cluster.local"
            - name: CUBE_HOST
              value: "cube.floe-e2e.svc.cluster.local"
          volumeMounts:
            - name: results
              mountPath: /results
      volumes:
        - name: results
          emptyDir: {}
```

---

## Running E2E Tests

```bash
# Create Kind cluster with multi-node config
kind create cluster --name floe-e2e --config tests/e2e/kind-config.yaml

# Deploy FULL stack
helm install floe-e2e ./charts/floe-platform \
  --namespace floe-e2e --create-namespace \
  --set dagster.enabled=true \
  --set polaris.enabled=true \
  --set cube.enabled=true \
  --set observability.enabled=true \
  --wait --timeout=10m

# Run E2E tests as K8s Job
kubectl apply -f tests/e2e/test-job.yaml -n floe-e2e
kubectl wait --for=condition=complete job/e2e-tests -n floe-e2e --timeout=10m

# View results
kubectl logs job/e2e-tests -n floe-e2e
```

---

## Test Environment Specifications

| Environment | Cluster | Deployment | Use Case |
|-------------|---------|------------|----------|
| Unit | None | None | Fast, isolated tests |
| Integration | Kind (single-node) | Minimal (Dagster only) | Component integration |
| E2E | Kind (multi-node) | Full stack | Complete workflows |
| Staging | Dedicated EKS/GKE | Production config | Soak tests, benchmarks |

---

## Related

- [Testing Index](index.md)
- [Integration Testing](integration-testing.md)
- [K8s Testing Infrastructure](k8s-infrastructure.md)
- [CI/CD Pipeline](ci-cd.md)
