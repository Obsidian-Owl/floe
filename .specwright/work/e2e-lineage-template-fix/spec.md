# Spec: E2E Lineage Template Fix

## AC-1: try_create_iceberg_resources graceful failure
`try_create_iceberg_resources()` MUST return `{}` when `create_iceberg_resources()` raises, matching the documented contract. It MUST NOT re-raise.

## AC-2: Generated template emits traceCorrelation facets
When `lineage_enabled=True`, the generated `definitions.py` asset function MUST call `TraceCorrelationFacetBuilder.from_otel_context()` and include the facet in `lineage.emit_start()` run_facets.

## AC-3: Generated template emits parentRun facets
When `lineage_enabled=True`, the generated `definitions.py` asset function MUST call `extract_dbt_model_lineage()` after dbt build and emit each returned event via `lineage.emit_event()`.

## AC-4: Generated template has full lineage lifecycle
When `lineage_enabled=True`, the generated asset function MUST call `lineage.emit_start()` before dbt, `lineage.emit_complete()` after success, and `lineage.emit_fail()` on exception.

## AC-5: Lineage never blocks dbt execution
ALL lineage calls in the generated template MUST be wrapped in try/except so failures never prevent dbt from running.

## AC-6: Demo definitions.py files updated
All 3 demo product `definitions.py` files MUST be updated to include the lineage emission code matching the new template output.
