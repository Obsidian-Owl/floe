# Tasks: January 2026 Tech Debt Reduction

**Input**: Design documents from `/specs/12a-tech-debt-q1-2026/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify baseline and create foundational test infrastructure

- [ ] T001 Run baseline tech debt audit and save snapshot
- [ ] T002 [P] Verify all existing tests pass before refactoring (`make test-unit`)
- [ ] T003 [P] Verify mypy --strict passes on target files

**Checkpoint**: Baseline established, safe to begin refactoring

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create testing infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create golden test fixtures directory at `testing/fixtures/golden/`
- [ ] T005 [P] Create golden test runner utility in `testing/base_classes/golden_test_utils.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Break Circular Dependency (Priority: P0) 🎯 MVP

**Goal**: Break circular dependency between floe_core and floe_rbac_k8s using registry lookup

**Independent Test**: `python -c "import floe_core; import floe_rbac_k8s"` succeeds without ImportError

### Tests for User Story 1

- [ ] T006 [P] [US1] Create import cycle detection test in `packages/floe-core/tests/unit/test_import_cycle.py`

### Implementation for User Story 1

- [ ] T007 [US1] Remove direct K8sRBACPlugin import from `packages/floe-core/src/floe_core/rbac/generator.py`, use RBACPlugin ABC only
- [ ] T008 [US1] Replace direct import with registry lookup in `packages/floe-core/src/floe_core/cli/rbac/generate.py`
- [ ] T009 [US1] Verify import cycle test passes
- [ ] T010 [US1] Run mypy --strict on modified files

**Checkpoint**: US1 complete - packages can be versioned independently

---

## Phase 4: User Story 2 - Fix N+1 Performance Issues (Priority: P0)

**Goal**: Fix N+1 patterns in OCI client via parallel fetching and dictionary lookup

**Independent Test**: Benchmark `client.list()` with 100 tags completes in <6s (5x improvement)

### Tests for User Story 2

- [ ] T011 [P] [US2] Create performance benchmark test in `packages/floe-core/tests/unit/oci/test_client_performance.py`

### Implementation for User Story 2

- [ ] T012 [P] [US2] Create `_BatchFetcher` class in `packages/floe-core/src/floe_core/oci/batch_fetcher.py`
- [ ] T013 [US2] Refactor `client.list()` to use ThreadPoolExecutor in `packages/floe-core/src/floe_core/oci/client.py`
- [ ] T014 [US2] Refactor `client.pull()` to use dictionary lookup instead of linear search in `packages/floe-core/src/floe_core/oci/client.py`
- [ ] T015 [US2] Add limit parameter to `plugin_registry.list()` in `packages/floe-core/src/floe_core/plugin_registry.py` (FR-007)
- [ ] T016 [US2] Add max_violations parameter to `PolicyEnforcer.enforce()` in `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py` (FR-008)
- [ ] T017 [US2] Add caching to `RBACPermissionAggregator.aggregate_permissions()` in `packages/floe-core/src/floe_core/rbac/aggregator.py` (FR-009)
- [ ] T018 [US2] Run benchmark test and verify 5x improvement

**Checkpoint**: US2 complete - OCI operations are 5x faster

---

## Phase 5: User Story 3 - Reduce Code Complexity (Priority: P1)

**Goal**: Refactor high-CC functions to meet complexity targets

**Independent Test**: `radon cc --show-complexity` shows diff_command CC ≤10, pull CC ≤12

### Tests for User Story 3

- [ ] T019 [P] [US3] Create golden tests for `diff_command()` in `packages/floe-core/tests/unit/cli/rbac/test_diff_golden.py`
- [ ] T020 [P] [US3] Create golden tests for `pull()` in `packages/floe-core/tests/unit/oci/test_pull_golden.py`

### Implementation for User Story 3

- [ ] T021 [US3] Apply Extract Method to `diff_command()` in `packages/floe-core/src/floe_core/cli/rbac/diff.py` (target CC ≤10)
- [ ] T022 [US3] Apply Extract Method to `pull()` in `packages/floe-core/src/floe_core/oci/client.py` (target CC ≤12)
- [ ] T023 [US3] Apply Strategy pattern to `_generate_impl()` in `packages/floe-core/src/floe_core/rbac/generator.py` (FR-017)
- [ ] T024 [US3] Verify golden tests still pass after refactoring
- [ ] T025 [US3] Run radon cc to verify complexity targets met
- [ ] T025a [US3] Verify 100% test coverage on refactored functions: `pytest --cov=floe_core.cli.rbac.diff --cov=floe_core.oci.client --cov-fail-under=100`

**Checkpoint**: US3 complete - all high-complexity functions refactored

---

## Phase 6: User Story 4 - Split IcebergTableManager (Priority: P1)

**Goal**: Decompose god class into facade with specialized internal classes

**Independent Test**: IcebergTableManager has ≤5 public methods, public API unchanged

### Tests for User Story 4

- [ ] T026 [P] [US4] Create tests for `_IcebergTableLifecycle` in `packages/floe-iceberg/tests/unit/test_lifecycle.py`
- [ ] T027 [P] [US4] Create tests for `_IcebergSchemaManager` in `packages/floe-iceberg/tests/unit/test_schema_manager.py`
- [ ] T028 [P] [US4] Create tests for `_IcebergSnapshotManager` in `packages/floe-iceberg/tests/unit/test_snapshot_manager.py`
- [ ] T029 [P] [US4] Create tests for `_IcebergCompactionManager` in `packages/floe-iceberg/tests/unit/test_compaction_manager.py`

### Implementation for User Story 4

- [ ] T030 [P] [US4] Create `_IcebergTableLifecycle` class in `packages/floe-iceberg/src/floe_iceberg/_lifecycle.py`
- [ ] T031 [P] [US4] Create `_IcebergSchemaManager` class in `packages/floe-iceberg/src/floe_iceberg/_schema_manager.py`
- [ ] T032 [P] [US4] Create `_IcebergSnapshotManager` class in `packages/floe-iceberg/src/floe_iceberg/_snapshot_manager.py`
- [ ] T033 [P] [US4] Create `_IcebergCompactionManager` class in `packages/floe-iceberg/src/floe_iceberg/_compaction_manager.py`
- [ ] T034 [US4] Refactor `IcebergTableManager` to facade pattern in `packages/floe-iceberg/src/floe_iceberg/manager.py`
- [ ] T035 [US4] Verify existing manager tests still pass
- [ ] T036 [US4] Verify public API unchanged (backward compatibility)

**Checkpoint**: US4 complete - IcebergTableManager is a clean facade

---

## Phase 7: User Story 5 - Fix Test Policy Violations (Priority: P1)

**Goal**: Remove pytest.skip() calls and use IntegrationTestBase pattern

**Independent Test**: `rg "pytest.skip" plugins/floe-orchestrator-dagster/tests/` returns no matches

### Implementation for User Story 5

- [ ] T037 [US5] Refactor `test_iceberg_io_manager.py` to inherit from IntegrationTestBase in `plugins/floe-orchestrator-dagster/tests/integration/test_iceberg_io_manager.py`
- [ ] T038 [US5] Replace `pytest.skip()` calls with `check_infrastructure()` pattern
- [ ] T039 [US5] Convert stub tests (containing only `pass`) to actual assertions
- [ ] T040 [US5] Verify no pytest.skip() calls remain: `rg "pytest.skip" plugins/floe-orchestrator-dagster/tests/`

**Checkpoint**: US5 complete - all tests fail explicitly when infrastructure missing

---

## Phase 8: User Story 6 - Add Missing Test Coverage (Priority: P1)

**Goal**: Add test coverage for OCI error and metrics modules

**Independent Test**: `pytest --cov=floe_core.oci` shows >80% coverage

### Implementation for User Story 6

- [ ] T041 [P] [US6] Create `tests/unit/oci/test_errors.py` covering full exception hierarchy in `packages/floe-core/tests/unit/oci/test_errors.py`
- [ ] T042 [P] [US6] Create `tests/unit/oci/test_metrics.py` covering metric emission scenarios in `packages/floe-core/tests/unit/oci/test_metrics.py`
- [ ] T043 [US6] Add `@pytest.mark.requirement()` markers to all new tests (FR-021)
- [ ] T044 [US6] Run coverage and verify >80% for OCI module

**Checkpoint**: US6 complete - OCI module has comprehensive test coverage

---

## Phase 9: User Story 7 - Reduce Test Duplication (Priority: P2)

**Goal**: Create shared base test classes for plugins

**Independent Test**: 3+ plugin test files inherit from base classes

### Implementation for User Story 7

- [ ] T045 [P] [US7] Create `BasePluginMetadataTests` in `testing/base_classes/plugin_metadata_tests.py`
- [ ] T046 [P] [US7] Create `BasePluginLifecycleTests` in `testing/base_classes/plugin_lifecycle_tests.py`
- [ ] T047 [P] [US7] Create `BasePluginDiscoveryTests` in `testing/base_classes/plugin_discovery_tests.py`
- [ ] T048 [US7] Migrate DuckDB compute plugin tests to use base classes in `plugins/floe-compute-duckdb/tests/`
- [ ] T049 [US7] Migrate Polaris catalog plugin tests to use base classes in `plugins/floe-catalog-polaris/tests/`
- [ ] T050 [US7] Migrate Dagster orchestrator plugin tests to use base classes in `plugins/floe-orchestrator-dagster/tests/`
- [ ] T051 [US7] Verify all migrated tests pass

**Checkpoint**: US7 complete - plugin test duplication reduced by >50%

---

## Phase 10: User Story 8 - Clean Up Dependencies (Priority: P3)

**Goal**: Remove unused dependencies from floe-orchestrator-dagster

**Independent Test**: `uv sync && pytest plugins/floe-orchestrator-dagster/tests/ -v` passes

### Implementation for User Story 8

- [ ] T052 [P] [US8] Remove `croniter` from `plugins/floe-orchestrator-dagster/pyproject.toml`
- [ ] T053 [P] [US8] Remove `pytz` from `plugins/floe-orchestrator-dagster/pyproject.toml`
- [ ] T054 [US8] Run `uv sync` to update lockfile
- [ ] T055 [US8] Verify all tests pass after dependency removal

**Checkpoint**: US8 complete - unused dependencies removed

---

## Phase 11: Polish & Verification

**Purpose**: Final verification and cleanup

- [ ] T056 Run full tech debt audit: `/tech-debt-review --all`
- [ ] T057 Verify debt score ≥80 (target: 80+, baseline: 68)
- [ ] T058 Verify critical issues = 0 (target: 0, baseline: 5)
- [ ] T059 Verify high issues ≤3 (target: ≤3, baseline: 12)
- [ ] T060 Run `mypy --strict` on all modified files
- [ ] T060a Verify OCIClient LOC < 500: `wc -l packages/floe-core/src/floe_core/oci/client.py` (FR-004)
- [ ] T061 Run `make test-unit` to verify all tests pass
- [ ] T062 Run quickstart.md validation commands
- [ ] T063 Update CHANGELOG.md with Epic 12A changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **US1 (Phase 3)**: Depends on Foundational - P0 MVP, start first
- **US2 (Phase 4)**: Depends on Foundational - P0, can parallel with US1
- **US3 (Phase 5)**: Depends on Foundational + US2 (T022 refactors pull() after T014 applies dict lookup)
- **US4 (Phase 6)**: Depends on Foundational - can parallel with US1-US3
- **US5 (Phase 7)**: Depends on Foundational - can parallel
- **US6 (Phase 8)**: Depends on US2 (OCI client changes)
- **US7 (Phase 9)**: Depends on Foundational - can parallel
- **US8 (Phase 10)**: Depends on Foundational - can parallel
- **Polish (Phase 11)**: Depends on all user stories complete

### Critical Path

```
Setup → Foundational → US1 (P0) → US2 (P0) → US3 (P1) → Polish
                    ↳ US4 (P1) → ───────────────────────↗
                    ↳ US5 (P1) → ───────────────────────↗
                    ↳ US6 (P1) → ───────────────────────↗
                    ↳ US7 (P2) → ───────────────────────↗
                    ↳ US8 (P3) → ───────────────────────↗
```

### Parallel Opportunities

- T002, T003 (Setup verification)
- T004, T005 (Foundational tasks)
- T011, T012 (US2 test + batch_fetcher)
- T019, T020 (US3 golden tests)
- T026, T027, T028, T029 (US4 tests for extracted classes)
- T030, T031, T032, T033 (US4 internal class creation)
- T041, T042 (US6 error and metrics tests)
- T045, T046, T047 (US7 base test classes)
- T052, T053 (US8 dependency removal)

---

## Summary

| Phase | User Story | Priority | Tasks | Est. Effort |
|-------|-----------|----------|-------|-------------|
| 1 | Setup | - | T001-T003 | 0.5 days |
| 2 | Foundational | - | T004-T005 | 0.5 days |
| 3 | US1: Circular Dep | P0 | T006-T010 | 1 day |
| 4 | US2: N+1 Performance | P0 | T011-T018 | 2 days |
| 5 | US3: Complexity | P1 | T019-T025 | 2 days |
| 6 | US4: IcebergTableManager | P1 | T026-T036 | 3 days |
| 7 | US5: Test Policy | P1 | T037-T040 | 1 day |
| 8 | US6: Test Coverage | P1 | T041-T044 | 1 day |
| 9 | US7: Test Duplication | P2 | T045-T051 | 2 days |
| 10 | US8: Dependencies | P3 | T052-T055 | 0.5 days |
| 11 | Polish | - | T056-T063 | 0.5 days |
| **Total** | | | **63 tasks** | **~14 days** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Golden tests MUST pass after refactoring (behavior preservation)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
