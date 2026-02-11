# Plan: Test Hardening Audit + E2E Brutalization

## Architecture Decisions

### AD-1: Audit as Automated Script
The audit (WU-1) should be a **runnable Python script** that produces a markdown report,
not a one-time manual review. This makes it repeatable and can run in CI.

**Rationale**: Manual audits go stale. A script in `scripts/test-audit.py` can re-run
after every Epic to track progress.

### AD-2: E2E Tests Use Port-Forwards, Not Dual-Mode
New E2E tests (WU-2) will connect to services via port-forwards set up by
`make test-e2e`. They will NOT use the dual-mode `_get_effective_host()` from
`testing/fixtures/services.py`.

**Rationale**: The user explicitly said "no leaky abstractions". Port-forwards are
the standard way to access K8s services from host. The `make test-e2e` target
already manages this.

### AD-3: E2E Tests in tests/e2e/, Not Package-Level
All new E2E tests go in `tests/e2e/` (root level), not in individual packages.
E2E tests by definition cross package boundaries.

### AD-4: Audit Report Location
Audit report goes in `docs/audits/` — a new directory for quality artifacts.

### AD-5: No New Dependencies on testing/ Package
New E2E tests import from `testing.fixtures.polling` (wait_for_condition only)
and standard libraries. No new IntegrationTestBase inheritance.

**Note**: 8/11 existing E2E tests use IntegrationTestBase. New tests will NOT inherit
from it, creating two patterns temporarily. This is intentional — new tests model
the future direction (port-forward + env vars), and Epic 15 will migrate existing
tests to the same pattern.

### AD-6: Ephemeral Storage Acknowledged
`values-test.yaml` has `persistence.enabled: false` for MinIO and PostgreSQL.
Data does NOT survive pod restarts. Tests must not assume data durability.

**Implications**:
- AC-2.7 (service failure): Tests error handling only, not retry-after-restore
- AC-2.9 (helm upgrade): Tests rollout mechanism only, not data survival
- Data durability testing requires persistent volumes (production concern)

### AD-7: Cube E2E Deferred
No Cube Helm templates exist in `charts/floe-platform/templates/`. The `cube.enabled`
config in values-test.yaml has no corresponding K8s resources. AC-2.8 is deferred until
Cube templates are created.

### AD-8: Dagster Code Location Loading in Kind
For AC-2.2, the critical compile-deploy-materialize test must verify that Dagster can
load code locations from CompiledArtifacts. In Kind, this works via the `floe-jobs` chart
which creates ConfigMaps and Jobs that reference demo product code. The test must verify
the entire chain: `compile → artifacts → chart values → Dagster workspace → code location loaded`.

---

## Work Unit Decomposition

### WU-1: Test Audit (1-2 sessions)

**Tasks:**

| # | Task | Output |
|---|------|--------|
| T01 | Write audit script: mock fallback scanner | Script finds all Mock/MagicMock usage, classifies as legitimate vs leaky |
| T02 | Write audit script: config duplication detector | Script cross-refs Python hardcoded values with values-test.yaml |
| T03 | Write audit script: assertion strength analyzer | Script classifies every assert by strength hierarchy |
| T04 | Write audit script: side-effect verification checker | Script finds methods that write/send/publish and checks for assert_called |
| T05 | Write audit script: test classification validator | Script checks file location vs markers vs imports |
| T06 | Write audit script: E2E coverage gap mapper | Script maps user workflows to existing test coverage |
| T07 | Write audit script: plugin integration coverage | Script checks each plugin for real-service integration tests |
| T08 | Write audit script: custom infra inventory | Script catalogs testing/ package with line counts and classifications |
| T09 | Run full audit, generate report | Execute all scripts, produce docs/audits/test-hardening-audit-2026-02.md |
| T10 | Create Epic 15 in Linear | Track test infrastructure modernization as future work |

### WU-2: E2E Hardening (2-3 sessions)

**Tasks:**

| # | Task | Output | Depends On |
|---|------|--------|------------|
| T11 | Write test_platform_deployment_e2e.py | AC-2.1: Full platform deployment verification | WU-1 (to know what's missing) |
| T12 | Write test_compile_deploy_materialize_e2e.py | AC-2.2: The critical user workflow | T11 |
| T13 | Write test_observability_roundtrip_e2e.py | AC-2.3: OTel traces land in Jaeger | T11 |
| T14 | Write test_lineage_roundtrip_e2e.py | AC-2.4: OpenLineage events in Marquez | T11 |
| T15 | Write test_governance_enforcement_e2e.py | AC-2.5: Policy violation → rejection | T12 |
| T16 | Write test_multi_product_isolation_e2e.py | AC-2.6: Concurrent products, no bleed | T12 |
| T17 | Write test_service_failure_resilience_e2e.py | AC-2.7: Kill pod → graceful error (no retry) | T12 |
| ~~T18~~ | ~~Write test_semantic_query_e2e.py~~ | ~~AC-2.8: DEFERRED — no Cube templates~~ | — |
| T19 | Write test_helm_upgrade_e2e.py | AC-2.9: Rolling upgrade + service continuity | T11 |
| T20 | Write test_dbt_lifecycle_e2e.py | AC-2.10: Full dbt lifecycle | T11 |
| T21 | Reclassify test_compilation.py | Move compilation-only tests to contract tier | T09 |
| T22 | Update conftest.py for new E2E tests | Fixtures for port-forward-based service access | T11 |

---

## Execution Order

```
Session 1: T01-T09 (Audit scripts + report)
Session 2: T10-T11, T22 (Linear epic + platform deployment test + conftest)
Session 3: T12-T14 (Core workflow + observability + lineage)
Session 4: T15-T17 (Governance + isolation + failure)
Session 5: T19-T21 (Upgrade + dbt lifecycle + reclassification)
```

**Note**: T18 (Cube semantic query) deferred — no Cube Helm templates exist.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Audit finds >100 issues | Prioritize by severity (critical/major/minor), fix critical only in this epic |
| E2E tests flaky on Kind | Use generous timeouts, polling with backoff, unique namespaces |
| Port-forwards unstable | `make test-e2e` manages port-forward lifecycle; tests wait for services |
| Cube templates missing | AC-2.8 deferred entirely; tracked for future Cube Helm epic |
| Ephemeral storage in Kind | Tests verify error handling and rollout, NOT data durability |
| Audit script false positives | Manual review pass on audit output before publishing |

---

## Success Criteria

1. Audit report exists at `docs/audits/test-hardening-audit-2026-02.md` with all 8 AC-1.x sections
2. At least 7 new E2E tests pass against Kind cluster (9 active ACs minus 2 for margin)
3. Every new E2E test uses real services (zero mocks)
4. Epic 15 created in Linear with inventory from audit
5. `make test-e2e` runs all E2E tests (old + new) in < 20 minutes
