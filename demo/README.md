# Floe Platform Demo

Quick-start guide for running the Floe E2E demo platform with 3 complete data products.

## Prerequisites

- **Kind cluster**: `kind create cluster --config kind-config.yaml`
- **Helm 3.12+**: `brew install helm` (macOS) or [official docs](https://helm.sh/docs/intro/install/)
- **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Python dependency manager)

## Quick Start

```bash
# 1. Start the demo platform (all services + 3 data products)
make demo

# 2. Access the web UIs (after ~3-5 minutes for all pods to be ready)
# - Dagster: http://localhost:3000 (orchestration)
# - Polaris: http://localhost:8181 (data catalog)
# - Grafana: http://localhost:3001 (observability)
# - Jaeger: http://localhost:16686 (distributed tracing)
# - Marquez: http://localhost:5000 (data lineage)

# 3. View logs
kubectl logs -f deployment/dagster-webserver

# 4. Stop the platform
make demo-down
```

## Demo Products (3)

| Product | Location | Description |
|---------|----------|-------------|
| **Customer 360** | `demo/customer-360/` | Consolidated customer master data (staging → intermediate → marts) |
| **Financial Risk** | `demo/financial-risk/` | Risk metrics and portfolio analysis with Spark compute |
| **IoT Telemetry** | `demo/iot-telemetry/` | Real-time sensor data aggregation and anomaly detection |

Each product demonstrates:
- **floe.yaml** - Data product specification (pipelines, schedules)
- **dbt models** - SQL transformations (staging, intermediate, marts)
- **Data contracts** - ODCS v3.1 schema + SLAs (auto-discovered from `datacontract.yaml`)
- **Orchestration** - Dagster asset dependencies and scheduling
- **Observability** - OpenTelemetry traces, OpenLineage lineage, structured logging

## Web UI Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| **Dagster** | http://localhost:3000 | View assets, triggers, run history |
| **Polaris** | http://localhost:8181 | Explore catalog namespaces + tables |
| **Grafana** | http://localhost:3001 | Metrics dashboards (CPU, memory, duration) |
| **Jaeger** | http://localhost:16686 | Trace visualization and span inspection |
| **Marquez** | http://localhost:5000 | Data lineage graph (beta) |

## Common Commands

```bash
# Validate demo specifications
make validate-demo

# Compile one product
floe compile demo/customer-360/

# Run unit tests
make test-unit

# Run full CI checks (lint, type, security, test)
make check

# View pod logs
kubectl logs -n floe <pod-name>

# Port-forward to access services
kubectl port-forward -n floe svc/dagster-webserver 3000:80
```

## Demo Architecture

```
Kind Cluster
├── floe namespace
│   ├── Dagster (orchestration + webserver)
│   ├── Polaris (data catalog REST API)
│   ├── LocalStack (S3-compatible storage)
│   ├── PostgreSQL (metadata database)
│   └── Prometheus (metrics scraping)
├── Monitoring
│   ├── Grafana (dashboards)
│   ├── Jaeger (distributed tracing)
│   └── Marquez (lineage)
└── Demo Jobs (K8s Jobs)
    ├── Customer 360 (daily @ 6 AM)
    ├── Financial Risk (weekly)
    └── IoT Telemetry (hourly)
```

## Troubleshooting

**Pods not starting?**
```bash
kubectl get pods -n floe
kubectl describe pod -n floe <pod-name>
```

**Port conflicts?**
```bash
# Check what's using port 3000
lsof -i :3000
# Kill if needed
kill -9 $(lsof -t -i :3000)
```

**Want to clean up completely?**
```bash
make demo-down
kind delete cluster
```

## Next Steps

- [Data Contracts Guide](../docs/architecture/data-contracts.md)
- [Testing Standards](../TESTING.md)
- [Architecture Overview](../docs/architecture/ARCHITECTURE-SUMMARY.md)
