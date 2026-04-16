# Build Gate Evidence — runtime-loader

**Generated:** 2026-04-06T13:50:00Z

## Tier Layout

| Tier | Command | Configured |
|------|---------|------------|
| build | `commands.build` | SKIP (null) |
| test | `commands.test` = `make test-unit` | YES |
| test:integration | `commands.test:integration` | SKIP (null) |
| test:smoke | `commands.test:smoke` | SKIP (null) |

## Tier Results

### build
- **Status:** SKIP (not configured)

### test
- **Command:** `.venv/bin/python -m pytest plugins/floe-orchestrator-dagster/tests/unit/ -v --tb=short`
- **Exit code:** 0
- **Duration:** ~4s
- **Result:** 627 passed, 75 warnings
- **Warnings:** SQLAlchemy pool reset on closed DB (test teardown), Pydantic V2 deprecation (dagster internals), asyncio mock warnings — all non-blocking
- **Status:** PASS

### test:integration
- **Status:** SKIP (not configured)
- **Note:** Integration tests were run manually and passed (6/6) but not part of configured gate command

### test:smoke
- **Status:** SKIP (not configured)

## Gate Verdict

**Status: PASS**

- Configured tier (test) passed with 627 tests
- 3 unconfigured tiers (build, test:integration, test:smoke) = SKIP
