# Design: OpenLineage Observability Fixes

## Problem

5 E2E observability tests fail because:
1. **OpenLineage emission** (3 tests): The `SyncHttpLineageTransport` attempts to POST to `http://floe-platform-marquez:5000/api/v1/lineage` (K8s-internal hostname from `demo/manifest.yaml`). When compilation runs on the host/DevPod outside K8s, the hostname is unresolvable → `ConnectError`.
2. **Structured log trace context** (1 test): `test_structured_logs_with_trace_id` expects `trace_id` fields in structlog output. The compilation pipeline emits structured logs via structlog, but trace context (trace_id, span_id) is not being injected into the log processor chain.
3. **OTel trace round-trip** (1 test): `test_compilation_generates_traces` compiles via `compiled_artifacts` fixture which also uses the raw manifest. The OTel side may work (env var override in fixture), but the test specifically checks for `customer-360` service name in Jaeger which requires `OTEL_SERVICE_NAME` to be set.

## Root Cause

There is an **asymmetry** between OTel tracing and OpenLineage configuration:

| System | Config Source | Override Mechanism | E2E Status |
|--------|-------------|-------------------|------------|
| OTel tracing | Env vars (`OTEL_EXPORTER_OTLP_ENDPOINT`) | `seed_observability` fixture sets env var | Works |
| OpenLineage | `manifest.yaml` `observability.lineage.endpoint` | **None** | Fails |

The manifest uses K8s DNS names (correct for in-cluster), but E2E tests compile on the host where port-forwards expose services on `localhost`.

## Approach

### Fix 1: Add env var override for lineage endpoint in `_build_lineage_config()`

Follow the same pattern as OTel: allow `OPENLINEAGE_URL` env var to override the manifest endpoint. This is the standard OpenLineage env var name.

**Where**: `packages/floe-core/src/floe_core/compilation/stages.py:_build_lineage_config()`

**Change**: After reading `lineage.endpoint` from manifest, check for `OPENLINEAGE_URL` env var override:
```python
url = os.environ.get("OPENLINEAGE_URL") or lineage.endpoint
```

This is consistent with:
- OpenLineage spec's standard env var (`OPENLINEAGE_URL`)
- OTel's pattern (`OTEL_EXPORTER_OTLP_ENDPOINT`)
- Non-breaking: In-cluster uses manifest config; E2E tests set env var

### Fix 2: Set `OPENLINEAGE_URL` in E2E test fixtures

**Where**: `tests/e2e/conftest.py:seed_observability()` and `tests/conftest.py:compiled_artifacts()`

**Change**: Set `OPENLINEAGE_URL=http://localhost:5100/api/v1/lineage` alongside the existing OTel env var overrides. Port 5100 is the port-forwarded Marquez endpoint.

### Fix 3: Ensure `ensure_telemetry_initialized()` is called before compilation in test

**Status**: The structlog trace context processor (`add_trace_context`) already exists in `telemetry/logging.py` and is already wired into `configure_logging()`. The `test_structured_logs_with_trace_id` test already calls `ensure_telemetry_initialized()` itself (line 534).

**Root cause hypothesis**: The test may fail because `structlog.configure(cache_logger_on_first_use=True)` caches loggers from an earlier import that happened before `configure_logging()` was called, preventing the trace context processor from taking effect. Alternatively, the test may fail as a cascade from `seed_observability` failing (ConnectError during compilation logs a warning that corrupts log parsing).

**Where**: `tests/e2e/conftest.py:seed_observability()` — needs `OPENLINEAGE_URL` set (Fix 2) to prevent ConnectError warnings polluting log output.

**Change**: Fix 2 (env var override) should resolve the ConnectError that may cascade. If the test still fails after Fix 1+2, we'll need to investigate `cache_logger_on_first_use` or structlog reconfiguration after `reset_telemetry()`. No production code change needed for this fix.

### Fix 4: Ensure `compiled_artifacts` fixture sets `OTEL_SERVICE_NAME`

**Where**: `tests/conftest.py:compiled_artifacts()` or the test itself

**Change**: `test_compilation_generates_traces` needs `OTEL_SERVICE_NAME=customer-360` set before compilation so Jaeger registers the service correctly.

## Blast Radius

### Touched
| Module/File | Scope | Propagation |
|---|---|---|
| `floe_core/compilation/stages.py:_build_lineage_config()` | Local | Env var check adds one line; no behavioral change when env var absent |
| `floe_core/telemetry/initialization.py` | None | No changes needed — trace context processor already wired |
| `tests/e2e/conftest.py:seed_observability()` | Local | Env var setup/restore in test fixture |
| `tests/conftest.py:compiled_artifacts()` | Local | Env var setup/restore in test fixture |

### NOT Touched
- Manifest schema (`LineageManifestConfig`) — no schema changes
- Transport classes (`SyncHttpLineageTransport`) — URL resolution unchanged
- Emitter classes — no changes
- In-cluster behavior — env var not set in production, manifest config used
- Any other E2E tests — only observability fixtures modified

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| `OPENLINEAGE_URL` env var leaks to other tests | Fixture saves/restores env vars (same pattern as OTel) |
| Structured log test may have deeper caching issue | Fix 1+2 resolves the primary cause; investigate structlog `cache_logger_on_first_use` if test still fails |
| Port 5100 not available in all environments | Env var is only set in E2E fixtures, not in production |

## Alternatives Considered

1. **Create a test-specific manifest with localhost URLs**: Would work but duplicates the manifest and creates drift risk. Rejected.
2. **Override at transport creation time via `compile_pipeline()` parameter**: More invasive API change. The env var approach is simpler and follows OpenLineage conventions.
3. **Use `SyncConsoleLineageTransport` in tests**: Would not test the actual HTTP emission path. Rejected.
