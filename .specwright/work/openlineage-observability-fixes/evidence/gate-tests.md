# Gate: tests
## Status: WARN
## Timestamp: 2026-03-26T17:55:00Z

### Findings

| Severity | ID | File | Finding |
|----------|-----|------|---------|
| BLOCK | 1 | test_lineage_config.py | Missing test for whitespace-only OPENLINEAGE_URL (e.g., `"   "`) |
| BLOCK | 2 | test_lineage_config.py | No test verifies `result["type"]` field in returned config dict |
| BLOCK | 3 | test_lineage_config.py | Missing test: OPENLINEAGE_URL set but lineage.endpoint=None — env var silently ignored due to early return |
| BLOCK | 4 | test_lineage_config.py | No wiring test that compile_pipeline() passes _build_lineage_config() result to create_sync_emitter() |
| WARN | 1 | test_lineage_config.py | No test for non-http transports (console, kafka) with env var |
| WARN | 4 | tests/e2e/conftest.py | _marquez_has_lineage does not check floe.compilation namespace |
| WARN | 5 | test_observability.py | `len(all_jobs) > 0` is weak, mitigated by subsequent content check |
