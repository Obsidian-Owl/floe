# Tasks: Tech Debt Resolution (Epic 12B)

**Input**: Design documents from `/specs/12b-tech-debt-resolution/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US8)
- Includes exact file paths in descriptions

## Phase Mapping

| tasks.md Phase | plan.md Phase | Priority | User Story |
|----------------|---------------|----------|------------|
| Phase 1-2 | - | - | Setup/Foundation |
| Phase 3 | Phase 1 | P0 | US1 (Circular Dep) |
| Phase 4 | Phase 1 | P0 | US2 (Skipped Tests) |
| Phase 5 | Phase 1 | P0 | US3 (Critical CC) |
| Phase 6 | Phase 3 | P1 | US4 (God Modules) |
| Phase 7 | Phase 2 | P1 | US5 (Dep Pinning) |
| Phase 8 | Phase 2 | P1 | US6 (Coverage) |
| Phase 9 | Phase 3 | P2 | US7 (High CC) |
| Phase 10 | Phase 3 | P2 | US8 (Duplication) |
| Phase 11 | Phase 4 | P3 | Polish |

## Path Conventions

- **Monorepo**: `packages/*/src/`, `plugins/*/src/`
- **Tests**: `packages/*/tests/`, `plugins/*/tests/`, `tests/` (root)

---

## Phase 1: Setup

**Purpose**: Baseline verification and audit snapshot

- [ ] T001 Run tech debt baseline audit and save snapshot in .claude/reviews/
- [ ] T002 [P] Create backup branch from current HEAD (git branch backup-pre-12b)
- [ ] T003 [P] Verify all existing tests pass before refactoring with `make test-unit`

---

## Phase 2: Foundational (Dependency Pinning)

**Purpose**: Pin critical dependencies before any code changes (protects against mid-refactor breakage)

**Requirement**: FR-015 (12B-DEP-001, 12B-DEP-002)

- [ ] T004 [P] Pin pydantic>=2.12.5,<3.0 in packages/floe-core/pyproject.toml
- [ ] T005 [P] Pin pydantic>=2.12.5,<3.0 in packages/floe-iceberg/pyproject.toml
- [ ] T006 [P] Pin kubernetes>=35.0.0,<36.0 in packages/floe-core/pyproject.toml
- [ ] T007 [P] Pin kubernetes>=35.0.0,<36.0 in plugins/floe-secrets-k8s/pyproject.toml
- [ ] T008 [P] Pin kubernetes>=35.0.0,<36.0 in plugins/floe-rbac-k8s/pyproject.toml
- [ ] T009 [P] Pin pyiceberg>=0.10.0,<0.11.0 in packages/floe-iceberg/pyproject.toml
- [ ] T010 [P] Pin opentelemetry-api>=1.39.0,<2.0 in packages/floe-core/pyproject.toml
- [ ] T011 Run `uv sync` and verify no dependency conflicts
- [ ] T012 Run `pip-audit` to verify 0 vulnerabilities

**Checkpoint**: Dependencies pinned - refactoring can begin safely

---

## Phase 3: User Story 1 - Resolve Circular Dependencies (Priority: P0)

**Goal**: Break schemas → telemetry → plugins cycle so modules import independently
**Independent Test**: `python -c "from floe_core.schemas import CompiledArtifacts"` imports no telemetry/plugins
**Requirement**: FR-001 (12B-ARCH-001)

### Implementation for US1

- [ ] T013 [US1] Create packages/floe-core/src/floe_core/schemas/telemetry.py with TelemetryConfig classes
- [ ] T014 [US1] Move ResourceAttributes class to schemas/telemetry.py from telemetry/config.py
- [ ] T015 [US1] Move OTLPExporterConfig class to schemas/telemetry.py from telemetry/config.py
- [ ] T016 [US1] Move SamplerConfig class to schemas/telemetry.py from telemetry/config.py
- [ ] T017 [US1] Move TelemetryConfig class to schemas/telemetry.py from telemetry/config.py
- [ ] T018 [US1] Update packages/floe-core/src/floe_core/telemetry/config.py to re-export from schemas
- [ ] T019 [US1] Update packages/floe-core/src/floe_core/schemas/compiled_artifacts.py import path
- [ ] T020 [US1] Update packages/floe-core/src/floe_core/schemas/__init__.py to export telemetry schemas
- [ ] T021 [US1] Run `python -m mypy --strict packages/floe-core/` to verify no import cycles
- [ ] T022 [US1] Run `pytest packages/floe-core/tests/` to verify all tests pass

**Checkpoint**: Circular dependency resolved - schemas module is independent

---

## Phase 4: User Story 2 - Remove Skipped Tests (Priority: P0)

**Goal**: Implement drop_table() and enable the 3 skipped tests
**Independent Test**: `pytest --co -q | grep -c skip` returns 0
**Requirement**: FR-010 (12B-TEST-001)

### Implementation for US2

- [ ] T023 [US2] Add TableNotFoundError to packages/floe-iceberg/src/floe_iceberg/errors.py
- [ ] T024 [US2] Implement drop_table() method in packages/floe-iceberg/src/floe_iceberg/manager.py
- [ ] T025 [US2] Add drop_table() tests in packages/floe-iceberg/tests/unit/test_manager.py
- [ ] T026 [US2] Remove @pytest.mark.skip from test_drop_table_removes_existing_table in test_lifecycle.py:408
- [ ] T027 [US2] Remove @pytest.mark.skip from test_drop_table_raises_for_nonexistent_table in test_lifecycle.py:428
- [ ] T028 [US2] Remove @pytest.mark.skip from test_drop_table_with_purge_removes_data in test_lifecycle.py:440
- [ ] T029 [US2] Run `pytest packages/floe-iceberg/tests/unit/test_lifecycle.py -v` to verify all pass

**Checkpoint**: Zero skipped tests - drop_table() fully implemented

---

## Phase 5: User Story 3 - Reduce Critical Complexity (Priority: P0)

**Goal**: Refactor map_pyiceberg_error() from CC 26 to CC ≤10 using Strategy Pattern
**Independent Test**: Complexity analysis shows CC ≤ 10
**Requirement**: FR-006 (12B-CX-001)

### Implementation for US3

- [ ] T030 [US3] Create error handler functions in plugins/floe-catalog-polaris/src/floe_catalog_polaris/errors.py
- [ ] T031 [US3] Create ERROR_HANDLERS dispatch dictionary in errors.py
- [ ] T032 [US3] Refactor map_pyiceberg_error() to use dispatch dictionary
- [ ] T033 [US3] Add tests for each error handler in plugins/floe-catalog-polaris/tests/unit/test_errors.py
- [ ] T034 [US3] Verify cyclomatic complexity ≤10 with analysis script
- [ ] T035 [US3] Run `pytest plugins/floe-catalog-polaris/tests/` to verify all pass

**Checkpoint**: Critical complexity resolved - map_pyiceberg_error CC ≤ 10

---

## Phase 6: User Story 4 - Split God Modules (Priority: P1)

**Goal**: Split plugin_registry.py (1230 lines) and oci/client.py (1389 lines) into focused modules
**Independent Test**: No file exceeds 400 lines, all tests pass
**Requirement**: FR-003, FR-004 (12B-ARCH-003, 12B-ARCH-004)

### Implementation for US4 - Plugin Registry Split

- [ ] T036 [P] [US4] Create packages/floe-core/src/floe_core/plugins/discovery.py (~200 lines)
- [ ] T037 [P] [US4] Create packages/floe-core/src/floe_core/plugins/loader.py (~200 lines)
- [ ] T038 [P] [US4] Create packages/floe-core/src/floe_core/plugins/lifecycle.py (~250 lines)
- [ ] T039 [P] [US4] Create packages/floe-core/src/floe_core/plugins/dependencies.py (~200 lines)
- [ ] T040 [US4] Refactor packages/floe-core/src/floe_core/plugin_registry.py to facade (~400 lines)
- [ ] T041 [US4] Update packages/floe-core/src/floe_core/plugins/__init__.py with re-exports
- [ ] T042 [US4] Run `pytest packages/floe-core/tests/ -k plugin` to verify all pass

### Implementation for US4 - OCI Client Split

- [ ] T043 [P] [US4] Create packages/floe-core/src/floe_core/oci/manifest.py (~400 lines)
- [ ] T044 [P] [US4] Create packages/floe-core/src/floe_core/oci/layers.py (~400 lines)
- [ ] T045 [US4] Refactor packages/floe-core/src/floe_core/oci/client.py to facade (~400 lines)
- [ ] T046 [US4] Update packages/floe-core/src/floe_core/oci/__init__.py with re-exports
- [ ] T047 [US4] Run `pytest packages/floe-core/tests/ -k oci` to verify all pass

**Checkpoint**: God modules split - all files ≤ 400 lines

---

## Phase 7: User Story 5 - Pin Critical Dependencies (Priority: P1)

**Goal**: Pin remaining unpinned dependencies with upper bounds
**Independent Test**: grep -r "pydantic>=" packages/*/pyproject.toml | grep -v "<" returns empty
**Requirement**: FR-015, FR-016, FR-017 (12B-DEP)

*Note: Core dependencies already pinned in Phase 2. This phase covers remaining packages.*

### Implementation for US5

- [ ] T048 [P] [US5] Pin pyarrow>=22.0.0,<23.0 in packages/floe-iceberg/pyproject.toml
- [ ] T049 [P] [US5] Pin structlog>=25.0,<26.0 in packages/floe-core/pyproject.toml
- [ ] T050 [P] [US5] Pin click>=8.3.0,<9.0 in packages/floe-core/pyproject.toml
- [ ] T051 [P] [US5] Pin httpx>=0.28.0,<1.0 in plugins/floe-catalog-polaris/pyproject.toml
- [ ] T052 [US5] Run `uv sync --all-packages` to verify dependency resolution
- [ ] T053 [US5] Run `pip-audit` to verify 0 vulnerabilities
- [ ] T054 [US5] [FR-018] Audit floe-cli package usage; deprecate and remove if unused
- [ ] T054a [US5] [FR-016] Verify all dependencies are within 1 major version of latest

**Checkpoint**: All dependencies pinned with upper bounds

---

## Phase 8: User Story 6 - Increase Test Coverage (Priority: P1)

**Goal**: CLI RBAC and Plugin ABCs at ≥80% coverage
**Independent Test**: pytest --cov=floe_core.cli.rbac shows ≥80%
**Requirement**: FR-011, FR-012, FR-013 (12B-TEST-002, 12B-TEST-003, 12B-TEST-005)

### Tests for US6 - CLI RBAC Coverage

- [ ] T055 [P] [US6] Add tests for audit_command in packages/floe-core/tests/unit/cli/rbac/test_audit.py
- [ ] T056 [P] [US6] Add tests for validate_command in packages/floe-core/tests/unit/cli/rbac/test_validate.py
- [ ] T057 [P] [US6] Add tests for diff_command in packages/floe-core/tests/unit/cli/rbac/test_diff.py
- [ ] T058 [P] [US6] Add tests for apply_command in packages/floe-core/tests/unit/cli/rbac/test_apply.py
- [ ] T059 [US6] Verify CLI RBAC coverage ≥80% with `pytest --cov=floe_core.cli.rbac`

### Tests for US6 - Plugin ABC Coverage

- [ ] T060 [P] [US6] Create BasePluginTests in testing/base_classes/base_plugin_tests.py
- [ ] T061 [P] [US6] Add tests for ComputePlugin ABC in tests/contract/test_compute_plugin_abc.py
- [ ] T062 [P] [US6] Add tests for OrchestratorPlugin ABC in tests/contract/test_orchestrator_plugin_abc.py
- [ ] T063 [P] [US6] Add tests for CatalogPlugin ABC in tests/contract/test_catalog_plugin_abc.py
- [ ] T064 [US6] Verify Plugin ABC coverage ≥80%

### Requirement Markers

- [ ] T065 [US6] Add @pytest.mark.requirement() to all tests missing markers
- [ ] T066 [US6] Run traceability check to verify 100% marker coverage

**Checkpoint**: CLI RBAC ≥80%, Plugin ABCs ≥80%, 100% requirement markers

---

## Phase 9: User Story 7 - Reduce Remaining High Complexity (Priority: P2)

**Goal**: Refactor 7 HIGH complexity functions to CC ≤12
**Independent Test**: Complexity analysis shows max CC ≤ 12
**Requirement**: FR-007, FR-008 (12B-CX-002-008)

### Implementation for US7

- [ ] T067 [P] [US7] Refactor __getattr__ in packages/floe-core/src/floe_core/rbac/__init__.py (CC 18→12)
- [ ] T068 [P] [US7] Refactor audit_command in packages/floe-core/src/floe_core/cli/rbac/audit.py (CC 18→12)
- [ ] T069 [P] [US7] Refactor validate_security_policy_not_weakened in packages/floe-core/src/floe_core/schemas/validation.py (CC 17→12)
- [ ] T070 [P] [US7] Refactor enforce in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py (CC 17→12)
- [ ] T071 [P] [US7] Refactor validate in plugins/floe-identity-keycloak/src/floe_identity_keycloak/token_validator.py (CC 17→12)
- [ ] T072 [P] [US7] Refactor list_secrets in plugins/floe-secrets-infisical/src/floe_secrets_infisical/plugin.py (CC 16→12)
- [ ] T073 [P] [US7] Refactor pull in packages/floe-core/src/floe_core/oci/client.py (CC 15→12)
- [ ] T074 [US7] Run complexity analysis to verify all functions CC ≤ 12
- [ ] T075 [US7] Run full test suite to verify no regressions

### Nesting Depth Reduction (FR-008)

- [ ] T075a [P] [FR-008] Identify top 5 functions with nesting depth >4 using complexity analysis
- [ ] T075b [P] [FR-008] Refactor high-nesting functions by extracting inner loops to named methods
- [ ] T075c [FR-008] Verify all functions have nesting depth ≤4

### Long Function Review (FR-009)

- [ ] T075d [P] [FR-009] List all functions >100 lines in floe-core and plugins
- [ ] T075e [P] [FR-009] Review and extract opportunities from long functions
- [ ] T075f [FR-009] Verify no functions exceed 100 lines without documented justification

**Checkpoint**: All HIGH complexity functions reduced to CC ≤ 12, nesting depth ≤4, long functions reviewed

---

## Phase 10: User Story 8 - Reduce Test Duplication (Priority: P2)

**Goal**: Reduce test duplication from 31.6% to ≤15%
**Independent Test**: Test duplication analysis shows ≤15%
**Requirement**: FR-014 (12B-TEST-006, 12B-TEST-007)

### Implementation for US8

- [ ] T076 [P] [US8] Create BasePluginDiscoveryTests in testing/base_classes/base_plugin_discovery_tests.py
- [ ] T077 [P] [US8] Create BaseHealthCheckTests in testing/base_classes/base_health_check_tests.py
- [ ] T078 [US8] Migrate Keycloak discovery tests to inherit BasePluginDiscoveryTests
- [ ] T079 [US8] Migrate Infisical discovery tests to inherit BasePluginDiscoveryTests
- [ ] T080 [P] [US8] Extract audit event fixtures to packages/floe-core/tests/conftest.py
- [ ] T081 [P] [US8] Parametrize dry-run tests in packages/floe-core/tests/
- [ ] T082 [US8] Run test duplication analysis to verify ≤15%
- [ ] T083 [US8] Run full test suite to verify no regressions

**Checkpoint**: Test duplication ≤15% - tests DRY

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and documentation

### Architecture Refinement (12B-ARCH-005-007)

- [ ] T084 [P] Reduce re-exports in submodule __init__.py files
- [ ] T085 [P] Update packages/floe-core/src/floe_core/__init__.py to export ≤15 symbols
- [ ] T085a [P] [FR-005] Audit submodule __init__.py files to export only public API symbols
- [ ] T085b [P] [FR-005] Remove private symbol exports from schemas/__init__.py
- [ ] T085c [P] [FR-005] Remove private symbol exports from plugins/__init__.py
- [ ] T085d [P] [FR-005] Remove private symbol exports from oci/__init__.py

### TODO Cleanup (12B-TODO-001-003)

- [ ] T086 [P] Document SORT compaction TODO in packages/floe-iceberg/src/floe_iceberg/compaction.py:383
- [ ] T087 [P] Document ORAS connectivity TODO in packages/floe-core/src/floe_core/oci/client.py:1257
- [ ] T088 [P] Replace PyIceberg issue "XXX" with real number in packages/floe-iceberg/src/floe_iceberg/manager.py:61

### Performance Hardening (12B-PERF-001-002)

- [ ] T089 Add max_resources validation to packages/floe-core/src/floe_core/rbac/diff.py:204
- [ ] T090 Optimize string concatenation in packages/floe-core/src/floe_core/rbac/diff.py:68-113

### Final Verification

- [ ] T091 Run `/tech-debt-review --all` to verify debt score ≥90
- [ ] T092 Run `make check` to verify all CI checks pass
- [ ] T093 Run quickstart.md validation to verify refactoring steps documented

**Checkpoint**: Debt score 90/100 - Epic 12B complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all code changes
- **Phase 3-5 (P0 Stories)**: Depend on Phase 2 - Can run in parallel
  - US1 (circular dep) should complete before US4 (god modules) for clean separation
- **Phase 6-8 (P1 Stories)**: Depend on Phase 2 - Can run in parallel
- **Phase 9-10 (P2 Stories)**: Depend on Phase 2 - Can run in parallel
- **Phase 11 (Polish)**: Depends on all story phases

### User Story Dependencies

| Story | Depends On | Reason |
|-------|------------|--------|
| US1 (Circular Dep) | Phase 2 | Dependencies pinned first |
| US2 (Skipped Tests) | Phase 2 | Dependencies pinned first |
| US3 (Critical CC) | Phase 2 | Dependencies pinned first |
| US4 (God Modules) | US1 | Clean separation requires circular dep resolved |
| US5 (Dep Pinning) | Phase 2 | Extends foundational pinning |
| US6 (Coverage) | Phase 2 | Can start after pinning |
| US7 (High CC) | Phase 2 | Can start after pinning |
| US8 (Duplication) | US6 | Base classes needed first |

### Parallel Opportunities

Within each phase, tasks marked [P] can run in parallel:
- Phase 2: T004-T010 (all dependency pins)
- Phase 6: T036-T039 (plugin modules), T043-T044 (OCI modules)
- Phase 8: T055-T058 (CLI tests), T060-T063 (ABC tests)
- Phase 9: T067-T073 (all complexity reductions)
- Phase 10: T076-T077 (base classes), T080-T081 (fixtures)

---

## Parallel Example: Phase 6 (God Module Split)

```bash
# Launch plugin module extractions in parallel:
Task: "Create packages/floe-core/src/floe_core/plugins/discovery.py (~200 lines)"
Task: "Create packages/floe-core/src/floe_core/plugins/loader.py (~200 lines)"
Task: "Create packages/floe-core/src/floe_core/plugins/lifecycle.py (~250 lines)"
Task: "Create packages/floe-core/src/floe_core/plugins/dependencies.py (~200 lines)"

# Then sequentially:
Task: "Refactor packages/floe-core/src/floe_core/plugin_registry.py to facade (~400 lines)"
```

---

## Implementation Strategy

### Critical Path (P0 Stories First)

1. Complete Phase 1-2 (Setup + Dependencies) → Foundation ready
2. Complete US1 → Circular dependency resolved
3. Complete US2 → Zero skipped tests
4. Complete US3 → Critical complexity resolved
5. **CHECKPOINT**: Debt score should be ~80/100

### Incremental Delivery

| Milestone | Stories Complete | Target Debt Score |
|-----------|------------------|-------------------|
| Foundation | - | 74 (baseline) |
| P0 Complete | US1, US2, US3 | 80 |
| P1 Complete | US4, US5, US6 | 85 |
| P2 Complete | US7, US8 | 88 |
| Polish Complete | All | 90 |

---

## Summary

| Phase | Tasks | Parallel | Story |
|-------|-------|----------|-------|
| Setup | 3 | 2 | - |
| Foundational | 9 | 7 | - |
| US1 (Circular Dep) | 10 | 0 | P0 |
| US2 (Skipped Tests) | 7 | 0 | P0 |
| US3 (Critical CC) | 6 | 0 | P0 |
| US4 (God Modules) | 12 | 6 | P1 |
| US5 (Dep Pinning) | 8 | 4 | P1 |
| US6 (Coverage) | 12 | 8 | P1 |
| US7 (High CC) + FR-008/009 | 15 | 11 | P2 |
| US8 (Duplication) | 8 | 4 | P2 |
| Polish + FR-005 | 14 | 9 | - |
| **Total** | **104** | **51** | **8 stories** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [USn] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate and run tech debt review
- All refactorings maintain backward compatibility via re-exports
