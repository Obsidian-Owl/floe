# Tasks: IcebergTableManager (Epic 4D)

**Input**: Design documents from `/specs/4d-storage-plugin/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

**Package**: `packages/floe-iceberg/`
- Source: `packages/floe-iceberg/src/floe_iceberg/`
- Tests: `packages/floe-iceberg/tests/`
- Contract tests: `tests/contract/` (ROOT level)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package initialization and project structure

- [ ] T001 Create package structure `packages/floe-iceberg/src/floe_iceberg/__init__.py` with public exports
- [ ] T002 Create `packages/floe-iceberg/pyproject.toml` with dependencies (pyiceberg>=0.9.0 for upsert support, pydantic>=2.0, structlog, opentelemetry-api>=1.20.0, pyarrow)
- [ ] T003 [P] Create test structure `packages/floe-iceberg/tests/conftest.py` with shared fixtures (mock CatalogPlugin, mock StoragePlugin)
- [ ] T004 [P] Create `packages/floe-iceberg/tests/unit/` directory structure

**Checkpoint**: Package structure ready for development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### Error Types (All Stories Depend On)

- [ ] T005 [P] Create `packages/floe-iceberg/src/floe_iceberg/errors.py` with base IcebergError and all exception types (TableAlreadyExistsError, NoSuchTableError, NoSuchNamespaceError, SchemaEvolutionError, WriteError, CommitConflictError, SnapshotNotFoundError, RollbackError, CompactionError, ValidationError)
- [ ] T006 [P] Write unit tests for error types in `packages/floe-iceberg/tests/unit/test_errors.py`

### Enumeration Types (All Stories Depend On)

- [ ] T007 [P] Create enums (FieldType, PartitionTransform, SchemaChangeType, WriteMode, CommitStrategy, OperationType, CompactionStrategyType) in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T007a [P] Define IDENTIFIER_PATTERN constant in `packages/floe-iceberg/src/floe_iceberg/models.py` for SonarQube S1192 compliance
- [ ] T008 [P] Write unit tests for enums in `packages/floe-iceberg/tests/unit/test_models.py`

### Configuration Models (Manager Depends On)

- [ ] T009 Implement IcebergTableManagerConfig model in `packages/floe-iceberg/src/floe_iceberg/models.py` per data-model.md
- [ ] T010 Write unit tests for IcebergTableManagerConfig validation in `packages/floe-iceberg/tests/unit/test_models.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Platform Provides IcebergTableManager Utility (Priority: P0)

**Goal**: Provide internal utility class that wraps PyIceberg table operations

**Independent Test**: Use IcebergTableManager with mock catalog, verify all operations work without external dependencies

**Requirements**: FR-001, FR-004, FR-008, FR-009, FR-010, FR-011

### Tests for User Story 1

- [ ] T011 [P] [US1] Write contract test validating IcebergTableManager accepts CatalogPlugin/StoragePlugin interfaces in `tests/contract/test_floe_iceberg_contract.py`
- [ ] T012 [P] [US1] Write unit tests for IcebergTableManager.__init__ with mock plugins in `packages/floe-iceberg/tests/unit/test_manager.py`

### Implementation for User Story 1

- [ ] T013 [US1] Create IcebergTableManager class skeleton with __init__ accepting CatalogPlugin, StoragePlugin, and optional config in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T014 [US1] Implement catalog connection via CatalogPlugin.connect() in IcebergTableManager.__init__
- [ ] T015 [US1] Implement FileIO retrieval via StoragePlugin.get_pyiceberg_fileio() in IcebergTableManager.__init__
- [ ] T016 [US1] Add structured logging with structlog in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T017 [US1] Export IcebergTableManager from `packages/floe-iceberg/src/floe_iceberg/__init__.py`

**Checkpoint**: IcebergTableManager can be instantiated with mock plugins and validates dependency injection

---

## Phase 4: User Story 2 - Data Engineer Creates and Manages Iceberg Tables (Priority: P0)

**Goal**: Enable table creation with schema definition, partitioning, and catalog registration

**Independent Test**: Create Iceberg table with defined schema, verify table exists in catalog with correct metadata

**Requirements**: FR-001, FR-012, FR-013, FR-014, FR-015, FR-016

### Models for User Story 2

- [ ] T018 [P] [US2] Implement SchemaField model in `packages/floe-iceberg/src/floe_iceberg/models.py` per data-model.md
- [ ] T019 [P] [US2] Implement TableSchema model with to_pyiceberg_schema() method in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T020 [P] [US2] Implement PartitionField model in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T021 [P] [US2] Implement PartitionSpec model with to_pyiceberg_spec() method in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T022 [US2] Implement TableConfig model with identifier property in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T023 [P] [US2] Write unit tests for schema/partition models in `packages/floe-iceberg/tests/unit/test_models.py`

### Tests for User Story 2

- [ ] T024 [P] [US2] Write unit tests for create_table() with mock catalog in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T025 [P] [US2] Write unit tests for load_table() in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T026 [P] [US2] Write unit tests for table_exists() in `packages/floe-iceberg/tests/unit/test_manager.py`

### Implementation for User Story 2

- [ ] T027 [US2] Implement create_table(config, if_not_exists) method in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T028 [US2] Implement TableAlreadyExistsError handling with if_not_exists parameter
- [ ] T029 [US2] Implement load_table(identifier) method in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T030 [US2] Implement table_exists(identifier) method in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T031 [US2] Add config validation before table creation

**Checkpoint**: Tables can be created with schemas and partitioning, loaded by identifier, existence checked

---

## Phase 5: User Story 3 - Data Engineer Evolves Table Schema (Priority: P1)

**Goal**: Enable safe schema evolution without data migration

**Independent Test**: Create table, add nullable column, verify existing and new queries work

**Requirements**: FR-002, FR-017, FR-018, FR-019, FR-020, FR-021

### Models for User Story 3

- [ ] T032 [P] [US3] Implement SchemaChange model in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T033 [P] [US3] Implement SchemaEvolution model with allow_incompatible_changes flag in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T034 [P] [US3] Write unit tests for schema evolution models in `packages/floe-iceberg/tests/unit/test_models.py`

### Tests for User Story 3

- [ ] T035 [P] [US3] Write unit tests for evolve_schema() - add column in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T036 [P] [US3] Write unit tests for evolve_schema() - rename column in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T037 [P] [US3] Write unit tests for evolve_schema() - type widening in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T038 [P] [US3] Write unit tests for evolve_schema() - incompatible change rejection in `packages/floe-iceberg/tests/unit/test_manager.py`

### Implementation for User Story 3

- [ ] T039 [US3] Implement evolve_schema(table, evolution) method in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T040 [US3] Implement add_column change type in evolve_schema()
- [ ] T041 [US3] Implement rename_column change type in evolve_schema()
- [ ] T042 [US3] Implement widen_type change type in evolve_schema()
- [ ] T043 [US3] Implement incompatible change validation with allow_incompatible_changes flag
- [ ] T044 [US3] Add SchemaEvolutionError and IncompatibleSchemaChangeError handling

**Checkpoint**: Schema can be evolved safely with add/rename/widen operations, incompatible changes rejected

---

## Phase 6: User Story 4 - Data Engineer Manages Snapshots and Time Travel (Priority: P1)

**Goal**: Enable snapshot listing, time travel queries, rollback, and expiration

**Independent Test**: Create table, make multiple writes, query data at different snapshots

**Requirements**: FR-003, FR-006, FR-007, FR-022, FR-023, FR-024, FR-025

### Models for User Story 4

- [ ] T045 [P] [US4] Implement SnapshotInfo model with added_files/added_records properties in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T046 [P] [US4] Write unit tests for SnapshotInfo model in `packages/floe-iceberg/tests/unit/test_models.py`

### Tests for User Story 4

- [ ] T047 [P] [US4] Write unit tests for list_snapshots() in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T048 [P] [US4] Write unit tests for rollback_to_snapshot() in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T049 [P] [US4] Write unit tests for expire_snapshots() in `packages/floe-iceberg/tests/unit/test_manager.py`

### Implementation for User Story 4

- [ ] T050 [US4] Implement list_snapshots(table) method returning list[SnapshotInfo] in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T051 [US4] Implement rollback_to_snapshot(table, snapshot_id) method in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T052 [US4] Implement expire_snapshots(table, older_than_days, min_snapshots_to_keep) method with governance-aware defaults in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T053 [US4] Add SnapshotNotFoundError and RollbackError handling

**Checkpoint**: Snapshots can be listed, rollback works, expiration respects retention policy

---

## Phase 7: User Story 5 - Data Engineer Writes Data with ACID Guarantees (Priority: P1)

**Goal**: Enable atomic append, overwrite, and upsert with concurrent write handling

**Independent Test**: Perform concurrent writes and reads, verify atomicity and isolation

**Requirements**: FR-005, FR-022, FR-026, FR-027, FR-028, FR-029

### Models for User Story 5

- [ ] T054 [P] [US5] Implement WriteConfig model with mode, commit_strategy, overwrite_filter, join_columns, snapshot_properties in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T055 [P] [US5] Write unit tests for WriteConfig validation in `packages/floe-iceberg/tests/unit/test_models.py`

### Tests for User Story 5

- [ ] T056 [P] [US5] Write unit tests for write_data() - append mode in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T057 [P] [US5] Write unit tests for write_data() - overwrite mode in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T058 [P] [US5] Write unit tests for write_data() - upsert mode with join_columns in `packages/floe-iceberg/tests/unit/test_manager.py`
- [ ] T058a [P] [US5] Write unit tests for write_data() - commit conflict retry in `packages/floe-iceberg/tests/unit/test_manager.py`

### Implementation for User Story 5

- [ ] T059 [US5] Implement write_data(table, data, config) method skeleton in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T060 [US5] Implement append mode in write_data() with fast_append default
- [ ] T061 [US5] Implement overwrite mode in write_data() with filter support
- [ ] T061a [US5] Implement upsert mode in write_data() using PyIceberg table.upsert()
- [ ] T061b [US5] Add WriteConfig validation: join_columns required when mode=UPSERT
- [ ] T061c [US5] Add WriteConfig validation: join_columns must exist in table schema
- [ ] T062 [US5] Implement exponential backoff retry on CommitFailedException in write_data()
- [ ] T063 [US5] Implement snapshot_properties attachment for lineage tracking
- [ ] T064 [US5] Add WriteError and CommitConflictError handling

**Checkpoint**: Data writes are atomic with ACID guarantees, concurrent writes handled with retry

---

## Phase 8: User Story 6 - Data Engineer Configures Partitioning Strategy (Priority: P2)

**Goal**: Enable partition configuration with transforms and partition evolution

**Independent Test**: Create partitioned table, write data, verify partition pruning works

**Requirements**: FR-013 (covered in US2), partition evolution support

### Tests for User Story 6

- [ ] T065 [P] [US6] Write unit tests for PartitionSpec with all transform types in `packages/floe-iceberg/tests/unit/test_models.py`
- [ ] T066 [P] [US6] Write integration test for partition pruning in `packages/floe-iceberg/tests/integration/test_manager_integration.py`

### Implementation for User Story 6

- [ ] T067 [US6] Enhance PartitionSpec.to_pyiceberg_spec() to support all transforms (identity, year, month, day, hour, bucket, truncate)
- [ ] T068 [US6] Add partition validation in TableConfig (source field exists, partition field IDs >= 1000)

**Checkpoint**: All partition transforms work, partition validation enforced

---

## Phase 9: User Story 7 - Platform Operator Monitors Storage Operations (Priority: P2)

**Goal**: Emit OpenTelemetry spans for all storage operations

**Independent Test**: Perform storage operations, verify OTel spans emitted with correct attributes

**Requirements**: FR-041, FR-042, FR-043, FR-044

### Implementation for User Story 7

- [ ] T069 [P] [US7] Create `packages/floe-iceberg/src/floe_iceberg/telemetry.py` with OTel span decorator
- [ ] T070 [P] [US7] Write unit tests for telemetry decorator in `packages/floe-iceberg/tests/unit/test_telemetry.py`
- [ ] T071 [US7] Add @traced decorator to create_table() with span attributes (table.identifier, operation)
- [ ] T072 [US7] Add @traced decorator to write_data() with span attributes (write.mode, commit.strategy, records.added)
- [ ] T073 [US7] Add @traced decorator to evolve_schema() with span attributes
- [ ] T074 [US7] Add @traced decorator to snapshot operations with span attributes
- [ ] T075 [US7] Add @traced decorator to compact_table() with span attributes
- [ ] T076 [US7] Ensure no data values or sensitive info in logs/traces (FR-044)

**Checkpoint**: All operations emit OTel spans with correct attributes, no sensitive data leaked

---

## Phase 10: User Story 8 - Data Engineer Integrates Storage with Dagster (Priority: P1)

**Goal**: Provide IcebergIOManager for Dagster asset integration

**Independent Test**: Create Dagster asset that outputs to Iceberg table, verify data flows correctly

**Requirements**: FR-037, FR-038, FR-039, FR-040

### Models for User Story 8

- [ ] T077 [P] [US8] Implement IcebergIOManagerConfig model in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T078 [P] [US8] Write unit tests for IcebergIOManagerConfig in `packages/floe-iceberg/tests/unit/test_models.py`

### Tests for User Story 8

- [ ] T079 [P] [US8] Write unit tests for IcebergIOManager.handle_output() in `packages/floe-iceberg/tests/unit/test_io_manager.py`
- [ ] T080 [P] [US8] Write unit tests for IcebergIOManager.load_input() in `packages/floe-iceberg/tests/unit/test_io_manager.py`
- [ ] T081 [P] [US8] Write unit tests for table identifier generation from asset key in `packages/floe-iceberg/tests/unit/test_io_manager.py`

### Implementation for User Story 8

- [ ] T082 [US8] Create `packages/floe-iceberg/src/floe_iceberg/io_manager.py` with IcebergIOManager class inheriting ConfigurableIOManager
- [ ] T083 [US8] Implement handle_output(context, obj) method for writing PyArrow tables
- [ ] T084 [US8] Implement load_input(context) method for reading PyArrow tables
- [ ] T085 [US8] Implement _get_table_identifier(context) for asset key to table mapping
- [ ] T086 [US8] Implement _get_write_config(context) for metadata-based configuration
- [ ] T087 [US8] Add schema inference on first write when table doesn't exist
- [ ] T088 [US8] Add partitioned asset support with partition key to filter mapping
- [ ] T089 [US8] Export IcebergIOManager from `packages/floe-iceberg/src/floe_iceberg/__init__.py`

**Checkpoint**: Dagster assets can read/write Iceberg tables via IOManager, partitioned assets supported

---

## Phase 11: Compaction (Cross-Cutting)

**Goal**: Provide compaction execution for file optimization

**Requirements**: FR-030, FR-031, FR-032

### Models

- [ ] T090 [P] Implement CompactionStrategy model in `packages/floe-iceberg/src/floe_iceberg/models.py`
- [ ] T091 [P] Write unit tests for CompactionStrategy model in `packages/floe-iceberg/tests/unit/test_models.py`

### Tests

- [ ] T092 [P] Write unit tests for compact_table() - bin_pack strategy in `packages/floe-iceberg/tests/unit/test_manager.py`

### Implementation

- [ ] T093 Create `packages/floe-iceberg/src/floe_iceberg/compaction.py` with compaction logic
- [ ] T094 Implement compact_table(table, strategy) method in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T095 Implement bin_pack compaction strategy
- [ ] T096 Add CompactionError handling

**Checkpoint**: Tables can be compacted with bin_pack strategy

---

## Phase 12: Integration Tests (Validation)

**Purpose**: Validate with real Polaris and S3 in K8s

- [ ] T097 [P] Write integration test for create_table with real Polaris in `packages/floe-iceberg/tests/integration/test_manager_integration.py`
- [ ] T098 [P] Write integration test for write_data with real S3 in `packages/floe-iceberg/tests/integration/test_manager_integration.py`
- [ ] T099 [P] Write integration test for schema evolution in `packages/floe-iceberg/tests/integration/test_manager_integration.py`
- [ ] T100 [P] Write integration test for snapshot management in `packages/floe-iceberg/tests/integration/test_manager_integration.py`
- [ ] T101 Write integration test for IcebergIOManager with Dagster in `packages/floe-iceberg/tests/integration/test_io_manager_integration.py`

**Checkpoint**: All operations validated against real infrastructure

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements across all user stories

- [ ] T102 [P] Add docstrings to all public methods following Google style
- [ ] T103 [P] Run mypy --strict and fix any type errors
- [ ] T104 [P] Run ruff and fix any linting issues
- [ ] T105 Verify quickstart.md examples work with implementation
- [ ] T105a [P] Document time-travel query pattern in quickstart.md (use native PyIceberg scan with snapshot_id per FR-023)
- [ ] T106 Add JSON Schema export for all Pydantic models
- [ ] T107 Final review: Verify all FRs are implemented (FR-001 through FR-047)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational - Core manager class
- **US2 (Phase 4)**: Depends on US1 - Table creation needs manager
- **US3 (Phase 5)**: Depends on US2 - Schema evolution needs tables
- **US4 (Phase 6)**: Depends on US2 - Snapshot mgmt needs tables
- **US5 (Phase 7)**: Depends on US2 - Writes need tables
- **US6 (Phase 8)**: Depends on US2 - Partitioning is part of table creation
- **US7 (Phase 9)**: Can start after US1 - Observability wraps all ops
- **US8 (Phase 10)**: Depends on US2, US5 - IOManager uses manager
- **Compaction (Phase 11)**: Depends on US2 - Compacts existing tables
- **Integration (Phase 12)**: Depends on all user stories
- **Polish (Phase 13)**: Depends on all phases

### User Story Dependencies

| Story | Can Start After | Can Run In Parallel With |
|-------|-----------------|--------------------------|
| US1 (Manager) | Foundational | - |
| US2 (Tables) | US1 | - |
| US3 (Schema) | US2 | US4, US5, US6, US7 |
| US4 (Snapshots) | US2 | US3, US5, US6, US7 |
| US5 (Writes) | US2 | US3, US4, US6, US7 |
| US6 (Partitions) | US2 | US3, US4, US5, US7 |
| US7 (Observability) | US1 | US3, US4, US5, US6 |
| US8 (IOManager) | US2, US5 | US3, US4, US6 |

### Within Each User Story

1. Models before implementation
2. Tests written and FAIL before implementation
3. Implementation in dependency order
4. Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T003, T004 can run in parallel
- **Phase 2**: T005-T008 can run in parallel
- **Phase 4**: T018-T021, T023-T026 can run in parallel (models + tests)
- **Phase 5**: T032-T038 can run in parallel (models + tests)
- **After US2 complete**: US3, US4, US5, US6, US7 can all start in parallel

---

## Parallel Example: User Story 2 (Table Creation)

```bash
# Launch all models in parallel:
Task: T018 - Implement SchemaField model
Task: T019 - Implement TableSchema model
Task: T020 - Implement PartitionField model
Task: T021 - Implement PartitionSpec model

# Then launch all tests in parallel:
Task: T023 - Write unit tests for schema/partition models
Task: T024 - Write unit tests for create_table()
Task: T025 - Write unit tests for load_table()
Task: T026 - Write unit tests for table_exists()
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (Manager)
4. Complete Phase 4: US2 (Tables)
5. **STOP and VALIDATE**: Test table creation independently
6. Demo/deploy if ready

### Incremental Delivery

1. Setup + Foundational + US1 + US2 → Tables work (MVP!)
2. Add US5 (Writes) → Data can be written
3. Add US8 (IOManager) → Dagster integration
4. Add US3, US4 → Schema evolution, snapshots
5. Add US6, US7 → Partitioning, observability
6. Add compaction → Optimization
7. Each story adds value without breaking previous

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational + US1 together
2. Once US2 done:
   - Developer A: US3 (Schema Evolution)
   - Developer B: US5 (Writes)
   - Developer C: US8 (IOManager)
3. Stories complete and integrate independently

---

## Requirement Traceability

| FR | Tasks | User Story |
|----|-------|------------|
| FR-001 | T013, T027 | US1, US2 |
| FR-002 | T039-T044 | US3 |
| FR-003 | T050 | US4 |
| FR-004 | T013-T015 | US1 |
| FR-005 | T058, T059-T064 (incl. T061a-c) | US5 |
| FR-006 | T050 | US4 |
| FR-007 | T051 | US4 |
| FR-008-011 | T013-T015 | US1 |
| FR-012-016 | T027-T031 | US2 |
| FR-017-021 | T039-T044 | US3 |
| FR-022-025 | T050-T053 | US4 |
| FR-026-029 | T059-T064 | US5 |
| FR-030-032 | T093-T096 | Phase 11 |
| FR-033-036 | T067-T068 | US6 |
| FR-037-040 | T082-T089 | US8 |
| FR-041-044 | T069-T076 | US7 |
| FR-045-047 | T009-T010, T022 | Phase 2, US2 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- TDD: Write tests first, verify they FAIL, then implement
- Commit after each task or logical group (300-600 LOC)
- Stop at any checkpoint to validate story independently
- All integration tests require `@pytest.mark.requirement()` markers
