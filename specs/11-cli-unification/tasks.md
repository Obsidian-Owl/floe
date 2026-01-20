# Tasks: CLI Unification

**Input**: Design documents from `/specs/11-cli-unification/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests included per TDD approach and constitution requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Include exact file paths in descriptions

## Path Conventions

- **Package**: `packages/floe-core/src/floe_core/cli/`
- **Tests**: `packages/floe-core/tests/unit/cli/`, `packages/floe-core/tests/integration/cli/`
- **Contract Tests**: `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and CLI framework migration

- [ ] T001 Add Click dependency to packages/floe-core/pyproject.toml
- [ ] T002 Create Click root group skeleton in packages/floe-core/src/floe_core/cli/main.py
- [ ] T003 [P] Add --version flag using importlib.metadata in packages/floe-core/src/floe_core/cli/main.py
- [ ] T004 [P] Implement error handling utilities in packages/floe-core/src/floe_core/cli/utils.py
- [ ] T005 Update packages/floe-core/src/floe_core/cli/__init__.py to export Click main

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create platform/ directory structure in packages/floe-core/src/floe_core/cli/platform/__init__.py
- [ ] T007 [P] Create rbac/ directory structure in packages/floe-core/src/floe_core/cli/rbac/__init__.py
- [ ] T008 [P] Create artifact/ directory structure in packages/floe-core/src/floe_core/cli/artifact/__init__.py
- [ ] T009 [P] Create data/ directory structure in packages/floe-core/src/floe_core/cli/data/__init__.py
- [ ] T010 Wire command groups into main.py in packages/floe-core/src/floe_core/cli/main.py
- [ ] T011 Capture RBAC baseline golden files for regression testing in tests/fixtures/cli/golden/

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Unified Platform Compile with Enforcement Export (Priority: P1) 🎯 MVP

**Goal**: Platform Team can run `floe platform compile` with enforcement report options to validate governance policies and export compliance reports

**Independent Test**: Run `floe platform compile --spec floe.yaml --manifest manifest.yaml --enforcement-report report.sarif --enforcement-format sarif` and verify SARIF file is created with valid content

### Tests for User Story 1

- [ ] T012 [P] [US1] Unit test for platform compile command in packages/floe-core/tests/unit/cli/test_platform_compile.py
- [ ] T013 [P] [US1] Contract test for compile output format in tests/contract/test_cli_compile_contract.py

### Implementation for User Story 1

- [ ] T014 [US1] Implement platform compile command skeleton in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T015 [US1] Add --spec and --manifest options to compile command in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T016 [US1] Add --output option for CompiledArtifacts path in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T017 [US1] Add --enforcement-report option in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T018 [US1] Add --enforcement-format option (json/sarif/html) in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T019 [US1] Implement directory creation for enforcement report path in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T020 [US1] Wire enforcement export to existing export functions in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T021 [US1] Add exit code handling (0 success, 1 failure) in packages/floe-core/src/floe_core/cli/platform/compile.py
- [ ] T022 [P] [US1] Implement platform test stub in packages/floe-core/src/floe_core/cli/platform/test.py
- [ ] T023 [P] [US1] Implement platform publish stub in packages/floe-core/src/floe_core/cli/platform/publish.py
- [ ] T024 [P] [US1] Implement platform deploy stub in packages/floe-core/src/floe_core/cli/platform/deploy.py
- [ ] T025 [P] [US1] Implement platform status stub in packages/floe-core/src/floe_core/cli/platform/status.py
- [ ] T026 [US1] Integration test compile with real files in packages/floe-core/tests/integration/cli/test_compile_integration.py

**Checkpoint**: Platform compile with enforcement export is fully functional

---

## Phase 4: User Story 2 - RBAC Command Migration (Priority: P2)

**Goal**: All RBAC management commands (generate, validate, audit, diff) work from unified CLI without changing existing workflows

**Independent Test**: Run each RBAC subcommand and verify output matches pre-migration behavior via golden file comparison

### Tests for User Story 2

- [ ] T027 [P] [US2] Unit tests for rbac generate in packages/floe-core/tests/unit/cli/test_rbac_generate.py
- [ ] T028 [P] [US2] Unit tests for rbac validate in packages/floe-core/tests/unit/cli/test_rbac_validate.py
- [ ] T029 [P] [US2] Unit tests for rbac audit in packages/floe-core/tests/unit/cli/test_rbac_audit.py
- [ ] T030 [P] [US2] Unit tests for rbac diff in packages/floe-core/tests/unit/cli/test_rbac_diff.py
- [ ] T031 [US2] Golden file regression tests in tests/contract/test_cli_rbac_output_contracts.py

### Implementation for User Story 2

- [ ] T032 [US2] Migrate rbac generate command to packages/floe-core/src/floe_core/cli/rbac/generate.py
- [ ] T033 [US2] Migrate rbac validate command to packages/floe-core/src/floe_core/cli/rbac/validate.py
- [ ] T034 [US2] Migrate rbac audit command to packages/floe-core/src/floe_core/cli/rbac/audit.py
- [ ] T035 [US2] Migrate rbac diff command to packages/floe-core/src/floe_core/cli/rbac/diff.py
- [ ] T036 [US2] Wire rbac commands into rbac group in packages/floe-core/src/floe_core/cli/rbac/__init__.py
- [ ] T037 [US2] Add optional kubernetes dependency error handling in packages/floe-core/src/floe_core/cli/rbac/audit.py
- [ ] T038 [US2] Integration test rbac with K8s in packages/floe-core/tests/integration/cli/test_rbac_integration.py
- [ ] T039 [US2] Verify golden file output equivalence in tests/contract/test_cli_rbac_output_contracts.py

**Checkpoint**: All RBAC commands work identically to floe-cli

---

## Phase 5: User Story 3 - Discoverable Command Help (Priority: P2)

**Goal**: New users can run `floe --help` and discover all available functionality without documentation

**Independent Test**: Run `floe --help`, `floe platform --help`, `floe rbac --help` and verify clear, complete help text

### Tests for User Story 3

- [ ] T040 [P] [US3] Unit test for help output completeness in packages/floe-core/tests/unit/cli/test_help.py
- [ ] T041 [P] [US3] Snapshot test for help text format in packages/floe-core/tests/unit/cli/test_help_snapshots.py

### Implementation for User Story 3

- [ ] T042 [US3] Add comprehensive docstrings to root group in packages/floe-core/src/floe_core/cli/main.py
- [ ] T043 [US3] Add comprehensive docstrings to platform group in packages/floe-core/src/floe_core/cli/platform/__init__.py
- [ ] T044 [US3] Add comprehensive docstrings to rbac group in packages/floe-core/src/floe_core/cli/rbac/__init__.py
- [ ] T045 [US3] Add comprehensive docstrings to artifact group in packages/floe-core/src/floe_core/cli/artifact/__init__.py
- [ ] T046 [US3] Add option help text to all commands in packages/floe-core/src/floe_core/cli/
- [ ] T047 [US3] Verify help response time <1s in packages/floe-core/tests/unit/cli/test_help.py

**Checkpoint**: CLI is fully discoverable via --help

---

## Phase 6: User Story 4 - Artifact Push Command Migration (Priority: P3)

**Goal**: Artifact push works from unified CLI for CI/CD pipelines

**Independent Test**: Run `floe artifact push` with valid artifacts and verify push succeeds

### Tests for User Story 4

- [ ] T048 [P] [US4] Unit test for artifact push in packages/floe-core/tests/unit/cli/test_artifact_push.py

### Implementation for User Story 4

- [ ] T049 [US4] Convert artifact push from argparse to Click in packages/floe-core/src/floe_core/cli/artifact/push.py
- [ ] T050 [US4] Add --artifact and --registry options in packages/floe-core/src/floe_core/cli/artifact/push.py
- [ ] T051 [US4] Wire artifact push into artifact group in packages/floe-core/src/floe_core/cli/artifact/__init__.py
- [ ] T052 [US4] Add environment variable authentication support in packages/floe-core/src/floe_core/cli/artifact/push.py

**Checkpoint**: Artifact push works from unified CLI

---

## Phase 7: User Story 5 - Data Team Compile Stub (Priority: P4)

**Goal**: Data Team has stub commands for future implementation

**Independent Test**: Run `floe compile --help` and verify command exists with appropriate help

### Tests for User Story 5

- [ ] T053 [P] [US5] Unit test for data team stub commands in packages/floe-core/tests/unit/cli/test_data_stubs.py

### Implementation for User Story 5

- [ ] T054 [P] [US5] Implement compile stub in packages/floe-core/src/floe_core/cli/data/compile.py
- [ ] T055 [P] [US5] Implement validate stub in packages/floe-core/src/floe_core/cli/data/validate.py
- [ ] T056 [P] [US5] Implement run stub in packages/floe-core/src/floe_core/cli/data/run.py
- [ ] T057 [P] [US5] Implement test stub in packages/floe-core/src/floe_core/cli/data/test.py
- [ ] T058 [US5] Wire data team commands into root group in packages/floe-core/src/floe_core/cli/main.py

**Checkpoint**: Data team stubs are in place

---

## Phase 8: Deprecation and Cleanup

**Purpose**: Deprecate floe-cli package and clean up

- [ ] T059 Remove floe-cli from workspace dependencies in pyproject.toml (root)
- [ ] T060 Add deprecation notice to packages/floe-cli/README.md
- [ ] T061 Remove floe-cli entry point by updating packages/floe-cli/pyproject.toml
- [ ] T062 Verify single floe entry point works in packages/floe-core/tests/integration/cli/test_entry_point.py

---

## Phase 9: Verification (Success Criteria)

**Purpose**: Verify all success criteria from spec

- [ ] T063 SC-001: Verify `floe --help` <1s performance in packages/floe-core/tests/integration/cli/test_performance.py
- [ ] T064 SC-002: Verify compile performance (500+ models <5s) in packages/floe-core/tests/integration/cli/test_performance.py
- [ ] T065 SC-003: Verify RBAC golden file equivalence in tests/contract/test_cli_rbac_output_contracts.py
- [ ] T066 SC-004: Verify no entry point conflicts in packages/floe-core/tests/integration/cli/test_entry_point.py
- [ ] T067 SC-005: Run full CLI test suite (make test-unit && make test-integration)
- [ ] T068 SC-006: Manual review of help text readability
- [ ] T069 SC-007: Verify existing compile functionality preserved in packages/floe-core/tests/integration/cli/test_compile_integration.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) should complete first (MVP, blocks Epic 3B)
  - US2-US3 (P2) can proceed in parallel after US1
  - US4 (P3) can proceed after foundation
  - US5 (P4) can proceed after foundation
- **Deprecation (Phase 8)**: Depends on all user stories being complete
- **Verification (Phase 9)**: Depends on Deprecation complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Benefits from US1/US2 for more complete help
- **User Story 4 (P3)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 5 (P4)**: Can start after Foundational (Phase 2) - No dependencies on other stories

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Core command before options
- Options before integration
- Story complete before verification

### Parallel Opportunities

- T003, T004 can run in parallel (Phase 1)
- T006, T007, T008, T009 can run in parallel (Phase 2)
- T012, T013 can run in parallel (US1 tests)
- T022, T023, T024, T025 can run in parallel (US1 platform stubs)
- T027, T028, T029, T030 can run in parallel (US2 tests)
- T040, T041 can run in parallel (US3 tests)
- T054, T055, T056, T057 can run in parallel (US5 stubs)
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 2 (RBAC Migration)

```bash
# Launch all tests for User Story 2 together:
Task: "Unit tests for rbac generate in packages/floe-core/tests/unit/cli/test_rbac_generate.py"
Task: "Unit tests for rbac validate in packages/floe-core/tests/unit/cli/test_rbac_validate.py"
Task: "Unit tests for rbac audit in packages/floe-core/tests/unit/cli/test_rbac_audit.py"
Task: "Unit tests for rbac diff in packages/floe-core/tests/unit/cli/test_rbac_diff.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Platform Compile)
4. **STOP and VALIDATE**: Test `floe platform compile` with enforcement export
5. **UNBLOCKS EPIC 3B**: Can now complete T066-T069 from Epic 3B

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → **Epic 3B unblocked**
3. Add User Story 2 → Test independently → RBAC migrated
4. Add User Story 3 → Test independently → Help complete
5. Add User Story 4 → Test independently → Artifact push migrated
6. Add User Story 5 → Test independently → Data team ready
7. Deprecation + Verification → Epic 11 complete

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- US1 completion is critical for unblocking Epic 3B
