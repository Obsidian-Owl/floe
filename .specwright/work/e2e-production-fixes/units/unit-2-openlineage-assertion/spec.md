# Spec: OpenLineage Test Assertion Fix

## Acceptance Criteria

### AC-1: Test queries Marquez events API for event types
- The `has_start` check at line 1012 is replaced with a Marquez events API query
- `GET /api/v1/events/lineage?limit=100` is called
- Event types are extracted from the `eventType` field
- `has_start = "START" in event_types`
- `has_complete = "COMPLETE" in event_types`

### AC-2: Fallback to run-state check if events API unavailable
- If the events endpoint returns non-200, the test falls back to the existing `run_states` check
- This ensures backward compatibility with older Marquez versions

### AC-3: Assertion is at least as strong as the original
- The new check proves the platform *sent* a START event (not just that a run exists with a state)
- The error message is updated to reference the events API and include diagnostic info (event types found)
- No assertion is removed or weakened — this is a stronger check

### AC-4: `test_openlineage_four_emission_points` passes
- After `seed_observability` runs (compilation + Dagster run), the test finds both START and COMPLETE event types
- All sub-assertions pass: `has_dbt_model_job`, `has_pipeline_job`, `has_start`, `has_complete`, `duration_checked`, `parent_facet_found`

## Error Cases
- Marquez events API returns 404 → graceful fallback to run-state check
- Marquez events API returns empty list → test fails with clear message about no events received
- Events contain only COMPLETE (no START) → test fails with message listing event types found
