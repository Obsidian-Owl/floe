# Tasks: Data Contracts (Epic 3C)

**Input**: Design documents from `/specs/3c-data-contracts/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

## Path Conventions

- **Monorepo**: `packages/floe-core/src/floe_core/`, `packages/floe-iceberg/src/floe_iceberg/`
- **Tests**: `packages/floe-core/tests/unit/`, `tests/contract/`, `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add datacontract-cli dependency and extend core schemas

- [ ] T001 Add datacontract-cli to floe-core dependencies in `packages/floe-core/pyproject.toml`
- [ ] T002 [P] Add `"data_contract"` to VALID_POLICY_TYPES in `packages/floe-core/src/floe_core/schemas/governance.py`
- [ ] T003 [P] Add FLOE-E5xx error code URLs to `packages/floe-core/src/floe_core/enforcement/patterns.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Pydantic models and schema extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Create DataContract Pydantic model with ODCS v3 fields in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T005 [P] Create DataContractModel and DataContractElement models in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T006 [P] Create SLAProperties, FreshnessSLA, QualitySLA models in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T007 [P] Create ContractTerms, DeprecationInfo models in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T008 [P] Create ElementType, ElementFormat, Classification, ContractStatus enums in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T009 Create DataContractsConfig, DriftDetectionConfig in `packages/floe-core/src/floe_core/schemas/governance.py`
- [ ] T010 Add data_contracts field to GovernanceConfig in `packages/floe-core/src/floe_core/schemas/manifest.py`
- [ ] T011 Add data_contracts field to CompiledArtifacts in `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`
- [ ] T012 Add contract_violations field to EnforcementSummary in `packages/floe-core/src/floe_core/enforcement/result.py`
- [ ] T013 Export new models from `packages/floe-core/src/floe_core/schemas/__init__.py`

**Checkpoint**: Foundation ready - all Pydantic models exist, user story implementation can begin

---

## Phase 3: User Story 1 - Contract Definition and Validation (Priority: P1)

**Goal**: Data engineers can define contracts in `datacontract.yaml` and have them validated at compile time for ODCS v3 compliance

**Independent Test**: Create a `datacontract.yaml` with valid/invalid configurations, run `floe compile`, verify validation catches all issues with clear FLOE-E5xx error messages

**Spec References**: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, FR-009, FR-010

### Tests for User Story 1

- [ ] T014 [P] [US1] Unit test for DataContract model validation in `packages/floe-core/tests/unit/schemas/test_data_contract.py`
- [ ] T015 [P] [US1] Unit test for datacontract-cli parsing wrapper in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_parsing.py`
- [ ] T016 [P] [US1] Contract test for DataContract schema stability in `tests/contract/test_data_contract_schema.py`

### Implementation for User Story 1

- [ ] T017 [US1] Create ContractValidationResult model in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T018 [US1] Create ContractParser class with datacontract-cli integration in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T019 [US1] Implement `_check_datacontract_cli()` dependency check in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T020 [US1] Implement `parse_contract()` to load YAML and lint via datacontract-cli in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T021 [US1] Implement `_lint_error_to_violation()` to convert lint errors to Violations with FLOE-E5xx codes in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T022 [US1] Implement `_convert_to_floe_model()` to convert datacontract-cli dict to DataContract Pydantic model in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T023 [US1] Create ContractValidator class with `validate()` method in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T024 [US1] Export ContractValidator from `packages/floe-core/src/floe_core/enforcement/validators/__init__.py`
- [ ] T025 [US1] Add `_validate_data_contracts()` method to PolicyEnforcer in `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py`
- [ ] T026 [US1] Wire ContractValidator call in `_run_all_validators()` in `packages/floe-core/src/floe_core/enforcement/policy_enforcer.py`

**Checkpoint**: Contract parsing and ODCS validation working - `floe compile` validates contracts

---

## Phase 4: User Story 2 - Contract Auto-Generation from Ports (Priority: P1)

**Goal**: Data engineers get contracts auto-generated from `floe.yaml` output_ports when no explicit contract exists

**Independent Test**: Create a `floe.yaml` with output_ports, run `floe compile` without `datacontract.yaml`, verify generated contract matches port definition

**Spec References**: FR-003, FR-004

### Tests for User Story 2

- [ ] T027 [P] [US2] Unit test for contract generation from ports in `packages/floe-core/tests/unit/contracts/test_generator.py`
- [ ] T028 [P] [US2] Unit test for contract merging (explicit overrides generated) in `packages/floe-core/tests/unit/contracts/test_generator.py`

### Implementation for User Story 2

- [ ] T029 [US2] Create `packages/floe-core/src/floe_core/contracts/` directory and `__init__.py`
- [ ] T030 [US2] Implement ContractGenerator class in `packages/floe-core/src/floe_core/contracts/generator.py`
- [ ] T031 [US2] Implement `generate_from_ports()` to create base contract from floe.yaml output_ports in `packages/floe-core/src/floe_core/contracts/generator.py`
- [ ] T032 [US2] Implement `merge_contracts()` to merge explicit with generated (explicit wins) in `packages/floe-core/src/floe_core/contracts/generator.py`
- [ ] T033 [US2] Implement contract name derivation as `{data_product_name}-{port_name}` in `packages/floe-core/src/floe_core/contracts/generator.py`
- [ ] T034 [US2] Integrate ContractGenerator in ContractValidator - generate if no explicit contract in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T035 [US2] Add FLOE-E500 error when no datacontract.yaml AND no output_ports defined in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`

**Checkpoint**: Auto-generation working - contracts generated from ports when explicit contract missing

---

## Phase 5: User Story 3 - Contract Inheritance Validation (Priority: P1)

**Goal**: Platform engineers can define enterprise/domain contracts that child contracts cannot weaken

**Independent Test**: Create enterprise -> domain -> product contract chain with strengthening/weakening SLAs, verify inheritance rules enforced with FLOE-E510

**Spec References**: FR-011, FR-012, FR-013, FR-014

### Tests for User Story 3

- [ ] T036 [P] [US3] Unit test for SLA weakening detection in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_inheritance.py`
- [ ] T037 [P] [US3] Unit test for SLA strengthening (allowed) in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_inheritance.py`
- [ ] T038 [P] [US3] Unit test for classification weakening detection in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_inheritance.py`
- [ ] T038b [P] [US3] Unit test for circular contract dependency detection in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_inheritance.py`

### Implementation for User Story 3

- [ ] T039 [US3] Implement InheritanceValidator class in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T040 [US3] Implement `_parse_duration()` to compare ISO 8601 durations in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T041 [US3] Implement `_parse_percentage()` to compare percentage SLAs in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T042 [US3] Implement `validate_inheritance()` comparing parent vs child SLAs in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T043 [US3] Implement freshness, availability, quality comparison logic in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T044 [US3] Implement classification inheritance rules (child cannot weaken) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T044b [US3] Implement circular dependency detection with cycle path reporting in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T045 [US3] Integrate InheritanceValidator in ContractValidator.validate() in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`

**Checkpoint**: Inheritance validation working - child contracts cannot weaken parent SLAs

---

## Phase 6: User Story 4 - Contract Version Bump Validation (Priority: P2)

**Goal**: System enforces semantic versioning rules when contracts are modified

**Independent Test**: Modify contracts with breaking/non-breaking/patch changes, verify version bump requirements enforced with FLOE-E520

**Spec References**: FR-015, FR-016, FR-017, FR-018, FR-019, FR-020

### Tests for User Story 4

- [ ] T046 [P] [US4] Unit test for breaking change detection (column removal) in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_versioning.py`
- [ ] T047 [P] [US4] Unit test for non-breaking change detection (optional column add) in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_versioning.py`
- [ ] T048 [P] [US4] Unit test for patch change detection (description only) in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_versioning.py`

### Implementation for User Story 4

- [ ] T049 [US4] Implement VersionValidator class in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T050 [US4] Implement `_detect_breaking_changes()` (remove element, change type, make optional required, relax SLA) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T051 [US4] Implement `_detect_non_breaking_changes()` (add optional, make required optional, stricter SLA) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T052 [US4] Implement `_detect_patch_changes()` (description, tags, links) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T053 [US4] Implement `validate_version_bump()` comparing changes to version increment in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T054 [US4] Implement catalog baseline retrieval (load registered contract for comparison) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T055 [US4] Integrate VersionValidator in ContractValidator.validate() in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`

**Checkpoint**: Version validation working - semantic versioning rules enforced

---

## Phase 7: User Story 5 - Schema Drift Detection (Priority: P2)

**Goal**: System detects when contract schema differs from actual Iceberg table schema

**Independent Test**: Create contract with schema differing from table, run compile, verify drift detected with field-level details (FLOE-E530/E531/E532)

**Spec References**: FR-021, FR-022, FR-023, FR-024, FR-025

### Tests for User Story 5

- [ ] T056 [P] [US5] Unit test for type mismatch detection in `packages/floe-iceberg/tests/unit/test_drift_detector.py`
- [ ] T057 [P] [US5] Unit test for missing column detection in `packages/floe-iceberg/tests/unit/test_drift_detector.py`
- [ ] T058 [P] [US5] Unit test for extra column detection (info only) in `packages/floe-iceberg/tests/unit/test_drift_detector.py`
- [ ] T059 [P] [US5] Contract test for drift detection between floe-core and floe-iceberg in `tests/contract/test_core_to_iceberg_drift_contract.py`

### Implementation for User Story 5

- [ ] T060 [US5] Create SchemaComparisonResult, TypeMismatch models in `packages/floe-core/src/floe_core/schemas/data_contract.py`
- [ ] T061 [US5] Create DriftDetector class in `packages/floe-iceberg/src/floe_iceberg/drift_detector.py`
- [ ] T062 [US5] Implement ODCS-to-PyIceberg type mapping in `packages/floe-iceberg/src/floe_iceberg/drift_detector.py`
- [ ] T063 [US5] Implement `compare_schemas()` comparing contract elements to table schema fields in `packages/floe-iceberg/src/floe_iceberg/drift_detector.py`
- [ ] T064 [US5] Implement type mismatch, missing column, extra column detection in `packages/floe-iceberg/src/floe_iceberg/drift_detector.py`
- [ ] T065 [US5] Export DriftDetector from `packages/floe-iceberg/src/floe_iceberg/__init__.py`
- [ ] T066 [US5] Integrate DriftDetector in ContractValidator (skip if table doesn't exist) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`

**Checkpoint**: Schema drift detection working - mismatches between contract and table detected

---

## Phase 8: User Story 6 - Contract Registration in Catalog (Priority: P2)

**Goal**: Contracts registered in Iceberg catalog namespace properties for discoverability

**Independent Test**: Compile data product with contract, verify contract metadata appears in catalog namespace properties via CatalogPlugin

**Spec References**: FR-026, FR-027, FR-028

### Tests for User Story 6

- [ ] T067 [P] [US6] Unit test for catalog registration call in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_registration.py`
- [ ] T068 [P] [US6] Unit test for soft failure on catalog unreachability in `packages/floe-core/tests/unit/enforcement/validators/test_data_contracts_registration.py`
- [ ] T069 [P] [US6] Integration test for catalog registration in `tests/integration/test_data_contracts_catalog.py`

### Implementation for User Story 6

- [ ] T070 [US6] Implement CatalogRegistrar class in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T071 [US6] Implement `register_contract()` storing metadata in namespace properties in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T072 [US6] Implement `_compute_schema_hash()` for contract fingerprinting in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T073 [US6] Implement soft failure handling (warning on catalog unreachability) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`
- [ ] T074 [US6] Integrate CatalogRegistrar in ContractValidator (register on successful validation) in `packages/floe-core/src/floe_core/enforcement/validators/data_contracts.py`

**Checkpoint**: Contract registration working - contracts discoverable via catalog API

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Integration, documentation, and cleanup

- [ ] T075 [P] Add data contracts section to enforcement documentation
- [ ] T076 [P] Create example datacontract.yaml in demo/ directory
- [ ] T077 Update CLI help text for `--skip-contracts`, `--drift-detection` flags in `floe compile` command
- [ ] T078 Run full integration test: `floe compile` with all contract features
- [ ] T079 Verify all error codes have documentation URLs in patterns.py
- [ ] T080 [P] Performance benchmark: validate <2s for 50-model contract (SC-001)
- [ ] T081 [P] Performance benchmark: validate <5s drift detection for 100-column table (SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational completion
  - US1, US2, US3 (P1): Can proceed in parallel after Foundational
  - US4, US5, US6 (P2): Can proceed in parallel after Foundational
  - US5 (Drift): Depends on US1 (ContractValidator exists)
  - US6 (Registration): Depends on US1 (ContractValidator exists)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (Contract Validation)**: Foundation only - no other story dependencies
- **US2 (Auto-Generation)**: Foundation only - integrates with US1's ContractValidator
- **US3 (Inheritance)**: Foundation only - integrates with US1's ContractValidator
- **US4 (Versioning)**: Foundation only - integrates with US1's ContractValidator
- **US5 (Drift)**: Depends on US1 ContractValidator existing
- **US6 (Registration)**: Depends on US1 ContractValidator existing

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before validators
- Core logic before integration
- Integration with PolicyEnforcer last

### Parallel Opportunities

**Phase 1 (Setup)**:
```
T002 || T003  (different files)
```

**Phase 2 (Foundational)**:
```
T004 -> (T005 || T006 || T007 || T008)  (all in same file but independent classes)
T009 || T010 || T011 || T012  (different files)
```

**Phase 3-8 (User Stories)**: After Foundational completes:
```
US1 || US2 || US3  (P1 stories can run in parallel)
US4 || US5 || US6  (P2 stories can run in parallel, after P1 core)
```

**Within US1**:
```
T014 || T015 || T016  (tests in different files)
T017 -> T018 -> T019 -> T020 -> T021 -> T022 -> T023 -> T024 -> T025 -> T026
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Contract Definition and Validation)
4. **STOP and VALIDATE**: `floe compile` validates datacontract.yaml
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Validation) → Test independently → Core MVP!
3. Add US2 (Auto-Gen) → Easier adoption path
4. Add US3 (Inheritance) → Governance at scale
5. Add US4 (Versioning) → Prevent breaking changes
6. Add US5 (Drift) → Catch mismatches
7. Add US6 (Registration) → Discoverability

### Priority Order for Solo Developer

1. Setup + Foundational (T001-T013)
2. US1: Contract Validation (T014-T026) - **MUST COMPLETE**
3. US3: Inheritance (T036-T045) - High governance value
4. US2: Auto-Generation (T027-T035) - Lowers barrier
5. US4: Versioning (T046-T055) - Breaking change prevention
6. US5: Drift (T056-T066) - Data quality
7. US6: Registration (T067-T074) - Discoverability
8. Polish (T075-T079)

---

## Task Summary

| Phase | Story | Task Count | Parallel Opportunities |
|-------|-------|------------|----------------------|
| Setup | - | 3 | 2 |
| Foundational | - | 10 | 7 |
| US1 | Contract Validation | 13 | 3 (tests) |
| US2 | Auto-Generation | 9 | 2 (tests) |
| US3 | Inheritance | 12 | 4 (tests) |
| US4 | Versioning | 10 | 3 (tests) |
| US5 | Drift | 11 | 4 (tests) |
| US6 | Registration | 8 | 3 (tests) |
| Polish | - | 7 | 4 |
| **Total** | | **83** | **32** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- All error codes FLOE-E5xx (500-532) defined in spec.md
- datacontract-cli is HARD dependency - fail fast if not installed
- Tests use `@pytest.mark.requirement("3C-FR-XXX")` for traceability
- No version bumps needed - pre-release development
