# Quickstart: Epic 3D Contract Monitoring

**Branch**: `3d-contract-monitoring` | **Date**: 2026-02-08

## Prerequisites

- Python 3.11+
- PostgreSQL (local or via Docker)
- Kind cluster (for integration tests)
- `uv` package manager

## Setup

```bash
# 1. Switch to feature branch
git checkout 3d-contract-monitoring

# 2. Install floe-core with monitoring dependencies
cd packages/floe-core
uv pip install -e ".[dev]"

# 3. Install alert channel plugins (for Phase 4+)
cd ../../plugins/floe-alert-webhook && uv pip install -e ".[dev]"
cd ../floe-alert-slack && uv pip install -e ".[dev]"
cd ../floe-alert-email && uv pip install -e ".[dev]"
cd ../floe-alert-alertmanager && uv pip install -e ".[dev]"
```

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | >=2.0 | Data models (frozen, extra=forbid) |
| opentelemetry-api | >=1.39.0 | OTel metrics via MetricRecorder |
| opentelemetry-sdk | >=1.20.0 | OTel SDK for testing |
| structlog | >=24.0 | Structured logging |
| httpx | >=0.25.0 | Async HTTP (webhooks, Slack, Alertmanager) |
| sqlalchemy[asyncio] | >=2.0 | Async PostgreSQL ORM |
| asyncpg | >=0.29.0 | PostgreSQL async driver |
| click | >=8.0 | CLI commands |

## Running Tests

```bash
# Unit tests (no infrastructure needed)
make test-unit

# Integration tests (requires Kind cluster + PostgreSQL)
make test

# Specific monitoring tests
uv run pytest packages/floe-core/tests/unit/contracts/monitoring/ -v

# Contract tests
uv run pytest tests/contract/test_alert_channel_plugin_contract.py -v
```

## Development Workflow

### Phase 1: Core Models
Start here. No external dependencies needed.

```bash
# Work on models
packages/floe-core/src/floe_core/contracts/monitoring/violations.py
packages/floe-core/src/floe_core/contracts/monitoring/config.py
packages/floe-core/src/floe_core/contracts/monitoring/sla.py
packages/floe-core/src/floe_core/plugins/alert_channel.py

# Run unit tests
uv run pytest packages/floe-core/tests/unit/contracts/monitoring/ -v
```

### Phase 2: Check Implementations
Requires Phase 1 models.

```bash
# Work on checks
packages/floe-core/src/floe_core/contracts/monitoring/checks/

# Run check tests
uv run pytest packages/floe-core/tests/unit/contracts/monitoring/test_freshness.py -v
```

### Phase 3: Monitoring Engine
Requires PostgreSQL for persistence tests.

```bash
# Start PostgreSQL locally
docker run -d --name floe-pg -p 5432:5432 \
  -e POSTGRES_DB=floe_monitoring \
  -e POSTGRES_USER=floe \
  -e POSTGRES_PASSWORD=floe \
  postgres:16

# Run integration tests
uv run pytest packages/floe-core/tests/integration/contracts/monitoring/ -v
```

### Phase 4: Alert Channels
Each plugin is independent.

```bash
# Test individual channel
uv run pytest plugins/floe-alert-webhook/tests/ -v
uv run pytest plugins/floe-alert-slack/tests/ -v
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `spec.md` | Feature specification (47 FRs) |
| `plan.md` | Implementation plan (7 phases) |
| `data-model.md` | Entity models, DB schema, facets |
| `research.md` | Existing foundation, technology decisions |
| `contracts/contract-violation-facet.json` | OpenLineage facet JSON schema |

## Existing Code to Reuse

| Component | Location |
|-----------|----------|
| DataContract models | `floe_core.schemas.data_contract` |
| ContractValidator | `floe_core.enforcement.validators` |
| PluginMetadata ABC | `floe_core.plugin_metadata` |
| PluginRegistry | `floe_core.plugin_registry` |
| MetricRecorder | `floe_core.telemetry.metrics` |
| LineageBackendPlugin | `floe_core.plugins.lineage` |
| CLI framework | `floe_core.cli` |
