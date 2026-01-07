# Kubernetes Testing Infrastructure

This guide covers the K8s-native testing infrastructure for floe.

---

## Test Execution Environments

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  UNIT TESTS                                                                  │
│  Environment: CI Runner (GitHub Actions ubuntu-latest)                      │
│  Why: Fast, no infrastructure dependencies                                  │
│  Command: uv run pytest tests/unit                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTEGRATION TESTS                                                           │
│  Environment: Kind cluster in CI (ephemeral K8s)                            │
│  Why: Real K8s networking, service discovery, pod lifecycle                 │
│  Deployment: Helm install floe-platform (minimal: Dagster + DuckDB)         │
│  Execution: Test pods run inside the cluster                                │
│  Command: kubectl apply -f tests/integration/test-job.yaml                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  E2E TESTS                                                                   │
│  Environment: Kind cluster with FULL stack                                  │
│  Why: Production-identical infrastructure                                   │
│  Deployment: Helm install floe-platform (full: Dagster + Polaris + Cube)    │
│  Execution: Test pods run complete pipeline scenarios                       │
│  Command: kubectl apply -f tests/e2e/test-job.yaml                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STAGING / PRE-PROD TESTS                                                    │
│  Environment: Dedicated staging cluster (persistent)                        │
│  Why: Long-running tests, performance benchmarks, soak tests                │
│  Deployment: Same Helm chart as production                                  │
│  Execution: Scheduled test jobs with production-like data volumes           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Test Pod Architecture

Integration and E2E tests run as Kubernetes Jobs:

```yaml
# tests/integration/test-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: floe-integration-tests
  namespace: floe-test
spec:
  backoffLimit: 0  # Fail fast, don't retry
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: test-runner
          image: ghcr.io/floe/test-runner:latest
          command: ["pytest", "tests/integration", "-v", "--junitxml=/results/junit.xml"]
          env:
            - name: DAGSTER_HOST
              value: "dagster-webserver.floe-test.svc.cluster.local"
            - name: POLARIS_HOST
              value: "polaris.floe-test.svc.cluster.local"
          volumeMounts:
            - name: results
              mountPath: /results
      volumes:
        - name: results
          emptyDir: {}
```

**Key Points:**
- Test pods run INSIDE the cluster, accessing services via K8s DNS
- Same network policies, resource limits, and security context as production
- Results exported via JUnit XML for CI integration
- Pods are ephemeral—created per test run, cleaned up after

---

## Test Runner Image

```dockerfile
# tests/Dockerfile
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY tests/ tests/
COPY src/ src/

ENTRYPOINT ["uv", "run", "pytest"]
```

---

## Local K8s Testing

Developers can run K8s tests locally:

```bash
# Create local Kind cluster
kind create cluster --name floe-dev

# Deploy minimal stack
helm install floe-dev ./charts/floe-platform --set minimal=true

# Run tests
kubectl apply -f tests/integration/test-job.yaml
kubectl logs -f job/integration-tests
```

---

## CI Resource Requirements

| Job | Runner | Memory | Time |
|-----|--------|--------|------|
| Unit | ubuntu-latest | 4GB | ~2min |
| Integration | ubuntu-latest | 8GB | ~5min |
| E2E | ubuntu-latest-8-cores | 16GB | ~12min |

---

## Related

- [Testing Index](index.md)
- [Integration Testing](integration-testing.md)
- [E2E Testing](e2e-testing.md)
- [CI/CD Pipeline](ci-cd.md)
- [ADR-0017: K8s Testing Infrastructure](../../architecture/adr/0017-k8s-testing-infrastructure.md)
