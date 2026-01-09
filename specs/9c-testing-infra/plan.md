# Implementation Plan: K8s-Native Testing Infrastructure

**Branch**: `9c-testing-infra` | **Date**: 2026-01-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/9c-testing-infra/spec.md`

## Summary

Establish foundational K8s-native testing infrastructure for the floe platform, enabling integration tests to run inside Kind clusters matching production deployment patterns. This includes test base classes, service fixtures (MinIO, PostgreSQL, Polaris, DuckDB, Dagster), polling utilities, requirement traceability enforcement, and CI workflow extensions for Stage 2 (security scanning + integration tests).

## Technical Context

**Language/Version**: Python 3.10+ (aligned with existing floe packages)
**Primary Dependencies**: pytest>=7.0.0, pytest-cov>=4.0.0, kubernetes (Python client), structlog
**Storage**: N/A (test infrastructure, no persistent storage)
**Testing**: pytest with custom IntegrationTestBase, test-runner container image for K8s Jobs
**Target Platform**: Kind cluster (local), GitHub Actions runners (CI)
**Project Type**: Single project (testing module within floe monorepo)
**Performance Goals**: Kind cluster ready <3 min, all test services healthy <2 min, integration tests complete <10 min
**Constraints**: CI runner resources (4GB RAM, 2 CPUs minimum for Kind)
**Scale/Scope**: Foundation for all floe epics; enables ~50+ integration tests across platform

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`testing/` module at repo root)
- [x] No SQL parsing/validation in Python (N/A for test infra)
- [x] No orchestration logic outside floe-dagster (N/A - test fixtures only)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (N/A - not a plugin)
- [x] Plugin registered via entry point (N/A)
- [x] PluginMetadata declares name, version, floe_api_version (N/A)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s) - test infra supports K8s-native
- [x] Pluggable choices documented in manifest.yaml (N/A)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (N/A - test utilities)
- [x] Pydantic v2 models for all schemas (base classes will use Pydantic for config)
- [x] Contract changes follow versioning rules (N/A)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster (THIS EPIC IMPLEMENTS THIS)
- [x] No `pytest.skip()` usage (enforced by design)
- [x] `@pytest.mark.requirement()` on all integration tests (THIS EPIC IMPLEMENTS THIS)

**Principle VI: Security First**
- [x] Input validation via Pydantic (test configs)
- [x] Credentials use SecretStr (test service credentials)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (test infra is foundation layer)
- [x] Layer ownership respected (N/A)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (test fixtures can emit traces for debugging)
- [x] OpenLineage events for data transformations (N/A for test infra)

**Constitution Check: PASS** - This epic implements Principle V (K8s-Native Testing) for the platform.

## Project Structure

### Documentation (this feature)

```text
specs/9c-testing-infra/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
testing/
├── __init__.py
├── base_classes/
│   ├── __init__.py
│   ├── integration_test_base.py    # IntegrationTestBase class
│   ├── plugin_test_base.py         # PluginTestBase class
│   └── adapter_test_base.py        # AdapterTestBase class
├── fixtures/
│   ├── __init__.py
│   ├── conftest.py                 # pytest plugin registration
│   ├── services.py                 # Service health check utilities
│   ├── polling.py                  # wait_for_condition, wait_for_service
│   ├── namespaces.py               # Unique namespace generation
│   ├── data.py                     # Test data helpers
│   ├── postgres.py                 # PostgreSQL fixture
│   ├── duckdb.py                   # DuckDB fixture
│   ├── polaris.py                  # Polaris catalog fixture
│   ├── minio.py                    # MinIO/S3 fixture
│   └── dagster.py                  # Dagster fixture
├── k8s/
│   ├── kind-config.yaml            # Kind cluster configuration
│   ├── services/                   # Raw K8s manifests (NOT Helm)
│   │   ├── namespace.yaml          # floe-test namespace
│   │   ├── postgres.yaml           # PostgreSQL deployment
│   │   ├── polaris.yaml            # Polaris catalog deployment
│   │   ├── minio.yaml              # MinIO S3 deployment
│   │   └── dagster.yaml            # Dagster webserver deployment
│   ├── jobs/
│   │   └── test-runner.yaml        # K8s Job manifest for test execution
│   ├── setup-cluster.sh            # Cluster creation script
│   └── cleanup-cluster.sh          # Cluster teardown script
├── traceability/
│   ├── __init__.py
│   └── checker.py                  # Requirement traceability checker
├── ci/
│   ├── test-unit.sh                # Unit test runner script
│   ├── test-integration.sh         # Integration test runner script
│   └── test-e2e.sh                 # E2E test runner script
└── Dockerfile                      # Test runner container image

# Root-level files
Makefile                            # Test targets (kind-up, kind-down, test-*)
.github/workflows/ci.yml            # CI workflow (UPDATE Stage 2)
```

**Structure Decision**: Testing infrastructure placed at repo root (`testing/`) as a shared module used by all packages. This follows the epic's file ownership and avoids per-package duplication.

## Complexity Tracking

> No Constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
