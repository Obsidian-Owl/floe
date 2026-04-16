# Gate: Tests

**Status**: PASS
**Run at**: 2026-04-07
**Command**: `.venv/bin/python -m pytest tests/unit/test_dagster_security_contexts.py tests/unit/test_observability_security_contexts.py tests/unit/test_makefile_containerized_tools.py tests/unit/test_audit_marquez_gap.py tests/contract/test_helm_security_contexts.py tests/contract/test_rbac_least_privilege.py`

## Summary

26 tests, 26 passed, 0 failed, 0 skipped.

## Coverage by Acceptance Criterion

| AC | Test File | Count | Result |
|----|-----------|-------|--------|
| AC-1 | tests/unit/test_dagster_security_contexts.py | 8 | PASS |
| AC-2 | tests/unit/test_observability_security_contexts.py (OTel, Jaeger) | 3 | PASS |
| AC-3 | tests/unit/test_observability_security_contexts.py (MinIO) | 2 | PASS |
| AC-4 | tests/contract/test_helm_security_contexts.py | 3 | PASS |
| AC-5, AC-6, AC-7 | tests/unit/test_makefile_containerized_tools.py | 4 | PASS |
| AC-8 | tests/contract/test_rbac_least_privilege.py (standard runner) | 2 | PASS |
| AC-9 | tests/contract/test_rbac_least_privilege.py (destructive runner) | 2 | PASS |
| AC-10 | tests/unit/test_audit_marquez_gap.py | 2 | PASS |

## Findings

None. All AC-scoped tests pass.

## Notes

- The project's standard `make test-unit` target scopes pytest to
  `packages/*/tests/unit`, `plugins/*/tests/unit`, and `testing/tests/unit`.
  It does NOT include root `tests/unit/` or `tests/contract/` where the
  security-hardening evidence tests live. This gate therefore runs the
  new files explicitly.
