# Context: OpenLineage Observability Fixes

## Problem Summary

5 E2E observability tests fail because the OpenLineage sync emitter cannot connect to Marquez during compilation. The manifest configures a K8s-internal hostname (`http://floe-platform-marquez:5000/api/v1/lineage`) but compilation runs on the host where that hostname is unreachable.

## Key Files

### Emission Pipeline
- `packages/floe-core/src/floe_core/compilation/stages.py:217-338` — `_build_lineage_config()` reads manifest config, `compile_pipeline()` creates emitter and calls emit_start/complete/fail
- `packages/floe-core/src/floe_core/lineage/emitter.py:195-362` — `SyncLineageEmitter` class, `create_sync_emitter()` factory
- `packages/floe-core/src/floe_core/lineage/transport.py:382-500` — `SyncNoOpTransport`, `SyncConsoleLineageTransport`, `SyncHttpLineageTransport`

### Configuration
- `demo/manifest.yaml:67-78` — Observability config with `lineage.endpoint: http://floe-platform-marquez:5000/api/v1/lineage`
- `packages/floe-core/src/floe_core/schemas/manifest.py` — `LineageManifestConfig` schema (enabled, transport, endpoint)

### Test Infrastructure
- `tests/e2e/conftest.py:932-1015` — `seed_observability` fixture: compiles demo products, triggers Dagster run
- `tests/e2e/conftest.py:971-973` — Sets `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` (OTel override works)
- `tests/e2e/conftest.py:976` — Uses `demo/manifest.yaml` directly (no lineage endpoint override)
- `tests/e2e/test_observability.py` — 4 failing tests (FR-041, FR-042, FR-045, FR-048)
- `tests/e2e/test_observability_roundtrip_e2e.py` — 1 failing test (AC-2.3)

### Lineage Plugin
- `plugins/floe-lineage-marquez/` — MarquezLineageBackendPlugin, appends `/api/v1/lineage` to base URL
- Port-forward: `localhost:5100` → K8s `floe-platform-marquez:5000`

## Root Cause Analysis

### Why OTel tracing works but OpenLineage doesn't
- **OTel**: Uses env vars (`OTEL_EXPORTER_OTLP_ENDPOINT`) — the test fixture overrides to `localhost:4317`
- **OpenLineage**: Reads endpoint from manifest YAML — no env var override mechanism exists
- The manifest uses K8s DNS names (correct for in-cluster), but compilation runs on the host

### The asymmetry
| System | Config Source | Override Mechanism | E2E Status |
|--------|-------------|-------------------|------------|
| OTel tracing | Env vars | Fixture sets `OTEL_EXPORTER_OTLP_ENDPOINT` | WORKS |
| OpenLineage | manifest.yaml | None | FAILS |

### Error chain
1. `seed_observability` calls `compile_pipeline(spec_path, manifest_path)`
2. `_build_lineage_config(manifest)` returns `{"type": "http", "url": "http://floe-platform-marquez:5000/api/v1/lineage"}`
3. `create_sync_emitter()` creates `SyncHttpLineageTransport(url=...)`
4. `emitter.emit_start()` → `httpx.Client.post(url)` → `ConnectError` (hostname unresolvable)
5. Exception caught at stages.py:336-338, logged as `lineage_emit_start_failed, error: ConnectError`
6. Compilation succeeds (non-blocking), but no lineage events reach Marquez

## Test Expectations

### test_openlineage_events_in_marquez (FR-041, FR-048)
- Queries Marquez `/api/v1/namespaces/{ns}/jobs` for pipeline jobs
- Expects real OpenLineage jobs from compilation

### test_trace_lineage_correlation (FR-042)
- Queries both Jaeger (`/api/traces`) and Marquez (`/api/v1/namespaces/{ns}/jobs/{name}/runs`)
- Expects trace_id correlation between OTel and OpenLineage

### test_structured_logs_with_trace_id (FR-045)
- Captures compilation log output, expects `trace_id` in structured log lines
- **Key finding**: The `add_trace_context` processor already exists in `telemetry/logging.py:34-69` and is already wired into `configure_logging()`. The test already calls `ensure_telemetry_initialized()` itself (line 534). No new structlog processor code needed.
- **Likely cause**: ConnectError warnings from lineage emission polluting log output, or `cache_logger_on_first_use=True` preventing reconfiguration after `reset_telemetry()`

### test_openlineage_four_emission_points (FR-041)
- Expects 4 lifecycle events: dbt model START/COMPLETE + pipeline START/COMPLETE

### test_compilation_generates_traces (AC-2.3)
- Compiles customer-360, queries Jaeger for traces from `customer-360` service
- Expects span hierarchy with parent-child relationships

## Constraints
- CWE-532: Never log credential-bearing URLs — use `type(exc).__name__` only
- Must not break in-cluster compilation (K8s DNS names must still work)
- Follow same pattern as OTel (env var override)
- Non-blocking: emission failures must not block compilation
