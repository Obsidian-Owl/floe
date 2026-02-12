# Spec: Test Hardening Audit + E2E Brutalization

## Overview

Two work units:
1. **WU-1: Test Audit** — Comprehensive catalog of every gap, weak test, mock fallback, and config duplication
2. **WU-2: E2E Hardening** — Write brutal E2E tests using real Helm deployment path

Custom test infrastructure removal is tracked as **Epic 15: Test Infrastructure Modernization** (deferred).

---

## WU-1: Test Audit

### Acceptance Criteria

Each criterion is testable. The audit produces a machine-parseable markdown report.

#### AC-1.1: Mock Fallback Catalog
- [ ] Every `MagicMock()`, `Mock()`, `MockCatalog`, `MockTable`, `MockCatalogPlugin` usage across all test files is cataloged
- [ ] For each mock: file path, line number, what real service it replaces, whether the test COULD use a real service instead
- [ ] Report distinguishes: (a) legitimate unit test mocks, (b) integration/E2E tests that should use real services but don't

#### AC-1.2: Config Duplication Map
- [ ] Every hardcoded service endpoint (host, port, credential) in `testing/` is listed
- [ ] Each is cross-referenced with the canonical value in `values-test.yaml`
- [ ] Drift is flagged: Python says X, Helm says Y
- [ ] Report shows single-source-of-truth violations

#### AC-1.3: Assertion Strength Audit
- [ ] Every `assert X is not None` where X cannot be None is flagged (trivial assertion)
- [ ] Every `assert len(X) > 0` without content validation is flagged (TQR-002)
- [ ] Every `assert result.success is True` on a side-effect method without `assert_called*()` is flagged (Accomplishment Simulator)
- [ ] Report shows assertion strength distribution: strongest / strong / moderate / weak / forbidden

#### AC-1.4: Side-Effect Verification Audit
- [ ] Every method whose primary purpose is write/send/publish/deploy is identified
- [ ] For each: does the test verify the side effect occurred (mock.assert_called*) or only the return value?
- [ ] Report catalogs every "Return-Value-as-Proxy" violation
- [ ] Report catalogs every "Import-Satisfying Mock" (MagicMock without assert_called)

#### AC-1.5: Test Classification Audit
- [ ] Every test file is classified: unit / contract / integration / e2e
- [ ] Misclassified tests are flagged (e.g., `test_compilation.py` in `tests/e2e/` but doesn't need K8s)
- [ ] Tests in wrong directory per test organization rules are flagged
- [ ] Tests missing `@pytest.mark.requirement()` are listed

#### AC-1.6: E2E Coverage Gap Map
- [ ] Every user workflow that lacks E2E coverage is listed with severity
- [ ] Minimum gaps to catalog:
  - Full deployment workflow: compile → helm deploy → dagster materialize → iceberg validate
  - Observability round-trip: pipeline run → traces in Jaeger
  - Lineage round-trip: pipeline run → events in Marquez
  - Governance enforcement: policy violation → rejection
  - Multi-product isolation: concurrent products → no namespace bleed
  - Failure cascade: service failure → graceful degradation
  - Semantic query: Cube deployment → API query → metric resolution
  - Security boundary: NetworkPolicy → cross-product traffic blocked

#### AC-1.7: Plugin Integration Coverage
- [ ] For each of the 21 plugins: does it have integration tests against real services?
- [ ] Which plugins fall back to mocks in integration tests?
- [ ] Which plugins have NO integration tests at all?
- [ ] Report flags plugins where unit tests could hide real integration bugs

#### AC-1.8: Custom Test Infra Inventory
- [ ] Every file in `testing/` is listed with line count and purpose
- [ ] Files that duplicate Helm/K8s functionality are flagged
- [ ] Files that are unused or only used by meta-tests are flagged
- [ ] This inventory feeds the deferred Epic 15

---

## WU-2: E2E Hardening

### Acceptance Criteria

These are specs for NEW E2E tests. Each test must:
- Use the real Helm deployment path (values-test.yaml)
- Use real `manifest.yaml` + `floe.yaml` files from `demo/`
- Run against real K8s services (no mocks, no dual-mode networking)
- Fail loudly when infrastructure is missing (no pytest.skip)
- Have `@pytest.mark.requirement()` and `@pytest.mark.e2e` markers
- Have docstrings explaining WHAT and WHY

#### AC-2.1: Full Platform Deployment E2E
- [ ] Test: `helm install floe-platform → wait for pods → verify all services healthy`
- [ ] Validates: Dagster webserver responds at /server_info, Polaris responds at /q/health/ready, MinIO responds at /minio/health/ready, Marquez responds at /api/v1/namespaces, Jaeger responds at /api/services
- [ ] Asserts: All expected pods are Running, all services have endpoints
- [ ] Uses: `kubectl` commands against real cluster, NOT custom TCP health checks

#### AC-2.2: Compile-Deploy-Materialize-Validate E2E
- [ ] Test: `floe compile demo/customer-360/floe.yaml → deploy to Dagster → trigger materialization → validate Iceberg tables in Polaris`
- [ ] Validates: CompiledArtifacts contain all 3 demo products, Dagster code locations loaded, asset materialization succeeds, Iceberg tables exist with correct row counts and schemas
- [ ] This is THE critical user workflow test
- [ ] Must exercise the REAL 6-stage compilation pipeline feeding REAL charts
- [ ] **Design note**: Dagster code locations in Kind must reference code that's loadable inside the pod. The `floe-jobs` chart templates configure code location paths (typically `/app/demo/`). Test must verify that the code location ConfigMap/sidecar mechanism works — the compilation produces artifacts that Dagster's workspace can actually load.

#### AC-2.3: Observability Round-Trip E2E
- [ ] Test: Compile with OTel config → run pipeline → query Jaeger for traces
- [ ] Validates: Traces appear in Jaeger with correct service name, span hierarchy shows compilation stages, trace context propagates from compile to dbt run
- [ ] Must query real Jaeger API, not just assert OTel SDK was configured
- [ ] **Differentiation from existing `test_observability.py`**: Existing test validates OTel SDK configuration and individual span creation. This test validates the full round-trip: compilation produces traced artifacts → pipeline execution sends traces through OTel Collector → traces land in Jaeger and are queryable. The existing test checks "was OTel configured?"; this test checks "did traces actually flow through the full observability pipeline?"

#### AC-2.4: Lineage Round-Trip E2E
- [ ] Test: Run pipeline → query Marquez for lineage events
- [ ] Validates: OpenLineage events recorded in Marquez, job/dataset graph is correct, lineage namespace matches product name
- [ ] Must query real Marquez API (/api/v1/lineage)

#### AC-2.5: Governance Enforcement E2E
- [ ] Test: Configure strict enforcement → compile spec that violates governance policy → verify rejection
- [ ] Validates: Compilation fails with descriptive governance error, enforcement level respected (off/warn/strict), violation details propagated to CompiledArtifacts
- [ ] Also test: warn mode allows compilation but records violations
- [ ] **Differentiation from existing `test_governance.py`**: Existing test validates governance rules (RBAC, secrets, network policies, security scanning) at the policy level. This test validates the compilation pipeline's ENFORCE stage — when governance is configured in `manifest.yaml` with `enforcement_level: strict`, does `floe compile` actually reject a violating spec? The existing test checks "do governance rules work?"; this test checks "does the compilation pipeline integrate governance enforcement correctly?"

#### AC-2.6: Multi-Product Isolation E2E
- [ ] Test: Deploy all 3 demo products simultaneously → verify namespace isolation
- [ ] Validates: Each product compiles independently, Iceberg namespaces don't collide, Dagster code locations are separate, no cross-product data leakage in Polaris catalog
- [ ] Must run products concurrently, not sequentially

#### AC-2.7: Service Failure Resilience E2E
- [ ] Test: Start pipeline → kill a service pod (e.g., MinIO) → verify graceful error
- [ ] Validates: Pipeline fails with descriptive error (not silent), Dagster records failure with error metadata
- [ ] Must actually `kubectl delete pod`, not simulate failure
- [ ] NOTE: `persistence.enabled: false` in values-test.yaml — data does NOT survive pod restart. Test verifies error handling only, NOT retry-after-restore (retry requires persistent storage, tracked as separate concern)

#### ~~AC-2.8: Semantic Layer Query E2E~~ — DEFERRED
- **Reason**: No Cube Helm templates exist in `charts/floe-platform/templates/`. Cube is configured in values-test.yaml (`cube.enabled: true`) but no K8s resources are generated. Cannot write an E2E test against a service that doesn't deploy.
- **Tracked**: Epic 15 or separate Cube Helm epic must create templates first.
- **Gate**: This AC becomes unblocked when `charts/floe-platform/templates/cube-*.yaml` exists.

#### AC-2.9: Helm Upgrade E2E
- [ ] Test: Deploy v1 → modify values (e.g., resource limits, replica count) → `helm upgrade` → verify rolling update completes
- [ ] Validates: Pods roll to new revision, services become healthy after upgrade, no CrashLoopBackOff during rollout
- [ ] Tests the upgrade path, not just fresh install
- [ ] NOTE: `persistence.enabled: false` in values-test.yaml — data does NOT survive pod restart. This test validates the Helm upgrade mechanism (rolling update, service continuity), NOT data durability. Data durability requires persistent volumes (production concern, not Kind test concern).

#### AC-2.10: dbt Build Full Lifecycle E2E
- [ ] Test: For each demo product: `dbt deps → dbt seed → dbt run → dbt test → dbt docs generate`
- [ ] Validates: All dbt lifecycle commands succeed, docs catalog generated, test results parseable
- [ ] Must run dbt against real DuckDB + Polaris, not mocked backends

---

## Non-Functional Requirements

### NF-1: Test Execution
- All E2E tests must run via `make test-e2e`
- Total E2E suite completes in < 20 minutes on Kind cluster (budget: existing tests ~10min + new tests ~10min)
- Tests are idempotent (can run repeatedly without manual cleanup)

### NF-2: Traceability
- Every test has `@pytest.mark.requirement()` linking to this spec
- `python -m testing.traceability --all --threshold 100` passes

### NF-3: No New Custom Infra
- New E2E tests MUST NOT add new files to `testing/base_classes/`
- New E2E tests MUST NOT add new mock services to `testing/fixtures/`
- Service config comes from environment variables (set by port-forward scripts or K8s)

### NF-4: Documentation
- Audit report is a markdown file in `docs/audits/test-hardening-audit-2026-02.md`
- E2E test file docstrings explain the user workflow being tested

---

## Deferred: Epic 15 — Test Infrastructure Modernization

Track as a separate Epic in Linear:
- Remove `testing/base_classes/` (replace with thin env-var reader)
- Remove `testing/fixtures/catalog.py` MockCatalog (665 lines)
- Remove dual-mode networking from `testing/fixtures/services.py`
- Single source of truth: `values-test.yaml` → env vars → tests
- Remove `testing/tests/` meta-tests
- Target: < 500 lines total in `testing/` package
