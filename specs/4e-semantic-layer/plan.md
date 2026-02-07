# Implementation Plan: Semantic Layer Plugin

**Branch**: `4e-semantic-layer` | **Date**: 2026-02-06 | **Spec**: specs/4e-semantic-layer/spec.md

## Summary

Implement the CubeSemanticPlugin as the default semantic layer for floe, providing automatic dbt manifest-to-Cube YAML schema generation, compute plugin datasource delegation, security context, API endpoint discovery, and full Helm deployment (Cube API, Refresh Worker, Cube Store Router + Workers). This extends the existing SemanticLayerPlugin ABC with 2 new methods, adds a `get_cube_datasource_config()` method to DuckDBComputePlugin, creates the `plugins/floe-semantic-cube/` package, deploys via a Helm subchart of `floe-platform`, and provides test fixtures and contract tests.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: PyYAML (schema generation), pydantic>=2.0 (config), structlog>=24.0 (logging), opentelemetry-api>=1.0 (tracing), httpx>=0.25.0 (health checks)
**Storage**: N/A (Cube handles data access via ComputePlugin delegation)
**Testing**: pytest, testing.base_classes (BasePluginDiscoveryTests, BaseHealthCheckTests, BasePluginLifecycleTests), IntegrationTestBase
**Target Platform**: K8s (Helm subchart of floe-platform)
**Project Type**: Monorepo plugin package
**Performance Goals**: Schema generation <2s for 10-model manifest (SC-004)
**Constraints**: Must follow plugin ABC pattern, Pydantic v2, mypy --strict, ruff, bandit
**Scale/Scope**: 1 new plugin package (`plugins/floe-semantic-cube/`), 1 ABC enhancement (`packages/floe-core/`), 1 compute plugin extension (`plugins/floe-compute-duckdb/`), 1 Helm subchart (`charts/floe-platform/charts/cube/`), 1 test fixture file, 2 contract test files

## Constitution Check

**Principle I: Technology Ownership**
- [x] Code is placed in correct package: ABC in `packages/floe-core/`, Cube impl in `plugins/floe-semantic-cube/`, DuckDB extension in `plugins/floe-compute-duckdb/`, Helm in `charts/floe-platform/charts/cube/`
- [x] No SQL parsing/validation in Python -- dbt manifest is read as JSON, Cube SQL strings are pass-through templates (`SELECT * FROM {{ source_table }}`)
- [x] No orchestration logic outside floe-dagster -- Cube plugin handles semantic layer only; pre-aggregation scheduling is explicitly out of scope

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface: CubeSemanticPlugin inherits SemanticLayerPlugin ABC
- [x] Plugin registered via entry point: `[project.entry-points."floe.semantic_layers"]` with `cube = "floe_semantic_cube:CubeSemanticPlugin"`
- [x] PluginMetadata declares name ("cube"), version ("0.1.0"), floe_api_version ("1.0")

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved: OTel tracing on schema generation/health check, structured logging, K8s deployment
- [x] Pluggable choices documented: Semantic layer is pluggable (Cube is default, dbt Semantic Layer future); compute engine delegation is pluggable (DuckDB, Snowflake, etc.)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts: `CompiledArtifacts.plugins.semantic` is `PluginRef | None` (already in v0.5.0, no schema change)
- [x] Pydantic v2 models for all schemas: `CubeSemanticConfig` with `ConfigDict(frozen=True, extra="forbid")`, `SecretStr` for api_secret
- [x] Contract changes follow versioning rules: ABC adds 2 new abstract methods (minor version bump); no breaking changes since no concrete implementations exist yet

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster: Cube API health check tests against deployed Cube
- [x] No `pytest.skip()` usage: Tests FAIL if infrastructure unavailable
- [x] `@pytest.mark.requirement()` on all integration tests: Mapped to FR-xxx identifiers

**Principle VI: Security First**
- [x] Input validation via Pydantic: `CubeSemanticConfig` validates all fields
- [x] Credentials use SecretStr: `api_secret: SecretStr` in config
- [x] No shell=True, no dynamic code execution on untrusted data: Schema generator uses PyYAML safe_dump, no eval/exec

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only: Plugin config comes from `CubeSemanticConfig`; Helm values flow from parent chart
- [x] Layer ownership respected: Plugin (Layer 1: Foundation), Helm chart (Layer 3: Services)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted: `floe.semantic.sync_from_dbt_manifest`, `floe.semantic.health_check`, `floe.semantic.get_datasource_config` spans
- [x] OpenLineage events for data transformations: Not directly applicable (Cube delegates to dbt/compute for data movement; lineage comes from those layers)

## Project Structure

### Documentation (this feature)

```text
specs/4e-semantic-layer/
├── spec.md              # Feature specification (exists)
└── plan.md              # This file
```

### Source Code (repository root)

```text
# ABC Enhancement (MODIFY EXISTING)
packages/floe-core/src/floe_core/plugins/
  semantic.py                    # Add get_api_endpoints(), get_helm_values_override()

# Cube Plugin (NEW)
plugins/floe-semantic-cube/
  pyproject.toml                 # Entry point: floe.semantic_layers -> cube
  src/floe_semantic_cube/
    __init__.py                  # Exports: CubeSemanticPlugin, CubeSemanticConfig
    plugin.py                    # CubeSemanticPlugin (all 5 ABC methods + lifecycle)
    config.py                    # CubeSemanticConfig (Pydantic v2, frozen, SecretStr)
    schema_generator.py          # CubeSchemaGenerator: dbt manifest -> Cube YAML
    errors.py                    # CubeSemanticError, SchemaGenerationError, etc.
    tracing.py                   # OTel span helpers (follow polaris tracing.py pattern)
    py.typed                     # PEP 561 marker
  tests/
    conftest.py                  # Package-level fixtures
    unit/
      conftest.py
      test_plugin.py             # CubeSemanticPlugin ABC compliance, metadata
      test_config.py             # CubeSemanticConfig validation, edge cases
      test_schema_generator.py   # dbt manifest -> Cube YAML conversion
      test_errors.py             # Error type validation
    integration/
      conftest.py
      test_discovery.py          # Inherits BasePluginDiscoveryTests
      test_health_check.py       # Inherits BaseHealthCheckTests

# DuckDB Extension (MODIFY EXISTING)
plugins/floe-compute-duckdb/
  src/floe_compute_duckdb/
    plugin.py                    # Add get_cube_datasource_config() method

# Helm Chart (NEW)
charts/floe-platform/charts/cube/
  Chart.yaml                     # apiVersion: v2, subchart metadata
  values.yaml                    # Default config (image, resources, ports)
  templates/
    deployment-api.yaml          # Cube API (port 4000 REST/GraphQL, port 15432 SQL)
    deployment-refresh-worker.yaml  # Cube Refresh Worker (pre-aggregation builder)
    statefulset-cube-store.yaml  # Cube Store Router + Workers
    service-api.yaml             # ClusterIP for API (4000)
    service-sql.yaml             # ClusterIP for SQL (15432)
    service-cube-store.yaml      # ClusterIP for Cube Store Router (3030)
    configmap.yaml               # Non-secret env vars (CUBEJS_DB_TYPE, etc.)
    _helpers.tpl                 # Naming helpers for cube subchart

# Parent Chart Integration (MODIFY EXISTING)
charts/floe-platform/
  Chart.yaml                     # Add cube subchart dependency
  values.yaml                    # Add cube.* section
  templates/
    secret-cube.yaml             # NEW: CUBEJS_API_SECRET from K8s Secret
    configmap-cube.yaml          # NEW: Cube configuration (datasource, etc.)

# Test Fixtures (NEW)
testing/fixtures/semantic.py     # cube_config, cube_plugin fixtures

# Contract Tests (NEW)
tests/contract/test_semantic_layer_abc.py       # ABC contract stability
tests/contract/test_core_to_semantic_contract.py  # CompiledArtifacts.plugins.semantic round-trip
```

**Structure Decision**: Plugin package at `plugins/floe-semantic-cube/` following the established pattern from `plugins/floe-catalog-polaris/` and `plugins/floe-compute-duckdb/`. Uses `hatchling` build system with `src/` layout and `[project.entry-points."floe.semantic_layers"]`.

## Integration Design

### Entry Point Integration

- Feature reachable from: Plugin Registry via entry point `floe.semantic_layers`
- Entry point declaration: `plugins/floe-semantic-cube/pyproject.toml` -> `[project.entry-points."floe.semantic_layers"]` -> `cube = "floe_semantic_cube:CubeSemanticPlugin"`
- Discovery path: `PluginDiscovery.discover_all()` -> `PluginLoader.get(PluginType.SEMANTIC_LAYER, "cube")` -> `CubeSemanticPlugin` instance
- Wiring verification: `test_all_plugin_types_discoverable` E2E test must pass with `SEMANTIC_LAYER` type present (currently FAIL, SC-003)

### Dependency Integration

| From Package | What Is Used | Import Path |
|---|---|---|
| `floe-core` | `SemanticLayerPlugin` ABC | `floe_core.plugins.semantic.SemanticLayerPlugin` |
| `floe-core` | `PluginMetadata`, `HealthStatus`, `HealthState` | `floe_core.plugin_metadata` |
| `floe-core` | `ComputePlugin` (TYPE_CHECKING only) | `floe_core.plugins.compute.ComputePlugin` |
| `floe-core` | `ComputeConfig`, `CatalogConfig` | `floe_core.compute_config` |
| `floe-core` | OTel observability helpers | `floe_core.observability` |
| `pydantic` | `BaseModel`, `ConfigDict`, `Field`, `SecretStr`, `field_validator` | `pydantic` |
| `structlog` | Structured logging | `structlog` |
| `opentelemetry-api` | Span creation, attributes | `opentelemetry.trace` |
| `httpx` | HTTP health check to Cube API `/readiness` | `httpx` |
| `PyYAML` | YAML generation for Cube schema files | `yaml` |

### Produces for Others

| What Is Produced | Consumer | Integration Point |
|---|---|---|
| `CubeSemanticPlugin` instance | Plugin Registry | Entry point `floe.semantic_layers` |
| Cube YAML schema files | Cube runtime | Written to `output_dir` by `sync_from_dbt_manifest()` |
| Datasource config dict | Cube runtime | Returned by `get_datasource_config(compute_plugin)` |
| Helm values override | Helm chart | Returned by `get_helm_values_override()` |
| API endpoint dict | Platform consumers (BI tools, etc.) | Returned by `get_api_endpoints()` |
| Security context dict | Cube runtime | Returned by `get_security_context()` |
| `get_cube_datasource_config()` on DuckDB | CubeSemanticPlugin | Called in `get_datasource_config()` |
| Test fixtures (`cube_config`, `cube_plugin`) | Integration tests | `testing/fixtures/semantic.py` |

### Cleanup Required

- None (new code, no refactoring of existing code beyond additive changes to ABC and DuckDB plugin)

## Implementation Phases

### Phase 0: Foundation (ABC Enhancement + Config + Errors + Tracing)

This phase establishes the interface contract and shared infrastructure.

**T001: Enhance SemanticLayerPlugin ABC with 2 new abstract methods**
- File: `packages/floe-core/src/floe_core/plugins/semantic.py`
- Add `get_api_endpoints(self) -> dict[str, str]` abstract method with docstring
- Add `get_helm_values_override(self) -> dict[str, Any]` abstract method with docstring
- Update module docstring to list all 5 abstract methods
- No breaking changes (no existing concrete implementations)
- Requirements: FR-001, FR-002

**T002: Create plugin package scaffold (pyproject.toml, __init__.py, py.typed)**
- File: `plugins/floe-semantic-cube/pyproject.toml`
  - Build system: `hatchling`
  - Entry point: `[project.entry-points."floe.semantic_layers"]` -> `cube = "floe_semantic_cube:CubeSemanticPlugin"`
  - Dependencies: `floe-core>=0.1.0`, `pydantic>=2.0,<3.0`, `structlog>=24.0,<26.0`, `httpx>=0.25.0,<1.0`, `opentelemetry-api>=1.0,<2.0`, `PyYAML>=6.0,<7.0`
  - Wheel packages: `["src/floe_semantic_cube"]`
  - Tool config: mypy strict, ruff, pytest markers
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/__init__.py` (exports CubeSemanticPlugin, CubeSemanticConfig)
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/py.typed` (empty PEP 561 marker)

**T003: Create CubeSemanticConfig Pydantic model**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/config.py`
- `CubeSemanticConfig(BaseModel)` with `model_config = ConfigDict(frozen=True, extra="forbid")`
- Fields:
  - `server_url: str` (Cube API URL, default `"http://cube:4000"`)
  - `api_secret: SecretStr` (Cube API secret)
  - `database_name: str` (default `"analytics"`)
  - `schema_path: Path | None` (default None, optional output path)
  - `health_check_timeout: float` (default 5.0, seconds)
  - `model_filter_tags: list[str]` (default `[]`, filter dbt models by tag)
  - `model_filter_schemas: list[str]` (default `[]`, filter dbt models by schema)
- Field validators: `server_url` must be valid URL, `health_check_timeout` > 0
- Requirements: FR-007, FR-045, FR-046, FR-047

**T004: Create error types**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/errors.py`
- `CubeSemanticError(Exception)` -- base error
- `SchemaGenerationError(CubeSemanticError)` -- manifest parsing or YAML generation failures
- `CubeHealthCheckError(CubeSemanticError)` -- health check failures
- `CubeDatasourceError(CubeSemanticError)` -- datasource config failures

**T005: Create OTel tracing helpers**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/tracing.py`
- Follow pattern from `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py`
- Span name prefix: `floe.semantic`
- Helper functions: `start_semantic_span(operation)`, `record_schema_generation_duration()`, `record_schema_generation_error()`
- Attributes: `semantic.plugin`, `semantic.operation`, `semantic.model_count`, `semantic.output_dir`

### Phase 1: Core Plugin (CubeSemanticPlugin)

This phase implements the plugin class with all 5 ABC methods plus lifecycle.

**T006: Implement CubeSemanticPlugin class skeleton**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- Class: `CubeSemanticPlugin(SemanticLayerPlugin)`
- Metadata properties: `name="cube"`, `version="0.1.0"`, `floe_api_version="1.0"`, `description="Cube semantic layer plugin for floe data platform"`
- Dependencies property: `["duckdb"]` (soft dependency on compute)
- `get_config_schema()` returns `CubeSemanticConfig`
- Constructor accepts `CubeSemanticConfig` instance (or uses defaults)
- Requirements: FR-003, FR-004, FR-005, FR-006, FR-007

**T007: Implement startup/shutdown lifecycle**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- `startup()`: Validate config, initialize httpx.Client for health checks, log startup
- `shutdown()`: Close httpx.Client, log shutdown
- OTel spans on both operations
- Requirements: FR-009

**T008: Implement health_check()**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- HTTP GET to `{server_url}/readiness` with configurable timeout
- Returns `HealthStatus(state=HealthState.HEALTHY)` on 200
- Returns `HealthStatus(state=HealthState.UNHEALTHY, message=...)` on failure/timeout
- OTel span: `floe.semantic.health_check`
- Uses httpx (already in dependencies)
- Requirements: FR-008, FR-048, FR-049, FR-050

**T009: Implement get_api_endpoints()**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- Returns dict with:
  - `"rest": f"{server_url}/cubejs-api/v1/load"`
  - `"graphql": f"{server_url}/cubejs-api/graphql"`
  - `"sql": f"{server_url}:15432"` (Postgres wire protocol info)
- Requirements: FR-035, FR-036, FR-037

**T010: Implement get_helm_values_override()**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- Returns dict matching Helm values structure:
  - `cube.enabled: True`
  - `cube.image.tag: "v0.36.0"`
  - `cube.api.port: 4000`, `cube.api.sqlPort: 15432`
  - `cube.config.databaseType` from compute delegation
  - Resource limits from config or sensible defaults
- Requirements: FR-038

**T011: Implement get_security_context()**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- Accepts `namespace: str` and `roles: list[str]`
- Returns dict with:
  - `tenant_id`: namespace value
  - `allowed_roles`: list of roles
  - `row_filters`: dict mapping cube names to SQL filters (e.g., `"tenant_id = '{namespace}'"`)
  - `column_permissions`: role-based visibility (admin gets full access)
- Admin role detection: if "admin" in roles, no row filters applied
- Requirements: FR-032, FR-033, FR-034

**T012: Implement get_datasource_config()**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- Accepts `compute_plugin: ComputePlugin`
- Checks if plugin has `get_cube_datasource_config()` method (duck-typing check with `hasattr`)
- If present: calls `compute_plugin.get_cube_datasource_config()` and returns result
- If absent: builds generic config from plugin name/metadata (fallback for non-DuckDB computes)
- OTel span: `floe.semantic.get_datasource_config`
- Requirements: FR-026, FR-027, FR-028

### Phase 2: Schema Generator

This phase implements dbt manifest-to-Cube YAML conversion.

**T013: Implement CubeSchemaGenerator class**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Class: `CubeSchemaGenerator`
- Constructor accepts: `model_filter_tags: list[str]`, `model_filter_schemas: list[str]`
- Main method: `generate(manifest_path: Path, output_dir: Path) -> list[Path]`
- Requirements: FR-010, FR-017, FR-018, FR-019, FR-020

**T014: Implement manifest parsing and model filtering**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Parse `manifest.json` as JSON (standard library `json`)
- Extract model nodes from `manifest["nodes"]` where `resource_type == "model"`
- Filter by schema prefix if `model_filter_schemas` is set
- Filter by tag if `model_filter_tags` is set
- Raise `FileNotFoundError` if manifest_path does not exist
- Raise `SchemaGenerationError` if manifest is malformed (missing "nodes" key, invalid JSON)
- Requirements: FR-010, FR-016, FR-019, FR-020

**T015: Implement column-to-measure/dimension inference**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Numeric types (`INTEGER`, `BIGINT`, `FLOAT`, `DECIMAL`, `DOUBLE`, `NUMBER`, `NUMERIC`, `INT`, `SMALLINT`, `TINYINT`, `REAL`) -> Cube measures
  - Measure type defaults: `sum` for amount/value columns; `count` for ID columns (heuristic: column name contains "id" or "count")
  - Overridable via `meta.cube_measure_type` tag
- Non-numeric types (`VARCHAR`, `STRING`, `TEXT`, `CHAR`, `DATE`, `TIMESTAMP`, `TIMESTAMP_NTZ`, `BOOLEAN`, `BOOL`) -> Cube dimensions
  - Dimension type inference: `string` for text types, `time` for date/timestamp, `boolean` for bool
  - Overridable via `meta.cube_type` tag
- Requirements: FR-012, FR-013, FR-015

**T016: Implement ref-to-join conversion**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Parse `depends_on.nodes` from each model node
- For each dependency that is also a model node: create a Cube join
- Join relationship: default `belongs_to`; overridable via `meta.cube_join_relationship`
- Join SQL: inferred from common column names between models (e.g., `${CUBE}.customer_id = ${customers}.id`), or from `meta.cube_join_sql` override
- Requirements: FR-014

**T017: Implement pre-aggregation generation**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Check each model for `meta.cube_pre_aggregation` tag
- If present, generate `preAggregations` block in Cube YAML
- Support fields:
  - `type: "rollup"` (default)
  - `measures: [...]` (list of measure names)
  - `dimensions: [...]` (list of dimension names)
  - `timeDimension: "..."` (for time-partitioned rollups)
  - `granularity: "day"|"week"|"month"` (partition granularity)
  - `refreshKey.every: "1 hour"` (refresh schedule)
  - `refreshKey.sql: "..."` (SQL-based refresh trigger)
- Models without `meta.cube_pre_aggregation` get no preAggregations block
- Requirements: FR-021, FR-022, FR-023, FR-024, FR-025

**T018: Implement YAML file writing**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`
- Clean output_dir before writing (delete all `.yaml` and `.yml` files -- FR-018)
- Generate one YAML file per model: `{output_dir}/{model_name}.yaml`
- Use `yaml.safe_dump()` with `default_flow_style=False`, `sort_keys=False`
- Cube YAML structure per file:
  ```yaml
  cubes:
    - name: orders
      sql_table: schema.orders
      measures:
        - name: total_amount
          type: sum
          sql: total_amount
      dimensions:
        - name: status
          type: string
          sql: status
      joins:
        - name: customers
          sql: "${CUBE}.customer_id = ${customers}.id"
          relationship: belongs_to
      preAggregations:  # only if meta.cube_pre_aggregation present
        - name: main
          type: rollup
          measures: [total_amount]
          dimensions: [status]
          timeDimension: created_at
          granularity: day
          refreshKey:
            every: "1 hour"
  ```
- Return list of written file paths
- Requirements: FR-011, FR-017, FR-018

**T019: Wire sync_from_dbt_manifest() to CubeSchemaGenerator**
- File: `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`
- `sync_from_dbt_manifest(manifest_path, output_dir)` creates `CubeSchemaGenerator` with config filters, calls `generate()`, returns file list
- OTel span: `floe.semantic.sync_from_dbt_manifest` with attributes: manifest_path, output_dir, model_count
- Structured logging on start, completion, error
- Requirements: FR-010, FR-048, FR-049

### Phase 3: DuckDB Compute Extension

This phase adds Cube datasource config to the DuckDB compute plugin.

**T020: Add get_cube_datasource_config() to DuckDBComputePlugin**
- File: `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`
- New method: `get_cube_datasource_config(self, catalog_config: CatalogConfig | None = None) -> dict[str, Any]`
- Returns dict with:
  - `"type": "duckdb"`
  - `"databasePath": ":memory:"` (or from config)
  - `"initSql": "INSTALL iceberg; LOAD iceberg; ATTACH ..."` (built from `get_catalog_attachment_sql()` if catalog_config provided)
  - `"extensions": ["iceberg"]` (if catalog_config provided)
- Reuses existing `get_catalog_attachment_sql()` for the ATTACH statement
- This is a concrete method (not abstract on ComputePlugin) -- Cube-specific, per clarification
- Requirements: FR-029, FR-030, FR-031

### Phase 3a: Orchestrator Wiring

This phase wires the semantic layer plugin into the orchestrator following the established Iceberg pattern.

**T043a: Create semantic resource factory**
- File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py` (NEW)
- Function: `try_create_semantic_resources(plugins: ResolvedPlugins | None) -> dict[str, Any]`
- Follow `try_create_iceberg_resources()` pattern from `resources/iceberg.py`
- Graceful degradation: return `{}` if `plugins.semantic` is None
- Load semantic plugin via `PluginRegistry.get(PluginType.SEMANTIC_LAYER, plugins.semantic.type)`
- Configure plugin from `PluginRef.config` dict
- Call `startup()` and initial `health_check()` (non-fatal on failure)
- Return `{"semantic_layer": configured_plugin_instance}`
- Requirements: FR-054, FR-056, FR-058

**T043b: Wire semantic resources into create_definitions()**
- File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
- In `create_definitions()`, call `try_create_semantic_resources(validated.plugins)` alongside existing `_create_iceberg_resources()`
- Merge returned dict into the resources dict passed to `Definitions()`
- Requirements: FR-054

**T043c: Create downstream sync_semantic_schemas Dagster asset**
- File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py` (NEW)
- Function: Creates a `@asset` that depends on all dbt model assets
- Required resource keys: `{"dbt", "semantic_layer"}`
- Implementation:
  1. Get manifest path from `dbt.get_manifest()` → `{project_dir}/target/manifest.json`
  2. Get output_dir from `semantic_layer.config.schema_path` (or default)
  3. Call `semantic_layer.sync_from_dbt_manifest(manifest_path, output_dir)`
  4. Log number of generated schema files
- OTel span: `floe.orchestrator.sync_semantic_schemas`
- Structured logging on start, completion, error
- Requirements: FR-055, FR-057

**T043d: Write unit tests for orchestrator semantic wiring**
- File: `plugins/floe-orchestrator-dagster/tests/unit/test_semantic_resources.py` (NEW)
- Tests:
  - `try_create_semantic_resources()` with valid PluginRef returns dict with "semantic_layer" key
  - `try_create_semantic_resources()` with None plugins returns empty dict
  - `try_create_semantic_resources()` with None semantic returns empty dict
  - `try_create_semantic_resources()` with invalid plugin type raises gracefully
  - `sync_semantic_schemas` asset calls `sync_from_dbt_manifest()` with correct args
  - `sync_semantic_schemas` asset handles SchemaGenerationError
  - Resources correctly merged in `create_definitions()` alongside Iceberg
- Requirements: FR-054, FR-055, FR-056, FR-057, FR-058

**T043e: Write integration test for full wiring chain**
- File: `plugins/floe-orchestrator-dagster/tests/integration/test_semantic_wiring.py` (NEW)
- Tests:
  - Full chain: `CompiledArtifacts` with `plugins.semantic` configured → orchestrator loads plugin → resource available in Definitions
  - Definitions includes both "iceberg" and "semantic_layer" resources when both configured
  - Definitions works with only "semantic_layer" (no Iceberg) and vice versa
- Inherits `IntegrationTestBase`
- Requirements: FR-054, FR-058

### Phase 4: Helm Chart

This phase creates the Cube subchart and integrates with the parent chart.

**T021: Create Cube subchart scaffold**
- File: `charts/floe-platform/charts/cube/Chart.yaml`
  - `apiVersion: v2`, `name: cube`, `type: application`, `version: 0.1.0`, `appVersion: "0.36.0"`
- File: `charts/floe-platform/charts/cube/values.yaml`
  - `enabled: true` (default)
  - `image.repository: cubejs/cube`, `image.tag: v0.36.0`
  - `cubeStore.image.repository: cubejs/cubestore`, `cubeStore.image.tag: v0.36.0`
  - API port: 4000, SQL port: 15432, Cube Store Router port: 3030
  - Resource defaults (requests: 256Mi/250m, limits: 1Gi/1000m)
  - `replicaCount` for API, refreshWorker, cubeStore workers
- File: `charts/floe-platform/charts/cube/templates/_helpers.tpl`
  - `cube.fullname`, `cube.labels`, `cube.selectorLabels` helpers
  - Follow naming pattern from parent chart helpers

**T022: Create Cube API Deployment template**
- File: `charts/floe-platform/charts/cube/templates/deployment-api.yaml`
- Deployment with:
  - Container: `cubejs/cube:{{ .Values.image.tag }}`
  - Ports: 4000 (REST/GraphQL), 15432 (SQL/Postgres wire)
  - Env from ConfigMap and Secret
  - Readiness probe: HTTP GET `/readiness` port 4000
  - Liveness probe: HTTP GET `/readiness` port 4000
  - Security context: runAsNonRoot, no privilege escalation
  - Resource limits/requests from values
- Conditional: `{{- if .Values.enabled }}`
- Requirements: FR-039

**T023: Create Cube Refresh Worker Deployment template**
- File: `charts/floe-platform/charts/cube/templates/deployment-refresh-worker.yaml`
- Deployment with:
  - Container: `cubejs/cube:{{ .Values.image.tag }}`
  - Env: `CUBEJS_SCHEDULED_REFRESH_TIMER=true` (triggers pre-agg builds)
  - Same env from ConfigMap and Secret as API
  - No service/port exposure (worker process)
  - Resource limits/requests from values
- Conditional: `{{- if .Values.enabled }}`
- Requirements: FR-040

**T024: Create Cube Store StatefulSet template**
- File: `charts/floe-platform/charts/cube/templates/statefulset-cube-store.yaml`
- StatefulSet with:
  - Container: `cubejs/cubestore:{{ .Values.cubeStore.image.tag }}`
  - Router port: 3030 (meta), 3306 (query)
  - Worker ports configured via env
  - PVC for data persistence (if configured)
  - Env: `CUBESTORE_SERVER_NAME`, `CUBESTORE_PORT`, `CUBESTORE_META_PORT`
  - Security context: runAsNonRoot
  - Resource limits/requests from values
- Conditional: `{{- if and .Values.enabled .Values.cubeStore.enabled }}`
- Requirements: FR-041

**T025: Create Service templates**
- File: `charts/floe-platform/charts/cube/templates/service-api.yaml`
  - ClusterIP service exposing port 4000 (REST/GraphQL API)
  - Selector: cube API deployment labels
- File: `charts/floe-platform/charts/cube/templates/service-sql.yaml`
  - ClusterIP service exposing port 15432 (SQL/Postgres wire protocol)
  - Selector: cube API deployment labels
- File: `charts/floe-platform/charts/cube/templates/service-cube-store.yaml`
  - ClusterIP service exposing port 3030 (Cube Store Router)
  - Selector: cube store StatefulSet labels
- Requirements: FR-039

**T026: Create ConfigMap template**
- File: `charts/floe-platform/charts/cube/templates/configmap.yaml`
- Non-secret environment variables:
  - `CUBEJS_DB_TYPE: {{ .Values.config.databaseType }}`
  - `CUBEJS_DEV_MODE: "false"`
  - `CUBEJS_CACHE_AND_QUEUE_DRIVER: "cubestore"`
  - `CUBEJS_CUBESTORE_HOST: {{ include "cube.fullname" . }}-store`
  - `CUBEJS_CUBESTORE_PORT: "3030"`
  - `CUBEJS_TELEMETRY: "false"`
  - `CUBEJS_LOG_LEVEL: {{ .Values.config.logLevel | default "info" }}`
- Conditional: `{{- if .Values.enabled }}`

**T027: Integrate subchart into parent chart**
- File: `charts/floe-platform/Chart.yaml` -- Add dependency:
  ```yaml
  - name: cube
    version: "0.1.0"
    condition: cube.enabled
    alias: cube
  ```
  (Note: local subchart, no repository needed since it's in `charts/` dir)
- File: `charts/floe-platform/values.yaml` -- Add `cube.*` section:
  ```yaml
  cube:
    enabled: false  # Disabled by default, enabled per environment
    image:
      repository: cubejs/cube
      tag: v0.36.0
    config:
      databaseType: duckdb
      logLevel: info
    api:
      replicaCount: 1
      resources:
        requests: { cpu: 250m, memory: 256Mi }
        limits: { cpu: 1000m, memory: 1Gi }
    cubeStore:
      enabled: true
      replicaCount: 1
      resources:
        requests: { cpu: 250m, memory: 256Mi }
        limits: { cpu: 1000m, memory: 1Gi }
  ```
- File: `charts/floe-platform/templates/secret-cube.yaml` -- NEW:
  - Secret containing `CUBEJS_API_SECRET` from `{{ .Values.cube.apiSecret }}`
  - Conditional: `{{- if .Values.cube.enabled }}`
- File: `charts/floe-platform/templates/configmap-cube.yaml` -- NEW:
  - Parent-level ConfigMap for Cube env vars that reference other chart resources
  - E.g., database connection strings that reference internal service names
  - Conditional: `{{- if .Values.cube.enabled }}`
- Requirements: FR-042, FR-043, FR-044

**T028: Add Cube to environment-specific values files**
- File: `charts/floe-platform/values-demo.yaml` -- Add `cube.enabled: true`
- File: `charts/floe-platform/values-dev.yaml` -- Add `cube.enabled: true`
- File: `charts/floe-platform/values-test.yaml` -- Add `cube.enabled: true`
- File: `charts/floe-platform/values-staging.yaml` -- Add `cube.enabled: false` (opt-in)
- File: `charts/floe-platform/values-prod.yaml` -- Add `cube.enabled: false` (opt-in)

### Phase 5: Testing & Quality

This phase creates all test infrastructure and test files.

**T029: Create test fixtures for Cube plugin**
- File: `testing/fixtures/semantic.py`
- Fixtures (follow pattern from `testing/fixtures/polaris.py`, `testing/fixtures/duckdb.py`):
  - `cube_config() -> CubeSemanticConfig` (session-scoped, from env vars or defaults)
  - `cube_plugin(cube_config) -> CubeSemanticPlugin` (function-scoped, connected instance)
  - `sample_dbt_manifest(tmp_path) -> Path` (writes a sample manifest.json with 3 models)
  - `cube_output_dir(tmp_path) -> Path` (temp directory for generated schemas)
- Requirements: FR-051, FR-052, FR-053

**T030: Create unit tests for CubeSemanticConfig**
- File: `plugins/floe-semantic-cube/tests/unit/test_config.py`
- Tests:
  - Valid config creation with all fields
  - Config is frozen (immutable)
  - Config rejects extra fields
  - `api_secret` is `SecretStr` (not logged)
  - `server_url` validation (valid URL)
  - `health_check_timeout` must be > 0
  - Default values are correct
  - Edge cases: empty tags, empty schemas, None schema_path
- Requirements: FR-007, FR-045, FR-046, FR-047

**T031: Create unit tests for CubeSemanticPlugin**
- File: `plugins/floe-semantic-cube/tests/unit/test_plugin.py`
- Tests:
  - Plugin inherits from SemanticLayerPlugin
  - Metadata properties (name, version, floe_api_version, description)
  - `get_config_schema()` returns `CubeSemanticConfig`
  - `get_api_endpoints()` returns correct dict structure
  - `get_helm_values_override()` returns valid Helm values dict
  - `get_security_context()` with namespace and roles
  - `get_security_context()` with admin role (no row filters)
  - `get_datasource_config()` with mock compute plugin
  - `health_check()` with mocked httpx (healthy, unhealthy, timeout)
  - `startup()` and `shutdown()` lifecycle
- Requirements: FR-003, FR-006, FR-008, FR-009, FR-032-FR-037

**T032: Create unit tests for CubeSchemaGenerator**
- File: `plugins/floe-semantic-cube/tests/unit/test_schema_generator.py`
- Tests:
  - Single model conversion to Cube YAML
  - Numeric column -> measure (sum default)
  - Non-numeric column -> dimension (string/time/boolean)
  - `meta.cube_type` tag overrides dimension type
  - `meta.cube_measure_type` tag overrides measure type
  - ID column heuristic (count aggregation)
  - ref() dependency -> Cube join
  - `meta.cube_join_relationship` override
  - Multi-model manifest -> multiple YAML files
  - Model filtering by schema
  - Model filtering by tag
  - Pre-aggregation generation from meta tags
  - Pre-aggregation with refreshKey
  - Pre-aggregation with partitionGranularity
  - No pre-aggregation when meta tag absent
  - Output dir cleanup (deletes old .yaml files)
  - Empty manifest (no model nodes) -> empty list
  - Model with no columns -> cube with no measures/dimensions
  - Invalid manifest JSON -> SchemaGenerationError
  - Missing manifest file -> FileNotFoundError
  - Special characters in model name -> safe filename
  - Schema performance: 10-model manifest < 2 seconds (SC-004)
- Requirements: FR-010-FR-025

**T033: Create unit tests for error types**
- File: `plugins/floe-semantic-cube/tests/unit/test_errors.py`
- Tests:
  - Each error type inherits from CubeSemanticError
  - Error messages are informative
  - Error types can carry context data

**T034: Create contract tests for SemanticLayerPlugin ABC**
- File: `tests/contract/test_semantic_layer_abc.py`
- Tests (follow pattern from `tests/contract/test_compute_plugin_contract.py`):
  - `SemanticLayerPlugin` cannot be instantiated directly (TypeError)
  - ABC has exactly 5 abstract methods: `sync_from_dbt_manifest`, `get_security_context`, `get_datasource_config`, `get_api_endpoints`, `get_helm_values_override`
  - Abstract methods have correct signatures (inspect.signature)
  - Type hints are complete (get_type_hints)
  - ABC inherits from PluginMetadata
  - Optional methods from PluginMetadata work (health_check, startup, shutdown)
  - Method docstrings present

**T035: Create contract tests for CompiledArtifacts.plugins.semantic round-trip**
- File: `tests/contract/test_core_to_semantic_contract.py`
- Tests:
  - `CompiledArtifacts.plugins.semantic` accepts `PluginRef` with type="cube"
  - Serialize -> deserialize preserves all fields
  - None value (no semantic plugin) serializes correctly
  - PluginRef config dict with Cube-specific fields round-trips
- Requirements: SC-006

**T036: Create integration tests for plugin discovery**
- File: `plugins/floe-semantic-cube/tests/integration/test_discovery.py`
- Inherits `BasePluginDiscoveryTests` from `testing/base_classes/plugin_discovery_tests.py`
- Required class attributes:
  - `entry_point_group = "floe.semantic_layers"`
  - `expected_name = "cube"`
  - `expected_module_prefix = "floe_semantic_cube"`
  - `expected_class_name = "CubeSemanticPlugin"`
- Implement `create_plugin_instance()` fixture
- Requirements: SC-001, SC-003

**T037: Create integration tests for health check**
- File: `plugins/floe-semantic-cube/tests/integration/test_health_check.py`
- Inherits `BaseHealthCheckTests` from `testing/base_classes/base_health_check_tests.py`
- Requires `unconnected_plugin` fixture (plugin not yet started)
- Requires `connected_plugin` fixture (plugin with running Cube API)
- Requirements: SC-002

**T038: Create DuckDB compute extension tests**
- File: `plugins/floe-compute-duckdb/tests/unit/test_cube_datasource.py` (NEW test file in existing package)
- Tests:
  - `get_cube_datasource_config()` returns correct dict structure
  - Config includes `type: "duckdb"`
  - Config includes `initSql` with INSTALL/LOAD/ATTACH when catalog_config provided
  - Config without catalog_config returns basic DuckDB config
  - Returned dict has all Cube-required keys
- Requirements: FR-029, FR-030, FR-031, SC-009

**T039: Helm chart template validation**
- Verification via `helm template` command (not a pytest test):
  - `helm template test charts/floe-platform/ --set cube.enabled=true` renders all Cube resources
  - `helm template test charts/floe-platform/ --set cube.enabled=false` renders no Cube resources
  - All 4 Cube Stack components present: API Deployment, Refresh Worker Deployment, Cube Store StatefulSet, Services
  - Secret contains `CUBEJS_API_SECRET`
  - ConfigMap contains required env vars
- Requirements: SC-008

**T040: Test conftest files and package wiring**
- File: `plugins/floe-semantic-cube/tests/conftest.py` (package root conftest)
- File: `plugins/floe-semantic-cube/tests/unit/conftest.py` (unit test conftest with fixtures)
- File: `plugins/floe-semantic-cube/tests/integration/conftest.py` (integration conftest)
- Verify `uv pip install -e plugins/floe-semantic-cube` succeeds
- Verify `pytest plugins/floe-semantic-cube/tests/unit/` passes

### Phase 6: Quality Gates

**T041: Static analysis verification**
- Run `mypy --strict plugins/floe-semantic-cube/src/` -- must pass
- Run `ruff check plugins/floe-semantic-cube/` -- must pass
- Run `ruff check plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` -- must pass (after DuckDB extension)
- Run `bandit -r plugins/floe-semantic-cube/src/` -- must pass (no security issues)
- Requirements: SC-010

**T042: Coverage verification**
- Run `pytest plugins/floe-semantic-cube/tests/unit/ --cov=floe_semantic_cube --cov-report=term-missing`
- Unit test coverage must exceed 80% for `plugins/floe-semantic-cube/`
- Requirements: SC-007

## Task Dependency Graph

```
T001 (ABC enhancement)
  └─> T006 (plugin skeleton) ─> T007..T012 (all plugin methods)
T002 (package scaffold)
  └─> T003 (config) ─> T006
  └─> T004 (errors) ─> T013
  └─> T005 (tracing) ─> T006

T013..T018 (schema generator) ─> T019 (wire to plugin)

T020 (DuckDB extension) -- independent, no prereqs beyond existing code

T043a (semantic resource factory) depends on T006 (plugin skeleton)
T043b (wire into create_definitions) depends on T043a
T043c (sync asset) depends on T043a + T019 (schema gen wired to plugin)
T043d (unit tests) depends on T043a + T043b + T043c
T043e (integration test) depends on T043a + T043b

T021..T028 (Helm chart) -- independent of Python code, can parallel

T029 (test fixtures) depends on T006 (plugin exists)
T030..T033 (unit tests) depend on their respective implementation tasks
T034..T035 (contract tests) depend on T001 (ABC enhancement)
T036..T037 (integration tests) depend on T029 (fixtures) + T006 (plugin)
T038 (DuckDB tests) depends on T020
T039 (Helm validation) depends on T021..T028

T040 (conftest wiring) depends on T002 + T029
T041..T042 (quality gates) depend on all previous tasks including T043a..T043e
```

## Complexity Tracking

No constitution violations. All checkboxes passed. No complexity justification needed.
