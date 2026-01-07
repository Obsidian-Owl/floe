# Platform Services

This document describes the long-lived services in Layer 3 of the floe architecture.

## Service Categories

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PLATFORM SERVICES (Layer 3)                                             │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  ORCHESTRATOR (Plugin)                                               ││
│  │  Default: Dagster │ Alternatives: Airflow, Prefect                  ││
│  │                                                                      ││
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        ││
│  │  │   Webserver    │  │    Daemon      │  │   PostgreSQL   │        ││
│  │  │  (Deployment)  │  │  (Deployment)  │  │ (StatefulSet)  │        ││
│  │  └────────────────┘  └────────────────┘  └────────────────┘        ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  CATALOG (Plugin)                                                    ││
│  │  Default: Polaris │ Alternatives: AWS Glue, Hive, Nessie            ││
│  │                                                                      ││
│  │  ┌────────────────┐  ┌────────────────┐                             ││
│  │  │  Polaris API   │  │   PostgreSQL   │                             ││
│  │  │  (Deployment)  │  │ (StatefulSet)  │                             ││
│  │  └────────────────┘  └────────────────┘                             ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  SEMANTIC LAYER (Plugin)                                             ││
│  │  Default: Cube │ Alternatives: dbt Semantic Layer, None             ││
│  │                                                                      ││
│  │  ┌────────────────┐  ┌────────────────┐                             ││
│  │  │  Cube Server   │  │     Redis      │                             ││
│  │  │  (Deployment)  │  │ (StatefulSet)  │                             ││
│  │  └────────────────┘  └────────────────┘                             ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  OBSERVABILITY (Enforced)                                            ││
│  │  OpenTelemetry + OpenLineage                                        ││
│  │                                                                      ││
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        ││
│  │  │ OTLP Collector │  │   Prometheus   │  │    Grafana     │        ││
│  │  │  (Deployment)  │  │ (StatefulSet)  │  │  (Deployment)  │        ││
│  │  └────────────────┘  └────────────────┘  └────────────────┘        ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  STORAGE                                                             ││
│  │  Object Storage + OCI Registry                                      ││
│  │                                                                      ││
│  │  ┌────────────────┐  ┌────────────────┐                             ││
│  │  │     MinIO      │  │  OCI Registry  │                             ││
│  │  │ (StatefulSet)  │  │   (External)   │                             ││
│  │  └────────────────┘  └────────────────┘                             ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

## Service Specifications

### Orchestrator Services

| Service | K8s Resource | Purpose | Dependencies |
|---------|--------------|---------|--------------|
| Dagster Webserver | Deployment | UI, API | PostgreSQL |
| Dagster Daemon | Deployment | Scheduling, sensors | PostgreSQL |
| PostgreSQL | StatefulSet | Job history, state | PVC |

**Resource Allocation:**
```yaml
webserver:
  replicas: 2
  resources:
    requests: { cpu: 500m, memory: 512Mi }
    limits: { cpu: 1000m, memory: 1Gi }

daemon:
  replicas: 1
  resources:
    requests: { cpu: 250m, memory: 256Mi }
    limits: { cpu: 500m, memory: 512Mi }
```

### Catalog Services

| Service | K8s Resource | Purpose | Dependencies |
|---------|--------------|---------|--------------|
| Polaris Server | Deployment | Iceberg catalog API | PostgreSQL |
| PostgreSQL | StatefulSet | Catalog metadata | PVC |

**Endpoints:**
- REST API: `http://polaris.floe-platform.svc.cluster.local:8181`
- Iceberg catalog URI: `http://polaris.floe-platform.svc.cluster.local:8181/api/catalog`

### Semantic Layer Services

| Service | K8s Resource | Purpose | Dependencies |
|---------|--------------|---------|--------------|
| Cube Server | Deployment | Semantic layer API | Redis, Catalog |
| Redis | StatefulSet | Query cache | PVC |

**Endpoints:**
- REST API: `http://cube.floe-platform.svc.cluster.local:4000`
- GraphQL: `http://cube.floe-platform.svc.cluster.local:4000/cubejs-api/graphql`

### Observability Services

| Service | K8s Resource | Purpose | Dependencies |
|---------|--------------|---------|--------------|
| OTLP Collector | Deployment | Telemetry collection | None |
| Prometheus | StatefulSet | Metrics storage | PVC |
| Grafana | Deployment | Dashboards | Prometheus |

**Telemetry Flow:**
```
Jobs → OTLP Collector → Prometheus (metrics)
                     → Jaeger/Grafana Tempo (traces)
                     → Loki (logs)
```

### Storage Services

| Service | K8s Resource | Purpose | Dependencies |
|---------|--------------|---------|--------------|
| MinIO | StatefulSet | Object storage (Iceberg data) | PVC |
| OCI Registry | External | Platform artifacts | External |

## Deployment

### Deploy All Services

```bash
# Deploy all platform services
floe platform deploy

# Output:
Deploying platform services to namespace: floe-platform
  ✓ Namespace created
  ✓ PostgreSQL (orchestrator-db): StatefulSet 1/1 ready
  ✓ PostgreSQL (catalog-db): StatefulSet 1/1 ready
  ✓ Redis (semantic-cache): StatefulSet 1/1 ready
  ✓ MinIO: StatefulSet 4/4 ready
  ✓ Polaris: Deployment 2/2 ready
  ✓ Dagster webserver: Deployment 2/2 ready
  ✓ Dagster daemon: Deployment 1/1 ready
  ✓ Cube: Deployment 2/2 ready
  ✓ OTLP Collector: Deployment 2/2 ready

Platform services deployed successfully!
```

### Deploy Specific Component

```bash
floe platform deploy --component=orchestrator
floe platform deploy --component=catalog
floe platform deploy --component=semantic
floe platform deploy --component=observability
```

### Check Status

```bash
floe platform status

# Output:
Platform: acme-data-platform v1.2.3
Namespace: floe-platform

Services:
  orchestrator:
    webserver: 2/2 ready (healthy)
    daemon: 1/1 ready (healthy)
    database: 1/1 ready
  catalog:
    polaris: 2/2 ready (healthy)
    database: 1/1 ready
  semantic:
    cube: 2/2 ready (healthy)
    cache: 1/1 ready
  observability:
    otlp-collector: 2/2 ready
    prometheus: 1/1 ready
    grafana: 1/1 ready
```

## Health Checks

All services expose health endpoints:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

## Startup Order

Services start in dependency order:

1. **Storage** (MinIO, PostgreSQL instances)
2. **Catalog** (Polaris) - depends on PostgreSQL
3. **Observability** (OTLP Collector, Prometheus)
4. **Orchestrator** (Dagster) - depends on PostgreSQL
5. **Semantic Layer** (Cube) - depends on Catalog

## Scaling

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dagster-webserver
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dagster-webserver
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### StatefulSet Considerations

Databases (PostgreSQL, Redis) use StatefulSets and typically don't autoscale:
- Use vertical scaling (increase resources)
- Consider managed services for production (RDS, ElastiCache)

## Networking

### Service Discovery

All services use K8s DNS:
```
<service>.<namespace>.svc.cluster.local
```

Examples:
- `dagster-webserver.floe-platform.svc.cluster.local:3000`
- `polaris.floe-platform.svc.cluster.local:8181`
- `cube.floe-platform.svc.cluster.local:4000`

### Ingress

```yaml
# platform-manifest.yaml
services:
  orchestrator:
    ingress:
      enabled: true
      host: dagster.platform.example.com
  catalog:
    ingress:
      enabled: true
      host: catalog.platform.example.com
```

## Related Documents

- [ADR-0019: Platform Services Lifecycle](adr/0019-platform-services-lifecycle.md)
- [Four-Layer Overview](four-layer-overview.md)
- [06-deployment-view.md](../guides/06-deployment-view.md)
