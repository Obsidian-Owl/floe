# Decisions

## D1: Fix F1 by removing assetSelection (not by adding seed selection)
- **Type**: DISAMBIGUATION (multiple valid approaches)
- **Rule applied**: Simplest correct solution
- **Rationale**: Removing `assetSelection` runs the full `dbt build` which handles
  seed→model ordering internally. Adding seed selection would be fragile (seed names
  change) and wouldn't match production behavior.

## D2: Defer F4 (OpenLineage START) to backlog
- **Type**: DISAMBIGUATION (fix scope)
- **Rule applied**: Architectural scope (>3 files, crosses boundaries)
- **Rationale**: Fixing OpenLineage emission requires changes across orchestrator plugin,
  lineage plugin, demo definitions, and Helm chart config. This is a design-level task.
  The test correctly surfaces the gap — do not weaken it.

## D3: Use JSON parsing pattern for F5 (not JSONPath)
- **Type**: DISAMBIGUATION (implementation approach)
- **Rule applied**: Follow existing codebase pattern
- **Rationale**: Two other test files already use JSON parsing with Succeeded filtering.
  Consistency over novelty.

## D4: Fix conftest.py seed_observability callsite too
- **Type**: DISAMBIGUATION (scope of F1 fix)
- **Rule applied**: Fix all instances, not just the first
- **Rationale**: Critic correctly identified conftest.py:797 has the identical
  `assetSelection` pattern. Must be fixed alongside the test callsite. This is
  best-effort fixture so it fails silently today.

## D5: F4 test remains failing after this work unit
- **Type**: DISAMBIGUATION (expected test outcome)
- **Rule applied**: Tests FAIL, never skip — do not weaken assertions
- **Rationale**: The OpenLineage START emission gap is real. The test will continue
  to fail until the production code is fixed. This is the correct behavior — the test
  surfaces a genuine gap. Log as backlog item with clear description.

## D6: Audit all package lockfiles (not just floe-core)
- **Type**: DISAMBIGUATION (scope)
- **Rule applied**: Fix the class of problem, not just the instance
- **Rationale**: If floe-core has a stale lockfile, other packages might too. Quick to check.
