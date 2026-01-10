# Tasks: Catalog Plugin

**Input**: Design documents from `/specs/001-catalog-plugin/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are REQUIRED per K8s-native testing standards. All tests use `@pytest.mark.requirement()` markers.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **floe-core ABC**: `packages/floe-core/src/floe_core/plugins/`
- **Polaris plugin**: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/`
- **Contract tests**: `tests/contract/`
- **Base test classes**: `testing/base_classes/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization for Polaris plugin package and test infrastructure

- [ ] T001 Create plugin package structure at `plugins/floe-catalog-polaris/` per plan.md
- [ ] T002 Initialize pyproject.toml with entry point `floe.catalogs = polaris` at `plugins/floe-catalog-polaris/pyproject.toml`
- [ ] T003 [P] Create `plugins/floe-catalog-polaris/src/floe_catalog_polaris/__init__.py` with package exports
- [ ] T004 [P] Create test directories at `plugins/floe-catalog-polaris/tests/unit/` and `plugins/floe-catalog-polaris/tests/integration/`
- [ ] T005 [P] Create conftest.py at `plugins/floe-catalog-polaris/tests/conftest.py` with shared fixtures

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Update CatalogPlugin ABC with credential vending signature at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T007 [P] Create plugin error types (CatalogError, NotSupportedError, ConflictError, NotFoundError, AuthenticationError, CatalogUnavailableError) at `packages/floe-core/src/floe_core/plugin_errors.py`
- [ ] T008 [P] Create Pydantic config models (OAuth2Config, PolarisCatalogConfig) at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/config.py`
- [ ] T009 [P] Create VendedCredentials Pydantic model at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py`
- [ ] T010 [P] Create HealthStatus Pydantic model at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py`
- [ ] T011 [P] Create Namespace and NamespaceProperties Pydantic models at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py`
- [ ] T012 [P] Create TableIdentifier Pydantic model at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py`
- [ ] T013 Create OTel tracing helpers at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py`
- [ ] T014 Export CatalogPlugin ABC from `packages/floe-core/src/floe_core/__init__.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Plugin Developer Implements Custom Catalog Adapter (Priority: P0) 🎯 MVP

**Goal**: Define CatalogPlugin ABC with all required methods so plugin developers can implement custom catalog adapters

**Independent Test**: A mock catalog implementation satisfies all ABC requirements and passes compliance tests

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T015 [P] [US1] Create ABC compliance test at `tests/contract/test_catalog_plugin_abc.py` for method signatures
- [ ] T016 [P] [US1] Create unit tests for ABC instantiation at `packages/floe-core/tests/unit/plugins/test_catalog_abc.py`

### Implementation for User Story 1

- [ ] T017 [US1] Add `connect()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T018 [US1] Add `create_namespace()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T019 [US1] Add `list_namespaces()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T020 [US1] Add `delete_namespace()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T021 [US1] Add `create_table()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T022 [US1] Add `list_tables()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T023 [US1] Add `drop_table()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T024 [US1] Add `vend_credentials()` abstract method to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T025 [US1] Add `health_check()` method with default implementation to CatalogPlugin ABC at `packages/floe-core/src/floe_core/plugins/catalog.py`
- [ ] T026 [US1] Create BaseCatalogPluginTests compliance test class at `testing/base_classes/base_catalog_plugin_tests.py`
- [ ] T027 [US1] Add docstrings with examples to all ABC methods at `packages/floe-core/src/floe_core/plugins/catalog.py`

**Checkpoint**: CatalogPlugin ABC is complete. Plugin developers can now implement custom adapters.

---

## Phase 4: User Story 2 - Platform Operator Uses Polaris as Default Catalog (Priority: P0) 🎯 MVP

**Goal**: Implement PolarisCatalogPlugin with OAuth2 authentication and PyIceberg integration

**Independent Test**: Connect to Polaris, authenticate via OAuth2, perform basic catalog operations

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T028 [P] [US2] Create unit tests for config validation at `plugins/floe-catalog-polaris/tests/unit/test_config.py`
- [ ] T029 [P] [US2] Create unit tests for plugin instantiation at `plugins/floe-catalog-polaris/tests/unit/test_plugin.py`
- [ ] T030 [P] [US2] Create integration test for Polaris connection at `plugins/floe-catalog-polaris/tests/integration/test_polaris_connection.py`

### Implementation for User Story 2

- [ ] T031 [US2] Implement PolarisCatalogPlugin class skeleton at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T032 [US2] Implement `connect()` method with PyIceberg REST catalog at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T033 [US2] Implement OAuth2 token management with auto-refresh at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/client.py`
- [ ] T034 [US2] Add retry logic with exponential backoff (tenacity) at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/client.py`
- [ ] T035 [US2] Implement error mapping (PyIceberg exceptions → floe errors) at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T036 [US2] Add OTel span for `connect()` operation at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T037 [US2] Add structlog logging for connection lifecycle at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T038 [US2] Register plugin via entry point in `plugins/floe-catalog-polaris/pyproject.toml`

**Checkpoint**: PolarisCatalogPlugin can connect to Polaris and authenticate. Core functionality ready.

---

## Phase 5: User Story 3 - Platform Operator Manages Namespaces (Priority: P1)

**Goal**: Implement namespace management (create, list, delete) with hierarchical support

**Independent Test**: Create namespace with properties, list namespaces, delete empty namespace

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T039 [P] [US3] Create unit tests for namespace operations at `plugins/floe-catalog-polaris/tests/unit/test_namespace.py`
- [ ] T040 [P] [US3] Create integration tests for namespace operations at `plugins/floe-catalog-polaris/tests/integration/test_namespace_operations.py`

### Implementation for User Story 3

- [ ] T041 [US3] Implement `create_namespace()` method at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T042 [US3] Implement `list_namespaces()` method with optional parent filter at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T043 [US3] Implement `delete_namespace()` method at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T044 [US3] Create namespace helper module at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/namespace.py`
- [ ] T045 [US3] Add OTel spans for all namespace operations at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T046 [US3] Handle ConflictError for existing namespaces at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T047 [US3] Handle NotFoundError for missing namespaces at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`

**Checkpoint**: Namespace management fully functional. Platform operators can organize tables.

---

## Phase 6: User Story 4 - Platform Operator Registers and Lists Tables (Priority: P1)

**Goal**: Implement table operations (create, list, drop) for Iceberg tables

**Independent Test**: Create table with schema, list tables in namespace, drop table

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T048 [P] [US4] Create unit tests for table operations at `plugins/floe-catalog-polaris/tests/unit/test_tables.py`
- [ ] T049 [P] [US4] Create integration tests for table operations at `plugins/floe-catalog-polaris/tests/integration/test_table_operations.py`

### Implementation for User Story 4

- [ ] T050 [US4] Implement `create_table()` method at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T051 [US4] Implement `list_tables()` method at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T052 [US4] Implement `drop_table()` method with purge option at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T053 [US4] Add OTel spans for all table operations at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T054 [US4] Handle ConflictError for existing tables at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T055 [US4] Handle NotFoundError for missing tables at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`

**Checkpoint**: Table operations fully functional. Platform operators can register and manage tables.

---

## Phase 7: User Story 5 - Security Engineer Configures Access Control (Priority: P1)

**Goal**: Implement credential vending using X-Iceberg-Access-Delegation pattern

**Independent Test**: Vend read credentials for table, vend write credentials, verify expiration

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T056 [P] [US5] Create unit tests for credential vending at `plugins/floe-catalog-polaris/tests/unit/test_credentials.py`
- [ ] T057 [P] [US5] Create integration tests for credential vending at `plugins/floe-catalog-polaris/tests/integration/test_credential_vending.py`

### Implementation for User Story 5

- [ ] T058 [US5] Implement `vend_credentials()` method at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T059 [US5] Create credential vending helper at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/credentials.py`
- [ ] T060 [US5] Add X-Iceberg-Access-Delegation header handling at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/client.py`
- [ ] T061 [US5] Parse vended credentials from PyIceberg table.io properties at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/credentials.py`
- [ ] T062 [US5] Add OTel span for `vend_credentials()` operation at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T063 [US5] Implement credential TTL validation (max 24 hours) at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/credentials.py`
- [ ] T064 [US5] Handle NotSupportedError for catalogs without vending at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`

**Checkpoint**: Credential vending functional. Security engineers can scope access to tables.

---

## Phase 8: User Story 6 - Platform Operator Monitors Catalog Health (Priority: P2)

**Goal**: Implement health check with response time tracking

**Independent Test**: Health check returns status, response time, and message

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T065 [P] [US6] Create unit tests for health check at `plugins/floe-catalog-polaris/tests/unit/test_health.py`
- [ ] T066 [P] [US6] Create integration tests for health check at `plugins/floe-catalog-polaris/tests/integration/test_health_check.py`

### Implementation for User Story 6

- [ ] T067 [US6] Implement `health_check()` method at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T068 [US6] Use `list_namespaces()` as lightweight health probe at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T069 [US6] Track response time in milliseconds at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T070 [US6] Add OTel span for `health_check()` operation at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`
- [ ] T071 [US6] Handle timeout parameter (max 10 seconds) at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/plugin.py`

**Checkpoint**: Health monitoring functional. Platform operators can integrate with monitoring systems.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T072 [P] Export JSON Schema for PolarisCatalogConfig at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/config.py`
- [ ] T073 [P] Add type stubs for public API at `plugins/floe-catalog-polaris/src/floe_catalog_polaris/py.typed`
- [ ] T074 [P] Run mypy --strict on all plugin code
- [ ] T075 [P] Run ruff linting and formatting
- [ ] T076 [P] Add integration test conftest with Polaris fixtures at `plugins/floe-catalog-polaris/tests/integration/conftest.py`
- [ ] T077 Validate quickstart.md examples work end-to-end
- [ ] T078 Run full test suite with requirement traceability report
- [ ] T079 [P] Security audit: verify no hardcoded credentials, all secrets use SecretStr

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 + US2 (P0): Must complete first - provide ABC and reference implementation
  - US3-US6 (P1/P2): Can proceed in parallel after US1+US2
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P0)**: Can start after Foundational (Phase 2) - Defines the ABC interface
- **User Story 2 (P0)**: Can start after US1 - Implements Polaris plugin skeleton
- **User Story 3 (P1)**: Can start after US2 - Adds namespace operations
- **User Story 4 (P1)**: Can start after US2 - Adds table operations (parallel with US3)
- **User Story 5 (P1)**: Can start after US2 - Adds credential vending (parallel with US3/US4)
- **User Story 6 (P2)**: Can start after US2 - Adds health checks (parallel with US3/US4/US5)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/config before services
- Services before plugin methods
- Core implementation before OTel instrumentation
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (T007-T012)
- All tests for a user story marked [P] can run in parallel
- US3, US4, US5, US6 can run in parallel after US2 completes

---

## Parallel Example: Foundational Phase

```bash
# Launch all model creation in parallel:
Task: "Create plugin error types at packages/floe-core/src/floe_core/plugin_errors.py"
Task: "Create Pydantic config models at plugins/floe-catalog-polaris/src/floe_catalog_polaris/config.py"
Task: "Create VendedCredentials model at plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py"
Task: "Create HealthStatus model at plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py"
Task: "Create Namespace models at plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py"
Task: "Create TableIdentifier model at plugins/floe-catalog-polaris/src/floe_catalog_polaris/models.py"
```

## Parallel Example: User Story 3-6 (After US2)

```bash
# Launch all P1/P2 stories in parallel:
Task: "Implement namespace operations (US3)"
Task: "Implement table operations (US4)"
Task: "Implement credential vending (US5)"
Task: "Implement health checks (US6)"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (ABC Definition)
4. Complete Phase 4: User Story 2 (Polaris Connection)
5. **STOP and VALIDATE**: Can connect to Polaris and authenticate
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → ABC defined → Test with mock implementation
3. Add User Story 2 → Polaris connection → Test with real Polaris (MVP!)
4. Add User Story 3 → Namespace management → Test independently
5. Add User Story 4 → Table operations → Test independently
6. Add User Story 5 → Credential vending → Test independently
7. Add User Story 6 → Health checks → Test independently
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Developer A: User Story 1 (ABC)
3. Developer B: User Story 2 (Polaris) - starts after US1
4. After US2:
   - Developer A: User Story 3 (Namespaces)
   - Developer B: User Story 4 (Tables)
   - Developer C: User Story 5 (Credentials)
   - Developer D: User Story 6 (Health)
5. Stories complete and integrate independently

---

## Task to Requirement Mapping

| Task Range | User Story | Requirements (from spec.md) |
|------------|------------|----------------------------|
| T015-T027 | US1 (ABC) | FR-001 to FR-005 |
| T028-T038 | US2 (Polaris) | FR-006 to FR-009, FR-034 to FR-036 |
| T039-T047 | US3 (Namespaces) | FR-010 to FR-013 |
| T048-T055 | US4 (Tables) | FR-014 to FR-018 |
| T056-T064 | US5 (Credentials) | FR-019 to FR-023, FR-024 to FR-027 |
| T065-T071 | US6 (Health) | FR-028 to FR-033 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All tests require `@pytest.mark.requirement()` markers per testing standards
