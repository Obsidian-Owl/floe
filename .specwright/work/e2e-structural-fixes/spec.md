# Spec: E2E Structural Fixes

## Overview

Fix the four remaining structural blockers preventing reliable E2E test execution,
both host-based and in-cluster. These are the highest bang-for-buck fixes to reduce
the 91 non-passing E2E tests (50 failed + 41 errors).

## Acceptance Criteria

### AC-1: Root conftest uses ServiceEndpoint for compilation endpoints

The `compiled_artifacts()` fixture in `tests/conftest.py` MUST resolve
`OPENLINEAGE_URL` and `OTEL_EXPORTER_OTLP_ENDPOINT` via `ServiceEndpoint`
instead of hardcoded `localhost` values.

**Verifiable conditions:**

1. `tests/conftest.py` uses `ServiceEndpoint("marquez").url` to construct
   `OPENLINEAGE_URL` (not hardcoded `localhost:5100`).
2. `tests/conftest.py` uses `ServiceEndpoint("otel-collector-grpc").url` for
   `OTEL_EXPORTER_OTLP_ENDPOINT` (not hardcoded `localhost:4317`).
3. When `INTEGRATION_TEST_HOST=k8s`, the fixture resolves endpoints to K8s DNS
   hostnames (e.g., `floe-platform-marquez.floe-test.svc.cluster.local`).
4. When `INTEGRATION_TEST_HOST` is unset (host-based), endpoints resolve to
   `localhost` with correct ports (backward compatible).
5. Error message strings in `tests/e2e/test_observability.py` (4 occurrences) and
   `tests/e2e/test_platform_bootstrap.py` (2 occurrences) that reference
   `localhost:5100` or `localhost:4317` use the resolved endpoint for accurate
   diagnostics.

### AC-2: In-cluster E2E orchestration script

A `testing/ci/test-e2e-cluster.sh` script MUST exist that runs the E2E test
suite as a K8s Job inside the cluster, eliminating host-to-cluster connectivity
as a dependency.

**Verifiable conditions:**

1. Script builds test runner image: `docker build -t floe-test-runner:latest -f testing/Dockerfile .`
2. Script loads image into Kind: `kind load docker-image floe-test-runner:latest`
3. Script deletes previous Job (idempotent): `kubectl delete job floe-test-e2e --ignore-not-found -n floe-test`
4. Script submits Job: `kubectl apply -f testing/k8s/jobs/test-e2e.yaml -n floe-test`
5. Script waits for completion: `kubectl wait --for=condition=complete --timeout=3600s`
6. Script extracts results: `kubectl logs` for output, `kubectl cp` for JUnit XML
7. Script exits with non-zero status if any tests fail (parsed from Job exit code)
8. Script distinguishes Job failure (exit 1) from `kubectl wait` timeout (exit 2)
   and cleans up timed-out Jobs
9. Script redirects error messages to stderr (`>&2`), uses `[[` for conditionals
10. A `test-e2e-cluster` Makefile target exists and calls the script

### AC-3: Charts directory accessible in test container

All 10 E2E test files referencing `charts/` MUST be able to find and read chart
files when running inside the test container.

**Verifiable conditions:**

1. `testing/Dockerfile` copies `charts/` into the image at `/app/charts/`
   (already confirmed: line 70 `COPY charts/ ./charts/`).
2. `_find_chart_root()` in `test_governance.py` resolves `charts/` relative to
   repo root when `WORKDIR=/app` inside the container.
3. The `_find_repo_root()` method finds `/app/pyproject.toml` inside the container
   (verified: `COPY pyproject.toml` on Dockerfile line 64).
4. No test file uses absolute host paths for chart access.

### AC-4: Profile isolation during E2E sessions

The `test_demo_profile_untouched_during_session` test MUST pass for all 3 demo
products (customer-360, financial-risk, iot-telemetry).

**Verifiable conditions:**

1. The `compiled_artifacts()` fixture does NOT write to `demo/<product>/profiles.yml`.
2. Compilation uses a temporary directory for any dbt profile output, not the
   source demo directory.
3. After a full E2E compilation cycle, `demo/<product>/profiles.yml` is unchanged
   from git HEAD (type remains `duckdb`, no `attach` key present).
4. If `compile_pipeline()` internally writes `profiles.yml`, the write target
   is the generated_profiles directory, not the demo source.

## WARNs (from Architect Review)

1. **Error message count**: `test_platform_bootstrap.py` has 2 occurrences (lines 464, 534),
   not 1 as stated in design.md. Spec AC-1.5 is correct (says 2). Design noted but not blocking.
2. **Timeout vs failure**: AC-2 now distinguishes Job failure from kubectl wait timeout
   (condition 8 added). Timed-out Jobs need cleanup to avoid blocking resubmission.
3. **Task 4 fallback**: If `_find_chart_root()` fails inside container, add `PROJECT_ROOT`
   env var fallback. This is addressed in plan.md Task 4 approach but not as a separate AC
   because Dockerfile already has `COPY charts/` and traversal should work.
