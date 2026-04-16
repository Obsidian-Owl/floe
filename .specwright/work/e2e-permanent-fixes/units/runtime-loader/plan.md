# Plan: Runtime Loader (Option B)

## Task Breakdown

### Task 1: Extract Iceberg export function (AC-4)

Extract `_export_dbt_to_iceberg()` from `demo/customer-360/definitions.py` into a new module. Parameterize with `product_name`, `project_dir`, and `artifacts` (parsed CompiledArtifacts object).

**File change map:**
- CREATE `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/__init__.py`
- CREATE `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py`
- CREATE `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py`

**Acceptance criteria:** AC-4

### Task 2: Implement runtime loader (AC-1, AC-2, AC-3, AC-5)

Create `loader.py` with `load_product_definitions()` that:
- Reads and validates `compiled_artifacts.json`
- Creates `@dbt_assets` function with lineage hooks (emit_start/fail/complete) and Iceberg export
- Wraps resource factories in `ResourceDefinition` generators
- Returns `Definitions` with all resources

**File change map:**
- CREATE `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py`
- CREATE `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py`

**Acceptance criteria:** AC-1, AC-2, AC-3, AC-5

### Task 3: Simplify demo definitions.py (AC-6)

Replace the 3 demo product `definitions.py` files with the thin loader pattern.

**File change map:**
- MODIFY `demo/customer-360/definitions.py` (187 → ~15 lines)
- MODIFY `demo/iot-telemetry/definitions.py` (187 → ~15 lines)
- MODIFY `demo/financial-risk/definitions.py` (187 → ~15 lines)

**Acceptance criteria:** AC-6

### Task 4: Update code generator and tests (AC-7, AC-8)

Simplify `generate_entry_point_code()` to emit the thin loader pattern. Update existing unit tests.

**File change map:**
- MODIFY `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` (template section, lines 1100-1406)
- MODIFY `plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_lineage.py`

**Acceptance criteria:** AC-7, AC-8

## Task Dependencies

```
Task 1 (extract export) ──┐
                           ├──► Task 3 (simplify definitions.py)
Task 2 (loader module)  ──┘
                           └──► Task 4 (update generator + tests)
```

Tasks 1 and 2 are independent and can be done in parallel. Tasks 3 and 4 depend on both. Tasks 5 and 6 depend on tasks 3 and 4.

### Task 5: Integration test — loader produces materializable Definitions (NEW)

Import thin `definitions.py` from `demo/customer-360/` with real `compiled_artifacts.json` and `target/manifest.json`. Assert `defs` is valid `Definitions` with expected resources and assets. Assert no network connections during import (Polaris/MinIO unreachable).

**File change map:**
- CREATE `plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py`

**Acceptance criteria:** AC-1, AC-2

### Task 6: E2E test — thin definitions.py works in deployed Dagster (NEW)

After demo pipeline deploys to Kind with thin `definitions.py`, verify Dagster discovers code location. Verify `dagster asset list` returns expected assets.

**File change map:**
- CREATE or MODIFY `tests/e2e/test_runtime_loader_e2e.py`

**Acceptance criteria:** AC-1, AC-6

## Code Budget (structure only, no implementations)

### loader.py signature
```python
def load_product_definitions(
    product_name: str,
    project_dir: Path,
) -> Definitions:
```

### export/iceberg.py signature
```python
def export_dbt_to_iceberg(
    context: Any,
    product_name: str,
    project_dir: Path,
    artifacts: CompiledArtifacts,
) -> None:
```

### Simplified definitions.py structure
```python
from pathlib import Path
from floe_orchestrator_dagster.loader import load_product_definitions

PROJECT_DIR = Path(__file__).parent
defs = load_product_definitions(product_name="customer-360", project_dir=PROJECT_DIR)
```

## As-Built Notes

### Deviations from plan
- **Task 4 target file**: Plan referenced `test_code_generator_lineage.py` but actual file was `test_code_generator_iceberg.py`. Same test file, updated in place.
- **DbtProject not used in loader**: `DbtProject` was omitted from loader because test fixtures don't include `dbt_project.yml`. The `@dbt_assets` decorator receives `manifest=manifest_path` directly.
- **DbtCliResource wrapped in ResourceDefinition**: To satisfy AC-2 (no eager connections), `DbtCliResource` is wrapped in a `ResourceDefinition` generator. `DbtCliResource` validates `dbt_project.yml` at instantiation, so wrapping defers this to Dagster startup.
- **Iceberg resource wrapped in ResourceDefinition generator**: Rather than calling `try_create_iceberg_resources()` eagerly, the loader wraps it in a `ResourceDefinition` generator conditional on `_plugins.catalog` being set.

### Actual file paths
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/loader.py` (143 lines)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/__init__.py`
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/export/iceberg.py` (129 lines)
- `plugins/floe-orchestrator-dagster/tests/unit/test_loader.py` (727 lines, 21 tests)
- `plugins/floe-orchestrator-dagster/tests/unit/test_export_iceberg.py` (14 tests)
- `plugins/floe-orchestrator-dagster/tests/unit/test_code_generator_iceberg.py` (548 lines, 88 tests)
- `plugins/floe-orchestrator-dagster/tests/integration/test_loader_integration.py` (6 tests)
- `tests/e2e/test_runtime_loader_e2e.py` (3 tests)
- `demo/customer-360/definitions.py` (17 lines)
- `demo/financial-risk/definitions.py` (17 lines)
- `demo/iot-telemetry/definitions.py` (17 lines)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` (generate_entry_point_code simplified)

### Test coverage
- 132 total tests across unit (123), integration (6), E2E (3)
- Net code reduction: -483 lines from demo files, -102 lines from plugin.py generator
