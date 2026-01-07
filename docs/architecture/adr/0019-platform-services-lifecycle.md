# ADR-0019: Platform Services Lifecycle

## Status

Accepted

## Context

floe operates two fundamentally different types of workloads:

1. **Long-lived services** - Orchestrator UIs, catalog servers, semantic layer APIs
2. **Ephemeral jobs** - dbt runs, pipeline executions, data quality checks

Without clear lifecycle boundaries:
- Teams conflate deployment strategies
- State management becomes unclear
- Scaling approaches are inappropriate
- Debugging is difficult

## Decision

Define distinct lifecycle models for platform services vs pipeline jobs.

### Layer 3: Platform Services (Long-lived)

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

**Services:**

| Service | K8s Resource | State | Purpose |
|---------|--------------|-------|---------|
| Dagster webserver | Deployment | PostgreSQL | Orchestrator UI |
| Dagster daemon | Deployment | PostgreSQL | Job scheduling |
| Polaris server | Deployment | PostgreSQL | Iceberg catalog |
| Cube server | Deployment | Redis | Semantic layer API |
| OTLP Collector | Deployment | None | Telemetry collection |
| Prometheus | StatefulSet | PVC | Metrics storage |
| Grafana | Deployment | PVC | Dashboards |
| MinIO | StatefulSet | PVC | Object storage |

### Layer 4: Pipeline Jobs (Ephemeral)

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

**Jobs:**

| Job Type | Trigger | Duration | Output |
|----------|---------|----------|--------|
| dbt run | Schedule/manual | Minutes | Iceberg tables |
| dbt test | Post-run | Seconds | Test results |
| dlt ingestion | Schedule | Minutes | Raw tables |
| Quality checks | Post-run | Seconds | Pass/fail |

## Consequences

### Positive

- **Clear ownership** - Platform Team owns services, Data Team triggers jobs
- **Appropriate scaling** - Services use HPA, jobs scale per-execution
- **State clarity** - Services manage state, jobs are stateless
- **Debugging** - Different tooling per layer (`kubectl logs` vs job history)

### Negative

- **Complexity** - Two deployment models to understand
- **Coordination** - Services must be up before jobs can run
- **Resource planning** - Different capacity planning per layer

### Neutral

- Orchestrator bridges the gap (service that manages jobs)
- Both layers use standard K8s resources

## Deployment Commands

### Platform Services (Layer 3)

```bash
# Deploy all platform services
floe platform deploy

# Deploy specific service
floe platform deploy --component=orchestrator

# Upgrade services
floe platform upgrade --version=1.3.0

# Check service health
floe platform status

# View service logs
floe platform logs orchestrator
floe platform logs catalog
```

### Pipeline Jobs (Layer 4)

```bash
# Trigger pipeline run (creates K8s Job)
floe run

# View job status
floe status

# View job logs
floe logs --run-id=abc123

# Jobs are also visible via orchestrator UI
```

## Service Dependencies

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PIPELINE JOBS (Layer 4) - Ephemeral                                     │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  dbt-run-abc123 (Job)                                              │  │
│  │  └─ Connects to: compute, catalog, OTLP                           │  │
│  │                                                                     │  │
│  │  dlt-ingest-xyz789 (Job)                                           │  │
│  │  └─ Connects to: catalog, OTLP                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ Requires
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PLATFORM SERVICES (Layer 3) - Long-lived                                │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Orchestrator│  │   Catalog   │  │  Semantic   │  │ Observability│    │
│  │   Dagster   │  │   Polaris   │  │    Cube     │  │    OTLP     │    │
│  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │  │  ┌───────┐  │    │
│  │  │Websvr │  │  │  │Server │  │  │  │Server │  │  │  │Collect│  │    │
│  │  │Daemon │  │  │  │       │  │  │  │       │  │  │  │       │  │    │
│  │  └───┬───┘  │  │  └───┬───┘  │  │  └───┬───┘  │  │  └───┬───┘  │    │
│  │      │      │  │      │      │  │      │      │  │      │      │    │
│  │  ┌───▼───┐  │  │  ┌───▼───┐  │  │  ┌───▼───┐  │  │      │      │    │
│  │  │  PG   │  │  │  │  PG   │  │  │  │ Redis │  │  │      │      │    │
│  │  └───────┘  │  │  └───────┘  │  │  └───────┘  │  │      │      │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────│──────┘    │
│                                                             │           │
│  ┌──────────────────────────────────────────────────────────│───────┐  │
│  │  STORAGE                                                 │        │  │
│  │  ┌─────────────┐  ┌─────────────┐                       │        │  │
│  │  │   MinIO     │  │   OCI Reg   │                 ┌─────▼─────┐  │  │
│  │  │ (objects)   │  │ (artifacts) │                 │Prometheus │  │  │
│  │  └─────────────┘  └─────────────┘                 │  Grafana  │  │  │
│  │                                                    └───────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Startup Order

Platform services must start in dependency order:

```yaml
# charts/floe-platform/templates/startup-order.yaml
1. Storage (MinIO, PostgreSQL instances)
   └─ Wait: StatefulSet ready

2. Catalog (Polaris)
   └─ Wait: Deployment ready, healthcheck passes

3. Observability (OTLP Collector, Prometheus)
   └─ Wait: Deployment ready

4. Orchestrator (Dagster webserver, daemon)
   └─ Wait: Deployment ready, code locations loaded

5. Semantic Layer (Cube)
   └─ Wait: Deployment ready, schema loaded
```

## Health Checks

### Service Health (Layer 3)

```yaml
# Kubernetes probes for long-lived services
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

### Job Health (Layer 4)

```yaml
# Jobs don't use probes - they run to completion
# Health is determined by exit code
spec:
  backoffLimit: 0  # Fail fast, let orchestrator handle retries
  ttlSecondsAfterFinished: 3600  # Cleanup after 1 hour
```

## Resource Allocation

### Services (Continuous)

```yaml
# Sized for steady-state operation
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi
```

### Jobs (Burst)

```yaml
# Sized for workload, determined by ComputePlugin
resources:
  requests:
    cpu: 1000m      # Higher for computation
    memory: 2Gi     # Higher for data processing
  limits:
    cpu: 4000m
    memory: 8Gi
```

## References

- [ADR-0016: Platform Enforcement Architecture](0016-platform-enforcement-architecture.md) - Four-layer architecture
- [ADR-0017: K8s Testing Infrastructure](0017-k8s-testing-infrastructure.md) - Testing approach
- [06-deployment-view.md](../../guides/06-deployment-view.md) - Deployment details
