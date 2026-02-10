# Testing Standards (MANDATORY)

## Test Code is Production Code

**YOU MUST apply the same rigor to test code as production code:**
- Type hints on ALL test functions and fixtures
- Security: No hardcoded credentials, even in tests
- Quality: No flaky tests, no test pollution
- Maintainability: Clear docstrings, DRY principles

---

## Test Assertion Integrity (NON-NEGOTIABLE)

**YOU MUST NEVER weaken test assertions to make failing tests pass.**

When a test fails, the **code under test** is wrong, not the test. Test assertions encode architectural intent and expected behavior. Weakening them hides bugs.

### FORBIDDEN: Assertion Softening

```python
# ❌ FORBIDDEN - Weakening assertion to avoid fixing real bug
# Original (strong - validates actual data):
assert scanned.num_rows == 3
assert set(scanned["name"].to_pylist()) == {"Alice", "Bob", "Charlie"}

# Softened (weak - proves nothing):
assert scanned is not None  # "simplified"
assert scanned.num_rows > 0  # "relaxed for reliability"
```

### FORBIDDEN: Mock Substitution in Integration Tests

```python
# ❌ FORBIDDEN - Replacing real service with mock in integration test
# Plan specified: "real Polaris + real MinIO, no mocks"
# Implementation sneaks in:
table_manager = MagicMock()  # NOT a real integration test
```

### FORBIDDEN: Exception Swallowing

```python
# ❌ FORBIDDEN - Hiding failures to make tests green
try:
    result = real_operation()
    assert result.success
except Exception:
    pass  # "sometimes flaky"
```

### REQUIRED: Escalation on Test Failure

When a test reveals a genuine problem (not a typo or simple bug):

1. **STOP** - Do not modify the test assertion
2. **Diagnose** - Identify the root cause
3. **Escalate** - Use `AskUserQuestion` to present the problem and options
4. **Wait** - Do not proceed until the user approves a path forward

```python
# Test fails: assert scanned.num_rows == 3 (actual: 0)
# Root cause: S3 endpoint mismatch
# CORRECT RESPONSE: Escalate via AskUserQuestion
#   "Test reveals S3 endpoint resolution issue. Options: ..."
# WRONG RESPONSE: Change assertion to `assert scanned is not None`
```

### Assertion Strength Hierarchy

Always use the strongest possible assertion:

| Strength | Pattern | When to Use |
|----------|---------|-------------|
| **Strongest** | `assert value == expected_exact_value` | Default - always prefer |
| **Strong** | `assert set(values) == {"a", "b", "c"}` | When order doesn't matter |
| **Moderate** | `assert len(values) == 3` | When exact values vary (e.g., UUIDs) |
| **Weak** | `assert len(values) > 0` | ONLY when count genuinely varies |
| **Forbidden** | `assert value is not None` | NEVER for values that should have specific content |

**See also**: `.claude/rules/quality-escalation.md` for the full escalation protocol.

---

## Side-Effect Verification (NON-NEGOTIABLE)

**YOU MUST verify side effects for any method whose primary purpose is an action (write, send, publish, deploy, delete).**

Return values alone NEVER prove a side effect occurred. A function can compute metrics, build a well-formed result object, and return `success=True` — all without performing its core action. This is the **"Accomplishment Simulator"** anti-pattern.

### The Accomplishment Simulator Anti-Pattern

**Named after the Epic 4G incident**: A `write()` method computed checksums, logged success, emitted OTel spans, returned a perfectly-formed `EgressResult(success=True, rows_delivered=100)` — but never called `dlt.pipeline.run()`. It passed 122 unit tests, security review, architecture review, contract tests, and 20 pre-push hooks.

```python
# ❌ THE ACCOMPLISHMENT SIMULATOR - Tests only check return value shape
def test_write_returns_egress_result(plugin):
    """LOOKS like it tests write, but only tests result shape."""
    result = plugin.write(mock_sink, mock_data)
    assert isinstance(result, EgressResult)  # Shape check
    assert result.success is True            # Shape check
    assert result.rows_delivered >= 0        # Shape check
    # MISSING: Did write() actually WRITE anything?

# ✅ SIDE-EFFECT VERIFICATION - Tests prove the action happened
def test_write_invokes_dlt_pipeline(plugin):
    """Proves write() actually delegates to dlt pipeline."""
    import sys
    mock_dlt = sys.modules["dlt"]

    plugin.write(sink, mock_data)

    mock_dlt.pipeline.assert_called_once()           # Pipeline created
    mock_dlt.pipeline.return_value.run.assert_called_once()  # Pipeline executed
```

### REQUIRED: Side-Effect Test Checklist

For ANY method whose primary purpose is a side effect, tests MUST include:

| Verb in Spec | Required Assertion | Assertion Type |
|--------------|-------------------|----------------|
| **write/push/send** | `mock_target.write.assert_called_once()` | Mock invocation |
| **delete/remove** | `mock_store.delete.assert_called_with(key)` | Mock invocation |
| **publish/emit** | `mock_bus.publish.assert_called_once()` | Mock invocation |
| **deploy/create** | `mock_client.create.assert_called_once()` | Mock invocation |
| **update/modify** | `mock_store.update.assert_called_with(...)` | Mock invocation |

### FORBIDDEN: Return-Value-as-Proxy

```python
# ❌ FORBIDDEN - Assumes return value proves side effect
result = plugin.write(sink, data)
assert result.success is True
assert result.rows_delivered == 100
# "Tests pass" but write() might be a no-op!

# ❌ FORBIDDEN - Tests only error handling, not happy path behavior
def test_write_raises_on_failure(plugin):
    """Only tests failure mode — doesn't prove success mode works."""
    with pytest.raises(SinkWriteError):
        plugin.write(bad_sink, data)
```

### Mock Invocation Audit Rule

Every `MagicMock()` in a test fixture MUST have at least one corresponding `assert_called*()` in the test suite. A mock that is never asserted on is an **import-satisfying mock** — it prevents ImportError but proves nothing about behavior.

```python
# ❌ IMPORT-SATISFYING MOCK - Exists only to prevent ImportError
mock_dlt = MagicMock()
mock_dlt.__version__ = "1.20.0"
# Never: mock_dlt.pipeline.assert_called_once()

# ✅ INVOCATION-VERIFYING MOCK - Proves behavior
mock_dlt = MagicMock()
mock_dlt.__version__ = "1.20.0"
# In test: mock_dlt.pipeline.assert_called_once()
# In test: mock_dlt.pipeline.return_value.run.assert_called_once()
```

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

# 8. Side-effect methods have invocation assertions
# For every test of a write/send/publish/deploy method, verify mock.assert_called*()
rg "def test.*write|def test.*send|def test.*publish|def test.*deploy" --type py tests/ -l | \
  xargs -I{} sh -c 'rg "assert_called" {} || echo "WARNING: {} has side-effect tests without mock invocation assertions"'
# Expected: No warnings

# 9. No import-satisfying-only mocks
# Mocks in fixtures should have corresponding assert_called* in tests
rg "MagicMock\(\)" --type py tests/ -l | head -5
# Manual review: Each MagicMock must have assert_called* somewhere in the test file
```

---

## CI Enforcement

**These standards are enforced in CI:**

1. **Requirement Traceability Gate**: `uv run python -m testing.traceability --all --threshold 100` MUST pass
2. **No Skipped Tests**: CI reports skipped test count, MUST be 0
3. **Type Check**: `mypy --strict floe-*/tests/ plugins/*/tests/` MUST pass
4. **Anti-Pattern Detection**: Pre-commit hook blocks hardcoded sleeps, skipped tests
5. **Coverage Gate**: Unit tests >80%, integration tests >70%
6. **Side-Effect Verification**: Tests for side-effect methods (write, send, publish, deploy) MUST include `assert_called*()` on mocked dependencies
7. **Mock Invocation Audit**: Pre-commit hook flags `MagicMock()` in fixtures without corresponding `assert_called*()` in tests

---

## References

- **TESTING.md** - Comprehensive testing guide (900+ lines)
- **testing-skill** - Research-driven skill for test implementation
- **testing/base_classes/integration_test_base.py** - Base class API
- **testing/fixtures/services.py** - Polling utilities
