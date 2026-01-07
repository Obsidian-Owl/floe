# Testing Standards (MANDATORY)

## Test Code is Production Code

**YOU MUST apply the same rigor to test code as production code:**
- Type hints on ALL test functions and fixtures
- Security: No hardcoded credentials, even in tests
- Quality: No flaky tests, no test pollution
- Maintainability: Clear docstrings, DRY principles

---

## Tests FAIL, Never Skip (NON-NEGOTIABLE)

**YOU MUST NEVER use `pytest.skip()` or `@pytest.mark.skip`:**

```python
# ❌ FORBIDDEN - Skipped tests hide problems
@pytest.mark.skip("Service not available")
def test_something():
    ...

def test_something():
    if not service_available():
        pytest.skip("Service not available")  # NEVER!

# ✅ CORRECT - Tests FAIL when infrastructure missing
def test_something(service_client):
    """Test requires service - FAILS if not available."""
    response = service_client.query(...)
    assert response.status_code == 200

# Fixture fails when infrastructure missing
@pytest.fixture
def service_client():
    """Create service client. FAILS if not available."""
    try:
        client = create_client()
        client.ping()
    except Exception as e:
        pytest.fail(
            f"Service not available: {e}\n"
            "Start infrastructure: make test-k8s"
        )
    return client
```

**The ONLY acceptable skip uses:**
1. `pytest.importorskip("optional_library")` - genuinely optional dependencies
2. `@pytest.mark.skipif(sys.platform == "win32")` - literal platform impossibility

**Why**: Skipped tests are invisible failures. CI shows "All tests pass" when half are skipped = false confidence.

---

## No Hardcoded Sleep (CRITICAL)

**YOU MUST NEVER use `time.sleep()` in tests:**

```python
# ❌ FORBIDDEN - Hardcoded sleep
import time
def test_service_ready():
    start_service()
    time.sleep(5)  # Race condition, wastes time
    assert service.is_ready()

# ✅ CORRECT - Use polling utilities
from testing.fixtures.services import wait_for_condition

def test_service_ready():
    start_service()
    assert wait_for_condition(
        lambda: service.is_ready(),
        timeout=10.0,
        description="service to become ready"
    ), "Service did not become ready within 10s"
```

**Grep check**: `rg "time\.sleep\(" --type py tests/` should return NOTHING.

---

## Requirement Traceability (MANDATORY)

**YOU MUST add `@pytest.mark.requirement()` to ALL tests:**

```python
# ❌ FORBIDDEN - No requirement marker
def test_create_catalog():
    ...

# ✅ CORRECT - Linked to spec requirement
@pytest.mark.requirement("004-FR-001")
def test_create_catalog():
    """Test catalog creation succeeds."""
    ...

# Multiple requirements covered
@pytest.mark.requirement("004-FR-001")
@pytest.mark.requirement("006-FR-012")
def test_polaris_integration():
    """Test covers multiple requirements."""
    ...
```

**Enforcement**: `python -m testing.traceability --all --threshold 100` MUST show 100% coverage.

---

## Test Documentation (MANDATORY)

**YOU MUST add docstrings to ALL test functions:**

```python
# ❌ FORBIDDEN - No docstring
def test_create_catalog():
    catalog = create_catalog(name="test")
    assert catalog is not None

# ✅ CORRECT - Clear docstring explaining intent
@pytest.mark.requirement("004-FR-001")
def test_create_catalog():
    """Test catalog creation succeeds with valid input.

    Validates that create_catalog returns a valid Catalog object
    when provided with a valid name and warehouse.
    """
    catalog = create_catalog(name="test", warehouse="warehouse")
    assert catalog is not None
    assert catalog.name == "test"
```

**Pattern**: Docstring should explain WHAT is being tested and WHY.

---

## Positive AND Negative Path Testing (MANDATORY)

**YOU MUST test both success and failure paths:**

```python
# ❌ INCOMPLETE - Only positive path
@pytest.mark.requirement("004-FR-001")
def test_create_catalog():
    """Test catalog creation."""
    catalog = create_catalog(name="valid")
    assert catalog is not None

# ✅ COMPLETE - Both paths tested
@pytest.mark.requirement("004-FR-001")
def test_create_catalog():
    """Test catalog creation succeeds with valid input."""
    catalog = create_catalog(name="valid", warehouse="warehouse")
    assert catalog is not None

@pytest.mark.requirement("004-FR-002")
def test_create_catalog_invalid_name():
    """Test catalog creation fails with invalid name."""
    with pytest.raises(ValidationError, match="Invalid name"):
        create_catalog(name="", warehouse="warehouse")

@pytest.mark.requirement("004-FR-003")
def test_create_catalog_already_exists():
    """Test catalog creation fails when name exists."""
    create_catalog(name="existing", warehouse="warehouse")
    with pytest.raises(ConflictError, match="already exists"):
        create_catalog(name="existing", warehouse="warehouse")
```

**Pattern**: For every `test_X`, you MUST have `test_X_invalid`, `test_X_failure`, `test_X_error`, etc.

---

## Floating Point Precision (CRITICAL)

**YOU MUST use `pytest.approx()` for float comparisons:**

```python
# ❌ FORBIDDEN - Direct equality
def test_timeout():
    assert config.timeout == 1.0  # Flaky due to precision

# ✅ CORRECT - Use pytest.approx()
import pytest

def test_timeout():
    assert config.timeout == pytest.approx(1.0)

def test_ratio():
    assert ratio == pytest.approx(0.5, rel_tol=1e-9)
```

**Grep check**: `rg "assert.*==.*\d+\.\d+" --type py tests/` should return NOTHING.

---

## Test Isolation (MANDATORY)

**YOU MUST ensure tests are isolated and can run in any order:**

```python
# ❌ FORBIDDEN - Shared global state
GLOBAL_CACHE = {}

def test_create_item():
    GLOBAL_CACHE["key"] = "value"  # Pollutes next test!

def test_check_cache():
    assert "key" in GLOBAL_CACHE  # Depends on previous test

# ✅ CORRECT - Unique namespace per test
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
```

**YOU MUST use unique namespaces/IDs for:**
- Database records
- Cache keys
- Catalog namespaces
- S3 bucket paths
- Kubernetes namespaces

**Helper**: `IntegrationTestBase.generate_unique_namespace("prefix")`

---

## Integration Test Base Classes (MANDATORY)

**For integration tests, YOU MUST inherit from `IntegrationTestBase`:**

```python
from testing.base_classes.integration_test_base import IntegrationTestBase

class TestPolarisIntegration(IntegrationTestBase):
    """Integration tests for Polaris catalog."""
    required_services = [("polaris", 8181), ("localstack", 4566)]

    @pytest.mark.requirement("004-FR-001")
    def test_create_catalog(self) -> None:
        """Test catalog creation with real Polaris."""
        self.check_infrastructure("polaris", 8181)
        namespace = self.generate_unique_namespace("test_polaris")
        catalog = create_catalog(name=f"{namespace}_catalog")
        assert catalog is not None
```

**See TESTING.md for**: Complete IntegrationTestBase API, service fixtures, polling utilities

---

## Type Hints in Tests (MANDATORY)

**YOU MUST include type hints on ALL test functions and fixtures:**

```python
from __future__ import annotations  # REQUIRED at top

# ❌ FORBIDDEN - No type hints
def test_something():
    result = process_data()
    assert result > 0

@pytest.fixture
def my_fixture():
    return create_object()

# ✅ CORRECT - Type hints present
from __future__ import annotations

from typing import Any

@pytest.mark.requirement("001-FR-001")
def test_something() -> None:
    """Test with type hints."""
    result: int = process_data()
    assert result > 0

@pytest.fixture
def my_fixture() -> MyObject:
    """Fixture with return type."""
    return create_object()

@pytest.fixture
def config_dict() -> dict[str, Any]:
    """Fixture returning dict."""
    return {"key": "value"}
```

**Run**: `mypy --strict floe-*/tests/ plugins/*/tests/` MUST pass.

---

## Test Organization (REFERENCE)

**See `.claude/rules/test-organization.md` for**:
- Complete decision tree (package vs root placement)
- Test tier selection (unit/contract/integration/E2E)
- Anti-patterns and fixes
- Directory structure validation

---

## Edge Cases Coverage (MANDATORY)

**YOU MUST test edge cases:**

**Checklist**:
- [ ] Empty input (`""`, `[]`, `{}`)
- [ ] None values
- [ ] Max bounds (very large numbers, long strings)
- [ ] Min bounds (zero, negative)
- [ ] Invalid types (string where int expected)
- [ ] Boundary conditions (e.g., age=18 for age>=18 validation)
- [ ] Duplicate entries (when uniqueness required)
- [ ] Missing required fields

```python
@pytest.mark.requirement("004-FR-010")
def test_create_catalog_edge_cases():
    """Test catalog creation with edge cases."""
    # Empty name
    with pytest.raises(ValidationError, match="name.*required"):
        create_catalog(name="", warehouse="warehouse")

    # None values
    with pytest.raises(ValidationError):
        create_catalog(name=None, warehouse=None)

    # Very long name (max bounds)
    long_name = "a" * 1000
    with pytest.raises(ValidationError, match="name.*too long"):
        create_catalog(name=long_name, warehouse="warehouse")

    # Invalid characters
    with pytest.raises(ValidationError, match="Invalid.*characters"):
        create_catalog(name="invalid@name!", warehouse="warehouse")
```

---

## Pre-Commit Test Quality Checklist

**Before committing, verify:**

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

# 4. All tests have requirement markers
rg "@pytest\.mark\.requirement" --type py tests/ | wc -l
# Expected: Count matches number of tests

# 5. All tests have docstrings
git diff main...HEAD | grep -A3 '^\+def test_' | grep '"""' | wc -l
# Expected: Count matches number of new tests

# 6. Requirement traceability 100%
uv run python -m testing.traceability --all --threshold 100
# Expected: 100% coverage

# 7. Tests pass
make test-unit
# Expected: All pass
```

---

## CI Enforcement

**These standards are enforced in CI:**

1. **Requirement Traceability Gate**: `uv run python -m testing.traceability --all --threshold 100` MUST pass
2. **No Skipped Tests**: CI reports skipped test count, MUST be 0
3. **Type Check**: `mypy --strict floe-*/tests/ plugins/*/tests/` MUST pass
4. **Anti-Pattern Detection**: Pre-commit hook blocks hardcoded sleeps, skipped tests
5. **Coverage Gate**: Unit tests >80%, integration tests >70%

---

## References

- **TESTING.md** - Comprehensive testing guide (900+ lines)
- **testing-skill** - Research-driven skill for test implementation
- **testing/base_classes/integration_test_base.py** - Base class API
- **testing/fixtures/services.py** - Polling utilities
