# Feature Specification: Semantic Layer Plugin

**Epic**: 4E (Semantic Layer Plugin)
**Feature Branch**: `4e-semantic-layer`
**Created**: 2026-02-06
**Status**: Draft
**Input**: User description: "Implement the SemanticLayerPlugin concrete implementation using Cube, including dbt manifest to Cube schema generation, compute plugin datasource delegation, security context, Helm deployment (full Cube Stack), test fixtures, and DuckDB compute extension for Cube datasource config"

## Clarifications

### Session 2026-02-06

- Q: The existing SemanticLayerPlugin ABC has 3 methods but the epic plan shows 6. Should we expand the ABC? A: Add `get_api_endpoints()` and `get_helm_values_override()` to the ABC (5 total methods). `get_dagster_resource_config()` stays as Cube-specific since the orchestrator is pluggable and coupling Dagster into the semantic layer ABC violates component ownership.
- Q: Should the Cube Helm chart be included in this epic's scope? A: Yes, full Cube Stack: API, Refresh Worker, Cube Store Router, and Cube Store Workers. Complete production deployment as subchart of floe-platform.
- Q: Should extending DuckDBComputePlugin with Cube datasource config be in scope? A: Yes, include in 4E. The Cube plugin needs datasource config from compute; this is a natural part of wiring Cube end-to-end.
- Q: Where should generated Cube schema files live? A: Use the `output_dir` parameter from `sync_from_dbt_manifest()`. Caller decides location (e.g., `cube/schema/` in project, temp dir for testing).
- Q: How should the schema generator classify dbt columns as Cube measures vs dimensions? A: Use dbt manifest column `data_type` (numeric types → measures, string/date types → dimensions) with `meta.cube_type` tag overrides for exceptions. This leverages warehouse adapter type info already in the manifest and handles 90%+ of cases automatically.
- Q: When sync_from_dbt_manifest() re-runs and output_dir already has schema files, what should happen? A: Clean and regenerate. Delete all YAML files in output_dir before writing new schemas. Schema generation is idempotent and deterministic — dbt manifest is always the source of truth. Treats generated schemas as build artifacts, not hand-edited files.
- Q: Should the Cube plugin support defining pre-aggregation rules as part of schema generation in Epic 4E? A: Yes, include in 4E scope. Schema generation should produce `preAggregations` blocks in Cube YAML, driven by dbt `meta` tags (e.g., `meta.cube_pre_aggregation`). Covers rollup definitions, refresh key config, and partition granularity. Scheduling of pre-aggregation refresh remains out of scope (orchestrator responsibility).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin Developer Reviews and Extends SemanticLayerPlugin ABC (Priority: P0)

A plugin developer needs to implement an alternative semantic layer (e.g., dbt Semantic Layer, Lightdash). They require a well-defined interface that specifies exactly what operations a semantic layer must support, enabling them to implement adapters without knowledge of Cube internals.

**Why this priority**: The ABC is the foundation all semantic layer plugins depend on. It already exists with 3 methods but needs 2 additional methods (`get_api_endpoints`, `get_helm_values_override`) to be complete.

**Independent Test**: Can be fully tested by implementing a mock semantic layer that satisfies all ABC requirements, verifying the interface is complete and usable without any external dependencies.

**Acceptance Scenarios**:

1. **Given** a developer creating a new semantic layer adapter, **When** they inherit from `SemanticLayerPlugin` ABC, **Then** they receive clear errors for any unimplemented required methods (all 5 abstract methods)
2. **Given** a complete semantic layer plugin implementation, **When** registered with the plugin registry via entry point `floe.semantic_layers`, **Then** it is discoverable and instantiable by the platform
3. **Given** the `SemanticLayerPlugin` ABC, **When** a developer reviews the interface, **Then** all method signatures include typed parameters and return values with documentation
4. **Given** the existing 3 ABC methods, **When** 2 new methods are added, **Then** backward compatibility is maintained (existing code that type-checks against ABC is unaffected since no concrete implementations exist yet)

---

### User Story 2 - Data Engineer Uses Cube as Default Semantic Layer (Priority: P0)

A data engineer wants Cube as the default semantic layer so they can query dbt models via SQL, REST, and GraphQL APIs. The Cube plugin must implement the full ABC, register as an entry point, and be discoverable by the platform.

**Why this priority**: Without a concrete implementation, the ABC provides no value. Cube is the default semantic layer per ADR-0001.

**Independent Test**: Can be fully tested by instantiating `CubeSemanticPlugin`, verifying all ABC methods are implemented, and checking plugin metadata (name, version, floe_api_version).

**Acceptance Scenarios**:

1. **Given** a valid `CubeSemanticConfig` configuration, **When** the plugin initializes, **Then** it establishes configuration and health check succeeds
2. **Given** the `CubeSemanticPlugin` class, **When** checked against `SemanticLayerPlugin` ABC, **Then** `issubclass(CubeSemanticPlugin, SemanticLayerPlugin)` returns True
3. **Given** the plugin is registered in pyproject.toml, **When** `PluginDiscovery.discover_all()` runs, **Then** the plugin appears under `PluginType.SEMANTIC_LAYER` with name "cube"
4. **Given** the `PluginLoader`, **When** `loader.get(PluginType.SEMANTIC_LAYER, "cube")` is called, **Then** a valid `CubeSemanticPlugin` instance is returned
5. **Given** the E2E test `test_all_plugin_types_discoverable`, **When** it runs, **Then** `SEMANTIC_LAYER` type passes (currently FAIL)

---

### User Story 3 - Data Engineer Generates Cube Schemas from dbt Manifest (Priority: P0)

A data engineer wants Cube schemas generated automatically from dbt models so they don't manually maintain two schema definitions. When `floe compile` runs, the semantic layer plugin reads `manifest.json` and generates Cube YAML schema files.

**Why this priority**: Schema generation is the core value of the semantic layer plugin. Without it, users must manually write Cube schemas, defeating the purpose of the integration.

**Independent Test**: Can be fully tested by providing a sample dbt manifest.json fixture, running `sync_from_dbt_manifest()`, and verifying the output YAML files contain correct Cube definitions.

**Acceptance Scenarios**:

1. **Given** a dbt manifest with model nodes, **When** `sync_from_dbt_manifest()` is called, **Then** each model node becomes a Cube with name matching the dbt model name
2. **Given** a dbt model with columns, **When** schema is generated, **Then** numeric columns become measures (type: sum/count) and non-numeric columns become dimensions
3. **Given** a dbt model with `ref()` dependencies, **When** schema is generated, **Then** Cube joins are inferred from the dependency graph
4. **Given** a dbt model with `meta` tags, **When** schema is generated, **Then** Cube metadata is populated from dbt meta (e.g., `meta.cube_type: "view"`)
5. **Given** an `output_dir` parameter, **When** schema generation runs, **Then** YAML files are written to the specified directory
6. **Given** a manifest with models from multiple schemas (bronze, silver, gold), **When** schema is generated with a filter, **Then** only specified schemas/tags are included

---

### User Story 4 - Platform Provides Compute Datasource Config for Cube (Priority: P0)

The Cube semantic layer delegates database connectivity to the active ComputePlugin (ADR-0032). The DuckDB compute plugin must provide a method that returns Cube-compatible datasource configuration, including Iceberg catalog attachment SQL.

**Why this priority**: Without compute plugin delegation, Cube has no database connection. This is the critical integration point between Cube and the data layer.

**Independent Test**: Can be fully tested by calling `get_datasource_config(duckdb_plugin)` on the Cube plugin and verifying the returned config contains DuckDB-specific settings with Iceberg attachment SQL.

**Acceptance Scenarios**:

1. **Given** a DuckDB compute plugin instance, **When** `get_datasource_config(compute_plugin)` is called, **Then** the returned config contains `type: "duckdb"` and a valid database path
2. **Given** the DuckDB plugin has Iceberg catalog configuration, **When** datasource config is generated, **Then** the `initSql` field contains `LOAD iceberg; ATTACH ...` SQL for catalog attachment
3. **Given** a different compute plugin (e.g., Snowflake), **When** `get_datasource_config()` is called, **Then** a Snowflake-compatible datasource config is returned
4. **Given** the `DuckDBComputePlugin` class, **When** inspected, **Then** it has a `get_cube_datasource_config()` method returning Cube-compatible configuration

---

### User Story 5 - Platform Operator Configures Security Context (Priority: P1)

A platform operator needs row-level security for multi-tenant data. The semantic layer plugin provides security context that maps namespaces and roles to row filters and column permissions.

**Why this priority**: Security context enables multi-tenancy in the semantic layer. Without it, all users see all data.

**Independent Test**: Can be fully tested by building a security context with namespace and roles, and verifying the output dictionary contains correct row filters and column permissions.

**Acceptance Scenarios**:

1. **Given** a namespace "tenant_acme" and roles ["analyst"], **When** `get_security_context()` is called, **Then** the returned dict includes row filters scoped to that tenant
2. **Given** a namespace with multiple roles, **When** security context is built, **Then** role-based column visibility is included
3. **Given** an admin role, **When** security context is built, **Then** no row filters are applied (full access)

---

### User Story 6 - Platform Operator Deploys Cube via Helm (Priority: P1)

A platform operator deploys the full Cube Stack in Kubernetes via Helm. The deployment includes Cube API (REST/GraphQL/SQL endpoints), Refresh Worker (pre-aggregation builder), Cube Store Router, and Cube Store Workers.

**Why this priority**: K8s deployment is required for the semantic layer to run in production. The Helm chart enables infrastructure-as-code deployment.

**Independent Test**: Can be tested by running `helm template` on the chart and validating the generated manifests contain all required resources.

**Acceptance Scenarios**:

1. **Given** the floe-platform Helm chart, **When** `cube.enabled: true` in values.yaml, **Then** the Cube subchart is deployed with API, Refresh Worker, and Cube Store components
2. **Given** `get_helm_values_override()` output from the plugin, **When** merged with chart values, **Then** the deployment reflects plugin configuration (image tag, API settings, resource limits)
3. **Given** the Cube API deployment, **When** running, **Then** port 4000 serves REST/GraphQL and port 15432 serves SQL (Postgres wire protocol)
4. **Given** Cube secrets configuration, **When** deployed, **Then** `CUBEJS_API_SECRET` is sourced from a K8s Secret (not hardcoded)
5. **Given** `cube.enabled: false`, **When** Helm template renders, **Then** no Cube resources are created

---

### User Story 7 - Data Engineer Queries Semantic Layer via APIs (Priority: P1)

A data engineer queries the semantic layer through SQL, REST, or GraphQL APIs. The plugin provides API endpoint discovery so tools and applications can find the correct endpoints.

**Why this priority**: API exposure is the consumption interface. Without discoverable endpoints, BI tools cannot connect.

**Independent Test**: Can be fully tested by calling `get_api_endpoints()` and verifying the returned dictionary contains SQL, REST, and GraphQL endpoint paths.

**Acceptance Scenarios**:

1. **Given** a running Cube API, **When** `get_api_endpoints()` is called, **Then** it returns `{"sql": ..., "rest": ..., "graphql": ...}`
2. **Given** the REST endpoint, **When** a query is sent to `/cubejs-api/v1/load`, **Then** a JSON response with data is returned
3. **Given** the SQL endpoint on port 15432, **When** connected via psql or psycopg2, **Then** Cube SQL queries using `MEASURE()` syntax work

---

### User Story 8 - Platform Operator Monitors Semantic Layer Health (Priority: P2)

A platform operator needs to monitor the semantic layer for health and availability. The plugin provides health checks and observability integration.

**Why this priority**: Health monitoring is important for production but not required for basic semantic layer functionality.

**Independent Test**: Can be fully tested by calling `health_check()` and verifying it returns a valid `HealthStatus` with response time.

**Acceptance Scenarios**:

1. **Given** a running Cube API, **When** `health_check()` is called, **Then** it returns `HealthStatus.HEALTHY` with response time
2. **Given** Cube API is unreachable, **When** `health_check()` is called, **Then** it returns `HealthStatus.UNHEALTHY` with error details
3. **Given** health check with timeout parameter, **When** the API responds slowly, **Then** the check respects the configured timeout

---

### Edge Cases

- What happens when the dbt manifest has no model nodes?
- How does the system handle dbt models with no columns (e.g., incremental models with only `ref()`)?
- What happens when Cube API is unavailable during health check?
- How does schema generation handle dbt model names with special characters?
- What happens when `sync_from_dbt_manifest` is called with a non-existent manifest path?
- How does the system handle conflicting Cube schema files from previous generation runs?
- What happens when DuckDB compute plugin doesn't have Iceberg configuration?
- How does security context handle namespaces that don't exist?
- What happens when Helm deployment has insufficient resources for Cube Store?
- How does the system handle Cube API secret rotation?

## Requirements *(mandatory)*

### Functional Requirements

**SemanticLayerPlugin ABC Enhancement**

- **FR-001**: ABC MUST define `get_api_endpoints() -> dict[str, str]` abstract method returning semantic layer API endpoint paths
- **FR-002**: ABC MUST define `get_helm_values_override() -> dict[str, Any]` abstract method returning Helm deployment configuration

**CubeSemanticPlugin Implementation**

- **FR-003**: System MUST provide `CubeSemanticPlugin` class implementing `SemanticLayerPlugin` ABC with all 5 abstract methods
- **FR-004**: Plugin MUST be registered as entry point `floe.semantic_layers` with name "cube" in pyproject.toml
- **FR-005**: Plugin MUST be discoverable via `PluginDiscovery.discover_all()` and `PluginLoader.get(PluginType.SEMANTIC_LAYER, "cube")`
- **FR-006**: Plugin MUST expose `name="cube"`, `version="0.1.0"`, `floe_api_version="1.0"` metadata properties
- **FR-007**: Plugin MUST accept configuration via `CubeSemanticConfig` Pydantic model with `model_config = ConfigDict(frozen=True, extra="forbid")`
- **FR-008**: Plugin MUST implement `health_check()` returning `HealthStatus` based on Cube API reachability
- **FR-009**: Plugin MUST implement `startup()` and `shutdown()` lifecycle methods

**Schema Generation (sync_from_dbt_manifest)**

- **FR-010**: System MUST parse dbt `manifest.json` and convert model nodes to Cube YAML schema definitions
- **FR-011**: Each dbt model MUST become a Cube with `sql_table: schema.model_name` (Cube YAML convention)
- **FR-012**: Columns with numeric `data_type` in dbt manifest (INTEGER, FLOAT, DECIMAL, NUMBER, etc.) MUST become Cube measures with aggregation type: `sum` for amount/value columns, `count` for ID columns; overridable via `meta.cube_measure_type` tag
- **FR-013**: Columns with non-numeric `data_type` (VARCHAR, STRING, DATE, TIMESTAMP, BOOLEAN) MUST become Cube dimensions with Cube type inferred from SQL type (string→string, date/timestamp→time, boolean→boolean); overridable via `meta.cube_type` tag
- **FR-014**: dbt `ref()` relationships MUST be converted to Cube joins
- **FR-015**: dbt model `meta` tags MUST propagate to Cube metadata (e.g., `meta.cube_type`, `meta.cube_measure_type`)
- **FR-016**: System MUST support filtering models by schema prefix or tag
- **FR-017**: Generated schema files MUST be valid Cube YAML format
- **FR-018**: System MUST clean (delete all `.yaml`/`.yml` files in) the `output_dir` before writing new schema files, ensuring idempotent regeneration with no orphaned schemas
- **FR-019**: System MUST raise `FileNotFoundError` if manifest path doesn't exist
- **FR-020**: System MUST raise `SchemaGenerationError` if manifest is malformed (missing "nodes" key, invalid JSON)

**Pre-Aggregation Definitions**

- **FR-021**: Schema generator MUST produce `preAggregations` blocks in Cube YAML when dbt models have `meta.cube_pre_aggregation` tags
- **FR-022**: Pre-aggregation definitions MUST support rollup type with configurable measure/dimension selections
- **FR-023**: Pre-aggregation definitions MUST support `refreshKey` configuration (e.g., `every: "1 hour"`, `sql`-based)
- **FR-024**: Pre-aggregation definitions MUST support `partitionGranularity` for time-partitioned rollups (day, week, month)
- **FR-025**: Models without `meta.cube_pre_aggregation` tags MUST NOT have preAggregations generated (opt-in only)

**Datasource Configuration (get_datasource_config)**

- **FR-026**: System MUST accept a `ComputePlugin` instance and return datasource config dict
- **FR-027**: For DuckDB compute, config MUST include `type: "duckdb"`, database path, and Iceberg catalog attachment `initSql`
- **FR-028**: System MUST support extensible datasource config for different compute backends (DuckDB, Snowflake, Spark)

**DuckDB Compute Extension**

- **FR-029**: `DuckDBComputePlugin` MUST expose a `get_cube_datasource_config()` method returning Cube-compatible configuration
- **FR-030**: Config MUST include `initSql` with `LOAD iceberg; ATTACH` statement for Polaris catalog
- **FR-031**: Config MUST include configurable database path and catalog endpoint

**Security Context (get_security_context)**

- **FR-032**: System MUST map namespace to row-level security filters
- **FR-033**: System MUST map roles to column-level access permissions
- **FR-034**: Admin roles MUST bypass all security filters

**API Endpoints (get_api_endpoints)**

- **FR-035**: System MUST return REST endpoint path (`/cubejs-api/v1/load`)
- **FR-036**: System MUST return GraphQL endpoint path (`/cubejs-api/graphql`)
- **FR-037**: System MUST return SQL endpoint information (Postgres wire protocol, port 15432)

**Helm Deployment**

- **FR-038**: System MUST provide `get_helm_values_override()` returning Helm values for Cube deployment
- **FR-039**: Helm chart MUST deploy Cube API as a Deployment with REST/GraphQL (port 4000) and SQL (port 15432) endpoints
- **FR-040**: Helm chart MUST deploy Cube Refresh Worker as a Deployment for pre-aggregation building
- **FR-041**: Helm chart MUST deploy Cube Store as a StatefulSet with Router and Worker components
- **FR-042**: Helm chart MUST source `CUBEJS_API_SECRET` from a K8s Secret
- **FR-043**: Helm chart MUST support `cube.enabled` toggle to disable the entire subchart
- **FR-044**: Helm chart MUST include configurable resource limits and requests for all components

**Orchestrator Wiring**

- **FR-054**: Orchestrator plugin MUST load the semantic layer plugin as a Dagster resource via `try_create_semantic_resources(plugins)` when `CompiledArtifacts.plugins.semantic` is configured
- **FR-055**: Orchestrator MUST create a downstream Dagster asset `sync_semantic_schemas` that depends on all dbt model assets and calls `sync_from_dbt_manifest()` after dbt runs complete
- **FR-056**: Semantic resource factory MUST follow the established Iceberg wiring pattern (`try_create_iceberg_resources`)
- **FR-057**: Schema sync asset MUST read manifest from `DBTResource.get_manifest()` path and write to configured `schema_path`
- **FR-058**: Orchestrator MUST gracefully degrade when `plugins.semantic` is None (no semantic layer configured)

**Configuration**

- **FR-045**: Plugin MUST accept configuration through `CubeSemanticConfig` Pydantic model
- **FR-046**: Config MUST include `server_url` (Cube API URL), `api_secret` (SecretStr), and compute delegation settings
- **FR-047**: Config MUST validate all fields using Pydantic v2 field validators

**Observability**

- **FR-048**: Plugin MUST emit OpenTelemetry spans for schema generation and health check operations
- **FR-049**: Plugin MUST use structured logging via `structlog` for all operations
- **FR-050**: Plugin MUST NOT log secret values (api_secret, credentials)

**Test Fixtures**

- **FR-051**: System MUST provide `testing/fixtures/semantic.py` with Cube-specific test fixtures
- **FR-052**: Fixtures MUST include `cube_config` (session-scoped), `cube_plugin` (connected instance)
- **FR-053**: Fixtures MUST integrate with existing `IntegrationTestBase` and `BasePluginDiscoveryTests`

### Key Entities

- **SemanticLayerPlugin**: Abstract base class in floe-core defining the interface for semantic layer plugins. Extended with `get_api_endpoints()` and `get_helm_values_override()` methods. All concrete implementations must register via `floe.semantic_layers` entry point.

- **CubeSemanticPlugin**: Concrete implementation of `SemanticLayerPlugin` for Cube. Handles schema generation from dbt manifests, datasource configuration via compute plugin delegation, security context building, API endpoint discovery, and Helm values generation. Lives in `plugins/floe-semantic-cube/`.

- **CubeSemanticConfig**: Pydantic v2 configuration model for the Cube plugin. Includes `server_url` (str), `api_secret` (SecretStr), `database_name` (str), `schema_path` (Path | None), model filter settings, and compute delegation preferences. Uses `ConfigDict(frozen=True, extra="forbid")`.

- **CubeSchemaGenerator**: Internal class that converts dbt manifest.json nodes to Cube YAML schema files. Responsible for: model-to-cube mapping, column-to-measure/dimension inference, ref-to-join conversion, and meta tag propagation.

- **DuckDBComputePlugin (extension)**: Existing plugin in `plugins/floe-compute-duckdb/` extended with `get_cube_datasource_config()` method. Returns Cube-compatible datasource config including DuckDB database path and Iceberg catalog attachment `initSql`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `CubeSemanticPlugin` passes all `BasePluginDiscoveryTests` (11 inherited tests) confirming entry point registration and discovery
- **SC-002**: `CubeSemanticPlugin` passes all `BaseHealthCheckTests` (11 inherited tests) confirming health check compliance
- **SC-003**: `test_all_plugin_types_discoverable` E2E test passes with `SEMANTIC_LAYER` type present (currently FAIL)
- **SC-004**: Schema generation converts a 10-model dbt manifest to valid Cube YAML files within 2 seconds
- **SC-005**: All generated Cube YAML files pass Cube schema validation (syntactically valid)
- **SC-006**: Contract test validates `CompiledArtifacts.plugins.semantic` round-trip (serialize + deserialize preserves all fields)
- **SC-007**: Unit test coverage for `plugins/floe-semantic-cube/` exceeds 80%
- **SC-008**: Helm chart renders valid K8s manifests with all 4 Cube Stack components when `cube.enabled: true`
- **SC-009**: DuckDB compute plugin returns valid Cube datasource config with Iceberg attachment SQL
- **SC-010**: All new code passes `mypy --strict`, `ruff`, `bandit` checks

## Assumptions

- SemanticLayerPlugin ABC already exists in `packages/floe-core/src/floe_core/plugins/semantic.py` with 3 methods
- CompiledArtifacts v0.5.0 already has `plugins.semantic` field as `PluginRef | None` (no schema changes needed)
- Entry point group `floe.semantic_layers` is registered in `PluginType` enum
- Plugin registry from Epic 1 is available for plugin discovery
- DuckDB compute plugin (Epic 4A) is available and functional
- Catalog plugin (Epic 4C, Polaris) is available for Iceberg catalog attachment in DuckDB
- Storage plugin (Epic 4D, Iceberg) provides table management
- Helm infrastructure (Epic 9B) supports subchart additions
- Cube.js Docker image is publicly available (cubejs/cube)
- dbt manifest.json follows dbt's documented schema (v11+)
- PyYAML is available for Cube schema file generation

## Out of Scope

- dbt Semantic Layer implementation (alternative to Cube - future epic)
- Cube pre-aggregation materialization **scheduling** (orchestrator decides when to trigger; definitions are in scope)
- Custom Cube functions or measures beyond what dbt manifest provides
- Cube Playground/Developer UI deployment
- Cube data model versioning (Cube manages this internally)
- Direct BI tool integration configuration (users configure BI tools independently)
- Cube caching configuration beyond basic Cube Store deployment
- `get_dagster_resource_config()` as ABC method (Cube-specific, not generic to all semantic layers)
- Streaming or real-time semantic layer queries
- Cube multi-cluster deployment or horizontal scaling beyond basic replicas
- Cube API secret rotation (handled by K8s Secret rotation mechanisms, not the plugin)
- dbt selection syntax filtering (future enhancement; schema prefix and tag filtering covers primary use cases)

## Integration & Wiring

### Full Wiring Path

The complete integration chain from configuration to semantic layer consumption:

```
CompiledArtifacts (floe-core)
  -> PluginRegistry.get(COMPUTE, "duckdb")     -> ComputePlugin
  -> PluginRegistry.get(SEMANTIC_LAYER, "cube") -> CubeSemanticPlugin
  -> plugin.get_datasource_config(compute_plugin) -> Cube datasource config
  -> plugin.get_helm_values_override() -> Helm values for deployment
  -> plugin.get_api_endpoints() -> REST/GraphQL/SQL endpoint discovery

Orchestrator (runtime wiring):
  -> try_create_semantic_resources(plugins) -> Dagster resource
  -> sync_semantic_schemas asset (downstream of all dbt assets)
     -> calls plugin.sync_from_dbt_manifest(manifest, output_dir)
     -> Cube schema files auto-update after every dbt run
```

### Data Flow

```
dbt models -> Iceberg tables (Epic 4D) -> Polaris catalog (Epic 4C)
    |                                          |
manifest.json                    DuckDB compute (Epic 4A)
    |                                          |
    v                                          |
Dagster sync_semantic_schemas asset (post-dbt) |
    |                                          |
    v                                          |
Cube schema generation ---------> Cube queries through DuckDB
    |
REST/GraphQL/SQL APIs -> BI tools, dashboards, AI agents
```

### Component Boundary Summary

| Component | Package | Responsibility |
|-----------|---------|---------------|
| SemanticLayerPlugin ABC | `packages/floe-core/` | Interface definition (5 abstract methods) |
| CubeSemanticPlugin | `plugins/floe-semantic-cube/` | Cube implementation of ABC |
| CubeSchemaGenerator | `plugins/floe-semantic-cube/` | dbt manifest -> Cube YAML conversion |
| CubeSemanticConfig | `plugins/floe-semantic-cube/` | Pydantic configuration model |
| DuckDBComputePlugin (ext) | `plugins/floe-compute-duckdb/` | `get_cube_datasource_config()` method |
| Orchestrator semantic wiring | `plugins/floe-orchestrator-dagster/` | `try_create_semantic_resources()` + sync asset |
| Cube Helm chart | `charts/floe-platform/charts/cube/` | K8s deployment (API, Worker, Store) |
| Test fixtures | `testing/fixtures/semantic.py` | Cube-specific test infrastructure |

### Existing Contract

`CompiledArtifacts.plugins.semantic` is already present as `PluginRef | None` in v0.5.0. No schema changes required. The Cube plugin populates this field:

```python
PluginRef(
    type="cube",
    version="0.1.0",
    config={
        "server_url": "http://cube:4000",
        "api_secret": "...",
        "database_name": "analytics"
    }
)
```

### File Ownership (Exclusive)

```text
# ABC Enhancement (MODIFY EXISTING)
packages/floe-core/src/floe_core/plugins/
  semantic.py                    # Add get_api_endpoints, get_helm_values_override

# Cube Plugin (NEW)
plugins/floe-semantic-cube/
  pyproject.toml                 # Entry point: floe.semantic_layers
  src/floe_semantic_cube/
    __init__.py
    plugin.py                    # CubeSemanticPlugin
    config.py                    # CubeSemanticConfig (Pydantic)
    schema_generator.py          # dbt manifest -> Cube YAML
    errors.py                    # Error types
    tracing.py                   # OTel helpers
    py.typed                     # PEP 561 marker
  tests/
    conftest.py
    unit/
      conftest.py
      test_plugin.py
      test_config.py
      test_schema_generator.py
    integration/
      conftest.py
      test_discovery.py          # Inherits BasePluginDiscoveryTests
      test_health_check.py       # Inherits BaseHealthCheckTests

# DuckDB Extension (MODIFY EXISTING)
plugins/floe-compute-duckdb/
  src/floe_compute_duckdb/
    plugin.py                    # Add get_cube_datasource_config()

# Orchestrator Wiring (MODIFY EXISTING)
plugins/floe-orchestrator-dagster/
  src/floe_orchestrator_dagster/
    resources/
      semantic.py                # try_create_semantic_resources() (NEW)
    assets/
      semantic_sync.py           # sync_semantic_schemas downstream asset (NEW)
  tests/
    unit/
      test_semantic_resources.py # Unit tests for resource factory + sync asset (NEW)
    integration/
      test_semantic_wiring.py    # Integration test for full wiring chain (NEW)

# Helm Chart (NEW)
charts/floe-platform/charts/cube/
  Chart.yaml
  values.yaml
  templates/
    deployment-api.yaml
    deployment-refresh-worker.yaml
    statefulset-cube-store.yaml
    service-api.yaml
    service-sql.yaml
    configmap.yaml
    _helpers.tpl

# Test Fixtures (NEW)
testing/fixtures/semantic.py

# Contract Tests (NEW)
tests/contract/test_semantic_layer_abc.py
tests/contract/test_core_to_semantic_contract.py
```
