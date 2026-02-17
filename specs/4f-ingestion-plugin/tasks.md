# Tasks: Ingestion Plugin (dlt)

**Input**: Design documents from `/specs/4f-ingestion-plugin/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests are included using TDD approach. Write tests FIRST, ensure they FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Relationship to plan.md

This `tasks.md` file contains **implementation-level tasks** that decompose the
**high-level deliverables** in `plan.md`. The two documents serve complementary purposes:

- **plan.md**: Architecture and design view — "What to build?" (28 high-level deliverables)
- **tasks.md**: Execution and granularity view — "How to build it?" (52+ implementation tasks)

Key differences:
1. **TDD ordering**: Tests appear before their implementation (plan.md orders by phase)
2. **User story grouping**: Tasks grouped by feature for parallel work (plan.md groups by implementation phase)
3. **Test granularity**: Integration tests split per feature for independent testability
4. **Intermediate scaffolding**: Extra tasks for test fixtures, conftest files, exports

| Plan.md Phase | Plan Tasks | Tasks.md Equivalent | Tasks.md Count |
|---|---|---|---|
| Phase 0: Foundation (T001–T005) | 5 | Phase 1: Setup (T001–T007) | 7 |
| Phase 1: Core Plugin (T006–T011) | 6 | Phase 2: Foundational + Phase 3: US1 | 10 |
| Phase 2: Orchestrator (T012–T015) | 4 | Phase 6: User Story 4 (T030–T036) | 7 |
| Phase 3: Testing (T016–T028) | 13 | Phases 3–10 (integrated with stories) | 28 |
| **Total** | **28** | **Total** | **52+** |

See detailed mapping in prior research (migrated from legacy OMC research notes).

## Path Conventions

- **Plugin package**: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/`
- **Plugin tests**: `plugins/floe-ingestion-dlt/tests/`
- **Orchestrator wiring**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/`
- **Orchestrator tests**: `plugins/floe-orchestrator-dagster/tests/`
- **Shared fixtures**: `testing/fixtures/`
- **Contract tests**: `tests/contract/`

## Testing Standards and Requirements

All tests MUST follow `.claude/rules/testing-standards.md`:

**Requirement Traceability** (MANDATORY):
- Add `@pytest.mark.requirement("XXX-FR-NNN")` to EVERY test function
- Map each test to its feature requirement from spec.md
- Run `uv run python -m testing.traceability --all --threshold 100` before PR
- 100% requirement coverage required for merge

**Assertion Strength** (NON-NEGOTIABLE):
- Use strongest possible assertion: `assert value == expected` (NOT `assert value is not None`)
- See hierarchy in `.claude/rules/testing-standards.md` lines 69–79
- Never weaken assertions to make tests pass — escalate via `AskUserQuestion`

**Tests FAIL, Never Skip** (NON-NEGOTIABLE):
- `pytest.skip()` is FORBIDDEN (only `pytest.importorskip()` or platform-specific `skipif` allowed)
- Fixtures must FAIL when infrastructure is missing, not skip

**Anti-Patterns** (FORBIDDEN):
- `time.sleep()` — use `wait_for_condition()` from `testing.fixtures.services`
- `except Exception: pass` — never swallow exceptions
- Mocks in integration tests — only unit tests use mocks

**Performance Assertions** (for SC-004):
- Use `time.perf_counter()` for high-resolution timing
- Hard timeout pattern: `assert elapsed < 30.0, f"Loaded {rows} rows in {elapsed:.2f}s (limit: 30s)"`
- For variable timings: use `wait_for_condition()` with timeout

**References**: `.claude/rules/testing-standards.md`, `TESTING.md`, `.claude/rules/test-organization.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package scaffold, dependencies, and shared infrastructure modules

- [ ] T001 Create plugin package scaffold with pyproject.toml, __init__.py, and py.typed in plugins/floe-ingestion-dlt/
- [ ] T002 [P] Create DltIngestionConfig, IngestionSourceConfig, and RetryConfig Pydantic models in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py
- [ ] T003 [P] Create error type hierarchy (IngestionError, SourceConnectionError, DestinationWriteError, SchemaContractViolation, PipelineConfigurationError) and ErrorCategory enum in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/errors.py
- [ ] T004 [P] Create OTel tracing helpers (start_ingestion_span, record_ingestion_result, record_ingestion_error) in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py
- [ ] T005 Create retry logic with error categorization (categorize_error, create_retry_decorator) in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/retry.py
- [ ] T006 Create test fixtures (dlt_config, dlt_plugin, sample_ingestion_source_config, mock_dlt_source) in testing/fixtures/ingestion.py
- [ ] T007 Create conftest files for plugin test directories in plugins/floe-ingestion-dlt/tests/conftest.py, tests/unit/conftest.py, tests/integration/conftest.py

**Checkpoint**: Package installs cleanly via `uv pip install -e plugins/floe-ingestion-dlt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DltIngestionPlugin class skeleton that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Implement DltIngestionPlugin class skeleton with metadata properties (name, version, floe_api_version, is_external, get_config_schema) in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T009 Implement startup() and shutdown() lifecycle methods with OTel spans and source package validation in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T010 Implement health_check() returning HealthStatus (verify dlt importable + catalog reachable) in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T011 Update __init__.py exports (DltIngestionPlugin, DltIngestionConfig, IngestionSourceConfig) in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/__init__.py

**Checkpoint**: Foundation ready - `DltIngestionPlugin` can be instantiated, started, health-checked, and shut down. User story implementation can now begin.

---

## Phase 3: User Story 1 - Plugin Discovery and ABC Compliance (Priority: P0)

**Goal**: Plugin is discoverable via entry points and passes all plugin compliance tests (BasePluginDiscoveryTests + BaseHealthCheckTests)

**Independent Test**: `issubclass(DltIngestionPlugin, IngestionPlugin)` returns True; `BasePluginDiscoveryTests` (11 tests) and `BaseHealthCheckTests` (11 tests) all pass

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US1] Create contract test for IngestionPlugin ABC (cannot instantiate, has correct abstract methods/properties, inherits PluginMetadata) in tests/contract/test_ingestion_plugin_abc.py
- [ ] T013 [P] [US1] Create contract test for CompiledArtifacts.plugins.ingestion round-trip (PluginRef serialize/deserialize, None handling) in tests/contract/test_core_to_ingestion_contract.py
- [ ] T014 [P] [US1] Create integration test inheriting BasePluginDiscoveryTests (entry_point_group="floe.ingestion", expected_name="dlt") in plugins/floe-ingestion-dlt/tests/integration/test_discovery.py
- [ ] T015 [P] [US1] Create integration test inheriting BaseHealthCheckTests (unconnected_plugin, connected_plugin fixtures) in plugins/floe-ingestion-dlt/tests/integration/test_health_check.py

### Implementation for User Story 1

- [ ] T016 [US1] Verify entry point registration in pyproject.toml resolves correctly via PluginDiscovery.discover_all() — fix any issues found by T014
- [ ] T017 [US1] Verify health_check() returns correct HealthStatus for both HEALTHY and UNHEALTHY states — fix any issues found by T015

**Checkpoint**: US1 complete — `BasePluginDiscoveryTests` (11 tests) and `BaseHealthCheckTests` (11 tests) pass. SC-001, SC-002, SC-003 satisfied.

---

## Phase 4: User Story 2 - Create and Run Ingestion Pipeline (Priority: P0)

**Goal**: Plugin creates dlt pipelines from IngestionConfig and executes them, returning IngestionResult with metrics

**Independent Test**: `create_pipeline()` returns a dlt pipeline object; `run()` returns IngestionResult with `success=True` and `rows_loaded > 0`

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T018 [P] [US2] Create unit tests for create_pipeline() — valid config returns pipeline, invalid config raises ValidationError, missing source raises PipelineConfigurationError — in plugins/floe-ingestion-dlt/tests/unit/test_plugin.py
- [ ] T019 [P] [US2] Create unit tests for run() — successful run returns IngestionResult with metrics, failed run sets success=False with errors list, empty source returns rows_loaded=0 — in plugins/floe-ingestion-dlt/tests/unit/test_plugin.py
- [ ] T020 [P] [US2] Create unit tests for DltIngestionConfig validation — frozen model, extra fields rejected, source_type/write_mode/schema_contract validators, empty sources rejected — in plugins/floe-ingestion-dlt/tests/unit/test_config.py

### Implementation for User Story 2

- [ ] T021 [US2] Implement create_pipeline() accepting IngestionConfig, configuring dlt pipeline with pipeline_name from destination_table, destination="iceberg", dataset_name from namespace — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T022 [US2] Implement run() executing dlt pipeline, populating IngestionResult with rows_loaded, bytes_written, duration_seconds, handling empty source data (0 rows = success) — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T023 [US2] Implement get_destination_config() mapping catalog_config to dlt Iceberg destination parameters (catalog_type="rest", credentials.uri, credentials.warehouse, S3 config) — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py

**Checkpoint**: US2 complete — Pipelines can be created and executed. FR-011 to FR-018, FR-021 satisfied.

---

## Phase 5: User Story 3 - Load Data to Iceberg via Polaris (Priority: P0)

**Goal**: Data lands in Iceberg tables managed by Polaris REST catalog with correct write dispositions (append, replace, merge)

**Independent Test**: After pipeline.run(), Iceberg table scan returns correct row count for each write mode

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T024 [P] [US3] Create unit tests for get_destination_config() — Polaris catalog config maps to correct dlt Iceberg destination params, MinIO/S3 storage config supported — in plugins/floe-ingestion-dlt/tests/unit/test_plugin.py
- [ ] T025 [P] [US3] Create integration test for pipeline execution with append mode — data lands in Iceberg, row count verified via table scan, performance verified via `time.perf_counter()` with 30s hard timeout (SC-004) — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py
- [ ] T026 [P] [US3] Create integration tests for replace and merge write modes — replace overwrites, merge upserts with primary key (both delete-insert and upsert strategies per FR-025) — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py

### Implementation for User Story 3

- [ ] T027 [US3] Implement write_mode="append" support mapping to dlt write_disposition="append" in run() — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T028 [US3] Implement write_mode="replace" support mapping to dlt write_disposition="replace" in run() — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T029 [US3] Implement write_mode="merge" support with primary_key mapping to dlt write_disposition="merge" in run() — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py

**Checkpoint**: US3 complete — Data lands in Iceberg with all 3 write modes. SC-004, SC-005 satisfied. FR-019 to FR-030 satisfied.

---

## Phase 6: User Story 4 - Orchestrator Integration (Priority: P1)

**Goal**: Orchestrator plugin loads ingestion plugin as a resource, creates execution units per dlt resource, and supports graceful degradation when ingestion is not configured

**Independent Test**: `try_create_ingestion_resources()` with valid PluginRef returns dict with "dlt" key; returns `{}` when plugins.ingestion is None

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T030 [P] [US4] Create unit tests for try_create_ingestion_resources() — valid PluginRef returns resources, None plugins returns empty dict, None ingestion returns empty dict — in plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_resources.py
- [ ] T031 [P] [US4] Create unit tests for FloeIngestionTranslator — correct asset key naming (ingestion__{source}__{resource}), metadata includes source_type and destination_table — in plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py
- [ ] T032 [P] [US4] Create integration test for orchestrator wiring chain — CompiledArtifacts with ingestion configured results in Definitions with "dlt" resource, graceful degradation without ingestion — in plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py

### Implementation for User Story 4

- [ ] T033 [US4] Create ingestion resource factory (create_ingestion_resources, try_create_ingestion_resources) following Epic 4E pattern in plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py
- [ ] T034 [US4] Create FloeIngestionTranslator(DagsterDltTranslator) and create_ingestion_assets() factory in plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py
- [ ] T035 [US4] Wire ingestion resources into create_definitions() — call _create_ingestion_resources(), merge resources, create ingestion assets if "dlt" resource present — in plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py
- [ ] T036 [US4] Add dagster-dlt>=0.25.0 to orchestrator plugin dependencies in plugins/floe-orchestrator-dagster/pyproject.toml

**Checkpoint**: US4 complete — Orchestrator creates ingestion resources and assets from CompiledArtifacts. FR-059 to FR-066 satisfied.

---

## Phase 7: User Story 5 - Schema Contract Enforcement (Priority: P1)

**Goal**: Pipeline enforces schema contracts (evolve, freeze, discard_value) controlling how source schema changes are handled

**Independent Test**: With schema_contract="freeze", pipeline raises SchemaContractViolation when source schema changes; with "evolve", Iceberg table schema gains new column

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T037 [P] [US5] Create integration test for schema_contract="evolve" — new source column is added to Iceberg table schema — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py
- [ ] T038 [P] [US5] Create integration test for schema_contract="freeze" — new source column raises SchemaContractViolation — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py
- [ ] T039 [P] [US5] Create integration test for schema_contract="discard_value" — non-conforming column values discarded, existing schema preserved — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py
- [ ] T039a [P] [US5] Create integration test for column removal preservation (FR-037) — remove a column from source data, verify Iceberg table retains the column (additive-only schema evolution) — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py

### Implementation for User Story 5

- [ ] T040 [US5] Implement schema contract mapping from IngestionConfig.schema_contract to dlt schema_contract parameter in run() — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T041 [US5] Implement SchemaContractViolation error raising when freeze contract is violated, with structured logging at ERROR level — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py

**Checkpoint**: US5 complete — All 3 schema contracts behave correctly. SC-006 satisfied. FR-031 to FR-037 satisfied.

---

## Phase 8: User Story 6 - Incremental Loading (Priority: P1)

**Goal**: Pipeline supports cursor-based incremental loading via dlt, loading only new/changed data on subsequent runs

**Independent Test**: Run pipeline twice; second run loads only new records (row count comparison)

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T042 [P] [US6] Create integration test for incremental loading — run twice with cursor_field, second run loads only new records, rows_loaded reflects incremental count — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py
- [ ] T043 [P] [US6] Create integration test for incremental merge with primary_key — records with existing keys are upserted on second run — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py

### Implementation for User Story 6

- [ ] T044 [US6] Implement cursor_field support in create_pipeline() mapping to dlt.sources.incremental() with pipeline_name-based state isolation — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T045 [US6] Implement primary_key support for merge write mode mapping to dlt resource primary_key parameter — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py

**Checkpoint**: US6 complete — Incremental loading works with cursor-based state managed by dlt. SC-007 satisfied. FR-038 to FR-043 satisfied.

---

## Phase 9: User Story 7 - Observability (Priority: P2)

**Goal**: Plugin emits OTel spans and structured logs for all pipeline operations

**Independent Test**: Run pipeline with OTel tracing enabled; verify spans contain required attributes (rows_loaded, source_type, duration_seconds)

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T046 [P] [US7] Create unit tests for OTel span emission — create_pipeline, run, get_destination_config emit spans with correct attributes — in plugins/floe-ingestion-dlt/tests/unit/test_plugin.py
- [ ] T047 [P] [US7] Create unit tests for structured logging — pipeline operations log pipeline_id, source_type, status; secrets are NOT logged — in plugins/floe-ingestion-dlt/tests/unit/test_plugin.py

### Implementation for User Story 7

- [ ] T048 [US7] Wire OTel tracing helpers into all plugin methods (create_pipeline, run, get_destination_config, startup, shutdown, health_check) — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T049 [US7] Add structlog logging to all plugin operations with bound context (pipeline_id, source_type, destination_table) and secret masking — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py

**Checkpoint**: US7 complete — OTel spans and structured logs emitted for all operations. SC-011 satisfied. FR-044 to FR-050 satisfied.

---

## Phase 10: User Story 8 - Error Handling with Retry (Priority: P2)

**Goal**: Transient errors are retried with exponential backoff; permanent errors fail immediately; all errors carry pipeline context

**Independent Test**: Inject transient error (network timeout) — retried up to max_retries; inject permanent error (auth failure) — fails immediately without retry

### Tests for User Story 8

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T050 [P] [US8] Create unit tests for error hierarchy — each error inherits from IngestionError, carries context (source_type, destination_table, pipeline_name), correct default categories — in plugins/floe-ingestion-dlt/tests/unit/test_errors.py
- [ ] T051 [P] [US8] Create unit tests for retry logic — TRANSIENT errors retried up to max_retries, PERMANENT errors fail immediately, exponential backoff timing, create_retry_decorator respects RetryConfig — in plugins/floe-ingestion-dlt/tests/unit/test_retry.py
- [ ] T052 [P] [US8] Create unit tests for error categorization — categorize_error maps PipelineStepFailed with network error to TRANSIENT, auth error to PERMANENT, ValidationError to CONFIGURATION — in plugins/floe-ingestion-dlt/tests/unit/test_retry.py
- [ ] T053 [P] [US8] Create integration test for error handling — source connection failure raises SourceConnectionError, Iceberg write failure during run returns IngestionResult with success=False — in plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py

### Implementation for User Story 8

- [ ] T054 [US8] Wire retry decorator into run() method using create_retry_decorator with RetryConfig from DltIngestionConfig — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py
- [ ] T055 [US8] Wire error categorization into run() — catch dlt PipelineStepFailed, categorize, wrap in appropriate IngestionError subclass with context, populate IngestionResult.errors — in plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py

**Checkpoint**: US8 complete — Transient errors retried, permanent errors fail fast, all errors carry context. SC-012 satisfied. FR-051 to FR-058 satisfied.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, static analysis, coverage verification

- [ ] T056 Run mypy --strict on plugins/floe-ingestion-dlt/src/ — must pass with zero errors
- [ ] T057 [P] Run ruff check on plugins/floe-ingestion-dlt/ — must pass with zero errors
- [ ] T058 [P] Run bandit -r on plugins/floe-ingestion-dlt/src/ — must pass with zero security issues
- [ ] T059 Run pytest plugins/floe-ingestion-dlt/tests/unit/ --cov=floe_ingestion_dlt --cov-report=term-missing — coverage must exceed 80%
- [ ] T060 Verify uv pip install -e plugins/floe-ingestion-dlt succeeds and all unit tests pass
- [ ] T061 Run quickstart.md validation — verify code examples in specs/4f-ingestion-plugin/quickstart.md are syntactically correct

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — contract tests + discovery/health tests
- **User Story 2 (Phase 4)**: Depends on Foundational — core pipeline creation + execution
- **User Story 3 (Phase 5)**: Depends on US2 — write modes require working pipeline
- **User Story 4 (Phase 6)**: Depends on Foundational — orchestrator wiring (independent of US2/US3)
- **User Story 5 (Phase 7)**: Depends on US2 — schema contracts applied during run()
- **User Story 6 (Phase 8)**: Depends on US2 — incremental loading applied during create_pipeline()/run()
- **User Story 7 (Phase 9)**: Depends on Foundational — OTel spans added to existing methods
- **User Story 8 (Phase 10)**: Depends on Foundational — retry wired into existing methods
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P0)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **US2 (P0)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **US3 (P0)**: Depends on US2 (needs working create_pipeline + run)
- **US4 (P1)**: Can start after Foundational (Phase 2) — Independent of US2/US3 (orchestrator wiring)
- **US5 (P1)**: Depends on US2 (needs working pipeline to test schema contracts)
- **US6 (P1)**: Depends on US2 (needs working pipeline to test incremental loading)
- **US7 (P2)**: Can start after Foundational for lifecycle methods; pipeline method wiring (create_pipeline, run, get_destination_config) requires US2 completion
- **US8 (P2)**: Can start after Foundational — Error handling is additive

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation tasks may depend on each other within a story
- Story complete before moving to next priority

### Parallel Opportunities

**Maximum parallelism after Phase 2 completes:**
- US1, US2, US4, US7, US8 can all start simultaneously (all independent of each other)
- US3, US5, US6 must wait for US2 completion
- All test tasks within a story marked [P] can run in parallel

---

## Parallel Example: After Phase 2 Completes

```bash
# Launch these user stories simultaneously:
# Worker A: US1 (Discovery + Compliance)
Task: "T012 Contract test for IngestionPlugin ABC in tests/contract/test_ingestion_plugin_abc.py"
Task: "T014 Integration test inheriting BasePluginDiscoveryTests"

# Worker B: US2 (Core Pipeline)
Task: "T018 Unit tests for create_pipeline()"
Task: "T019 Unit tests for run()"
Task: "T020 Unit tests for DltIngestionConfig validation"

# Worker C: US4 (Orchestrator Wiring)
Task: "T030 Unit tests for try_create_ingestion_resources()"
Task: "T031 Unit tests for FloeIngestionTranslator"

# Worker D: US7+US8 (Observability + Error Handling)
Task: "T046 Unit tests for OTel span emission"
Task: "T050 Unit tests for error hierarchy"
Task: "T051 Unit tests for retry logic"
```

---

## Implementation Strategy

### MVP First (User Stories 1-3)

1. Complete Phase 1: Setup (package scaffold)
2. Complete Phase 2: Foundational (plugin skeleton)
3. Complete Phase 3: US1 (discovery + compliance — validates foundation)
4. Complete Phase 4: US2 (create_pipeline + run — core value)
5. Complete Phase 5: US3 (write modes + Iceberg — data lands)
6. **STOP and VALIDATE**: MVP functional — data flows from source to Iceberg

### Incremental Delivery

1. Setup + Foundational → Plugin installs and starts
2. Add US1 → Plugin discoverable by platform (SC-001, SC-002, SC-003)
3. Add US2 → Pipelines can be created and run (core value)
4. Add US3 → Data lands in Iceberg with write modes (SC-004, SC-005)
5. Add US4 → Orchestrator creates assets from ingestion config (FR-059-FR-066)
6. Add US5 → Schema contracts protect data quality (SC-006)
7. Add US6 → Incremental loading for efficiency (SC-007)
8. Add US7 → OTel spans for observability (SC-011)
9. Add US8 → Retry logic for reliability (SC-012)
10. Polish → Quality gates pass (SC-009, SC-010)

### Parallel Team Strategy

With 4 workers after Phase 2:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Worker A: US1 (Discovery) → US3 (Write Modes)
   - Worker B: US2 (Core Pipeline) → US5 (Schema Contracts) → US6 (Incremental)
   - Worker C: US4 (Orchestrator Wiring)
   - Worker D: US7 (Observability) → US8 (Error Handling)
3. All converge for Phase 11: Polish

---

## Requirement Traceability

| User Story | Requirements | Success Criteria | Tasks |
|-----------|-------------|-----------------|-------|
| US1 | FR-001 to FR-010, FR-074 to FR-079 | SC-001, SC-002, SC-003 | T012-T017 |
| Contract | SC-008 round-trip validation | SC-008 | T013 |
| US2 | FR-011 to FR-018, FR-021, FR-067 to FR-073 | SC-004 (partial) | T018-T023 |
| US3 | FR-019, FR-020, FR-022 to FR-030 | SC-004, SC-005 | T024-T029 |
| US4 | FR-059 to FR-066 | SC-003 (E2E) | T030-T036 |
| US5 | FR-031 to FR-037 | SC-006 | T037-T041 |
| US6 | FR-038 to FR-043 | SC-007 | T042-T045 |
| US7 | FR-044 to FR-050 | SC-011 | T046-T049 |
| US8 | FR-051 to FR-058 | SC-012 | T050-T055 |
| Polish | — | SC-009, SC-010 | T056-T061 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All `@pytest.mark.requirement()` markers must map to FR-xxx identifiers
- Integration tests require K8s Kind cluster with Polaris + MinIO
- Data landing verification (plan.md `test_iceberg_load.py`) is absorbed into `test_pipeline.py` integration tests (T025-T026, T037-T039)
- T039a added for FR-037 (column removal preservation) — not in original plan.md but required by spec
- Infrastructure/setup phases (1, 2, 11) intentionally omit `[Story]` labels as they are cross-cutting
