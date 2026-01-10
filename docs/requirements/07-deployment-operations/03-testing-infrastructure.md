# REQ-636 to REQ-650: Kubernetes Testing Infrastructure

**Domain**: Deployment and Operations
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines Kind (Kubernetes IN Docker) cluster setup, test execution infrastructure, and result collection for running integration and E2E tests in Kubernetes. All integration and E2E tests must run in Kubernetes clusters, not on CI runners with mocked services.

**Key Principle**: Infrastructure parity (ADR-0017) - test in K8s like production

## Requirements

### REQ-636: Kind Cluster Creation **[New]**

**Requirement**: System MUST create Kind clusters for integration and E2E testing in CI pipelines.

**Rationale**: Enables testing actual K8s behavior without Docker Compose.

**Acceptance Criteria**:
- [ ] Integration tests: 1-node Kind cluster (minimal resource overhead)
- [ ] E2E tests: 3-node Kind cluster (tests multi-node scheduling)
- [ ] Cluster creation automated via CI workflow (helm/kind-action)
- [ ] Kind version: >= 0.20.0 (supports latest K8s features)
- [ ] K8s version: 1.27+ (feature parity with production)
- [ ] Cluster lifecycle: create at test start, destroy at test end
- [ ] Container runtime: containerd (not docker, default in Kind)

**Enforcement**:
- Kind cluster creation tests (cluster starts successfully)
- kubectl connectivity tests (can access cluster)
- Node readiness tests (all nodes Ready)

**Constraints**:
- MUST use Kind for local and CI testing (no Docker Compose)
- MUST destroy cluster after tests (clean up resources)
- MUST use same K8s version as production
- FORBIDDEN to use Minikube or other K8s distributions (Kind is standard)

**Test Coverage**: `tests/integration/test_kind_cluster.py`

**Traceability**:
- ADR-0017 (Kubernetes-Based Testing Infrastructure)
- Kind documentation (https://kind.sigs.k8s.io/)

---

### REQ-637: Kind Cluster Configuration **[New]**

**Requirement**: System MUST provide Kind cluster configuration files for different test scenarios.

**Rationale**: Enables reproducible cluster setup with specific features (ingress, storage, CNI).

**Acceptance Criteria**:
- [ ] Config file: testing/k8s/kind-config.yaml
- [ ] Features enabled: local storage provisioner, ingress controller (optional)
- [ ] Image preloading: pre-load platform images to avoid registry pulls
- [ ] Port forwarding: map K8s ports to host (for local testing)
- [ ] Extra mounts: optional mount host directories into cluster
- [ ] Customizable: support different configs for unit/integration/E2E tests

**Enforcement**:
- Config syntax validation (YAML parse succeeds)
- Cluster creation with config tests
- Feature availability tests (local storage works, ingress responds)

**Constraints**:
- MUST use Kind config file (not command-line flags)
- MUST support image preloading (speeds up tests)
- MUST enable local storage provisioner (tests need PVCs)
- FORBIDDEN to require manual cluster creation

**Test Coverage**: `tests/integration/test_kind_config.py`

**Traceability**:
- Kind cluster configuration documentation
- testing/k8s/ directory

---

### REQ-638: Test Runner Container Image **[New]**

**Requirement**: System MUST provide test runner container image with pytest and all dependencies for running tests inside K8s.

**Rationale**: Enables tests to run as K8s Jobs without requiring test dependencies on CI runner.

**Acceptance Criteria**:
- [ ] Image: ghcr.io/anthropics/floe/test-runner:latest
- [ ] Base image: python:3.11-slim
- [ ] Dependencies: pytest, pytest-asyncio, pytest-kubernetes, uv (package manager)
- [ ] Entry point: `pytest` (configurable command)
- [ ] Volume mounts: /results for test output (JUnit XML, coverage reports)
- [ ] Environment variables: PYTHONUNBUFFERED=1, test configuration

**Enforcement**:
- Image build tests (image builds successfully)
- Image functionality tests (pytest runs in container)
- Dependency tests (all required packages available)

**Constraints**:
- MUST use lightweight base image (python:3.11-slim)
- MUST install uv for dependency management (reproducible)
- MUST use multi-stage build (reduce image size)
- FORBIDDEN to use full Python base image (too large)

**Test Coverage**: `tests/integration/test_runner_image.py`

**Traceability**:
- testing/ directory (Dockerfile)
- GitHub Actions workflow (image build and push)

---

### REQ-639: Test Job Execution **[New]**

**Requirement**: System MUST define and execute tests as Kubernetes Jobs inside Kind clusters.

**Rationale**: Enables testing K8s-specific behavior (service discovery, probes, resource limits).

**Acceptance Criteria**:
- [ ] Test Job manifest: templates/test-job.yaml
- [ ] Job specification: backoffLimit=0 (fail fast), ttlSecondsAfterFinished=3600
- [ ] Pod spec: security context (non-root), resource limits, volumes
- [ ] Environment: pod can access K8s API (kubernetes-client library)
- [ ] Logs captured: kubectl logs job/test-runner
- [ ] Results collected: JUnit XML from /results volume
- [ ] Test status: Job status reflects test success/failure

**Enforcement**:
- Test Job creation tests (manifest valid)
- Test execution tests (tests run and complete)
- Result collection tests (JUnit XML available)

**Constraints**:
- MUST use Job resource (not Pod for one-time execution)
- MUST set backoffLimit=0 (fail fast on test failure)
- MUST include pod security context (non-root)
- FORBIDDEN to use Deployment for tests (not one-time execution)

**Test Coverage**: `tests/integration/test_job_execution.py`

**Traceability**:
- REQ-602 (Job Execution Model)
- Kubernetes Job documentation

---

### REQ-640: Integration Test Environment **[New]**

**Requirement**: System MUST deploy minimal platform services to Kind cluster for integration tests (Dagster + DuckDB only).

**Rationale**: Enables component testing without full platform overhead.

**Acceptance Criteria**:
- [ ] Services deployed: Dagster webserver, Dagster daemon, PostgreSQL
- [ ] Compute: DuckDB (local SQLite, no external database)
- [ ] Catalog: in-memory or local Iceberg metadata (no Polaris)
- [ ] Skip: Cube, full observability stack, Airflow
- [ ] Deployment: Helm install with values-integration.yaml
- [ ] Health checks: all services ready before tests start

**Enforcement**:
- Minimal deployment tests (only required services deployed)
- Service health tests (ready probes pass)
- Service connectivity tests (pods can communicate)

**Constraints**:
- MUST minimize resource usage (fit on 1-2 node Kind cluster)
- MUST NOT deploy unused services
- MUST use DuckDB for compute (simplest setup)
- FORBIDDEN to deploy full Polaris/Cube stack for integration tests

**Test Coverage**: `tests/integration/test_integration_environment.py`

**Traceability**:
- ADR-0017 (test pyramid)
- values-integration.yaml (Helm values)

---

### REQ-641: E2E Test Environment **[New]**

**Requirement**: System MUST deploy full platform stack to Kind cluster for E2E tests (all services enabled).

**Rationale**: Enables complete workflow testing from spec to execution.

**Acceptance Criteria**:
- [ ] Services deployed: Dagster, Polaris, Cube, OTLP Collector, full observability
- [ ] Databases: PostgreSQL, Redis, MinIO (persistent storage)
- [ ] Compute options: DuckDB, Snowflake (if test credentials available)
- [ ] Catalog: Polaris REST API
- [ ] Semantic layer: Cube
- [ ] Observability: OTLP Collector, Jaeger (optional), Prometheus/Grafana (optional)
- [ ] Deployment: Helm install with values-e2e.yaml
- [ ] Health checks: wait for all services (>10min for cold start)

**Enforcement**:
- Full deployment tests (all services deployed)
- Service health tests (all services ready)
- Multi-node scheduling tests (pods spread across nodes)
- Resource consumption tests (cluster has enough resources)

**Constraints**:
- MUST deploy all services (E2E tests need full stack)
- MUST wait for all services ready (long startup time acceptable)
- MUST support 3+ node Kind clusters (for proper scheduling)
- FORBIDDEN to skip services in E2E (defeats purpose of end-to-end)

**Test Coverage**: `tests/e2e/test_e2e_environment.py`

**Traceability**:
- ADR-0017 (full platform E2E)
- values-e2e.yaml (Helm values)

---

### REQ-642: Service Health Monitoring **[New]**

**Requirement**: System MUST monitor service health during test execution and fail tests if services become unhealthy.

**Rationale**: Catches infrastructure issues early and prevents cascading test failures.

**Acceptance Criteria**:
- [ ] Pre-test checks: verify all required services are Ready (kubectl get pods)
- [ ] Runtime monitoring: watch for CrashLoopBackOff, ImagePullBackOff
- [ ] Health polling: HTTP/TCP probes to service endpoints
- [ ] Timeout: fail if service doesn't become Ready within timeout (default: 5min)
- [ ] Error collection: capture service logs on health check failure
- [ ] Test skip: gracefully skip tests if service unavailable (not hard failure)

**Enforcement**:
- Health check function tests (correctly identifies ready/unready state)
- Timeout tests (fails after timeout)
- Log collection tests (logs available on failure)

**Constraints**:
- MUST implement IntegrationTestBase.check_infrastructure() method
- MUST poll for health (not assume immediate readiness)
- MUST set reasonable timeout (5-10 minutes for cold start)
- FORBIDDEN to hardcoded wait times (use actual health checks)

**Test Coverage**: `tests/integration/test_health_monitoring.py`

**Traceability**:
- REQ-609 (Health Checks - Probes)
- testing/base_classes/integration_test_base.py

---

### REQ-643: Network Connectivity Testing **[New]**

**Requirement**: System MUST test pod-to-pod network connectivity as part of test infrastructure validation.

**Rationale**: Catches networking issues (DNS, network policies, service discovery).

**Acceptance Criteria**:
- [ ] DNS resolution: pod can resolve service names (kubectl exec ping)
- [ ] TCP connectivity: pod can reach service endpoints (nc, curl)
- [ ] HTTP connectivity: test HTTP requests to services
- [ ] Network policies: test allow/deny rules (if enabled)
- [ ] Connection pooling: verify connections reused (not exhausted)
- [ ] Failure detection: tests fail if connectivity broken

**Enforcement**:
- Connectivity tests (successful communication)
- DNS tests (name resolution works)
- Network policy tests (allow rules work, deny rules block)

**Constraints**:
- MUST test connectivity before running actual tests
- MUST detect network policy issues early
- MUST provide clear error messages on connectivity failure
- FORBIDDEN to assume network works (verify explicitly)

**Test Coverage**: `tests/integration/test_network_connectivity.py`

**Traceability**:
- REQ-604 (Service Discovery)
- REQ-608 (Network Policies)

---

### REQ-644: Test Result Collection **[New]**

**Requirement**: System MUST collect test results from K8s Job pods and upload to CI system.

**Rationale**: Enables CI to report test status and display results.

**Acceptance Criteria**:
- [ ] JUnit XML: collected from /results/junit.xml in test Job
- [ ] Coverage reports: collected from /results/coverage.xml
- [ ] Log files: collected from kubectl logs job/test-runner
- [ ] Upload to CI: results uploaded as artifacts or reported to CI system
- [ ] Test status: CI reports pass/fail based on Job status
- [ ] Result retention: results stored for 90 days (in CI artifacts)

**Enforcement**:
- Result collection tests (results available after Job completes)
- Upload tests (results successfully uploaded to CI)
- Status reporting tests (CI reflects correct status)

**Constraints**:
- MUST collect JUnit XML (standard test result format)
- MUST collect logs (for debugging failures)
- MUST handle collection even on test failure
- FORBIDDEN to lose test results on pod deletion

**Test Coverage**: `tests/integration/test_result_collection.py`

**Traceability**:
- CI workflow (result collection steps)
- GitHub Actions artifacts documentation

---

### REQ-645: Test Isolation and Cleanup **[New]**

**Requirement**: System MUST ensure tests are isolated and clean up resources between test runs.

**Rationale**: Prevents test pollution and enables independent test execution.

**Acceptance Criteria**:
- [ ] Namespace isolation: each test run uses unique namespace (or cleanup between)
- [ ] Unique identifiers: test resources use unique names (uuid-based)
- [ ] Cleanup: resources deleted after test completion (namespaces, PVCs, Secrets)
- [ ] Data isolation: test data doesn't affect other tests
- [ ] Concurrent safety: multiple tests can run in parallel (in different namespaces)
- [ ] Rollback: failed tests don't leave dangling resources

**Enforcement**:
- Namespace uniqueness tests (each test has unique namespace)
- Cleanup verification tests (resources deleted after test)
- Concurrent test tests (multiple tests run without interference)

**Constraints**:
- MUST use unique namespaces or cleanup between tests
- MUST delete resources on test failure (not leave dangling state)
- MUST NOT share state between tests
- FORBIDDEN to rely on cleanup order (each test independent)

**Test Coverage**: `tests/integration/test_isolation_cleanup.py`

**Traceability**:
- TESTING.md (test isolation patterns)
- testing/base_classes/integration_test_base.py

---

### REQ-646: Test Timeout Management **[New]**

**Requirement**: System MUST enforce reasonable timeouts for test execution to prevent hanging tests.

**Rationale**: Prevents test infrastructure from waiting indefinitely on broken services.

**Acceptance Criteria**:
- [ ] Job timeout: activeDeadlineSeconds=3600 (1 hour max for test Job)
- [ ] Individual test timeout: 5 minutes per test (configurable)
- [ ] Service startup timeout: 10 minutes for service deployment
- [ ] Health check timeout: 30 seconds per probe
- [ ] Database migration timeout: 5 minutes
- [ ] Timeout exceeded: test fails with clear error message

**Enforcement**:
- Timeout configuration tests (values set correctly)
- Timeout behavior tests (test fails on timeout, not hangs)
- Error message tests (clear message on timeout)

**Constraints**:
- MUST set activeDeadlineSeconds on test Job
- MUST set pytest timeout (pytest-timeout plugin)
- MUST set reasonable service startup timeout
- FORBIDDEN to set infinite timeouts (even for slow tests)

**Test Coverage**: `tests/integration/test_timeout_management.py`

**Traceability**:
- pytest-timeout documentation
- Kubernetes Job timeouts

---

### REQ-647: CI/CD Integration **[New]**

**Requirement**: System MUST integrate test execution with CI/CD pipeline (GitHub Actions) with automated Kind cluster creation/destruction.

**Rationale**: Enables automated testing on every commit.

**Acceptance Criteria**:
- [ ] GitHub Actions workflow: create Kind cluster, deploy services, run tests, cleanup
- [ ] Matrix jobs: unit (no K8s), integration (1-node), E2E (3-node)
- [ ] Parallelization: run multiple test jobs in parallel
- [ ] Artifact storage: store test results and logs
- [ ] Status reporting: CI reports pass/fail, creates checks
- [ ] Retry logic: automatically retry flaky tests (up to 2 retries)

**Enforcement**:
- Workflow validation tests (.github/workflows/*.yml syntax)
- Local workflow testing (act tool for GitHub Actions testing)
- CI integration tests (workflow runs successfully)

**Constraints**:
- MUST use helm/kind-action for Kind cluster creation
- MUST parallelize test jobs (speed up CI pipeline)
- MUST collect artifacts on success and failure
- FORBIDDEN to skip flaky tests (fix root cause instead)

**Test Coverage**: CI workflow tests (manual validation)

**Traceability**:
- GitHub Actions documentation
- helm/kind-action (Helm Kind GitHub Action)

---

### REQ-648: Local Development Testing **[New]**

**Requirement**: System MUST enable developers to run integration and E2E tests locally with `make test-k8s` command.

**Rationale**: Enables faster feedback loop during development.

**Acceptance Criteria**:
- [ ] Makefile target: `make test-k8s` (create Kind cluster, run integration tests)
- [ ] Makefile target: `make test-e2e` (create Kind cluster, run E2E tests)
- [ ] Makefile target: `make test-k8s-cleanup` (destroy Kind cluster)
- [ ] Prerequisite: Docker/containerd must be running
- [ ] Documentation: docs/guides/local-testing.md explains setup
- [ ] One-command invocation: single command runs everything

**Enforcement**:
- Makefile tests (targets exist and work)
- Local testing documentation tests (README has instructions)
- End-to-end local testing (full flow works)

**Constraints**:
- MUST provide single `make` command (no manual steps)
- MUST auto-detect Kind cluster existence (don't recreate)
- MUST provide clear error messages on prerequisites missing
- FORBIDDEN to require manual cluster setup

**Test Coverage**: Local testing verification (manual)

**Traceability**:
- Makefile (targets implementation)
- TESTING.md (local testing guidance)

---

### REQ-649: Test Debugging Support **[New]**

**Requirement**: System MUST provide debugging tools and procedures for failed tests.

**Rationale**: Enables developers to diagnose and fix test failures.

**Acceptance Criteria**:
- [ ] Pod logs: `kubectl logs` available for failed test pods
- [ ] Pod shell: `kubectl exec` available for debugging inside pod
- [ ] Persistent pod: option to keep failed pod for inspection (vs. auto-cleanup)
- [ ] Event logs: `kubectl get events` shows pod scheduling/readiness issues
- [ ] Resource usage: `kubectl top node/pod` shows resource consumption
- [ ] Debugging docs: docs/guides/test-debugging.md explains procedures

**Enforcement**:
- Debugging tool availability tests (kubectl works on Kind cluster)
- Log access tests (logs retrievable from failed pods)
- Pod inspection tests (can exec into pod)

**Constraints**:
- MUST preserve pod on failure (for debugging)
- MUST provide clear instructions for debugging
- MUST expose pod logs and events
- FORBIDDEN to cleanup pods immediately on failure (retain for debugging)

**Test Coverage**: Local debugging validation (manual)

**Traceability**:
- TESTING.md (debugging procedures)
- docs/guides/test-debugging.md (debugging guide)

---

### REQ-650: Test Performance Monitoring **[New]**

**Requirement**: System MUST collect and report test performance metrics (execution time, resource usage).

**Rationale**: Enables tracking test performance regressions and infrastructure issues.

**Acceptance Criteria**:
- [ ] Execution time: total time and per-test breakdown
- [ ] Resource usage: CPU and memory consumption during tests
- [ ] Cluster metrics: node resource utilization
- [ ] Performance trend: historical comparison to detect regressions
- [ ] Reporting: test results include performance metrics
- [ ] Thresholds: alert if tests slower than baseline (configurable)

**Enforcement**:
- Metric collection tests (metrics captured correctly)
- Performance reporting tests (results include metrics)
- Trend analysis tests (can compare to baseline)

**Constraints**:
- MUST collect execution time per test (use pytest plugins)
- MUST collect cluster resource metrics (kubectl top)
- MUST report metrics in test results
- FORBIDDEN to hardcode performance thresholds (make configurable)

**Test Coverage**: `tests/integration/test_performance_monitoring.py`

**Traceability**:
- pytest plugins (pytest-benchmark, pytest-duration)
- Kubernetes metrics API
- GitHub Actions workflow reporting

---

## Plugin-Specific Test Fixtures

> **Architectural Note**: Plugin-specific test fixtures are **NOT** part of Epic 9C. They are delivered with their respective plugin epics, using the testing framework provided by Epic 9C.

Epic 9C provides the **framework** for testing:
- `IntegrationTestBase`, `PluginTestBase`, `AdapterTestBase` base classes
- Polling utilities (`wait_for_condition`, `wait_for_service`)
- Namespace isolation helpers
- Kind cluster configuration
- Core service fixtures (PostgreSQL, MinIO, Polaris, DuckDB, Dagster)

Each plugin epic is responsible for adding its own test fixtures:

| Plugin Type | Fixture File | Owning Epic |
|-------------|--------------|-------------|
| Telemetry (Jaeger, OTEL) | `testing/fixtures/telemetry.py` | Epic 6A |
| Lineage (Marquez, DataHub) | `testing/fixtures/lineage.py` | Epic 6B |
| DBT | `testing/fixtures/dbt.py` | Epic 5A |
| Semantic Layer (Cube) | `testing/fixtures/cube.py` | Semantic Epic |
| Ingestion (dlt, Airbyte) | `testing/fixtures/ingestion.py` | Ingestion Epic |
| Secrets (Vault, K8s) | `testing/fixtures/secrets.py` | Epic 7A |
| Identity (Keycloak, Dex) | `testing/fixtures/identity.py` | Epic 7A |
| Quality (GX, Soda) | `testing/fixtures/quality.py` | Epic 5B |

This follows the **file ownership principle**: each epic owns everything related to its plugin, including test fixtures
