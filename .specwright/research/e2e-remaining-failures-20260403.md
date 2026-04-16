# Research Brief: E2E Remaining Failures (3 Issues, 1 Cascading)

**Date:** 2026-04-03
**Confidence:** HIGH (code analysis + runtime evidence)
**Tracks:** 3 (+ 1 cascading from Track 1)

---

## Track 1: `test_make_demo_completes` — Import-Time Polaris Connection

**Confidence:** HIGH

### Problem
The test dynamically imports each demo product's `definitions.py` from the host.
At import time, `definitions.py` calls `_load_iceberg_resources()` which eagerly
connects to Polaris via `IcebergTableManager.__init__` -> `_connect_to_catalog()`.
This fails because `floe-platform-polaris` is K8s-internal DNS, unreachable from host.

### Root Cause
`try_create_iceberg_resources()` in `iceberg.py:203-207` catches exceptions but
**re-raises** them. Its docstring says "returning empty dict on failure" but the
implementation contradicts this.

### Fix
Remove the `raise` in `try_create_iceberg_resources()` — the function already logs
the exception. Returning `{}` matches the documented contract and lets definitions.py
load on hosts without Polaris access (degraded mode: no Iceberg IO, everything else works).

**File:** `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py:207`
**Change:** Delete `raise`

---

## Track 2: `test_trace_lineage_correlation` — No traceCorrelation Facets in Marquez

**Confidence:** HIGH

### Problem
The test finds a trace_id in Jaeger and searches for it in Marquez run facets. Zero matches.

### Root Cause — CODE GENERATION GAP
The **generated `definitions.py` files** (used by all 3 demo products) do NOT emit
traceCorrelation facets. The asset function is:

```python
# demo/customer-360/definitions.py:159
yield from dbt.cli(["build"], context=context).stream()
```

The lineage resource (`try_create_lineage_resource(None)`) is wired as a Dagster resource
but the asset function **never calls it**. The `emit_start()` / `emit_complete()` calls
that attach traceCorrelation facets only exist in the **dynamic asset creation path**
(`plugin.py:557-616`), which the demo products don't use.

### Fix
Add lineage emission to the generated template's asset function. The template at
`plugin.py:1344-1351` needs to:
1. Import `TraceCorrelationFacetBuilder` 
2. Call `lineage.emit_start()` with trace facets before `dbt.cli()`
3. Call `lineage.emit_complete()` after successful build
4. Call `lineage.emit_fail()` on exception

**File:** `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py:1100-1363`
**Change:** Add lineage emission block to template (conditional on `lineage_enabled`)

---

## Track 3: `test_openlineage_four_emission_points` — No parentRun Facets in Marquez

**Confidence:** HIGH

### Problem
917 Marquez runs, zero contain a valid `parentRun` facet with a runId.

### Root Cause — SAME CODE GENERATION GAP AS TRACK 2
The `parentRun` facet is only emitted by `extract_dbt_model_lineage()` (in
`lineage_extraction.py:216-240`). This function is called from `plugin.py:584-593`
in the **dynamic asset creation path** — but the generated `definitions.py` never
calls it.

The 917 runs in Marquez come from:
- Compilation-phase events (emitted by `compile_pipeline()`) — no parentRun
- Asset-level events from dagster-dbt's built-in OpenLineage integration — no parentRun
Neither source includes parentRun facets.

### Fix
Add per-model lineage extraction to the generated template. After `dbt.cli(["build"])`,
the template should:
1. Import `extract_dbt_model_lineage` and `UUID`
2. Call `extract_dbt_model_lineage(project_dir, parent_run_id, ...)` 
3. Emit each returned event via `lineage.emit_event(event)`

**File:** Same as Track 2 — `plugin.py:1100-1363` template
**Change:** Add lineage extraction block (conditional on `lineage_enabled`)

---

## Track 4: DNS Resolution (Cascading from Track 1)

This is the same failure as Track 1. The DNS error for `floe-platform-polaris:8181` is
the symptom of the import-time connection attempt. Fixing Track 1 eliminates this.

---

## Summary: Fix Plan

| Track | Root Cause | Fix | Files |
|-------|-----------|-----|-------|
| 1 | `try_create_iceberg_resources` re-raises despite docstring | Remove `raise` | `iceberg.py` |
| 2 | Generated template doesn't emit lineage events | Add lineage emission to template | `plugin.py` |
| 3 | Generated template doesn't extract per-model lineage | Add extraction to template | `plugin.py` |
| 4 | Cascading from Track 1 | Fixed by Track 1 | — |

**Key insight:** Tracks 2 and 3 are the **same underlying bug** — the code generator
produces asset functions that wire the lineage resource but never use it. The dynamic
asset creation code in `plugin.py:530-620` has all the lineage logic; it just needs to
be replicated in the template.

---

## References

- `plugin.py:1100-1363` — Template generator (`generate_entry_point_code`)
- `plugin.py:530-620` — Dynamic asset creation with full lineage (reference implementation)
- `lineage_extraction.py:176-275` — Per-model extraction with parentRun facets
- `facets.py:162-263` — TraceCorrelation and ParentRun facet builders
- `iceberg.py:161-207` — `try_create_iceberg_resources` with contradictory raise
- `demo/customer-360/definitions.py` — Generated template (no lineage emission)
