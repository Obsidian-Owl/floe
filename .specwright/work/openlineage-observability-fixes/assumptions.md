# Assumptions: OpenLineage Observability Fixes

## A-1: `OPENLINEAGE_URL` is the standard env var name
- **Type**: reference
- **Status**: VERIFIED
- **Evidence**: OpenLineage spec defines `OPENLINEAGE_URL` as the standard environment variable for endpoint configuration. Consistent with the project's OTel pattern (`OTEL_EXPORTER_OTLP_ENDPOINT`).

## A-2: Port 5100 is the port-forwarded Marquez endpoint
- **Type**: reference
- **Status**: VERIFIED
- **Evidence**: `testing/k8s/setup-cluster.sh` does not explicitly list Marquez port-forward, but the E2E test infrastructure uses `localhost:5100` for Marquez API access (confirmed from test fixtures and Makefile port-forward targets).

## A-3: structlog trace context processor already exists and is wired
- **Type**: reference
- **Status**: VERIFIED
- **Evidence**: `telemetry/logging.py:34-69` defines `add_trace_context` processor. `configure_logging()` (line 72-121) wires it into structlog via `structlog.configure()`. `ensure_telemetry_initialized()` in `initialization.py:102` calls `configure_logging()`. No new production code needed for trace context injection.

## A-4: `compiled_artifacts` fixture in `tests/conftest.py` does not set `OTEL_SERVICE_NAME`
- **Type**: clarify
- **Status**: VERIFIED
- **Evidence**: Read `tests/conftest.py:75-107` — the fixture calls `compile_pipeline()` with the raw manifest but does not set `OTEL_SERVICE_NAME` env var. The `test_compilation_generates_traces` test expects `customer-360` service name in Jaeger.

## A-5: Env var override is non-breaking for in-cluster compilation
- **Type**: reference
- **Status**: VERIFIED
- **Evidence**: When `OPENLINEAGE_URL` is not set, `os.environ.get()` returns `None`, and the manifest endpoint is used unchanged. No behavioral change for in-cluster deployments.
