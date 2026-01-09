# Research: K8s-Native Testing Infrastructure

**Feature**: 001-testing-infra
**Date**: 2026-01-09
**Status**: Complete

## Research Areas

This document captures research findings for implementing the K8s-native testing infrastructure.

---

## 1. Kind Cluster Configuration

### Decision
Use `helm/kind-action@v1` with explicit version pinning and optimized configuration.

### Rationale
- Fastest cluster creation time (30-60s with caching)
- Native GitHub Actions integration
- Best Docker-in-Docker support
- Image caching reduces CI time significantly

### Recommended Configuration

```yaml
# testing/k8s/kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: floe-test
nodes:
  - role: control-plane
    image: kindest/node:v1.29.0
    kubeadmConfigPatches:
      - |
        kind: KubeletConfiguration
        systemReserved:
          cpu: 100m
          memory: 100Mi
        kubeReserved:
          cpu: 50m
          memory: 50Mi
networking:
  podSubnet: "10.244.0.0/16"
  serviceSubnet: "10.96.0.0/16"
  kubeProxyMode: iptables
```

### Key Points
- Pin explicit Kind and kubectl versions for reproducibility
- Set `wait: 60s` in kind-action for service readiness
- Use `kind load docker-image` to preload images
- Export logs on failure: `kind export logs`

### Alternatives Considered
- **Minikube**: Rejected - slower startup, less CI-friendly
- **k3d**: Considered - lightweight but less GitHub Actions support
- **Remote cluster**: Reserved for staging/soak tests only

---

## 2. Test-Runner Container Image

### Decision
Multi-stage Dockerfile with `uv` for fast dependency installation, pytest as entrypoint.

### Rationale
- `uv` provides 10-100x faster dependency installation
- Multi-stage build reduces image size by 40%
- JUnit XML output integrates with all CI systems
- EmptyDir volumes for artifact collection

### Recommended Dockerfile Structure

```dockerfile
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Create venv (non-portable, must be created in container)
RUN python -m venv /opt/venv --upgrade-deps

# Copy and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip sync uv.lock

# Copy source
COPY . .

# Artifacts directory
RUN mkdir -p /artifacts && chmod 777 /artifacts

ENTRYPOINT ["pytest"]
CMD ["tests/", "-v", "--junitxml=/artifacts/results.xml"]
```

### Artifact Collection Pattern

```yaml
# K8s Job spec
volumes:
- name: artifacts
  emptyDir:
    sizeLimit: 1Gi

# Post-job extraction
kubectl cp <pod>:/artifacts ./test-results/
```

### Alternatives Considered
- **Testkube**: Full-featured but additional dependency
- **Host execution with port-forward**: Rejected per ADR-0017 (tests must run inside cluster)

---

## 3. Pytest Requirement Traceability

### Decision
Custom `@pytest.mark.requirement()` marker with pytest hooks for collection and a CLI tool for CI enforcement.

### Rationale
- Lightweight solution without external dependencies
- Integrates with existing Linear + Beads workflow
- Transparent implementation (not a black box)
- 100% coverage enforcement via exit code

### Implementation Pattern

**Marker Registration (pyproject.toml)**:
```toml
[tool.pytest.ini_options]
markers = [
    "requirement(id): Mark test with requirement ID for traceability",
]
```

**Collection Hook (conftest.py)**:
```python
def pytest_collection_finish(session: pytest.Session) -> None:
    """Collect requirement markers for traceability report."""
    for item in session.items:
        for marker in item.iter_markers(name="requirement"):
            req_id = marker.args[0]
            # Store: requirement → [test_ids]
```

**CI Verification**:
```bash
python -m testing.traceability --all --threshold 100
# Exit code 1 if coverage < 100%
```

### Key Points
- Multiple markers allowed per test (stacked decorators)
- Requirement ID format: `001-FR-001` (spec prefix + functional requirement)
- CI gate fails if any test lacks marker
- Report outputs JSON for integration with Linear

### Alternatives Considered
- **pytest-allure-spec-coverage**: Requires Allure dependency
- **pytest-cov**: Code coverage, not requirement coverage
- **External traceability tools**: Overkill for this use case

---

## 4. Service Fixtures Architecture

### Decision
Pytest fixtures using Kubernetes Python client with polling utilities for health checks.

### Rationale
- K8s Python client provides native pod/service access
- Polling utilities prevent flaky tests from hardcoded sleeps
- Unique namespaces per test ensure isolation

### Fixture Pattern

```python
@pytest.fixture
def postgres_connection(k8s_client) -> Generator[Connection, None, None]:
    """PostgreSQL connection fixture."""
    namespace = generate_unique_namespace("postgres")

    # Wait for service
    wait_for_service("postgres", 5432, namespace=namespace)

    # Create connection
    conn = psycopg2.connect(
        host=f"postgres.{namespace}.svc.cluster.local",
        port=5432,
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )

    yield conn

    # Cleanup
    conn.close()
    delete_namespace(namespace)
```

### Service Manifest Pattern (Raw K8s, NOT Helm)

```yaml
# testing/k8s/services/postgres.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: floe-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
```

### Key Points
- Raw K8s manifests avoid circular dependency on Epic 9B (Helm)
- Each service gets dedicated fixture module
- Fixtures clean up namespaces on teardown
- Service discovery via K8s DNS: `<service>.<namespace>.svc.cluster.local`

---

## 5. CI Workflow Extensions (Stage 2)

### Decision
Add `security` and `integration-tests` jobs to existing `.github/workflows/ci.yml`.

### Rationale
- Extends existing Stage 1 CI (already complete)
- Security scanning catches vulnerabilities early
- Integration tests validate K8s deployment patterns
- ci-success gate ensures all jobs pass

### Recommended Workflow Structure

```yaml
jobs:
  # Existing Stage 1 jobs...

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Bandit
        run: bandit -r packages/ -ll
      - name: Run pip-audit
        run: pip-audit

  integration-tests:
    needs: [unit-tests, security]
    runs-on: ubuntu-latest
    steps:
      - uses: helm/kind-action@v1
        with:
          cluster_name: floe-test
          config: testing/k8s/kind-config.yaml
      - name: Deploy services
        run: kubectl apply -f testing/k8s/services/
      - name: Wait for services
        run: kubectl wait --for=condition=ready pods --all -n floe-test
      - name: Run integration tests
        run: make test-integration
      - name: Collect results
        if: always()
        run: kubectl logs job/test-runner -n floe-test > test-results.log

  ci-success:
    needs: [lint-typecheck, unit-tests, contract-tests, sonarcloud, security, integration-tests]
    runs-on: ubuntu-latest
    steps:
      - run: echo "All CI checks passed"
```

### Key Points
- Security job runs in parallel with unit-tests (fast feedback)
- Integration tests depend on unit-tests + security
- ci-success gate updated to include new jobs
- Artifact upload for test results on failure

---

## 6. Makefile Targets

### Decision
Add test-focused Makefile targets that abstract pytest and Kind commands.

### Recommended Targets

```makefile
# Kind cluster management
.PHONY: kind-up kind-down

kind-up:
	@echo "Creating Kind cluster..."
	kind create cluster --name floe-test --config testing/k8s/kind-config.yaml
	kubectl apply -f testing/k8s/services/
	kubectl wait --for=condition=ready pods --all -n floe-test --timeout=120s

kind-down:
	@echo "Destroying Kind cluster..."
	kind delete cluster --name floe-test

# Test targets
.PHONY: test test-unit test-integration test-e2e

test: test-unit test-integration

test-unit:
	@echo "Running unit tests..."
	pytest packages/*/tests/unit tests/contract -v --cov

test-integration: kind-up
	@echo "Running integration tests in K8s..."
	kubectl apply -f testing/k8s/jobs/test-runner.yaml
	kubectl wait --for=condition=complete job/integration-tests -n floe-test --timeout=600s

test-e2e: kind-up
	@echo "Running E2E tests in K8s..."
	kubectl apply -f testing/k8s/jobs/e2e-runner.yaml
	kubectl wait --for=condition=complete job/e2e-tests -n floe-test --timeout=900s

# Full CI check
.PHONY: check
check: lint typecheck test
	@echo "All checks passed"
```

---

## Summary

| Area | Decision | Key Benefit |
|------|----------|-------------|
| Kind Cluster | helm/kind-action with pinned versions | Fast, reproducible CI |
| Test Runner | Multi-stage Dockerfile with uv | 10x faster builds |
| Traceability | Custom pytest hooks + CLI | 100% enforcement, no deps |
| Fixtures | K8s Python client + polling | Reliable, no sleeps |
| CI Stage 2 | Extend existing ci.yml | Security + integration |
| Makefile | Abstract Kind + pytest | Developer ergonomics |

All research items resolved. Proceeding to Phase 1 design.
