# Design: E2E Lineage Template Fix

## Problem

3 remaining E2E test failures (+ 1 cascading) all trace to the code generator:

1. **`test_make_demo_completes`** — `try_create_iceberg_resources()` re-raises despite docstring promising empty dict on failure. Import-time Polaris connection fails from host (K8s-internal DNS).
2. **`test_trace_lineage_correlation`** — Generated `definitions.py` wires `LineageResource` but never calls it. No `traceCorrelation` facets emitted.
3. **`test_openlineage_four_emission_points`** — Generated template never calls `extract_dbt_model_lineage()`. No `parentRun` facets emitted.
4. **DNS resolution failure** — Cascading from #1.

## Root Cause

The dynamic asset creation path (`plugin.py:530-620`) has full lineage emission:
- `TraceCorrelationFacetBuilder.from_otel_context()` for trace correlation
- `lineage.emit_start()` / `emit_complete()` / `emit_fail()` lifecycle
- `extract_dbt_model_lineage()` for per-model parentRun facets

The template generator (`plugin.py:1100-1370`) produces asset functions that **wire the lineage resource but never use it**. The generated `definitions.py` just does:
```python
yield from dbt.cli(["build"], context=context).stream()
```

## Solution

### Fix 1: Remove re-raise in `try_create_iceberg_resources()` (Track 1+4)

**File:** `iceberg.py:207`
**Change:** Delete `raise` — the function already logs the exception. Returning `{}` matches the documented contract and lets `definitions.py` load on hosts without Polaris access.

### Fix 2: Add lineage emission to template generator (Tracks 2+3)

**File:** `plugin.py:1100-1370` — `generate_entry_point_code()`

Add lineage emission code to the generated asset function, modeled after `plugin.py:530-620`. The template asset function changes from:

```python
def {safe_name}_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
    _export_dbt_to_iceberg(context)  # if iceberg_enabled
```

To (when `lineage_enabled`):

```python
def {safe_name}_dbt_assets(context, dbt: DbtCliResource):
    import logging
    from uuid import UUID, uuid4
    _logger = logging.getLogger(__name__)
    lineage = context.resources.lineage
    run_id = None

    # 1. Emit START with trace correlation
    run_facets = {}
    try:
        trace_facet = TraceCorrelationFacetBuilder.from_otel_context()
        if trace_facet is not None:
            run_facets["traceCorrelation"] = trace_facet
    except Exception:
        _logger.warning("lineage_trace_facet_failed", exc_info=True)
    try:
        run_id = lineage.emit_start("{safe_name}_dbt_assets", run_facets=run_facets or None)
    except Exception:
        _logger.warning("lineage_emit_start_failed", exc_info=True)
        run_id = uuid4()

    # 2. Run dbt
    try:
        yield from dbt.cli(["build"], context=context).stream()
    except Exception as exc:
        try:
            lineage.emit_fail(run_id, "{safe_name}_dbt_assets", error_message=type(exc).__name__)
        except Exception:
            _logger.warning("lineage_emit_fail_failed", exc_info=True)
        raise

    # 3. Extract per-model lineage with parentRun facets
    try:
        dagster_parent_id = UUID(context.run.run_id)
        events = extract_dbt_model_lineage(
            DBT_PROJECT_DIR, dagster_parent_id,
            "{safe_name}_dbt_assets", lineage.namespace,
        )
        for event in events:
            lineage.emit_event(event)
    except Exception:
        _logger.warning("lineage_extraction_failed", exc_info=True)

    # 4. Export to Iceberg (if enabled)
    _export_dbt_to_iceberg(context)  # if iceberg_enabled

    # 5. Emit COMPLETE
    try:
        lineage.emit_complete(run_id, "{safe_name}_dbt_assets")
    except Exception:
        _logger.warning("lineage_emit_complete_failed", exc_info=True)
```

### Conditional imports

When `lineage_enabled`, the template adds:
- `from floe_core.lineage.facets import TraceCorrelationFacetBuilder`
- `from floe_orchestrator_dagster.lineage_extraction import extract_dbt_model_lineage`

These are already conditionally added (lineage import) or need to be added (facets + extraction imports).

## Blast Radius

| Module/File | Scope | Propagation |
|-------------|-------|-------------|
| `iceberg.py:207` | Single line deletion | Local — only affects import-time behavior when Polaris unreachable |
| `plugin.py:1100-1370` (template) | Template string modification | Adjacent — affects ALL future `floe compile --generate-definitions` output |
| `demo/*/definitions.py` | Regenerated | Local — these are AUTO-GENERATED files |

### What this design does NOT change
- Dynamic asset creation path (`plugin.py:530-620`) — untouched
- `LineageResource` / `NoOpLineageResource` APIs — untouched
- `extract_dbt_model_lineage()` — untouched
- `TraceCorrelationFacetBuilder` — untouched
- Any test files — untouched
- Helm charts or K8s configuration — untouched

## Risk Assessment

**Low risk.** Both fixes are well-understood:
- Fix 1 is a 1-line deletion aligning code with documented contract
- Fix 2 replicates proven patterns from the dynamic path (plugin.py:530-620)
- All lineage calls are wrapped in try/except (never blocks dbt execution)
- Generated files are clearly marked AUTO-GENERATED

## Integration Points

- Generated `definitions.py` → `LineageResource.emit_start/complete/fail/emit_event`
- Generated `definitions.py` → `TraceCorrelationFacetBuilder.from_otel_context()`
- Generated `definitions.py` → `extract_dbt_model_lineage()`
- E2E tests → Marquez API (searches for traceCorrelation and parentRun facets)
- E2E tests → Jaeger API (finds trace_id for correlation)
