# Plan: OpenLineage Facet Key + Template Lineage

## Tasks

### Task 1: Change facet key from "parentRun" to "parent"
Update `lineage_extraction.py:240` and all unit test assertions.

**File change map:**
| File | Change |
|---|---|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/lineage_extraction.py` | `"parentRun"` → `"parent"` in LineageRun facets dict |
| `plugins/floe-orchestrator-dagster/tests/unit/test_lineage_extraction.py` | Update all `"parentRun"` assertions to `"parent"` |

### Task 2: Add lineage emission to template-generated asset function
Modify the template in `plugin.py:1317-1363` to:
1. Add `lineage: LineageResource` to function params (conditional on lineage_enabled)
2. Add `from floe_orchestrator_dagster.resources.lineage import LineageResource` import (conditional)
3. Add `emit_start` call before `dbt.cli(["build"])`
4. Add `emit_complete` call after successful build
5. Wrap lineage calls in try/except (non-fatal, like the dynamic path)

**File change map:**
| File | Change |
|---|---|
| `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` | Template section: add conditional lineage params, imports, emit calls |

**Template structure (when lineage enabled):**
```python
def {safe_name}_dbt_assets(context, dbt: DbtCliResource, lineage: LineageResource):
    run_id = lineage.emit_start("{safe_name}_dbt_assets")
    yield from dbt.cli(["build"], context=context).stream()
    lineage.emit_complete(run_id, "{safe_name}_dbt_assets")
```

### Task 3: Regenerate demo definitions
Run `floe compile --generate-definitions` for all demo products to update checked-in `definitions.py` files.

**File change map:**
| File | Change |
|---|---|
| `demo/customer-360/definitions.py` | Regenerated with lineage calls |
| `demo/supply-chain/definitions.py` | Regenerated with lineage calls |
| `demo/financial-risk/definitions.py` | Regenerated with lineage calls |
