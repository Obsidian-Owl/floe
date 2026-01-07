# Data Mesh Deployment Topology

For federated Data Mesh deployments, the architecture separates shared platform services from domain-specific workloads.

---

## 1. Namespace Structure

```
+---------------------------------------------------------------------------+
|                         KUBERNETES CLUSTER                                 |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  Namespace: floe-platform (Shared Services)                          |  |
|  |  Owner: Central Platform Team                                        |  |
|  |                                                                      |  |
|  |  * Polaris Catalog (shared across all domains)                       |  |
|  |  * OTLP Collector (federated traces/metrics/lineage)                 |  |
|  |  * Marquez (cross-domain lineage)                                    |  |
|  |  * MinIO / Object Storage (shared Iceberg warehouse)                 |  |
|  +----------------------------------+-----------------------------------+  |
|                                     |                                      |
|           +-------------------------+-------------------------+            |
|           v                         v                         v            |
|  +---------------------+   +---------------------+   +---------------------+|
|  | Namespace:          |   | Namespace:          |   | Namespace:          ||
|  | floe-sales-domain   |   | floe-marketing-domain|  | floe-finance-domain ||
|  |                     |   |                     |   |                     ||
|  | Orchestrator:       |   | Orchestrator:       |   | Orchestrator:       ||
|  | * Dagster webserver |   | * Airflow (domain   |   | * Dagster webserver ||
|  | * Dagster daemon    |   |   choice)           |   | * Dagster daemon    ||
|  | * PostgreSQL        |   | * PostgreSQL        |   | * PostgreSQL        ||
|  |                     |   |                     |   |                     ||
|  | Data Products:      |   | Data Products:      |   | Data Products:      ||
|  | * customer-360      |   | * campaign-perf     |   | * revenue-metrics   ||
|  | * order-analytics   |   | * attribution       |   | * cost-center       ||
|  +---------------------+   +---------------------+   +---------------------+|
|                                                                            |
+---------------------------------------------------------------------------+
```

---

## 2. Shared vs Domain-Specific Services

| Service | Deployment | Rationale |
|---------|------------|-----------|
| **Catalog (Polaris)** | Shared | Single source of truth for all domains |
| **Object Storage** | Shared | Unified Iceberg warehouse |
| **Lineage (Marquez)** | Shared | Cross-domain lineage visibility |
| **OTLP Collector** | Shared | Federated observability |
| **Orchestrator** | Per-domain | Domain autonomy in tooling |
| **Semantic Layer** | Per-domain | Domain-specific business logic |
| **PostgreSQL (orchestrator)** | Per-domain | Isolation of execution state |

---

## 3. Cross-Domain Service Discovery

Domains connect to shared services via K8s DNS:

```yaml
# Domain deployment references shared catalog
env:
  - name: POLARIS_HOST
    value: "polaris.floe-platform.svc.cluster.local"
  - name: OTLP_ENDPOINT
    value: "http://otel-collector.floe-platform.svc.cluster.local:4317"
  - name: OPENLINEAGE_URL
    value: "http://marquez.floe-platform.svc.cluster.local:5000"
```

---

## 4. Multi-Cluster Data Mesh

For large enterprises, domains may run in separate clusters:

```
+---------------------+      +---------------------+      +---------------------+
|  SHARED SERVICES    |      |  SALES CLUSTER      |      |  MARKETING CLUSTER  |
|  CLUSTER            |      |  (Region: us-east)  |      |  (Region: eu-west)  |
|                     |      |                     |      |                     |
|  * Polaris Catalog  |<---->|  * Dagster          |<---->|  * Airflow          |
|  * Marquez Lineage  |      |  * Sales Products   |      |  * Marketing Prods  |
|  * Central OTLP     |      |  * Local OTLP       |      |  * Local OTLP       |
+---------------------+      +---------------------+      +---------------------+
         ^                            |                            |
         |                            |                            |
         +----------------------------+----------------------------+
                          Cross-cluster networking
                          (Service Mesh / Ingress)
```

---

## 5. Data Mesh Helm Deployment

```bash
# 1. Deploy shared services (Central Platform Team)
helm install floe-platform charts/floe-platform \
  --namespace floe-platform \
  --values enterprise-values.yaml

# 2. Deploy domain services (Domain Platform Team)
helm install sales-domain charts/floe-domain \
  --namespace floe-sales-domain \
  --set domain.name=sales \
  --set domain.enterprise.ref=oci://registry/enterprise:v1.0.0

# 3. Deploy data products (Product Team)
floe product init --domain=sales:v1.0.0
floe product register
```

---

## Related Documentation

- [ADR-0021: Data Architecture Patterns](../../architecture/adr/0021-data-architecture-patterns.md) - Full Data Mesh documentation
- [Two-Layer Model](two-layer-model.md) - Basic deployment model
- [Production](production.md) - Production considerations
