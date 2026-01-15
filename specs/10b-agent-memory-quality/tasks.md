# Tasks: Agent Memory Validation & Quality

**Input**: Design documents from `/specs/10b-agent-memory-quality/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: TDD approach - tests written FIRST, verified to FAIL, then implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Includes exact file paths in descriptions

## Path Conventions

- **Project Root**: `devtools/agent-memory/`
- **Source**: `devtools/agent-memory/src/agent_memory/`
- **Tests**: `devtools/agent-memory/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test infrastructure and fixtures needed by all user stories

- [ ] T001 Create contract test directory at devtools/agent-memory/tests/contract/
- [ ] T002 [P] Create contract test conftest.py at devtools/agent-memory/tests/contract/conftest.py with mock_request fixture
- [ ] T003 [P] Update root conftest.py at devtools/agent-memory/tests/conftest.py with shared test utilities

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core fixtures that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create PayloadCapture fixture that mocks CogneeClient._make_request() and captures json_data in devtools/agent-memory/tests/contract/conftest.py
- [ ] T005 [P] Create TestDatasetFixture helper class in devtools/agent-memory/tests/conftest.py for unique dataset names
- [ ] T006 [P] Add pytest.mark.requirement decorator registration in devtools/agent-memory/tests/conftest.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Contract Test Protection (Priority: P1) :dart: MVP

**Goal**: Validate API field names against Cognee Cloud API specification to catch field name mismatches before merge

**Independent Test**: Run `pytest tests/contract/ -v` - all tests pass in < 5 seconds with zero network calls

**Requirements Covered**: FR-001, FR-002, FR-003, FR-004, FR-005 | SC-001, SC-006

### Tests for User Story 1 (TDD - Write FIRST, verify FAIL)

- [ ] T007 [P] [US1] Contract test for add_content textData field in devtools/agent-memory/tests/contract/test_cognee_api_contract.py (FR-001)
- [ ] T008 [P] [US1] Contract test for add_content datasetName field in devtools/agent-memory/tests/contract/test_cognee_api_contract.py (FR-002)
- [ ] T009 [P] [US1] Contract test for search searchType field in devtools/agent-memory/tests/contract/test_cognee_api_contract.py (FR-003)
- [ ] T010 [P] [US1] Contract test for search topK field in devtools/agent-memory/tests/contract/test_cognee_api_contract.py (FR-004)
- [ ] T011 [P] [US1] Contract test for cognify datasets field in devtools/agent-memory/tests/contract/test_cognee_api_contract.py (FR-005)

### Implementation for User Story 1

- [ ] T012 [US1] Verify existing add_content uses textData (not data) in devtools/agent-memory/src/agent_memory/cognee_client.py line ~408
- [ ] T013 [US1] Verify existing search uses searchType and topK in devtools/agent-memory/src/agent_memory/cognee_client.py line ~573-574
- [ ] T014 [US1] Run contract tests and confirm all pass in < 5 seconds

**Checkpoint**: Contract tests catch any future field name regressions. US1 complete and independently testable.

---

## Phase 4: User Story 2 - CogneeClient Unit Test Coverage (Priority: P1)

**Goal**: Achieve 80%+ coverage of CogneeClient with unit tests for payload construction and response parsing

**Independent Test**: Run `pytest tests/unit/test_cognee_client.py -v --cov=agent_memory.cognee_client` - 80%+ coverage

**Requirements Covered**: FR-014, FR-015, FR-008 | SC-002, SC-007

### Tests for User Story 2 (TDD - Write FIRST, verify FAIL)

- [ ] T015 [P] [US2] Unit test for search response parsing - direct list format in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-015)
- [ ] T016 [P] [US2] Unit test for search response parsing - dict with results in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-015)
- [ ] T017 [P] [US2] Unit test for search response parsing - dict with data in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-015)
- [ ] T018 [P] [US2] Unit test for search response parsing - nested search_result in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-015)
- [ ] T019 [P] [US2] Unit test for search response parsing - empty response in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-015)
- [ ] T020 [P] [US2] Unit test for memify SDK error handling in devtools/agent-memory/tests/unit/test_cli_memify.py (FR-008)
- [ ] T021 [P] [US2] Unit test for add_content payload construction in devtools/agent-memory/tests/unit/test_cognee_client.py
- [ ] T022 [P] [US2] Unit test for cognify payload construction in devtools/agent-memory/tests/unit/test_cognee_client.py
- [ ] T023 [P] [US2] Unit test for error handling - retryable status codes in devtools/agent-memory/tests/unit/test_cognee_client.py
- [ ] T024 [P] [US2] Unit test for error handling - non-retryable status codes in devtools/agent-memory/tests/unit/test_cognee_client.py

### Implementation for User Story 2

- [ ] T025 [US2] Verify response parsing handles all 5 formats in devtools/agent-memory/src/agent_memory/cognee_client.py lines ~598-615
- [ ] T026 [US2] Run unit tests with coverage report and verify 80%+ coverage

**Checkpoint**: CogneeClient has comprehensive unit tests. US2 complete and independently testable.

---

## Phase 5: User Story 3 - Content Searchability Verification (Priority: P2)

**Goal**: Integration tests verify synced content actually appears in search results, not just result counts

**Independent Test**: Run `pytest tests/integration/ -v` with Cognee Cloud access - content verification passes

**Requirements Covered**: FR-009, FR-010, FR-011, FR-012, FR-013, FR-016, FR-017, FR-018 | SC-003, SC-009, SC-010

### Tests for User Story 3 (TDD - Write FIRST)

- [ ] T027 [P] [US3] Integration test for content searchability with unique marker in devtools/agent-memory/tests/integration/test_sync_cycle.py (FR-016)
- [ ] T028 [P] [US3] Integration test for dataset isolation in devtools/agent-memory/tests/integration/test_dataset_isolation.py (FR-017)
- [ ] T029 [P] [US3] Integration test for verify flag in devtools/agent-memory/tests/integration/test_sync_cycle.py (FR-010)
- [ ] T030 [P] [US3] Unit test for verify=True parameter in add_content in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-009)
- [ ] T030a [P] [US3] Unit test for verify=False default behavior (no verification call) in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-009)
- [ ] T031 [P] [US3] Unit test for status polling in cognify in devtools/agent-memory/tests/unit/test_cognee_client.py (FR-012)

### Implementation for User Story 3

- [ ] T032 [US3] Add verify parameter (default=False, timeout=30s) to add_content method in devtools/agent-memory/src/agent_memory/cognee_client.py (FR-009)
- [ ] T033 [US3] Implement read-after-write verification logic in add_content in devtools/agent-memory/src/agent_memory/cognee_client.py (FR-010)
- [ ] T034 [US3] Add --verify flag to CLI sync command in devtools/agent-memory/src/agent_memory/cli.py (FR-011)
- [ ] T035 [US3] Add get_dataset_status method to CogneeClient in devtools/agent-memory/src/agent_memory/cognee_client.py (FR-012)
- [ ] T036 [US3] Add wait_for_completion parameter to cognify method in devtools/agent-memory/src/agent_memory/cognee_client.py (FR-012)
- [ ] T037 [US3] Implement status polling with configurable timeout (default=300 seconds per FR-013) in devtools/agent-memory/src/agent_memory/cognee_client.py (FR-013)
- [ ] T038 [US3] Update integration tests to use unique datasets with TestDatasetFixture in devtools/agent-memory/tests/integration/test_dataset_isolation.py (FR-017)
- [ ] T039 [US3] Add test dataset cleanup in teardown fixtures in devtools/agent-memory/tests/integration/conftest.py (FR-018)
- [ ] T040 [US3] Run integration tests and verify content searchability assertions pass

**Checkpoint**: Integration tests validate actual content, not just counts. US3 complete and independently testable.

---

## Phase 6: User Story 4 - Fix Verification Protocol (Priority: P2)

**Goal**: Document and execute verification protocol confirming the "dad jokes" bug fix works

**Independent Test**: Execute verification protocol - search returns floe content, not default values

**Requirements Covered**: FR-019 | SC-004

### Tests for User Story 4

- [ ] T041 [US4] Create verification protocol script/checklist in specs/10b-agent-memory-quality/verification-protocol.md (FR-019)

### Implementation for User Story 4

- [ ] T042 [US4] Document reset procedure in verification protocol
- [ ] T043 [US4] Document re-sync procedure with --verify flag in verification protocol
- [ ] T044 [US4] Document search validation criteria (must contain floe content, not "dad jokes") in verification protocol
- [ ] T045 [US4] Execute verification protocol and document results

**Checkpoint**: Bug fix is verified working. US4 complete.

---

## Phase 7: User Story 5 - API Quirks Documentation (Priority: P3)

**Goal**: Document Cognee API quirks in CLAUDE.md to prevent future mistakes

**Independent Test**: Documentation review - CLAUDE.md contains API quirks section with camelCase requirements

**Requirements Covered**: FR-006, FR-007, FR-020, FR-021 | SC-005, SC-008

### Implementation for User Story 5

- [ ] T046 [P] [US5] Add Cognee API camelCase requirements section to CLAUDE.md (FR-020)
- [ ] T047 [P] [US5] Add response format variations table to CLAUDE.md (FR-021)
- [ ] T048 [P] [US5] Document memify is SDK-only (not REST API) in CLAUDE.md (FR-006, FR-007)
- [ ] T049 [US5] Review documentation is findable and accurate

**Checkpoint**: Future developers can find API quirks documentation. US5 complete.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T050 Run full test suite: pytest tests/contract/ tests/unit/ tests/integration/ -v
- [ ] T051 [P] Verify contract tests execute in < 5 seconds (SC-006)
- [ ] T052 [P] Verify unit tests execute in < 30 seconds (SC-007)
- [ ] T053 Generate coverage report and verify 80%+ for CogneeClient (SC-002)
- [ ] T054 Run quickstart.md validation steps
- [ ] T055 Update specs/10b-agent-memory-quality/plan.md with completion status

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) and US2 (P1) can proceed in parallel
  - US3 (P2) depends on US1 contract tests existing (for regression prevention)
  - US4 (P2) can proceed after US3 implementation
  - US5 (P3) can proceed independently
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundational) ─────────────────────────────────────┐
    │                                                        │
    ├──────────────┬────────────────────────────────────────┤
    ▼              ▼                                        ▼
Phase 3 (US1)  Phase 4 (US2)                         Phase 7 (US5)
Contract Tests  Unit Tests                           Documentation
    │              │
    └──────┬───────┘
           ▼
    Phase 5 (US3)
    Integration Tests
           │
           ▼
    Phase 6 (US4)
    Verification Protocol
           │
           ▼
    Phase 8 (Polish)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Contract tests before unit tests (US1 → US2)
- Unit tests before integration tests (US2 → US3)
- All tests passing before verification (US3 → US4)

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel
- US1 and US2 can run in parallel (both P1, independent)
- US5 can run in parallel with US3/US4 (independent)
- All tests within a story marked [P] can run in parallel
- All implementation tasks within a story can run sequentially

---

## Parallel Example: User Story 1 Contract Tests

```bash
# Launch all contract tests together (Phase 3 tests):
Task: "Contract test for add_content textData field" (T007)
Task: "Contract test for add_content datasetName field" (T008)
Task: "Contract test for search searchType field" (T009)
Task: "Contract test for search topK field" (T010)
Task: "Contract test for cognify datasets field" (T011)
```

## Parallel Example: User Story 2 Unit Tests

```bash
# Launch all response parsing tests together (Phase 4 tests):
Task: "Unit test for search response parsing - direct list" (T015)
Task: "Unit test for search response parsing - dict with results" (T016)
Task: "Unit test for search response parsing - dict with data" (T017)
Task: "Unit test for search response parsing - nested search_result" (T018)
Task: "Unit test for search response parsing - empty response" (T019)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Contract Tests
4. Complete Phase 4: US2 - Unit Tests
5. **STOP and VALIDATE**: Run `pytest tests/contract/ tests/unit/ -v` - all pass, 80%+ coverage
6. Deploy/demo if ready - basic regression prevention in place

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Contract tests catch field name bugs (MVP!)
3. Add US2 → Unit tests provide 80%+ coverage
4. Add US3 → Integration tests verify content searchability
5. Add US4 → Verification protocol confirms bug fix
6. Add US5 → Documentation prevents future mistakes
7. Each story adds value without breaking previous stories

### Single Developer Strategy

Execute in priority order:
1. Phase 1 + Phase 2 (foundation)
2. Phase 3 (US1 - P1)
3. Phase 4 (US2 - P1)
4. Phase 5 (US3 - P2)
5. Phase 6 (US4 - P2)
6. Phase 7 (US5 - P3)
7. Phase 8 (polish)

---

## Requirement Traceability Matrix

| Task | FR | SC | Description |
|------|----|----|-------------|
| T007 | FR-001 | SC-001 | Contract test: textData field |
| T008 | FR-002 | SC-001 | Contract test: datasetName field |
| T009 | FR-003 | SC-001 | Contract test: searchType field |
| T010 | FR-004 | SC-001 | Contract test: topK field |
| T011 | FR-005 | SC-001 | Contract test: datasets field |
| T014 | - | SC-006 | Contract tests < 5 seconds |
| T015-T019 | FR-015 | SC-002 | Response parsing unit tests |
| T020 | FR-008 | - | Memify SDK error handling |
| T026 | FR-014 | SC-002 | 80%+ unit test coverage |
| T027 | FR-016 | SC-003 | Content searchability verification |
| T028 | FR-017 | SC-003 | Dataset isolation |
| T029 | FR-010 | SC-009 | Verify flag integration test |
| T030 | FR-009 | SC-009 | Verify=True unit test |
| T030a | FR-009 | SC-009 | Verify=False default behavior unit test |
| T032-T033 | FR-009, FR-010 | SC-009 | Verify parameter implementation |
| T034 | FR-011 | SC-009 | CLI --verify flag |
| T035-T037 | FR-012, FR-013 | SC-010 | Status polling implementation |
| T038 | FR-017 | SC-003 | Unique test datasets |
| T039 | FR-018 | SC-003 | Test dataset cleanup |
| T041-T045 | FR-019 | SC-004 | Verification protocol |
| T046 | FR-020 | SC-005 | CamelCase documentation |
| T047 | FR-021 | SC-005 | Response format documentation |
| T048 | FR-006, FR-007 | SC-008 | Memify SDK documentation |
| T051 | - | SC-006 | Contract tests < 5s validation |
| T052 | - | SC-007 | Unit tests < 30s validation |
| T053 | FR-014 | SC-002 | 80%+ coverage validation |

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests FAIL before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All tests must include `@pytest.mark.requirement()` decorator
