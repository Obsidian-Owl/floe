# 06. Deployment View

This document describes deployment architecture for floe, covering the separation between platform services (long-lived) and pipeline jobs (ephemeral).

---

## 1. Two-Layer Deployment Model

floe deployment separates two concerns:

| Layer | Owner | K8s Resource | Lifecycle |
|-------|-------|--------------|-----------|
| **Platform Services** | Platform Team | Deployment, StatefulSet | Long-lived, upgraded |
| **Pipeline Jobs** | Data Team (execution) | Job | Run-to-completion |

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PLATFORM SERVICES (Layer 3 - Long-lived)                                    │
│  Deployed by: floe platform deploy                                          │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Orchestrator (Dagster):     Catalog (Polaris):    Semantic (Cube): │    │
│  │  • webserver (Deployment)    • server (Deployment) • server (Deploy) │    │
│  │  • daemon (Deployment)       • PostgreSQL          • Redis           │    │
│  │  • PostgreSQL (StatefulSet)                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Observability:              Storage:                               │    │
│  │  • OTLP Collector            • MinIO / S3 / GCS / ADLS              │    │
│  │  • Prometheus (optional)     • OCI Registry (platform artifacts)    │    │
│  │  • Grafana (optional)                                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │ Triggers
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PIPELINE JOBS (Layer 4 - Ephemeral)                                         │
│  Triggered by: Orchestrator on schedule/sensor                              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  dbt run pods (K8s Job)      Quality check pods    Ingestion pods   │    │
│  │  • Run-to-completion         (K8s Job)             (K8s Job)        │    │
│  │  • Inherit platform config   • Run-to-completion   • dlt pipelines  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Deployment Options Overview

| Option | Use Case | Complexity |
|--------|----------|------------|
| **Local (uv)** | Development, single user | Low |
| **Docker Compose** | Development, evaluation | Low |
| **Kubernetes (Helm)** | Production, team use | Medium |

---

## 3. Local Development (uv)

### 3.1 Installation

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

### 3.2 Project Setup

```bash
# Initialize project
floe init my-project
cd my-project

# Validate configuration
floe validate

# Run pipeline (uses configured compute target)
floe run --env dev
```

### 3.3 Local Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL MACHINE                                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  floe-cli process                                        │    │
│  │                                                          │    │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐               │    │
│  │  │ Dagster │──►│   dbt   │──►│ DuckDB  │               │    │
│  │  │ (in-    │   │  (in-   │   │  (in-   │               │    │
│  │  │ process)│   │ process)│   │ process)│               │    │
│  │  └─────────┘   └─────────┘   └─────────┘               │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────┐   ┌─────────────────┐                      │
│  │ ./warehouse/    │   │ .floe/          │                      │
│  │ └─ data.duckdb  │   │ └─ artifacts.json│                      │
│  └─────────────────┘   └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

### 3.4 Limitations

- No persistent Dagster UI (run-and-exit)
- No built-in observability backends
- Single-user, single-machine only

---

## 4. Docker Compose

### 4.1 Quick Start

```bash
# Start full development environment
floe dev

# Or manually with Docker Compose
docker compose up -d
```

### 4.2 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOCKER HOST                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  docker-compose network: floe                                        │    │
│  │                                                                      │    │
│  │  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐         │    │
│  │  │   dagster     │   │   postgres    │   │   marquez     │         │    │
│  │  │   :3000       │──►│   :5432       │◄──│   :5000/:5001 │         │    │
│  │  └───────────────┘   └───────────────┘   └───────────────┘         │    │
│  │         │                                        ▲                  │    │
│  │         │                                        │                  │    │
│  │         ▼                                        │                  │    │
│  │  ┌───────────────┐   ┌───────────────┐          │                  │    │
│  │  │ otel-collector│──►│    jaeger     │──────────┘                  │    │
│  │  │   :4317       │   │   :16686      │                             │    │
│  │  └───────────────┘   └───────────────┘                             │    │
│  │                                                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  volumes                                                             │    │
│  │  ├── postgres_data (persistent)                                     │    │
│  │  ├── ./models (bind mount, live reload)                             │    │
│  │  └── ./.floe/artifacts.json (bind mount)                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 docker-compose.yml

```yaml
version: "3.8"

services:
  # PostgreSQL - Dagster metadata + Marquez storage
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: floe
      POSTGRES_PASSWORD: floe
      POSTGRES_DB: dagster
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "floe"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - floe

  # Dagster - Orchestration
  dagster:
    image: ghcr.io/floe/dagster:latest
    ports:
      - "3000:3000"
    environment:
      DAGSTER_HOME: /opt/dagster/dagster_home
      DAGSTER_POSTGRES_HOST: postgres
      DAGSTER_POSTGRES_USER: floe
      DAGSTER_POSTGRES_PASSWORD: floe
      DAGSTER_POSTGRES_DB: dagster
      FLOE_ARTIFACTS_PATH: /app/artifacts.json
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
      OTEL_SERVICE_NAME: floe-dagster
      OPENLINEAGE_URL: http://marquez-api:5000
      OPENLINEAGE_NAMESPACE: floe
    volumes:
      - ./.floe/artifacts.json:/app/artifacts.json:ro
      - ./models:/app/models:ro
      - ./seeds:/app/seeds:ro
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - floe

  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config", "/etc/otel/config.yaml"]
    volumes:
      - ./otel-config.yaml:/etc/otel/config.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Prometheus metrics
    networks:
      - floe

  # Jaeger - Distributed Tracing
  jaeger:
    image: jaegertracing/all-in-one:1.53
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    ports:
      - "16686:16686"  # UI
      - "14250:14250"  # gRPC
    networks:
      - floe

  # Marquez API - Data Lineage
  marquez-api:
    image: marquezproject/marquez:0.47.0
    environment:
      MARQUEZ_PORT: 5000
      MARQUEZ_ADMIN_PORT: 5001
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: marquez
      POSTGRES_USER: floe
      POSTGRES_PASSWORD: floe
    ports:
      - "5000:5000"   # API
      - "5001:5001"   # Admin
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - floe

  # Marquez Web - Lineage UI
  marquez-web:
    image: marquezproject/marquez-web:0.47.0
    environment:
      MARQUEZ_HOST: marquez-api
      MARQUEZ_PORT: 5000
    ports:
      - "3001:3000"
    depends_on:
      - marquez-api
    networks:
      - floe

networks:
  floe:
    driver: bridge

volumes:
  postgres_data:
```

### 4.4 OTel Collector Configuration

```yaml
# otel-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  logging:
    verbosity: detailed

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/jaeger, logging]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging]
```

### 4.5 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Dagster UI | http://localhost:3000 | Asset management, runs |
| Jaeger UI | http://localhost:16686 | Distributed tracing |
| Marquez Web | http://localhost:3001 | Data lineage |
| Marquez API | http://localhost:5000 | Lineage API |

---

## 5. Kubernetes (Helm)

### 5.1 Chart Structure

Charts are organized to support the plugin architecture:

```
floe/
├── charts/
│   ├── floe-platform/                    # Meta-chart: assembles plugin charts
│   │   ├── Chart.yaml                    # Dependencies on plugin charts
│   │   ├── values.yaml
│   │   └── templates/
│   │       ├── namespace.yaml
│   │       └── observability.yaml        # OTLP, Prometheus, Grafana
│   │
│   └── floe-jobs/                        # Base chart for pipeline jobs
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── job.yaml                  # dbt run job template
│           └── configmap.yaml
│
└── plugins/                              # Each plugin includes its own chart
    ├── floe-orchestrator-dagster/
    │   └── chart/                        # Dagster services
    │       ├── Chart.yaml
    │       └── templates/
    │           ├── webserver.yaml
    │           ├── daemon.yaml
    │           └── postgresql.yaml
    │
    ├── floe-catalog-polaris/
    │   └── chart/                        # Polaris server
    │
    └── floe-semantic-cube/
        └── chart/                        # Cube server + Redis
```

**Key Design**: The `floe-platform` meta-chart assembles plugin charts based on `platform-manifest.yaml` selections.

### 5.2 Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                                   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Namespace: floe                                               │  │
│  │                                                                        │  │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐     │  │
│  │  │ dagster-webserver│  │  dagster-daemon │   │  dagster-worker │     │  │
│  │  │   (Deployment)   │   │  (Deployment)   │   │  (Deployment)   │     │  │
│  │  │   replicas: 2    │   │   replicas: 1   │   │   replicas: 3   │     │  │
│  │  └────────┬─────────┘   └────────┬────────┘   └────────┬────────┘     │  │
│  │           │                      │                     │              │  │
│  │           └──────────────────────┼─────────────────────┘              │  │
│  │                                  │                                    │  │
│  │                                  ▼                                    │  │
│  │                    ┌─────────────────────────┐                        │  │
│  │                    │  PostgreSQL (StatefulSet)│                        │  │
│  │                    │  or external RDS         │                        │  │
│  │                    └─────────────────────────┘                        │  │
│  │                                                                        │  │
│  │  ┌─────────────────┐   ┌─────────────────┐                           │  │
│  │  │  otel-collector │   │     marquez     │                           │  │
│  │  │   (DaemonSet)   │   │  (Deployment)   │                           │  │
│  │  └─────────────────┘   └─────────────────┘                           │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Ingress                                                               │  │
│  │  ├── dagster.example.com → dagster-webserver:3000                     │  │
│  │  ├── traces.example.com → jaeger-query:16686                          │  │
│  │  └── lineage.example.com → marquez-web:3000                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Installation

```bash
# Add Helm repository
helm repo add floe https://charts.floe.dev
helm repo update

# Install with default values
helm install floe floe/floe \
  --namespace floe \
  --create-namespace

# Install with custom values
helm install floe floe/floe \
  --namespace floe \
  --create-namespace \
  --values values-production.yaml
```

### 5.4 values.yaml

```yaml
# values.yaml - Generated from platform-manifest.yaml
global:
  # Compute configuration (inherited from platform)
  compute:
    type: snowflake
    secretRef: snowflake-credentials

  # Observability endpoints
  observability:
    otlpEndpoint: http://otel-collector:4317
    lineageEndpoint: http://marquez:5000

# Dagster configuration
dagster:
  enabled: true
  webserver:
    replicas: 2
    resources:
      requests:
        cpu: 500m
        memory: 1Gi
      limits:
        cpu: 2000m
        memory: 4Gi

  daemon:
    enabled: true
    resources:
      requests:
        cpu: 250m
        memory: 512Mi

  worker:
    replicas: 3
    resources:
      requests:
        cpu: 1000m
        memory: 2Gi

  # External database (recommended for production)
  postgresql:
    enabled: false
  externalPostgresql:
    host: my-rds-instance.xxx.us-east-1.rds.amazonaws.com
    port: 5432
    database: dagster
    existingSecret: dagster-postgresql
    secretKeys:
      username: username
      password: password

# OTel Collector
otel-collector:
  enabled: true
  mode: daemonset
  config:
    exporters:
      otlp/grafana:
        endpoint: tempo-us-east-1.grafana.net:443
        headers:
          authorization: "Basic ${GRAFANA_API_KEY}"

# Marquez (optional - can use external)
marquez:
  enabled: true
  api:
    replicas: 2
  web:
    enabled: true

# Ingress
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: dagster.example.com
      paths:
        - path: /
          pathType: Prefix
          backend:
            service:
              name: dagster-webserver
              port: 3000
  tls:
    - secretName: dagster-tls
      hosts:
        - dagster.example.com
```

### 5.5 Secrets Management

```yaml
# secrets.yaml (apply separately, store in Vault/SOPS)
apiVersion: v1
kind: Secret
metadata:
  name: snowflake-credentials
  namespace: floe
type: Opaque
stringData:
  SNOWFLAKE_ACCOUNT: "xxx.us-east-1"
  SNOWFLAKE_USER: "floe_user"
  SNOWFLAKE_PASSWORD: "secret"
  SNOWFLAKE_ROLE: "floe_role"
  SNOWFLAKE_WAREHOUSE: "floe_wh"
  SNOWFLAKE_DATABASE: "floe_db"
---
apiVersion: v1
kind: Secret
metadata:
  name: dagster-postgresql
  namespace: floe
type: Opaque
stringData:
  username: "dagster"
  password: "secret"
```

### 5.6 Resource Requirements

| Component | Min CPU | Min Memory | Recommended |
|-----------|---------|------------|-------------|
| dagster-webserver | 500m | 1Gi | 2 replicas |
| dagster-daemon | 250m | 512Mi | 1 replica |
| dagster-worker | 1000m | 2Gi | 3+ replicas |
| postgresql | 500m | 1Gi | External RDS |
| otel-collector | 200m | 256Mi | DaemonSet |
| marquez | 500m | 1Gi | 2 replicas |

---

## 6. Production Considerations

### 6.1 High Availability

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       HIGH AVAILABILITY SETUP                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Load Balancer                                                       │    │
│  │  └── health checks: /health                                         │    │
│  └────────────────────────────────┬────────────────────────────────────┘    │
│                                   │                                         │
│            ┌──────────────────────┼──────────────────────┐                 │
│            ▼                      ▼                      ▼                 │
│     ┌──────────────┐       ┌──────────────┐       ┌──────────────┐        │
│     │  webserver   │       │  webserver   │       │  webserver   │        │
│     │  (zone-a)    │       │  (zone-b)    │       │  (zone-c)    │        │
│     └──────────────┘       └──────────────┘       └──────────────┘        │
│                                   │                                         │
│                                   ▼                                         │
│                    ┌─────────────────────────────┐                          │
│                    │  PostgreSQL (Multi-AZ RDS)  │                          │
│                    │  └── automatic failover      │                          │
│                    └─────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Scaling Guidelines

| Workload | Scaling Strategy |
|----------|------------------|
| **Light** (< 100 runs/day) | 1 webserver, 1 daemon, 2 workers |
| **Medium** (100-1000 runs/day) | 2 webservers, 1 daemon, 5 workers |
| **Heavy** (1000+ runs/day) | 3 webservers, 1 daemon, 10+ workers, queue partitioning |

### 6.3 Backup Strategy

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

### 6.4 Monitoring

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

### 6.5 Pod Disruption Budgets

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

### 6.6 Dagster Daemon High Availability

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

**Mode: single (default)**

Single daemon instance with fast recovery:

```
┌─────────────────────────────────────────────────────────────────┐
│  Daemon Pod (single instance)                                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  dagster-daemon container                                   │ │
│  │  • Runs scheduler, sensors, run launcher                   │ │
│  │  • Heartbeat written to PostgreSQL every 30s               │ │
│  │  • K8s restarts pod on failure (< 60s recovery)            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  livenessProbe:                                                  │
│    exec: ["dagster", "daemon", "liveness-check"]                │
│    periodSeconds: 30                                            │
│    failureThreshold: 2                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Mode: ha (leader election)**

Active-passive configuration using K8s lease-based leader election:

```
┌─────────────────────────────────────────────────────────────────┐
│  Daemon Pods (2 replicas, 1 active)                              │
│                                                                  │
│  ┌─────────────────────────┐   ┌─────────────────────────┐      │
│  │  dagster-daemon-0       │   │  dagster-daemon-1       │      │
│  │  (LEADER - active)      │   │  (STANDBY - idle)       │      │
│  │  • Holds K8s Lease      │   │  • Watches Lease        │      │
│  │  • Runs all services    │   │  • Ready to take over   │      │
│  └────────────┬────────────┘   └─────────────────────────┘      │
│               │                                                  │
│               ▼                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  K8s Lease: dagster-daemon-leader                          │ │
│  │  holderIdentity: dagster-daemon-0                          │ │
│  │  leaseDurationSeconds: 15                                  │ │
│  │  renewTime: 2026-01-03T10:30:00Z                          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Failover Behavior:**

| Event | Recovery Time | Behavior |
|-------|---------------|----------|
| Pod crash (single) | < 60s | K8s restarts pod, daemon resumes |
| Pod crash (HA) | < 15s | Standby acquires lease, becomes leader |
| Node drain (single) | During drain | Pod evicted, recreated on new node |
| Node drain (HA) | < 15s | Standby on different node takes over |

**Daemon State Persistence:**

The daemon persists all state to PostgreSQL, allowing recovery without data loss:

| State | Storage | Recovery |
|-------|---------|----------|
| Schedules | PostgreSQL `schedules` table | Automatic on restart |
| Sensors | PostgreSQL `instigators` table | Automatic on restart |
| Run queue | PostgreSQL `runs` table | Resumes queued runs |
| Heartbeat | PostgreSQL `daemon_heartbeats` table | New heartbeat on startup |

**Monitoring:**

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

**Recommendation:**

| Environment | Mode | Rationale |
|-------------|------|-----------|
| Development | single | Simpler, sufficient for dev |
| Staging | single | Test production-like recovery |
| Production (small) | single | Adequate with fast K8s restart |
| Production (critical) | ha | Sub-15s failover requirement |

---

## 7. Data Mesh Deployment Topology

For federated Data Mesh deployments, the architecture separates shared platform services from domain-specific workloads.

### 7.1 Namespace Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Namespace: floe-platform (Shared Services)                          │    │
│  │  Owner: Central Platform Team                                        │    │
│  │                                                                      │    │
│  │  • Polaris Catalog (shared across all domains)                      │    │
│  │  • OTLP Collector (federated traces/metrics/lineage)               │    │
│  │  • Marquez (cross-domain lineage)                                   │    │
│  │  • MinIO / Object Storage (shared Iceberg warehouse)                │    │
│  └──────────────────────────────────────┬───────────────────────────────┘    │
│                                         │                                    │
│           ┌─────────────────────────────┼─────────────────────────────┐      │
│           ▼                             ▼                             ▼      │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐│
│  │ Namespace:          │   │ Namespace:          │   │ Namespace:          ││
│  │ floe-sales-domain   │   │ floe-marketing-domain│  │ floe-finance-domain ││
│  │                     │   │                     │   │                     ││
│  │ Orchestrator:       │   │ Orchestrator:       │   │ Orchestrator:       ││
│  │ • Dagster webserver │   │ • Airflow (domain   │   │ • Dagster webserver ││
│  │ • Dagster daemon    │   │   choice)           │   │ • Dagster daemon    ││
│  │ • PostgreSQL        │   │ • PostgreSQL        │   │ • PostgreSQL        ││
│  │                     │   │                     │   │                     ││
│  │ Data Products:      │   │ Data Products:      │   │ Data Products:      ││
│  │ • customer-360      │   │ • campaign-perf     │   │ • revenue-metrics   ││
│  │ • order-analytics   │   │ • attribution       │   │ • cost-center       ││
│  └─────────────────────┘   └─────────────────────┘   └─────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Shared vs Domain-Specific Services

| Service | Deployment | Rationale |
|---------|------------|-----------|
| **Catalog (Polaris)** | Shared | Single source of truth for all domains |
| **Object Storage** | Shared | Unified Iceberg warehouse |
| **Lineage (Marquez)** | Shared | Cross-domain lineage visibility |
| **OTLP Collector** | Shared | Federated observability |
| **Orchestrator** | Per-domain | Domain autonomy in tooling |
| **Semantic Layer** | Per-domain | Domain-specific business logic |
| **PostgreSQL (orchestrator)** | Per-domain | Isolation of execution state |

### 7.3 Cross-Domain Service Discovery

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

### 7.4 Multi-Cluster Data Mesh

For large enterprises, domains may run in separate clusters:

```
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│  SHARED SERVICES    │      │  SALES CLUSTER      │      │  MARKETING CLUSTER  │
│  CLUSTER            │      │  (Region: us-east)  │      │  (Region: eu-west)  │
│                     │      │                     │      │                     │
│  • Polaris Catalog  │◄────►│  • Dagster          │◄────►│  • Airflow          │
│  • Marquez Lineage  │      │  • Sales Products   │      │  • Marketing Prods  │
│  • Central OTLP     │      │  • Local OTLP       │      │  • Local OTLP       │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
         ▲                            │                            │
         │                            │                            │
         └────────────────────────────┴────────────────────────────┘
                          Cross-cluster networking
                          (Service Mesh / Ingress)
```

### 7.5 Data Mesh Helm Deployment

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

See [ADR-0021: Data Architecture Patterns](../architecture/adr/0021-data-architecture-patterns.md) for full Data Mesh documentation.

---

## 8. Deployment Comparison

| Aspect | Local | Docker Compose | Kubernetes | Data Mesh |
|--------|-------|----------------|------------|-----------|
| **Setup time** | 5 min | 10 min | 30 min | 1+ hour |
| **Scalability** | Single user | Single host | Multi-node | Multi-cluster |
| **HA** | No | No | Yes | Yes |
| **Persistence** | File-based | Docker volumes | PVCs + RDS | PVCs + RDS |
| **Observability** | Minimal | Full stack | Full stack | Federated |
| **Cost** | Free | Free | Cloud costs | Higher cloud costs |
| **Use case** | Development | Evaluation | Production | Enterprise |
| **Domain isolation** | N/A | N/A | Namespaces | Namespaces or clusters |

