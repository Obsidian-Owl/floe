# Context: Test Portability (Unit 1)

## Purpose

Replace hardcoded `localhost` connection URLs in E2E tests with `ServiceEndpoint`
so tests work both via port-forward (dev) and in-cluster K8s DNS (CI).

## Key Files

### To Modify

| File | Line(s) | Current | Target |
|------|---------|---------|--------|
| `tests/e2e/test_observability.py` | 542 | `"http://localhost:4317"` | `ServiceEndpoint("otel-collector-grpc").url` |
| `tests/e2e/test_observability.py` | 1164 | `"http://localhost:4317"` | `ServiceEndpoint("otel-collector-grpc").url` |
| `tests/e2e/test_observability_roundtrip_e2e.py` | 180 | `"http://localhost:4317"` | `ServiceEndpoint("otel-collector-grpc").url` |
| `tests/e2e/test_platform_deployment_e2e.py` | 294 | `f"http://localhost:{marquez_port}"` | `ServiceEndpoint("marquez").url` |

### Read-Only References

- `testing/fixtures/services.py` — `ServiceEndpoint` class, `_get_effective_host()`,
  `SERVICE_DEFAULT_PORTS` dict. Already has `otel-collector-grpc: 4317` and `marquez: 5100`.
- `tests/e2e/conftest.py` — Already imports `ServiceEndpoint`. Line 349 is a docstring
  example (not functional code) — no change needed.

## Import Status

| File | ServiceEndpoint Imported? |
|------|--------------------------|
| `test_observability.py` | No — must add import |
| `test_observability_roundtrip_e2e.py` | No — must add import |
| `test_platform_deployment_e2e.py` | Yes — already imported |

## Gotchas

1. **OTel env var pattern must be preserved**: `test_observability.py:542,1164` intentionally
   set `OTEL_EXPORTER_OTLP_ENDPOINT` as an env var to test OTel configuration behavior.
   The ServiceEndpoint value replaces the URL string, but the `os.environ[...] = ...` pattern
   stays. Example: `os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ServiceEndpoint("otel-collector-grpc").url`

2. **Marquez env var fallback**: `test_platform_deployment_e2e.py:294` reads `MARQUEZ_URL`
   env var with localhost fallback. Replace the entire fallback chain with `ServiceEndpoint("marquez").url`.
   The `MARQUEZ_HOST_PORT` env var on line 293 becomes unnecessary.

3. **Roundtrip test default**: `test_observability_roundtrip_e2e.py:180` uses
   `os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")` — the default
   value needs replacing with `ServiceEndpoint("otel-collector-grpc").url`.

## ServiceEndpoint Resolution Chain

When `INTEGRATION_TEST_HOST=k8s` (in-cluster):
- `_get_effective_host("otel-collector-grpc", "floe-test")` → `"otel-collector-grpc.floe-test.svc.cluster.local"`
- `ServiceEndpoint("otel-collector-grpc").url` → `"http://otel-collector-grpc.floe-test.svc.cluster.local:4317"`

When `INTEGRATION_TEST_HOST` unset (host-based):
- `_get_effective_host("otel-collector-grpc", "floe-test")` → `"localhost"`
- `ServiceEndpoint("otel-collector-grpc").url` → `"http://localhost:4317"`

No changes to `services.py` needed — both modes already work.
