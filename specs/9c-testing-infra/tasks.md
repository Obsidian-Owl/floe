# Tasks: K8s-Native Testing Infrastructure

**Input**: Design documents from `/specs/9c-testing-infra/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions (from plan.md)

```text
testing/                         # Testing module at repo root
├── base_classes/               # Test base classes
├── fixtures/                   # Pytest fixtures
├── k8s/                        # Kind config and manifests
├── traceability/               # Requirement traceability
├── ci/                         # CI scripts
└── Dockerfile                  # Test runner image

Makefile                        # Test targets
.github/workflows/ci.yml        # CI workflow (Stage 2)
```

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create testing module structure and configure pytest

- [ ] T001 Create testing module directory structure per plan.md
- [ ] T002 [P] Create `testing/__init__.py` with module docstring
- [ ] T003 [P] Create `testing/base_classes/__init__.py`
- [ ] T004 [P] Create `testing/fixtures/__init__.py`
- [ ] T005 [P] Create `testing/traceability/__init__.py`
- [ ] T006 Register requirement marker in `pyproject.toml` pytest config
- [ ] T007 [P] Create `testing/k8s/` directory for Kind and manifests

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: US1 (Kind cluster) and US6 (Polling) must complete before other stories

### Polling Utilities (Required by all fixtures)

- [ ] T008 Create `testing/fixtures/polling.py` with PollingConfig model
- [ ] T009 Implement `wait_for_condition()` in `testing/fixtures/polling.py`
- [ ] T010 Implement `wait_for_service()` in `testing/fixtures/polling.py`
- [ ] T011 [P] Add unit tests for polling utilities in `testing/tests/unit/test_polling.py`

### Namespace Utilities (Required by all base classes)

- [ ] T012 Create `testing/fixtures/namespaces.py` with `generate_unique_namespace()`
- [ ] T013 [P] Add unit tests for namespace generation in `testing/tests/unit/test_namespaces.py`

### Service Health Utilities (Required by base classes)

- [ ] T014 Create `testing/fixtures/services.py` with `check_service_health()`
- [ ] T015 [P] Add unit tests for service health in `testing/tests/unit/test_services.py`

**Checkpoint**: Foundation ready - Kind cluster and base classes can now be implemented

---

## Phase 3: User Story 1 - Kind Cluster Setup (Priority: P0) 🎯 MVP

**Goal**: Developers can spin up a local Kind cluster with test services

**Independent Test**: Run `make kind-up`, verify `kubectl get pods -n floe-test` shows all services Running, run `make kind-down`

### K8s Configuration for US1

- [ ] T016 [US1] Create `testing/k8s/kind-config.yaml` per research.md specification
- [ ] T017 [P] [US1] Create `testing/k8s/services/namespace.yaml` for floe-test namespace
- [ ] T018 [P] [US1] Create `testing/k8s/services/postgres.yaml` deployment and service
- [ ] T019 [P] [US1] Create `testing/k8s/services/minio.yaml` deployment and service
- [ ] T020 [P] [US1] Create `testing/k8s/services/polaris.yaml` deployment and service
- [ ] T021 [P] [US1] Create `testing/k8s/services/dagster.yaml` deployment and service

### Cluster Scripts for US1

- [ ] T022 [US1] Create `testing/k8s/setup-cluster.sh` for cluster creation
- [ ] T023 [US1] Create `testing/k8s/cleanup-cluster.sh` for cluster teardown

### Test Runner Container for US1

- [ ] T024 [US1] Create `testing/Dockerfile` per research.md specification
- [ ] T025 [P] [US1] Create `testing/k8s/jobs/test-runner.yaml` K8s Job manifest

**Checkpoint**: Kind cluster is operational - `make kind-up` creates cluster with services

---

## Phase 4: User Story 2 - Integration Test Base Classes (Priority: P0)

**Goal**: Test authors have base classes that handle common integration test setup

**Independent Test**: Create a test inheriting from `IntegrationTestBase`, verify service checks and namespace isolation work

### Base Class Implementation for US2

- [ ] T026 [US2] Create `testing/base_classes/integration_test_base.py` with IntegrationTestBase
- [ ] T027 [US2] Implement `check_infrastructure()` method in IntegrationTestBase
- [ ] T028 [US2] Implement `generate_unique_namespace()` method in IntegrationTestBase
- [ ] T029 [US2] Implement `setup_method()` and `teardown_method()` in IntegrationTestBase
- [ ] T030 [P] [US2] Create `testing/base_classes/plugin_test_base.py` with PluginTestBase
- [ ] T031 [P] [US2] Create `testing/base_classes/adapter_test_base.py` with AdapterTestBase

### Tests for US2

- [ ] T032 [P] [US2] Create unit tests for IntegrationTestBase in `testing/tests/unit/test_integration_base.py`
- [ ] T033 [P] [US2] Create sample integration test in `testing/tests/integration/test_sample.py`

**Checkpoint**: Base classes ready - test authors can inherit and write integration tests

---

## Phase 5: User Story 3 - Requirement Traceability (Priority: P0)

**Goal**: Every test linked to a requirement, CI fails if markers missing

**Independent Test**: Run `python -m testing.traceability --all --threshold 100` and verify report

### Traceability Implementation for US3

- [ ] T034 [US3] Create `testing/traceability/checker.py` with pytest collection hook
- [ ] T035 [US3] Implement TraceabilityReport Pydantic model in `testing/traceability/checker.py`
- [ ] T036 [US3] Implement CLI interface for `python -m testing.traceability`
- [ ] T037 [US3] Create `testing/traceability/__main__.py` for module execution
- [ ] T038 [P] [US3] Add unit tests for traceability checker in `testing/tests/unit/test_traceability.py`

### pytest Plugin for US3

- [ ] T039 [US3] Create `testing/fixtures/conftest.py` with pytest hooks for marker collection
- [ ] T040 [US3] Register traceability plugin in `pyproject.toml`

**Checkpoint**: Traceability enforced - unmarked tests fail CI

---

## Phase 6: User Story 4 - Service Fixtures (Priority: P1)

**Goal**: Test authors have pytest fixtures for all test services

**Independent Test**: Use `postgres_connection` fixture in a test, verify connectivity and cleanup

**Dependencies**: Requires US1 (Kind cluster) and US2 (Base classes) complete

### PostgreSQL Fixture for US4

- [ ] T041 [P] [US4] Create `testing/fixtures/postgres.py` with PostgresConfig and fixture
- [ ] T042 [P] [US4] Add integration test for postgres fixture in `testing/tests/integration/test_postgres_fixture.py`

### MinIO Fixture for US4

- [ ] T043 [P] [US4] Create `testing/fixtures/minio.py` with MinIOConfig and fixture
- [ ] T044 [P] [US4] Add integration test for minio fixture in `testing/tests/integration/test_minio_fixture.py`

### Polaris Fixture for US4

- [ ] T045 [P] [US4] Create `testing/fixtures/polaris.py` with PolarisConfig and fixture
- [ ] T046 [P] [US4] Add integration test for polaris fixture in `testing/tests/integration/test_polaris_fixture.py`

### DuckDB Fixture for US4

- [ ] T047 [P] [US4] Create `testing/fixtures/duckdb.py` with DuckDBConfig and fixture
- [ ] T048 [P] [US4] Add unit test for duckdb fixture in `testing/tests/unit/test_duckdb_fixture.py`

### Dagster Fixture for US4

- [ ] T049 [P] [US4] Create `testing/fixtures/dagster.py` with DagsterConfig and fixture
- [ ] T050 [P] [US4] Add integration test for dagster fixture in `testing/tests/integration/test_dagster_fixture.py`

### Test Data Helpers for US4

- [ ] T051 [US4] Create `testing/fixtures/data.py` with test data generation helpers

**Checkpoint**: All service fixtures operational - test authors can connect to any service

---

## Phase 7: User Story 5 - CI Workflow Updates (Priority: P1)

**Goal**: CI runs integration tests automatically with security scanning

**Independent Test**: Push PR and verify security + integration-tests jobs run in GitHub Actions

**Dependencies**: Requires US1 (Kind), US2 (Base classes), US3 (Traceability) complete

### CI Workflow for US5

- [ ] T052 [US5] Add security job (Bandit, pip-audit) to `.github/workflows/ci.yml`
- [ ] T053 [US5] Add integration-tests job with Kind cluster to `.github/workflows/ci.yml`
- [ ] T054 [US5] Update ci-success job to require security and integration-tests
- [ ] T055 [P] [US5] Add traceability check to CI workflow

### CI Scripts for US5

- [ ] T056 [P] [US5] Create `testing/ci/test-unit.sh` runner script
- [ ] T057 [P] [US5] Create `testing/ci/test-integration.sh` runner script
- [ ] T058 [P] [US5] Create `testing/ci/test-e2e.sh` runner script

**Checkpoint**: CI Stage 2 operational - PRs run full test suite

---

## Phase 8: User Story 6 - Polling Utilities (Priority: P1)

**Goal**: Test authors use polling helpers instead of hardcoded sleeps

**Independent Test**: Use `wait_for_condition()` in a test, verify it returns when ready or times out

**Note**: Core polling utilities already implemented in Phase 2 (T008-T011). This phase adds documentation and validation.

### Polling Validation for US6

- [ ] T059 [US6] Add grep check for `time.sleep` in CI to ensure no hardcoded sleeps
- [ ] T060 [P] [US6] Document polling patterns in `testing/fixtures/polling.py` docstrings
- [ ] T061 [P] [US6] Create example test using polling in `testing/tests/integration/test_polling_example.py`

**Checkpoint**: No hardcoded sleeps in test code

---

## Phase 9: User Story 7 - Makefile Test Targets (Priority: P1)

**Goal**: Simple make commands for all test operations

**Independent Test**: Run `make help` and verify all test targets documented

### Makefile Targets for US7

- [ ] T062 [US7] Add `kind-up` target to `Makefile`
- [ ] T063 [US7] Add `kind-down` target to `Makefile`
- [ ] T064 [US7] Add `test` target (all tests) to `Makefile`
- [ ] T065 [US7] Add `test-unit` target to `Makefile`
- [ ] T066 [US7] Add `test-integration` target to `Makefile`
- [ ] T067 [US7] Add `test-e2e` target to `Makefile`
- [ ] T068 [US7] Add `check` target (full CI) to `Makefile`
- [ ] T069 [US7] Update `help` target with all test commands

**Checkpoint**: Developers can run `make help` and see all available test commands

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, validation

- [ ] T070 [P] Update TESTING.md with new infrastructure documentation
- [ ] T071 [P] Add type hints validation (mypy --strict) to all testing modules
- [ ] T072 [P] Run ruff linting and fix any issues
- [ ] T073 Run quickstart.md validation - verify all examples work
- [ ] T074 Verify SC-001: Kind cluster ready in <3 minutes
- [ ] T075 Verify SC-004: Zero `time.sleep()` calls via grep check
- [ ] T076 Verify SC-003: 100% requirement traceability

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup                    → No dependencies
Phase 2: Foundational             → Depends on Phase 1
    └─ Polling, Namespaces, Services
Phase 3: US1 (Kind Cluster)       → Depends on Phase 2
Phase 4: US2 (Base Classes)       → Depends on Phase 2
Phase 5: US3 (Traceability)       → Depends on Phase 1 only
Phase 6: US4 (Fixtures)           → Depends on US1 + US2
Phase 7: US5 (CI Workflow)        → Depends on US1 + US2 + US3
Phase 8: US6 (Polling Docs)       → Depends on Phase 2
Phase 9: US7 (Makefile)           → Depends on US1
Phase 10: Polish                  → Depends on all user stories
```

### User Story Dependencies

| Story | Priority | Dependencies | Can Start After |
|-------|----------|--------------|-----------------|
| US1 - Kind Cluster | P0 | Phase 2 | Foundational complete |
| US2 - Base Classes | P0 | Phase 2 | Foundational complete |
| US3 - Traceability | P0 | Phase 1 | Setup complete |
| US4 - Fixtures | P1 | US1, US2 | Kind + Base Classes complete |
| US5 - CI Workflow | P1 | US1, US2, US3 | Core P0 stories complete |
| US6 - Polling Docs | P1 | Phase 2 | Foundational complete |
| US7 - Makefile | P1 | US1 | Kind cluster complete |

### Parallel Opportunities

**After Phase 2 (Foundational) completes:**
- US1 (Kind Cluster) and US2 (Base Classes) can run in parallel
- US3 (Traceability) can run in parallel with US1/US2

**After US1 + US2 complete:**
- US4 (Fixtures) can start
- US5 (CI Workflow) can start (if US3 also complete)
- US7 (Makefile) can start

**Within each phase:**
- All tasks marked [P] can run in parallel
- K8s manifests (T017-T021) can all run in parallel
- Service fixtures (T041-T050) can all run in parallel

---

## Parallel Execution Examples

### Example 1: Foundational Phase (Phase 2)

```bash
# Launch all parallel foundational tasks together:
Task T011: "Unit tests for polling in testing/tests/unit/test_polling.py"
Task T013: "Unit tests for namespaces in testing/tests/unit/test_namespaces.py"
Task T015: "Unit tests for services in testing/tests/unit/test_services.py"
```

### Example 2: K8s Manifests (US1)

```bash
# Launch all K8s manifests in parallel:
Task T017: "Create testing/k8s/services/namespace.yaml"
Task T018: "Create testing/k8s/services/postgres.yaml"
Task T019: "Create testing/k8s/services/minio.yaml"
Task T020: "Create testing/k8s/services/polaris.yaml"
Task T021: "Create testing/k8s/services/dagster.yaml"
```

### Example 3: Service Fixtures (US4)

```bash
# Launch all fixture implementations in parallel:
Task T041: "Create testing/fixtures/postgres.py"
Task T043: "Create testing/fixtures/minio.py"
Task T045: "Create testing/fixtures/polaris.py"
Task T047: "Create testing/fixtures/duckdb.py"
Task T049: "Create testing/fixtures/dagster.py"
```

---

## Implementation Strategy

### MVP First (P0 Stories Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (polling, namespaces, services)
3. Complete Phase 3: US1 (Kind Cluster) - `make kind-up` works
4. Complete Phase 4: US2 (Base Classes) - tests can inherit
5. Complete Phase 5: US3 (Traceability) - unmarked tests fail
6. **STOP and VALIDATE**: Run `make kind-up`, create sample test, verify traceability
7. Deploy MVP - testing infrastructure is functional

### Full Delivery

1. Complete MVP (P0 stories)
2. Add Phase 6: US4 (Fixtures) - all services have fixtures
3. Add Phase 7: US5 (CI Workflow) - automated testing
4. Add Phase 8: US6 (Polling Docs) - documentation
5. Add Phase 9: US7 (Makefile) - developer experience
6. Complete Phase 10: Polish - quality assurance

---

## Task Summary

| Phase | Tasks | Parallel Tasks |
|-------|-------|----------------|
| Phase 1: Setup | 7 | 5 |
| Phase 2: Foundational | 8 | 4 |
| Phase 3: US1 Kind Cluster | 10 | 6 |
| Phase 4: US2 Base Classes | 8 | 4 |
| Phase 5: US3 Traceability | 7 | 1 |
| Phase 6: US4 Fixtures | 11 | 10 |
| Phase 7: US5 CI Workflow | 7 | 4 |
| Phase 8: US6 Polling | 3 | 2 |
| Phase 9: US7 Makefile | 8 | 0 |
| Phase 10: Polish | 7 | 3 |
| **Total** | **76** | **39** |

---

## Notes

- [P] tasks = different files, no dependencies
- [USn] label maps task to specific user story
- P0 stories (US1-US3) are MVP - complete first
- P1 stories (US4-US7) add value incrementally
- All integration tests must use `@pytest.mark.requirement()`
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
