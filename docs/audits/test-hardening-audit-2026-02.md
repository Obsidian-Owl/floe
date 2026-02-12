# Test Hardening Audit Report — February 2026

**Generated**: 2026-02-12
**Spec**: `.specwright/work/test-hardening-audit/spec.md`
**Status**: WU-1 Complete (Audit), WU-2 Pending (E2E Hardening)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total test files | 547 |
| Total assertions | 20,330 |
| Mock instances | 3,500+ |
| Hardcoded endpoint files | 70+ |
| Plugins without integration tests | 8 of 21 |
| Custom test infra lines | 12,861 |
| Unused fixture lines | 1,669 |

**Severity Distribution:**
- CRITICAL: 5 findings
- MAJOR: 8 findings
- MINOR: 6 findings

---

## AC-1.1: Mock Fallback Catalog

### Summary

| Category | Files | Instances | Status |
|----------|-------|-----------|--------|
| Unit tests | 148 | 3,148 | LEGITIMATE |
| Integration tests | 7 | 34 | REVIEW NEEDED |
| Contract tests | 3 | 4 | LEGITIMATE |
| E2E tests | 0 | 0 | CORRECT |
| Conftest fixtures | 7 | ~100 | LEGITIMATE |

**Total**: 3,500+ mock instances across 165 files.

### Special Mock Implementations

| Mock Class | File | Lines | Usages | Replaces |
|-----------|------|-------|--------|----------|
| MockCatalog | `testing/fixtures/catalog.py` | 250 | 178 | PyIceberg Catalog (Polaris) |
| MockCatalogPlugin | `testing/fixtures/catalog.py` | 100 | 149 | CatalogPlugin ABC |
| MockTable | `testing/fixtures/catalog.py` | 100 | 8 | Iceberg Table |
| MockTableIO | `testing/fixtures/catalog.py` | 65 | 8 | Table I/O operations |

Total custom mock: **665 lines** in `testing/fixtures/catalog.py`.

### Integration Tests Using Mocks (CRITICAL)

These are in `tests/integration/` but use mocks where real services should be used:

| File | Mocks | Should Use |
|------|-------|-----------|
| `floe-core/tests/integration/oci/test_authorization_integration.py` | 12 MagicMock | Real OCI registry |
| `floe-core/tests/integration/test_otel_export.py` | 14 MagicMock | Real OTel Collector |
| `floe-core/tests/integration/oci/test_signing_e2e.py` | 2 MagicMock | Real signing service |
| `floe-core/tests/integration/oci/test_verification_e2e.py` | 2 MagicMock | Real registry |
| `floe-core/tests/integration/oci/test_attestation_e2e.py` | 2 MagicMock | Real attestation |
| `floe-dbt-fusion/tests/integration/test_discovery.py` | 1 MagicMock | Real dbt project |
| `floe-core/tests/integration/enforcement/test_pipeline_enforcement.py` | 1 MagicMock | Real pipeline |

### Top Mock-Heavy Unit Tests (Legitimate)

| File | Count | Purpose |
|------|-------|---------|
| `floe-core/tests/unit/cli/test_artifact_verify.py` | 82 | OCI registry isolation |
| `floe-core/tests/unit/oci/test_client.py` | 66 | HTTP response mocking |
| `floe-core/tests/unit/cli/test_artifact_inspect.py` | 60 | CLI command isolation |
| `floe-core/tests/unit/cli/network/test_audit_command.py` | 59 | K8s API isolation |

---

## AC-1.2: Config Duplication Map

### Credential Drift (CRITICAL)

| Config Key | `values-test.yaml` | `testing/fixtures/` | Status |
|-----------|-------------------|---------------------|--------|
| Polaris credential | `demo-admin:demo-secret` | `root:secret` (polaris.py:46) | **DRIFT** |
| Polaris warehouse | `floe-e2e` | `test_warehouse` (polaris.py:43) | **DRIFT** |
| MinIO secret key | `minioadmin123` | `minioadmin` (minio.py:49) | **DRIFT** |
| PostgreSQL password | `floe-test-password-1234` | `floe_test_password` (postgres.py:55) | **DRIFT** |
| PostgreSQL database | `floe` | `floe_test` (postgres.py:57) | **DRIFT** |
| Catalog credential | N/A (uses Polaris) | `root:secret` (catalog.py:58) | **DRIFT** |

**5 of 6 credential pairs are DRIFTED** between Helm values and Python fixture defaults.

### Hostname Duplication

| Service | Occurrences | Files |
|---------|------------|-------|
| `polaris:8181` | 19+ | testing/fixtures/polaris.py, services.py, conftest.py, test_runner.yaml |
| `minio:9000` | 12+ | testing/fixtures/minio.py, conftest.py, test_runner.yaml |
| `localhost:3000` (Dagster) | 8+ | tests/e2e/conftest.py, test_platform_bootstrap.py |
| `localhost:8181` (Polaris) | 10+ | tests/e2e/conftest.py, test_platform_bootstrap.py |
| `localhost:9000` (MinIO) | 6+ | tests/e2e/conftest.py, test_platform_bootstrap.py |
| `localhost:16686` (Jaeger) | 10+ | tests/e2e/conftest.py, test_platform_bootstrap.py, test_observability.py |
| `localhost:5000` (Marquez) | 8+ | tests/e2e/conftest.py, test_platform_bootstrap.py |
| `floe-test` (namespace) | 100+ | Everywhere |

### Single Source of Truth Violations

**Total files with hardcoded values**: 70+

The canonical source is `charts/floe-platform/values-test.yaml` (310 lines). But service config is duplicated in:
1. `testing/fixtures/*.py` (env var fallbacks with WRONG defaults)
2. `testing/k8s/jobs/test-runner.yaml` (hardcoded env vars)
3. `tests/e2e/conftest.py` (hardcoded credentials)
4. `testing/k8s/setup-cluster.sh` (hardcoded names)
5. `testing/ci/test-e2e.sh` (hardcoded ports)

---

## AC-1.3: Assertion Strength Audit

### Distribution

| Strength | Pattern | Count | % |
|----------|---------|-------|---|
| **Strongest** | `assert X == exact_value` | ~15,000 | 73.8% |
| **Strong** | `assert set(X) == {...}` | 816 | 4.0% |
| **Moderate** | `assert len(X) == N` | 4,624 | 22.7% |
| **Moderate** | `assert isinstance(X, Y)` | 1,001 | 4.9% |
| **Weak** | `assert len(X) > 0` | 265 | 1.3% |
| **Forbidden** | `assert X is not None` (trivial) | 980 | 4.8% |

### Weak Assertions (MAJOR)

265 instances of `assert len(X) > 0` without subsequent content validation:

| File | Line | Context |
|------|------|---------|
| `tests/e2e/test_observability.py` | 98 | `assert len(traces) > 0` — no trace content check |
| `tests/e2e/test_demo_mode.py` | 163 | `assert len(version) > 0` — no version format check |
| `tests/e2e/test_data_pipeline.py` | 922-929 | Multiple model count checks — no model name validation |
| `floe-iceberg/tests/unit/test_models.py` | 51 | `assert len(IDENTIFIER_PATTERN) > 0` — trivially true |

### Forbidden Assertions (MAJOR)

980 instances of `assert X is not None` across 235 files. Estimated 30-40% are trivially true (checking freshly-created objects):

| File | Line | Status |
|------|------|--------|
| `floe-secrets-k8s/tests/unit/test_config.py` | - | `assert config.kubeconfig_path is not None` — just assigned |
| `floe-secrets-k8s/tests/unit/test_env_injection.py` | 75 | `assert result is not None` — just returned |
| `floe-identity-keycloak/tests/integration/test_discovery.py` | - | `assert plugin is not None` — just instantiated |
| `floe-iceberg/tests/unit/test_manager.py` | 142 | `assert manager._log is not None` — always exists |

---

## AC-1.4: Side-Effect Verification Audit

### Summary

| Metric | Count |
|--------|-------|
| Side-effect `assert result.success` patterns | 123 |
| Total `.assert_called*()` patterns | 437 |
| Behavioral verification ratio | 3.5 per test file (low) |

### Return-Value-as-Proxy Violations (CRITICAL)

Files where side-effect methods are tested ONLY by return value:

| File | Success Assertions | Behavioral Assertions | Status |
|------|-------------------|----------------------|--------|
| `floe-core/tests/integration/test_rbac_generation.py` | 10 | 0 | **VIOLATION** |
| `floe-dbt-core/tests/unit/test_linting.py` | 7 | unclear | REVIEW |
| `floe-dbt-fusion/tests/unit/test_linting.py` | 5 | 0 | **VIOLATION** |
| `floe-orchestrator-dagster/tests/integration/test_iceberg_io_manager.py` | 8 | via real services | OK (real integration) |

### Positive Examples

Files with proper side-effect verification:
- `floe-ingestion-dlt/tests/unit/test_dlt_sink_connector.py:311` — `mock_dlt.pipeline.assert_called_once()`
- `floe-alert-webhook/tests/unit/test_plugin.py:107` — `mock_post.assert_awaited_once()`

---

## AC-1.5: Test Classification Audit

### Distribution

| Tier | Root-Level | Package-Level | Total |
|------|-----------|--------------|-------|
| Unit | 211 | ~200+ | 411+ |
| Contract | 53 | 0 | 53 |
| Integration | 57 | 42+ | 99+ |
| E2E | 12 | 0 | 12 |

### Misclassified Tests (MAJOR)

#### Discovery tests in integration/ (should be unit/contract)
15+ plugin `test_discovery.py` files in `tests/integration/` only test entry point loading via `importlib.metadata` — no real services needed:

- `plugins/floe-secrets-k8s/tests/integration/test_discovery.py`
- `plugins/floe-catalog-polaris/tests/integration/test_discovery.py`
- `plugins/floe-identity-keycloak/tests/integration/test_discovery.py`
- (13+ more)

#### E2E test that doesn't need K8s
- `tests/e2e/test_compilation.py` (829 lines) — Tests the compilation pipeline. Does NOT require K8s services. Should be `tests/contract/`.

#### Multi-package tests in package directories
32 test files import from multiple packages but live in single-package test directories. These are likely plugin compliance tests and should be in `tests/contract/`.

### Requirement Marker Coverage

- Tests WITH `@pytest.mark.requirement()`: 527 files (97.2%)
- Tests WITHOUT markers: 15 files (2.8%)

Missing markers in:
- `plugins/floe-compute-duckdb/tests/unit/test_config.py`
- `tests/contract/test_polaris_plugin_compliance.py`
- `tests/e2e/test_demo_flow.py` (deprecated, empty)
- `packages/floe-core/tests/unit/telemetry/*.py` (2 files)
- `packages/floe-core/tests/unit/oci/*.py` (6 files)
- `packages/floe-core/tests/unit/cli/test_artifact_sbom.py`
- `packages/floe-core/tests/integration/test_lineage_integration.py`

### pytest.skip() Violations (CRITICAL)

2 instances of `pytest.skip()` instead of `pytest.fail()`:
- `tests/integration/helm/test_platform_install.py:206` — skips on install failure
- `tests/integration/helm/test_platform_install.py:286` — skips on install failure

---

## AC-1.6: E2E Coverage Gap Map

### Existing E2E Coverage

| Test File | What It Tests | K8s Required |
|-----------|--------------|-------------|
| `test_compilation.py` | 6-stage compilation pipeline | NO (misclassified) |
| `test_data_pipeline.py` | dbt seed/run/test + Iceberg validation | YES |
| `test_helm_workflow.py` | Helm chart rendering + installation | YES |
| `test_observability.py` | OTel SDK config + Jaeger traces | YES |
| `test_platform_bootstrap.py` | Platform initialization + health | YES |
| `test_plugin_system.py` | Plugin discovery + lifecycle | YES |
| `test_governance.py` | Governance rules enforcement | YES |
| `test_promotion.py` | Artifact promotion workflow | YES |
| `test_schema_evolution.py` | Iceberg schema evolution | YES |
| `test_demo_mode.py` | Demo mode verification | YES |
| `test_demo_flow.py` | DEPRECATED (empty) | - |

### Missing Workflows (sorted by severity)

| Gap | Severity | Description |
|-----|----------|-------------|
| **Full user workflow** | CRITICAL | `floe compile` -> `helm deploy` -> `dagster materialize` -> `iceberg validate` — no test covers this end-to-end chain |
| **Multi-product isolation** | CRITICAL | No test runs all 3 demo products concurrently to verify namespace isolation |
| **Service failure handling** | HIGH | No test kills a pod mid-pipeline to verify error handling |
| **Observability round-trip** | HIGH | Existing test checks OTel SDK config; no test verifies traces flow through Collector to Jaeger |
| **Lineage round-trip** | HIGH | No test verifies OpenLineage events land in Marquez after pipeline run |
| **Governance in compilation** | MEDIUM | Existing test checks governance rules; no test verifies the ENFORCE compilation stage |
| **Helm upgrade path** | MEDIUM | No test validates `helm upgrade` rollout + service continuity |
| **dbt full lifecycle** | MEDIUM | `test_data_pipeline.py` covers seed/run/test but not `dbt deps` + `dbt docs generate` |
| **Cube semantic query** | DEFERRED | No Cube Helm templates exist — cannot test |
| **Security boundary** | LOW | NetworkPolicy tests exist but no cross-namespace traffic blocking E2E |

---

## AC-1.7: Plugin Integration Coverage

### Coverage Matrix

| Plugin | Unit | Integration | Real Services | Mock Fallbacks | Status |
|--------|------|-------------|--------------|----------------|--------|
| floe-catalog-polaris | 9 | 7 | YES | No | GOOD |
| floe-compute-duckdb | 5 | 3 | YES | No | GOOD |
| floe-dbt-core | 4 | 2 | YES | No | GOOD |
| floe-dbt-fusion | 5 | 2 | MIXED | 1 file mocks binary detection | ACCEPTABLE |
| floe-identity-keycloak | 8 | 2 | YES | No | GOOD |
| floe-ingestion-dlt | 7 | 3 | STUBBED | pytest.fail() stubs | **GAP** |
| floe-network-security-k8s | 10 | 4 | YES | No | GOOD |
| floe-orchestrator-dagster | 19 | 5 | YES | No | GOOD |
| floe-rbac-k8s | 2 | 4 | YES | No | GOOD |
| floe-secrets-infisical | 5 | 2 | YES | No | GOOD |
| floe-secrets-k8s | 6 | 2 | YES | No | GOOD |
| floe-semantic-cube | 5 | 2 | NO | `@patch` on httpx | **MOCK ONLY** |
| floe-telemetry-jaeger | 1 | 1 | YES | No | GOOD |
| floe-alert-alertmanager | 2 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-alert-email | 2 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-alert-slack | 2 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-alert-webhook | 2 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-lineage-marquez | 3 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-quality-dbt | 3 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-quality-gx | 4 | 0 | N/A | N/A | **NO INTEGRATION** |
| floe-telemetry-console | 1 | 0 | N/A | N/A | **NO INTEGRATION** |

### Summary

- **8 plugins** have NO integration tests at all (alert-*, lineage-marquez, quality-*, telemetry-console)
- **1 plugin** (floe-semantic-cube) has integration tests that only use mocks — anti-pattern
- **1 plugin** (floe-ingestion-dlt) has stubbed integration tests (pytest.fail placeholders)
- **11 plugins** have proper real-service integration tests

---

## AC-1.8: Custom Test Infrastructure Inventory

### Summary

| Category | Files | Lines | Notes |
|----------|-------|-------|-------|
| Test framework (core) | 16 | ~2,500 | IntegrationTestBase, polling, services, traceability |
| Service fixtures | 15 | ~4,500 | Polaris, PostgreSQL, MinIO, DuckDB, Dagster, etc. |
| Plugin compliance bases | 9 | ~2,700 | ABC validation for 8 plugin types |
| Meta-tests | 14 | ~3,700 | Tests for the testing infrastructure |
| **Total** | **51** | **12,861** | |

### Unused Fixtures (MAJOR)

These fixtures are exported from `testing/fixtures/__init__.py` but never imported outside `testing/`:

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `governance.py` | 749 | Governance test factories | **UNUSED** |
| `telemetry.py` | 358 | Jaeger/OTLP configs | **UNUSED** |
| `data.py` | 239 | Test data generators | **UNUSED** |
| `semantic.py` | 218 | Cube semantic configs | **UNUSED** |
| `lineage.py` | 105 | OpenLineage/Marquez fixtures | **UNUSED** |
| **Total** | **1,669** | | Dead code |

### Files Duplicating Helm/K8s Functionality

| File | Lines | Duplicates |
|------|-------|-----------|
| `fixtures/services.py` | 274 | K8s liveness probes (raw TCP sockets vs kubectl) |
| `fixtures/polling.py` | 236 | `kubectl wait` mechanism |
| `base_classes/integration_test_base.py` | 228 | K8s readiness checks |
| `fixtures/catalog.py` | 664 | Real Polaris catalog (full in-memory mock) |

### Meta-Tests (Testing the Testing Infrastructure)

14 test files totaling ~3,700 lines that test the testing package itself:

- `test_base_classes.py` (307 lines) — tests IntegrationTestBase
- `test_catalog_fixtures.py` (376 lines) — tests MockCatalog
- `test_dagster_fixture.py` (199 lines) — tests DagsterConfig
- `test_duckdb_fixture.py` (331 lines) — tests DuckDB connection
- (10 more files)

These become unnecessary when the custom test infra is removed (Epic 15).

---

## Findings Summary

### CRITICAL (5)

| ID | Finding | Location |
|----|---------|----------|
| C-01 | 5/6 credential pairs DRIFTED between values-test.yaml and Python fixtures | AC-1.2 |
| C-02 | 7 integration tests use mocks where real services should be used | AC-1.1 |
| C-03 | `test_rbac_generation.py` has 10 success assertions, 0 behavioral verifications | AC-1.4 |
| C-04 | 2 tests use `pytest.skip()` instead of `pytest.fail()` | AC-1.5 |
| C-05 | No E2E test covers the full user workflow (compile -> deploy -> materialize -> validate) | AC-1.6 |

### MAJOR (8)

| ID | Finding | Location |
|----|---------|----------|
| M-01 | 265 `assert len(X) > 0` without content validation | AC-1.3 |
| M-02 | 980 `assert X is not None` (30-40% trivially true) | AC-1.3 |
| M-03 | 15+ discovery tests misclassified as integration | AC-1.5 |
| M-04 | `test_compilation.py` misclassified as E2E (doesn't need K8s) | AC-1.5 |
| M-05 | 8 plugins have NO integration tests | AC-1.7 |
| M-06 | `floe-semantic-cube` integration tests use mocks only | AC-1.7 |
| M-07 | 1,669 lines of unused fixture code | AC-1.8 |
| M-08 | 70+ files with hardcoded service endpoints | AC-1.2 |

### MINOR (6)

| ID | Finding | Location |
|----|---------|----------|
| m-01 | 15 test files missing `@pytest.mark.requirement()` | AC-1.5 |
| m-02 | 32 multi-package tests in single-package directories | AC-1.5 |
| m-03 | `test_demo_flow.py` deprecated and empty | AC-1.5 |
| m-04 | `floe-ingestion-dlt` integration tests are stubbed (pytest.fail placeholders) | AC-1.7 |
| m-05 | 3,700 lines of meta-tests for testing infrastructure | AC-1.8 |
| m-06 | `floe-dbt-fusion` mocks binary detection in integration test | AC-1.7 |

---

## Deferred: Epic 15 — Test Infrastructure Modernization

Based on this audit, Epic 15 should include:

1. **Remove `testing/fixtures/catalog.py`** (665 lines) — Replace MockCatalog with real Polaris
2. **Remove dual-mode networking** from `testing/fixtures/services.py` — Use port-forwards only
3. **Remove unused fixtures** (1,669 lines) — governance, semantic, lineage, telemetry, data
4. **Remove meta-tests** (~3,700 lines) — No longer needed when custom infra removed
5. **Remove plugin base classes** (~2,700 lines) — Replace with thin pytest fixtures
6. **Fix credential drift** — Single source from `values-test.yaml` via env vars
7. **Reclassify 15+ discovery tests** — Move from integration/ to unit/ or contract/
8. **Move `test_compilation.py`** from tests/e2e/ to tests/contract/
9. **Target**: < 500 lines total in `testing/` package (currently 12,861)
