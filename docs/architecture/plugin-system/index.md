# Plugin Architecture

This document describes the plugin system that enables floe's flexibility.

## Overview

floe uses a plugin architecture for all configurable components:

| Plugin Type | Default | Purpose | ADR |
|-------------|---------|---------|-----|
| **Compute** | DuckDB | Where dbt transforms execute | ADR-0010 |
| **Orchestrator** | Dagster | Job scheduling and execution | ADR-0033 |
| **Catalog** | Polaris | Iceberg table catalog | ADR-0008 |
| **Storage** | MinIO (local), S3 (prod) | Object storage for Iceberg data | ADR-0036 |
| **TelemetryBackend** | Jaeger (local), Datadog (prod) | OTLP telemetry backend (traces, metrics, logs) | ADR-0035 |
| **LineageBackend** | Marquez (local), Atlan (prod) | OpenLineage backend (data lineage) | ADR-0035 |
| **DBT** | dbt-core (local) | dbt compilation environment (local/fusion/cloud) | ADR-0043 |
| **Semantic Layer** | Cube | Business intelligence API | ADR-0001 |
| **Ingestion** | dlt | Data loading from sources | ADR-0020 |
| **Secrets** | K8s Secrets | Credential management | ADR-0023/0031 |
| **Identity** | Keycloak | Authentication provider | ADR-0024 |

**Total:** 11 plugin types (per ADR-0037 Composability Principle)

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins. Policy enforcement tooling is provided via DBTPlugin, and rules are configured via platform-manifest.yaml. Data contracts use ODCS v3 as an enforced standard.

> **Canonical Registry**: This table is the authoritative source for plugin type counts and entry points. All documentation references should link here.

### Plugin Type History

| Version | Count | Changes |
|---------|-------|---------|
| floe-core 2.1 | 11 | Moved PolicyEnforcer + DataContract to core modules (not plugins) |
| floe-core 2.0 | 13 | Split ObservabilityPlugin -> TelemetryBackendPlugin + LineageBackendPlugin (ADR-0035) |
| floe-core 1.5 | 12 | Added DBTPlugin (ADR-0043) |
| floe-core 1.4 | 11 | Added DataQualityPlugin (ADR-0044) |
| floe-core 1.0 | 11 | Initial plugin architecture |

## Plugin Structure

Each plugin is a self-contained package:

```
plugins/floe-orchestrator-dagster/
├── src/
│   ├── __init__.py
│   └── plugin.py           # DagsterOrchestratorPlugin class
├── chart/                   # Helm chart (if service deployment needed)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── configmap.yaml
├── tests/
│   ├── test_plugin.py
│   └── conftest.py
└── pyproject.toml          # Entry point registration
```

## Documentation Index

| Document | Description |
|----------|-------------|
| [Discovery and Registry](discovery.md) | Plugin discovery via entry points, PluginRegistry implementation |
| [Plugin Interfaces](interfaces.md) | All plugin interface ABCs (ComputePlugin, OrchestratorPlugin, etc.) |
| [Lifecycle and Versioning](lifecycle.md) | API versioning, compatibility checks, PluginMetadata |
| [Configuration and CLI](configuration.md) | CLI commands, creating custom plugins |
| [Integration Patterns](integration-patterns.md) | Compute-catalog integration, DuckDB example |

## Related Documents

- [ADR-0008: Repository Split](../adr/0008-repository-split.md) - Plugin architecture details
- [ADR-0010: Target-Agnostic Compute](../adr/0010-target-agnostic-compute.md) - ComputePlugin
- [ADR-0020: Ingestion Plugins](../adr/0020-ingestion-plugins.md) - IngestionPlugin
- [ADR-0031: Infisical as Default Secrets Management](../adr/0031-infisical-secrets.md) - SecretsPlugin
- [ADR-0032: Semantic Layer Compute Plugin Integration](../adr/0032-cube-compute-integration.md) - SemanticLayerPlugin delegation
- [ADR-0033: Target Airflow 3.x](../adr/0033-airflow-3x.md) - OrchestratorPlugin for Airflow
- [ADR-0034: dbt-duckdb Iceberg Catalog Workaround](../adr/0034-dbt-duckdb-iceberg.md) - ComputePlugin Iceberg integration
- [Interfaces](../interfaces/index.md) - Full interface definitions
