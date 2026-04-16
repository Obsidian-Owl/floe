# Decisions: e2e-test-isolation-fixes

## D1: Use monkeypatch instead of tmp_path-only approach for profile isolation

**Decision**: Redirect `dbt_utils.__file__` via monkeypatch so `Path(__file__).parent` resolves to `tmp_path`.

**Alternatives**:
1. **Patch `run_dbt` function** — Changes production code for test convenience. Rejected per constitution.
2. **Use only tmp_path** — The tests validate `run_dbt()`'s path resolution which is hardcoded to `Path(__file__).parent`. Can't test real behavior without redirecting the path. Rejected.
3. **Don't clean up in finally** — Simplest but leaves test artifacts in source tree. Rejected.

**Rule applied**: DISAMBIGUATION — simplest solution that preserves test behavior and doesn't modify production code.

## D2: Load lineage resource from observability config, not plugins.lineage_backend

**Decision**: Generate `_load_lineage_resource()` that reads `observability.lineage_endpoint` directly.

**Rationale**: `plugins.lineage_backend` is `null` in compiled artifacts, but `observability.lineage_endpoint` IS configured with the Marquez URL. The template should use the available configuration.

**Alternatives**:
1. **Require lineage_backend plugin** — Would require schema/compile changes to populate the plugin ref. Over-engineered for this fix. Rejected.
2. **Pass endpoint as env var** — Adds deployment complexity. The endpoint is already in compiled_artifacts. Rejected.

**Rule applied**: Use existing configuration. Simplest path to real lineage emission.

## D3: Single work unit (no decomposition needed)

**Decision**: Both fixes are under 3 files each, tightly scoped. Single work unit.

**Rule applied**: Simplicity — decomposition adds overhead without benefit for small changes.
