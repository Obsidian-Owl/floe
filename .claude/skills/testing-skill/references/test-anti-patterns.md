# Test Anti-Patterns Reference

## Overview

Common anti-patterns that lead to flaky, unreliable tests. These patterns MUST be avoided.

---

## 1. Hardcoded Sleep (CRITICAL)

### Problem

`time.sleep()` creates race conditions and slows tests unnecessarily.

### Detection

```bash
rg "time\.sleep\(" --type py <test_files>
```

### ❌ FORBIDDEN

```python
import time

def test_service_ready():
    start_service()
    time.sleep(5)  # Maybe enough? Maybe not? Slows every test run
    assert service.is_ready()

def test_data_arrives():
    trigger_pipeline()
    time.sleep(10)  # Arbitrary wait
    data = fetch_data()
    assert len(data) > 0
```

**Problems**:
- Race conditions: Service might need 6 seconds, test fails randomly
- Wastes time: Service ready in 2s, still waits 5s
- Flaky in CI: CI might be slower, needs more time

### ✅ CORRECT

```python
from testing.fixtures.services import wait_for_condition, poll_until

def test_service_ready():
    start_service()
    assert wait_for_condition(
        condition=lambda: service.is_ready(),
        timeout=10.0,
        poll_interval=0.5,
        description="service to become ready"
    ), "Service did not become ready within 10s"

def test_data_arrives():
    trigger_pipeline()
    data = poll_until(
        fetch_func=lambda: fetch_data(),
        check_func=lambda data: len(data) > 0,
        timeout=30.0,
        poll_interval=1.0,
        description="data to arrive"
    )
    assert data is not None, "Data did not arrive within 30s"
    assert len(data) > 0
```

**Benefits**:
- Deterministic: Returns as soon as condition met
- Faster: No unnecessary waiting
- Reliable: Timeout handles slow CI environments

---

## 2. Skipped Tests (CRITICAL)

### Problem

Skipped tests hide problems and create false confidence.

### Detection

```bash
rg "@pytest\.mark\.skip|pytest\.skip\(" --type py <test_files>
```

### ❌ FORBIDDEN

```python
import pytest

@pytest.mark.skip("Service not available")
def test_polaris_connection():
    """Test Polaris connection."""
    catalog = create_polaris_catalog()
    assert catalog is not None

def test_lineage_emission():
    if not marquez_available():
        pytest.skip("Marquez not running")
    # ...

@pytest.mark.skip("Flaky test, fix later")
def test_async_operation():
    # ...
```

**Problems**:
- Invisible failures: CI shows "All tests pass" when half are skipped
- Infrastructure rot: Broken setup goes unnoticed
- Flaky tests accumulate: "Fix later" never happens
- False confidence: Coverage metrics lie

### ✅ CORRECT

```python
import pytest

def test_polaris_connection(polaris_catalog):
    """Test Polaris connection.

    Fixture FAILS if Polaris not available (infrastructure check).
    """
    assert polaris_catalog is not None
    namespaces = polaris_catalog.list_namespaces()
    assert isinstance(namespaces, list)

# Fixture fails when infrastructure missing
@pytest.fixture
def polaris_catalog():
    """Create Polaris catalog. FAILS if not available."""
    try:
        catalog = create_polaris_catalog()
        # Verify connectivity
        catalog.list_namespaces()
    except Exception as e:
        pytest.fail(
            f"Polaris not available: {e}\n"
            "Start infrastructure: make docker-up"
        )
    return catalog

# Fix flaky test instead of skipping
def test_async_operation():
    """Fixed async operation test with proper awaits."""
    result = asyncio.run(async_operation())
    assert result is not None
```

**Benefits**:
- Tests FAIL when infrastructure missing (forces fixes)
- No hidden failures
- Flaky tests get fixed, not hidden

### Acceptable Skip Uses (Rare)

**Only two acceptable uses**:

1. **Optional dependencies**:
   ```python
   pytest.importorskip("optional_library")
   ```

2. **Platform-specific** (literal impossibility):
   ```python
   @pytest.mark.skipif(sys.platform == "win32", reason="POSIX only")
   ```

---

## 3. Test Pollution (Shared State)

### Problem

Tests affect each other through shared state, causing order-dependent failures.

### Detection

Run tests with random order:
```bash
uv run pytest --random-order
```

If failures appear/disappear, you have test pollution.

### ❌ FORBIDDEN

```python
# Global cache pollutes between tests
GLOBAL_CACHE = {}

def test_create_item():
    GLOBAL_CACHE["key"] = "value"  # Pollutes next test

def test_check_cache():
    # Depends on previous test running first!
    assert "key" in GLOBAL_CACHE

# Shared database without cleanup
def test_create_user():
    db.users.insert({"id": 1, "name": "Alice"})

def test_user_exists():
    # Fails if test_create_user didn't run first
    user = db.users.find_one({"id": 1})
    assert user["name"] == "Alice"

# Environment variables not reset
def test_with_env():
    os.environ["MY_VAR"] = "value"
    # Not cleaned up!
```

**Problems**:
- Order-dependent: Tests pass in one order, fail in another
- Parallel execution breaks: `pytest-xdist` reveals hidden dependencies
- Hard to debug: Failure only when run after specific test

### ✅ CORRECT

```python
import uuid

def test_create_item():
    """Test with unique namespace (isolated)."""
    namespace = f"test_{uuid.uuid4().hex[:8]}"
    cache = get_cache(namespace)
    cache["key"] = "value"
    assert cache["key"] == "value"

def test_check_cache():
    """Test with own unique namespace."""
    namespace = f"test_{uuid.uuid4().hex[:8]}"
    cache = get_cache(namespace)
    cache["key"] = "other_value"
    assert cache["key"] == "other_value"

# Database cleanup in fixture
@pytest.fixture
def clean_db():
    """Provide clean database for each test."""
    db.users.delete_many({})  # Clean before
    yield db
    db.users.delete_many({})  # Clean after

def test_create_user(clean_db):
    clean_db.users.insert({"id": 1, "name": "Alice"})
    assert clean_db.users.count_documents({}) == 1

def test_user_exists(clean_db):
    clean_db.users.insert({"id": 2, "name": "Bob"})
    user = clean_db.users.find_one({"id": 2})
    assert user["name"] == "Bob"

# Environment variable cleanup
@pytest.fixture
def temp_env():
    """Provide temporary environment variable."""
    old_value = os.environ.get("MY_VAR")
    yield
    # Restore original state
    if old_value is None:
        os.environ.pop("MY_VAR", None)
    else:
        os.environ["MY_VAR"] = old_value

def test_with_env(temp_env):
    os.environ["MY_VAR"] = "value"
    # Automatically cleaned up by fixture
```

**Benefits**:
- Test isolation: Each test is independent
- Parallel-safe: Works with `pytest-xdist`
- Order-independent: Pass in any order

### Sources of Test Pollution

| Source | Solution |
|--------|----------|
| Global variables | Use unique namespaces per test |
| Shared databases | Cleanup in fixtures (before + after) |
| Redis/caches | Use unique keys with UUID |
| Filesystem | Use `tmp_path` fixture, cleanup after |
| Environment variables | Restore original values in fixture |
| Singleton objects | Reset state in fixture or use factory pattern |

---

## 4. Missing Negative Path Tests

### Problem

Only testing success cases, not error handling.

### Detection

```bash
# Find positive tests
rg "def test_create_|def test_update_|def test_delete_" --type py

# Check for corresponding negative tests
rg "def test_create_.*invalid|def test_create_.*failure" --type py
```

### ❌ INCOMPLETE

```python
def test_create_catalog():
    """Test catalog creation."""
    catalog = create_catalog(name="valid")
    assert catalog is not None
    # Only tests success path!
```

**Problems**:
- Error handling not tested
- Edge cases missed
- Production bugs when invalid input received

### ✅ COMPLETE

```python
# Positive path
@pytest.mark.requirement("004-FR-001")
def test_create_catalog():
    """Test catalog creation succeeds with valid input."""
    catalog = create_catalog(name="valid_name", warehouse="warehouse")
    assert catalog is not None
    assert catalog.name == "valid_name"

# Negative paths (ALL failure modes)
@pytest.mark.requirement("004-FR-002")
def test_create_catalog_empty_name():
    """Test catalog creation fails with empty name."""
    with pytest.raises(ValidationError, match="name.*required"):
        create_catalog(name="", warehouse="warehouse")

@pytest.mark.requirement("004-FR-003")
def test_create_catalog_invalid_chars():
    """Test catalog creation fails with invalid characters."""
    with pytest.raises(ValidationError, match="Invalid.*characters"):
        create_catalog(name="invalid-name!", warehouse="warehouse")

@pytest.mark.requirement("004-FR-004")
def test_create_catalog_already_exists():
    """Test catalog creation fails when name exists."""
    create_catalog(name="existing", warehouse="warehouse")
    with pytest.raises(ConflictError, match="already exists"):
        create_catalog(name="existing", warehouse="warehouse")

@pytest.mark.requirement("004-FR-005")
def test_create_catalog_missing_warehouse():
    """Test catalog creation fails without warehouse."""
    with pytest.raises(ValidationError, match="warehouse.*required"):
        create_catalog(name="valid", warehouse="")

@pytest.mark.requirement("004-FR-006")
def test_create_catalog_none_values():
    """Test catalog creation fails with None values."""
    with pytest.raises(ValidationError):
        create_catalog(name=None, warehouse=None)
```

**Pattern**: For every success path, test ALL failure modes.

### Edge Cases Checklist

Always test:
- [ ] Empty input (`""`, `[]`, `{}`)
- [ ] None values
- [ ] Max bounds (very large numbers, long strings)
- [ ] Min bounds (zero, negative)
- [ ] Invalid types (string where int expected)
- [ ] Boundary conditions (age=18 for age>=18 validation)
- [ ] Duplicate entries (when uniqueness required)
- [ ] Missing required fields

---

## 5. Floating Point Precision

### Problem

Floating point `==` comparisons are unreliable due to precision issues.

### Detection

```bash
rg "assert.*==.*\d+\.\d+" --type py <test_files>
```

### ❌ FORBIDDEN

```python
def test_timeout():
    config = load_config()
    assert config.timeout == 1.0  # May fail: 0.9999999999 != 1.0

def test_ratio():
    ratio = calculate_ratio()
    assert ratio == 0.5  # May fail: 0.49999999 != 0.5
```

**Problems**:
- Flaky failures due to floating point precision
- SonarQube rule S1244 flags this
- Non-deterministic behavior

### ✅ CORRECT

```python
import pytest

def test_timeout():
    config = load_config()
    assert config.timeout == pytest.approx(1.0)

def test_ratio():
    ratio = calculate_ratio()
    assert ratio == pytest.approx(0.5, rel_tol=1e-9)

def test_with_custom_tolerance():
    value = expensive_computation()
    assert value == pytest.approx(expected, abs=0.01)
```

**Benefits**:
- Reliable comparisons
- Configurable tolerance
- SonarQube compliant

---

## 6. Non-Deterministic Behavior

### Problem

Tests pass/fail randomly due to race conditions or external factors.

### Common Causes

| Cause | Solution |
|-------|----------|
| Race conditions | Add proper awaits, use polling |
| Parallel execution with shared resources | Use unique namespaces, fixtures |
| Random test order revealing dependencies | Fix test pollution, ensure isolation |
| Time-based logic (dates, timestamps) | Mock `datetime.now()`, `time.time()` |
| External API calls | Mock external APIs, use VCR.py |
| Filesystem state | Use `tmp_path` fixture |
| Random number generation | Use deterministic seeds: `random.seed(42)` |

### Detection

```bash
# Run tests multiple times
for i in {1..10}; do uv run pytest tests/; done

# Run with random order
uv run pytest --random-order

# Run in parallel
uv run pytest -n auto
```

If failures appear/disappear, you have non-determinism.

### ❌ FORBIDDEN

```python
import random
from datetime import datetime

def test_random_data():
    # Non-deterministic!
    value = random.randint(1, 100)
    result = process(value)
    assert result > 0  # Sometimes fails

def test_timestamp():
    # Non-deterministic!
    now = datetime.now()
    if now.hour < 12:
        # Test behaves differently AM vs PM
        assert morning_logic()
    else:
        assert afternoon_logic()
```

### ✅ CORRECT

```python
import random
from datetime import datetime
from unittest.mock import patch

def test_random_data():
    # Deterministic with seed
    random.seed(42)
    value = random.randint(1, 100)  # Always 81 with seed 42
    result = process(value)
    assert result == expected_result_for_81

@patch("mymodule.datetime")
def test_timestamp(mock_datetime):
    # Mock time for determinism
    mock_datetime.now.return_value = datetime(2025, 1, 5, 10, 0, 0)
    assert morning_logic()  # Always tests morning logic

    mock_datetime.now.return_value = datetime(2025, 1, 5, 14, 0, 0)
    assert afternoon_logic()  # Always tests afternoon logic
```

**Benefits**:
- Deterministic test behavior
- Reproducible failures
- Reliable CI

---

## Summary: Anti-Pattern Detection Checklist

Before committing tests, run these checks:

```bash
# 1. No hardcoded sleeps
rg "time\.sleep\(" --type py tests/
# Expected: No results

# 2. No skipped tests
rg "@pytest\.mark\.skip|pytest\.skip\(" --type py tests/
# Expected: No results (except importorskip, platform-specific)

# 3. No floating point equality
rg "assert.*==.*\d+\.\d+" --type py tests/
# Expected: No results

# 4. Tests have requirement markers
rg "@pytest\.mark\.requirement" --type py tests/ | wc -l
# Expected: Count matches number of tests

# 5. Negative path tests exist
rg "def test_.*_invalid|def test_.*_failure|def test_.*_error" --type py tests/
# Expected: At least 1 negative test per positive test
```

---

## References

- **TESTING.md** - "Test Anti-Patterns (MUST AVOID)" section
- **testing/fixtures/services.py** - Polling utilities source
- **testing/base_classes/integration_test_base.py** - Service detection patterns
