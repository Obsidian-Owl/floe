# Context: E2E Lineage Template Fix

**baselineCommit:** e1dbdb3f64b2fec5574b3c006645173418fc5800

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | Template generator + dynamic asset creation | 1100-1370 (template), 530-620 (reference) |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py` | `try_create_iceberg_resources` with contradictory raise | 161-207 |
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py` | `extract_dbt_model_lineage()` | 176-220 |
| `packages/floe-core/src/floe_core/lineage/facets.py` | `TraceCorrelationFacetBuilder` | 162-209 |
| `demo/customer-360/definitions.py` | Generated template (needs regeneration) | All |

## Research Brief

See `.specwright/research/e2e-remaining-failures-20260403.md` for full analysis.

## Gotchas

1. The template uses f-string interpolation with `{safe_name}` — any new code in the template must escape literal `{` as `{{`.
2. The `iceberg_post_build` variable is only set when `iceberg_enabled` — lineage code needs its own conditional variable.
3. `lineage.namespace` is a property on `LineageResource` — the generated code must access it at runtime.
4. The `extract_dbt_model_lineage` function signature: `(project_dir: Path, parent_run_id: UUID, parent_job_name: str, namespace: str) -> list[LineageEvent]`.
5. Import-time execution: `_load_iceberg_resources()` runs at module import (it's called in the `defs = Definitions(...)` block). After fixing the raise, this will gracefully return `{}` when Polaris is unreachable.
6. Demo `definitions.py` files are AUTO-GENERATED — they need to be regenerated after fixing the template, OR the demo can be re-compiled. For now, we manually update the 3 demo files to match the new template output.
