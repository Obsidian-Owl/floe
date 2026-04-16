# Spec: OpenLineage Facet Key + Template Lineage

## Acceptance Criteria

### AC-1: Facet key changed to "parent"
`lineage_extraction.py:240` MUST use `"parent"` as the facet key in the `LineageRun` facets dict, conforming to the current OpenLineage ParentRunFacet specification.

**How to verify:** The string `"parentRun"` does not appear as a dict key in `lineage_extraction.py`. The key `"parent"` is used instead.

### AC-2: Unit tests updated for "parent" key
All unit tests in `test_lineage_extraction.py` that assert on the `"parentRun"` facet key MUST be updated to assert on `"parent"`.

**How to verify:** No test asserts `"parentRun" in ...`. All parent facet assertions use `"parent"`.

### AC-3: Template asset function declares lineage parameter
When lineage is enabled, the template-generated asset function MUST declare `lineage: LineageResource` as a parameter (in addition to `context` and `dbt`).

**How to verify:** Template generates `def {safe_name}_dbt_assets(context, dbt: DbtCliResource, lineage: LineageResource):` when lineage_enabled is True.

### AC-4: Template calls emit_start before dbt build
When lineage is enabled, the template-generated asset function MUST call `lineage.emit_start()` before `dbt.cli(["build"])`.

**How to verify:** Generated code contains `lineage.emit_start(` before `dbt.cli(`.

### AC-5: Template calls emit_complete after dbt build
When lineage is enabled, the template-generated asset function MUST call `lineage.emit_complete()` after successful `dbt.cli(["build"])`.

**How to verify:** Generated code contains `lineage.emit_complete(` after the dbt.cli call.

### AC-6: Template without lineage unchanged
When lineage is NOT enabled (lineage_enabled=False), the template MUST generate the same asset function as before — no lineage parameter, no emit calls.

**How to verify:** Template with lineage_enabled=False produces the original function signature `def {safe_name}_dbt_assets(context, dbt: DbtCliResource):`.

### AC-7: LineageResource import added to template
When lineage is enabled, the template MUST include the `LineageResource` import in the imports block.

**How to verify:** Generated code contains `from floe_orchestrator_dagster.resources.lineage import LineageResource` (or equivalent).
