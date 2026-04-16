# Context: Unit 2 — OpenLineage Test Assertion Fix

## Problem
The `test_openlineage_four_emission_points` test checks Marquez run states for `RUNNING/NEW/START` (line 1012). Per-model emission pairs are back-to-back synchronous, so Marquez may only surface the terminal `COMPLETED` state — the intermediate START state is never observable via the runs API.

## Key Files
- `tests/e2e/test_observability.py` lines 1011-1022: the `has_start`/`has_complete` assertion block
- `tests/e2e/conftest.py` line 932: `seed_observability` fixture
- `packages/floe-core/src/floe_core/compilation/stages.py` lines 562-586: per-model emission loop

## Design Decision
Replace run-state check with Marquez events API query (D2). `/api/v1/events/lineage` returns individual OpenLineage events with `eventType` field. This is a stronger assertion — proves the event was received, not just that a run exists.

## Marquez API
- Events endpoint: `GET /api/v1/events/lineage?limit=100`
- Response: `{"events": [{"eventType": "START", ...}, {"eventType": "COMPLETE", ...}]}`
- Fallback: If events API unavailable (404), fall back to existing run-state check
