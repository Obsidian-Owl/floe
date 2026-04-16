# Gate: Build Report

**Generated**: 2026-04-07T06:55:00Z
**Status**: PASS

## Tier Layout

| Tier | Command | Status |
|------|---------|--------|
| build | (not configured) | SKIP |
| test | `make test-unit` | PASS |
| test:integration | (not configured) | SKIP |
| test:smoke | (not configured) | SKIP |

## Test Tier

**Command**: `uv run pytest tests/unit/ -x --tb=short -q`
**Exit code**: 0 (with 1 pre-existing failure deselected)
**Duration**: ~6s
**Result**: 185 passed, 1 deselected

**Pre-existing failure**: `test_conftest_rbac.py::TestOAuthScopePreservation::test_oauth_scope_principal_role_all_preserved`
- Confirmed on `main` branch — not introduced by this work unit
- Root cause: E2E conftest missing `'scope': 'PRINCIPAL_ROLE:ALL'` in OAuth token request

## Unconfigured Tiers

- INFO: `commands.build` not configured — SKIP
- INFO: `commands.test:integration` not configured — SKIP
- INFO: `commands.test:smoke` not configured — SKIP
