# Security Gate — loud-failures
**Status**: PASS (1 WARN)
**Timestamp**: 2026-04-06T15:12:00Z

- No hardcoded secrets
- No eval/exec/shell=True
- No exception swallowing (all 4 factories re-raise)
- CWE-532: Logs use type(exc).__name__ not str(exc)
- WARN: LineageResource.emit_fail(error_message=...) API surface could receive unsanitized exception strings from callers — no current violation found, pre-existing risk
