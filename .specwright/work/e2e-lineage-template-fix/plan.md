# Plan: E2E Lineage Template Fix

## Task 1: Fix try_create_iceberg_resources re-raise
- Remove `raise` from `iceberg.py:207`
- Covers: AC-1

## Task 2: Add lineage emission to template generator
- Modify `generate_entry_point_code()` in `plugin.py` to include lineage emission code when `lineage_enabled=True`
- Add conditional imports: `TraceCorrelationFacetBuilder`, `extract_dbt_model_lineage`, `UUID`, `uuid4`
- Add lineage body block: emit_start with trace facets, try/except around dbt, extract per-model lineage, emit_complete/fail
- Covers: AC-2, AC-3, AC-4, AC-5

## Task 3: Update demo definitions.py files
- Regenerate/update all 3 demo `definitions.py` files to include lineage emission
- Covers: AC-6
