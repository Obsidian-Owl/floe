# Spec: OpenLineage Observability Fixes

## Description

Add `OPENLINEAGE_URL` env var override to `_build_lineage_config()` and set it in E2E
test fixtures so the sync HTTP lineage transport reaches Marquez via localhost
port-forwards. Also set `OTEL_SERVICE_NAME` in the `compiled_artifacts` fixture for the
OTel trace round-trip test.

## Acceptance Criteria

### AC-1: `_build_lineage_config()` respects `OPENLINEAGE_URL` env var

When `OPENLINEAGE_URL` is set, `_build_lineage_config()` uses it as the transport URL,
overriding the manifest's `observability.lineage.endpoint`.

**Testable conditions:**
- With `OPENLINEAGE_URL=http://localhost:5100/api/v1/lineage` set, the returned config
  dict has `url` equal to the env var value, not the manifest value.
- With `OPENLINEAGE_URL` unset, the returned config dict has `url` equal to the manifest
  endpoint (no behavioral change).
- With `OPENLINEAGE_URL` set but empty string, the manifest endpoint is used (empty
  string treated as absent).
- With lineage disabled in manifest, returns `None` regardless of env var.

### AC-2: `seed_observability` fixture sets `OPENLINEAGE_URL`

The `seed_observability` fixture in `tests/e2e/conftest.py` sets
`OPENLINEAGE_URL=http://localhost:5100/api/v1/lineage` before compilation and restores
the original value (or removes it) in the `finally` block.

**Testable conditions:**
- `OPENLINEAGE_URL` is set alongside `OTEL_EXPORTER_OTLP_ENDPOINT` before compilation.
- `OPENLINEAGE_URL` is restored/removed in the `finally` block (same save/restore pattern
  as the existing OTel env vars).
- After `seed_observability` runs, lineage events reach Marquez (no `ConnectError` in logs).

### AC-3: `compiled_artifacts` fixture sets `OPENLINEAGE_URL` and `OTEL_SERVICE_NAME`

The `compiled_artifacts` factory in `tests/conftest.py` sets env vars **inside** the
`_compile_artifacts()` inner function (per-invocation, not session-scoped):
- `OPENLINEAGE_URL=http://localhost:5100/api/v1/lineage`
- `OTEL_SERVICE_NAME` derived from spec path via `spec_path.parent.name` (e.g.,
  `Path("demo/customer-360/floe.yaml").parent.name` → `"customer-360"`)

Both env vars are saved before and restored/removed after each `compile_pipeline()` call.

**Testable conditions:**
- `OPENLINEAGE_URL` is set before `compile_pipeline()` is called.
- `OTEL_SERVICE_NAME` equals `spec_path.parent.name` for each compilation.
- Both env vars are restored/removed after each invocation (no leaking between calls).
- `test_compilation_generates_traces` finds `customer-360` service in Jaeger.

### AC-4: All 5 observability E2E tests pass

The following tests pass when run against the Kind cluster with port-forwards:
1. `test_openlineage_events_in_marquez` (FR-041, FR-048)
2. `test_trace_lineage_correlation` (FR-042)
3. `test_structured_logs_with_trace_id` (FR-045)
4. `test_openlineage_four_emission_points` (FR-041)
5. `test_compilation_generates_traces` (requirement marker `AC-2.3`, in `test_observability_roundtrip_e2e.py`)

### AC-5: Structured log test passes or has actionable diagnostic

`test_structured_logs_with_trace_id` is expected to pass once the ConnectError cascade
is resolved by AC-1 + AC-2. The structlog trace context processor already exists and is
wired. If the test still fails after fixing the lineage endpoint, add diagnostic logging
to capture structlog configuration state (processor chain, `cache_logger_on_first_use`
status) for further investigation.

**Testable conditions:**
- `test_structured_logs_with_trace_id` passes, OR
- If it fails, the failure message includes diagnostic info about structlog state
  (not just "no trace_id found").

### AC-6: In-cluster behavior unchanged

When `OPENLINEAGE_URL` is not set (production/in-cluster), `_build_lineage_config()`
returns the manifest endpoint unchanged. No behavioral change for in-cluster deployments.

**Testable conditions:**
- Unit test with no env var set: config uses manifest endpoint.
- No changes to manifest schema, transport classes, or emitter classes.
