# Gate: Tests — WU-3 Evidence

**Work Unit**: wu-3-dagster-sdk-migration (Dagster SDK Migration)
**Gate**: gate-tests
**Status**: WARN
**Timestamp**: 2026-02-13T17:00:00Z

## Scope

Files audited:

- `testing/tests/unit/test_dagster_migration.py` (14 tests, NEW)
- `tests/e2e/test_compile_deploy_materialize_e2e.py` (GraphQL query migration)
- `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py` (asset_selection addition)
- `plugins/floe-orchestrator-dagster/tests/unit/test_health_sensor.py` (existing sensor tests)

## Summary

- **BLOCK**: 2
- **WARN**: 5
- **INFO**: 4

---

## BLOCK Findings

### B-001: `is not None` on values that can never be None (test_dagster_migration.py:163,170,177)

Three tests in `TestDagsterImportCompatibility` use `assert X is not None` on class objects retrieved via import. A successful import statement guarantees the name is bound; the assertion is trivially true and proves nothing about compatibility.

```python
# Line 163 — test_configurable_io_manager_available
from dagster import ConfigurableIOManager
assert ConfigurableIOManager is not None  # Always true after import

# Line 170 — test_configurable_resource_available
from dagster import ConfigurableResource
assert ConfigurableResource is not None  # Always true after import

# Line 177 — test_dagster_dlt_translator_available
from dagster_dlt import DagsterDltTranslator
assert DagsterDltTranslator is not None  # Always true after import
```

**Required fix**: Replace with meaningful assertions that verify the class is usable, e.g. `assert issubclass(ConfigurableIOManager, IOManager)` or `assert callable(ConfigurableResource)` or verify an expected attribute exists on the class. At minimum `assert inspect.isclass(X)` proves the symbol is a class, not an arbitrary re-export.

**Rule reference**: `.claude/rules/code-quality.md` "Identity Check Always True/False" (CRITICAL), `.claude/rules/testing-standards.md` Assertion Strength Hierarchy ("Forbidden: `assert value is not None`").

### B-002: No test validates sensor `asset_selection` parameter (test_health_sensor.py)

The sensor definition was modified to add `asset_selection="*"` (sensors.py:132), which is a key WU-3 acceptance criterion (WU3-AC5). However, the existing sensor test file `test_health_sensor.py` has zero assertions on the `asset_selection` attribute. The `TestSensorDefinition` class (line 185) checks `name` but not `asset_selection`.

The migration test `test_sensor_has_explicit_target` (test_dagster_migration.py:96) only does a substring search on the source file (`"asset_selection=" in content`). This is a string-level check, not a runtime verification.

**Required fix**: Add a test in `test_health_sensor.py` (or `test_dagster_migration.py`) that imports `health_check_sensor` and asserts on the runtime `asset_selection` property, e.g.:

```python
@pytest.mark.requirement("WU3-AC5")
def test_sensor_has_asset_selection(self) -> None:
    """Verify sensor targets all assets via asset_selection."""
    from dagster import AssetSelection
    from floe_orchestrator_dagster.sensors import health_check_sensor
    assert health_check_sensor.asset_selection is not None
    assert health_check_sensor.asset_selection == AssetSelection.all()
```

**Rule reference**: `.claude/rules/testing-standards.md` "Side-Effect Verification" principle applied to configuration: runtime verification over string matching.

---

## WARN Findings

### W-001: Structural tests rely on substring search over file content (test_dagster_migration.py:41-89)

All four `TestGraphQLQueryCompatibility` tests read the E2E test file as a string and check for substring presence/absence. This works for the current file but is fragile:

- A comment containing `repositoryLocationsOrError` would cause a false failure.
- Renaming the file or moving the query to a constant breaks the path reference.
- No AST-level verification that the string actually appears inside a GraphQL query literal.

**Recommendation**: Accept for now (file is controlled), but consider AST-based verification or extracting GraphQL queries to named constants that can be imported.

### W-002: `test_sensor_definition_importable` has weak assertion (test_dagster_migration.py:116)

```python
assert health_check_sensor is not None  # Line 116
assert health_check_sensor.name == "health_check_sensor"  # Line 117
```

The first assertion is trivially true (same B-001 pattern). The second is meaningful but the test could additionally verify sensor type, description, or minimum_interval_seconds.

**Recommendation**: Remove `is not None` assertion, add `assert isinstance(health_check_sensor, SensorDefinition)`.

### W-003: Import-only tests have no behavioral assertions (test_dagster_migration.py:124-150)

Three tests (`test_core_dagster_imports`, `test_dagster_dbt_imports`, `test_dagster_dlt_imports`) import symbols and then do nothing with them. The `# noqa: F401` comments confirm these are import-only checks. While import verification is useful for SDK migration, these tests provide no behavioral signal beyond "the import did not raise ImportError."

**Recommendation**: Add at least one assertion per test that verifies the imported symbol is a class/function (e.g., `assert callable(sensor)`). This ensures the symbol is the expected type, not a re-exported alias or sentinel.

### W-004: `test_all_source_files_parse` uses magic number 13 (test_dagster_migration.py:194)

```python
assert len(py_files) >= 13
```

If source files are added or removed, this threshold becomes silently stale. The test will still pass with 14+ files but fail to detect if a file was accidentally deleted from 13 to 12.

**Recommendation**: Either pin the exact expected count and update it deliberately, or remove the count assertion entirely since the AST parse loop itself validates each file.

### W-005: Sensor test `test_sensor_has_minimum_interval` tests wrong thing (test_health_sensor.py:199)

Despite its name, this test does not actually verify the minimum interval configuration (60 seconds). It verifies that the implementation function is callable and returns a generator. The `minimum_interval_seconds=60` parameter on the `sensor()` decorator (sensors.py:131) is never asserted.

**Recommendation**: Assert the actual attribute: `assert health_check_sensor.minimum_interval_seconds == 60`.

---

## INFO Findings

### I-001: `TYPE_CHECKING` block is empty (test_health_sensor.py:25-26)

```python
if TYPE_CHECKING:
    pass
```

Empty `TYPE_CHECKING` block serves no purpose. Likely a leftover from a removed import.

### I-002: Repeated file reads in TestGraphQLQueryCompatibility (test_dagster_migration.py)

Each of the four tests in this class reads the same file via `E2E_DEPLOY_TEST.read_text()`. This could be a class-level fixture or `setUpClass` to avoid redundant I/O.

### I-003: No `__init__.py` exclusion comment in AST scan (test_dagster_migration.py:192)

The test excludes `__pycache__` but does not explicitly address `__init__.py` files. These files are included in the count and parse check, which is correct behavior, but the intent could be documented.

### I-004: E2E test file is well-structured with strong assertions

The `test_compile_deploy_materialize_e2e.py` file uses correct `repositoriesOrError` and `RepositoryConnection` patterns (confirming WU3-AC4 migration). GraphQL queries are inline and well-commented. Assertions are specific (exact string matching on status, field presence checks, content validation loops).

---

## Coverage Map

| Acceptance Criterion | Tests | Coverage | Notes |
|---------------------|-------|----------|-------|
| WU3-AC3 (import compat) | 5 tests | Adequate | 3 import-only, 1 module import, 1 AST parse |
| WU3-AC4 (GraphQL migration) | 4 tests | Good | Positive + negative for both query and type |
| WU3-AC5 (sensor target) | 2 tests | Weak | String search only; no runtime assertion on asset_selection |
| WU3-AC7 (ConfigurableIOManager) | 1 test | Weak | `is not None` on import (trivially true) |
| WU3-AC8 (ConfigurableResource) | 1 test | Weak | `is not None` on import (trivially true) |
| WU3-AC9 (DagsterDltTranslator) | 1 test | Weak | `is not None` on import (trivially true) |

## Requirement Markers Audit

All 14 tests in `test_dagster_migration.py` have `@pytest.mark.requirement()` markers. **PASS**.

## Docstring Audit

All 14 tests in `test_dagster_migration.py` have docstrings. **PASS**.

## Type Hints Audit

All test methods return `-> None`. Module uses `from __future__ import annotations`. **PASS**.

## Verdict

**WARN** -- Two BLOCK-level findings must be resolved before the work unit can pass the gate:

1. Replace trivially-true `is not None` assertions with meaningful checks (B-001).
2. Add runtime assertion for `asset_selection` on the sensor definition (B-002).

Once B-001 and B-002 are fixed, verdict upgrades to **PASS** (WARN findings are acceptable).
