# Tasks: Semantic Layer Plugin (Epic 4E)

**Input**: Design documents from `/specs/4e-semantic-layer/`
**Prerequisites**: plan.md (required), spec.md (required)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

**New Package**: `plugins/floe-semantic-cube/`
- Source: `plugins/floe-semantic-cube/src/floe_semantic_cube/`
- Tests: `plugins/floe-semantic-cube/tests/`

**Modified Packages**:
- ABC: `packages/floe-core/src/floe_core/plugins/semantic.py`
- DuckDB: `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`

**Helm Chart**: `charts/floe-platform/charts/cube/`

**Contract Tests**: `tests/contract/` (ROOT level)
**Test Fixtures**: `testing/fixtures/semantic.py`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package scaffold, error types, tracing helpers, and configuration model

- [ ] T001 Create package structure `plugins/floe-semantic-cube/pyproject.toml` with hatchling build system, entry point `floe.semantic_layers` -> `cube = "floe_semantic_cube:CubeSemanticPlugin"`, dependencies (floe-core>=0.1.0, pydantic>=2.0, structlog>=24.0, httpx>=0.25.0, opentelemetry-api>=1.0, PyYAML>=6.0), and tool config (mypy strict, ruff, pytest markers)
- [ ] T002 [P] Create `plugins/floe-semantic-cube/src/floe_semantic_cube/__init__.py` exporting CubeSemanticPlugin and CubeSemanticConfig, and `plugins/floe-semantic-cube/src/floe_semantic_cube/py.typed` PEP 561 marker
- [ ] T003 [P] Create test directory structure: `plugins/floe-semantic-cube/tests/conftest.py`, `plugins/floe-semantic-cube/tests/unit/conftest.py`, `plugins/floe-semantic-cube/tests/integration/conftest.py`
- [ ] T004 [P] Create error types in `plugins/floe-semantic-cube/src/floe_semantic_cube/errors.py`: CubeSemanticError (base), SchemaGenerationError, CubeHealthCheckError, CubeDatasourceError
- [ ] T005 [P] Create OTel tracing helpers in `plugins/floe-semantic-cube/src/floe_semantic_cube/tracing.py` following polaris tracing.py pattern: start_semantic_span(), record_schema_generation_duration(), record_schema_generation_error() with span prefix `floe.semantic`

**Checkpoint**: Package structure ready for development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: ABC enhancement and config model that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### ABC Enhancement

- [ ] T006 Add `get_api_endpoints(self) -> dict[str, str]` and `get_helm_values_override(self) -> dict[str, Any]` abstract methods to SemanticLayerPlugin ABC in `packages/floe-core/src/floe_core/plugins/semantic.py`, update module docstring to list all 5 abstract methods (FR-001, FR-002)

### Configuration Model

- [ ] T007 Implement CubeSemanticConfig Pydantic model in `plugins/floe-semantic-cube/src/floe_semantic_cube/config.py` with fields: server_url (str, default "http://cube:4000"), api_secret (SecretStr), database_name (str, default "analytics"), schema_path (Path | None), health_check_timeout (float, default 5.0), model_filter_tags (list[str]), model_filter_schemas (list[str]); ConfigDict(frozen=True, extra="forbid"); field validators for server_url and health_check_timeout (FR-007, FR-045, FR-046, FR-047)

### Config Tests

- [ ] T008 Write unit tests for CubeSemanticConfig in `plugins/floe-semantic-cube/tests/unit/test_config.py`: valid creation, frozen immutability, extra field rejection, SecretStr for api_secret, server_url validation, health_check_timeout > 0, default values, edge cases (empty tags/schemas, None schema_path) (FR-007, FR-045, FR-046, FR-047)

### Error Tests

- [ ] T009 [P] Write unit tests for error types in `plugins/floe-semantic-cube/tests/unit/test_errors.py`: inheritance from CubeSemanticError, error messages, context data

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Plugin Developer Reviews and Extends SemanticLayerPlugin ABC (Priority: P0)

**Goal**: Complete ABC with 5 abstract methods, validate interface with contract tests

**Independent Test**: Implement a mock semantic layer satisfying all ABC requirements; verify interface completeness without external dependencies

**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006

### Tests for User Story 1

- [ ] T010 [P] [US1] Write contract tests for SemanticLayerPlugin ABC in `tests/contract/test_semantic_layer_abc.py`: ABC not directly instantiable, exactly 5 abstract methods (sync_from_dbt_manifest, get_security_context, get_datasource_config, get_api_endpoints, get_helm_values_override), correct method signatures (inspect.signature), complete type hints (get_type_hints), inherits PluginMetadata, optional methods work (health_check, startup, shutdown), method docstrings present (SC-001)
- [ ] T011 [P] [US1] Write contract tests for CompiledArtifacts.plugins.semantic round-trip in `tests/contract/test_core_to_semantic_contract.py`: PluginRef with type="cube" accepted, serialize-deserialize preserves all fields, None value serializes correctly, Cube-specific config dict round-trips (SC-006)

**Checkpoint**: ABC contract verified - concrete implementations can proceed

---

## Phase 4: User Story 2 - Data Engineer Uses Cube as Default Semantic Layer (Priority: P0)

**Goal**: CubeSemanticPlugin implementing full ABC, registered as entry point, discoverable by platform

**Independent Test**: Instantiate CubeSemanticPlugin, verify all ABC methods implemented, check metadata, validate plugin discovery via entry point

**Requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009

### Tests for User Story 2

- [ ] T012 [P] [US2] Write unit tests for CubeSemanticPlugin in `plugins/floe-semantic-cube/tests/unit/test_plugin.py`: inherits SemanticLayerPlugin, metadata properties (name="cube", version="0.1.0", floe_api_version="1.0", description), get_config_schema() returns CubeSemanticConfig, get_api_endpoints() dict structure, get_helm_values_override() valid dict, get_security_context() with namespace/roles, get_security_context() admin bypass, get_security_context() edge cases (empty namespace, special characters, very long namespace), get_datasource_config() with mock compute, health_check() mocked (healthy/unhealthy/timeout), startup()/shutdown() lifecycle (FR-003, FR-006, FR-008, FR-009, FR-032, FR-033, FR-034)
- [ ] T013 [P] [US2] Write integration tests for plugin discovery in `plugins/floe-semantic-cube/tests/integration/test_discovery.py` inheriting BasePluginDiscoveryTests: entry_point_group="floe.semantic_layers", expected_name="cube", expected_module_prefix="floe_semantic_cube", expected_class_name="CubeSemanticPlugin", create_plugin_instance() fixture (SC-001, SC-003)
- [ ] T014 [P] [US2] Write integration tests for health check in `plugins/floe-semantic-cube/tests/integration/test_health_check.py` inheriting BaseHealthCheckTests: unconnected_plugin fixture, connected_plugin fixture (SC-002)

### Implementation for User Story 2

- [ ] T015 [US2] Implement CubeSemanticPlugin class skeleton in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: inherit SemanticLayerPlugin, metadata properties (name, version, floe_api_version, description), dependencies property (["duckdb"]), get_config_schema() returning CubeSemanticConfig, constructor accepting CubeSemanticConfig (FR-003, FR-004, FR-005, FR-006, FR-007)
- [ ] T016 [US2] Implement startup()/shutdown() lifecycle in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: validate config, initialize httpx.Client, OTel spans, structured logging (FR-009)
- [ ] T017 [US2] Implement health_check() in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: HTTP GET to {server_url}/readiness, return HealthStatus based on response, configurable timeout, OTel span floe.semantic.health_check (FR-008, FR-048, FR-049, FR-050)
- [ ] T018 [US2] Implement get_api_endpoints() in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: return dict with rest, graphql, sql endpoint paths derived from server_url (FR-035, FR-036, FR-037)
- [ ] T019 [US2] Implement get_helm_values_override() in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: return dict with cube.enabled, cube.image.tag, cube.api.port/sqlPort, cube.config.databaseType, resource limits (FR-038)
- [ ] T020 [US2] Implement get_security_context() in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: accept namespace and roles, return dict with tenant_id, allowed_roles, row_filters, column_permissions; admin role bypass (FR-032, FR-033, FR-034)
- [ ] T021 [US2] Implement get_datasource_config() in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: accept ComputePlugin, duck-type check for get_cube_datasource_config(), fallback for non-DuckDB computes, OTel span (FR-026, FR-027, FR-028)
- [ ] T022 [US2] Create test fixtures in `testing/fixtures/semantic.py`: cube_config (session-scoped), cube_plugin (function-scoped connected instance), sample_dbt_manifest (3-model fixture), cube_output_dir (temp directory) (FR-051, FR-052, FR-053)

**Checkpoint**: CubeSemanticPlugin fully functional, discoverable, and testable independently

---

## Phase 5: User Story 3 - Data Engineer Generates Cube Schemas from dbt Manifest (Priority: P0)

**Goal**: Automatic dbt manifest-to-Cube YAML schema generation with filtering, joins, and pre-aggregations

**Independent Test**: Provide sample dbt manifest.json, run sync_from_dbt_manifest(), verify output YAML files contain correct Cube definitions

**Requirements**: FR-010 through FR-025

### Tests for User Story 3

- [ ] T023 [US3] Write unit tests for CubeSchemaGenerator in `plugins/floe-semantic-cube/tests/unit/test_schema_generator.py`: single model conversion, numeric column -> measure (sum default), non-numeric column -> dimension (string/time/boolean), meta.cube_type override, meta.cube_measure_type override, ID column heuristic (count), ref() -> join, meta.cube_join_relationship override, multi-model -> multiple YAML files, filter by schema, filter by tag, pre-aggregation from meta tags, pre-aggregation with refreshKey, pre-aggregation with partitionGranularity, no pre-aggregation when meta absent, output dir cleanup, empty manifest -> empty list, model with no columns -> cube with no measures/dimensions, invalid manifest JSON -> SchemaGenerationError, missing manifest file -> FileNotFoundError, special characters in model name, performance: 10-model manifest < 2s, generated YAML structural validation (cubes list with name/sql_table/measures/dimensions keys per file) (FR-010 through FR-025, SC-004, SC-005)

### Implementation for User Story 3

- [ ] T024 [US3] Create CubeSchemaGenerator class skeleton in `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`: constructor with model_filter_tags and model_filter_schemas, main generate(manifest_path, output_dir) method signature (FR-010, FR-017)
- [ ] T025 [US3] Implement manifest parsing and model filtering in `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`: parse manifest.json, extract model nodes from manifest["nodes"], filter by schema prefix and tag, raise FileNotFoundError/SchemaGenerationError (FR-010, FR-016, FR-019, FR-020)
- [ ] T026 [US3] Implement column-to-measure/dimension inference in `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`: numeric types -> measures (sum default, count for ID columns), non-numeric -> dimensions (string/time/boolean), meta.cube_type and meta.cube_measure_type overrides (FR-012, FR-013, FR-015)
- [ ] T027 [US3] Implement ref-to-join conversion in `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`: parse depends_on.nodes, create Cube joins for model dependencies, default belongs_to relationship, meta.cube_join_relationship and meta.cube_join_sql overrides (FR-014)
- [ ] T028 [US3] Implement pre-aggregation generation in `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`: check meta.cube_pre_aggregation, generate preAggregations block with rollup type, measures, dimensions, timeDimension, granularity, refreshKey; opt-in only (FR-021, FR-022, FR-023, FR-024, FR-025)
- [ ] T029 [US3] Implement YAML file writing in `plugins/floe-semantic-cube/src/floe_semantic_cube/schema_generator.py`: clean output_dir (delete .yaml/.yml), generate one YAML per model using yaml.safe_dump(), return list of written paths (FR-011, FR-017, FR-018)
- [ ] T030 [US3] Wire sync_from_dbt_manifest() to CubeSchemaGenerator in `plugins/floe-semantic-cube/src/floe_semantic_cube/plugin.py`: create generator with config filters, call generate(), OTel span floe.semantic.sync_from_dbt_manifest, structured logging (FR-010, FR-048, FR-049)

**Checkpoint**: Schema generation fully functional with filtering, joins, pre-aggregations, and observability

---

## Phase 6: User Story 4 - Platform Provides Compute Datasource Config for Cube (Priority: P0)

**Goal**: DuckDB compute plugin provides Cube-compatible datasource config including Iceberg attachment SQL

**Independent Test**: Call get_datasource_config(duckdb_plugin) and verify returned config contains DuckDB settings with Iceberg SQL

**Requirements**: FR-029, FR-030, FR-031

### Tests for User Story 4

- [ ] T031 [US4] Write unit tests for DuckDB Cube datasource in `plugins/floe-compute-duckdb/tests/unit/test_cube_datasource.py`: get_cube_datasource_config() returns correct dict, includes type="duckdb", includes initSql with INSTALL/LOAD/ATTACH when catalog_config provided, basic config without catalog_config, all Cube-required keys present (FR-029, FR-030, FR-031, SC-009)

### Implementation for User Story 4

- [ ] T032 [US4] Add get_cube_datasource_config() method to DuckDBComputePlugin in `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py`: accept optional CatalogConfig, return dict with type, databasePath, initSql (INSTALL iceberg; LOAD iceberg; ATTACH...), extensions list; reuse existing get_catalog_attachment_sql() (FR-029, FR-030, FR-031)

**Checkpoint**: DuckDB compute plugin provides Cube datasource config

---

## Phase 6a: Orchestrator Wiring (Cross-Cutting)

**Purpose**: Wire semantic layer plugin into Dagster orchestrator as a resource + downstream asset for post-dbt schema sync

**Independent Test**: Verify `try_create_semantic_resources()` returns valid Dagster resources; verify `sync_semantic_schemas` asset triggers after dbt assets complete

**Requirements**: FR-054, FR-055, FR-056, FR-057, FR-058

### Orchestrator Resource Factory

- [ ] T047 Create `try_create_semantic_resources(plugins)` in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py` following the established Iceberg resource factory pattern (`try_create_iceberg_resources`): load semantic plugin from CompiledArtifacts.plugins.semantic via PluginRegistry, instantiate with config, return dict of Dagster resources {"semantic_layer": plugin_instance}, graceful no-op when plugins.semantic is None (FR-054, FR-056, FR-058)

### Orchestrator Wiring

- [ ] T048 Wire semantic resources into `create_definitions()` in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`: call `try_create_semantic_resources(plugins)` alongside existing `try_create_iceberg_resources()`, merge returned resources into Definitions resources dict (FR-054, FR-056)

### Post-dbt Schema Sync Asset

- [ ] T049 Create downstream `sync_semantic_schemas` Dagster asset in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/semantic_sync.py`: @asset that depends on all dbt model assets, calls `plugin.sync_from_dbt_manifest(manifest_path, output_dir)` using manifest from `DBTResource.get_manifest()` and schema_path from semantic config, OTel span `floe.orchestrator.sync_semantic_schemas`, structured logging (FR-055, FR-057)

### Tests for Orchestrator Wiring

- [ ] T050 Write unit tests for orchestrator semantic wiring in `plugins/floe-orchestrator-dagster/tests/unit/test_semantic_resources.py`: try_create_semantic_resources() returns valid resources, try_create_semantic_resources() returns empty dict when plugins.semantic is None, sync_semantic_schemas asset depends on dbt assets, sync_semantic_schemas calls sync_from_dbt_manifest with correct args, resource factory follows Iceberg pattern (FR-054, FR-055, FR-056, FR-057, FR-058)
- [ ] T051 Write integration test for full wiring chain in `plugins/floe-orchestrator-dagster/tests/integration/test_semantic_wiring.py` inheriting IntegrationTestBase: semantic plugin loaded via entry point, resource created from compiled artifacts, sync asset wired into Definitions, full create_definitions() produces valid Definitions with semantic resources (FR-054, FR-055)

**Checkpoint**: Semantic layer plugin fully wired into orchestrator with resource factory + post-dbt sync asset

---

## Phase 7: User Story 5 - Platform Operator Configures Security Context (Priority: P1)

**Goal**: Multi-tenant row-level security via namespace/role mapping to row filters and column permissions

**Independent Test**: Build security context with namespace and roles, verify output dict contains correct filters and permissions

**Requirements**: FR-032, FR-033, FR-034

> **Note**: Security context implementation is in T020 (Phase 4). Tests are in T012 (Phase 4). This story is covered by the CubeSemanticPlugin implementation. No additional tasks needed beyond verification.

**Checkpoint**: Security context verified via US2 plugin tests

---

## Phase 8: User Story 6 - Platform Operator Deploys Cube via Helm (Priority: P1)

**Goal**: Full Cube Stack deployment in K8s: API, Refresh Worker, Cube Store Router + Workers via Helm subchart

**Independent Test**: Run `helm template` and validate generated manifests contain all required resources

**Requirements**: FR-038 through FR-044

### Tests for User Story 6

- [ ] T033 [US6] Validate Helm chart via `helm template test charts/floe-platform/ --set cube.enabled=true` renders all Cube resources; `--set cube.enabled=false` renders none; verify 4 Cube Stack components (API Deployment, Refresh Worker Deployment, Cube Store StatefulSet, Services), Secret contains CUBEJS_API_SECRET, ConfigMap contains required env vars (SC-008)

### Implementation for User Story 6

- [ ] T034 [P] [US6] Create Cube subchart scaffold: `charts/floe-platform/charts/cube/Chart.yaml` (apiVersion v2, name cube, appVersion 0.36.0), `charts/floe-platform/charts/cube/values.yaml` (enabled, image, ports, resources), `charts/floe-platform/charts/cube/templates/_helpers.tpl` (fullname, labels, selectorLabels)
- [ ] T035 [P] [US6] Create Cube API Deployment template in `charts/floe-platform/charts/cube/templates/deployment-api.yaml`: cubejs/cube image, ports 4000 + 15432, env from ConfigMap/Secret, readiness/liveness probes on /readiness, security context (runAsNonRoot), conditional on .Values.enabled (FR-039)
- [ ] T036 [P] [US6] Create Cube Refresh Worker Deployment template in `charts/floe-platform/charts/cube/templates/deployment-refresh-worker.yaml`: cubejs/cube image, CUBEJS_SCHEDULED_REFRESH_TIMER=true, same env, no port exposure, conditional on .Values.enabled (FR-040)
- [ ] T037 [P] [US6] Create Cube Store StatefulSet template in `charts/floe-platform/charts/cube/templates/statefulset-cube-store.yaml`: cubejs/cubestore image, router port 3030, worker ports, PVC for persistence, security context, conditional on .Values.enabled and .Values.cubeStore.enabled (FR-041)
- [ ] T038 [P] [US6] Create Service templates in `charts/floe-platform/charts/cube/templates/`: service-api.yaml (ClusterIP port 4000), service-sql.yaml (ClusterIP port 15432), service-cube-store.yaml (ClusterIP port 3030) (FR-039)
- [ ] T039 [P] [US6] Create ConfigMap template in `charts/floe-platform/charts/cube/templates/configmap.yaml`: CUBEJS_DB_TYPE, CUBEJS_DEV_MODE=false, CUBEJS_CACHE_AND_QUEUE_DRIVER=cubestore, CUBEJS_CUBESTORE_HOST, CUBEJS_TELEMETRY=false, CUBEJS_LOG_LEVEL, conditional on .Values.enabled
- [ ] T040 [US6] Integrate subchart into parent chart: add cube dependency to `charts/floe-platform/Chart.yaml`, add cube.* section to `charts/floe-platform/values.yaml` (disabled by default), create `charts/floe-platform/templates/secret-cube.yaml` (CUBEJS_API_SECRET from K8s Secret), create `charts/floe-platform/templates/configmap-cube.yaml` (parent-level config), all conditional on cube.enabled (FR-042, FR-043, FR-044)
- [ ] T041 [US6] Add Cube to environment-specific values files: `charts/floe-platform/values-demo.yaml` (enabled), `charts/floe-platform/values-dev.yaml` (enabled), `charts/floe-platform/values-test.yaml` (enabled), `charts/floe-platform/values-staging.yaml` (disabled), `charts/floe-platform/values-prod.yaml` (disabled)

**Checkpoint**: Full Cube Stack deployable via Helm with enable/disable toggle

---

## Phase 9: User Story 7 - Data Engineer Queries Semantic Layer via APIs (Priority: P1)

**Goal**: API endpoint discovery for SQL, REST, and GraphQL consumption

**Independent Test**: Call get_api_endpoints() and verify returned dict contains SQL, REST, and GraphQL paths

**Requirements**: FR-035, FR-036, FR-037

> **Note**: API endpoint implementation is in T018 (Phase 4). Tests are in T012 (Phase 4). This story is covered by the CubeSemanticPlugin implementation. No additional tasks needed beyond verification.

**Checkpoint**: API endpoints verified via US2 plugin tests

---

## Phase 10: User Story 8 - Platform Operator Monitors Semantic Layer Health (Priority: P2)

**Goal**: Health check and observability integration for production monitoring

**Independent Test**: Call health_check() and verify HealthStatus with response time

**Requirements**: FR-008, FR-048, FR-049, FR-050

> **Note**: Health check implementation is in T017 (Phase 4). Tests are in T012 (unit) and T014 (integration) in Phase 4. This story is covered by existing tasks. No additional tasks needed beyond verification.

**Checkpoint**: Health monitoring verified via US2 plugin tests and integration tests

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, static analysis, coverage, and final wiring verification

- [ ] T042 Update `plugins/floe-semantic-cube/src/floe_semantic_cube/__init__.py` to export all public symbols and verify `uv pip install -e plugins/floe-semantic-cube` succeeds
- [ ] T043 [P] Run mypy --strict on `plugins/floe-semantic-cube/src/` and `plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py` -- must pass (SC-010)
- [ ] T044 [P] Run ruff check on `plugins/floe-semantic-cube/` -- must pass (SC-010)
- [ ] T045 [P] Run bandit -r on `plugins/floe-semantic-cube/src/` -- must pass (SC-010)
- [ ] T046 Run pytest `plugins/floe-semantic-cube/tests/unit/` with coverage -- must exceed 80% for floe_semantic_cube (SC-007)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on T001-T005 completion - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on T006 (ABC enhancement) only
- **US2 (Phase 4)**: Depends on T006-T009 (full foundation) and T010-T011 (US1 contracts)
- **US3 (Phase 5)**: Depends on T015 (plugin skeleton from US2)
- **US4 (Phase 6)**: Independent of other stories (modifies existing DuckDB plugin)
- **Orchestrator Wiring (Phase 6a)**: Depends on T006 (ABC enhancement) and T030 (schema gen wired to plugin); T049 also depends on T030
- **US5 (Phase 7)**: Covered by US2 tasks
- **US6 (Phase 8)**: Independent of Python code, can parallel with Phases 4-6
- **US7 (Phase 9)**: Covered by US2 tasks
- **US8 (Phase 10)**: Covered by US2 tasks
- **Polish (Phase 11)**: Depends on all previous phases

### User Story Dependencies

- **US1 (P0)**: Can start after Foundational - No dependencies on other stories
- **US2 (P0)**: Depends on US1 contracts being defined (interface must be verified)
- **US3 (P0)**: Depends on US2 plugin skeleton (sync_from_dbt_manifest wires to plugin)
- **US4 (P0)**: Independent - can run in parallel with US2/US3
- **US5 (P1)**: Covered by US2 implementation
- **US6 (P1)**: Independent - can run in parallel with all Python stories
- **US7 (P1)**: Covered by US2 implementation
- **US8 (P2)**: Covered by US2 implementation

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/config before services
- Services before wiring
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T003, T004, T005 can all run in parallel (Phase 1)
- T006 and T009 can run in parallel (Phase 2)
- T010 and T011 can run in parallel (US1 contracts)
- T012, T013, T014 can all run in parallel (US2 tests)
- T034, T035, T036, T037, T038, T039 can all run in parallel (US6 Helm templates)
- US4 (DuckDB extension) can run in parallel with US2/US3
- US6 (Helm chart) can run in parallel with all Python stories
- T047 and T049 can start in parallel once dependencies met (Phase 6a)
- T043, T044, T045 can all run in parallel (quality gates)

---

## Parallel Example: User Story 6 (Helm Chart)

```bash
# Launch all Helm template tasks in parallel:
Task: "Create Cube subchart scaffold (Chart.yaml, values.yaml, _helpers.tpl)"
Task: "Create Cube API Deployment template"
Task: "Create Cube Refresh Worker Deployment template"
Task: "Create Cube Store StatefulSet template"
Task: "Create Service templates (API, SQL, Cube Store)"
Task: "Create ConfigMap template"
```

## Parallel Example: Foundation + Independent Stories

```bash
# After foundation complete, launch in parallel:
Task: "US2 - CubeSemanticPlugin implementation"
Task: "US4 - DuckDB compute extension"
Task: "US6 - Helm chart creation"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (ABC + Config)
3. Complete Phase 3: US1 (ABC contracts)
4. Complete Phase 4: US2 (Plugin implementation)
5. Complete Phase 5: US3 (Schema generation)
6. **VALIDATE**: Plugin discoverable, schema generation works, all unit tests pass

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. US1 (ABC contracts) -> Interface verified
3. US2 (Plugin) -> Cube plugin functional, discoverable
4. US3 (Schema gen) -> dbt manifest -> Cube YAML automated
5. US4 (DuckDB) -> Compute datasource delegation wired
6. US6 (Helm) -> Full Cube Stack deployable in K8s
7. Polish -> Quality gates pass, coverage verified

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 contracts -> US2 plugin -> US3 schema generator
   - Developer B: US4 DuckDB extension (independent)
   - Developer C: US6 Helm chart (independent)
3. All converge at Polish phase

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US5, US7, US8 have no dedicated tasks because their functionality is fully covered by US2 tasks (security context, API endpoints, health check are all plugin methods)
- Helm chart (US6) is fully independent of Python code and can be built in parallel
- DuckDB extension (US4) only modifies an existing plugin file - no new package needed
- Total: 51 tasks across 12 phases (including Phase 6a: Orchestrator Wiring)
- Task IDs in this file (T001-T051) are organized by user story and do not map 1:1 to plan.md task IDs.
- T047-T051 (Orchestrator Wiring) were added by gap analysis to ensure the semantic layer plugin is properly wired into the orchestrator abstractions.
