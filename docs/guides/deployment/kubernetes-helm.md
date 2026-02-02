# Kubernetes (Helm)

This document covers Helm-based Kubernetes deployment for floe.

> **Note**: For the latest chart documentation, see:
> - [floe-platform Chart README](../../../charts/floe-platform/README.md)
> - [floe-jobs Chart README](../../../charts/floe-jobs/README.md)

---

## Quick Start

```bash
# From Helm Repository
helm repo add floe https://obsidian-owl.github.io/floe
helm repo update
helm install floe floe/floe-platform --namespace floe-dev --create-namespace

# From OCI Registry (GHCR)
helm install floe oci://ghcr.io/obsidian-owl/charts/floe-platform \
  --namespace floe-dev --create-namespace

# From Local Chart
helm dependency update ./charts/floe-platform
helm install floe ./charts/floe-platform --namespace floe-dev --create-namespace
```

---

## 1. Chart Structure

Charts are organized to support the plugin architecture:

```
floe/
+-- charts/
|   +-- floe-platform/                    # Meta-chart: assembles plugin charts
|   |   +-- Chart.yaml                    # Dependencies on plugin charts
|   |   +-- values.yaml
|   |   +-- templates/
|   |       +-- namespace.yaml
|   |       +-- observability.yaml        # OTLP, Prometheus, Grafana
|   |
|   +-- floe-jobs/                        # Base chart for pipeline jobs
|       +-- Chart.yaml
|       +-- values.yaml
|       +-- templates/
|           +-- job.yaml                  # dbt run job template
|           +-- configmap.yaml
|
+-- plugins/                              # Each plugin includes its own chart
    +-- floe-orchestrator-dagster/
    |   +-- chart/                        # Dagster services
    |       +-- Chart.yaml
    |       +-- templates/
    |           +-- webserver.yaml
    |           +-- daemon.yaml
    |           +-- postgresql.yaml
    |
    +-- floe-catalog-polaris/
    |   +-- chart/                        # Polaris server
    |
    +-- floe-semantic-cube/
        +-- chart/                        # Cube server + Redis
```

**Key Design**: The `floe-platform` meta-chart assembles plugin charts based on `manifest.yaml` selections.

---

## 2. Deployment Architecture

```
+---------------------------------------------------------------------------+
|                         KUBERNETES CLUSTER                                 |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  Namespace: floe                                                     |  |
|  |                                                                      |  |
|  |  +-----------------+   +-----------------+   +-----------------+     |  |
|  |  | dagster-webserver|  |  dagster-daemon |   |  dagster-worker |     |  |
|  |  |   (Deployment)   |   |  (Deployment)   |   |  (Deployment)   |     |  |
|  |  |   replicas: 2    |   |   replicas: 1   |   |   replicas: 3   |     |  |
|  |  +--------+---------+   +--------+--------+   +--------+--------+     |  |
|  |           |                      |                     |              |  |
|  |           +----------------------+---------------------+              |  |
|  |                                  |                                    |  |
|  |                                  v                                    |  |
|  |                    +-------------------------+                        |  |
|  |                    |  PostgreSQL (StatefulSet)|                        |  |
|  |                    |  or external RDS         |                        |  |
|  |                    +-------------------------+                        |  |
|  |                                                                       |  |
|  |  +-----------------+   +-----------------+                            |  |
|  |  |  otel-collector |   |     marquez     |                            |  |
|  |  |   (DaemonSet)   |   |  (Deployment)   |                            |  |
|  |  +-----------------+   +-----------------+                            |  |
|  |                                                                       |  |
|  +---------------------------------------------------------------------+  |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  Ingress                                                             |  |
|  |  +-- dagster.example.com -> dagster-webserver:3000                   |  |
|  |  +-- traces.example.com -> jaeger-query:16686                        |  |
|  |  +-- lineage.example.com -> marquez-web:3000                         |  |
|  +---------------------------------------------------------------------+  |
+---------------------------------------------------------------------------+
```

---

## 3. Installation

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

---

## 4. values.yaml

```yaml
# values.yaml - Generated from manifest.yaml
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

---

## 5. Secrets Management

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

---

## 6. Resource Requirements

| Component | Min CPU | Min Memory | Recommended |
|-----------|---------|------------|-------------|
| dagster-webserver | 500m | 1Gi | 2 replicas |
| dagster-daemon | 250m | 512Mi | 1 replica |
| dagster-worker | 1000m | 2Gi | 3+ replicas |
| postgresql | 500m | 1Gi | External RDS |
| otel-collector | 200m | 256Mi | DaemonSet |
| marquez | 500m | 1Gi | 2 replicas |

---

## Related Documentation

- [floe-platform Chart](../../../charts/floe-platform/README.md) - Platform services chart
- [floe-jobs Chart](../../../charts/floe-jobs/README.md) - Jobs and pipelines chart
- [Production](production.md) - HA, scaling, monitoring
- [Two-Layer Model](two-layer-model.md) - Deployment model overview
- [Local Development](local-development.md) - Development setup
