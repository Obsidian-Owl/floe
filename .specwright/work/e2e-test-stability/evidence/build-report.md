# Build Gate Report

**Work Unit**: e2e-test-stability
**Timestamp**: 2026-03-31T11:22:00Z
**Verdict**: PASS

## Tier Layout

| Tier | Command | Status |
|------|---------|--------|
| build | *(not configured)* | SKIP |
| test | `make test-unit` | PASS |
| test:integration | *(not configured)* | SKIP |
| test:smoke | *(not configured)* | SKIP |

## Tier: test

- **Command**: `make test-unit`
- **Exit code**: 0
- **Duration**: 510.74s (8m30s)
- **Results**: 8840 passed, 1 skipped, 19 warnings
- **Coverage**: 87.44% (threshold: 80%)

### Notes

- INFO: `commands.build` not configured — SKIP
- INFO: `commands.test:integration` not configured — SKIP
- INFO: `commands.test:smoke` not configured — SKIP
- 19 warnings are deprecation/forward-compat warnings from third-party libraries (pydantic, great_expectations, asyncio mock). No action required.
