# Specwright Backlog

## Open

### BL-001 [debt] Helm upgrade cascade — bootstrap job + PostgreSQL timeout
Added: 2026-03-15 | Source: sw-learn | Work: fix-dbt-iceberg-pipeline
Updated: 2026-03-15 | Validated against E2E run (173 passed, 21 failed, 5 errors)
Priority: P1 — causes 8 test failures in Helm upgrade/workflow suites
Tests: test_helm_upgrade_e2e.py (4 failures), test_helm_workflow.py (4 failures)
Status: PARTIALLY FIXED — stale job cleanup added to `test-e2e.sh` and `setup-cluster.sh`.
  Stale jobs no longer block fresh deploys. However, bootstrap job FAILS (not times out)
  at step 7/7: assigning catalog role to principal role `ALL`.
  Polaris returns 404: `Entity ALL not found when trying to assign floe-e2e.catalog_admin to ALL`.
  Job exits with failure → Helm release enters `failed` state → cascade failures.
Root cause: Bootstrap job step 7 tries to assign catalog role to principal role `ALL`,
  but no such principal role exists in Polaris. The OAuth scope `PRINCIPAL_ROLE:ALL` works
  for authentication but `ALL` is not an actual principal role entity in the management API.
  Steps 1-6 succeed (catalog, role, privileges all created). The catalog is functional
  without step 7 — the failure is cosmetic but Helm treats it as fatal.
Fix: (A) Make step 7 non-fatal (warn on 404 instead of exit 1) — quickest unblock,
  (B) create the `ALL` principal role in a preceding step,
  (C) change `principalRole` to the actual default principal role name.

---

### BL-002 [debt] PostgreSQL StatefulSet not ready within Helm timeout
Added: 2026-03-15 | Source: sw-learn | Work: fix-dbt-iceberg-pipeline
Updated: 2026-03-15 | Merged into BL-001 (same root cause — Helm timeout cascade)
Priority: P2 — merged with BL-001
Status: MERGED — PostgreSQL timeout is part of the BL-001 bootstrap cascade. Fixing BL-001
  (increase Helm timeout or add startupProbe) resolves this item too.

---

### BL-003 [debt] Marquez returns 403 — auth config not applied
Added: 2026-03-15 | Source: sw-learn | Work: fix-dbt-iceberg-pipeline
Updated: 2026-03-15 | Validated: 6 failures across lineage and observability suites
Priority: P2 — blocks all lineage validation tests
Tests: test_lineage_roundtrip_e2e.py (3 failures), test_observability_roundtrip_e2e.py (3 failures)
Root cause: Marquez Helm deployment does not configure auth. The `marquez_client` fixture
creates an unauthenticated httpx.Client. Marquez API returns 403 on all endpoints.
macOS AirPlay on port 5000 also interferes with port detection (`port_already_available`
sees a non-"000" HTTP response and skips the port-forward).
Fix: (A) Configure Marquez with `MARQUEZ_AUTH_DISABLED=true` in chart ConfigMap, or
(B) add API key auth to the `marquez_client` fixture. Also add AirPlay port 5000
exclusion to `port_already_available` check.

---

### BL-004 [debt] OTel traces not reaching Jaeger — ProxyTracerProvider
Added: 2026-03-15 | Source: sw-learn | Work: fix-dbt-iceberg-pipeline
Updated: 2026-03-15 | Validated: 4 failures in observability suite
Priority: P3 — observability gap, no data correctness impact
Tests: test_observability.py (4 failures — trace/span/attribute/context tests)
Root cause: OTel SDK returns no-op `ProxyTracerProvider` because trace exporter is not
initialized in the test environment. Pipeline execution doesn't emit spans to OTel Collector.
The Collector may also have incorrect Jaeger endpoint config.
Fix: (A) Initialize OTel SDK with OTLP exporter in test conftest or pipeline entry point,
(B) verify OTel Collector config forwards to Jaeger OTLP receiver,
(C) ensure `OTEL_EXPORTER_OTLP_ENDPOINT` env var is set for test processes.

---

### BL-005 [debt] Governance schema evolution tests — missing manifest fields
Added: 2026-03-15 | Source: sw-learn | Work: fix-dbt-iceberg-pipeline
Updated: 2026-03-15 | Validated: 5 of 7 governance tests now pass
Priority: P3 — governance audit trail, no data impact
Tests: test_governance.py (2 remaining failures — schema evolution governance tests)
Status: PARTIALLY RESOLVED — governance enforcement tests (test_governance_enforcement_e2e.py)
  now pass after WU-6 T35 fix. Only schema evolution governance tests in test_governance.py
  still fail because demo `manifest.yaml` lacks `schema_evolution_policy` config.
Root cause: Demo manifest missing `schema_evolution_policy` section. Schema evolution
  governance tests expect policy enforcement results that require this config.
Fix: Add `schema_evolution_policy` section to demo manifest.yaml.

---

### BL-006 [debt] Dagster GraphQL KeyError on asset materialization trigger
Added: 2026-03-15 | Source: E2E validation | Work: fix-dbt-iceberg-pipeline
Priority: P3 — affects asset materialization trigger test
Tests: test_trigger_asset_materialization (1 failure)
Root cause: Dagster GraphQL `launchRun` response returns unexpected structure — test
code does `response["data"]["launchRun"]["run"]` but `run` key is missing from response.
Likely a Dagster API version mismatch or the mutation response schema changed.
Fix: (A) Check Dagster GraphQL schema for current `launchRun` response format,
(B) update test to handle the actual response structure.

---

### BL-007 [debt] Platform deployment cascade — 3 errors in conftest setup
Added: 2026-03-15 | Source: E2E validation | Work: fix-dbt-iceberg-pipeline
Priority: P3 — blocks 3 test collection/setup
Tests: test_platform_bootstrap.py (3 errors — collection/fixture failures)
Root cause: Fixture setup errors during test collection. Likely caused by Helm release
being in `failed` state when tests run — bootstrap fixtures can't verify platform health.
Fix: Depends on BL-001. Once Helm release is healthy, fixture setup should succeed.
Depends on: BL-001

---

### BL-008 [debt] macOS AirPlay port 5000 conflicts with Marquez detection
Added: 2026-03-15 | Source: sw-learn | Work: fix-dbt-iceberg-pipeline
Priority: P4 — developer experience on macOS
Tests: Affects port_already_available() in test-e2e.sh for Marquez service
Root cause: macOS AirPlay/AirTunes service listens on port 5000, returning HTTP 403.
`port_already_available` sees a non-"000" HTTP response and thinks Marquez is already
available, skipping the port-forward. Result: Marquez fixture connects to AirPlay instead.
Fix: Add port 5000 to a known-conflict exclusion list in `port_already_available`, or
change Marquez NodePort to avoid 5000.

---

### BL-009 [epic] Keycloak OIDC integration for Polaris
Added: 2026-03-16 | Source: sw-design | Work: polaris-rbac-keycloak (deferred)
Priority: P2 — security hardening, not blocking current E2E
Status: PLANNED — deferred from bootstrap fix work to separate epic
Scope: Add Keycloak subchart, configure Polaris `mixed` auth mode, realm import,
  JWT claim mapping, E2E token flow tests.
Assumptions to resolve: Polaris mixed auth mode (A3), iss claim in Kind (A4),
  Bitnami realm import (A5), token lifetime for Dagster jobs (A6).
Research: `.specwright/research/polaris-rbac-zero-trust-20260316.md` (tracks 4-5)

---

### BL-010 [debt] KUBECONFIG_PATH hardcoded to `devpod-floe.config` regardless of workspace name
Added: 2026-03-25 | Source: PR #196 review (greptile-apps) | Work: devpod-ops-automation
Priority: P4 — developer experience, no breakage with default workspace name
Files: `scripts/devpod-test.sh:31`, `scripts/devpod-sync-kubeconfig.sh:19`
Root cause: Both scripts hardcode `KUBECONFIG_PATH="${HOME}/.kube/devpod-floe.config"` regardless
  of `DEVPOD_WORKSPACE`. Non-default workspace names produce a confusingly named config file.
  Both scripts must be updated together to avoid a mismatch.
Fix: Derive filename from workspace: `KUBECONFIG_PATH="${HOME}/.kube/devpod-${WORKSPACE}.config"`
  in both `devpod-test.sh` and `devpod-sync-kubeconfig.sh`.

---

## Resolved

### BL-006 [resolved] Artifact promotion tests — OCI registry deployed
Resolved: 2026-03-15 | Work: fix-dbt-iceberg-pipeline (U3 stale job cleanup)
Original: OCI registry not deployed in Kind cluster. All 11 test_promotion.py tests failed.
Resolution: OCI registries (anon + auth) were already deployed in values-test.yaml.
  Stale job cleanup (BL-001 fix) unblocked the platform, and all 11 promotion tests now pass.

---

### BL-007 [resolved] Service failure resilience tests pass
Resolved: 2026-03-15 | Work: fix-dbt-iceberg-pipeline (U3 stale job cleanup)
Original: 3 resilience tests failed due to cascading infrastructure issues from stale pods.
Resolution: With healthy platform (stale jobs cleaned), all 3 resilience tests pass.
