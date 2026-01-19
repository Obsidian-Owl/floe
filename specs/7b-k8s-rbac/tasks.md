# Tasks: K8s RBAC Plugin System

**Input**: Design documents from `/specs/7b-k8s-rbac/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests are REQUIRED per project constitution (TDD, K8s-native testing).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US6)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md monorepo structure:
- **floe-core schemas**: `packages/floe-core/src/floe_core/schemas/`
- **floe-core plugins**: `packages/floe-core/src/floe_core/plugins/`
- **floe-core rbac**: `packages/floe-core/src/floe_core/rbac/`
- **K8s plugin**: `plugins/floe-rbac-k8s/src/floe_rbac_k8s/`
- **Base test classes**: `testing/base_classes/`
- **Contract tests**: `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and package structure

- [ ] T001 Create plugin package structure for `plugins/floe-rbac-k8s/` with pyproject.toml
- [ ] T002 [P] Create `packages/floe-core/src/floe_core/schemas/` directory if not exists
- [ ] T003 [P] Create `packages/floe-core/src/floe_core/rbac/` directory with __init__.py
- [ ] T004 [P] Add kubernetes>=27.0.0 dependency to floe-core pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

### Pydantic Schemas (All stories depend on these)

- [ ] T005 [P] Create SecurityConfig schema in `packages/floe-core/src/floe_core/schemas/security.py` (RBACConfig, PodSecurityLevelConfig, SecurityConfig)
- [ ] T006 [P] Create ServiceAccountConfig schema in `packages/floe-core/src/floe_core/schemas/rbac.py`
- [ ] T007 [P] Create RoleRule and RoleConfig schemas in `packages/floe-core/src/floe_core/schemas/rbac.py`
- [ ] T008 [P] Create RoleBindingSubject and RoleBindingConfig schemas in `packages/floe-core/src/floe_core/schemas/rbac.py`
- [ ] T009 [P] Create NamespaceConfig schema in `packages/floe-core/src/floe_core/schemas/rbac.py`
- [ ] T010 [P] Create PodSecurityConfig schema in `packages/floe-core/src/floe_core/schemas/rbac.py`
- [ ] T011 [P] Create GenerationResult dataclass in `packages/floe-core/src/floe_core/rbac/result.py`

### RBACPlugin ABC (All stories depend on this)

- [ ] T012 Create RBACPlugin ABC in `packages/floe-core/src/floe_core/plugins/rbac.py` with abstract methods (FR-001, FR-003)

### Base Test Class (All stories depend on this)

- [ ] T013 Create BaseRBACPluginTests in `testing/base_classes/base_rbac_plugin_tests.py` with compliance tests

### Unit Tests for Foundational

- [ ] T014 [P] Unit tests for SecurityConfig schema in `packages/floe-core/tests/unit/test_security_schema.py`
- [ ] T015 [P] Unit tests for RBAC schemas in `packages/floe-core/tests/unit/test_rbac_schemas.py`
- [ ] T016 [P] Unit tests for RBACPlugin ABC in `packages/floe-core/tests/unit/test_rbac_plugin_abc.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Service Account Generation (Priority: P0)

**Goal**: Automatically generate service accounts with least-privilege permissions for data pipeline jobs

**Independent Test**: Deploy a dbt job, verify ServiceAccount exists with correct Role/RoleBinding, confirm job can access specified secrets but nothing else

**Requirements**: FR-010, FR-011, FR-012, FR-013, FR-014, FR-020, FR-021, FR-022, FR-024, FR-070, FR-071

### Tests for User Story 1

- [ ] T017 [P] [US1] Contract test for ServiceAccount generation in `tests/contract/test_service_account_generation.py`
- [ ] T018 [P] [US1] Unit test for ServiceAccountConfig.to_k8s_manifest() in `packages/floe-core/tests/unit/test_service_account_manifest.py`
- [ ] T019 [P] [US1] Unit test for RoleConfig.to_k8s_manifest() in `packages/floe-core/tests/unit/test_role_manifest.py`
- [ ] T020 [P] [US1] Unit test for RoleBindingConfig.to_k8s_manifest() in `packages/floe-core/tests/unit/test_rolebinding_manifest.py`

### Implementation for User Story 1

- [ ] T021 [US1] Implement K8sRBACPlugin.generate_service_account() in `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py` (FR-010, FR-011, FR-013, FR-014)
- [ ] T022 [US1] Implement K8sRBACPlugin.generate_role() in `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py` (FR-020, FR-021, FR-024)
- [ ] T023 [US1] Implement K8sRBACPlugin.generate_role_binding() in `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py` (FR-022)
- [ ] T024 [US1] Add wildcard validation to RoleConfig preventing * in apiGroups/resources/verbs (FR-070)
- [ ] T024a [US1] Add validation ensuring ClusterRoleBindings only generated when security.rbac.cluster_scope: true (FR-071)
- [ ] T025 [US1] Register K8sRBACPlugin via entry point in `plugins/floe-rbac-k8s/pyproject.toml` (FR-004)

### Integration Tests for User Story 1

- [ ] T026 [US1] Integration test for K8sRBACPlugin compliance in `plugins/floe-rbac-k8s/tests/integration/test_k8s_rbac_compliance.py`

**Checkpoint**: Service accounts can be generated with least-privilege permissions

---

## Phase 4: User Story 2 - Namespace Isolation (Priority: P0)

**Goal**: Namespace-based isolation so jobs from different domains cannot access each other's resources

**Independent Test**: Create two domain namespaces, deploy jobs in each, verify cross-namespace access is denied

**Requirements**: FR-030, FR-031, FR-032, FR-033, FR-034, FR-040, FR-044

> **Note on FR-040-044 split**: US2 implements the base pod/container security context (FR-040, FR-044) as part of namespace isolation. US5 extends this with PSS-specific enforcement testing (FR-041, FR-042, FR-043) to verify admission rejection of non-compliant pods.

### Tests for User Story 2

- [ ] T027 [P] [US2] Contract test for NamespaceConfig.to_k8s_manifest() in `tests/contract/test_namespace_generation.py`
- [ ] T028 [P] [US2] Unit test for PodSecurityConfig.to_pod_security_context() in `packages/floe-core/tests/unit/test_pod_security_context.py`
- [ ] T029 [P] [US2] Unit test for PodSecurityConfig.to_container_security_context() in `packages/floe-core/tests/unit/test_container_security_context.py`

### Implementation for User Story 2

- [ ] T030 [US2] Implement K8sRBACPlugin.generate_namespace() in `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py` (FR-030, FR-034)
- [ ] T031 [US2] Implement K8sRBACPlugin.generate_pod_security_context() in `plugins/floe-rbac-k8s/src/floe_rbac_k8s/plugin.py` (FR-040, FR-041, FR-042, FR-043, FR-044)
- [ ] T032 [US2] Add PSS label defaults for floe-jobs (restricted) and floe-platform (baseline) in NamespaceConfig (FR-031, FR-032, FR-033)

### Integration Tests for User Story 2

- [ ] T033 [US2] Integration test for namespace isolation in `plugins/floe-rbac-k8s/tests/integration/test_namespace_isolation.py`

**Checkpoint**: Namespace isolation with PSS enforcement works independently

---

## Phase 5: User Story 3 - Cross-Namespace Access (Priority: P1)

**Goal**: Platform services (Dagster) can create jobs in floe-jobs namespace across namespace boundaries

**Independent Test**: Deploy Dagster in floe-platform, trigger a job, verify it creates a job pod in floe-jobs namespace

**Requirements**: FR-012, FR-023

### Tests for User Story 3

- [ ] T034 [P] [US3] Contract test for cross-namespace RoleBinding in `tests/contract/test_cross_namespace_binding.py`
- [ ] T035 [P] [US3] Unit test for RoleBindingConfig with cross-namespace subjects in `packages/floe-core/tests/unit/test_cross_namespace_rolebinding.py`

### Implementation for User Story 3

- [ ] T036 [US3] Extend RoleBindingConfig to support cross-namespace subjects in `packages/floe-core/src/floe_core/schemas/rbac.py` (FR-012)
- [ ] T037 [US3] Implement cross-namespace RoleBinding generation in K8sRBACPlugin (FR-023)
- [ ] T038 [US3] Add validation that cross-namespace access is only to explicitly allowed namespaces

### Integration Tests for User Story 3

- [ ] T039 [US3] Integration test for Dagster cross-namespace access in `plugins/floe-rbac-k8s/tests/integration/test_cross_namespace_access.py`

**Checkpoint**: Platform services can create jobs across namespaces with explicit grants

---

## Phase 6: User Story 4 - RBAC Manifest Generation (Priority: P1)

**Goal**: Generate RBAC manifests from floe configuration so data engineers don't need to manually write K8s RBAC resources

**Independent Test**: Run `floe compile`, examine output RBAC manifests, apply to test cluster

**Requirements**: FR-002, FR-050, FR-051, FR-052, FR-053, FR-072, FR-073

### Tests for User Story 4

- [ ] T040 [P] [US4] Contract test for RBACManifestGenerator output in `tests/contract/test_rbac_manifest_generator.py`
- [ ] T041 [P] [US4] Unit test for permission aggregation in `packages/floe-core/tests/unit/test_permission_aggregation.py`
- [ ] T042 [P] [US4] Unit test for manifest file writing in `packages/floe-core/tests/unit/test_manifest_writing.py`

### Implementation for User Story 4

- [ ] T043 [US4] Create RBACManifestGenerator class in `packages/floe-core/src/floe_core/rbac/generator.py` (FR-002)
- [ ] T044 [US4] Implement RBACManifestGenerator.generate() method (FR-050)
- [ ] T045 [US4] Implement RBACManifestGenerator.aggregate_permissions() for combining data product permissions (FR-052)
- [ ] T046 [US4] Implement RBACManifestGenerator.write_manifests() producing separate files per resource type (FR-053)
- [ ] T047 [US4] Add YAML validation ensuring manifests pass kubectl dry-run (FR-051)
- [ ] T048 [US4] Add audit logging for RBAC generation operations (FR-072)
- [ ] T049 [US4] Add validation failing if secret reference not in RBAC permissions (FR-073)

### Integration Tests for User Story 4

- [ ] T050 [US4] Integration test for full manifest generation workflow in `packages/floe-core/tests/integration/test_rbac_generation.py`

**Checkpoint**: RBAC manifests can be generated from configuration and applied to cluster

---

## Phase 7: User Story 5 - Pod Security Standards (Priority: P2)

**Goal**: Enforce Pod Security Standards so all job pods meet security baselines

**Independent Test**: Deploy a job with non-compliant security context, verify admission rejection

**Requirements**: FR-040, FR-041, FR-042, FR-043, FR-044 (PSS enforcement via namespace labels from US2)

### Tests for User Story 5

- [ ] T051 [P] [US5] Integration test for PSS enforcement rejection in `plugins/floe-rbac-k8s/tests/integration/test_pss_enforcement.py`
- [ ] T052 [P] [US5] Unit test for seccompProfile generation in `packages/floe-core/tests/unit/test_seccomp_profile.py`

### Implementation for User Story 5

- [ ] T053 [US5] Add seccompProfile RuntimeDefault to PodSecurityConfig (FR-042)
- [ ] T054 [US5] Add capabilities.drop ["ALL"] to container security context (FR-041)
- [ ] T055 [US5] Add configurable volume mounts for writable directories with readOnlyRootFilesystem (FR-043)

**Checkpoint**: Pods without compliant security context are rejected by PSS admission

---

## Phase 8: User Story 6 - RBAC Audit and Validation (Priority: P2)

**Goal**: Validate RBAC configurations to ensure least-privilege principles are followed

**Independent Test**: Run `floe rbac audit` and review generated report

**Requirements**: FR-060, FR-061, FR-062, FR-063

### Tests for User Story 6

- [ ] T056 [P] [US6] Unit test for RBAC audit report generation in `packages/floe-cli/tests/unit/test_rbac_audit.py`
- [ ] T057 [P] [US6] Unit test for RBAC validation in `packages/floe-cli/tests/unit/test_rbac_validate.py`
- [ ] T058 [P] [US6] Unit test for RBAC diff in `packages/floe-cli/tests/unit/test_rbac_diff.py`

### Implementation for User Story 6

- [ ] T059 [US6] Implement `floe rbac generate` CLI command in `packages/floe-cli/src/floe_cli/commands/rbac.py` (FR-060)
- [ ] T060 [US6] Implement `floe rbac validate` CLI command (FR-061)
- [ ] T061 [US6] Implement `floe rbac audit` CLI command (FR-062)
- [ ] T062 [US6] Implement `floe rbac diff` CLI command (FR-063)
- [ ] T063 [US6] Add wildcard permission detection in audit (FR-070 validation)

### Integration Tests for User Story 6

- [ ] T064 [US6] Integration test for full audit workflow in `packages/floe-cli/tests/integration/test_rbac_cli_integration.py`

**Checkpoint**: RBAC can be audited, validated, and drift detected

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T065 [P] Add OpenTelemetry tracing to RBACManifestGenerator operations
- [ ] T066 [P] Export JSON Schema for SecurityConfig to `schemas/security.schema.json`
- [ ] T067 [P] Update floe-core __init__.py to export RBAC schemas and plugin ABC
- [ ] T068 Run quickstart.md validation with generated manifests
- [ ] T069 Final contract test validating full pipeline: SecurityConfig -> K8sRBACPlugin -> RBACManifestGenerator -> YAML files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-8)**: All depend on Foundational phase completion
  - US1 and US2 are P0 - implement first (can run in parallel)
  - US3 and US4 are P1 - implement after P0 (can run in parallel)
  - US5 and US6 are P2 - implement last (can run in parallel)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P0)**: Can start after Foundational - No dependencies on other stories
- **US2 (P0)**: Can start after Foundational - No dependencies on other stories
- **US3 (P1)**: Depends on US1 (needs ServiceAccount/Role patterns) - builds on cross-namespace binding
- **US4 (P1)**: Depends on US1+US2 (needs all manifest types) - aggregates all generation logic
- **US5 (P2)**: Depends on US2 (uses PSS labels from namespace) - extends security context
- **US6 (P2)**: Depends on US4 (needs manifest generation) - validates generated output

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD)
- Schemas before implementation
- Implementation before integration tests
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2 (Foundational)** - All schemas can be created in parallel:
```bash
Task: T005, T006, T007, T008, T009, T010, T011 (all [P])
```

**Phase 3 (US1) Tests** - All tests can run in parallel:
```bash
Task: T017, T018, T019, T020 (all [P] [US1])
```

**Phase 4 (US2) Tests** - All tests can run in parallel:
```bash
Task: T027, T028, T029 (all [P] [US2])
```

**P0 User Stories** - US1 and US2 can be worked on in parallel by different developers

**P1 User Stories** - US3 and US4 can be worked on in parallel (after P0 complete)

**P2 User Stories** - US5 and US6 can be worked on in parallel (after P1 complete)

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Service Accounts)
4. Complete Phase 4: User Story 2 (Namespace Isolation)
5. **STOP and VALIDATE**: Test US1+US2 independently - basic RBAC generation works
6. Deploy/demo if ready - core security features functional

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 + US2 → Test independently → **MVP** (P0 complete)
3. Add US3 + US4 → Test independently → **Full Generation** (P1 complete)
4. Add US5 + US6 → Test independently → **Audit & Compliance** (P2 complete)
5. Polish phase → Production ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Service Accounts)
   - Developer B: US2 (Namespace Isolation)
3. Once P0 complete:
   - Developer A: US3 (Cross-Namespace)
   - Developer B: US4 (Manifest Generation)
4. Once P1 complete:
   - Developer A: US5 (PSS)
   - Developer B: US6 (Audit/Validation)
5. Team completes Polish together

---

## Requirement Traceability

| Requirement | Task(s) | User Story |
|-------------|---------|------------|
| FR-001 | T012 | Foundational |
| FR-002 | T043 | US4 |
| FR-003 | T012 | Foundational |
| FR-004 | T025 | US1 |
| FR-010 | T021 | US1 |
| FR-011 | T021 | US1 |
| FR-012 | T036 | US3 |
| FR-013 | T021 | US1 |
| FR-014 | T021 | US1 |
| FR-020 | T022 | US1 |
| FR-021 | T022 | US1 |
| FR-022 | T023 | US1 |
| FR-023 | T037 | US3 |
| FR-024 | T022 | US1 |
| FR-030 | T030 | US2 |
| FR-031 | T032 | US2 |
| FR-032 | T032 | US2 |
| FR-033 | T032 | US2 |
| FR-034 | T030 | US2 |
| FR-040 | T031 | US2 |
| FR-041 | T054 | US5 |
| FR-042 | T053 | US5 |
| FR-043 | T055 | US5 |
| FR-044 | T031 | US2 |
| FR-050 | T044 | US4 |
| FR-051 | T047 | US4 |
| FR-052 | T045 | US4 |
| FR-053 | T046 | US4 |
| FR-060 | T059 | US6 |
| FR-061 | T060 | US6 |
| FR-062 | T061 | US6 |
| FR-063 | T062 | US6 |
| FR-070 | T024, T063 | US1, US6 |
| FR-071 | T024a | US1 |
| FR-072 | T048 | US4 |
| FR-073 | T049 | US4 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests MUST fail before implementing (TDD per constitution)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All integration tests run in Kind cluster (K8s-native testing)
- Use `@pytest.mark.requirement()` markers for traceability
