# Assumptions: e2e-test-isolation-fixes

## A1: Profile isolation is the root cause of 47 failures

- **Type**: Technical (Type 2)
- **Status**: ACCEPTED
- **Evidence**: Test log shows `--profiles-dir demo/customer-360` (fallback) for failing tests. `test_profile_isolation.py` has explicit `shutil.rmtree()` on real source tree paths. Session-scoped fixture yields dict with correct paths but files are absent.
- **Resolution**: Code inspection confirms the cascade chain.

## A2: NoOpLineageResource is the sole cause of the openlineage test failure

- **Type**: Technical (Type 2)
- **Status**: ACCEPTED
- **Evidence**: `compiled_artifacts.json` has `lineage: true` + `lineage_endpoint` configured. Template generates `NoOpLineageResource()` unconditionally. NoOp discards all events. Marquez shows 966 runs with zero parentRun facets.
- **Resolution**: Code inspection confirms the template hardcodes NoOp at line 1334.

## A3: LineageResource module-level creation is safe

- **Type**: Technical (Type 2)
- **Status**: ACCEPTED
- **Evidence**: `LineageResource.__init__()` starts a daemon thread (line 67). Daemon threads are cleaned up at process exit. The resource persists for the Dagster process lifetime, same as the module-level `NoOpLineageResource` pattern already used.
- **Resolution**: Daemon thread flag ensures cleanup. No resource leak risk.

## A4: create_emitter works with transport_config from observability settings

- **Type**: Technical (Type 2)
- **Status**: ACCEPTED
- **Evidence**: `create_emitter()` accepts `transport_config: dict` and `default_namespace: str`. The observability section provides `lineage_transport` ("http") and `lineage_endpoint` (URL). The transport_config dict format `{"type": "http", "url": "<endpoint>"}` matches what the emitter factory expects.
- **Resolution**: Verified by reading `floe_core/lineage/emitter.py` factory interface.
