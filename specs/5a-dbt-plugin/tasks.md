# Tasks: Epic 5A - dbt Plugin Abstraction

**Input**: Design documents from `/specs/5a-dbt-plugin/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Task Summary

| Phase | Focus | Tasks | Parallel |
|-------|-------|-------|----------|
| Setup | Project initialization | 6 | 4 |
| Foundational | Error classes, shared fixtures | 8 | 5 |
| US1+US4+US5 | DBTCorePlugin + Dagster + Artifacts | 24 | 11 |
| US2 | DBTFusionPlugin | 15 | 6 |
| US3 | SQL Linting | 10 | 4 |
| Polish | Contract tests, docs, validation | 11 | 6 |
| **Total** | | **74** | **37** |

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create plugin package scaffolding and configure dependencies

- [ ] T001 [Setup] Create `plugins/floe-dbt-core/` directory structure per plan.md
- [ ] T002 [P] [Setup] Create `plugins/floe-dbt-core/pyproject.toml` with entry point `floe.dbt = core`
- [ ] T003 [P] [Setup] Create `plugins/floe-dbt-fusion/` directory structure per plan.md
- [ ] T004 [P] [Setup] Create `plugins/floe-dbt-fusion/pyproject.toml` with entry point `floe.dbt = fusion`
- [ ] T005 [P] [Setup] Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/` directory
- [ ] T006 [Setup] Add `PluginType.DBT` to `packages/floe-core/src/floe_core/plugin_types.py` if not present

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Error classes and test fixtures that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Error Classes (FR-033, FR-034, FR-035, FR-036, FR-041)

- [ ] T007 [P] [Foundation] Create `plugins/floe-dbt-core/src/floe_dbt_core/errors.py` with DBTCompilationError, DBTExecutionError, DBTConfigurationError, DBTLintError
- [ ] T008 [P] [Foundation] Create `plugins/floe-dbt-fusion/src/floe_dbt_fusion/errors.py` with DBTFusionNotFoundError, DBTAdapterUnavailableError

### Test Fixtures

- [ ] T009 [P] [Foundation] Create `plugins/floe-dbt-core/tests/conftest.py` with shared fixtures (mock dbtRunner, temp dbt project)
- [ ] T010 [P] [Foundation] Create `plugins/floe-dbt-fusion/tests/conftest.py` with shared fixtures (mock CLI, temp dbt project)
- [ ] T011 [P] [Foundation] Create `plugins/floe-orchestrator-dagster/tests/fixtures/dbt_fixtures.py` with DBTResource test fixtures

### Shared Test dbt Project

- [ ] T012 [Foundation] Create `testing/fixtures/dbt_project/` with minimal dbt project for testing (dbt_project.yml, profiles.yml, 1 model)
- [ ] T013 [P] [Foundation] Create `testing/fixtures/dbt_project/models/example_model.sql` as simple SELECT statement
- [ ] T014 [P] [Foundation] Create `testing/fixtures/dbt_project/profiles.yml` with DuckDB target for testing

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 + 4 + 5 - DBTCorePlugin + Dagster + Artifacts (Priority: P1/P2)

**Goal**: Implement DBTCorePlugin with dbtRunner, integrate with Dagster, and provide artifact retrieval

**Why combined**: US1 (local development) and US4 (orchestrator integration) are both P1 and tightly coupled. US5 (artifacts) is P2 but shares the same codebase.

**Independent Test**: Run `floe compile && floe run` with a simple dbt project. Dagster asset materialization uses DBTPlugin.run_models() internally.

### Unit Tests for DBTCorePlugin

- [ ] T015 [P] [US1] Create `plugins/floe-dbt-core/tests/unit/test_plugin.py` with tests for compile_project, run_models, test_models
- [ ] T016 [P] [US1] Create `plugins/floe-dbt-core/tests/unit/test_artifacts.py` with tests for get_manifest, get_run_results (US5)
- [ ] T017 [P] [US1] Create `plugins/floe-dbt-core/tests/unit/test_errors.py` with tests for error handling and file/line preservation

### DBTCorePlugin Implementation

- [ ] T018 [US1] Create `plugins/floe-dbt-core/src/floe_dbt_core/__init__.py` exporting DBTCorePlugin
- [ ] T019 [US1] Implement `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` with PluginMetadata properties (name, version, floe_api_version)
- [ ] T020 [US1] Implement compile_project() using dbtRunner.invoke(["compile"]) in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-002)
- [ ] T021 [US1] Implement run_models() using dbtRunner.invoke(["run"]) with select/exclude/full_refresh in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-003)
- [ ] T022 [US1] Implement test_models() using dbtRunner.invoke(["test"]) in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-004)
- [ ] T023 [US5] Implement get_manifest() reading target/manifest.json in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-006)
- [ ] T024 [US5] Implement get_run_results() reading target/run_results.json in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-007)
- [ ] T025 [US1] Implement supports_parallel_execution() returning False in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-012)
- [ ] T026 [US1] Implement get_runtime_metadata() returning dbt version and adapter info in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-010)
- [ ] T027 [US1] Add dbtRunner callback handling for structured error capture in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-015, FR-016)
- [ ] T028 [US1] Add automatic `dbt deps` execution before compile if packages.yml exists in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-014)

### Dagster Integration (US4)

- [ ] T029 [P] [US4] Create `plugins/floe-orchestrator-dagster/tests/unit/test_dbt_resource.py` with DBTResource unit tests
- [ ] T030 [US4] Create `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/dbt_resource.py` with DBTResource ConfigurableResource (FR-037)
- [ ] T031 [US4] Implement DBTResource.get_plugin() loading from registry in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/dbt_resource.py`
- [ ] T032 [US4] Implement DBTResource.compile(), run_models(), test_models() delegating to plugin in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/dbt_resource.py`
- [ ] T033 [US4] Add DBTResource export to `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/__init__.py`
- [ ] T034 [US4] Wire DBTResource to placeholder assets in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` (FR-030, FR-031)
- [ ] T035 [US4] Add select/exclude pattern passing in asset materialization in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` (FR-032)

### OpenTelemetry Integration (NFR-006)

- [ ] T036 [P] [US1] Add OpenTelemetry span instrumentation to DBTCorePlugin methods in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py`

### Integration Tests (Kind Cluster)

- [ ] T036a [US1] Create `plugins/floe-dbt-core/tests/integration/test_dbt_core_integration.py` with real dbt execution against DuckDB
- [ ] T036b [US4] Create `plugins/floe-orchestrator-dagster/tests/integration/test_dbt_resource_integration.py` with real Dagster asset materialization

**Checkpoint**: DBTCorePlugin fully functional, Dagster integration complete, artifacts retrievable

---

## Phase 4: User Story 2 - dbt Fusion High-Performance Compilation (Priority: P2)

**Goal**: Implement DBTFusionPlugin with CLI subprocess invocation and automatic fallback

**Independent Test**: Configure `plugins.dbt_runtime: fusion` in manifest.yaml, run `floe compile` on a 100-model project. Compilation completes in <2s.

### Unit Tests for DBTFusionPlugin

- [ ] T037 [P] [US2] Create `plugins/floe-dbt-fusion/tests/unit/test_detection.py` with tests for binary detection and version parsing
- [ ] T038 [P] [US2] Create `plugins/floe-dbt-fusion/tests/unit/test_plugin.py` with tests for compile_project, run_models using mocked subprocess
- [ ] T039 [P] [US2] Create `plugins/floe-dbt-fusion/tests/unit/test_fallback.py` with tests for automatic fallback when adapters unavailable

### DBTFusionPlugin Implementation

- [ ] T040 [US2] Create `plugins/floe-dbt-fusion/src/floe_dbt_fusion/__init__.py` exporting DBTFusionPlugin
- [ ] T041 [US2] Create `plugins/floe-dbt-fusion/src/floe_dbt_fusion/detection.py` with detect_fusion_binary() and get_fusion_version() (FR-020)
- [ ] T042 [US2] Create `plugins/floe-dbt-fusion/src/floe_dbt_fusion/detection.py` with check_adapter_available() for Rust adapter detection (FR-021)
- [ ] T043 [US2] Implement `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py` with PluginMetadata properties
- [ ] T044 [US2] Implement compile_project() using subprocess.run(["dbt-sa-cli", "compile"]) in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py` (FR-017)
- [ ] T045 [US2] Implement run_models() using subprocess in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py`
- [ ] T046 [US2] Implement test_models() using subprocess in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py`
- [ ] T047 [US2] Implement supports_parallel_execution() returning True in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py` (FR-018)
- [ ] T048 [US2] Implement get_manifest() and get_run_results() (same as core, reads files) in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py`

### Automatic Fallback (FR-039, FR-040)

- [ ] T049 [US2] Create `plugins/floe-dbt-fusion/src/floe_dbt_fusion/fallback.py` with FallbackHandler class
- [ ] T050 [US2] Implement automatic fallback to DBTCorePlugin when Rust adapter unavailable in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/fallback.py`

### Integration Tests (Kind Cluster)

- [ ] T050a [US2] Create `plugins/floe-dbt-fusion/tests/integration/test_fusion_integration.py` with real Fusion CLI execution (requires Fusion binary)

**Checkpoint**: DBTFusionPlugin functional with automatic fallback to core

---

## Phase 5: User Story 3 - SQL Linting with Dialect Awareness (Priority: P3)

**Goal**: Implement SQL linting with SQLFluff (core) and built-in static analysis (Fusion)

**Independent Test**: Run `floe lint` on a project with intentional SQL anti-patterns. The linter reports issues with file locations and suggested fixes.

### Unit Tests for Linting

- [ ] T051 [P] [US3] Create `plugins/floe-dbt-core/tests/unit/test_linting.py` with SQLFluff integration tests
- [ ] T052 [P] [US3] Create `plugins/floe-dbt-fusion/tests/unit/test_linting.py` with Fusion static analysis tests

### SQLFluff Integration (DBTCorePlugin)

- [ ] T053 [US3] Create `plugins/floe-dbt-core/src/floe_dbt_core/linting.py` with SQLFluff dialect mapping (FR-013)
- [ ] T054 [US3] Implement LintViolation Pydantic model in `plugins/floe-dbt-core/src/floe_dbt_core/linting.py` (FR-025)
- [ ] T055 [US3] Implement lint_project() in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` delegating to linting.py (FR-005)
- [ ] T056 [US3] Implement supports_sql_linting() returning True in `plugins/floe-dbt-core/src/floe_dbt_core/plugin.py` (FR-009)
- [ ] T057 [US3] Add auto-fix capability to lint_project() when fix=True in `plugins/floe-dbt-core/src/floe_dbt_core/linting.py` (FR-024)

### Fusion Static Analysis (DBTFusionPlugin)

- [ ] T058 [US3] Implement lint_project() using Fusion's built-in static analysis in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py` (FR-019)
- [ ] T059 [US3] Implement supports_sql_linting() returning True in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py`
- [ ] T060 [US3] Parse Fusion static analysis output into LintResult format in `plugins/floe-dbt-fusion/src/floe_dbt_fusion/plugin.py`

**Checkpoint**: SQL linting functional for both plugins with dialect awareness

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Contract tests, documentation, and final validation

### Contract Tests (SC-003)

- [ ] T061 [P] Create `tests/contract/test_dbt_plugin_contract.py` with plugin compliance tests per contracts/dbt-plugin-api.md
- [ ] T062 [P] Add parametrized fixture loading both "core" and "fusion" plugins in `tests/contract/test_dbt_plugin_contract.py`
- [ ] T063 Add contract tests for all 10 abstract methods in `tests/contract/test_dbt_plugin_contract.py`

### Plugin Discovery (FR-026, FR-027, FR-028, FR-029)

- [ ] T064 Add `floe.dbt` entry point group handling to `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T065 Add default to "core" when `plugins.dbt_runtime` not specified in manifest.yaml (FR-028)

### Documentation & Validation

- [ ] T066 [P] Update `plugins/floe-dbt-core/README.md` with usage examples
- [ ] T067 [P] Update `plugins/floe-dbt-fusion/README.md` with installation and usage
- [ ] T068 Validate quickstart.md examples work end-to-end by running code snippets in `testing/fixtures/dbt_project/` environment

### Version Compatibility Validation (NFR-003, NFR-004)

- [ ] T069 [P] Add CI validation for dbt-core>=1.6,<2.0 version requirement in `plugins/floe-dbt-core/pyproject.toml` (NFR-003)
- [ ] T070 [P] Add CI validation for dbt Fusion 0.1+ version requirement in `plugins/floe-dbt-fusion/pyproject.toml` (NFR-004)

### Enforcement (SC-004)

- [ ] T071 Add pre-commit hook to prevent dbtRunner imports in `plugins/floe-orchestrator-dagster/` (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1+US4+US5 (Phase 3)**: Depends on Foundational - Core plugin must be first
- **US2 (Phase 4)**: Depends on Foundational, can parallel with Phase 3 after T025 (core plugin exists for fallback)
- **US3 (Phase 5)**: Depends on US1 (T019-T026 complete), can parallel with US2
- **Polish (Phase 6)**: Depends on US1, US2, US3 completion

### User Story Dependencies

- **US1 (Local Development)**: Foundation only - no other story dependencies
- **US4 (Orchestrator)**: Depends on US1 (needs DBTCorePlugin)
- **US5 (Artifacts)**: Implemented with US1 (same codebase)
- **US2 (Fusion)**: Foundation only, can use US1 for fallback
- **US3 (Linting)**: Depends on US1 and US2 plugin structure

### Within Each User Story

- Unit tests MUST be written and FAIL before implementation
- Error classes before plugin implementation
- Plugin metadata before methods
- Core methods (compile, run) before auxiliary (lint, artifacts)
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```
T002 + T003 + T004 + T005 (all different directories)
```

**Phase 2 (Foundational)**:
```
T007 + T008 (different packages)
T009 + T010 + T011 (different test directories)
T013 + T014 (different files in fixture project)
```

**Phase 3 (US1+US4+US5)**:
```
T015 + T016 + T017 (different test files)
T029 (Dagster tests) + T015-T017 (Core tests)
T036 (OTel) can parallel with T029-T035 (Dagster)
```

**Phase 4 (US2)**:
```
T037 + T038 + T039 (different test files)
```

**Phase 5 (US3)**:
```
T051 + T052 (different packages)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1+US4+US5 (DBTCorePlugin + Dagster)
4. **STOP and VALIDATE**: Test with demo dbt project
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1+US4+US5 → Local development works → Demo (MVP!)
3. Add US2 → Fusion high-performance → Demo
4. Add US3 → SQL linting → Demo
5. Polish → Contract tests, docs → Release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1+US4+US5 (DBTCorePlugin + Dagster)
   - Developer B: US2 (DBTFusionPlugin - after T028 fallback target exists)
3. US3 (Linting) after US1/US2 plugin structure complete
4. Polish phase by any available developer

---

## Notes

- DBTPlugin ABC already exists in floe-core - no changes needed
- dbt-core dbtRunner is NOT thread-safe - DBTCorePlugin.supports_parallel_execution() = False
- Fusion requires Rust adapters - automatic fallback to core when unavailable
- SQLFluff dialect is determined from profiles.yml target type
- All tests require `@pytest.mark.requirement()` markers per constitution
