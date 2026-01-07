# Local Development

This document covers local development options for floe: using uv directly and Docker Compose.

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

## 2. Docker Compose

### 2.1 Quick Start

```bash
# Start full development environment
floe dev

# Or manually with Docker Compose
docker compose up -d
```

### 2.2 Architecture

```
+---------------------------------------------------------------------------+
|                           DOCKER HOST                                      |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  docker-compose network: floe                                        |  |
|  |                                                                      |  |
|  |  +---------------+   +---------------+   +---------------+           |  |
|  |  |   dagster     |   |   postgres    |   |   marquez     |           |  |
|  |  |   :3000       |-->|   :5432       |<--|   :5000/:5001 |           |  |
|  |  +---------------+   +---------------+   +---------------+           |  |
|  |         |                                        ^                   |  |
|  |         |                                        |                   |  |
|  |         v                                        |                   |  |
|  |  +---------------+   +---------------+           |                   |  |
|  |  | otel-collector|-->|    jaeger     |-----------+                   |  |
|  |  |   :4317       |   |   :16686      |                               |  |
|  |  +---------------+   +---------------+                               |  |
|  |                                                                      |  |
|  +---------------------------------------------------------------------+  |
|                                                                            |
|  +---------------------------------------------------------------------+  |
|  |  volumes                                                             |  |
|  |  +-- postgres_data (persistent)                                      |  |
|  |  +-- ./models (bind mount, live reload)                              |  |
|  |  +-- ./.floe/artifacts.json (bind mount)                             |  |
|  +---------------------------------------------------------------------+  |
+---------------------------------------------------------------------------+
```

### 2.3 docker-compose.yml

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

### 2.4 OTel Collector Configuration

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

### 2.5 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Dagster UI | http://localhost:3000 | Asset management, runs |
| Jaeger UI | http://localhost:16686 | Distributed tracing |
| Marquez Web | http://localhost:3001 | Data lineage |
| Marquez API | http://localhost:5000 | Lineage API |

---

## Related Documentation

- [Kubernetes Helm](kubernetes-helm.md) - Production deployment
- [Two-Layer Model](two-layer-model.md) - Deployment model overview
