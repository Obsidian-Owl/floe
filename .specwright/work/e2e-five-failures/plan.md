# Plan: E2E Five Failures Fix

## Task Breakdown

### T1: Fix materialization asset selection (AC-1)

1. Edit `tests/e2e/test_compile_deploy_materialize_e2e.py`:
   - Remove `"assetSelection": [{"path": asset_path}]` from the `variables` dict (~line 525)
   - Update `_discover_repository_for_asset` call to only destructure needed values
     (repo_name, location_name, job_name) — prefix unused `asset_path` with `_`
2. Edit `tests/e2e/conftest.py`:
   - Remove `"assetSelection": [{"path": asset_path}]` from `seed_observability` (~line 797)
   - Prefix unused `asset_path` with `_` in the destructuring (~line 789)

### T2: Refresh stale package lockfiles (AC-2)

1. Run `cd packages/floe-core && uv lock` to regenerate lockfile
2. Verify `cryptography>=46.0.6` in the updated lockfile
3. Check all other package lockfiles for stale cryptography:
   - `packages/floe-cli/uv.lock`
   - `plugins/*/uv.lock`
   - `devtools/*/uv.lock`
4. Regenerate any stale lockfiles found

### T3: Fix pod readiness check (AC-3)

1. Edit `tests/e2e/test_platform_bootstrap.py`:
   - Replace `check_all_pods_ready()` function (lines 114-131)
   - Switch from JSONPath to JSON parsing (`-o json`)
   - Add `if phase == "Succeeded": continue` filter
   - Follow pattern from `test_helm_upgrade_e2e.py:180-199`
   - Add `import json` if not already imported

### T4: Log OpenLineage backlog item (AC-4)

1. Create GitHub issue via `gh issue create`:
   - Title: "OpenLineage: emit RunEvent.START events for dbt model and pipeline lifecycle"
   - Label: `specwright-backlog`
   - Body: describe the emission gap, reference the affected code paths and test

## File Change Map

| File | Change | Task |
|------|--------|------|
| `tests/e2e/test_compile_deploy_materialize_e2e.py` | Remove `assetSelection` from selector | T1 |
| `tests/e2e/conftest.py` | Remove `assetSelection` from `seed_observability` | T1 |
| `tests/e2e/test_platform_bootstrap.py` | Rewrite `check_all_pods_ready()` | T3 |
| `packages/floe-core/uv.lock` | Regenerate | T2 |
| Other `*/uv.lock` files | Regenerate if stale | T2 |

## Ordering

T1 → T2 → T3 → T4 (independent, any order works)

## As-Built Notes

### T1: Asset Selection Fix
- Removed `assetSelection` from both `test_compile_deploy_materialize_e2e.py` (~line 525) and `conftest.py` (~line 797)
- Prefixed unused `asset_path` with `_` in both files
- **Verified**: `test_trigger_asset_materialization` PASSED in E2E run
- **Discovery**: F2 (`test_iceberg_tables_exist_after_materialization`) still fails — DuckDB `:memory:` backend doesn't create Polaris namespaces. This is a separate production issue (demo needs Iceberg storage, not DuckDB)

### T2: Lockfile Refresh
- `packages/floe-core/uv.lock` and `devtools/agent-memory/uv.lock` upgraded cryptography 46.0.5 → 46.0.6
- Other package lockfiles were already current
- Not validated in E2E due to port-forward crash mid-run

### T3: Pod Readiness Check
- Rewrote `check_all_pods_ready()` in `test_platform_bootstrap.py` to use JSON parsing with `Succeeded` phase filter
- Added `import json` at line 18
- Not validated in E2E due to port-forward crash mid-run

### T4: OpenLineage Backlog
- Created GitHub issue #214: "OpenLineage: emit RunEvent.START events for dbt model and pipeline lifecycle"
- Label: `specwright-backlog`

### Deviations
- F2 was expected to be fixed by T1 (removing assetSelection). It partially was (seeds now run), but the underlying issue is deeper — the demo uses DuckDB, not Iceberg storage. This requires a separate work unit to fix.
