# Plan: Loud Failures (Unit 6)

## Task Breakdown

### Task 1: Fix ingestion factory exception swallowing (AC-4)

Change `try_create_ingestion_resources()` to re-raise exceptions when ingestion IS configured. Add structured log message before re-raise.

**File change map:**
- MODIFY `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py` (change `except Exception: return {}` to `except Exception: raise`)

**Acceptance criteria:** AC-4

### Task 2: Standardize log levels and message format (AC-2, AC-3)

Update all 4 `try_create_*` functions to use WARNING (not DEBUG) for unconfigured plugins and consistent structured log keys.

**File change map:**
- MODIFY `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py`
- MODIFY `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py`
- MODIFY `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py`
- MODIFY `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py`

**Acceptance criteria:** AC-2, AC-3

### Task 3: Unit tests for standardized factory semantics (AC-1)

Write/update unit tests for all 4 factories asserting consistent exception propagation, log levels, and message format.

**File change map:**
- MODIFY or CREATE `plugins/floe-orchestrator-dagster/tests/unit/test_resource_factories.py`

**Acceptance criteria:** AC-1

### Task 4: Contract test for factory semantics (AC-6)

Create parametrized contract test at root level enforcing the factory contract for all 4 factories.

**File change map:**
- CREATE `tests/contract/test_resource_factory_semantics.py`

**Acceptance criteria:** AC-6

### Task 5: Integration test — pipeline fails on unreachable Iceberg (AC-5)

Integration test that creates `Definitions` via `load_product_definitions()` with Iceberg configured but Polaris unreachable. Assert resource initialization raises.

**File change map:**
- CREATE `plugins/floe-orchestrator-dagster/tests/integration/test_loud_failure_integration.py`

**Acceptance criteria:** AC-5

## Task Dependencies

```
Task 1 (fix ingestion) ──┐
                          ├──► Task 3 (unit tests)
Task 2 (standardize logs) ┘
                          ├──► Task 4 (contract test)
                          └──► Task 5 (integration test)
```

Tasks 1 and 2 are independent. Tasks 3-5 depend on both.

## As-Built Notes

### Implementation Decisions

- **Lineage factory** already had correct re-raise behavior via direct call to `create_lineage_resource()`, but lacked a try/except wrapper for consistent `lineage_creation_failed` logging. Added try/except + raise around the call.
- **Lineage factory** uses `importlib.import_module` for module-level `get_registry` binding (to avoid AST import nodes per AC-13 constraint). Tests must patch at both `floe_core.plugin_registry.get_registry` AND `floe_orchestrator_dagster.resources.lineage.get_registry`.
- **Unit tests** (Task 3) placed in `plugins/floe-orchestrator-dagster/tests/unit/test_resource_factories.py` — parametrized across all 4 factories.
- **Contract tests** (Task 4) placed at `tests/contract/test_resource_factory_semantics.py` — root level because they import from multiple packages.
- **Integration test** (Task 5) uses real `compiled_artifacts.json` from `demo/customer-360/` with catalog/storage overwritten to unreachable endpoints.

### Actual File Paths

- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py` — exception swallowing fixed, log standardized
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/iceberg.py` — log standardized
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/semantic.py` — log standardized
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/lineage.py` — log + try/except added
- `plugins/floe-orchestrator-dagster/tests/unit/test_resource_factories.py` — 16 parametrized unit tests (NEW)
- `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_resources.py` — updated old swallow test to re-raise test
- `tests/contract/test_resource_factory_semantics.py` — 16 parametrized contract tests (NEW)
- `plugins/floe-orchestrator-dagster/tests/integration/test_loud_failure_integration.py` — 2 integration tests (NEW)
