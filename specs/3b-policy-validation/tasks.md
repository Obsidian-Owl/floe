# Tasks: Policy Validation Enhancement (Epic 3B)

**Input**: Design documents from `/specs/3b-policy-validation/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Package**: `packages/floe-core/src/floe_core/`
- **Tests**: `packages/floe-core/tests/` (unit, integration) and `tests/contract/` (cross-package)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency setup

- [ ] T001 Add jinja2>=3.0 dependency to packages/floe-core/pyproject.toml
- [ ] T002 [P] Create exporters subpackage structure at packages/floe-core/src/floe_core/enforcement/exporters/__init__.py
- [ ] T003 [P] Create test directory structure at packages/floe-core/tests/unit/enforcement/exporters/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Extend Violation model with context fields (downstream_impact, first_detected, occurrences, override_applied) in packages/floe-core/src/floe_core/enforcement/result.py
- [ ] T005 Add CustomRule discriminated union model to packages/floe-core/src/floe_core/schemas/governance.py
- [ ] T006 [P] Add PolicyOverride model to packages/floe-core/src/floe_core/schemas/governance.py
- [ ] T007 Extend GovernanceConfig with custom_rules and policy_overrides fields in packages/floe-core/src/floe_core/schemas/governance.py
- [ ] T008 Add EnforcementResultSummary model for CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T009 Extend EnforcementSummary with semantic_violations, custom_rule_violations, overrides_applied in packages/floe-core/src/floe_core/enforcement/result.py
- [ ] T010 Add violations_by_model computed property to EnforcementResult in packages/floe-core/src/floe_core/enforcement/result.py
- [ ] T011 [P] Unit tests for CustomRule schema validation in packages/floe-core/tests/unit/schemas/test_custom_rule.py
- [ ] T012 [P] Unit tests for PolicyOverride schema validation in packages/floe-core/tests/unit/schemas/test_policy_override.py
- [ ] T013 Unit tests for extended Violation model in packages/floe-core/tests/unit/enforcement/test_result.py
- [ ] T013a [P] Unit tests for manifest version validation (malformed/unsupported dbt versions) in packages/floe-core/tests/unit/enforcement/test_manifest_validation.py

**Checkpoint**: Schema extensions complete - user story implementation can now begin

---

## Phase 3: User Story 1 - Semantic Model Validation (Priority: P1) MVP

**Goal**: Validate model references (ref(), source()) and detect circular dependencies at compile-time

**Independent Test**: Run `floe compile` on dbt project with misconfigured relationships, verify FLOE-E3xx errors are generated

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T014 [P] [US1] Unit test for SemanticValidator.validate_refs() in packages/floe-core/tests/unit/enforcement/validators/test_semantic_validator.py
- [ ] T015 [P] [US1] Unit test for SemanticValidator.detect_circular_deps() in packages/floe-core/tests/unit/enforcement/validators/test_semantic_validator.py
- [ ] T016 [P] [US1] Unit test for SemanticValidator.validate_sources() in packages/floe-core/tests/unit/enforcement/validators/test_semantic_validator.py

### Implementation for User Story 1

- [ ] T017 [US1] Create SemanticValidator class with validate() method in packages/floe-core/src/floe_core/enforcement/validators/semantic.py
- [ ] T018 [US1] Implement ref() resolution validation (FLOE-E301) using manifest nodes in packages/floe-core/src/floe_core/enforcement/validators/semantic.py
- [ ] T019 [US1] Implement circular dependency detection (FLOE-E302) using Kahn's algorithm in packages/floe-core/src/floe_core/enforcement/validators/semantic.py
- [ ] T020 [US1] Implement source() resolution validation (FLOE-E303) using manifest sources in packages/floe-core/src/floe_core/enforcement/validators/semantic.py
- [ ] T021 [US1] Register SemanticValidator in PolicyEnforcer.enforce() in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T022 [US1] Export SemanticValidator from enforcement module in packages/floe-core/src/floe_core/enforcement/__init__.py

**Checkpoint**: Semantic validation fully functional and testable independently

---

## Phase 4: User Story 2 - Custom Policy Rules (Priority: P1)

**Goal**: Define custom validation rules in manifest.yaml without writing Python code

**Independent Test**: Add custom_rules to manifest.yaml governance section, verify PolicyEnforcer applies them correctly

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T023 [P] [US2] Unit test for require_tags_for_prefix rule in packages/floe-core/tests/unit/enforcement/validators/test_custom_rules_validator.py
- [ ] T024 [P] [US2] Unit test for require_meta_field rule in packages/floe-core/tests/unit/enforcement/validators/test_custom_rules_validator.py
- [ ] T025 [P] [US2] Unit test for require_tests_of_type rule in packages/floe-core/tests/unit/enforcement/validators/test_custom_rules_validator.py
- [ ] T026 [P] [US2] Unit test for invalid custom rule syntax error handling in packages/floe-core/tests/unit/enforcement/validators/test_custom_rules_validator.py

### Implementation for User Story 2

- [ ] T027 [US2] Create CustomRuleValidator class with validate() method in packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py
- [ ] T028 [US2] Implement require_tags_for_prefix rule (FLOE-E400) in packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py
- [ ] T029 [US2] Implement require_meta_field rule (FLOE-E401) in packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py
- [ ] T030 [US2] Implement require_tests_of_type rule (FLOE-E402) in packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py
- [ ] T031 [US2] Implement glob pattern matching for applies_to field using fnmatch in packages/floe-core/src/floe_core/enforcement/validators/custom_rules.py
- [ ] T032 [US2] Register CustomRuleValidator in PolicyEnforcer.enforce() in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T033 [US2] Export CustomRuleValidator from enforcement module in packages/floe-core/src/floe_core/enforcement/__init__.py

**Checkpoint**: Custom rules fully functional and testable independently

---

## Phase 5: User Story 3 - Severity Overrides (Priority: P2)

**Goal**: Override violation severity for specific models/patterns to support gradual migration

**Independent Test**: Add override rules to governance config, verify specific models bypass strict enforcement

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T034 [P] [US3] Unit test for downgrade action (error to warning) in packages/floe-core/tests/unit/enforcement/test_policy_overrides.py
- [ ] T035 [P] [US3] Unit test for exclude action (skip validation) in packages/floe-core/tests/unit/enforcement/test_policy_overrides.py
- [ ] T036 [P] [US3] Unit test for expiration date checking in packages/floe-core/tests/unit/enforcement/test_policy_overrides.py
- [ ] T037 [P] [US3] Unit test for policy_types filtering in packages/floe-core/tests/unit/enforcement/test_policy_overrides.py

### Implementation for User Story 3

- [ ] T038 [US3] Add apply_overrides() method to PolicyEnforcer in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T039 [US3] Implement pattern matching for overrides using fnmatch in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T040 [US3] Implement downgrade action (error severity to warning) in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T041 [US3] Implement exclude action (skip validation entirely) in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T042 [US3] Implement expiration date checking with structlog warning in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T043 [US3] Implement policy_types filter for override scope in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T044 [US3] Add audit logging for applied overrides with structlog (includes warning when pattern matches zero models) in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py

**Checkpoint**: Severity overrides fully functional and testable independently

---

## Phase 6: User Story 4 - Detailed Violation Context (Priority: P2)

**Goal**: Include rich context in violations (downstream models, historical compliance) for prioritization

**Independent Test**: Generate violations, verify context fields populated from manifest data

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T045 [P] [US4] Unit test for downstream_impact population from child_map in packages/floe-core/tests/unit/enforcement/test_violation_context.py
- [ ] T046 [P] [US4] Unit test for violations_by_model grouping in packages/floe-core/tests/unit/enforcement/test_violation_context.py

### Implementation for User Story 4

- [ ] T047 [US4] Add compute_downstream_impact() helper function in packages/floe-core/src/floe_core/enforcement/result.py
- [ ] T048 [US4] Implement downstream impact population using manifest child_map in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T049 [US4] Implement lazy computation of downstream_impact (include_context parameter) in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py
- [ ] T050 [US4] Add include_context parameter to PolicyEnforcer.enforce() in packages/floe-core/src/floe_core/enforcement/policy_enforcer.py

**Checkpoint**: Violation context fully functional and testable independently

---

## Phase 7: User Story 5 - Validation Report Export (Priority: P3)

**Goal**: Export validation results in JSON, SARIF, and HTML formats for CI/CD integration

**Independent Test**: Run validation, export to each format, verify output matches expected schema

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T051 [P] [US5] Unit test for export_json() in packages/floe-core/tests/unit/enforcement/exporters/test_json_exporter.py
- [ ] T052 [P] [US5] Unit test for export_sarif() schema compliance in packages/floe-core/tests/unit/enforcement/exporters/test_sarif_exporter.py
- [ ] T053 [P] [US5] Unit test for export_html() in packages/floe-core/tests/unit/enforcement/exporters/test_html_exporter.py

### Implementation for User Story 5

- [ ] T054 [US5] Implement export_json() function in packages/floe-core/src/floe_core/enforcement/exporters/json_exporter.py
- [ ] T055 [US5] Implement export_sarif() function with SARIF 2.1.0 compliance in packages/floe-core/src/floe_core/enforcement/exporters/sarif_exporter.py
- [ ] T056 [US5] Create SARIF rule definitions for all FLOE-Exxx error codes in packages/floe-core/src/floe_core/enforcement/exporters/sarif_exporter.py
- [ ] T057 [US5] Create HTML report template (summary stats, violation table, no JS dependencies) in packages/floe-core/src/floe_core/enforcement/exporters/templates/report.html.j2
- [ ] T058 [US5] Implement export_html() function with Jinja2 rendering in packages/floe-core/src/floe_core/enforcement/exporters/html_exporter.py
- [ ] T059 [US5] Implement directory creation if output path doesn't exist in packages/floe-core/src/floe_core/enforcement/exporters/__init__.py
- [ ] T060 [US5] Export all exporter functions from enforcement.exporters module in packages/floe-core/src/floe_core/enforcement/exporters/__init__.py

**Checkpoint**: Report export fully functional and testable independently

---

## Phase 8: Pipeline Integration & Polish

**Purpose**: Integrate enforcement with compilation pipeline, update CLI

### Pipeline Integration (FR-024, FR-025, FR-026)

- [ ] T061 Update run_enforce_stage() to return EnforcementResultSummary in packages/floe-core/src/floe_core/compilation/stages.py
- [ ] T062 Add enforcement_result field to CompiledArtifacts in packages/floe-core/src/floe_core/schemas/compiled_artifacts.py
- [ ] T063 Update compile_pipeline() to store enforcement summary in artifacts in packages/floe-core/src/floe_core/compilation/stages.py
- [ ] T064 [P] Contract test for EnforcementResultSummary in CompiledArtifacts in tests/contract/test_enforcement_contract.py

### Integration Tests

- [ ] T065 [P] Integration test for full enforcement pipeline in packages/floe-core/tests/integration/enforcement/test_pipeline_enforcement.py
- [ ] T066 [P] Integration test for export formats in packages/floe-core/tests/integration/enforcement/test_enforcement_exports.py

### Documentation & Validation

- [ ] T067 [P] Update enforcement module __init__.py with all exports in packages/floe-core/src/floe_core/enforcement/__init__.py
- [ ] T068 Run quickstart.md validation scenarios
- [ ] T069 Verify performance goal: <500ms for 500 models (SC-001)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (Semantic) and US2 (Custom Rules) can proceed in parallel (both P1)
  - US3 (Overrides) and US4 (Context) can proceed in parallel (both P2)
  - US5 (Export) can proceed after US1-US4 complete
- **Pipeline Integration (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Independent but may use violations from US1/US2
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Uses Violation model extended in Phase 2
- **User Story 5 (P3)**: Best started after US1-US4 to ensure all violation types exist for export testing

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Schema extensions before validators
- Validators before PolicyEnforcer integration
- Unit tests before integration tests
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational schema tasks T005-T007 can run in parallel
- Unit tests for schemas (T011-T012) can run in parallel
- Once Foundational phase completes:
  - US1 and US2 can start in parallel (both P1 priority)
  - All test tasks within a story marked [P] can run in parallel
- US3 and US4 can start in parallel after P1 stories or after Foundational
- All export tests (T051-T053) can run in parallel

---

## Parallel Example: P1 User Stories

```bash
# After Foundational phase completes, launch both P1 stories:

# Story 1 tests (all in parallel):
Task: "Unit test for SemanticValidator.validate_refs()"
Task: "Unit test for SemanticValidator.detect_circular_deps()"
Task: "Unit test for SemanticValidator.validate_sources()"

# Story 2 tests (all in parallel, same time as Story 1):
Task: "Unit test for require_tags_for_prefix rule"
Task: "Unit test for require_meta_field rule"
Task: "Unit test for require_tests_of_type rule"
Task: "Unit test for invalid custom rule syntax error handling"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Semantic Validation)
4. Complete Phase 4: User Story 2 (Custom Rules)
5. **STOP and VALIDATE**: Both P1 stories independently testable
6. Can ship MVP with semantic + custom rule validation

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (Semantic) → Test independently → Core validation MVP
3. Add US2 (Custom Rules) → Test independently → Full P1 delivery
4. Add US3 (Overrides) → Test independently → Migration support
5. Add US4 (Context) → Test independently → Enhanced debugging
6. Add US5 (Export) → Test independently → CI/CD integration
7. Phase 8: Pipeline integration → Full feature complete

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Semantic)
   - Developer B: User Story 2 (Custom Rules)
3. After P1 complete:
   - Developer A: User Story 3 (Overrides)
   - Developer B: User Story 4 (Context)
4. Developer A or B: User Story 5 (Export)
5. Together: Phase 8 (Pipeline Integration)

---

## Task Summary

| Phase | Task Count | Parallelizable | Story |
|-------|------------|----------------|-------|
| Phase 1: Setup | 3 | 2 | N/A |
| Phase 2: Foundational | 11 | 5 | N/A |
| Phase 3: US1 Semantic | 9 | 3 | US1 |
| Phase 4: US2 Custom Rules | 11 | 4 | US2 |
| Phase 5: US3 Overrides | 11 | 4 | US3 |
| Phase 6: US4 Context | 6 | 2 | US4 |
| Phase 7: US5 Export | 10 | 3 | US5 |
| Phase 8: Integration | 9 | 3 | N/A |
| **Total** | **70** | **26** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests FAIL before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Performance: All 5 validators must execute in <500ms for 500 models (SC-001)
