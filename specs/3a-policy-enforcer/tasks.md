# Tasks: Policy Enforcer Core (Epic 3A)

**Input**: Design documents from `/specs/3a-policy-enforcer/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Monorepo package**: `packages/floe-core/src/floe_core/` (source)
- **Unit tests**: `packages/floe-core/tests/unit/enforcement/`
- **Integration tests**: `packages/floe-core/tests/integration/enforcement/`
- **Contract tests**: `tests/contract/` (root-level, cross-package)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and module structure

- [ ] T001 Create enforcement module directory structure at `packages/floe-core/src/floe_core/enforcement/`
- [ ] T002 [P] Create `packages/floe-core/src/floe_core/enforcement/__init__.py` with public exports
- [ ] T003 [P] Create test directory structure at `packages/floe-core/tests/unit/enforcement/` and `packages/floe-core/tests/integration/enforcement/`
- [ ] T004 [P] Create `packages/floe-core/tests/unit/enforcement/conftest.py` with shared fixtures

---

## Phase 2: Foundational (Blocking Prerequisites) - User Story 2

**Purpose**: Schema foundation that MUST be complete before PolicyEnforcer implementation

**⚠️ CRITICAL**: No PolicyEnforcer work can begin until schemas are complete

### Goal: Extend GovernanceConfig with NamingConfig and QualityGatesConfig

**Independent Test**: Validate Pydantic models accept/reject correct configurations

### Tests for User Story 2 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T005 [P] [US2] Unit test for NamingConfig validation in `packages/floe-core/tests/unit/enforcement/test_governance_schemas.py`
- [ ] T006 [P] [US2] Unit test for QualityGatesConfig validation in `packages/floe-core/tests/unit/enforcement/test_governance_schemas.py`
- [ ] T007 [P] [US2] Unit test for LayerThresholds validation in `packages/floe-core/tests/unit/enforcement/test_governance_schemas.py`
- [ ] T008 [P] [US2] Unit test for GovernanceConfig extension in `packages/floe-core/tests/unit/enforcement/test_governance_schemas.py`
- [ ] T009 [P] [US2] Unit test for policy inheritance strengthening rules in `packages/floe-core/tests/unit/enforcement/test_policy_inheritance.py`
- [ ] T010 [P] [US2] Contract test for GovernanceConfig schema stability in `tests/contract/test_governance_schema_stability.py`

### Implementation for User Story 2

- [ ] T011 [P] [US2] Create NamingConfig Pydantic model in `packages/floe-core/src/floe_core/schemas/governance.py`
- [ ] T012 [P] [US2] Create QualityGatesConfig Pydantic model in `packages/floe-core/src/floe_core/schemas/governance.py`
- [ ] T013 [P] [US2] Create LayerThresholds Pydantic model in `packages/floe-core/src/floe_core/schemas/governance.py`
- [ ] T014 [US2] Extend GovernanceConfig in `packages/floe-core/src/floe_core/schemas/manifest.py` with naming and quality_gates fields (depends on T011-T013)
- [ ] T015 [US2] Add strength constants for naming.enforcement in `packages/floe-core/src/floe_core/schemas/validation.py`
- [ ] T016 [US2] Extend validate_security_policy_not_weakened() for NamingConfig fields in `packages/floe-core/src/floe_core/schemas/validation.py`
- [ ] T017 [US2] Extend validate_security_policy_not_weakened() for QualityGatesConfig fields in `packages/floe-core/src/floe_core/schemas/validation.py`
- [ ] T018 [US2] Export JSON Schema for GovernanceConfig to `specs/3a-policy-enforcer/contracts/governance-schema.json`
- [ ] T019 [US2] Update `packages/floe-core/src/floe_core/schemas/__init__.py` exports

**Checkpoint**: Foundation ready - GovernanceConfig extended, inheritance validation works

---

## Phase 3: User Story 1 - Policy Evaluation at Compile Time (Priority: P1) 🎯 MVP

**Goal**: Implement PolicyEnforcer core class and integrate into compilation pipeline

**Independent Test**: Compile a dbt project with policy violations, verify compilation fails with actionable errors

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T020 [P] [US1] Unit test for EnforcementResult model in `packages/floe-core/tests/unit/enforcement/test_result.py`
- [ ] T021 [P] [US1] Unit test for Violation model in `packages/floe-core/tests/unit/enforcement/test_result.py`
- [ ] T022 [P] [US1] Unit test for PolicyEnforcementError in `packages/floe-core/tests/unit/enforcement/test_errors.py`
- [ ] T023 [P] [US1] Unit test for PolicyEnforcer.enforce() orchestration in `packages/floe-core/tests/unit/enforcement/test_policy_enforcer.py`
- [ ] T024 [P] [US1] Contract test for EnforcementResult schema in `tests/contract/test_enforcement_result_schema.py`

### Implementation for User Story 1

- [ ] T025 [P] [US1] Create Violation Pydantic model in `packages/floe-core/src/floe_core/enforcement/result.py`
- [ ] T026 [P] [US1] Create EnforcementSummary Pydantic model in `packages/floe-core/src/floe_core/enforcement/result.py`
- [ ] T027 [US1] Create EnforcementResult Pydantic model in `packages/floe-core/src/floe_core/enforcement/result.py` (depends on T025, T026)
- [ ] T028 [US1] Create PolicyEnforcementError exception in `packages/floe-core/src/floe_core/enforcement/errors.py`
- [ ] T029 [US1] Implement PolicyEnforcer class skeleton in `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py`
- [ ] T030 [US1] Implement PolicyEnforcer.enforce() orchestrator method (depends on T029)
- [ ] T031 [US1] Add structlog audit logging to PolicyEnforcer (depends on T030)
- [ ] T032 [US1] Add OpenTelemetry span creation to PolicyEnforcer (depends on T30)
- [ ] T033 [US1] Export PolicyEnforcer in `packages/floe-core/src/floe_core/enforcement/__init__.py`

**Checkpoint**: PolicyEnforcer core exists, can be called with dbt manifest and GovernanceConfig

---

## Phase 4: User Story 3 - Naming Convention Enforcement (Priority: P2)

**Goal**: Implement naming convention validation with medallion, kimball, and custom patterns

**Independent Test**: Validate models against each naming pattern, verify correct pass/fail with suggestions

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T034 [P] [US3] Unit test for medallion pattern regex in `packages/floe-core/tests/unit/enforcement/test_naming_validator.py`
- [ ] T035 [P] [US3] Unit test for kimball pattern regex in `packages/floe-core/tests/unit/enforcement/test_naming_validator.py`
- [ ] T036 [P] [US3] Unit test for custom pattern validation (including conditional: custom_patterns required when pattern=custom) in `packages/floe-core/tests/unit/enforcement/test_naming_validator.py`
- [ ] T037 [P] [US3] Unit test for ReDoS protection in custom patterns in `packages/floe-core/tests/unit/enforcement/test_naming_validator.py`
- [ ] T038 [P] [US3] Unit test for NamingValidator.validate() method in `packages/floe-core/tests/unit/enforcement/test_naming_validator.py`
- [ ] T039 [P] [US3] Unit test for remediation suggestions in `packages/floe-core/tests/unit/enforcement/test_naming_validator.py`

### Implementation for User Story 3

- [ ] T040 [P] [US3] Define MEDALLION_PATTERN constant and DOCUMENTATION_URLS base in `packages/floe-core/src/floe_core/enforcement/patterns.py`
- [ ] T041 [P] [US3] Define KIMBALL_PATTERN constant in `packages/floe-core/src/floe_core/enforcement/patterns.py`
- [ ] T042 [US3] Implement custom pattern validation with ReDoS protection in `packages/floe-core/src/floe_core/enforcement/patterns.py` (depends on T040, T041)
- [ ] T043 [US3] Create NamingValidator class in `packages/floe-core/src/floe_core/enforcement/validators/naming.py`
- [ ] T044 [US3] Implement NamingValidator.validate() method (depends on T043)
- [ ] T045 [US3] Implement remediation suggestion generation for naming violations (depends on T044)
- [ ] T046 [US3] Wire NamingValidator into PolicyEnforcer.enforce() (depends on T044, T030)

**Checkpoint**: Naming validation works for medallion, kimball, and custom patterns

---

## Phase 5: User Story 4 - Test Coverage Enforcement (Priority: P2)

**Goal**: Implement column-level test coverage calculation and enforcement

**Independent Test**: Calculate coverage from dbt manifest, verify threshold enforcement per layer

### Tests for User Story 4 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T047 [P] [US4] Unit test for dbt manifest column parsing in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`
- [ ] T048 [P] [US4] Unit test for dbt manifest test parsing in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`
- [ ] T049 [P] [US4] Unit test for column-level coverage calculation in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`
- [ ] T050 [P] [US4] Unit test for layer detection (bronze/silver/gold) in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`
- [ ] T051 [P] [US4] Unit test for layer-specific threshold checking in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`
- [ ] T052 [P] [US4] Unit test for coverage gap suggestions in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`

### Implementation for User Story 4

- [ ] T053 [US4] Create CoverageValidator class in `packages/floe-core/src/floe_core/enforcement/validators/coverage.py`
- [ ] T054 [US4] Implement dbt manifest column extraction (depends on T053)
- [ ] T055 [US4] Implement dbt manifest test extraction and mapping to columns (depends on T054)
- [ ] T056 [US4] Implement column-level coverage calculation formula (depends on T055)
- [ ] T057 [US4] Implement layer detection from model name prefix (depends on T053)
- [ ] T058 [US4] Implement layer-specific threshold checking (depends on T056, T057)
- [ ] T059 [US4] Implement coverage gap suggestion generation (depends on T058)
- [ ] T060 [US4] Wire CoverageValidator into PolicyEnforcer.enforce() (depends on T058, T030)

**Checkpoint**: Coverage validation works with layer-specific thresholds

---

## Phase 6: User Story 5 - Documentation Validation (Priority: P2)

**Goal**: Implement documentation validation for model and column descriptions

**Independent Test**: Validate dbt manifests with varying documentation completeness

### Tests for User Story 5 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T061 [P] [US5] Unit test for model description detection in `packages/floe-core/tests/unit/enforcement/test_documentation_validator.py`
- [ ] T062 [P] [US5] Unit test for column description detection in `packages/floe-core/tests/unit/enforcement/test_documentation_validator.py`
- [ ] T063 [P] [US5] Unit test for placeholder description detection (TBD, TODO) in `packages/floe-core/tests/unit/enforcement/test_documentation_validator.py`
- [ ] T064 [P] [US5] Unit test for documentation template generation in `packages/floe-core/tests/unit/enforcement/test_documentation_validator.py`

### Implementation for User Story 5

- [ ] T065 [US5] Create DocumentationValidator class in `packages/floe-core/src/floe_core/enforcement/validators/documentation.py`
- [ ] T066 [US5] Implement model description check (depends on T065)
- [ ] T067 [US5] Implement column description check (depends on T065)
- [ ] T068 [US5] Implement placeholder description detection (depends on T066, T067)
- [ ] T069 [US5] Implement documentation template suggestion generation (depends on T068)
- [ ] T070 [US5] Wire DocumentationValidator into PolicyEnforcer.enforce() (depends on T068, T030)

**Checkpoint**: Documentation validation works for models and columns

---

## Phase 7: User Story 1 (Continued) - Pipeline Integration (Priority: P1)

**Goal**: Integrate PolicyEnforcer into Stage 4 (ENFORCE) of compilation pipeline

**Independent Test**: Run `floe compile` with policy violations, verify compilation blocks

### Tests for User Story 1 (Pipeline) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T071 [P] [US1] Integration test for ENFORCE stage in `packages/floe-core/tests/integration/enforcement/test_pipeline_enforcement.py`
- [ ] T072 [P] [US1] Integration test for strict mode blocking in `packages/floe-core/tests/integration/enforcement/test_pipeline_enforcement.py`
- [ ] T073 [P] [US1] Integration test for warn mode logging in `packages/floe-core/tests/integration/enforcement/test_pipeline_enforcement.py`

### Implementation for User Story 1 (Pipeline)

- [ ] T074 [US1] Implement ENFORCE stage in `packages/floe-core/src/floe_core/compilation/stages.py` (depends on T030, T046, T060, T070)
- [ ] T075 [US1] Handle enforcement result (block or warn) based on enforcement level (depends on T074)
- [ ] T076 [US1] Emit OTel span attributes for enforcement result (depends on T075)

**Checkpoint**: PolicyEnforcer runs during `floe compile` at Stage 4

---

## Phase 8: User Story 7 - Dry-Run Mode (Priority: P3)

**Goal**: Add `--dry-run` flag to preview violations without blocking compilation

**Independent Test**: Run `floe compile --dry-run` with violations, verify report without block

### Tests for User Story 7 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T077 [P] [US7] Unit test for dry-run flag handling in `packages/floe-core/tests/unit/enforcement/test_dry_run.py`
- [ ] T078 [P] [US7] Integration test for dry-run mode output in `packages/floe-core/tests/integration/enforcement/test_dry_run.py`

### Implementation for User Story 7

- [ ] T079 [US7] Add `--dry-run` flag to CLI compile command in `packages/floe-core/src/floe_core/cli/compile.py`
- [ ] T080 [US7] Pass dry-run flag through compilation pipeline (depends on T079)
- [ ] T081 [US7] Modify PolicyEnforcer to respect dry-run mode (depends on T080)
- [ ] T082 [US7] Generate dry-run report output format (depends on T081)

**Checkpoint**: Dry-run mode shows violations without blocking

---

## Phase 9: User Story 6 - Audit Logging (Priority: P3)

**Goal**: Add compliance audit logging with structured context

**Independent Test**: Run policy validation, verify structured log output

### Tests for User Story 6 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T083 [P] [US6] Unit test for audit log fields in `packages/floe-core/tests/unit/enforcement/test_audit_logging.py`
- [ ] T084 [P] [US6] Unit test for OTel span events in `packages/floe-core/tests/unit/enforcement/test_audit_logging.py`

### Implementation for User Story 6

- [ ] T085 [US6] Add policy decision logging with required audit fields to PolicyEnforcer
- [ ] T086 [US6] Add violation logging with required audit fields (depends on T085)
- [ ] T087 [US6] Emit OTel span events for violations (depends on T086)

**Checkpoint**: All policy decisions logged with audit context

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T088 [P] Update `packages/floe-core/src/floe_core/enforcement/__init__.py` with all public exports
- [ ] T089 [P] Verify JSON Schema exports match Pydantic models
- [ ] T090 Code review for security patterns (no shell=True, no eval, input validation)
- [ ] T091 Performance validation: <5s for 500 dbt models benchmark
- [ ] T092 [P] Run quickstart.md validation - verify examples work
- [ ] T093 Verify OTel span naming follows conventions
- [ ] T094 [P] [US1] Unit test for bypass prevention: verify strict mode cannot be overridden by env vars, CLI flags, or floe.yaml in `packages/floe-core/tests/unit/enforcement/test_bypass_prevention.py`
- [ ] T095 [P] [US4] Unit test for zero-column edge case: verify models with 0 columns use configured behavior (100% or N/A) in `packages/floe-core/tests/unit/enforcement/test_coverage_validator.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational/US2 (Phase 2)**: Depends on Setup - BLOCKS all other user stories
- **US1 Core (Phase 3)**: Depends on Foundational
- **US3 Naming (Phase 4)**: Depends on US1 Core (PolicyEnforcer skeleton)
- **US4 Coverage (Phase 5)**: Depends on US1 Core (PolicyEnforcer skeleton)
- **US5 Documentation (Phase 6)**: Depends on US1 Core (PolicyEnforcer skeleton)
- **US1 Pipeline (Phase 7)**: Depends on US3, US4, US5 (all validators)
- **US7 Dry-Run (Phase 8)**: Depends on US1 Pipeline
- **US6 Audit (Phase 9)**: Depends on US1 Core
- **Polish (Phase 10)**: Depends on all prior phases

### User Story Dependencies

```
US2 (Foundational) ─────────────────────┐
                                        ▼
                                   US1 Core
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           ▼                            ▼                            ▼
        US3 Naming                 US4 Coverage               US5 Documentation
           │                            │                            │
           └────────────────────────────┼────────────────────────────┘
                                        ▼
                                  US1 Pipeline
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
                    US7 Dry-Run                   US6 Audit
```

### Parallel Opportunities

- **Phase 1**: All tasks marked [P] can run in parallel
- **Phase 2**: Tests (T005-T010) can run in parallel; models (T011-T013) can run in parallel
- **Phase 3**: Tests (T020-T024) can run in parallel; result models (T025-T026) can run in parallel
- **Phases 4-6**: Can run in parallel after US1 Core completes (different validator files)
- **Phase 7-9**: Sequential - each builds on previous

---

## Task Summary

| Phase | User Story | Task Count | Priority |
|-------|------------|------------|----------|
| 1 | Setup | 4 | - |
| 2 | US2 (Foundational) | 15 | P1 |
| 3 | US1 (Core) | 14 | P1 |
| 4 | US3 (Naming) | 13 | P2 |
| 5 | US4 (Coverage) | 14 | P2 |
| 6 | US5 (Documentation) | 10 | P2 |
| 7 | US1 (Pipeline) | 6 | P1 |
| 8 | US7 (Dry-Run) | 6 | P3 |
| 9 | US6 (Audit) | 5 | P3 |
| 10 | Polish | 8 | - |
| **Total** | | **95** | |

---

## Implementation Strategy

### MVP First (P1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: US2 Foundational (schemas)
3. Complete Phase 3: US1 Core (PolicyEnforcer skeleton)
4. Complete Phases 4-6: US3, US4, US5 (validators) - can parallelize
5. Complete Phase 7: US1 Pipeline (integrate into compilation)
6. **STOP and VALIDATE**: Test compilation with policy enforcement

### Full Delivery (P1 + P2 + P3)

7. Complete Phase 8: US7 Dry-Run
8. Complete Phase 9: US6 Audit
9. Complete Phase 10: Polish
10. **FINAL VALIDATION**: All success criteria met

---

## Notes

- All tests follow TDD: write test FIRST, ensure it FAILS, then implement
- Each [P] task can run independently (different files)
- [US#] label maps task to spec.md user story for traceability
- Commit after each task or logical group
- @pytest.mark.requirement() on all tests for traceability
