# Gate: Wiring Report

**Generated**: 2026-04-07T09:10:00Z
**Status**: PASS

## Wiring Checks

| # | Check | Status |
|---|-------|--------|
| W-1 | pytest-html in pyproject.toml → `--html` flag in Job manifests | PASS |
| W-2 | pytest-json-report in pyproject.toml → `--json-report-file` flag | PASS |
| W-3 | `${TEST_SUITE}` prefix in source paths matches Job output filenames | PASS |
| W-4 | `OTEL_EXPORTER_OTLP_ENDPOINT` hostname matches `OTEL_HOST` pattern | PASS |
| W-5 | `LOG_TAIL_LINES` defined and used consistently | PASS |
| W-6 | `LOG_TAIL_LINES` documented in script header | PASS (fixed) |

## Post-build review fix applied

Source path mismatch for destructive suite was caught and fixed in commit `2996729`.
