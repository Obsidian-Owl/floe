# WU-3 Wiring Analysis: Dagster SDK Migration

**Date**: 2026-02-13
**Status**: PASS (no blockers, 3 warnings, 1 info)

## Summary

Wiring analysis of 3 changed files in WU-3 (Dagster SDK Migration):
1. `testing/tests/unit/test_dagster_migration.py` (NEW — 14 structural validation tests)
2. `tests/e2e/test_compile_deploy_materialize_e2e.py` (MODIFIED — GraphQL query update)
3. `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py` (MODIFIED — added asset_selection)

**Result**: All structural checks pass. Tests are properly discoverable by pytest, paths resolve correctly, no architectural violations detected, no circular dependencies introduced.

---

## Findings

### PASS: Test Discovery

**File**: `testing/tests/unit/test_dagster_migration.py`

- pytest auto-discovery works: test file matches `test_*.py` pattern
- All 14 tests execute successfully when run with `.venv/bin/python -m pytest`
- Test placement correct: unit tests in `testing/tests/unit/` (cross-cutting structural validation)
- No `__init__.py` present in test directory (compliant with `--import-mode=importlib`)

**Verification command**:
```bash
.venv/bin/python -m pytest testing/tests/unit/test_dagster_migration.py -v
# Result: 14 passed, 1 warning in 1.56s
```

---

### PASS: Path Resolution

**File**: `testing/tests/unit/test_dagster_migration.py:20-38`

All hardcoded paths resolve correctly from test location:

```python
REPO_ROOT = Path(__file__).resolve().parents[3]  # testing/tests/unit → repo root
```

**Path validation results**:

| Constant | Resolved Path | Exists? | Line Ref |
|----------|---------------|---------|----------|
| `E2E_DEPLOY_TEST` | `tests/e2e/test_compile_deploy_materialize_e2e.py` | ✅ YES | 21-23 |
| `SENSOR_MODULE` | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py` | ✅ YES | 24-31 |
| `DAGSTER_SRC_DIR` | `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/` | ✅ YES | 32-38 |

---

### PASS: Source File Count

**File**: `testing/tests/unit/test_dagster_migration.py:194`

Test expects `>= 13` source files in dagster plugin. Actual count verified:

```bash
find plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster -name "*.py" -type f ! -path "*__pycache__*" | wc -l
# Result: 13
```

**Files enumerated**:
1. `__init__.py`
2. `plugin.py`
3. `io_manager.py`
4. `sensors.py`
5. `tracing.py`
6. `resources/__init__.py`
7. `resources/dbt_resource.py`
8. `resources/iceberg.py`
9. `resources/ingestion.py`
10. `resources/semantic.py`
11. `assets/__init__.py`
12. `assets/ingestion.py`
13. `assets/semantic_sync.py`

Test assertion is correct: `assert len(py_files) >= 13` matches actual count.

---

### PASS: Architecture Compliance

**No component ownership violations detected**:

- ✅ Test file in `testing/tests/unit/` correctly imports from `plugins/floe-orchestrator-dagster` (root → plugin direction is allowed)
- ✅ Dagster plugin does NOT import from `testing/` or `tests/` (verified via grep, no reverse dependency)
- ✅ E2E test file correctly imports from `floe_core` and `floe_orchestrator_dagster` (multi-package test belongs in root `tests/`)
- ✅ Sensor module only imports from `dagster` SDK (no cross-package imports)

**Verification commands**:
```bash
grep -r "from testing" plugins/floe-orchestrator-dagster/src/
# Result: (no output) — no reverse dependency

grep -r "from tests" plugins/floe-orchestrator-dagster/src/
# Result: (no output) — no reverse dependency
```

---

### PASS: No Circular Dependencies

**Import graph analysis**:

```
testing/tests/unit/test_dagster_migration.py
  → floe_orchestrator_dagster (import inside test method)
  → dagster (import inside test method)

tests/e2e/test_compile_deploy_materialize_e2e.py
  → floe_core.schemas.compiled_artifacts
  → (no floe_orchestrator_dagster imports — E2E test uses GraphQL API)

plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py
  → dagster SDK only
```

**No circular dependency**: Test imports plugin for validation, plugin does NOT import test code. Directed acyclic graph confirmed.

---

### PASS: Import Consistency

**All imports from changed files are valid**:

1. **test_dagster_migration.py** imports (inside test methods):
   - `from floe_orchestrator_dagster.sensors import health_check_sensor` ✅
   - `from dagster import AssetKey, AssetsDefinition, ConfigurableIOManager, ...` ✅
   - `from dagster_dbt import DbtCliResource, dbt_assets` ✅
   - `from dagster_dlt import DagsterDltTranslator` ✅

2. **test_compile_deploy_materialize_e2e.py**:
   - `from floe_core.schemas.compiled_artifacts import CompiledArtifacts` ✅
   - All imports unchanged from pre-WU3 state (only GraphQL query string changed)

3. **sensors.py**:
   - `from dagster import RunRequest, SensorEvaluationContext, sensor` ✅
   - No new imports added (only decorator parameter changed)

**Verification**: All tests pass with `.venv/bin/python` (dagster installed), indicating imports resolve correctly.

---

### PASS: Test Placement

**Placement validation**:

| Test File | Location | Tier | Correct? | Rationale |
|-----------|----------|------|----------|-----------|
| `test_dagster_migration.py` | `testing/tests/unit/` | Unit | ✅ YES | Cross-cutting structural validation, no real services needed, uses AST/file reads |
| `test_compile_deploy_materialize_e2e.py` | `tests/e2e/` | E2E | ✅ YES | Full workflow validation, imports from multiple packages, requires all services |

**Decision tree compliance**:
- `test_dagster_migration.py`: Does NOT import from multiple packages at module level (imports inside test methods) → Unit tier is correct
- Validates structural patterns (AST parsing, string search, import verification) → No external services needed → Unit tier is correct
- `test_compile_deploy_materialize_e2e.py`: Validates compile → deploy → materialize workflow → E2E tier is correct

---

### WARN-001: GraphQL Query Deprecation Not Validated Elsewhere

**File**: `tests/e2e/test_compile_deploy_materialize_e2e.py:180-196`

The E2E test was updated from `repositoryLocationsOrError` to `repositoriesOrError` (Dagster 2.x API migration). Structural validation in `test_dagster_migration.py:59-71` confirms the old query is absent.

**However**: No grep of the entire codebase to confirm the deprecated query pattern isn't used elsewhere.

**Risk**: Low (only 1 E2E test uses Dagster GraphQL currently)

**Recommended fix**:
```bash
grep -r "repositoryLocationsOrError\|RepositoryLocationConnection" tests/ --include="*.py"
# Should return empty
```

**Mitigation**: CI should add a banned-pattern check to pre-commit hooks.

---

### WARN-002: Sensor `asset_selection` Parameter Not Validated Runtime

**File**: `testing/tests/unit/test_dagster_migration.py:96-109`

The test `test_sensor_has_explicit_target` only performs a string search:
```python
has_asset_selection = "asset_selection=" in content
```

This validates the source code contains the parameter, but does NOT validate the runtime behavior (that `health_check_sensor` actually has `asset_selection="*"` in its definition).

**Risk**: Low (test `test_sensor_definition_importable` at line 112 successfully imports the sensor, proving no syntax errors)

**Recommended enhancement** (from gate-tests-wu3.md):
```python
def test_sensor_has_asset_selection_at_runtime():
    """Verify sensor definition has asset_selection at runtime."""
    from floe_orchestrator_dagster.sensors import health_check_sensor
    # Dagster 2.x sensor API: check targets_type attribute
    assert hasattr(health_check_sensor, 'asset_selection'), \
        "Sensor must have asset_selection defined"
```

**Mitigation**: Existing test `test_sensor_definition_importable` indirectly validates this (sensor imports successfully), but explicit runtime check would be stronger.

---

### WARN-003: Magic Number in Source File Count Assertion

**File**: `testing/tests/unit/test_dagster_migration.py:194`

```python
assert len(py_files) >= 13, (
    f"Expected at least 13 source files, found {len(py_files)}: "
    ...
)
```

The number `13` is hardcoded. If a new file is added to the dagster plugin, the test won't fail (it's `>=` not `==`). If a file is removed, it WILL fail.

**Risk**: Low (test intent is to detect import errors via AST parsing, not enforce exact file count)

**Mitigation**: Acceptable as-is. The `>=` operator means "we expect at least this many files from the SDK migration audit." Fewer files would indicate a structural problem (deleted modules).

**Alternative**: Use dynamic count:
```python
expected_min = 13  # As of 2026-02-13 WU-3 SDK migration
assert len(py_files) >= expected_min, f"Dagster plugin has {len(py_files)} files, expected >= {expected_min}"
```

---

### INFO-001: Test Imports Inside Methods (Intentional Design)

**File**: `testing/tests/unit/test_dagster_migration.py`

All `dagster` and `dagster-dbt`/`dagster-dlt` imports occur inside test methods (lines 114, 126, 142, 150, etc.), not at module level.

**Reason**: This is intentional. The tests validate import compatibility with Dagster 2.x SDK. If imports were at module level and Dagster 2.x broke an import, the entire test file would fail to collect. By importing inside test methods, each import failure is isolated to a single test case with a clear error message.

**Example**:
```python
def test_core_dagster_imports(self) -> None:
    """Verify core dagster imports used across source files."""
    from dagster import AssetKey, AssetsDefinition, ...  # Import inside test
```

This is a **valid pattern** for import compatibility testing (common in SDK migration suites). Not a wiring issue.

---

## Verification Checklist

| Check | Result | Evidence |
|-------|--------|----------|
| **Unused exports**: New test module properly discoverable by pytest? | ✅ PASS | `pytest --collect-only` finds 14 tests in `test_dagster_migration.py` |
| **Orphaned files**: Any removed files or broken references? | ✅ PASS | All 3 referenced paths exist and resolve correctly |
| **Architecture violations**: Component ownership respected? | ✅ PASS | No reverse dependencies (plugin → test), correct import directions |
| **Circular dependencies**: Any circular imports introduced? | ✅ PASS | Import graph is acyclic (test → plugin → dagster SDK) |
| **Import consistency**: All imports from changed files valid? | ✅ PASS | All imports resolve (verified by test execution success) |
| **Test placement**: Tests in correct tier directory? | ✅ PASS | `test_dagster_migration.py` in `unit/` (no services), E2E test in `e2e/` (full workflow) |

---

## Commands Run

### Verification Commands
```bash
# Test discovery
.venv/bin/python -m pytest testing/tests/unit/test_dagster_migration.py -v
# Result: 14 passed, 1 warning in 1.56s

# Path resolution
ls tests/e2e/test_compile_deploy_materialize_e2e.py
ls plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py
ls -d plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/
# All exist

# Source file count
find plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster -name "*.py" -type f ! -path "*__pycache__*" | wc -l
# Result: 13

# Architecture compliance
grep -r "from testing" plugins/floe-orchestrator-dagster/src/
grep -r "from tests" plugins/floe-orchestrator-dagster/src/
# Both return empty (no reverse dependencies)

# Deprecated API usage check
grep -r "repositoryLocationsOrError\|RepositoryLocationConnection" tests/ --include="*.py"
# Returns empty (old API not used)

# Asset selection usage
grep -r "asset_selection\s*=" plugins/floe-orchestrator-dagster/src/ --include="*.py" -A 1 -B 1
# Found in sensors.py line 132
```

---

## Conclusion

**WIRING STATUS**: ✅ PASS (no blockers)

All structural integrity checks pass:
- Test files are properly discoverable by pytest
- All hardcoded paths resolve correctly
- No architectural violations (no reverse dependencies)
- No circular imports introduced
- Import statements from changed files all resolve correctly
- Test placement follows tier organization (unit vs E2E)

**WARNINGS**: 3 warnings issued (all LOW risk, recommended enhancements documented)

**NEXT GATE**: `gate-tests-wu3.md` (test quality analysis)

---

## References

- **Test file**: `testing/tests/unit/test_dagster_migration.py` (207 lines, 14 tests)
- **Modified E2E test**: `tests/e2e/test_compile_deploy_materialize_e2e.py` (513 lines)
- **Modified sensor**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/sensors.py` (137 lines)
- **Spec**: `.specwright/work/e2e-platform-gaps/spec.md` (WU-3 acceptance criteria)
- **Test quality gate**: `.specwright/work/e2e-platform-gaps/evidence/gate-tests-wu3.md`
