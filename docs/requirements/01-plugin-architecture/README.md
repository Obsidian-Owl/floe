# Domain 01: Plugin Architecture

**Priority**: CRITICAL
**Total Requirements**: 100
**Status**: Complete specification

## Overview

This domain defines the plugin architecture that enables floe extensibility. The plugin system allows platform teams to select compute engines, orchestrators, catalogs, and other infrastructure components without changing core code.

**Core Architectural Principle**: Composability (ADR-0037)
- Plugin Architecture > Configuration Switches
- Interface > Implementation
- Progressive Disclosure
- Opt-in Complexity

## Plugin Types (11 Total)

| Plugin Type | Entry Point | Purpose | Requirements |
|-------------|-------------|---------|--------------|
| ComputePlugin | `floe.computes` | dbt execution (DuckDB, Snowflake, Spark, etc.) | REQ-011 to REQ-020 |
| OrchestratorPlugin | `floe.orchestrators` | Job scheduling (Dagster, Airflow 3.x) | REQ-021 to REQ-030 |
| CatalogPlugin | `floe.catalogs` | Iceberg catalog (Polaris, Unity, Glue, Nessie) | REQ-031 to REQ-040 |
| StoragePlugin | `floe.storage` | Object storage (S3, GCS, Azure, MinIO) | REQ-041 to REQ-050 |
| TelemetryBackendPlugin | `floe.telemetry_backends` | Telemetry backends (Jaeger, Datadog, Grafana Cloud) | REQ-051 to REQ-055 |
| LineageBackendPlugin | `floe.lineage_backends` | Lineage backends (Marquez, Atlan, OpenMetadata) | REQ-056 to REQ-060 |
| SemanticLayerPlugin | `floe.semantic_layers` | BI APIs (Cube, MetricFlow, dbt SL) | REQ-061 to REQ-065 |
| IngestionPlugin | `floe.ingestion` | Data loading (dlt, Airbyte) | REQ-066 to REQ-070 |
| IdentityPlugin | `floe.identity` | Authentication (OIDC, OAuth2, JWT) | REQ-071 to REQ-075 |
| SecretsPlugin | `floe.secrets` | Credential management (Infisical, ESO, Vault) | REQ-076 to REQ-080 |
| DBTPlugin | `floe.dbt` | dbt compilation (dbt-core, dbt Fusion, dbt Cloud) | REQ-086 to REQ-100 |

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins. See Domain 03 for requirements. DataQualityPlugin (Great Expectations, Soda) exists but is tracked separately in ADR-0044.

## Key Architectural Decisions

- **ADR-0037**: Composability Principle - Plugin interfaces preferred over configuration switches
- **ADR-0008**: Repository Split - Plugin discovery via entry points
- **ADR-0010**: Target-Agnostic Compute - ComputePlugin abstraction
- **ADR-0035**: ObservabilityPlugin Interface - Pluggable observability backends
- **ADR-0036**: StoragePlugin Interface - PyIceberg FileIO pattern
- **ADR-0033**: Airflow 3.x Support - OrchestratorPlugin extensibility

## Requirements Files

- [01-plugin-discovery.md](01-plugin-discovery.md) - REQ-001 to REQ-010: Plugin registry, discovery, lifecycle
- [02-compute-plugin.md](02-compute-plugin.md) - REQ-011 to REQ-020: ComputePlugin ABC and compliance
- [03-orchestrator-plugin.md](03-orchestrator-plugin.md) - REQ-021 to REQ-030: OrchestratorPlugin ABC
- [04-catalog-plugin.md](04-catalog-plugin.md) - REQ-031 to REQ-040: CatalogPlugin ABC
- [05-storage-plugin.md](05-storage-plugin.md) - REQ-041 to REQ-050: StoragePlugin ABC (**NEW**)
- [06-observability-plugin.md](06-observability-plugin.md) - REQ-051 to REQ-060: ObservabilityPlugin ABC (**NEW**)
- [07-semantic-ingestion-plugins.md](07-semantic-ingestion-plugins.md) - REQ-061 to REQ-070: SemanticLayer + Ingestion
- [08-identity-secrets-plugins.md](08-identity-secrets-plugins.md) - REQ-071 to REQ-085: Identity + Secrets (**NEW**)
- [09-dbt-compilation-plugin.md](09-dbt-compilation-plugin.md) - REQ-086 to REQ-095: dbt Compilation Plugin (**NEW**)
- [10-sql-linting.md](10-sql-linting.md) - REQ-096 to REQ-100: SQL Linting (**NEW**)

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Test Spec |
|------------------|-----|------------------|-----------|
| REQ-001 to REQ-010 | ADR-0008, ADR-0037 | plugin-architecture.md | tests/unit/test_plugin_registry.py |
| REQ-011 to REQ-020 | ADR-0010 | plugin-architecture.md:103-142 | tests/contract/test_compute_plugin.py |
| REQ-021 to REQ-030 | ADR-0033 | plugin-architecture.md:144-167 | tests/contract/test_orchestrator_plugin.py |
| REQ-031 to REQ-040 | ADR-0008 | plugin-architecture.md:169-192 | tests/contract/test_catalog_plugin.py |
| REQ-041 to REQ-050 | ADR-0036 | plugin-architecture.md (NEW) | tests/contract/test_storage_plugin.py |
| REQ-051 to REQ-060 | ADR-0035 | plugin-architecture.md (NEW) | tests/contract/test_observability_plugin.py |
| REQ-061 to REQ-070 | ADR-0001, ADR-0020 | plugin-architecture.md:194-269 | tests/contract/test_semantic_ingestion.py |
| REQ-071 to REQ-085 | ADR-0022, ADR-0031 | plugin-architecture.md (NEW) | tests/contract/test_identity_secrets.py |
| REQ-086 to REQ-095 | ADR-0043 | plugin-architecture.md (NEW) | tests/contract/test_dbt_runtime_plugin.py |

## Epic Mapping (Refactoring Roadmap)

This domain's requirements are satisfied across multiple Epics:

- **Epic 3: Plugin Interface Extraction** - Extract ABCs from MVP hardcoded logic
  - REQ-001 to REQ-010: Plugin registry infrastructure
  - REQ-011 to REQ-020: ComputePlugin (7 MVP targets → plugins)
  - REQ-021 to REQ-030: OrchestratorPlugin (Dagster → plugin)
  - REQ-031 to REQ-040: CatalogPlugin (Polaris → plugin)
  - REQ-061 to REQ-065: SemanticLayerPlugin (Cube → plugin)
  - REQ-086 to REQ-095: DBTRuntimePlugin (dbt-core → plugin)

- **Epic 8: Production Hardening** - Add missing plugin types for production
  - REQ-041 to REQ-050: StoragePlugin (multi-cloud support)
  - REQ-051 to REQ-060: ObservabilityPlugin (pluggable backends)
  - REQ-066 to REQ-070: IngestionPlugin (dlt integration)
  - REQ-071 to REQ-085: IdentityPlugin + SecretsPlugin (production security)

## Validation Criteria

Domain 01 is complete when:

- [ ] All 95 requirements documented with complete template fields
- [ ] All plugin ABCs defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] Plugin discovery tests pass (PluginRegistry, entry points)
- [ ] All plugin compliance tests pass (ABC method signatures)
- [ ] Contract tests validate cross-package plugin usage
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements
- [ ] Test coverage > 80% for plugin infrastructure

## Notes

- **Backward Compatibility**: MVP hardcoded implementations become default plugins (e.g., `floe-compute-duckdb`, `floe-orchestrator-dagster`)
- **Breaking Changes**: NONE - Plugin system is additive, hardcoded logic remains as fallback
- **Migration Risk**: LOW - Well-defined interfaces, extensive test coverage
