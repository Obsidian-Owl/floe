# Specification Analysis Report: Epic 9B - Helm Charts and Kubernetes Deployment

**Analysis Date**: 2026-02-01
**Input**: spec.md, plan.md, tasks.md, existing K8s manifests, E2E tests
**Focus**: Integration points analysis, testing coverage, E2E validation assessment

---

## 1. How the Existing Integration Points Work

### Current Testing Infrastructure Architecture

The existing `testing/k8s/services/` manifests provide a **test-only infrastructure layer** for integration testing. Here's how they work together:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Kind Cluster (floe-test namespace)              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐      ┌──────────────────┐     ┌────────────────┐  │
│  │   PostgreSQL     │◄─────│    Dagster       │     │    Polaris     │  │
│  │  (init-db.sh)    │      │ (webserver+daemon)│     │  (in-memory)   │  │
│  │                  │      │                  │     │                │  │
│  │ Creates DBs:     │      │ Uses K8sRunLauncher  │◄─────►│ S3 endpoint:   │  │
│  │ - dagster        │      │ for job execution │     │   minio:9000   │  │
│  │ - polaris        │      └──────────────────┘     └────────────────┘  │
│  └──────────────────┘                                        ▲          │
│           ▲                                                  │          │
│           │                ┌──────────────────┐              │          │
│           │                │      MinIO       │──────────────┘          │
│           │                │   (S3 storage)   │                         │
│           └────────────────│  + IAM setup     │                         │
│                            │  + STS for Polaris                         │
│                            └──────────────────┘                         │
│                                                                          │
│  ┌──────────────────┐      ┌──────────────────┐     ┌────────────────┐  │
│  │     Marquez      │◄─────│  marquez-postgres│     │     Jaeger     │  │
│  │   (lineage)      │      │    (separate)    │     │   (tracing)    │  │
│  └──────────────────┘      └──────────────────┘     └────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Integration Patterns Discovered

| Component | Current Pattern | Production Gap |
|-----------|-----------------|----------------|
| **PostgreSQL** | Single Deployment with init script | No HA, no operator (CloudNativePG) |
| **Dagster** | Hardcoded ConfigMap + Secret | No workspace.yaml generation from artifacts |
| **Polaris** | In-memory metastore | Not `relational-jdbc` for persistence |
| **MinIO** | Setup Jobs create buckets/IAM | Good pattern, needs externalization |
| **Marquez** | Separate PostgreSQL | Good isolation pattern |

### Service Dependency Flow

```
postgres ──► dagster-webserver ──► dagster-daemon
    │                │
    ▼                ▼
polaris ◄──────── minio
    │                │
    └────────────────┼──► K8s Jobs (dbt runs)
                     │
               marquez (optional)
```

### Current Strengths

1. **Init container pattern**: Dagster uses `wait-for-postgres` init containers - reliable dependency ordering
2. **Init job pattern**: MinIO uses setup Jobs for bucket/IAM creation - idempotent initialization
3. **Probe configuration**: All services have readiness/liveness probes with sensible defaults
4. **RBAC setup**: Dagster has ServiceAccount + Role + RoleBinding for K8sRunLauncher
5. **Resource limits**: All containers have resource requests/limits defined

### Current Weaknesses

1. **Hardcoded credentials**: All Secrets contain test-only passwords in plaintext (acceptable for testing, but templates not externalized)
2. **No HPA/PDB**: No autoscaling or disruption budgets
3. **No NetworkPolicy**: No pod isolation
4. **No securityContext**: Pods may run as root
5. **Static configuration**: No template parameterization (Helm values)

---

## 2. E2E Testing Current State

### What Exists

```python
# tests/e2e/test_demo_flow.py
class TestDemoFlow(IntegrationTestBase):
    required_services = [("dagster", 3000), ("polaris", 8181), ("localstack", 4566)]

    def test_compile_deploy_run_validates(self, e2e_namespace: str):
        # TODO: Epic 13 - Implement E2E pipeline tests
        pytest.fail("E2E test not yet implemented.")
```

**Current State**: E2E tests are **stubs that fail** by design (following "tests FAIL, never skip" principle). They exist as placeholders for Epic 13.

### E2E Requirements Coverage

| Requirement | E2E Test | Status |
|-------------|----------|--------|
| E2E-001 | `test_compile_deploy_run_validates` | **STUB** |
| E2E-002 | `test_platform_services_healthy` | **STUB** |
| E2E-003 | `test_table_registration_and_discovery` | **STUB** |

---

## 3. Gap Analysis: Epic 9B Testing Coverage

### Testing Tasks in tasks.md

| Phase | Test Count | Test Types |
|-------|------------|------------|
| US1 (Platform) | 4 | Lint, Template, Install |
| US2 (Jobs) | 3 | Lint, Template, Install |
| US3 (Generator) | 3 | Unit merger, Unit generator, Integration command |
| US4 (Mapping) | 2 | Unit schema, Integration multi-namespace |
| US5 (Schema) | 1 | Schema validation |
| US7 (Testing) | 7 | Helm test pods, CI targets |
| **Total** | 20 | Various |

### Testing Coverage Assessment

#### Strengths

1. **Lint tests** (T018, T042): Validates chart syntax before deployment
2. **Template tests** (T019, T043): Validates rendered YAML before deployment
3. **Install tests** (T020, T044): Validates actual Kind cluster deployment
4. **Unit tests for generator** (T055-T056): Tests value generation logic
5. **Helm test pods** (T086-T087): In-chart health checks (`helm test`)
6. **CI integration** (T092): Automated chart validation

#### Gaps Identified

| Gap ID | Description | Severity | Recommendation |
|--------|-------------|----------|----------------|
| **GAP-001** | No E2E test for full deploy → run cycle | HIGH | Add task to extend E2E-001 |
| **GAP-002** | No E2E test for Helm chart → dbt Job execution | HIGH | Add integration test |
| **GAP-003** | No test for upgrade path (rolling update) | MEDIUM | Add T115 for upgrade test |
| **GAP-004** | No test for HPA scaling behavior | LOW | Add after US9 complete |
| **GAP-005** | No test for NetworkPolicy enforcement | MEDIUM | Add integration test |
| **GAP-006** | No test for External Secrets integration | MEDIUM | Add mock ESO test |
| **GAP-007** | Security scan (kubesec) only mentioned, no test verification | MEDIUM | Add kubesec assertion in T103 |

### Critical Testing Gap: E2E Pipeline Validation

The **target state vision** requires:

> "Deploy a production-grade platform and data product JUST by configuring the platform manifest and data product (dbt model + manifest). Every feature built to date needs to be well integrated and validated."

**Current tasks.md does NOT fully validate this vision** because:

1. **T111** ("Run full integration test suite in Kind cluster") is vague - doesn't specify which tests
2. **T112** ("Validate quickstart.md scenarios work end-to-end") is manual - should be automated
3. **No task connects Epic 9B (Helm) → Epic 13 (E2E) → deployment validation**

---

## 4. Recommended Additions to tasks.md

### New Tasks for E2E Validation

```markdown
## Phase 12a: E2E Integration (Add after Phase 12)

**Purpose**: Validate Helm charts enable full platform vision

- [ ] T115 [E2E] Create upgrade test in `tests/integration/helm/test_platform_upgrade.py` (SC-008)
- [ ] T116 [E2E] Create E2E test: deploy platform → register code location → trigger job in `tests/e2e/test_helm_workflow.py`
- [ ] T117 [E2E] Validate dbt Job completes successfully after Helm deployment
- [ ] T118 [E2E] Validate OpenLineage events emitted to Marquez after Job execution
- [ ] T119 [E2E] Validate OTel traces appear in collector after Job execution
- [ ] T120 [E2E] Create NetworkPolicy enforcement test (pod-to-pod isolation)
- [ ] T121 [E2E] Create automated quickstart validation script (`scripts/validate-quickstart.sh`)
```

### Testing Constitution Compliance

Per **Principle V: K8s-Native Testing**:

| Requirement | Current Coverage | Compliant? |
|-------------|------------------|------------|
| Tests run in Kind cluster | T020, T044, T111 | YES |
| Tests FAIL (never skip) | All integration tests inherit from `IntegrationTestBase` | YES |
| `@pytest.mark.requirement()` on all | Templates shown, needs verification | CHECK |
| No `time.sleep()` | Not verified in tasks | CHECK |

---

## 5. Integration Point Verification Matrix

This matrix shows whether Epic 9B tasks validate each integration point:

| Integration Point | Task Coverage | Validated By |
|-------------------|---------------|--------------|
| Dagster → PostgreSQL | T021, T029 | T020 (install test) |
| Polaris → MinIO (S3) | T024-T026, T032 | T020 (install test) |
| OTel Collector → Apps | T027-T028 | **GAP** - no telemetry test |
| Marquez → PostgreSQL | T109 (optional) | **GAP** - no lineage test |
| Dagster → K8s Jobs | T048-T049 | T044 (install test) |
| Generator → Artifacts | T058-T061 | T057 (integration test) |
| Schema → Values | T077-T079 | T076 (validation test) |

---

## 6. Summary: Is Testing Adequate?

### Overall Assessment: **GOOD with GAPS**

**Strengths:**
- Comprehensive chart testing (lint, template, install)
- Clear test-to-requirement mapping via requirement markers
- Kind cluster integration testing follows constitution
- User story isolation enables independent validation

**Gaps Requiring Action:**
1. **E2E workflow validation** (deploy → run → validate output) - not automated
2. **Upgrade testing** (SC-008) - mentioned but no explicit test task
3. **Observability validation** (OTel/OpenLineage) - no tests verify telemetry flows
4. **Security enforcement tests** - kubesec is CI-only, no functional security tests

### Recommended Priority

| Priority | Gap | Action |
|----------|-----|--------|
| P0 | GAP-001 (E2E deploy-run) | Add T116-T117 before MVP |
| P0 | GAP-002 (dbt Job execution) | Add T117 before MVP |
| P1 | GAP-003 (upgrade path) | Add T115 before Beta |
| P1 | GAP-005 (NetworkPolicy) | Add T120 before GA |
| P2 | GAP-004, GAP-006 | Add after GA |

---

## 7. Conclusion

The Epic 9B task list provides **solid foundational testing** for Helm charts but lacks **E2E validation of the complete vision**. The existing `testing/k8s/services/` manifests are well-structured and provide good patterns to follow, but they are:

1. Test-only (hardcoded values)
2. Not parameterized (not Helm templates)
3. Missing production features (HPA, PDB, NetworkPolicy, security contexts)

Epic 9B addresses all of these gaps in the chart implementation (US1-US9). However, **the testing does not fully validate that the platform vision works end-to-end**. Specifically:

- Can a user deploy the platform with a single `helm install`? → **Tested (T020)**
- Can a user run a dbt job after deployment? → **NOT automatically tested**
- Does telemetry flow through OTel Collector? → **NOT tested**
- Does lineage appear in Marquez? → **NOT tested**

**Recommendation**: Add T115-T121 to Phase 12a before marking Epic 9B complete.
