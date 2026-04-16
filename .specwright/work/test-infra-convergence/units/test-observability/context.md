# Context: Test Observability (Unit 2)

## Problem

When E2E tests fail in-cluster, the only debugging output is raw pytest console logs
captured via `kubectl logs`. No HTML reports, no structured logs, no OTel traces
from test code, and no service pod log extraction on failure.

## Existing Infrastructure

| File | Status | What exists |
|------|--------|-------------|
| `testing/Dockerfile` | Complete | Python 3.11 + uv + all floe packages. Has structlog via deps. |
| `testing/k8s/jobs/test-e2e.yaml` | Complete | Job manifest with `--junitxml` flag. PVC at `/artifacts/`. |
| `testing/k8s/pvc/test-artifacts.yaml` | Complete | 1Gi PVC for artifacts. |
| `testing/ci/test-e2e-cluster.sh` | Complete | Extracts logs + JUnit XML post-run (lines 120-146). |

## Key Design Decisions

- **D-3**: Three-tier observability: (A) pytest reports, (B) OTel traces, (C) pod log extraction.
- No service mesh or sidecar injection.
- OTel SDK is fail-open — if collector is unavailable, tests still pass (no traces).

## File Paths

- `testing/Dockerfile` — add `pytest-html`, `pytest-json-report`
- `testing/k8s/jobs/test-e2e.yaml` — add `--html`, `--json-report` args, OTel env vars
- `testing/k8s/jobs/test-e2e-destructive.yaml` — same additions
- `testing/ci/test-e2e-cluster.sh` — extend log extraction on failure (Layer C)

## OTel Collector in Cluster

The OTel collector is deployed as `floe-platform-otel` in the `floe-test` namespace.
Job manifest already has `OTEL_HOST: floe-platform-otel`. Tests that call
`ensure_telemetry_initialized()` will emit traces if `OTEL_EXPORTER_OTLP_ENDPOINT`
is set.
