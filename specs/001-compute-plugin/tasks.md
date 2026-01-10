# Tasks: Compute Plugin ABC with Multi-Compute Pipeline Support

**Input**: Design documents from `/specs/001-compute-plugin/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US7)
- Include exact file paths in descriptions

## Path Conventions

- **floe-core package**: `packages/floe-core/src/floe_core/`
- **DuckDB plugin**: `plugins/floe-compute-duckdb/`
- **Contract tests**: `tests/contract/`
- Tests follow K8s-native testing standards per `TESTING.md`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and DuckDB plugin package structure

- [ ] T001 Create DuckDB plugin package structure at plugins/floe-compute-duckdb/
- [ ] T002 Create pyproject.toml with entry point `floe.computes = duckdb` in plugins/floe-compute-duckdb/pyproject.toml
- [ ] T003 [P] Create plugin __init__.py with exports in plugins/floe-compute-duckdb/src/floe_compute_duckdb/__init__.py
- [ ] T004 [P] Configure pytest and test directories in plugins/floe-compute-duckdb/tests/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and errors that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T005 Create ConnectionStatus enum in packages/floe-core/src/floe_core/compute_config.py
- [ ] T006 [P] Create ConnectionResult Pydantic model in packages/floe-core/src/floe_core/compute_config.py
- [ ] T007 [P] Create ResourceSpec Pydantic model with K8s resource fields in packages/floe-core/src/floe_core/compute_config.py
- [ ] T008 [P] Create WORKLOAD_PRESETS dict (small/medium/large) in packages/floe-core/src/floe_core/compute_config.py
- [ ] T009 [P] Create ComputeConfig base Pydantic model in packages/floe-core/src/floe_core/compute_config.py
- [ ] T010 [P] Create CatalogConfig Pydantic model in packages/floe-core/src/floe_core/compute_config.py
- [ ] T011 Create ComputeError base exception with correlation_id in packages/floe-core/src/floe_core/compute_errors.py
- [ ] T012 [P] Create ComputeConnectionError exception in packages/floe-core/src/floe_core/compute_errors.py
- [ ] T013 [P] Create ComputeTimeoutError exception in packages/floe-core/src/floe_core/compute_errors.py
- [ ] T014 [P] Create ComputeConfigurationError exception in packages/floe-core/src/floe_core/compute_errors.py
- [ ] T015 Export all models from packages/floe-core/src/floe_core/__init__.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Plugin Developer Creates Compute Adapter (Priority: P0)

**Goal**: Define ComputePlugin ABC so plugin developers can create new compute adapters

**Independent Test**: Create a mock implementation and verify all abstract methods are enforced

**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-004a

### Tests for User Story 1

- [ ] T016 [P] [US1] Contract test for ComputePlugin ABC in tests/contract/test_compute_plugin_contract.py
- [ ] T017 [P] [US1] Unit test for incomplete implementation error in packages/floe-core/tests/unit/test_compute_plugin.py
- [ ] T018 [P] [US1] Unit test for ABC method signatures in packages/floe-core/tests/unit/test_compute_plugin.py

### Implementation for User Story 1

- [ ] T019 [US1] Create ComputePlugin ABC inheriting from PluginMetadata in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T020 [US1] Add abstract method generate_dbt_profile(config: ComputeConfig) -> dict in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T021 [US1] Add abstract method get_required_dbt_packages() -> list[str] in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T022 [US1] Add abstract method validate_connection(config: ComputeConfig) -> ConnectionResult in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T023 [US1] Add abstract method get_resource_requirements(workload_size: str) -> ResourceSpec in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T024 [US1] Add abstract method get_catalog_attachment_sql(catalog_config: CatalogConfig) -> list[str] | None in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T025 [US1] Add comprehensive docstrings with examples to all abstract methods in packages/floe-core/src/floe_core/compute_plugin.py
- [ ] T026 [US1] Export ComputePlugin from packages/floe-core/src/floe_core/__init__.py

**Checkpoint**: ComputePlugin ABC is complete - plugin developers can now inherit from it

---

## Phase 4: User Story 2 - Data Engineer Uses DuckDB for Local Development (Priority: P0)

**Goal**: Provide DuckDB reference implementation for zero-config local development

**Independent Test**: Generate dbt profile and validate connection with real DuckDB

**Requirements**: FR-005, FR-006, FR-007, FR-008, FR-009

### Tests for User Story 2

- [ ] T027 [P] [US2] Unit test for DuckDBConfig validation in plugins/floe-compute-duckdb/tests/unit/test_config.py
- [ ] T028 [P] [US2] Unit test for generate_dbt_profile output in plugins/floe-compute-duckdb/tests/unit/test_plugin.py
- [ ] T029 [P] [US2] Unit test for get_required_dbt_packages in plugins/floe-compute-duckdb/tests/unit/test_plugin.py
- [ ] T030 [P] [US2] Unit test for get_resource_requirements presets in plugins/floe-compute-duckdb/tests/unit/test_plugin.py
- [ ] T031 [P] [US2] Integration test for validate_connection with real DuckDB in plugins/floe-compute-duckdb/tests/integration/test_duckdb.py
- [ ] T032 [P] [US2] Integration test for in-memory and file-based modes in plugins/floe-compute-duckdb/tests/integration/test_duckdb.py

### Implementation for User Story 2

- [ ] T033 [P] [US2] Create AttachConfig Pydantic model in plugins/floe-compute-duckdb/src/floe_compute_duckdb/config.py
- [ ] T034 [US2] Create DuckDBConfig extending ComputeConfig in plugins/floe-compute-duckdb/src/floe_compute_duckdb/config.py
- [ ] T035 [US2] Add memory_limit validator (must end with GB or MB) in plugins/floe-compute-duckdb/src/floe_compute_duckdb/config.py
- [ ] T036 [US2] Create DuckDBComputePlugin class in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T037 [US2] Implement name, version, floe_api_version properties in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T038 [US2] Implement generate_dbt_profile with path, threads, extensions, settings in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T039 [US2] Implement get_required_dbt_packages returning dbt-duckdb>=1.9.0 in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T040 [US2] Implement validate_connection using native duckdb driver in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T041 [US2] Implement get_resource_requirements with workload presets in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T042 [US2] Implement get_catalog_attachment_sql for Iceberg REST catalog in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T043 [US2] Add attach block support in generate_dbt_profile in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py

**Checkpoint**: DuckDB plugin is complete - data engineers can use it for local development

---

## Phase 5: User Story 3 - Platform Engineer Configures Multi-Compute Pipeline (Priority: P0)

**Goal**: Support N approved compute targets with a default in manifest.yaml

**Independent Test**: Configure multiple computes and verify all are discovered and loaded

**Requirements**: FR-010, FR-011, FR-013

### Tests for User Story 3

- [ ] T044 [P] [US3] Unit test for compute.approved configuration parsing in packages/floe-core/tests/unit/test_compute_registry.py
- [ ] T045 [P] [US3] Unit test for compute.default fallback in packages/floe-core/tests/unit/test_compute_registry.py
- [ ] T046 [P] [US3] Unit test for validation error on non-approved compute in packages/floe-core/tests/unit/test_compute_registry.py

### Implementation for User Story 3

- [ ] T047 [US3] Create ComputeRegistry class for approved/default management in packages/floe-core/src/floe_core/compute_registry.py
- [ ] T048 [US3] Add compute.approved[] list validation in packages/floe-core/src/floe_core/compute_registry.py
- [ ] T049 [US3] Add compute.default with fallback logic in packages/floe-core/src/floe_core/compute_registry.py
- [ ] T050 [US3] Add compile-time validation for non-approved compute selection in packages/floe-core/src/floe_core/compute_registry.py
- [ ] T051 [US3] Integrate with PluginRegistry for compute plugin lookup in packages/floe-core/src/floe_core/compute_registry.py

**Checkpoint**: Multi-compute configuration is complete - platform engineers can define approved targets

---

## Phase 6: User Story 4 - Data Engineer Selects Compute Per Transform (Priority: P0)

**Goal**: Enable per-transform compute selection in floe.yaml

**Independent Test**: Configure different computes per transform and verify correct assignment

**Requirements**: FR-012, FR-014

### Tests for User Story 4

- [ ] T052 [P] [US4] Unit test for transforms[].compute field parsing in packages/floe-core/tests/unit/test_transform_compute.py
- [ ] T053 [P] [US4] Unit test for default compute inheritance in packages/floe-core/tests/unit/test_transform_compute.py
- [ ] T054 [P] [US4] Unit test for environment parity enforcement in packages/floe-core/tests/unit/test_transform_compute.py

### Implementation for User Story 4

- [ ] T055 [US4] Add compute field to transform schema in packages/floe-core/src/floe_core/schemas.py
- [ ] T056 [US4] Implement compute inheritance from platform default in packages/floe-core/src/floe_core/compiler.py
- [ ] T057 [US4] Implement environment parity check (same compute across dev/staging/prod) in packages/floe-core/src/floe_core/compiler.py
- [ ] T058 [US4] Add clear error messages for parity violations in packages/floe-core/src/floe_core/compiler.py

**Checkpoint**: Per-transform compute selection is complete with environment parity

---

## Phase 7: User Story 5 - Enterprise Architect Enforces Hierarchical Governance (Priority: P1)

**Goal**: Support hierarchical compute restriction (Enterprise -> Domain -> Product)

**Independent Test**: Define enterprise and domain manifests with different subsets

**Requirements**: FR-015, FR-016, FR-017

### Tests for User Story 5

- [ ] T059 [P] [US5] Unit test for domain subset validation in packages/floe-core/tests/unit/test_governance.py
- [ ] T060 [P] [US5] Unit test for governance violation error messages in packages/floe-core/tests/unit/test_governance.py

### Implementation for User Story 5

- [ ] T061 [US5] Add hierarchical compute.approved validation in packages/floe-core/src/floe_core/governance.py
- [ ] T062 [US5] Implement subset check (domain must be subset of enterprise) in packages/floe-core/src/floe_core/governance.py
- [ ] T063 [US5] Create clear error messages listing allowed options in packages/floe-core/src/floe_core/governance.py

**Checkpoint**: Hierarchical governance is complete

---

## Phase 8: User Story 6 - Platform Operator Monitors Connection Health (Priority: P1)

**Goal**: Enable connection health monitoring with OTel metrics

**Independent Test**: Invoke health check and verify metrics are emitted

**Requirements**: FR-018, FR-019, FR-024

### Tests for User Story 6

- [ ] T064 [P] [US6] Unit test for ConnectionResult structure in packages/floe-core/tests/unit/test_health.py
- [ ] T065 [P] [US6] Unit test for latency measurement in validate_connection in plugins/floe-compute-duckdb/tests/unit/test_health.py
- [ ] T066 [P] [US6] Integration test for OTel metrics emission in plugins/floe-compute-duckdb/tests/integration/test_otel.py

### Implementation for User Story 6

- [ ] T067 [US6] Add OTel tracer and meter setup in packages/floe-core/src/floe_core/observability.py
- [ ] T068 [US6] Add validation_duration histogram metric in packages/floe-core/src/floe_core/observability.py
- [ ] T069 [US6] Add validation_errors counter metric in packages/floe-core/src/floe_core/observability.py
- [ ] T070 [US6] Integrate OTel instrumentation in DuckDBComputePlugin.validate_connection in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py

**Checkpoint**: Health monitoring with OTel metrics is complete

---

## Phase 9: User Story 7 - Platform Operator Enforces Query Timeouts (Priority: P1)

**Goal**: Support configurable query timeouts via dbt profile configuration

**Independent Test**: Configure timeout and verify it appears in generated profile

**Requirements**: FR-020, FR-021

### Tests for User Story 7

- [ ] T071 [P] [US7] Unit test for timeout_seconds in ComputeConfig in packages/floe-core/tests/unit/test_timeout.py
- [ ] T072 [P] [US7] Unit test for timeout in generated dbt profile in plugins/floe-compute-duckdb/tests/unit/test_timeout.py

### Implementation for User Story 7

- [ ] T073 [US7] Add timeout configuration to generate_dbt_profile output in plugins/floe-compute-duckdb/src/floe_compute_duckdb/plugin.py
- [ ] T074 [US7] Document timeout handling in dbt adapter (dbt enforces timeout) in plugins/floe-compute-duckdb/README.md

**Checkpoint**: Timeout configuration is complete

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [ ] T075 [P] Add requirement markers to all tests (@pytest.mark.requirement)
- [ ] T076 [P] Verify mypy --strict passes on all new code
- [ ] T077 [P] Verify ruff linting passes
- [ ] T078 [P] Update packages/floe-core/src/floe_core/__init__.py with all exports
- [ ] T079 [P] Update plugins/floe-compute-duckdb/README.md with usage examples
- [ ] T080 Run quickstart.md validation scenarios
- [ ] T081 Verify >80% test coverage for new code

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ─────────── BLOCKS ALL USER STORIES
    │
    ├──► Phase 3 (US1: ABC) ◄─── MVP Core
    │         │
    │         ▼
    ├──► Phase 4 (US2: DuckDB) ◄─── MVP Implementation
    │         │
    │         ▼
    ├──► Phase 5 (US3: Multi-Compute)
    │         │
    │         ▼
    ├──► Phase 6 (US4: Per-Transform)
    │
    ├──► Phase 7 (US5: Governance)
    │
    ├──► Phase 8 (US6: Health Monitoring)
    │
    └──► Phase 9 (US7: Timeouts)
              │
              ▼
        Phase 10 (Polish)
```

### User Story Dependencies

- **US1 (ABC)**: No dependencies - foundational
- **US2 (DuckDB)**: Depends on US1 (needs ABC to implement)
- **US3 (Multi-Compute)**: Depends on US1 (needs ABC for plugin lookup)
- **US4 (Per-Transform)**: Depends on US3 (needs multi-compute registry)
- **US5 (Governance)**: Depends on US3 (needs compute registry)
- **US6 (Health)**: Depends on US1 (needs ConnectionResult from ABC)
- **US7 (Timeouts)**: Depends on US2 (needs DuckDB plugin to configure)

### Parallel Opportunities

**Within Phase 2 (Foundational)**:
```bash
# These can run in parallel (different files):
Task: T006 - ConnectionResult model
Task: T007 - ResourceSpec model
Task: T008 - WORKLOAD_PRESETS
Task: T009 - ComputeConfig model
Task: T010 - CatalogConfig model
```

**Within Phase 3 (US1 Tests)**:
```bash
# These can run in parallel:
Task: T016 - Contract test
Task: T017 - Incomplete implementation test
Task: T018 - Method signature test
```

**Within Phase 4 (US2)**:
```bash
# Unit tests can run in parallel:
Task: T027 - DuckDBConfig test
Task: T028 - generate_dbt_profile test
Task: T029 - get_required_dbt_packages test
Task: T030 - get_resource_requirements test
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 (ComputePlugin ABC)
4. Complete Phase 4: US2 (DuckDB implementation)
5. **STOP and VALIDATE**: Run contract tests, verify DuckDB works
6. Deploy/demo - MVP complete!

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (ABC) → Test independently → Plugin developers can start
3. Add US2 (DuckDB) → Test independently → Data engineers can develop locally
4. Add US3 (Multi-Compute) → Platform engineers can configure
5. Add US4 (Per-Transform) → Full pipeline flexibility
6. Add US5-US7 (Governance, Health, Timeouts) → Production readiness

---

## Task Summary

| Phase | Story | Task Count | Parallelizable |
|-------|-------|------------|----------------|
| Phase 1 | Setup | 4 | 2 |
| Phase 2 | Foundational | 11 | 8 |
| Phase 3 | US1: ABC | 11 | 3 |
| Phase 4 | US2: DuckDB | 17 | 6 |
| Phase 5 | US3: Multi-Compute | 8 | 3 |
| Phase 6 | US4: Per-Transform | 7 | 3 |
| Phase 7 | US5: Governance | 5 | 2 |
| Phase 8 | US6: Health | 7 | 3 |
| Phase 9 | US7: Timeouts | 4 | 2 |
| Phase 10 | Polish | 7 | 5 |
| **Total** | | **81** | **37** |

---

## Notes

- [P] tasks = different files, no dependencies
- [USx] label maps task to specific user story for traceability
- All tests use `@pytest.mark.requirement("FR-XXX")` for traceability
- Tests FAIL if infrastructure missing (no pytest.skip)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
