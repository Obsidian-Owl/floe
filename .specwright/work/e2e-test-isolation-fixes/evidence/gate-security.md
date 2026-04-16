# Gate: Security

**Status**: PASS (with WARNs)
**Ran**: 2026-04-04

## Findings

- 0 BLOCK, 0 HIGH (in scope), 3 WARN, 3 INFO
- HIGH-1 (predictable /tmp DuckDB path) is PRE-EXISTING — not introduced by this change
- No hardcoded secrets detected
- No dangerous constructs (eval, exec, shell=True, deserialization of untrusted data)

## WARNs (pre-existing, not introduced by this change)

- W1: Bare `except Exception` in _load_lineage_resource — intentional graceful degradation
- W2: `getattr` on observability object — Pydantic validates upstream
- W3: Iceberg table_name reuse without re-validation — guard precedes use
