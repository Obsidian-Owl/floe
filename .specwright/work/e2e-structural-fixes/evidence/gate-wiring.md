# Gate: Wiring

**Status**: PASS
**Timestamp**: 2026-03-30T14:17:00Z

## Checks

- [x] ServiceEndpoint("marquez") resolves: port 5000 default, MARQUEZ_HOST/MARQUEZ_PORT env vars
- [x] ServiceEndpoint("otel-collector-grpc") resolves: port 4317 default, env var override
- [x] K8s DNS resolution via INTEGRATION_TEST_HOST=k8s
- [x] Job manifest: INTEGRATION_TEST_HOST=k8s, MARQUEZ_HOST, OTEL_HOST, OTEL_COLLECTOR_GRPC_HOST set
- [x] Job name floe-test-e2e matches script JOB_NAME variable
- [x] Makefile target calls correct script path

## Findings

None.
