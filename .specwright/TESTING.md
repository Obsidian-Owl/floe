# floe Testing Strategy

Authority: Constitution (v1.7.0) > TESTING.md > patterns.md

---

## Boundaries

### Internal (test with real components, no mocks)

All infrastructure services run in a Kind cluster (`floe-test` namespace).
Integration and E2E tests hit real instances — never mock these.

| Dependency | Port | Rationale |
|------------|------|-----------|
| Polaris (REST catalog) | 8181 | Core to Iceberg table management. Mock hides catalog behavior. |
| Polaris Management API | 8182 | RBAC grants, principal management. Must test real REST semantics. |
| MinIO (S3-compatible) | 9000 | Storage layer for Iceberg data files. Real S3 API required. |
| PostgreSQL | 5432 | Metadata store for Dagster, Marquez, Polaris. Real SQL required. |
| Dagster Webserver | 3000 | Orchestration UI and GraphQL API. Real asset materialization. |
| Jaeger Query | 16686 | Trace verification. Real OTel pipeline required. |
| OTel Collector | 4317/4318 | Telemetry gateway. Real gRPC/HTTP export required. |
| Marquez | 5100 | OpenLineage lineage graph. Real event storage required. |
| OCI Registry | 5000 | Manifest attestation, signing, promotion workflows. |
| Keycloak | 8082 | Identity provider for RBAC integration tests. |
| Infisical (self-hosted) | 8083 | Secrets management integration tests. |
| Cube | 4000 | Semantic layer API. Real query engine required. |

### External (mock with contracts)

| Dependency | Mock Strategy | Rationale |
|------------|--------------|-----------|
| Cognee Cloud API | Contract tests (`tests/contract/test_cognee_api_contract.py`) | External SaaS. SSL/connectivity issues common. CamelCase field quirks. |
| GitHub API | `gh` CLI mocked in unit tests | External. PR creation tested via integration only. |

### Expensive (mock with documented rationale)

| Dependency | Mock Strategy | Live Testing | Rationale |
|------------|--------------|-------------|-----------|
| Infisical Cloud | Unit tests mock HTTP responses | Weekly nightly suite | SaaS with rate limits. Self-hosted instance in Kind for integration. |
| Cognee Cloud SDK (`cogwit`) | Unit tests mock SDK calls | Manual via `make cognee-test` | Per-request metered. SDK errors differ from REST errors. |

---

## Test Infrastructure

### Kind Cluster

**Setup**: `make kind-up` (deploys all services via Helm to `floe-test` namespace)
**Teardown**: `make kind-down`
**Chart**: `charts/floe-platform/values-test.yaml`

All integration and E2E tests require the Kind cluster. Tests FAIL (never skip)
when services are unavailable — this is Constitution Principle V.

### Port Resolution

Tests resolve service ports dynamically (Unit 1 of env-resilient-test-infra epic):

1. Environment variable `{SERVICE}_PORT` (highest priority)
2. Explicit port parameter
3. `SERVICE_DEFAULT_PORTS` dict in `testing/fixtures/services.py`
4. `ValueError` if no port found

E2E tests get canonical env vars from `testing/ci/test-e2e.sh`.

### Test Tiers

| Tier | Location | Infrastructure | Speed |
|------|----------|---------------|-------|
| Unit | `{package}/tests/unit/` | None (mocks) | <1s/test |
| Contract | `tests/contract/` (root) | None (schema validation) | <5s total |
| Integration | `{package}/tests/integration/` | Kind cluster | <30s/test |
| E2E | `tests/e2e/` | Kind cluster (full stack) | <5min/test |

### Test Execution

```bash
make test-unit          # Fast, no K8s
make test-integration   # Requires Kind cluster
make test-e2e           # Requires Kind + full stack (uses port-forwards)
make test               # All tiers
make check              # lint + typecheck + test
```

### Key Fixtures

| Fixture | Location | Purpose |
|---------|----------|---------|
| `IntegrationTestBase` | `testing/base_classes/integration_test_base.py` | Service health checks, unique namespaces |
| `ServiceEndpoint` | `testing/fixtures/services.py` | Port resolution, URL construction |
| `check_infrastructure()` | `testing/fixtures/services.py` | TCP health checks for service lists |
| `wait_for_condition()` | `testing/fixtures/services.py` | Polling utility (no `time.sleep()`) |

---

## Mock Allowances

Mocking is permitted ONLY for the dependencies listed below, with the stated rationale.
Any mock not listed here requires Constitution amendment or explicit user approval.

| Dependency | Where Mocked | Rationale | Live Alternative |
|------------|-------------|-----------|-----------------|
| Cognee Cloud REST API | Unit tests, contract tests | External SaaS, SSL issues, camelCase field quirks | Manual `make cognee-test` |
| Cognee SDK (`cogwit.memify`) | Unit tests | Metered API, SDK-only operation | Manual `make cognee-test` |
| Infisical Cloud API | Unit tests | SaaS rate limits | Self-hosted in Kind for integration |
| GitHub API (`gh` CLI) | Unit tests for PR logic | External service | Real `gh pr create` in sw-ship |
| Third-party plugin imports | Unit tests (`sys.modules` injection) | Optional dependencies not always installed | Integration tests with real packages |

### Explicitly Forbidden Mocks

These MUST NOT be mocked in any test tier (Constitution Principle V):

- Polaris catalog (use real Kind instance)
- MinIO/S3 storage (use real Kind instance)
- PostgreSQL (use real Kind instance)
- Dagster orchestration (use real Kind instance)
- OTel Collector / Jaeger (use real Kind instance)
- Marquez lineage (use real Kind instance)
- OCI Registry (use real Kind instance)
- dbt compilation (use real `dbtRunner`)

---

**Version**: 1.0.0 | **Created**: 2026-03-22
