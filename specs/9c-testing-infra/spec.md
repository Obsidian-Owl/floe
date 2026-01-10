# Feature Specification: K8s-Native Testing Infrastructure

**Feature Branch**: `001-testing-infra`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "K8s-native testing infrastructure for floe platform - Kind cluster, test base classes, service fixtures, and CI workflow updates"

**Linear Project**: [floe-09c-testing-infra](https://linear.app/obsidianowl/project/floe-09c-testing-infra-bc1023480bf2)

## Overview

This feature establishes the foundational testing infrastructure for the floe platform. It provides Kubernetes-native testing capabilities using Kind clusters, standardized test base classes, service fixtures for integration testing, and CI workflow enhancements.

**Wave 0 BLOCKER**: This is the foundation for ALL other epics. No feature PRs can be merged without this infrastructure in place.

### Existing CI Infrastructure (Already Complete)

The project already has Stage 1 CI in `.github/workflows/ci.yml`:

| Job             | Status   | Description                              |
|-----------------|----------|------------------------------------------|
| lint-typecheck  | Complete | Ruff + mypy --strict                     |
| unit-tests      | Complete | Python 3.10-3.12 matrix, 80% coverage    |
| contract-tests  | Complete | Cross-package validation                 |
| sonarcloud      | Complete | Quality gate + coverage                  |
| ci-success      | Complete | Branch protection gate                   |

This feature adds Stage 2 capabilities (security scanning, integration tests with Kind cluster).

---

## Clarifications

### Session 2026-01-09

- Q: How should integration/E2E tests execute - from host or as K8s Jobs? → A: Tests run AS K8s Jobs inside the cluster (per ADR-0017), requiring a test-runner container image
- Q: For S3 emulation, should we use MinIO or LocalStack? → A: MinIO for alpha (simpler, faster, S3-only). LocalStack deferred to future AWS integration work post-alpha.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Kind Cluster Setup (Priority: P0)

As a developer, I want to spin up a local Kind cluster for testing so that I can run integration tests against real Kubernetes services without needing a remote cluster.

**Why this priority**: Foundation for all integration testing. Without a local cluster, no integration tests can run, blocking all other development.

**Independent Test**: Can be fully tested by running `make kind-up`, verifying cluster is accessible via `kubectl`, and confirming test services are healthy. Delivers immediate value by enabling local integration testing.

**Acceptance Scenarios**:

1. **Given** Kind is installed on the developer's machine, **When** I run `make kind-up`, **Then** a Kind cluster is created with test services deployed
2. **Given** a Kind cluster is running, **When** I run `kubectl get pods -n floe-test`, **Then** I see all test services in Running state
3. **Given** a Kind cluster is running, **When** I run `make kind-down`, **Then** the cluster is completely removed

---

### User Story 2 - Integration Test Base Classes (Priority: P0)

As a test author, I want base classes that handle common integration test setup so that I can focus on writing test logic rather than boilerplate.

**Why this priority**: Required before any integration tests can be written. Provides consistent patterns and reduces test code duplication.

**Independent Test**: Can be tested by inheriting from `IntegrationTestBase` in a sample test and verifying service checks, namespace isolation, and cleanup work correctly.

**Acceptance Scenarios**:

1. **Given** I create a test class inheriting from `IntegrationTestBase`, **When** the test starts, **Then** service availability is verified before tests run
2. **Given** my test uses `generate_unique_namespace()`, **When** multiple tests run in parallel, **Then** each test has an isolated namespace
3. **Given** a test completes (pass or fail), **When** cleanup runs, **Then** test resources are removed from the cluster

---

### User Story 3 - Requirement Traceability (Priority: P0)

As a quality engineer, I want every test linked to a requirement so that I can verify test coverage and identify gaps.

**Why this priority**: Critical for quality gates. CI should fail if tests lack requirement markers.

**Independent Test**: Can be tested by running the traceability checker against test files and verifying it reports linked requirements and identifies unmarked tests.

**Acceptance Scenarios**:

1. **Given** a test has `@pytest.mark.requirement("REQ-XXX")` marker, **When** traceability report runs, **Then** the test is linked to that requirement
2. **Given** a test lacks a requirement marker, **When** traceability check runs in CI, **Then** the check fails with a clear error message
3. **Given** all tests have markers, **When** traceability report runs, **Then** it shows 100% coverage of documented requirements

---

### User Story 4 - Service Fixtures (Priority: P1)

As a test author, I want pytest fixtures for test services (PostgreSQL, Polaris, MinIO, DuckDB, Dagster) so that I can easily set up and tear down service connections in my tests.

**Why this priority**: Required for testing specific integrations. Can be developed incrementally per service.

**Independent Test**: Each fixture (e.g., `postgres_connection`) can be tested independently by using it in a simple test that verifies connectivity.

**Acceptance Scenarios**:

1. **Given** I use the `postgres_connection` fixture, **When** my test runs, **Then** I get a working connection to a test database
2. **Given** I use the `polaris_catalog` fixture, **When** my test runs, **Then** I get a catalog client with a unique namespace
3. **Given** my test completes, **When** cleanup runs, **Then** test data is removed (databases dropped, namespaces deleted)

---

### User Story 5 - CI Workflow Updates (Priority: P1)

As a platform maintainer, I want CI to run integration tests automatically so that regressions are caught before merge.

**Why this priority**: Automates quality gates. Depends on Kind cluster and test infrastructure being ready.

**Independent Test**: Can be tested by pushing a PR and verifying the integration-tests job runs in GitHub Actions with Kind cluster setup.

**Acceptance Scenarios**:

1. **Given** a PR is opened, **When** CI runs, **Then** security scans (Bandit, pip-audit) execute
2. **Given** CI starts integration tests, **When** Kind cluster setup begins, **Then** cluster is created and services deployed
3. **Given** all tests pass, **When** CI completes, **Then** ci-success gate is green

---

### User Story 6 - Polling Utilities (Priority: P1)

As a test author, I want polling helpers for async operations so that I avoid unreliable hardcoded sleeps.

**Why this priority**: Improves test reliability. Flaky tests with sleeps waste CI time and developer attention.

**Independent Test**: Can be tested by using `wait_for_condition()` to wait for a service to become ready and verifying it returns promptly when ready or times out with a clear message.

**Acceptance Scenarios**:

1. **Given** I call `wait_for_condition(lambda: service.is_ready(), timeout=30)`, **When** the service becomes ready, **Then** the function returns immediately
2. **Given** I call `wait_for_service("polaris", 8181, timeout=60)`, **When** the service never becomes ready, **Then** the function raises a clear timeout error
3. **Given** a test uses polling utilities, **When** I search for `time.sleep(` in test code, **Then** no hardcoded sleeps are found

---

### User Story 7 - Makefile Test Targets (Priority: P1)

As a developer, I want simple make commands for test execution so that I don't need to remember complex pytest invocations.

**Why this priority**: Developer experience. Makes testing accessible and consistent.

**Independent Test**: Can be tested by running `make help` and verifying all test targets are documented, then running each target.

**Acceptance Scenarios**:

1. **Given** I run `make help`, **When** output is displayed, **Then** all test targets are listed with descriptions
2. **Given** I run `make test-unit`, **When** tests complete, **Then** only unit tests ran (no K8s required)
3. **Given** I run `make test-integration`, **When** tests complete, **Then** integration tests ran against Kind cluster

---

### Edge Cases

- What happens when Kind cluster creation fails due to Docker not running?
  - Clear error message directing user to start Docker
- What happens when a test service fails to become healthy?
  - Timeout with specific service name and port in error message
- What happens when tests run in parallel and access the same namespace?
  - Unique namespace generation prevents collision
- What happens when CI runner has limited resources?
  - Test parallelization with resource constraints documented

---

## Requirements *(mandatory)*

### Functional Requirements

**Kind Cluster & Infrastructure**

- **FR-001**: System MUST provide a Kind cluster configuration for local Kubernetes testing
- **FR-002**: System MUST deploy test services using raw K8s manifests (NOT Helm, to avoid circular dependency)
- **FR-003**: System MUST support cluster creation via `make kind-up` command
- **FR-004**: System MUST support cluster teardown via `make kind-down` command
- **FR-004a**: System MUST provide a test-runner container image for executing tests as K8s Jobs
- **FR-004b**: System MUST provide K8s Job manifests for running integration/E2E tests inside the cluster

**Test Base Classes**

- **FR-005**: System MUST provide `IntegrationTestBase` class with service availability checks
- **FR-006**: System MUST provide `PluginTestBase` class for plugin compliance testing
- **FR-007**: System MUST provide `AdapterTestBase` class for adapter testing
- **FR-008**: Base classes MUST generate unique namespaces per test to ensure isolation
- **FR-009**: Base classes MUST clean up resources after tests complete

**Service Fixtures**

- **FR-010**: System MUST provide PostgreSQL fixture with connection management
- **FR-011**: System MUST provide DuckDB fixture with in-memory and file options
- **FR-012**: System MUST provide Polaris catalog fixture with namespace isolation
- **FR-013**: System MUST provide MinIO/S3 fixture with bucket management
- **FR-014**: System MUST provide Dagster fixture with asset execution helpers

**Polling & Reliability**

- **FR-015**: System MUST provide `wait_for_condition()` polling utility
- **FR-016**: System MUST provide `wait_for_service()` utility for health checks
- **FR-017**: System MUST NOT use hardcoded `time.sleep()` in test code

**Requirement Traceability**

- **FR-018**: System MUST provide `@pytest.mark.requirement()` marker for tests
- **FR-019**: System MUST provide traceability report generation
- **FR-020**: System MUST fail CI if tests lack requirement markers

**CI Workflow Updates**

- **FR-021**: System MUST add security job to existing `ci.yml` (Bandit, pip-audit)
- **FR-022**: System MUST add integration-tests job with Kind cluster setup
- **FR-023**: System MUST update ci-success gate to include new jobs

**Makefile Targets**

- **FR-024**: System MUST provide `make test` target for all tests
- **FR-025**: System MUST provide `make test-unit` target for unit tests only
- **FR-026**: System MUST provide `make test-integration` target for K8s tests
- **FR-027**: System MUST provide `make check` target for full CI checks
- **FR-028**: System MUST provide `make help` target documenting all commands

### Key Entities

- **IntegrationTestBase**: Base class providing service checks, namespace generation, and cleanup for integration tests
- **ServiceFixture**: Pytest fixtures providing connections to test services with automatic cleanup
- **Kind Cluster**: Local Kubernetes cluster for running integration tests
- **Requirement Marker**: pytest marker linking tests to requirements for traceability
- **Test Runner Image**: Container image containing pytest and test dependencies for executing tests as K8s Jobs

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can set up a local test cluster in under 3 minutes with `make kind-up`
- **SC-002**: Integration tests complete within 10 minutes on CI runners
- **SC-003**: 100% of integration tests have requirement traceability markers
- **SC-004**: Zero hardcoded `time.sleep()` calls in test code (verified by grep check)
- **SC-005**: All test services (PostgreSQL, Polaris, MinIO, DuckDB, Dagster) are accessible within 2 minutes of cluster creation
- **SC-006**: Test isolation is complete - parallel test runs do not interfere with each other
- **SC-007**: CI pipeline catches 100% of integration test failures before merge to main

---

## Assumptions

1. Developers have Docker installed and running (required for Kind)
2. Developers have `kubectl` and `kind` CLI tools installed
3. CI runners have sufficient resources for Kind cluster (4GB RAM, 2 CPUs minimum)
4. MinIO is used for S3 emulation in alpha (simpler, faster). LocalStack deferred to future AWS integration.
5. Raw K8s manifests are used instead of Helm to avoid dependency on Epic 9B

---

## Out of Scope

- Helm charts for test services (covered by Epic 9B)
- Production deployment infrastructure (covered by Epic 9A)
- End-to-end tests beyond basic smoke tests (added incrementally per feature)
- Performance benchmarking infrastructure (future enhancement)
