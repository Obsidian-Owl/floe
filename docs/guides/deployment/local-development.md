# Local Development

This document covers local development for floe using uv and Kind (Kubernetes in Docker).

**Note**: Docker Compose is NOT supported. All development uses Kubernetes-native tooling to ensure parity between local development and production (ADR-0017).

---

## 1. Local Development (uv)

### 1.1 Installation

```bash
# Create virtual environment with uv
uv venv
source .venv/bin/activate

# Install CLI and dependencies
uv add floe-cli

# For specific compute targets (dbt adapters)
uv add dbt-duckdb      # Default OSS compute
uv add dbt-snowflake   # Snowflake
uv add dbt-bigquery    # BigQuery
```

### 1.2 Project Setup

```bash
# Initialize project
floe init my-project
cd my-project

# Validate configuration
floe validate

# Run pipeline (uses configured compute target)
floe run --env dev
```

### 1.3 Local Architecture

```
+---------------------------------------------------------------+
|                     LOCAL MACHINE                              |
|                                                                |
|  +---------------------------------------------------------+  |
|  |  floe-cli process                                        |  |
|  |                                                          |  |
|  |  +---------+   +---------+   +---------+                 |  |
|  |  | Dagster |-->|   dbt   |-->| DuckDB  |                 |  |
|  |  | (in-    |   |  (in-   |   |  (in-   |                 |  |
|  |  | process)|   | process)|   | process)|                 |  |
|  |  +---------+   +---------+   +---------+                 |  |
|  |                                                          |  |
|  +---------------------------------------------------------+  |
|                                                                |
|  +-----------------+   +-----------------+                     |
|  | ./warehouse/    |   | .floe/          |                     |
|  | +- data.duckdb  |   | +- artifacts.json|                    |
|  +-----------------+   +-----------------+                     |
+---------------------------------------------------------------+
```

### 1.4 Limitations

- No persistent Dagster UI (run-and-exit)
- No built-in observability backends
- Single-user, single-machine only

---

## 2. Local Kubernetes (Kind)

For full-featured local development with all platform services, use Kind (Kubernetes in Docker).

### 2.1 Quick Start

```bash
# Create Kind cluster
make kind-create

# Deploy platform services
make deploy-local

# Verify deployment
kubectl get pods -n floe-dev
```

### 2.2 Architecture

```
+---------------------------------------------------------------------------+
|                           KIND CLUSTER                                      |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  namespace: floe-dev                                                 |  |
|  |                                                                      |  |
|  |  +---------------+   +---------------+   +---------------+           |  |
|  |  |   dagster     |   |   postgres    |   |   polaris     |           |  |
|  |  |  (Deployment) |-->| (StatefulSet) |<--|  (Deployment) |           |  |
|  |  +---------------+   +---------------+   +---------------+           |  |
|  |         |                   |                    |                   |  |
|  |         v                   v                    v                   |  |
|  |  +---------------+   +---------------+   +---------------+           |  |
|  |  | otel-collector|   |  localstack   |   |     cube      |           |  |
|  |  |  (DaemonSet)  |   | (StatefulSet) |   |  (Deployment) |           |  |
|  |  +---------------+   +---------------+   +---------------+           |  |
|  |                                                                      |  |
|  +---------------------------------------------------------------------+  |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  PersistentVolumeClaims                                              |  |
|  |  +-- postgres-data (10Gi)                                            |  |
|  |  +-- localstack-data (10Gi)                                          |  |
|  +---------------------------------------------------------------------+  |
+---------------------------------------------------------------------------+
```

### 2.3 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Dagster UI | http://localhost:30000 | Asset management, runs |
| Polaris | http://localhost:30181 | Iceberg catalog |
| Cube | http://localhost:30400 | Semantic layer API |
| LocalStack | http://localhost:30566 | S3-compatible storage |

### 2.4 Development Workflow

```bash
# Run tests in K8s
make test

# View logs
kubectl logs -f deployment/dagster-webserver -n floe-dev

# Port-forward for debugging
kubectl port-forward svc/dagster-webserver 3000:3000 -n floe-dev

# Clean up
make kind-delete
```

### 2.5 Why Not Docker Compose?

Docker Compose is **explicitly prohibited** (REQ-621) because:

1. **No K8s-specific testing**: Cannot test probes, resource limits, network policies
2. **No parity**: Docker Compose ≠ production K8s environment
3. **Hidden bugs**: Issues only discovered in production
4. **No RBAC testing**: Cannot test service accounts, secrets access

Kind provides full Kubernetes compatibility while running locally.

---

## Related Documentation

- [Kubernetes Helm](kubernetes-helm.md) - Production deployment
- [Two-Layer Model](two-layer-model.md) - Deployment model overview
