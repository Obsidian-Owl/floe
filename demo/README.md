# Floe Platform Demo

Quick-start guide for running the Floe alpha demo platform with 3 complete data products.

## Golden Alpha Demo

Customer 360 is the supported alpha demo path. Start with:

- [Customer 360 Golden Demo](../docs/demo/customer-360.md)
- [Customer 360 Validation](../docs/demo/customer-360-validation.md)

## Prerequisites

- **DevPod workspace on Hetzner**: running and reachable with the configured `DEVPOD_WORKSPACE`.
- **Kubeconfig sync**: `make devpod-sync` writes `${DEVPOD_KUBECONFIG}` or
  `${HOME}/.kube/devpod-${DEVPOD_WORKSPACE}.config`.
- **Helm 3.12+**: `brew install helm` (macOS) or [official docs](https://helm.sh/docs/intro/install/)
- **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh` (Python dependency manager)
- **kubectl**: configured to use the DevPod kubeconfig for demo inspection.

## Quick Start

```bash
# 1. Sync the DevPod kubeconfig from the Hetzner workspace
make devpod-sync

# 2. Use the DevPod cluster for kubectl inspection
export DEVPOD_WORKSPACE=${DEVPOD_WORKSPACE:-floe}
export DEVPOD_KUBECONFIG=${DEVPOD_KUBECONFIG:-${HOME}/.kube/devpod-${DEVPOD_WORKSPACE}.config}
export KUBECONFIG=${DEVPOD_KUBECONFIG}

# 3. Start the demo platform and service port-forwards
make demo

# 4. Access the web UIs (after ~3-5 minutes for all pods to be ready)
# - Dagster: http://localhost:3100 (orchestration)
# - Polaris: http://localhost:8181 (data catalog)
# - MinIO: http://localhost:9001 (object browser)
# - Jaeger: http://localhost:16686 (distributed tracing)
# - Marquez: http://localhost:5100 (data lineage)

# 5. View logs in the DevPod-backed cluster
kubectl logs -n floe-dev -f deployment/floe-platform-dagster-webserver

# 6. Stop demo port-forwards
make demo-stop
```

`make demo` deploys the platform services and starts port-forwards. Customer 360 outcome validation is tracked by the alpha release gate and is documented in the validation guide.

## Demo Products (3)

| Product | Location | Description |
|---------|----------|-------------|
| **Customer 360** | `demo/customer-360/` | Consolidated customer master data (staging → intermediate → marts) |
| **Financial Risk** | `demo/financial-risk/` | Risk metrics and portfolio analysis with DuckDB compute |
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
# Compile all demo products
make compile-demo

# Compile one product and generate Dagster definitions
uv run floe platform compile \
  --spec demo/customer-360/floe.yaml \
  --manifest demo/manifest.yaml \
  --output demo/customer-360/compiled_artifacts.json \
  --generate-definitions

# Run unit tests
make test-unit

# Run full CI checks (lint, type, security, test)
make check

# View pod logs in the DevPod-backed cluster
export DEVPOD_WORKSPACE=${DEVPOD_WORKSPACE:-floe}
export DEVPOD_KUBECONFIG=${DEVPOD_KUBECONFIG:-${HOME}/.kube/devpod-${DEVPOD_WORKSPACE}.config}
export KUBECONFIG=${DEVPOD_KUBECONFIG}
kubectl logs -n floe-dev <pod-name>

# Port-forward to access Dagster manually
export DEVPOD_WORKSPACE=${DEVPOD_WORKSPACE:-floe}
export DEVPOD_KUBECONFIG=${DEVPOD_KUBECONFIG:-${HOME}/.kube/devpod-${DEVPOD_WORKSPACE}.config}
export KUBECONFIG=${DEVPOD_KUBECONFIG}
kubectl port-forward -n floe-dev svc/floe-platform-dagster-webserver 3100:3000
```

## Demo Architecture

```
DevPod-backed Kubernetes cluster on Hetzner
├── floe-dev namespace
│   ├── Dagster (orchestration + webserver)
│   ├── Polaris (data catalog REST API)
│   ├── MinIO (S3-compatible storage)
│   ├── PostgreSQL (metadata database)
│   ├── OpenTelemetry Collector
│   ├── Jaeger (distributed tracing)
│   └── Marquez (lineage)
└── Demo Jobs (K8s Jobs)
    ├── Customer 360 (every 10 minutes in demo)
    ├── Financial Risk (every 10 minutes in demo)
    └── IoT Telemetry (every 10 minutes in demo)
```

## Troubleshooting

**Pods not starting?**
```bash
export DEVPOD_WORKSPACE=${DEVPOD_WORKSPACE:-floe}
export DEVPOD_KUBECONFIG=${DEVPOD_KUBECONFIG:-${HOME}/.kube/devpod-${DEVPOD_WORKSPACE}.config}
export KUBECONFIG=${DEVPOD_KUBECONFIG}
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

**Want to stop local demo port-forwards?**
```bash
make demo-stop
```

`make demo-stop` does not uninstall the remote platform or stop the DevPod
workspace. Use the DevPod/Hetzner lifecycle commands from your environment when
you are finished with the remote workspace.

## Local Smoke Testing

Local Kind remains useful for non-alpha smoke testing of Helm and image wiring, but it is not the supported alpha demo path. The alpha demo path is DevPod + Hetzner with `make devpod-sync` and `make demo`.

## Next Steps

- [Data Contracts Guide](../docs/architecture/data-contracts.md)
- [Testing Standards](../TESTING.md)
- [Architecture Overview](../docs/architecture/ARCHITECTURE-SUMMARY.md)
