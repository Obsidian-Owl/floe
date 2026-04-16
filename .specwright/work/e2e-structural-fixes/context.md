# Context: E2E Structural Fixes

## Problem Statement

The E2E test suite has 91 non-passing results (50 failed + 41 errors) out of ~230 tests.
The dominant failure mode is infrastructure connectivity — SSH tunnels and port-forwards
dying mid-run, causing cascade failures across 45+ tests.

## Failure Categorization (from 2026-03-29 run)

| Category | Count | Root Cause |
|----------|-------|-----------|
| Dagster unreachable (TCP) | ~20 errors | Port-forward/tunnel death |
| Marquez timeout (polling) | ~10 errors | Port-forward/tunnel death |
| Charts dir not found | 5 errors | Wrong working directory for in-cluster |
| OTel export failure | 1 error | Hardcoded localhost:4317 |
| Compilation failures | 6 failed | .git dir missing in container / profile issues |
| Profile isolation | 3 failed | Profile mutation during session |
| Remaining failures | ~46 failed | Mix of cascade + real bugs |

## Key Files

### Infrastructure
- `testing/ci/test-e2e.sh` — port-forward management (9 processes, no reconnect)
- `testing/Dockerfile` — test runner image (Python 3.11, uv, kubectl, dbt)
- `testing/k8s/jobs/test-runner.yaml` — in-cluster Job definitions (3 variants)
- `testing/k8s/kind-config.yaml` — Kind cluster with 15+ NodePort mappings
- `scripts/devpod-tunnels.sh` — SSH tunnel management (no keepalive)
- `scripts/devpod-sync-kubeconfig.sh` — K8s API tunnel (no keepalive)

### Test Code
- `tests/e2e/conftest.py` — 1337 lines, hardcoded localhost on lines 353, 974, 977
- `tests/e2e/dbt_utils.py` — dbt-specific test utilities

### Helm Charts
- `charts/floe-platform/values.yaml` — K8sRunLauncher config (lines 187-208)
- `charts/floe-platform/values-test.yaml` — test overrides
- `charts/floe-platform/templates/job-polaris-bootstrap.yaml` — bootstrap hook

### Demo
- `demo/{customer-360,financial-risk,iot-telemetry}/` — 3 data products
- `docker/dagster-demo/Dockerfile` — demo image build

## Existing Infrastructure (Ready)

| Component | Status | Location |
|-----------|--------|----------|
| ServiceEndpoint abstraction | Ready | `testing/fixtures/services.py` |
| `INTEGRATION_TEST_HOST=k8s` env var | Ready | Used in integration jobs |
| Test container image | Ready | `testing/Dockerfile` |
| In-cluster Job definitions | Ready | `testing/k8s/jobs/` |
| Retry/polling utilities | Ready | `testing/fixtures/polling.py` |
| Kind NodePort config | Ready | `testing/k8s/kind-config.yaml` |
| Test reordering (destructive last) | Ready | `conftest.py:pytest_collection_modifyitems` |
| Infrastructure smoke check | Ready | `conftest.py:infrastructure_smoke_check` |
| Helm release recovery | Ready | `conftest.py:helm_release_health` |
| pytest-rerunfailures | Ready | `conftest.py:pytest_configure` |

## Blockers for In-Cluster Testing

1. `tests/conftest.py:124` — hardcoded `"http://localhost:5100/api/v1/lineage"` (OpenLineage)
2. `tests/conftest.py:126` — hardcoded `"http://localhost:4317"` (OTel)
3. `test_helm_workflow.py` — assumes charts dir at relative path from CWD
4. ~~K8sRunLauncher `image` not set~~ — RESOLVED (values-test.yaml:110-118)

## Research Briefs Consumed

- `e2e-ci-resilience-20260329.md` — kubefwd, in-cluster patterns, CI resilience
- `tunnel-stability-20260329.md` — SSH tunnel root cause analysis
- `alpha-remaining-bugs-20260328.md` — K8sRunLauncher, OpenLineage parentRun, CVE
- `e2e-alpha-stability-20260327.md` — 7 remaining failures with fix paths
- `e2e-failures-20260327.md` — 5 root causes
- `e2e-test-bugs-20260326.md` — 12 test failures categorized
