# Floe Platform Demo

Quick-start guide for running the Floe E2E demo platform with 3 complete data products.

## Golden Alpha Demo

Customer 360 is the supported alpha demo path. Start with:

- [Customer 360 Golden Demo](../docs/demo/customer-360.md)
- [Customer 360 Validation](../docs/demo/customer-360-validation.md)

## Prerequisites

- **Kind cluster**: `kind create cluster --config kind-config.yaml`
- **Helm 3.12+**: `brew install helm` (macOS) or [official docs](https://helm.sh/docs/intro/install/)
- **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Python dependency manager)

## Quick Start

```bash
# 1. Start the demo platform (all services + 3 data products)
make demo

# 2. Access the web UIs (after ~3-5 minutes for all pods to be ready)
# - Dagster: http://localhost:3100 (orchestration)
# - Polaris: http://localhost:8181 (data catalog)
# - MinIO: http://localhost:9001 (object browser)
# - Jaeger: http://localhost:16686 (distributed tracing)
# - Marquez: http://localhost:5100 (data lineage)

# 3. View logs
kubectl logs -n floe-dev -f deployment/floe-platform-dagster-webserver

# 4. Stop demo port-forwards
make demo-stop
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
| **Dagster** | http://localhost:3100 | View assets, triggers, run history |
| **Polaris** | http://localhost:8181 | Explore catalog namespaces + tables |
| **MinIO** | http://localhost:9001 | Inspect demo object storage |
| **Jaeger** | http://localhost:16686 | Trace visualization and span inspection |
| **Marquez** | http://localhost:5100 | Data lineage graph (beta) |

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

# Port-forward to access Dagster manually
kubectl port-forward -n floe-dev svc/floe-platform-dagster-webserver 3100:3000
```

## Demo Architecture

```
Kind Cluster
├── floe-dev namespace
│   ├── Dagster (orchestration + webserver)
│   ├── Polaris (data catalog REST API)
│   ├── MinIO (S3-compatible storage)
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
kubectl get pods -n floe-dev
kubectl describe pod -n floe-dev <pod-name>
```

**Port conflicts?**
```bash
# Check what's using port 3100
lsof -i :3100
# Kill if needed
kill -9 $(lsof -t -i :3100)
```

**Want to clean up completely?**
```bash
make demo-stop
kind delete cluster
```

## Next Steps

- [Data Contracts Guide](../docs/architecture/data-contracts.md)
- [Testing Standards](../TESTING.md)
- [Architecture Overview](../docs/architecture/ARCHITECTURE-SUMMARY.md)
