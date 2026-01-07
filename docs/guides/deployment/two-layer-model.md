# Two-Layer Deployment Model

floe deployment separates two concerns:

| Layer | Owner | K8s Resource | Lifecycle |
|-------|-------|--------------|-----------|
| **Platform Services** | Platform Team | Deployment, StatefulSet | Long-lived, upgraded |
| **Pipeline Jobs** | Data Team (execution) | Job | Run-to-completion |

```
+---------------------------------------------------------------------------+
|  PLATFORM SERVICES (Layer 3 - Long-lived)                                  |
|  Deployed by: floe platform deploy                                         |
|                                                                            |
|  +---------------------------------------------------------------------+   |
|  |  Orchestrator (Dagster):     Catalog (Polaris):    Semantic (Cube): |   |
|  |  * webserver (Deployment)    * server (Deployment) * server (Deploy) |   |
|  |  * daemon (Deployment)       * PostgreSQL          * Redis           |   |
|  |  * PostgreSQL (StatefulSet)                                         |   |
|  +---------------------------------------------------------------------+   |
|                                                                            |
|  +---------------------------------------------------------------------+   |
|  |  Observability:              Storage:                               |   |
|  |  * OTLP Collector            * MinIO / S3 / GCS / ADLS              |   |
|  |  * Prometheus (optional)     * OCI Registry (platform artifacts)    |   |
|  |  * Grafana (optional)                                               |   |
|  +---------------------------------------------------------------------+   |
+----------------------------------+-----------------------------------------+
                                   | Triggers
                                   v
+---------------------------------------------------------------------------+
|  PIPELINE JOBS (Layer 4 - Ephemeral)                                       |
|  Triggered by: Orchestrator on schedule/sensor                             |
|                                                                            |
|  +---------------------------------------------------------------------+   |
|  |  dbt run pods (K8s Job)      Quality check pods    Ingestion pods   |   |
|  |  * Run-to-completion         (K8s Job)             (K8s Job)        |   |
|  |  * Inherit platform config   * Run-to-completion   * dlt pipelines  |   |
|  +---------------------------------------------------------------------+   |
+---------------------------------------------------------------------------+
```

## Platform Services (Layer 3)

Platform services run continuously and are managed by Platform Team.

| Characteristic | Value |
|----------------|-------|
| **K8s Resource** | Deployment, StatefulSet |
| **Lifecycle** | Long-lived, upgraded in place |
| **State** | Stateful (databases, caches) |
| **Scaling** | Fixed replicas or HPA |
| **Deployment** | `floe platform deploy` |
| **Upgrades** | Rolling updates, blue-green |
| **Owner** | Platform Team |

## Pipeline Jobs (Layer 4)

Pipeline jobs run to completion and are triggered by the orchestrator.

| Characteristic | Value |
|----------------|-------|
| **K8s Resource** | Job |
| **Lifecycle** | Run-to-completion |
| **State** | Stateless |
| **Scaling** | One pod per execution |
| **Deployment** | Triggered by orchestrator |
| **Retries** | Handled by orchestrator |
| **Owner** | Data Team (execution), Platform Team (infrastructure) |

## Related Documentation

- [Kubernetes Helm](kubernetes-helm.md) - Helm chart deployment
- [Platform Services](../../architecture/platform-services.md) - Service details
- [ADR-0019](../../architecture/adr/0019-platform-services-lifecycle.md) - Lifecycle decisions
