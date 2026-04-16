# Spec: Test Runner Observability

## Acceptance Criteria

### AC-1: Structured test output artifacts

The test runner Dockerfile MUST include `pytest-html` and `pytest-json-report` as
test dependencies. The E2E Job manifests MUST pass flags to generate:

- HTML report at `/artifacts/e2e-report.html`
- JSON report at `/artifacts/e2e-report.json`
- JUnit XML at `/artifacts/e2e-results.xml` (already exists)

All three artifacts MUST be extractable from the PVC after test completion.

**Boundary conditions**:
- If `pytest-html` fails to generate (e.g., permission error), tests MUST still
  complete — report generation failure is non-fatal.
- Destructive test Job MUST write to separate file names (`e2e-destructive-report.html`)
  to avoid overwriting standard test artifacts.

### AC-2: OTel trace emission from test runner

The E2E Job manifest MUST set `OTEL_EXPORTER_OTLP_ENDPOINT` pointing to the
in-cluster OTel collector (`http://floe-platform-otel:4317`).

When `OTEL_EXPORTER_OTLP_ENDPOINT` is set, tests that call
`ensure_telemetry_initialized()` MUST emit traces to the collector.

Verification: After a test run completes, querying the Jaeger API at
`http://<jaeger-host>:16686/api/traces?service=floe-test-runner&limit=1` MUST return
at least one trace (HTTP 200 with non-empty `data` array). This is a manual
verification step, not an automated gate — traces are a debugging aid, not a
pass/fail criterion.

**Boundary conditions**:
- If the OTel collector is unavailable, tests MUST still pass — no hangs, no errors.
  This is guaranteed by the OTel SDK spec (fail-open design). Project code MUST NOT
  wrap `ensure_telemetry_initialized()` in try/except that could re-raise.
- `OTEL_SERVICE_NAME` MUST be set to `floe-test-runner` to distinguish test traces
  from application traces in Jaeger.

### AC-3: Pod log extraction on failure

When the test Job fails (exit code != 0), `test-e2e-cluster.sh` MUST:

1. Collect logs from ALL pods in `$TEST_NAMESPACE` (last `$LOG_TAIL_LINES` lines each,
   default 100).
2. Save each pod's logs to `test-artifacts/pod-logs/{pod-name}.log`.
3. Capture K8s events: `kubectl get events --sort-by='.lastTimestamp' -n $TEST_NAMESPACE`
   saved to `test-artifacts/pod-logs/events.txt`.
4. Print a summary of collected pod log files to stdout.

On test success, pod log extraction is SKIPPED (unnecessary noise).

**Boundary conditions**:
- `LOG_TAIL_LINES` env var overrides the default 100.
- If a pod log extraction fails (pod already terminated), skip it with a warning — do
  not fail the extraction loop.
- Pod log extraction MUST complete in under 60 seconds (timeout per pod: 10s).

### AC-4: Pytest live-log forwarding

The E2E Job manifest MUST set environment variables or pytest flags to enable
live logging at INFO level:

- `PYTEST_ADDOPTS` includes `--log-cli-level=INFO` (or via `pyproject.toml` config).
- `kubectl logs -f` streaming in `test-e2e-cluster.sh` already works — this AC ensures
  the streamed content is useful for real-time debugging.

### AC-5: Artifact extraction completeness

`test-e2e-cluster.sh` MUST extract ALL artifacts from the PVC after test completion:

- `e2e-results.xml` (JUnit XML)
- `e2e-report.html` (HTML report)
- `e2e-report.json` (JSON report)
- `pod-logs/` directory (on failure only)

Extraction uses `kubectl cp` from the test pod. If the pod has already terminated,
use a helper busybox pod to access the PVC (existing pattern in `test-integration.sh`).

