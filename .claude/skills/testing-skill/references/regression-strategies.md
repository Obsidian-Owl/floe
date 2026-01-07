# Regression Testing Strategies Reference

## Overview

**Problem**: Changes in one component can break untouched components.

**Solution**: Layered regression strategy based on risk, impact, and speed.

**Goal**: <15 minutes merge validation for developer adoption.

---

## Layered Regression Strategy

### Three-Tier Approach

| Layer | Tests | Duration | Trigger | Failure Action |
|-------|-------|----------|---------|----------------|
| **Smoke** | 30-50 critical path tests | <5 min | Every commit | Block merge immediately |
| **Targeted** | 200-500 impacted tests | 8-15 min | Every PR | Block merge, investigate |
| **Full** | All tests (1000+) | >30 min | Nightly, pre-release | Alert, fix before release |

### Why Layered?

- **Fast feedback**: Smoke tests fail within minutes
- **Targeted coverage**: Run only what changed + critical paths
- **Resource efficient**: Don't run all tests on every commit
- **Developer experience**: <15min = acceptable wait time

---

## Smoke Tests

### Purpose

**Validate critical paths still work after changes.**

### Characteristics

- **Fast**: <5 minutes total
- **Critical**: Core functionality only
- **Stable**: No flaky tests allowed
- **Failing = blocking**: Stop everything if smoke fails

### Selection Criteria

| Include | Exclude |
|---------|---------|
| Core workflows (compile, deploy) | Edge cases |
| Critical integrations (catalog, storage) | Adapter-specific tests |
| Authentication/authorization | Performance tests |
| Data integrity | UI/cosmetic tests |

### Implementation

```python
import pytest

@pytest.mark.smoke
@pytest.mark.requirement("001-FR-001")
def test_compile_minimal_spec():
    """Smoke test: Basic compilation works."""
    spec = FloeSpec(name="test", version="1.0.0")
    artifacts = compile_spec(spec)
    assert artifacts.version == "2.0.0"

@pytest.mark.smoke
@pytest.mark.requirement("004-FR-001")
def test_create_catalog_smoke():
    """Smoke test: Catalog creation succeeds."""
    catalog = create_catalog(name="smoke_test", warehouse="warehouse")
    assert catalog is not None

@pytest.mark.smoke
@pytest.mark.requirement("008-FR-001")
def test_dbt_run_smoke():
    """Smoke test: dbt run executes."""
    result = run_dbt_models(["customers"])
    assert result.success is True
```

### Running Smoke Tests

```bash
# Run smoke tests only
uv run pytest -m smoke --maxfail=3 -x

# Parallel execution (faster)
uv run pytest -m smoke -n auto --maxfail=3

# Expected: <5 minutes, all pass
```

### CI Integration

```yaml
# GitHub Actions
jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Run smoke tests
        run: uv run pytest -m smoke --maxfail=3 -x
      - name: Block on failure
        if: failure()
        run: exit 1  # Fail the workflow
```

---

## Targeted Regression Tests

### Purpose

**Run tests for changed components + dependencies.**

### Impact Mapping

**Map changed files to impacted test suites**:

```python
IMPACT_MAP = {
    # Changes to schemas → run ALL contract tests
    "packages/floe-core/src/floe_core/schemas/": [
        "packages/*/tests/contract/"
    ],

    # Changes to base classes → run ALL integration tests
    "testing/base_classes/": [
        "packages/*/tests/integration/"
    ],

    # Changes to Helm charts → run ALL K8s tests
    "charts/": [
        "make test-k8s"
    ],

    # Changes to Makefile → validate test execution
    "Makefile": [
        "make test-all"
    ],

    # Package-specific changes
    "packages/floe-dagster/": [
        "packages/floe-dagster/tests/",
        "packages/floe-cube/tests/integration/",  # Depends on Dagster
    ],

    "packages/floe-dbt/": [
        "packages/floe-dbt/tests/",
        "packages/floe-dagster/tests/integration/",  # dbt integration
    ],
}
```

### Auto-Detection

```bash
#!/bin/bash
# testing/scripts/detect-impacted-tests.sh

# Get changed files
CHANGED_FILES=$(git diff --name-only main...HEAD)

# Detect impacted packages
IMPACTED_PACKAGES=$(echo "$CHANGED_FILES" | grep '^packages/' | cut -d'/' -f2 | sort -u)

# Run impacted tests
for package in $IMPACTED_PACKAGES; do
    echo "Running tests for $package..."
    uv run pytest packages/$package/tests/ -v
done

# Special cases
if echo "$CHANGED_FILES" | grep -q '^testing/base_classes/'; then
    echo "Base classes changed - running ALL integration tests"
    uv run pytest packages/*/tests/integration/ -v
fi

if echo "$CHANGED_FILES" | grep -q '^packages/floe-core/src/floe_core/schemas/'; then
    echo "Schemas changed - running ALL contract tests"
    uv run pytest packages/*/tests/contract/ -v
fi
```

### Running Targeted Tests

```bash
# Detect and run impacted tests
./testing/scripts/detect-impacted-tests.sh

# Or manually
uv run pytest packages/floe-core/tests/ packages/floe-dagster/tests/ -v

# Expected: 8-15 minutes
```

---

## Full Regression Suite

### Purpose

**Comprehensive validation before releases.**

### When to Run

- **Nightly**: Catch integration issues early
- **Pre-release**: Gate for tagging releases
- **Post-deployment**: Validate production
- **Manual**: On-demand full validation

### Execution

```bash
# Run all test tiers
make test-all

# Breakdown:
# - Unit tests: ~5 min
# - Contract tests: ~2 min
# - Integration tests (Docker): ~10 min
# - Integration tests (K8s): ~12 min
# - E2E tests: ~15 min
# Total: ~30-40 min
```

### CI Integration

```yaml
# GitHub Actions
name: Full Regression

on:
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2 AM
  workflow_dispatch:     # Manual trigger

jobs:
  full-regression:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - name: Run full regression
        run: make test-all
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Contract Tests (Critical)

### Purpose

**Validate cross-package compatibility.**

### BLOCKING Status

**If contract tests fail, DO NOT merge.** Contract test failures indicate breaking changes.

### What Contract Tests Validate

1. **Schema stability**: CompiledArtifacts schema didn't break
2. **Backward compatibility**: Old versions can read new schemas
3. **Type safety**: Pydantic models validate correctly
4. **JSON Schema export**: Schema generation works

### Example

```python
@pytest.mark.contract
@pytest.mark.requirement("001-FR-010")
def test_compiled_artifacts_backward_compatible():
    """Verify CompiledArtifacts schema is backward compatible."""
    from floe_core.schemas import CompiledArtifacts

    # Load baseline schema (v2.0.0)
    baseline_schema = load_baseline_schema("compiled_artifacts_v2.0.0.json")

    # Generate current schema
    current_schema = CompiledArtifacts.model_json_schema()

    # Validate backward compatibility
    assert current_schema["version"] >= baseline_schema["version"]

    # All baseline fields still present
    for field in baseline_schema["properties"]:
        assert field in current_schema["properties"], \
            f"Field '{field}' removed (breaking change)"

@pytest.mark.contract
@pytest.mark.requirement("001-FR-011")
def test_dagster_loads_compiled_artifacts():
    """Verify floe-dagster can load CompiledArtifacts."""
    from floe_core.schemas import CompiledArtifacts
    from floe_dagster.loaders import load_artifacts_from_json

    # floe-core generates
    artifacts = CompiledArtifacts(...)
    json_str = artifacts.model_dump_json()

    # floe-dagster loads
    loaded = load_artifacts_from_json(json_str)
    assert loaded.version == artifacts.version
```

### Running Contract Tests

```bash
# Run contract tests only
uv run pytest packages/*/tests/contract/ -v --tb=short

# Expected: ~2 minutes, 100% pass (BLOCKING)
```

---

## Cross-Component Testing

### Dependency Graph

```
floe-core (schemas)
  ├─> floe-dagster (orchestration)
  │     └─> floe-cube (consumption)
  ├─> floe-dbt (transformations)
  │     └─> floe-dagster (orchestration)
  ├─> floe-iceberg (storage)
  └─> floe-polaris (catalog)
```

### Impact Analysis

| Changed Component | Run Tests For |
|-------------------|---------------|
| **floe-core** | ALL packages (core schemas affect everything) |
| **floe-dagster** | floe-cube (depends on Dagster assets) |
| **floe-dbt** | floe-dagster (dbt integration) |
| **floe-iceberg** | floe-dagster, floe-polaris (storage integration) |
| **floe-polaris** | floe-iceberg, floe-dagster (catalog integration) |
| **testing/base_classes** | ALL integration tests (shared infrastructure) |

---

## Merge Validation Workflow

### Goal: <15 Minutes

**Breakdown**:
1. **Smoke tests** (parallel by package): ~4 min
2. **Contract tests** (BLOCKING): ~2 min
3. **Targeted impacted tests**: ~8 min

**Total**: ~14 minutes (within target)

### GitHub Actions Example

```yaml
name: PR Validation

on: [pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Smoke tests
        run: uv run pytest -m smoke --maxfail=3 -x

  contract:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - name: Contract tests
        run: uv run pytest packages/*/tests/contract/ -v

  targeted:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - name: Detect impacted tests
        run: ./testing/scripts/detect-impacted-tests.sh

  # All must pass before merge
  merge-gate:
    needs: [smoke, contract, targeted]
    runs-on: ubuntu-latest
    steps:
      - name: All checks passed
        run: echo "Ready for merge"
```

---

## Flakiness Mitigation

### Retries for Non-Deterministic Tests

```python
import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_potentially_flaky():
    """Test with automatic retries.

    Use sparingly - better to fix flakiness than retry.
    """
    result = async_operation()
    assert result.success
```

**Better**: Fix the flakiness (use polling, fix race condition).

### Quarantine Pattern

```python
@pytest.mark.xfail(reason="Flaky due to #1234", strict=False)
def test_known_flaky():
    """Known flaky test - fix in progress."""
    # Runs but doesn't block merge if fails
```

**Use only temporarily** while fixing the root cause.

---

## External Resources

- **TESTING.md** - "Regression Testing Strategy" section
- **Martin Fowler - Test Pyramid**: https://martinfowler.com/articles/practical-test-pyramid.html
- **Google Testing Blog**: https://testing.googleblog.com/
