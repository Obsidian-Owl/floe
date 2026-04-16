# Spec: Test Portability

## Overview

Replace 4 hardcoded `localhost` connection URLs in 3 E2E test files with
`ServiceEndpoint` so tests resolve service addresses correctly in both
host-based (dev) and in-cluster (CI) execution modes.

## Acceptance Criteria

### AC-1: OTel collector endpoint in test_observability.py (line 542)

The `OTEL_EXPORTER_OTLP_ENDPOINT` env var assignment at line 542 uses
`ServiceEndpoint("otel-collector-grpc").url` instead of `"http://localhost:4317"`.

**Boundary**: The `os.environ[...] = ...` pattern is preserved — only the URL
value changes. The env var is intentionally set to test OTel configuration behavior.

**Verification**:
- With `INTEGRATION_TEST_HOST=k8s`: env var is set to
  `http://otel-collector-grpc.floe-test.svc.cluster.local:4317`
- Without `INTEGRATION_TEST_HOST`: env var is set to `http://localhost:4317`

### AC-2: OTel collector endpoint in test_observability.py (line 1164)

Same as AC-1 but for the second occurrence at line 1164.

**Verification**: Same dual-mode check as AC-1.

### AC-3: OTel collector endpoint in test_observability_roundtrip_e2e.py (line 180)

The `os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", ...)` default value uses
`ServiceEndpoint("otel-collector-grpc").url` instead of `"http://localhost:4317"`.

**Boundary**: If `OTEL_EXPORTER_OTLP_ENDPOINT` is already set in the environment,
that value takes precedence (existing behavior preserved).

**Verification**:
- With `INTEGRATION_TEST_HOST=k8s` and no pre-set endpoint: resolves to K8s DNS URL
- With pre-set `OTEL_EXPORTER_OTLP_ENDPOINT`: uses the pre-set value (unchanged behavior)

### AC-4: Marquez URL in test_platform_deployment_e2e.py (line 294)

The Marquez URL construction uses `ServiceEndpoint("marquez").url` instead of the
`MARQUEZ_HOST_PORT` + localhost fallback chain.

**Exact pattern**: `marquez_url = os.environ.get("MARQUEZ_URL", ServiceEndpoint("marquez").url)`
The `MARQUEZ_HOST_PORT` intermediate variable is removed (unnecessary with ServiceEndpoint).

**Verification**:
- With `INTEGRATION_TEST_HOST=k8s`: URL is `http://marquez.floe-test.svc.cluster.local:5100`
- Without `INTEGRATION_TEST_HOST`: URL is `http://localhost:5100`
- With `MARQUEZ_URL` set: uses that value directly (unchanged behavior)

### AC-5: ServiceEndpoint imports added where missing

`from testing.fixtures.services import ServiceEndpoint` is present in:
- `tests/e2e/test_observability.py` (currently missing)
- `tests/e2e/test_observability_roundtrip_e2e.py` (currently missing)

`tests/e2e/test_platform_deployment_e2e.py` already has the import.

### AC-6: No localhost regression in non-functional references

The following localhost references are NOT changed (confirmed as non-functional):
- `conftest.py:349` — docstring example
- `test_observability.py:167,289,723,921` — error message strings
- `test_platform_bootstrap.py` — docstrings/comments
- `test_helm_workflow.py:509` — regex pattern for template validation
- `test_promotion.py:67` — OCI registry (separate concern)

## Design Reference

`.specwright/work/e2e-in-cluster-ci/design.md` — Section 2 (Refactor Hardcoded Localhost References)

## WARN: Design Correction

Context.md listed `conftest.py:349` as a functional change, but it is a docstring
example inside the `wait_for_service` fixture. The actual smoke check fixture already
uses `ServiceEndpoint`. Total functional changes: **4** (not 5).
