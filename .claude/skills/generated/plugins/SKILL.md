---
name: plugins
description: "Skill for the Plugins area of floe. 61 symbols across 47 files."
---

# Plugins

61 symbols | 47 files | Cohesion: 89%

## When to Use

- Working with code in `packages/`
- Understanding how resolve, dfs, lint_project work
- Modifying plugins-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `packages/floe-core/src/floe_core/plugins/dependencies.py` | resolve, _check_missing_dependencies, _find_cycle, dfs, DependencyResolver |
| `packages/floe-core/src/floe_core/plugins/dbt.py` | __init__, __init__, __init__, LintViolation, LintResult |
| `packages/floe-core/src/floe_core/plugins/quality.py` | QualityPlugin, __init_subclass__, get_lineage_emitter, get_quality_facets |
| `packages/floe-core/src/floe_core/plugins/storage.py` | StoragePlugin, delete |
| `packages/floe-core/src/floe_core/plugin_errors.py` | CircularDependencyError, MissingDependencyError |
| `plugins/floe-dbt-core/src/floe_dbt_core/errors.py` | __init__, __init__ |
| `plugins/floe-telemetry-jaeger/src/floe_telemetry_jaeger/plugin.py` | JaegerTelemetryPlugin |
| `plugins/floe-telemetry-console/src/floe_telemetry_console/plugin.py` | ConsoleTelemetryPlugin |
| `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py` | S3StoragePlugin |
| `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py` | CubeSemanticPlugin |

## Entry Points

Start here when exploring this area:

- **`resolve`** (Function) — `packages/floe-core/src/floe_core/plugins/dependencies.py:58`
- **`dfs`** (Function) — `packages/floe-core/src/floe_core/plugins/dependencies.py:206`
- **`lint_project`** (Function) — `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py:414`
- **`lint_sql_files`** (Function) — `plugins/floe-dbt-core/src/floe_dbt_core/linting.py:92`
- **`warn_on_extra_fields`** (Function) — `packages/floe-core/src/floe_core/schemas/manifest.py:527`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `JaegerTelemetryPlugin` | Class | `plugins/floe-telemetry-jaeger/src/floe_telemetry_jaeger/plugin.py` | 25 |
| `ConsoleTelemetryPlugin` | Class | `plugins/floe-telemetry-console/src/floe_telemetry_console/plugin.py` | 22 |
| `S3StoragePlugin` | Class | `plugins/floe-storage-s3/src/floe_storage_s3/plugin.py` | 38 |
| `CubeSemanticPlugin` | Class | `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py` | 50 |
| `K8sSecretsPlugin` | Class | `plugins/floe-secrets-k8s/src/floe_secrets_k8s/plugin.py` | 41 |
| `InfisicalSecretsPlugin` | Class | `plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py` | 88 |
| `K8sRBACPlugin` | Class | `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py` | 31 |
| `GreatExpectationsPlugin` | Class | `plugins/floe-quality-gx/src/floe_quality_gx/plugin.py` | 25 |
| `DBTExpectationsPlugin` | Class | `plugins/floe-quality-dbt/src/floe_quality_dbt/plugin.py` | 24 |
| `DagsterOrchestratorPlugin` | Class | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | 75 |
| `K8sNetworkSecurityPlugin` | Class | `plugins/floe-network-security-k8s/src/floe_network_security_k8s/plugin.py` | 25 |
| `MarquezLineageBackendPlugin` | Class | `plugins/floe-lineage-marquez/src/floe_lineage_marquez/__init__.py` | 164 |
| `DltIngestionPlugin` | Class | `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py` | 77 |
| `KeycloakIdentityPlugin` | Class | `plugins/floe-identity-keycloak/src/floe_identity_keycloak/plugin.py` | 35 |
| `DuckDBComputePlugin` | Class | `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` | 190 |
| `PolarisCatalogPlugin` | Class | `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py` | 60 |
| `PluginMetadata` | Class | `packages/floe-core/src/floe_core/plugin_metadata.py` | 75 |
| `TelemetryBackendPlugin` | Class | `packages/floe-core/src/floe_core/plugins/telemetry.py` | 26 |
| `StoragePlugin` | Class | `packages/floe-core/src/floe_core/plugins/storage.py` | 55 |
| `SinkConnector` | Class | `packages/floe-core/src/floe_core/plugins/sink.py` | 131 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Resolve → Items` | cross_community | 4 |
| `Lint_project → _is_full_fusion_cli` | cross_community | 4 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Floe_catalog_polaris | 4 calls |
| Schemas | 3 calls |
| Floe_core | 2 calls |
| Floe_dbt_fusion | 1 calls |

## How to Explore

1. `gitnexus_context({name: "resolve"})` — see callers and callees
2. `gitnexus_query({query: "plugins"})` — find related execution flows
3. Read key files listed above for implementation details
