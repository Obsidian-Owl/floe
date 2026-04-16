# Gate: security
## Status: WARN
## Timestamp: 2026-03-26T17:55:00Z

### Findings

| Severity | ID | File | Finding |
|----------|-----|------|---------|
| HIGH | 1 | stages.py:238 | OPENLINEAGE_URL accepted without URL scheme validation (CWE-918 SSRF risk) |
| MEDIUM | 2 | test_lineage_config.py:24-27 | Unit test constants use http:// not https:// |
| MEDIUM | 3 | tests/conftest.py:124-127 | OTEL_EXPORTER_OTLP_INSECURE=true hardcoded (localhost-scoped, acceptable) |
| MEDIUM | 4 | tests/e2e/conftest.py:458-469 | Polaris token response parse error could surface response body (CWE-532) |
| INFO | 5 | tests/e2e/conftest.py | subprocess calls use shell=False correctly throughout |
| INFO | 6 | tests/e2e/conftest.py | Demo credentials annotated with pragma: allowlist secret |

### Notes
- No hardcoded secrets in production code
- CWE-532 mitigation present: exception logging uses type(exc).__name__ only
- Security HIGH finding (SSRF) is mitigated by: (a) SyncHttpLineageTransport already validates URL scheme at transport.py:459, (b) env var is operator-controlled, not user-controlled
