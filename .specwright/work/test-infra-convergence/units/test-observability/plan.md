# Plan: Test Runner Observability

## Task Breakdown

### Task 1: Dockerfile — add pytest plugins

**AC covered**: AC-1

Add `pytest-html` and `pytest-json-report` to the test runner image as uv dev
dependencies.

**File change map**:
- `testing/Dockerfile` — add pytest-html, pytest-json-report (via pyproject.toml dep group)

### Task 2: Job manifests — add report flags and OTel env vars

**AC covered**: AC-1, AC-2, AC-4

Update both E2E Job manifests to:
- Add `--html`, `--json-report-file` pytest args
- Add `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_SERVICE_NAME` env vars
- Add `--log-cli-level=INFO` for live logging

**File change map**:
- `testing/k8s/jobs/test-e2e.yaml` — add args and env vars
- `testing/k8s/jobs/test-e2e-destructive.yaml` — same additions with distinct filenames

### Task 3: Pod log extraction on failure

**AC covered**: AC-3

Extend `test-e2e-cluster.sh` to capture service pod logs and K8s events when the
test Job fails. Add `LOG_TAIL_LINES` configurability.

**File change map**:
- `testing/ci/test-e2e-cluster.sh` — add `extract_pod_logs()` function after step 6

### Task 4: Artifact extraction completeness

**AC covered**: AC-5

Extend `test-e2e-cluster.sh` artifact extraction to include HTML and JSON reports
alongside existing JUnit XML extraction.

**File change map**:
- `testing/ci/test-e2e-cluster.sh` — extend extraction section (lines 120-146)

## Architecture Decisions

- pytest-html and pytest-json-report are added as uv dev dependencies, not pip install.
  They're part of the test runner environment, installed via `uv sync --frozen`.
- OTel env vars are set in the Job manifest (not Dockerfile) so they can be overridden
  per environment.
- Pod log extraction is failure-only to avoid noise on successful runs.

## Dependencies

- Depends on Unit 1 (in-cluster-runner) for the updated `test-e2e-cluster.sh` structure.
- The Dockerfile changes are independent and can proceed in parallel.

## As-Built Notes

### Plan Deviations

1. **Dockerfile changes were to pyproject.toml, not Dockerfile itself**: The plan said
   "Dockerfile — add pytest plugins" but the actual change was adding `pytest-html>=4.0`
   and `pytest-json-report>=1.5` to `pyproject.toml` workspace dependencies. The Dockerfile
   picks these up via `uv sync --frozen`. No Dockerfile changes were needed.

2. **Post-build review fix: source path mismatch**: The initial implementation used
   hardcoded source paths (`/artifacts/e2e-report.html`) in `kubectl cp` commands. The
   destructive Job writes to `/artifacts/e2e-destructive-report.html`. Fixed by using
   `${TEST_SUITE}` prefix in source paths to match Job manifest output filenames.

3. **Test regex fix**: The tester's `TestExtractionPlacement` regex used `(?:else|fi)` which
   matched "fi" inside "filename" in a comment. Fixed to use `\bfi\b` word boundary.

### Implementation Decisions

- `--self-contained-html` flag added to Job manifests for portable HTML reports (no external CSS).
- `--json-report` bare flag added alongside `--json-report-file=` to activate the plugin.
- `extract_pod_logs()` uses `timeout 10` command (not `--request-timeout`) for per-pod timeout.
- Pod log extraction uses `continue` after failure to advance the loop.

### Actual File Paths

- `pyproject.toml` — pytest-html, pytest-json-report dependencies (lines 18-19)
- `testing/k8s/jobs/test-e2e.yaml` — report args (lines 36-41), OTel env vars (lines 106-109)
- `testing/k8s/jobs/test-e2e-destructive.yaml` — same structure with distinct filenames
- `testing/ci/test-e2e-cluster.sh` — `extract_pod_logs()` (lines 40-68), artifact extraction (lines 218-228)
- `tests/unit/test_observability_deps.py` — 7 tests
- `tests/unit/test_observability_manifests.py` — 24 tests
- `tests/unit/test_pod_log_extraction.py` — 22 tests
- `tests/unit/test_artifact_extraction.py` — 16 tests
