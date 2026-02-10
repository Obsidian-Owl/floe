---
name: testing
description: ALWAYS USE when writing tests, test fixtures, test utilities, or debugging test failures. MUST be loaded before creating pytest tests, integration tests, or test infrastructure. Provides test quality patterns, anti-pattern detection, K8s-native testing guidance, and regression strategies.
---

# Testing Skill (Research-Driven)

## Constitution Alignment

This skill enforces project principles:
- **V. K8s-Native Testing**: All integration/E2E tests run in Kubernetes for production parity
- **Tests FAIL, Never Skip**: `pytest.skip()` is FORBIDDEN except for `importorskip`
- **Requirement Traceability**: 100% of integration tests MUST have `@pytest.mark.requirement()` markers
- **Contract Tests**: Cross-package contracts MUST have root-level tests in `tests/contract/`

## Philosophy

**Tests are production code.** Apply the same rigor to test code as production code: type safety, security, maintainability, and quality standards.

This skill does NOT prescribe specific test implementations. Instead, it guides you to:
1. **Research** the current testing infrastructure and patterns
2. **Discover** existing test utilities, fixtures, and base classes
3. **Validate** tests follow project standards (TESTING.md)
4. **Verify** tests align with K8s-native production parity goals

## Quick Reference

For available test infrastructure (base classes, fixtures, utilities):
- **See**: `TESTING.md` → "Test Infrastructure Quick Reference"

This keeps the skill lean. TESTING.md has the detailed tables and API reference.

---

## Core Principles

### The "FAIL not Skip" Philosophy

**Tests MUST fail when infrastructure is missing, NEVER skip.**

| Situation | ❌ Wrong Approach | ✅ Correct Approach |
|-----------|------------------|---------------------|
| Service unavailable | `pytest.skip()` | Test fails, user fixes infrastructure |
| Feature not implemented | `@pytest.mark.skip` | Don't write test yet, or test NOT-implemented behavior |
| Flaky test | Skip to "fix later" | Fix the flakiness (add retries, fix race) |

**Why**: Skipped tests are invisible failures. "All tests pass" when half are skipped = false confidence.

### Production Parity (K8s-Native Testing)

**Target State**: All integration/E2E tests run in ephemeral Kubernetes clusters (kind) for production parity.

**Current State (Epic 2 Migration)**:
- Docker Compose (current baseline, being phased out)
- kind (target state, <30s cluster creation)

**Benefits of K8s-Native**:
- Same Helm charts as staging/production
- K8s service discovery works identically
- Health probes, init containers, hooks tested
- No `/etc/hosts` modification needed

**Read**: [references/k8s-native-testing.md](references/k8s-native-testing.md)

---

## Pre-Implementation Research Protocol

### Step 1: Verify Testing Infrastructure State

**ALWAYS check current state first**:

```bash
# Check if Docker Compose is running
docker compose -f testing/docker/docker-compose.yml ps

# Check if kind cluster exists
kind get clusters

# Verify test execution model
make test-unit     # Unit tests (host)
make test-k8s      # Integration tests (kind - target)
make test-all      # Both Docker + K8s (validation)
```

**Critical Questions**:
- Which test tier am I writing? (unit, contract, integration, E2E)
- Where should this test run? (host, Docker, K8s)
- What services does this test require?

**Read**: `TESTING.md` - "Test Execution Model (CRITICAL)" section

### Step 2: Discover Existing Test Patterns

**BEFORE writing new tests**, search for existing implementations:

```bash
# Find existing test base classes
rg "class.*TestBase|IntegrationTestBase" --type py testing/base_classes/

# Find existing fixtures
rg "@pytest.fixture" --type py testing/fixtures/

# Find polling utilities (replaces time.sleep)
rg "wait_for_condition|poll_until" --type py testing/fixtures/services.py

# Find existing tests for similar components
rg "def test_" --type py packages/<package>/tests/
```

**Key Questions**:
- What base classes exist for this test type?
- What fixtures are already available?
- What polling patterns are in use?
- How do similar tests handle service detection?

### Step 3: Research Test Anti-Patterns

**Check for common anti-patterns in similar tests**:

```bash
# Check for hardcoded sleeps (FORBIDDEN)
rg "time\.sleep\(" --type py packages/<package>/tests/

# Check for skipped tests (FORBIDDEN)
rg "@pytest\.mark\.skip|pytest\.skip\(" --type py packages/<package>/tests/

# Check for floating point equality (FORBIDDEN)
rg "assert.*==.*\d+\.\d+" --type py packages/<package>/tests/

# Check for missing negative path tests
rg "def test_.*_invalid|def test_.*_failure" --type py packages/<package>/tests/

# Check for accomplishment simulator (side-effect tests without mock assertions)
rg "def test.*write|def test.*send|def test.*publish|def test.*deploy" --type py packages/<package>/tests/ -l | \
  xargs -I{} sh -c 'rg "assert_called" {} > /dev/null || echo "WARNING: {} may have Accomplishment Simulator — side-effect tests without mock invocation assertions"'

# Check for import-satisfying-only mocks (MagicMock never asserted on)
rg "MagicMock\(\)" --type py packages/<package>/tests/ -l | head -5
# For each file: verify MagicMock has corresponding assert_called* somewhere
```

**Read**: [references/test-anti-patterns.md](references/test-anti-patterns.md)

### Step 4: Validate Against Testing Standards

**Before implementing**, verify compliance with:

1. **Requirement Traceability**: Every test MUST have `@pytest.mark.requirement()` marker
2. **Test Documentation**: Every test MUST have docstring explaining intent
3. **Type Hints**: All test functions and fixtures MUST have type hints
4. **Negative Path Coverage**: Every positive test (`test_X`) MUST have negative test (`test_X_invalid`)
5. **Unique Namespaces**: Integration tests MUST use unique namespaces for isolation
6. **Side-Effect Verification**: Tests for write/send/publish/deploy methods MUST include `mock.assert_called*()` — not just check return value shape (see `.claude/rules/testing-standards.md` "Side-Effect Verification" section)

**Read**: `TESTING.md` - Full testing guide with all standards

---

## Implementation Guidance (Progressive Disclosure)

### Test Tier Selection

**Where should this test live?**

| Test Tier | Location | Execution | Requires | Coverage Target |
|-----------|----------|-----------|----------|-----------------|
| **Unit** | `packages/*/tests/unit/` | Host (`uv run pytest`) | No external deps | 60% of tests |
| **Contract** | `packages/*/tests/contract/` | Host | No external deps | 10% of tests |
| **Integration** | `packages/*/tests/integration/` | Docker/K8s | External services | 20-30% of tests |
| **E2E** | `packages/*/tests/e2e/` | Docker/K8s | Full pipeline | 5-10% of tests |

**Decision Tree**:
```
Does test require external services (DB, S3, Polaris)?
  ├─ YES → Integration test (Docker/K8s)
  └─ NO → Does test validate cross-package contracts?
      ├─ YES → Contract test (host)
      └─ NO → Unit test (host)
```

### Using Test Base Classes

**For Integration Tests** - ALWAYS inherit from `IntegrationTestBase`:

```python
from testing.base_classes.integration_test_base import IntegrationTestBase

class MyIntegrationTest(IntegrationTestBase):
    """Integration test with automatic service detection."""

    # Declare required services (automatic health checking)
    required_services = [("polaris", 8181), ("localstack", 4566)]

    def test_something(self):
        # Automatically checks infrastructure before running
        self.check_infrastructure("polaris", 8181)

        # Generate unique namespace for isolation
        namespace = self.generate_unique_namespace("test_feature")

        # Use context-aware hostname resolution
        host = self.get_service_host("polaris")  # "polaris" in Docker/K8s, "localhost" on host
```

**Read**: `testing/base_classes/integration_test_base.py` for full API

### Polling Instead of Sleep

**NEVER use `time.sleep()` in tests** - use polling utilities:

```python
from testing.fixtures.services import wait_for_condition, poll_until

# Wait for boolean condition
def test_service_ready():
    start_service()

    # ❌ FORBIDDEN
    # time.sleep(5)

    # ✅ CORRECT
    result = wait_for_condition(
        condition=lambda: service.is_ready(),
        timeout=10.0,
        poll_interval=0.5,
        description="service to become ready"
    )
    assert result, "Service did not become ready"

# Poll until data appears
def test_lineage_emission():
    trigger_pipeline()

    # ✅ CORRECT - Two-phase polling
    traces = poll_until(
        fetch_func=lambda: jaeger.get_traces(service="test"),
        check_func=lambda traces: len(traces) > 0,
        timeout=10.0,
        description="traces to be exported"
    )
    assert traces is not None
```

**Read**: [references/polling-patterns.md](references/polling-patterns.md)

### Positive AND Negative Path Testing

**Every positive test MUST have corresponding negative tests**:

```python
# ✅ COMPLETE - Both paths tested
@pytest.mark.requirement("004-FR-001")
def test_create_catalog():
    """Test catalog creation succeeds with valid input."""
    catalog = create_catalog(name="valid_name", warehouse="warehouse")
    assert catalog is not None
    assert catalog.name == "valid_name"

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

@pytest.mark.requirement("004-FR-004")
def test_create_catalog_missing_warehouse():
    """Test catalog creation fails without warehouse."""
    with pytest.raises(ValidationError, match="warehouse.*required"):
        create_catalog(name="valid", warehouse="")
```

**Pattern**: For every success path, test ALL failure modes.

---

## Test Quality Validation

### Pre-Implementation Checklist

Before writing tests:
- [ ] Verified test tier (unit, contract, integration, E2E)
- [ ] Searched for existing test patterns
- [ ] Identified required services (if integration test)
- [ ] Found appropriate base class or fixtures
- [ ] Reviewed anti-patterns to avoid

### During Implementation Checklist

While writing tests:
- [ ] Test inherits from appropriate base class (if integration)
- [ ] All functions have type hints
- [ ] Every test has docstring explaining intent
- [ ] Using `wait_for_condition` instead of `time.sleep()`
- [ ] Generating unique namespaces for isolation
- [ ] Both positive AND negative paths tested
- [ ] Edge cases covered (empty, None, max bounds)
- [ ] Side-effect methods (write/send/publish) have mock invocation assertions

### Post-Implementation Checklist

After writing tests:
- [ ] All tests have `@pytest.mark.requirement()` markers
- [ ] Requirement traceability 100% (`python -m testing.traceability`)
- [ ] Tests pass locally: `make test-unit` or `make test-k8s`
- [ ] No skipped tests (tests FAIL, never skip)
- [ ] No hardcoded sleeps detected (`rg "time\.sleep\(" tests/`)
- [ ] No floating point equality (`rg "assert.*==.*\d+\.\d+" tests/`)
- [ ] Test coverage >80% for unit tests, >70% for integration
- [ ] Side-effect tests verify mock invocations, not just return values
- [ ] No import-satisfying-only mocks (`MagicMock()` without `assert_called*()`)

---

## Regression Testing Awareness

**Remember**: Your tests may run as part of regression suites.

**Impact Mapping**:
- Changes to `floe-core/schemas/` → ALL contract tests run
- Changes to `testing/base_classes/` → ALL integration tests run
- Changes to `charts/` → ALL K8s tests run

**Smoke Tests**: Mark critical path tests with `@pytest.mark.smoke` for fast CI feedback.

**Read**: [references/regression-strategies.md](references/regression-strategies.md)

---

## Advanced Test Quality Metrics

### Mutation Testing (Aspirational)

**Goal**: >80% mutation score for critical modules.

```bash
# Install mutmut
uv pip install mutmut

# Run mutation testing (slow - not for CI)
mutmut run --paths-to-mutate=packages/floe-core/src

# View results
mutmut results
```

**When to use**: Before releases, for critical modules (authentication, validation).

**Read**: [references/test-quality-metrics.md](references/test-quality-metrics.md)

### Property-Based Testing

**Goal**: Find edge cases automatically with Hypothesis.

```python
from hypothesis import given, strategies as st

@pytest.mark.requirement("001-FR-005")
@given(st.text(min_size=1, max_size=100))
def test_identifier_validation_property(input_str: str):
    """Property-based test: identifier validation with random inputs."""
    if input_str[0].isalpha():
        result = is_valid_identifier(input_str)
        assert isinstance(result, bool)
        # Property: valid identifiers match pattern
        if result:
            assert input_str[0].isalpha()
            assert all(c.isalnum() or c == "_" for c in input_str)
```

**Research Finding**: Property-based testing finds **50x more mutations** per test than unit tests.

---

## Context Injection (For Future Claude Instances)

When this skill is invoked, you should:

1. **Verify infrastructure state** (don't assume):
   ```bash
   make test-unit  # Check unit tests work
   kind get clusters  # Check K8s state
   ```

2. **Discover existing patterns** (don't invent):
   ```bash
   rg "class.*TestBase" --type py testing/base_classes/
   rg "@pytest.fixture" --type py testing/fixtures/
   ```

3. **Research when uncertain** (don't guess):
   - Read `TESTING.md` for comprehensive guide
   - Check `testing/base_classes/` for reusable patterns
   - Search for similar tests: `rg "def test_" packages/<package>/tests/`

4. **Validate against standards** (don't skip):
   - Requirement traceability markers present
   - No anti-patterns (hardcoded sleeps, skipped tests)
   - Both positive and negative paths tested

---

## Quick Reference: Common Research Queries

Use these searches when encountering specific needs:

**Finding Patterns**:
- Polling utilities: `rg "wait_for_condition|poll_until" testing/fixtures/`
- Service detection: `rg "get_service_host|check_infrastructure" testing/base_classes/`
- Unique namespaces: `rg "generate_unique_namespace" testing/base_classes/`

**Finding Examples**:
- Similar integration tests: `rg "class.*IntegrationTest" --type py packages/<package>/tests/`
- Negative path tests: `rg "def test_.*_invalid|def test_.*_failure" --type py`
- Property-based tests: `rg "@given\(" --type py`

**Validating Quality**:
- Check for anti-patterns: `rg "time\.sleep\(|pytest\.skip\(" --type py tests/`
- Verify requirement markers: `rg "@pytest\.mark\.requirement" --type py tests/`
- Check traceability: `python -m testing.traceability --all`

---

## Progressive Disclosure References

**Load only when needed** (zero context until loaded):

- **[references/test-anti-patterns.md](references/test-anti-patterns.md)** - 5 critical anti-patterns to avoid
- **[references/test-quality-metrics.md](references/test-quality-metrics.md)** - Beyond code coverage (mutation testing, property-based, defect density)
- **[references/k8s-native-testing.md](references/k8s-native-testing.md)** - kind cluster setup, production parity, Epic 2 migration
- **[references/regression-strategies.md](references/regression-strategies.md)** - Layered regression (smoke → targeted → full), impact mapping
- **[references/polling-patterns.md](references/polling-patterns.md)** - wait_for_condition and poll_until API details

**Core Documentation**:
- **`TESTING.md`** - Comprehensive testing guide (900+ lines, updated with modern practices)
- **`testing/base_classes/integration_test_base.py`** - IntegrationTestBase API
- **`testing/fixtures/services.py`** - Polling utilities source code

---

## External Resources

Research these when you need deeper understanding:

- **pytest documentation**: https://docs.pytest.org/
- **Hypothesis (property-based testing)**: https://hypothesis.readthedocs.io/
- **Testcontainers**: https://testcontainers-python.readthedocs.io/
- **kind (Kubernetes in Docker)**: https://kind.sigs.k8s.io/
- **Mutation testing with mutmut**: https://mutmut.readthedocs.io/

---

**Remember**: This skill provides research guidance, NOT prescriptive patterns. Always:
1. Verify the testing infrastructure state
2. Discover existing test patterns
3. Research when encountering unfamiliar patterns
4. Validate against project standards (TESTING.md)
5. Ensure tests FAIL when infrastructure missing (never skip)
