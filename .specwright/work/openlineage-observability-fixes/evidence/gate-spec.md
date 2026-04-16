# Gate: spec
## Status: WARN
## Timestamp: 2026-03-26T18:00:00Z

### Acceptance Criteria Mapping

| AC | Status | Evidence |
|----|--------|----------|
| AC-1 | PASS | `_build_lineage_config()` reads `OPENLINEAGE_URL` at `stages.py:238`. 5 unit tests in `test_lineage_config.py` cover: override, unset, empty, disabled, no-observability. |
| AC-2 | PASS | `seed_observability` sets `OPENLINEAGE_URL` at `e2e/conftest.py:976`, restores in finally block at lines 1003-1012. |
| AC-3 | PASS | `compiled_artifacts` fixture sets `OPENLINEAGE_URL`, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_INSECURE` at `conftest.py:122-127`, restores in finally block. `test_compilation_generates_traces` finds `customer-360` in Jaeger. |
| AC-4 | WARN | 4 of 5 tests pass. `test_openlineage_four_emission_points` fails — production code gap (per-dbt-model lineage emission not wired). Not a test/infra issue. |
| AC-5 | PASS | `test_structured_logs_with_trace_id` passes. OTel endpoint set before `ensure_telemetry_initialized()` at `test_observability.py:537-539`. |
| AC-6 | PASS | Unit tests `test_openlineage_url_env_var_unset_uses_manifest`, `test_lineage_disabled_ignores_env_var`, `test_no_observability_config_ignores_env_var` all pass. No manifest schema changes. |

### Notes
- AC-4 partial: 1 remaining test failure is a WIP production feature gap (per-dbt-model OpenLineage emission),
  not a test infrastructure issue. The test correctly identifies the gap.
- All other ACs are fully met.
