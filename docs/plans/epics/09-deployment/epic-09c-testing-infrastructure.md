# Epic 9C: Testing Infrastructure

## Summary

Testing infrastructure provides the foundation for K8s-native testing. This includes Kind cluster configuration, test fixtures, integration test base classes, and CI/CD pipeline integration for automated testing.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-09c-testing-infra](https://linear.app/obsidianowl/project/floe-09c-testing-infra-bc1023480bf2)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-636 | Kind cluster configuration | CRITICAL |
| REQ-637 | Test base classes | HIGH |
| REQ-638 | Service fixtures | HIGH |
| REQ-639 | Namespace isolation | HIGH |
| REQ-640 | Test data management | HIGH |
| REQ-641 | Polling utilities | HIGH |
| REQ-642 | CI/CD integration | CRITICAL |
| REQ-643 | Test parallelization | MEDIUM |
| REQ-644 | Test reporting | HIGH |
| REQ-645 | Coverage analysis | HIGH |
| REQ-646 | Flaky test detection | MEDIUM |
| REQ-647 | Test categorization | HIGH |
| REQ-648 | Requirement traceability | CRITICAL |
| REQ-649 | Performance benchmarks | LOW |
| REQ-650 | Test documentation | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0064](../../../architecture/adr/0064-testing-strategy.md) - Testing strategy
- [ADR-0065](../../../architecture/adr/0065-k8s-native-testing.md) - K8s-native testing

### Documentation
- [TESTING.md](../../../TESTING.md) - Testing guide

### Contracts
- `IntegrationTestBase` - Base class for integration tests
- `ServiceFixture` - Service availability fixtures

---

## File Ownership (Exclusive)

```text
testing/
├── base_classes/
│   ├── __init__.py
│   └── integration_test_base.py    # IntegrationTestBase
├── fixtures/
│   ├── __init__.py
│   ├── services.py                  # Service fixtures
│   ├── namespaces.py                # Namespace management
│   └── data.py                      # Test data helpers
├── k8s/
│   ├── kind-config.yaml             # Kind cluster config
│   ├── kind-values.yaml             # Helm values for Kind
│   └── setup-cluster.sh             # Cluster setup script
├── traceability/
│   ├── __init__.py
│   └── checker.py                   # Requirement traceability
└── ci/
    ├── test-unit.sh
    ├── test-integration.sh
    └── test-e2e.sh
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 9B | Uses Helm charts for test setup |
| Blocks | None | Terminal Epic in deployment chain |

---

## User Stories (for SpecKit)

### US1: Kind Cluster Setup (P0)
**As a** developer
**I want** a local Kind cluster for testing
**So that** I can run integration tests locally

**Acceptance Criteria**:
- [ ] `make test-k8s` creates Kind cluster
- [ ] Platform services deployed via Helm
- [ ] Cluster persists between test runs
- [ ] `make test-k8s-clean` tears down

### US2: IntegrationTestBase (P0)
**As a** test author
**I want** a base class for integration tests
**So that** common setup is handled automatically

**Acceptance Criteria**:
- [ ] `IntegrationTestBase` class available
- [ ] Service availability checks
- [ ] Unique namespace generation
- [ ] Cleanup after tests

### US3: Requirement Traceability (P0)
**As a** quality engineer
**I want** tests linked to requirements
**So that** coverage is verifiable

**Acceptance Criteria**:
- [ ] `@pytest.mark.requirement()` marker
- [ ] Traceability report generation
- [ ] Coverage gap identification
- [ ] CI gate for 100% coverage

### US4: CI/CD Integration (P1)
**As a** platform developer
**I want** tests running in CI automatically
**So that** regressions are caught early

**Acceptance Criteria**:
- [ ] Unit tests in CI (fast)
- [ ] Integration tests in CI (K8s)
- [ ] E2E tests in CI (full stack)
- [ ] Test result reporting

### US5: Polling Utilities (P1)
**As a** test author
**I want** polling helpers for async operations
**So that** I don't use hardcoded sleeps

**Acceptance Criteria**:
- [ ] `wait_for_condition()` function
- [ ] `wait_for_service()` function
- [ ] Configurable timeout
- [ ] Clear failure messages

---

## Technical Notes

### Key Decisions
- All tests run in Kubernetes (Kind for local)
- No Docker Compose (deprecated)
- IntegrationTestBase for service tests
- Polling, never sleeping

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CI resource constraints | MEDIUM | HIGH | Test parallelization, caching |
| Flaky tests | HIGH | MEDIUM | Retry logic, flake detection |
| Kind cluster stability | MEDIUM | MEDIUM | Fresh cluster per CI run |

### Test Strategy
- **Meta**: Testing the testing infrastructure itself
- **Smoke**: Quick verification of test setup
- **Documentation**: TESTING.md accuracy

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/07-deployment-operations/`
- `TESTING.md`
- `testing/`

### Related Existing Code
- Helm charts from Epic 9B

### External Dependencies
- `pytest>=7.0.0`
- `pytest-cov>=4.0.0`
- `kind` CLI
- `kubectl` CLI
