# Design: E2E Five Failures Fix

## Summary

Fix 5 E2E test failures discovered during DevPod validation run (225 passed, 5 failed).
Three categories: test infrastructure (F3, F5), test logic (F1/F2), and production code (F4).

## Approach

### Fix 1: Materialization test selects wrong asset scope (F1 + F2)

**Problem**: `test_trigger_asset_materialization` materializes only `stg_crm_customers`
via `assetSelection`. With `@dbt_assets`, each dbt node is a separate Dagster asset.
Selecting only the staging model runs `dbt build --select stg_crm_customers`, which
skips seed dependencies. Seeds create the `main_raw` schema — without them, the
staging model fails with `Schema 'main_raw' does not exist`.

**Fix**: Remove `assetSelection` from the GraphQL mutation so Dagster materializes
ALL assets in the code location (seeds first, then staging, then marts). This matches
how the pipeline runs in production — the entire `dbt build` command runs sequentially.

**Alternative considered**: Materialize seeds first, then staging. Rejected because
it doubles the test complexity and still doesn't match the real workflow. The
`@dbt_assets` function calls `dbt build` (line 37 of definitions.py), which handles
ordering internally. The only requirement is NOT artificially constraining the selection.

**Alternative considered**: Change `assetSelection` to include seed assets. Rejected
because seed asset names depend on manifest content and are fragile to test against.

**Verification**: Dagster GraphQL docs confirm `assetSelection` is optional in the
`selector` — only `repositoryLocationName`, `repositoryName`, and `jobName` are
required. When `assetSelection` is omitted, Dagster materializes all assets in the job.

**Second callsite**: `conftest.py:797` (`seed_observability` fixture) has the identical
`assetSelection` pattern targeting only `stg_crm_customers`. This must also be fixed.
The fixture is best-effort (failures are warnings), so it silently fails today — but
fixing it ensures lineage seeding actually works, which is a prerequisite for F4-related
observability tests to pass once the production OpenLineage gap is addressed.

### Fix 2: Stale package lockfile (F3)

**Problem**: `packages/floe-core/uv.lock` still pins `cryptography==46.0.5` with
CVE `GHSA-m959-cc7f-wv43`. Root lockfile was updated to 46.0.6 but package-level
lockfiles were not refreshed.

**Fix**: Run `uv lock` in `packages/floe-core/` to pull in cryptography 46.0.6.
Also audit all other package lockfiles for staleness.

### Fix 3: Completed pods break readiness check (F5)

**Problem**: `check_all_pods_ready()` in `test_platform_bootstrap.py` uses JSONPath
across ALL pods. Completed Dagster run pods (phase=Succeeded) have `Ready=False`
because the container has exited normally.

**Fix**: Switch from JSONPath to JSON parsing and filter out `Succeeded` pods.
This pattern already exists in `test_helm_upgrade_e2e.py:189` and
`test_platform_deployment_e2e.py:142`.

### Fix 4: OpenLineage START events not emitted (F4)

**Problem**: Multi-layer issue:
1. Demo `definitions.py` passes `None` to `try_create_lineage_resource()` → NoOp
2. `@dbt_assets` doesn't use the custom emission code in `_create_asset_for_transform()`
3. No pipeline-level START/COMPLETE events are emitted

**Assessment**: This is a genuine production code gap in the OpenLineage integration.
The platform's custom lineage emission code and the dagster-dbt integration are on
separate code paths. Fixing this properly requires either:
- (a) Configuring a real Marquez endpoint in demo definitions (so lineage resource
  is active) AND hooking into dagster-dbt's event stream for per-model events
- (b) Building a custom dagster-dbt callback/event handler

**Recommendation**: This is architectural scope (crosses orchestrator plugin, lineage
plugin, demo definitions, and Helm chart configuration). Too large for this work unit.
Log as backlog item. For now, update the E2E test to be explicit about what it can
validate given the current architecture — specifically, it should validate that
Marquez has lineage data from Dagster's built-in OpenLineage integration (if configured)
or mark the missing emission points clearly in the assertion message.

**Wait** — let me reconsider. The test already has a clear, diagnostic assertion
message. The real question is whether the test is testing the right thing. If the
platform doesn't emit START events, the test is correctly surfacing that gap. We
should NOT weaken the test. Instead, we should log the production gap as a backlog item.

## Blast Radius

| Module | Change | Scope |
|--------|--------|-------|
| `tests/e2e/test_compile_deploy_materialize_e2e.py` | Remove `assetSelection` filter | Local |
| `tests/e2e/conftest.py` | Remove `assetSelection` in `seed_observability` | Local |
| `tests/e2e/test_platform_bootstrap.py` | Filter Succeeded pods | Local |
| `packages/floe-core/uv.lock` | Regenerate lockfile | Local |
| Other package lockfiles | Regenerate if stale | Local |

**Not changed**:
- Production code (orchestrator plugin, lineage, definitions)
- Helm charts
- CI workflows
- Other E2E tests (they already handle Succeeded pods correctly)

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Removing `assetSelection` makes test slower (runs all assets) | Medium | Accept — matches real workflow, dbt build handles ordering |
| Package lockfile regeneration pulls unexpected deps | Low | Review diff before committing |
| F4 (OpenLineage) remains unfixed | Accepted | Log as backlog — architectural scope |

## Integration Points

- F1 fix touches only test code (GraphQL mutation parameters)
- F5 fix aligns with existing codebase pattern (two other tests already do this)
- F3 fix is purely infrastructure (lockfile refresh)
