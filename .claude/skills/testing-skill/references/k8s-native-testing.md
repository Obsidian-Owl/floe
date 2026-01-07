# K8s-Native Testing Reference

## Overview

**Target State**: All integration and E2E tests run in ephemeral Kubernetes clusters (kind) for production parity.

**Current State (Epic 2 - Migration in Progress)**:
- Docker Compose (current baseline, 204KB, being phased out)
- kind (target state, 36KB, production parity)

---

## Why K8s-Native Testing?

### Production Parity

| Aspect | Docker Compose | kind (K8s-Native) |
|--------|----------------|-------------------|
| **Service discovery** | `/etc/hosts` hacks | K8s DNS (`service.namespace.svc.cluster.local`) |
| **Deployment method** | `docker-compose.yml` | Helm charts (same as production) |
| **Health probes** | Manual checks | K8s liveness/readiness/startup probes |
| **Init containers** | Not supported | Tested (seed data, migrations) |
| **Resource limits** | Docker limits | K8s ResourceQuota, LimitRanges |
| **Networking** | Bridge network | K8s NetworkPolicies, Services |
| **Secrets** | Environment variables | K8s Secrets, mounted volumes |

### Benefits

1. **Same artifacts in dev/CI/staging/production** - Helm charts tested locally
2. **K8s DNS resolution works** - No `/etc/hosts` modification
3. **Isolated namespaces** - Per-test or per-PR environments
4. **Fast ephemeral clusters** - kind creates cluster in <30s
5. **Production-like failures** - OOMKilled, CrashLoopBackOff, etc.

---

## kind Cluster Architecture

### Cluster Creation

```bash
# Create ephemeral kind cluster
kind create cluster --name floe-test --config testing/k8s/kind-config.yaml

# Load images into cluster (no registry needed)
docker build -t floe-test:latest .
kind load docker-image floe-test:latest --name floe-test

# Deploy Helm charts (same as production)
helm install floe-infra charts/floe-infrastructure/ \
  --namespace floe \
  --create-namespace \
  --values testing/k8s/values-test.yaml

# Wait for readiness
kubectl wait --for=condition=ready pod -l app=polaris --timeout=120s

# Run tests inside cluster
kubectl run test-runner \
  --image=floe-test:latest \
  --restart=Never \
  --namespace=floe \
  -- uv run pytest tests/ --cov

# Cleanup
kind delete cluster --name floe-test
```

### Test Execution Flow

```
make test-k8s
  └─> testing/k8s/scripts/run-all-tests.sh
        ├─> kind create cluster (ephemeral, <30s)
        ├─> docker build floe-test:latest
        ├─> kind load docker-image floe-test:latest
        ├─> helm install floe-infra-test (values-test.yaml)
        │     ├─ Polaris (Iceberg catalog)
        │     ├─ LocalStack (S3, STS, IAM)
        │     ├─ PostgreSQL (Dagster, Polaris)
        │     └─ Jaeger (OpenTelemetry)
        ├─> kubectl run test-runner --image=floe-test:latest
        │     └─> uv run pytest tests/ packages/*/tests/ --cov -v
        └─> kind delete cluster (cleanup)
```

---

## Migration Status (Epic 2)

### Phase 2A: Create K8s Test Infrastructure ✅ COMPLETE

- Created `testing/k8s/` directory structure
- Created `testing/k8s/scripts/run-all-tests.sh`
- Created `kind-config.yaml` with multi-node support
- Created `values-test.yaml` for test-specific Helm values

### Phase 2B: Validate K8s Tests in Parallel 🔄 IN PROGRESS

**Goal**: Run both Docker Compose and K8s tests in parallel to ensure parity.

```bash
# Run both environments
make test-all

# Expected:
# - Same tests pass in both environments
# - Same results (no environment-specific failures)
# - Validates migration readiness
```

**Validation Checklist**:
- [ ] All Docker Compose tests also pass in kind
- [ ] No environment-specific failures
- [ ] Performance comparable (K8s not significantly slower)
- [ ] Logs/debugging work in both environments

### Phase 2C: Switch Default 📋 PLANNED

**Breaking change**: Make `make test` default to K8s.

```makefile
# Before
test: test-integration  # Runs Docker Compose
test-k8s:               # Runs kind

# After (breaking change)
test: test-k8s          # Runs kind (default)
test-docker:            # Runs Docker Compose (legacy)
```

**Communication**: Announce breaking change, update documentation.

### Phase 2D: Remove Docker Compose 📋 PLANNED

**Goal**: Delete `testing/docker/` directory (204KB cleanup).

**Prerequisite**: Phase 2C complete, all teams migrated to K8s testing.

---

## kind Configuration

### kind-config.yaml

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      # Expose services on host for debugging
      - containerPort: 8181
        hostPort: 8181
        protocol: TCP  # Polaris
      - containerPort: 4566
        hostPort: 4566
        protocol: TCP  # LocalStack
      - containerPort: 16686
        hostPort: 16686
        protocol: TCP  # Jaeger UI

# Optional: Add worker nodes for multi-node testing
  - role: worker
```

### values-test.yaml

```yaml
# Test-specific overrides for Helm charts
polaris:
  replicaCount: 1  # Single replica for tests
  resources:
    requests:
      memory: 512Mi
      cpu: 500m
    limits:
      memory: 1Gi
      cpu: 1000m

localstack:
  service:
    type: ClusterIP  # Internal only
  persistence:
    enabled: false  # Ephemeral storage

postgresql:
  primary:
    persistence:
      enabled: false  # Ephemeral for tests
```

---

## K8s DNS Resolution

### Service Discovery

**In kind cluster**:
```python
# Service accessible via K8s DNS
polaris_host = "polaris.floe.svc.cluster.local"
polaris_port = 8181

# Or short name (same namespace)
polaris_host = "polaris"
```

**On host (for debugging)**:
```python
# Port-forward to access from host
# kubectl port-forward svc/polaris 8181:8181
polaris_host = "localhost"
polaris_port = 8181
```

### IntegrationTestBase Support

```python
from testing.base_classes.integration_test_base import IntegrationTestBase

class MyK8sTest(IntegrationTestBase):
    """Test using K8s service discovery."""

    required_services = [("polaris", 8181)]

    def test_something(self):
        # Automatically detects if running in K8s vs host
        host = self.get_service_host("polaris")
        # Returns "polaris" in K8s, "localhost" on host

        # Check infrastructure availability
        self.check_infrastructure("polaris", 8181)
```

---

## Isolated Namespaces

### Per-Test Namespaces

```python
import uuid
import pytest
from kubernetes import client, config

@pytest.fixture(scope="function")
def isolated_namespace():
    """Create isolated namespace for each test."""
    config.load_incluster_config()  # In-cluster
    v1 = client.CoreV1Api()

    # Create unique namespace
    namespace = f"test-{uuid.uuid4().hex[:8]}"
    v1.create_namespace(
        body=client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
    )

    yield namespace

    # Cleanup
    v1.delete_namespace(name=namespace)

def test_with_isolation(isolated_namespace):
    """Test runs in isolated namespace."""
    # Deploy resources to isolated_namespace
    # No risk of collision with other tests
```

### Per-PR Namespaces

```yaml
# GitHub Actions example
- name: Create PR namespace
  run: |
    kubectl create namespace pr-${{ github.event.pull_request.number }}

- name: Deploy to PR namespace
  run: |
    helm install floe-pr charts/floe-infrastructure/ \
      --namespace pr-${{ github.event.pull_request.number }}
```

---

## Debugging in K8s

### Common Commands

```bash
# Check pod status
kubectl get pods -n floe

# View logs
kubectl logs -n floe pod/test-runner

# Describe pod (see events)
kubectl describe pod -n floe test-runner

# Execute commands in pod
kubectl exec -n floe -it test-runner -- bash

# Port-forward for local access
kubectl port-forward -n floe svc/polaris 8181:8181
```

### Test Failure Debugging

```bash
# Get test runner logs
kubectl logs -n floe test-runner > test-output.log

# Check pod events
kubectl describe pod -n floe test-runner | grep -A 10 Events

# Check service availability
kubectl run debug --rm -it --image=curlimages/curl -- \
  curl http://polaris.floe.svc.cluster.local:8181/api/catalog/v1/config
```

---

## Performance Considerations

### kind Cluster Creation Time

| Operation | Time |
|-----------|------|
| `kind create cluster` | 20-30s (cold start) |
| `docker build` | 30-60s (cached: 5-10s) |
| `kind load docker-image` | 5-10s |
| `helm install` | 10-20s |
| **Total** | ~60-120s |

**Optimization**: Reuse cluster for multiple test runs (not ephemeral per test).

### Resource Usage

| Resource | Recommendation |
|----------|----------------|
| **RAM** | 4GB minimum for kind + services |
| **CPU** | 2 cores minimum |
| **Disk** | 10GB for images |

---

## CI Integration

### GitHub Actions Example

```yaml
name: K8s-Native Tests

on: [pull_request]

jobs:
  test-k8s:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install kind
        run: |
          curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
          chmod +x ./kind
          sudo mv ./kind /usr/local/bin/kind

      - name: Create kind cluster
        run: kind create cluster --config testing/k8s/kind-config.yaml

      - name: Run K8s-native tests
        run: make test-k8s

      - name: Cleanup
        if: always()
        run: kind delete cluster
```

---

## External Resources

- **kind Documentation**: https://kind.sigs.k8s.io/
- **Testcontainers K8s Module**: https://testcontainers-python.readthedocs.io/en/latest/k8s/
- **K8s Testing Best Practices**: https://kubernetes.io/docs/tasks/debug/
- **Epic 2 Migration Roadmap**: `docs/plan/MIGRATION-ROADMAP.md`
