# Epic 9C: Testing Infrastructure

## Summary

Testing infrastructure provides the foundation for K8s-native testing. This includes Kind cluster configuration, test fixtures, integration test base classes, and CI/CD pipeline integration for automated testing.

**Wave 0 BLOCKER**: This epic is the foundation for ALL other epics. No feature PRs can be merged without this infrastructure. Test services use raw K8s manifests (not Helm) to avoid circular dependencies.

### Existing CI Infrastructure (Stage 1 - Complete)

The project already has Stage 1 CI in `.github/workflows/ci.yml`:

| Job             | Status   | Description                              |
|-----------------|----------|------------------------------------------|
| lint-typecheck  | Complete | Ruff + mypy --strict                     |
| unit-tests      | Complete | Python 3.10-3.12 matrix, 80% coverage    |
| contract-tests  | Complete | Cross-package validation                 |
| ci-success      | Complete | Branch protection gate                   |

See `.github/CI.md` for full CI strategy documentation.

**This epic adds Stage 2**: Security scanning (Bandit, pip-audit) and integration tests with Kind cluster.

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
| REQ-651 | PostgreSQL test fixtures | HIGH |
| REQ-652 | DuckDB test fixtures | HIGH |
| REQ-653 | Polaris test fixtures | HIGH |
| REQ-654 | MinIO/S3 test fixtures | HIGH |
| REQ-655 | Dagster test fixtures | HIGH |
| REQ-656 | K8s manifests for test services (raw, not Helm) | HIGH |
| REQ-657 | Makefile test targets | CRITICAL |
| REQ-658 | Extend CI workflow with security + integration tests | CRITICAL |
| REQ-659 | PluginTestBase class | HIGH |
| REQ-660 | AdapterTestBase class | HIGH |

> **Note**: Plugin-specific test fixtures (telemetry, lineage, semantic layer, ingestion, secrets, identity, quality) are delivered with their respective plugin epics (5A, 5B, 6A, 6B, 7A, etc.), not in this epic. Epic 9C provides the testing **framework** that those fixtures build upon.

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
│   ├── integration_test_base.py    # IntegrationTestBase
│   ├── plugin_test_base.py         # PluginTestBase
│   └── adapter_test_base.py        # AdapterTestBase
├── fixtures/
│   ├── __init__.py
│   ├── services.py                 # Service health checks
│   ├── polling.py                  # Polling utilities
│   ├── namespaces.py               # Namespace management
│   ├── data.py                     # Test data helpers
│   ├── postgres.py                 # PostgreSQL fixtures
│   ├── duckdb.py                   # DuckDB fixtures
│   ├── polaris.py                  # Polaris fixtures
│   ├── minio.py                    # MinIO fixtures
│   └── dagster.py                  # Dagster fixtures
│   # Note: Plugin-specific fixtures (telemetry, lineage, etc.) are
│   # added by their respective plugin epics using this framework
├── k8s/
│   ├── kind-config.yaml            # Kind cluster config
│   ├── services/                   # Raw K8s manifests (NOT Helm)
│   │   ├── namespace.yaml
│   │   ├── postgres.yaml
│   │   ├── polaris.yaml
│   │   ├── minio.yaml
│   │   └── dagster.yaml
│   ├── setup-cluster.sh            # Cluster setup script
│   └── cleanup-cluster.sh          # Cluster teardown
├── traceability/
│   ├── __init__.py
│   └── checker.py                  # Requirement traceability
└── ci/
    ├── test-unit.sh
    ├── test-integration.sh
    └── test-e2e.sh

Makefile                            # Test targets
.github/workflows/ci.yml            # CI workflow (UPDATE existing Stage 1)
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | None | Wave 0 BLOCKER - foundation for all testing |
| Blocks | 1 | Plugin Registry needs test infrastructure |
| Blocks | 2A-B | Configuration needs test infrastructure |
| Blocks | 3A-D | Governance needs test infrastructure |
| Blocks | 4A-D | Core Plugins need test infrastructure |
| Blocks | 5A-B | Transformation needs test infrastructure |
| Blocks | 6A-B | Observability needs test infrastructure |
| Blocks | 7A-C | Security needs test infrastructure |
| Blocks | 8A-C | Artifact Distribution needs test infrastructure |
| Blocks | 9A-B | Deployment needs test infrastructure |

---

## User Stories (for SpecKit)

### US1: Kind Cluster Setup (P0)
**As a** developer
**I want** a local Kind cluster for testing
**So that** I can run integration tests locally

**Acceptance Criteria**:
- [ ] `make kind-up` creates Kind cluster
- [ ] Test services deployed via raw K8s manifests
- [ ] Cluster persists between test runs
- [ ] `make kind-down` tears down cluster

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

### US4: CI/CD Integration - Stage 2 (P1)
**As a** platform developer
**I want** integration tests running in CI automatically
**So that** regressions are caught early

**Existing (Stage 1 - Complete)**:
- [x] Unit tests in CI (fast) - `.github/workflows/ci.yml`
- [x] Contract tests in CI

**Acceptance Criteria (Stage 2 - This Epic)**:
- [ ] Security job added (Bandit, pip-audit)
- [ ] Integration tests in CI (Kind cluster)
- [ ] E2E tests in CI (full stack)
- [ ] ci-success gate updated to include new jobs

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
- Raw K8s manifests for test services (NOT Helm - avoids 9B dependency)
- IntegrationTestBase for service tests
- Polling, never sleeping
- MinIO preferred over LocalStack for S3 (faster, simpler)

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
- `.github/workflows/ci.yml` - Stage 1 CI (lint, unit tests, contract tests)
- `.github/CI.md` - CI strategy documentation
- `.pre-commit-config.yaml` - Pre-commit and pre-push hooks

### External Dependencies
- `pytest>=7.0.0`
- `pytest-cov>=4.0.0`
- `kind` CLI
- `kubectl` CLI
