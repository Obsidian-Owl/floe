# Research: Epic 3D Contract Monitoring

**Date**: 2026-02-08
**Branch**: `3d-contract-monitoring`

## Prior Decisions (from Agent-Memory)

- Epic 3C (Data Contracts) is complete with 83 tasks (FLO-1485 through FLO-1567)
- ODCS v3.1+ standard via `open-data-contract-standard` package
- ContractValidator exists with drift detection, inheritance validation, versioning
- Alert-only enforcement confirmed (ADR-0028)

## Existing Foundation (Reusable)

### DataContract Models (Epic 3C)

**Location**: `packages/floe-core/src/floe_core/schemas/data_contract.py`

| Model | Source | Key Fields |
|-------|--------|------------|
| `DataContract` | ODCS v3.1+ package alias | apiVersion, kind, id, version, status, name, domain, schema_, slaProperties |
| `SchemaObject` | ODCS DataContractModel | name, description, properties, logicalType |
| `SchemaProperty` | ODCS DataContractElement | name, logicalType, required, primaryKey, unique, classification |
| `ServiceLevelAgreementProperty` | ODCS SLA | property, value, element |
| `ContractViolation` | floe-core | error_code, severity, message, element_name, expected, actual |
| `ContractValidationResult` | floe-core | valid, violations, warnings, schema_hash, validated_at |
| `SchemaComparisonResult` | floe-core | matches, type_mismatches, missing_columns, extra_columns |

### Plugin Infrastructure

**Base**: `PluginMetadata` ABC at `packages/floe-core/src/floe_core/plugin_metadata.py`
- Properties: name, version, floe_api_version, description, dependencies
- Lifecycle: startup(), shutdown(), health_check() -> HealthStatus
- Config: get_config_schema() -> type[BaseModel] | None

**HealthStatus**: dataclass with state (HEALTHY|DEGRADED|UNHEALTHY), message, details

**Existing Plugins** (patterns to follow):
- `TelemetryBackendPlugin`: `plugins/telemetry.py` - OTLP exporter config, Helm values
- `LineageBackendPlugin`: `plugins/lineage.py` - HTTP transport config, namespace strategy
- `ComputePlugin`: `plugins/compute.py` - validate_connection() for availability pings, generate_dbt_profile() for connection config
- `QualityPlugin`: `plugins/quality.py` - run_checks(), run_suite(), calculate_quality_score()

**Plugin Types** (13 existing, need to add ALERT_CHANNEL → 14 total):
COMPUTE, CATALOG, ORCHESTRATOR, SEMANTIC_LAYER, INGESTION, STORAGE, TELEMETRY_BACKEND, LINEAGE_BACKEND, QUALITY, DBT, RBAC, IDENTITY, SECRETS

### Plugin Registry

**Location**: `packages/floe-core/src/floe_core/plugin_registry.py`
- Singleton: `get_registry()`
- Discovery: `discover_all()` scans entry points
- Loading: `get(PluginType, name)` lazy loads
- Entry point pattern: `[project.entry-points."floe.plugins.{type}"]`

### OTel Metrics

**Location**: `packages/floe-core/src/floe_core/telemetry/metrics.py`
- `MetricRecorder(name, version)` - wraps OTel API
- Methods: `increment()` (Counter), `set_gauge()` (Gauge), `record_histogram()` (Histogram)
- Labels via attributes dict, automatic instrument caching
- Dependencies: opentelemetry-api>=1.39.0, opentelemetry-sdk>=1.20.0

### OpenLineage

**Location**: `packages/floe-core/src/floe_core/plugins/lineage.py`
- `LineageBackendPlugin` ABC: get_transport_config(), get_namespace_strategy()
- Direct HTTP transport to lineage backend (Marquez, Atlan, etc.)

### CLI Framework

**Location**: `packages/floe-core/src/floe_core/cli/`
- Click-based with command groups: `data/`, `platform/`, `rbac/`
- Pattern: `@click.command()` with `@click.option()` and `@click.argument()`

### Enforcement Infrastructure

**Location**: `packages/floe-core/src/floe_core/enforcement/`
- `PolicyEnforcer`: Core enforcement orchestrator
- `Violation` model: error_code, severity, policy_type, message, expected, actual, suggestion
- `EnforcementResult`: passed, violations, summary
- `ContractValidator`: validate(), validate_with_drift_detection(), etc.

## Technology Decisions

### Decision 1: AlertChannelPlugin as New Plugin Type

**Decision**: Create `AlertChannelPlugin` as a new plugin ABC registered under `floe.alert_channels` entry point group (following existing pattern: `floe.computes`, `floe.catalogs`, etc.). Add `ALERT_CHANNEL` to PluginType enum.

**Rationale**: Follows established plugin pattern. Alert channels are pluggable — different orgs use different tools (Slack, PagerDuty, ServiceNow). Enterprise channels can be installed separately.

**Alternatives Rejected**:
- Hardcoded alert mechanisms: Violates Plugin-First Architecture (Constitution II)
- Embedding in TelemetryBackendPlugin: Conflates observability with alerting; different lifecycle

### Decision 2: Async Monitoring Engine with asyncio

**Decision**: ContractMonitor uses `asyncio` for check scheduling and execution.

**Rationale**: ADR-0028 specifies `async def` for all check methods. Monitoring involves I/O-heavy operations (DB queries, HTTP calls, compute engine pings). Async allows concurrent checks across contracts without thread overhead.

**Alternatives Rejected**:
- Threading: More complex, harder to test, no benefit over asyncio for I/O-bound work
- Celery/task queue: Over-engineered for a single-service deployment

### Decision 3: PostgreSQL for State Persistence

**Decision**: Use PostgreSQL (already in platform stack) for monitoring state via SQLAlchemy async.

**Rationale**: PostgreSQL is the platform database (CloudNativePG for prod, StatefulSet for non-prod). No new dependency. Supports time-series queries for trend analysis. 90-day retention with aggregates.

**Alternatives Rejected**:
- TimescaleDB: Adds dependency, PostgreSQL sufficient for monitoring scale
- Redis: No durability guarantees, not suitable for compliance data
- InfluxDB: Adds infrastructure complexity, overkill for contract monitoring

### Decision 4: MetricRecorder for OTel Metrics (Not prometheus_client)

**Decision**: Use existing `MetricRecorder` from `floe_core.telemetry.metrics` for all monitoring metrics, NOT direct `prometheus_client`.

**Rationale**: MetricRecorder wraps OTel API which exports via OTLP Collector to any backend (Prometheus, Grafana, Datadog). ADR-0028 mentions prometheus_client but ADR-0035 established OTel as the standard. MetricRecorder is the canonical pattern.

**Note**: ADR-0028 code examples use `prometheus_client.Registry` but this contradicts ADR-0035's OTel-first approach. The MetricRecorder pattern is correct.

### Decision 5: ContractViolationEvent as Sole Alert Interface

**Decision**: `ContractViolationEvent` (frozen Pydantic model) is the SOLE data contract between ContractMonitor and AlertChannelPlugins.

**Rationale**: Follows Constitution IV (Contract-Driven Integration). Alert channels should not need to understand monitoring internals. Single model enables consistent serialization to CloudEvents, Slack blocks, email templates, etc.

## Gaps Identified

1. **PluginType.ALERT_CHANNEL** does not exist in plugin_types.py — needs to be added
2. **No async scheduler** exists in floe-core — need to implement (asyncio-based)
3. **No PostgreSQL models** exist for monitoring state — need to create with SQLAlchemy
4. **OpenLineage event emission** helper does not exist — need a `LineageEventEmitter` utility using LineageBackendPlugin.get_transport_config() for HTTP transport
5. **CLI `sla` command group** does not exist — need to add to `packages/floe-core/src/floe_core/cli/`
6. **No monitoring-specific OTel semantic conventions** — need to define `floe.contract.*` attributes
7. **No Iceberg-to-contract schema type mapping** — SchemaDriftCheck uses CatalogPlugin to get Iceberg table schema; need type mapping from Iceberg types to contract SchemaProperty types

### Decision 6: CatalogPlugin for Schema Drift Queries (Not ComputePlugin)

**Decision**: SchemaDriftCheck queries actual table schemas via `CatalogPlugin.connect().load_table().schema()`, NOT via ComputePlugin.

**Rationale**: ComputePlugin ABC has no `get_table_schema()` method. Adding one would break all existing compute plugin implementations. CatalogPlugin already provides `connect()` returning a PyIceberg Catalog, from which `load_table()` yields the Iceberg table with its schema. Since all tables are Iceberg (Constitution III — enforced), this approach works universally. Iceberg schema types are mapped to contract `SchemaProperty` logical types for comparison.

**Alternatives Rejected**:
- Add `get_table_schema()` to ComputePlugin: Breaking change to all existing implementations
- Use dbt introspection: Adds dbt dependency to monitoring, not available in all environments
