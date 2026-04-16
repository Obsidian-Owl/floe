# Assumptions: E2E Lineage Template Fix

## ACCEPTED

### A1: try_create_iceberg_resources should not re-raise
- **Type:** Clarify (docstring vs implementation mismatch)
- **Resolution:** ACCEPTED — docstring explicitly says "returning empty dict on failure". The `raise` contradicts this. Removing it aligns code with documented intent.

### A2: Lineage emission never blocks dbt execution
- **Type:** Technical (from reference implementation)
- **Resolution:** ACCEPTED — the dynamic asset path (plugin.py:530-620) wraps ALL lineage calls in try/except. Template replicates this pattern.

### A3: Demo definitions.py files must be manually updated
- **Type:** Technical
- **Resolution:** ACCEPTED — the demo files are committed to the repo and marked AUTO-GENERATED. We update them directly to match the new template output rather than running `floe compile` (which would require the full compilation pipeline).

## VERIFIED

### V1: extract_dbt_model_lineage returns empty list when artifacts missing
- **Evidence:** `lineage_extraction.py:208-213` — returns `[]` when manifest or run_results not found.
- **Impact:** Safe to call unconditionally after dbt build.

### V2: TraceCorrelationFacetBuilder.from_otel_context() returns None when no active span
- **Evidence:** `facets.py:162-209` — returns None when no valid trace context.
- **Impact:** Template code checks for None before adding to run_facets.
