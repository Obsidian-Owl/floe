# Plan: Test Portability

## Task Breakdown

### Task 1: Replace OTel collector URLs in test_observability.py

**AC coverage**: AC-1, AC-2, AC-5 (partial)

**Changes**:
- Add `from testing.fixtures.services import ServiceEndpoint` to imports
- Line 542: Replace `"http://localhost:4317"` with `ServiceEndpoint("otel-collector-grpc").url`
- Line 1164: Replace `"http://localhost:4317"` with `ServiceEndpoint("otel-collector-grpc").url`

**File change map**:
| File | Action | Lines |
|------|--------|-------|
| `tests/e2e/test_observability.py` | Edit | imports, ~542, ~1164 |

### Task 2: Replace OTel collector URL in test_observability_roundtrip_e2e.py

**AC coverage**: AC-3, AC-5 (partial)

**Changes**:
- Add `from testing.fixtures.services import ServiceEndpoint` to imports
- Line 180: Replace `"http://localhost:4317"` default with `ServiceEndpoint("otel-collector-grpc").url`

**File change map**:
| File | Action | Lines |
|------|--------|-------|
| `tests/e2e/test_observability_roundtrip_e2e.py` | Edit | imports, ~180 |

### Task 3: Replace Marquez URL in test_platform_deployment_e2e.py

**AC coverage**: AC-4

**Changes**:
- Line ~293-294: Replace `MARQUEZ_HOST_PORT` + localhost fallback with
  `ServiceEndpoint("marquez").url`, preserving `MARQUEZ_URL` env var override

**File change map**:
| File | Action | Lines |
|------|--------|-------|
| `tests/e2e/test_platform_deployment_e2e.py` | Edit | ~293-294 |

## Task Order

```
Task 1 ─┐
Task 2 ─┼─ (independent, can run in parallel)
Task 3 ─┘
```

All tasks are independent. No ordering constraints.

## Verification Strategy

Unit tests for this work unit are lightweight — they verify that the ServiceEndpoint
construction produces correct URLs in both modes. The real validation is running the
E2E tests themselves (which happens in Unit 2 via the in-cluster CI pipeline).

**Local verification**: `INTEGRATION_TEST_HOST=k8s python -c "from testing.fixtures.services import ServiceEndpoint; print(ServiceEndpoint('otel-collector-grpc').url)"`
should print `http://otel-collector-grpc.floe-test.svc.cluster.local:4317`.

## As-Built Notes

- All 3 tasks implemented in a single commit (`d43c999`) — changes were mechanical
  string replacements with no complexity warranting separate commits.
- `ruff check` caught import sorting issue in `test_observability.py` (ServiceEndpoint
  import was placed after third-party imports but before local import of
  IntegrationTestBase). Auto-fixed with `ruff check --fix`.
- `MARQUEZ_HOST_PORT` env var removed as planned — `ServiceEndpoint("marquez").url`
  handles both modes. `MARQUEZ_URL` override preserved via `os.environ.get()`.
- Verified both resolution modes work:
  - localhost: `http://localhost:4317`, `http://localhost:5100`
  - k8s: `http://otel-collector-grpc.floe-test.svc.cluster.local:4317`,
    `http://marquez.floe-test.svc.cluster.local:5100`
- No changes to `ServiceEndpoint` class or `SERVICE_DEFAULT_PORTS` — both services
  already had correct port mappings.
- Pre-existing Pyright warnings in test files noted but not addressed (out of scope).
