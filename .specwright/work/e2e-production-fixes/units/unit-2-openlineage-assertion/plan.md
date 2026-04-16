# Plan: OpenLineage Test Assertion Fix

## Tasks

### Task 1: Replace has_start/has_complete with events API query
- File: `tests/e2e/test_observability.py` lines 1011-1022
- Replace the `run_states` check with events API query
- Add fallback for events API unavailability
- Update error message with diagnostic info

## File Change Map
| File | Change |
|------|--------|
| `tests/e2e/test_observability.py` | Replace lines 1011-1022 with events API query + fallback |

## Dependencies
- Depends on Marquez being accessible at localhost:5100 (same as current test)
- The per-model emission code from the branch must be merged (already on `feat/per-model-lineage-emission`)
