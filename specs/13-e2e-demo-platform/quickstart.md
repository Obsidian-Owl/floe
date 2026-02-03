# Quickstart: E2E Platform Testing & Live Demo

## Prerequisites

- Kind cluster running (`make kind-up`)
- Helm 3.12+
- Python 3.11 with uv

## Run E2E Tests

```bash
# Deploy platform and run all E2E tests
make test-e2e

# Run specific test file
pytest tests/e2e/test_platform_bootstrap.py -v

# Run by user story priority
pytest tests/e2e/ -m "requirement and 'FR-001'" -v
```

## Run Live Demo

```bash
# Full demo: bootstrap + 3 data products + dashboards
make demo

# Demo with larger seed data
FLOE_DEMO_SEED_SCALE=medium make demo

# Single data product only
make demo PRODUCTS=customer-360
```

## Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| Dagster UI | http://localhost:3000 | Pipeline management, asset lineage |
| Polaris | http://localhost:8181 | Catalog management |
| Marquez | http://localhost:5001 | OpenLineage visualization |
| Jaeger | http://localhost:16686 | Distributed traces |
| Grafana | http://localhost:3001 | Metrics dashboards |
| MinIO Console | http://localhost:9001 | Object storage |

## Cleanup

```bash
# Stop demo
make demo-stop

# Destroy Kind cluster
make kind-down
```
