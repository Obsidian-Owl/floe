# ADR-0017: Kubernetes-Based Testing Infrastructure

## Status

Accepted

## Context

floe is a Kubernetes-native data platform. The production deployment uses:
- Helm charts for all services (Dagster, Polaris, Cube)
- K8s Jobs for pipeline execution
- K8s Service discovery for inter-service communication
- K8s NetworkPolicies, ResourceQuotas, and SecurityContexts

Traditional CI testing approaches run tests on CI runners (e.g., GitHub Actions `ubuntu-latest`) using Docker Compose or testcontainers. This creates a significant gap:

| Aspect | Docker Compose | Kubernetes |
|--------|---------------|------------|
| Networking | Docker bridge network | CNI (Calico, Cilium) |
| Service Discovery | Container names | K8s DNS (*.svc.cluster.local) |
| Resource Limits | Docker constraints | K8s requests/limits |
| Health Checks | Docker healthcheck | K8s liveness/readiness probes |
| Pod Lifecycle | N/A | Init containers, sidecars |
| Security | Docker user | SecurityContext, PodSecurityPolicy |
| Storage | Docker volumes | PVCs, StorageClasses |

**The Problem:**
- Bugs that only manifest in K8s (networking, DNS, resource limits) are not caught until staging/production
- Helm chart errors are not detected in CI
- Service mesh, network policies, and security contexts are not tested
- "Works in Docker Compose, fails in K8s" is a common failure mode

**Key Principle:**
> "Test like you fly, fly like you test" — If production runs in K8s, tests must run in K8s.

## Decision

**Integration and E2E tests will run inside Kubernetes pods, not on CI runners.**

### Testing Pyramid with Infrastructure Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  E2E TESTS                                                                   │
│  Environment: Kind cluster (full Helm deployment)                           │
│  Stack: Dagster + Polaris + Cube + Observability                           │
│  Tests: Complete pipeline scenarios, cross-service workflows               │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ▲
┌─────────────────────────────────────────────────────────────────────────────┐
│  INTEGRATION TESTS                                                           │
│  Environment: Kind cluster (minimal Helm deployment)                        │
│  Stack: Dagster + DuckDB only                                              │
│  Tests: Component interactions, service discovery, API contracts           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     ▲
┌─────────────────────────────────────────────────────────────────────────────┐
│  UNIT TESTS                                                                  │
│  Environment: CI runner (no K8s)                                           │
│  Stack: None                                                                │
│  Tests: Pure functions, schema validation, isolated logic                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Implementation Approach

#### 1. Kind Clusters in CI

Use [Kind (Kubernetes IN Docker)](https://kind.sigs.k8s.io/) to create ephemeral K8s clusters in GitHub Actions:

```yaml
- name: Create Kind cluster
  uses: helm/kind-action@v1
  with:
    cluster_name: floe-test
```

#### 2. Test Execution as K8s Jobs

Tests run as Kubernetes Jobs inside the cluster:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: integration-tests
  namespace: floe-test
spec:
  backoffLimit: 0  # Fail fast
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
```

#### 3. Same Helm Charts as Production

The exact same Helm charts deployed in CI are deployed to production:

```yaml
- name: Deploy floe-platform
  run: |
    helm install floe-test ./charts/floe-platform \
      --namespace floe-test --create-namespace \
      --wait --timeout=10m
```

#### 4. Result Collection

Test results are collected from pods and uploaded as CI artifacts:

```yaml
- name: Collect results
  run: |
    kubectl logs job/integration-tests -n floe-test > test-results.log
    kubectl cp floe-test/integration-tests:/results/junit.xml ./junit.xml
```

### Test Environment Specifications

| Environment | Cluster | Deployment | Use Case |
|-------------|---------|------------|----------|
| Unit | None | None | Fast, isolated tests |
| Integration | Kind (single-node) | Minimal (Dagster only) | Component integration |
| E2E | Kind (multi-node) | Full stack | Complete workflows |
| Staging | Dedicated EKS/GKE | Production config | Soak tests, benchmarks |

### CI Workflow Structure

```yaml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    # Fast, no K8s needed

  integration-tests:
    needs: [unit-tests]
    runs-on: ubuntu-latest
    steps:
      - Create Kind cluster
      - Helm install floe-platform (minimal)
      - Run test Job in K8s
      - Collect results

  e2e-tests:
    needs: [integration-tests]
    runs-on: ubuntu-latest
    steps:
      - Create Kind cluster (multi-node)
      - Helm install floe-platform (full)
      - Run test Job in K8s
      - Collect results
```

## Consequences

### Positive

- **Infrastructure Parity**: Tests run on the same infrastructure as production
- **Helm Chart Validation**: Chart errors caught in CI, not production
- **K8s-Native Testing**: Service discovery, network policies, and security contexts are tested
- **Realistic Failure Modes**: K8s-specific issues (OOMKilled, CrashLoopBackOff) surface in CI
- **Confidence**: Passing CI means the Helm deployment actually works
- **Debugging**: Test pods can be inspected with `kubectl logs`, `kubectl exec`

### Negative

- **Slower CI**: Kind cluster creation adds ~2-3 minutes to pipeline
- **Resource Requirements**: CI runners need more memory for Kind + services
- **Complexity**: Test infrastructure is more complex than `pytest` on runner
- **Debugging Difficulty**: Failed tests require K8s knowledge to debug
- **Flaky Tests**: K8s startup timing can cause intermittent failures

### Mitigations

| Risk | Mitigation |
|------|------------|
| Slow CI | Parallelize unit tests; cache Docker images |
| Resource limits | Use GitHub large runners for E2E jobs |
| Complexity | Provide `make test-integration` for local K8s testing |
| Debugging | Always collect pod logs as artifacts |
| Flakiness | Implement proper health check waits; use `kubectl wait` |

### Neutral

- **Local Development**: Developers can still run unit tests locally without K8s
- **Test Image**: Requires maintaining a `test-runner` container image
- **Kind Version**: Must track Kind/K8s version compatibility

## Alternatives Considered

### 1. Docker Compose for Integration Tests

**Rejected because:**
- Does not test K8s-specific behavior (DNS, probes, resource limits)
- Helm chart bugs not detected
- "Works in Compose, fails in K8s" is too common

### 2. Testcontainers with K8s

**Rejected because:**
- Testcontainers K8s module is less mature
- Still runs on CI runner, not inside cluster
- Does not test service discovery via K8s DNS

### 3. Remote Test Cluster

**Partially adopted for staging:**
- Good for soak tests and performance benchmarks
- Too slow for CI (network latency, shared state)
- Cost implications for always-on cluster

### 4. Minikube Instead of Kind

**Rejected because:**
- Kind is faster to start
- Kind is more CI-friendly (Docker-in-Docker)
- Kind has better GitHub Actions support

## Implementation Notes

### Test Runner Image

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

### Local Testing

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

### CI Resource Requirements

| Job | Runner | Memory | Time |
|-----|--------|--------|------|
| Unit | ubuntu-latest | 4GB | ~2min |
| Integration | ubuntu-latest | 8GB | ~5min |
| E2E | ubuntu-latest-8-cores | 16GB | ~12min |

## References

- [Kind Documentation](https://kind.sigs.k8s.io/)
- [helm/kind-action](https://github.com/helm/kind-action)
- [Testing Kubernetes Operators](https://sdk.operatorframework.io/docs/building-operators/golang/testing/)
- [08-quality.md](../../guides/08-quality.md) - Testing strategy documentation
- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md)
