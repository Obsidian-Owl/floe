# Assumptions: E2E Production Fixes

## A1: Committed manifests are sufficient for Dagster code location loading
- **Type**: Technical (Type 2 -- reversible)
- **Status**: ACCEPTED (auto-resolved)
- **Basis**: `definitions.py` is already committed for the same reason (`.gitignore` comment line 117). Manifest files are generated artifacts but needed for Docker build context. Same pattern, same rationale.
- **Risk if wrong**: Stale manifests cause Dagster to load incorrect asset definitions. Mitigated by CI staleness check.

## A2: Marquez does not surface intermediate run states for rapid runs
- **Type**: Technical (Type 2 -- reversible)
- **Status**: ACCEPTED (auto-resolved)
- **Basis**: Per Marquez GitHub issue #2054, state updates are eventual. Back-to-back START/COMPLETE in <1ms likely results in only COMPLETED being observable via REST API. Test should check event existence, not intermediate state.
- **Risk if wrong**: If Marquez does surface START state, the current test assertion would pass -- no harm in making the test more robust.

## A3: requests 2.33.0 has no breaking changes for this project
- **Type**: Technical (Type 2 -- reversible)
- **Status**: ACCEPTED (auto-resolved)
- **Basis**: requests 2.33.0 changelog shows only: temp file fix, Python 3.9 drop (project uses 3.11), deprecated `get_connection` (not used in codebase). `uv lock --upgrade-package requests` will verify transitive compatibility.
- **Risk if wrong**: Lock resolution will fail, surfacing the issue immediately.

## A4: Option A (values-driven args) is the intended design for floe-jobs
- **Type**: Clarify (Type 2 -- reversible)
- **Status**: ACCEPTED (auto-resolved)
- **Basis**: `values-test.yaml` was clearly written expecting `profilesDir` and `projectDir` to be consumed by templates. The existence of these keys with no template consumption is a bug, not a design choice.
- **Risk if wrong**: Easy to revert to passthrough args pattern.

## A5: 600s is sufficient for pre-upgrade hook in Kind/CI
- **Type**: Technical (Type 2 -- reversible)
- **Status**: ACCEPTED (auto-resolved)
- **Basis**: The kubectl delete command completes in <5s when running. The 300s deadline only fails due to scheduling + image pull latency. 600s provides 5 extra minutes for image pull.
- **Risk if wrong**: Can be further increased in values-test.yaml without template changes.
