# Tasks: Plugin Registry Foundation

**Input**: Design documents from `/specs/001-plugin-registry/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Convention

Based on plan.md, this is a **single package** structure:
- Source: `packages/floe-core/src/floe_core/`
- Tests: `packages/floe-core/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create package directory structure: `packages/floe-core/src/floe_core/` and `packages/floe-core/tests/`
- [ ] T002 Create `packages/floe-core/pyproject.toml` with dependencies (pydantic>=2.0, structlog)
- [ ] T003 [P] Create `packages/floe-core/src/floe_core/__init__.py` with package exports
- [ ] T004 [P] Create `packages/floe-core/tests/conftest.py` with shared pytest fixtures
- [ ] T005 [P] Create `packages/floe-core/tests/unit/conftest.py` with unit test fixtures

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create `packages/floe-core/src/floe_core/plugin_types.py` with PluginType enum (11 types with entry point groups)
- [ ] T007 [P] Create `packages/floe-core/src/floe_core/plugin_errors.py` with exception hierarchy (PluginError, PluginNotFoundError, PluginIncompatibleError, PluginConfigurationError, DuplicatePluginError, CircularDependencyError)
- [ ] T008 [P] Create `packages/floe-core/src/floe_core/version_compat.py` with FLOE_PLUGIN_API_VERSION constant and is_compatible() function
- [ ] T009 Create HealthState enum and HealthStatus dataclass in `packages/floe-core/src/floe_core/plugin_metadata.py`
- [ ] T010 Create PluginMetadata base ABC in `packages/floe-core/src/floe_core/plugin_metadata.py` with abstract properties (name, version, floe_api_version) and default methods (get_config_schema, health_check, startup, shutdown, dependencies)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Plugin Discovery (Priority: P0) 🎯 MVP

**Goal**: Plugins are automatically discoverable when installed via entry points

**Independent Test**: Install a test plugin package and verify the registry finds it at startup

**Requirements Covered**: FR-001, FR-010, FR-011, SC-001, SC-005

### Implementation for User Story 1

- [ ] T011 [US1] Create PluginRegistry class skeleton in `packages/floe-core/src/floe_core/plugin_registry.py` with _discovered and _loaded dicts
- [ ] T012 [US1] Implement discover_all() method in `packages/floe-core/src/floe_core/plugin_registry.py` scanning all 11 entry point groups
- [ ] T013 [US1] Add error logging for malformed entry points (graceful degradation) in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T014 [US1] Implement get_registry() singleton function with thread-safe initialization in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T015 [US1] Add _reset_registry() function for testing in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T016 [P] [US1] Create unit tests for discovery in `packages/floe-core/tests/unit/test_plugin_registry.py` (mock entry_points)
- [ ] T017 [P] [US1] Create unit tests for graceful error handling in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Plugin discovery works - plugins found via entry points, errors logged but don't crash

---

## Phase 4: User Story 2 - Plugin Registration and Lookup (Priority: P1)

**Goal**: Central registry for registering and looking up plugins by type and name

**Independent Test**: Register mock plugins and retrieve them by type and name

**Requirements Covered**: FR-002, FR-009, FR-011, SC-002

### Implementation for User Story 2

- [ ] T018 [US2] Implement register() method with version compatibility check in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T019 [US2] Implement get() method with lazy loading in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T020 [US2] Implement list() method returning plugins by type in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T021 [US2] Implement list_all() method returning all plugins grouped by type in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T022 [US2] Add duplicate registration detection raising DuplicatePluginError in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T023 [US2] Add PluginNotFoundError handling for get() in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T024 [P] [US2] Create unit tests for register/get/list in `packages/floe-core/tests/unit/test_plugin_registry.py`
- [ ] T025 [P] [US2] Create unit tests for duplicate registration in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Plugin registration and lookup work - can register, retrieve by type+name, list all plugins

---

## Phase 5: User Story 3 - Version Compatibility Checking (Priority: P1)

**Goal**: Incompatible plugins are rejected at startup to prevent API mismatches

**Independent Test**: Attempt to register plugins with various version specifications and verify compatibility rules

**Requirements Covered**: FR-003, FR-004, FR-005, SC-004

### Implementation for User Story 3

- [ ] T026 [US3] Implement semver parsing in `packages/floe-core/src/floe_core/version_compat.py`
- [ ] T027 [US3] Implement is_compatible() with major version check and minor version backward compatibility in `packages/floe-core/src/floe_core/version_compat.py`
- [ ] T028 [US3] Integrate version check into register() and get() in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T029 [US3] Add PluginIncompatibleError with clear error message including versions in `packages/floe-core/src/floe_core/plugin_errors.py`
- [ ] T030 [P] [US3] Create unit tests for version compatibility in `packages/floe-core/tests/unit/test_version_compat.py`
- [ ] T031 [P] [US3] Create unit tests for incompatible plugin rejection in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Version compatibility enforced - incompatible plugins rejected with clear error messages

---

## Phase 6: User Story 4 - Plugin Configuration Validation (Priority: P2)

**Goal**: Plugin configuration is validated at startup using Pydantic schemas

**Independent Test**: Provide valid and invalid configurations and verify validation behavior

**Requirements Covered**: FR-006, FR-007, FR-008, SC-003

### Implementation for User Story 4

- [ ] T032 [US4] Implement configure() method in `packages/floe-core/src/floe_core/plugin_registry.py` calling plugin's get_config_schema()
- [ ] T033 [US4] Add Pydantic validation with field-level error extraction in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T034 [US4] Implement PluginConfigurationError with validation_errors list in `packages/floe-core/src/floe_core/plugin_errors.py`
- [ ] T035 [US4] Add _configs dict to store validated configurations in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T036 [US4] Add get_config() method to retrieve stored config in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T037 [P] [US4] Create unit tests for config validation in `packages/floe-core/tests/unit/test_plugin_registry.py`
- [ ] T038 [P] [US4] Create unit tests for validation error messages in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Configuration validation works - configs validated with clear error messages, defaults applied

---

## Phase 7: User Story 5 - Plugin Lifecycle Hooks (Priority: P3)

**Goal**: Plugins can have startup and shutdown hooks for initialization and cleanup

**Independent Test**: Register plugins with lifecycle hooks and verify they are called at appropriate times

**Requirements Covered**: FR-013, SC-006

### Implementation for User Story 5

- [ ] T039 [US5] Add startup() abstract method with default implementation to PluginMetadata in `packages/floe-core/src/floe_core/plugin_metadata.py`
- [ ] T040 [US5] Add shutdown() abstract method with default implementation to PluginMetadata in `packages/floe-core/src/floe_core/plugin_metadata.py`
- [ ] T041 [US5] Implement activate_plugin() in registry that calls startup() in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T042 [US5] Implement shutdown_all() in registry that calls shutdown() on loaded plugins in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T043 [US5] Add timeout handling (30s default) for lifecycle hooks in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T044 [US5] Add error handling for failed startup hooks (log and report) in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T045 [P] [US5] Create unit tests for lifecycle hooks in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Lifecycle hooks work - startup/shutdown called, errors handled gracefully

---

## Phase 8: User Story 6 - Plugin Health Checks (Priority: P3)

**Goal**: Plugin health can be checked for production monitoring

**Independent Test**: Call health check on plugins and verify appropriate responses

**Requirements Covered**: FR-014, SC-007

### Implementation for User Story 6

- [ ] T046 [US6] Ensure health_check() default implementation returns HEALTHY in `packages/floe-core/src/floe_core/plugin_metadata.py`
- [ ] T047 [US6] Implement health_check_all() in registry in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T048 [US6] Add timeout handling (5s) for health checks in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T049 [US6] Add exception handling returning UNHEALTHY status in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T050 [P] [US6] Create unit tests for health checks in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Health checks work - default healthy response, custom checks supported, timeout enforced

---

## Phase 9: User Story 7 - Plugin Dependency Resolution (Priority: P4)

**Goal**: Plugin dependencies are resolved and loaded in correct order

**Independent Test**: Register plugins with dependencies and verify load order

**Requirements Covered**: FR-015, FR-016, SC-008

### Implementation for User Story 7

- [ ] T051 [US7] Add dependencies property to PluginMetadata in `packages/floe-core/src/floe_core/plugin_metadata.py`
- [ ] T052 [US7] Implement resolve_dependencies() with Kahn's algorithm in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T053 [US7] Add circular dependency detection raising CircularDependencyError in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T054 [US7] Add missing dependency detection with clear error message in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T055 [US7] Integrate dependency resolution into plugin loading in `packages/floe-core/src/floe_core/plugin_registry.py`
- [ ] T056 [P] [US7] Create unit tests for dependency resolution in `packages/floe-core/tests/unit/test_plugin_registry.py`
- [ ] T057 [P] [US7] Create unit tests for circular dependency detection in `packages/floe-core/tests/unit/test_plugin_registry.py`

**Checkpoint**: Dependency resolution works - correct load order, circular deps detected, missing deps reported

---

## Phase 10: Plugin Type ABCs (Supporting Infrastructure)

**Purpose**: Create the 11 plugin type ABCs that inherit from PluginMetadata

**Note**: These are stub ABCs with method signatures only - full implementation is in plugin packages

- [ ] T058 [P] Create ComputePlugin ABC in `packages/floe-core/src/floe_core/plugins/compute.py`
- [ ] T059 [P] Create OrchestratorPlugin ABC in `packages/floe-core/src/floe_core/plugins/orchestrator.py`
- [ ] T060 [P] Create CatalogPlugin ABC in `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T061 [P] Create StoragePlugin ABC in `packages/floe-core/src/floe_core/plugins/storage.py`
- [ ] T062 [P] Create TelemetryBackendPlugin ABC in `packages/floe-core/src/floe_core/plugins/telemetry.py`
- [ ] T063 [P] Create LineageBackendPlugin ABC in `packages/floe-core/src/floe_core/plugins/lineage.py`
- [ ] T064 [P] Create DBTPlugin ABC in `packages/floe-core/src/floe_core/plugins/dbt.py`
- [ ] T065 [P] Create SemanticLayerPlugin ABC in `packages/floe-core/src/floe_core/plugins/semantic.py`
- [ ] T066 [P] Create IngestionPlugin ABC in `packages/floe-core/src/floe_core/plugins/ingestion.py`
- [ ] T067 [P] Create SecretsPlugin ABC in `packages/floe-core/src/floe_core/plugins/secrets.py`
- [ ] T068 [P] Create IdentityPlugin ABC in `packages/floe-core/src/floe_core/plugins/identity.py`
- [ ] T069 Create `packages/floe-core/src/floe_core/plugins/__init__.py` exporting all plugin ABCs

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T070 [P] Create contract test for PluginMetadata ABC stability in `packages/floe-core/tests/contract/test_plugin_abc_contract.py`
- [ ] T071 [P] Create contract test for PluginType enum stability in `packages/floe-core/tests/contract/test_plugin_abc_contract.py`
- [ ] T072 Update `packages/floe-core/src/floe_core/__init__.py` with all public exports
- [ ] T073 Add type hints and run mypy --strict on all modules
- [ ] T074 Add docstrings to all public classes and methods (Google style)
- [ ] T075 [P] Create root-level contract test in `tests/contract/test_plugin_abc_contract.py`
- [ ] T076 Run quickstart.md validation - verify all examples work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1 (Discovery): Can start after Foundational
  - US2 (Registration): Can start after Foundational, but builds on US1
  - US3 (Versioning): Can start after Foundational
  - US4 (Configuration): Can start after Foundational
  - US5 (Lifecycle): Can start after Foundational
  - US6 (Health): Can start after Foundational
  - US7 (Dependencies): Can start after Foundational
- **Plugin ABCs (Phase 10)**: Depends on Foundational (PluginMetadata must exist)
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Depends On | Notes |
|-------|------------|-------|
| US1 (Discovery) | Foundational | No dependencies on other stories |
| US2 (Registration) | US1 | Uses discovered entry points |
| US3 (Versioning) | US2 | Integrates into register() |
| US4 (Configuration) | US2 | Uses registered plugins |
| US5 (Lifecycle) | US2 | Calls hooks on loaded plugins |
| US6 (Health) | US2 | Checks health of loaded plugins |
| US7 (Dependencies) | US2 | Reorders plugin loading |

### Parallel Opportunities

**Within Setup (Phase 1)**:
- T003, T004, T005 can run in parallel

**Within Foundational (Phase 2)**:
- T007, T008 can run in parallel (different files)
- T009, T010 are sequential (same file)

**Within User Stories**:
- Tests (T016-T017, T024-T025, etc.) can run in parallel with each other
- Implementation tasks are mostly sequential within a story

**Across User Stories** (after US2 complete):
- US3, US4, US5, US6, US7 can all run in parallel if team capacity allows

**Phase 10 (Plugin ABCs)**:
- ALL tasks T058-T068 can run in parallel (different files)

---

## Parallel Example: Phase 10 (Plugin ABCs)

```bash
# All 11 plugin ABC files can be created in parallel:
Task: "Create ComputePlugin ABC in packages/floe-core/src/floe_core/plugins/compute.py"
Task: "Create OrchestratorPlugin ABC in packages/floe-core/src/floe_core/plugins/orchestrator.py"
Task: "Create CatalogPlugin ABC in packages/floe-core/src/floe_core/plugins/catalog.py"
Task: "Create StoragePlugin ABC in packages/floe-core/src/floe_core/plugins/storage.py"
Task: "Create TelemetryBackendPlugin ABC in packages/floe-core/src/floe_core/plugins/telemetry.py"
Task: "Create LineageBackendPlugin ABC in packages/floe-core/src/floe_core/plugins/lineage.py"
Task: "Create DBTPlugin ABC in packages/floe-core/src/floe_core/plugins/dbt.py"
Task: "Create SemanticLayerPlugin ABC in packages/floe-core/src/floe_core/plugins/semantic.py"
Task: "Create IngestionPlugin ABC in packages/floe-core/src/floe_core/plugins/ingestion.py"
Task: "Create SecretsPlugin ABC in packages/floe-core/src/floe_core/plugins/secrets.py"
Task: "Create IdentityPlugin ABC in packages/floe-core/src/floe_core/plugins/identity.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Discovery)
4. **STOP and VALIDATE**: Test plugin discovery independently
5. Deploy/demo if ready - plugins can be discovered!

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Discovery) → Plugins discovered (MVP!)
3. Add US2 (Registration) → Plugins accessible by type+name
4. Add US3 (Versioning) → Incompatible plugins rejected
5. Add US4 (Configuration) → Plugin configs validated
6. Add US5 (Lifecycle) → Startup/shutdown hooks work
7. Add US6 (Health) → Health checks available
8. Add US7 (Dependencies) → Complex plugin graphs supported
9. Add Phase 10 (ABCs) → All 11 plugin types defined
10. Polish → Contract tests, docs, type safety

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 → US2 (serial dependency)
   - Developer B: Phase 10 (Plugin ABCs) - independent
3. After US2 complete:
   - Developer A: US3 + US4
   - Developer B: US5 + US6
   - Developer C: US7
4. Everyone: Polish phase

---

## Summary

| Phase | Tasks | Parallel Tasks | Story |
|-------|-------|----------------|-------|
| Setup | 5 | 3 | - |
| Foundational | 5 | 2 | - |
| US1 Discovery | 7 | 2 | P0 |
| US2 Registration | 8 | 2 | P1 |
| US3 Versioning | 6 | 2 | P1 |
| US4 Configuration | 7 | 2 | P2 |
| US5 Lifecycle | 7 | 1 | P3 |
| US6 Health | 5 | 1 | P3 |
| US7 Dependencies | 7 | 2 | P4 |
| Plugin ABCs | 12 | 11 | - |
| Polish | 7 | 3 | - |
| **Total** | **76** | **31** | - |

**MVP Scope**: Setup + Foundational + US1 = **17 tasks**

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Contract tests (Phase 11) ensure ABC stability across versions
