# Decisions: E2E Lineage Template Fix

## D1: Replicate dynamic path pattern rather than abstracting

**Choice:** Copy the lineage emission pattern from `plugin.py:530-620` into the template, rather than extracting a shared helper function.

**Why:** The template generates standalone `definitions.py` files that must work independently. A shared helper would add a runtime dependency and coupling. The pattern is simple (emit_start/complete/fail + extract) and the template is code-generated, so the "duplication" is between a runtime function and a code-generator template — not actual code duplication.

**Rule:** DISAMBIGUATION — simplest approach, lowest coupling.

## D2: Inline imports in generated asset function body

**Choice:** Use inline `import logging` and `from uuid import UUID, uuid4` inside the generated asset function body, rather than adding them to the module-level imports.

**Why:** Keeps the lineage-specific imports contained within the lineage-conditional code block. The module-level imports (`TraceCorrelationFacetBuilder`, `extract_dbt_model_lineage`) are added to `thirdparty_imports` when `lineage_enabled`. The stdlib imports (`logging`, `uuid`) are inlined to avoid polluting the non-lineage template.

**Rule:** DISAMBIGUATION — minimal change to existing template structure.

## D3: Fix iceberg raise as separate commit from template changes

**Choice:** Two separate fixes: (1) remove raise in iceberg.py, (2) add lineage to template.

**Why:** Different root causes, different blast radii. Clean git history.

**Rule:** Atomic commits per convention.
