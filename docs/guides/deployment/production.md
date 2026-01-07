# Production Considerations

This document covers production-ready deployment patterns for floe.

---

## 1. High Availability

```
+---------------------------------------------------------------------------+
|                       HIGH AVAILABILITY SETUP                              |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  Load Balancer                                                       |  |
|  |  +-- health checks: /health                                          |  |
|  +----------------------------------+----------------------------------+  |
|                                     |                                     |
|            +------------------------+------------------------+            |
|            v                        v                        v            |
|     +--------------+         +--------------+         +--------------+    |
|     |  webserver   |         |  webserver   |         |  webserver   |    |
|     |  (zone-a)    |         |  (zone-b)    |         |  (zone-c)    |    |
|     +--------------+         +--------------+         +--------------+    |
|                                     |                                     |
|                                     v                                     |
|                    +-----------------------------+                        |
|                    |  PostgreSQL (Multi-AZ RDS)  |                        |
|                    |  +-- automatic failover     |                        |
|                    +-----------------------------+                        |
+---------------------------------------------------------------------------+
```

---

## 2. Scaling Guidelines

| Workload | Scaling Strategy |
|----------|------------------|
| **Light** (< 100 runs/day) | 1 webserver, 1 daemon, 2 workers |
| **Medium** (100-1000 runs/day) | 2 webservers, 1 daemon, 5 workers |
| **Heavy** (1000+ runs/day) | 3 webservers, 1 daemon, 10+ workers, queue partitioning |

---

## 3. Backup Strategy

```yaml
# CronJob for PostgreSQL backups
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dagster-backup
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: postgres:16
              command:
                - /bin/sh
                - -c
                - |
                  pg_dump -h $PGHOST -U $PGUSER -d dagster | \
                  gzip | \
                  aws s3 cp - s3://backups/dagster/$(date +%Y%m%d-%H%M%S).sql.gz
              envFrom:
                - secretRef:
                    name: dagster-postgresql
```

---

## 4. Monitoring

```yaml
# ServiceMonitor for Prometheus
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: dagster
spec:
  selector:
    matchLabels:
      app: dagster
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

**Key Metrics:**

| Metric | Alert Threshold |
|--------|-----------------|
| `dagster_runs_failed_total` | > 5 in 1 hour |
| `dagster_runs_duration_seconds` | p99 > 3600s |
| `dagster_daemon_heartbeat_age` | > 60s |
| `container_memory_usage_bytes` | > 90% limit |

---

## 5. Pod Disruption Budgets

PDBs ensure service availability during cluster maintenance:

```yaml
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: dagster-webserver-pdb
  namespace: floe
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: dagster
      component: webserver
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: dagster-worker-pdb
  namespace: floe
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: dagster
      component: worker
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: polaris-pdb
  namespace: floe
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: polaris
```

| Component | PDB Setting | Min Replicas | Notes |
|-----------|-------------|--------------|-------|
| dagster-webserver | minAvailable: 1 | 2 | UI availability |
| dagster-daemon | None | 1 | See HA section below |
| dagster-worker | minAvailable: 2 | 3 | Maintains job throughput |
| polaris | minAvailable: 1 | 2 | Catalog availability |
| marquez | minAvailable: 1 | 2 | Lineage availability |

---

## 6. Dagster Daemon High Availability

The Dagster daemon is a single-instance service by design. floe provides configurable daemon modes:

```yaml
# platform-manifest.yaml
orchestrator:
  type: dagster
  daemon:
    mode: single           # single | ha
    restart_timeout: 60s   # Max time to restart after failure
    health_check_interval: 30s
```

### Mode: single (default)

Single daemon instance with fast recovery:

```
+---------------------------------------------------------------+
|  Daemon Pod (single instance)                                  |
|                                                                |
|  +------------------------------------------------------------+|
|  |  dagster-daemon container                                   ||
|  |  * Runs scheduler, sensors, run launcher                    ||
|  |  * Heartbeat written to PostgreSQL every 30s                ||
|  |  * K8s restarts pod on failure (< 60s recovery)             ||
|  +------------------------------------------------------------+|
|                                                                |
|  livenessProbe:                                                |
|    exec: ["dagster", "daemon", "liveness-check"]               |
|    periodSeconds: 30                                           |
|    failureThreshold: 2                                         |
+---------------------------------------------------------------+
```

### Mode: ha (leader election)

Active-passive configuration using K8s lease-based leader election:

```
+---------------------------------------------------------------+
|  Daemon Pods (2 replicas, 1 active)                            |
|                                                                |
|  +-------------------------+   +-------------------------+     |
|  |  dagster-daemon-0       |   |  dagster-daemon-1       |     |
|  |  (LEADER - active)      |   |  (STANDBY - idle)       |     |
|  |  * Holds K8s Lease      |   |  * Watches Lease        |     |
|  |  * Runs all services    |   |  * Ready to take over   |     |
|  +------------+------------+   +-------------------------+     |
|               |                                                |
|               v                                                |
|  +------------------------------------------------------------+|
|  |  K8s Lease: dagster-daemon-leader                          ||
|  |  holderIdentity: dagster-daemon-0                          ||
|  |  leaseDurationSeconds: 15                                  ||
|  |  renewTime: 2026-01-03T10:30:00Z                           ||
|  +------------------------------------------------------------+|
+---------------------------------------------------------------+
```

### Failover Behavior

| Event | Recovery Time | Behavior |
|-------|---------------|----------|
| Pod crash (single) | < 60s | K8s restarts pod, daemon resumes |
| Pod crash (HA) | < 15s | Standby acquires lease, becomes leader |
| Node drain (single) | During drain | Pod evicted, recreated on new node |
| Node drain (HA) | < 15s | Standby on different node takes over |

### Daemon State Persistence

The daemon persists all state to PostgreSQL, allowing recovery without data loss:

| State | Storage | Recovery |
|-------|---------|----------|
| Schedules | PostgreSQL `schedules` table | Automatic on restart |
| Sensors | PostgreSQL `instigators` table | Automatic on restart |
| Run queue | PostgreSQL `runs` table | Resumes queued runs |
| Heartbeat | PostgreSQL `daemon_heartbeats` table | New heartbeat on startup |

### Monitoring

```yaml
# Alert on daemon unavailability
- alert: DagsterDaemonUnavailable
  expr: dagster_daemon_heartbeat_age_seconds > 120
  for: 2m
  labels:
    severity: critical
  annotations:
    summary: "Dagster daemon heartbeat stale"
```

### Recommendation

| Environment | Mode | Rationale |
|-------------|------|-----------|
| Development | single | Simpler, sufficient for dev |
| Staging | single | Test production-like recovery |
| Production (small) | single | Adequate with fast K8s restart |
| Production (critical) | ha | Sub-15s failover requirement |

---

## Related Documentation

- [Kubernetes Helm](kubernetes-helm.md) - Base Helm deployment
- [Data Mesh](data-mesh.md) - Multi-domain deployment
- [09-risks](../09-risks.md) - Risk documentation
