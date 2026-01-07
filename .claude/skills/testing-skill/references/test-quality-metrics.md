# Test Quality Metrics Reference

## Overview

Code coverage alone is **insufficient** for quality assurance. Use these additional metrics to measure test quality.

---

## 1. Requirement Traceability Coverage

### Metric

**100% of functional requirements have at least one test.**

### Measurement

```bash
# Generate traceability report
python -m testing.traceability --all --threshold 100

# Expected output:
# ✅ Feature 006: 12/12 requirements covered (100%)
# ✅ Feature 004: 8/8 requirements covered (100%)
# ✅ Overall: 100% coverage
```

### Implementation

```python
@pytest.mark.requirement("006-FR-012")  # Links to spec requirement
@pytest.mark.requirement("004-FR-001")  # Can cover multiple features
def test_create_catalog():
    """Test catalog creation with OAuth2 authentication.

    Covers:
    - 006-FR-012: floe-polaris MUST have integration tests
    - 004-FR-001: System MUST connect to Polaris REST catalogs
    """
    catalog = create_catalog(name="test", warehouse="warehouse")
    assert catalog is not None
```

### Enforcement

**CI gate**: Blocks merge if <100% traceability.

### Benefits

- Every requirement is tested
- No "orphaned" requirements
- Clear test-to-requirement mapping
- Audit trail for compliance

---

## 2. Mutation Testing (Aspirational)

### Metric

**Mutation score = % of introduced bugs caught by tests.**

**Research Finding**: Mutation testing catches **10-15% more defects** than code coverage alone.

### How It Works

1. **Mutate code**: Introduce bugs (change `>=` to `>`, `+` to `-`, etc.)
2. **Run tests**: Do tests catch the bug?
3. **Score**: `(Mutations Caught / Total Mutations) * 100`

### Example

```python
# Original code
def validate_age(age: int) -> bool:
    return age >= 18  # Mutation: Change to age > 18

# Weak test (doesn't catch mutation)
def test_validate_age():
    assert validate_age(20) is True  # Passes with both >= and >

# Strong test (catches mutation)
def test_validate_age_boundary():
    assert validate_age(18) is True  # Fails if mutated to >
    assert validate_age(17) is False
```

### Running Mutation Tests

```bash
# Install mutmut
uv pip install mutmut

# Run mutation testing (slow - not for CI)
mutmut run --paths-to-mutate=packages/floe-core/src

# View results
mutmut results

# Show details
mutmut show <mutation_id>

# Expected: >80% mutation score for critical modules
```

### When to Use

- **Before releases** (not every commit - too slow)
- **Critical modules** (authentication, validation, data integrity)
- **Low-coverage areas** (find gaps in test quality)

### Interpretation

| Mutation Score | Quality |
|----------------|---------|
| 90-100% | Excellent test quality |
| 70-89% | Good, some gaps |
| 50-69% | Moderate, needs improvement |
| <50% | Weak tests, major gaps |

---

## 3. Property-Based Testing

### Metric

**Edge cases found per test.**

**Research Finding**: Property-based testing finds **50x more mutations** per test than unit tests.

### How It Works

Instead of writing individual test cases, define **properties** that should always hold true, then let Hypothesis generate hundreds of random inputs.

### Traditional vs Property-Based

```python
# Traditional test - 1 case
def test_identifier_valid():
    assert is_valid_identifier("my_name") is True

# Property-based test - 100+ cases automatically
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
def test_identifier_property(input_str: str):
    """Property: valid identifiers match pattern."""
    if input_str[0].isalpha():
        result = is_valid_identifier(input_str)
        # Property: if valid, must start with letter and contain only alnum + _
        if result:
            assert input_str[0].isalpha()
            assert all(c.isalnum() or c == "_" for c in input_str)
```

### Common Properties

| Property Type | Example |
|---------------|---------|
| **Invariants** | Sorting list twice == sorting once |
| **Roundtrip** | serialize(deserialize(x)) == x |
| **Idempotence** | f(f(x)) == f(x) |
| **Symmetry** | distance(a, b) == distance(b, a) |
| **Monotonicity** | if x > y, then f(x) >= f(y) |

### When to Use

- **Complex validation logic** (identifiers, URLs, emails)
- **Parsers/serializers** (JSON, YAML, CSV)
- **Mathematical operations** (addition, multiplication)
- **String manipulation** (splitting, joining, encoding)

### Example: JSON Roundtrip

```python
from hypothesis import given
from hypothesis.strategies import dictionaries, text, integers

@given(dictionaries(text(), integers()))
def test_json_roundtrip(data):
    """Property: JSON serialize → deserialize preserves data."""
    serialized = json.dumps(data)
    deserialized = json.loads(serialized)
    assert deserialized == data
```

### Hypothesis Strategies

```python
from hypothesis import strategies as st

# Primitives
st.integers(min_value=0, max_value=100)
st.floats(min_value=0.0, max_value=1.0)
st.text(min_size=1, max_size=100)
st.booleans()

# Collections
st.lists(st.integers(), min_size=0, max_size=10)
st.dictionaries(st.text(), st.integers())
st.tuples(st.text(), st.integers())

# Composite
st.one_of(st.none(), st.text())  # Optional string
st.sampled_from(["red", "green", "blue"])  # Enum

# Custom
@st.composite
def catalog_names(draw):
    """Generate valid catalog names."""
    prefix = draw(st.sampled_from(["dev", "staging", "prod"]))
    suffix = draw(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1, max_size=10))
    return f"{prefix}_{suffix}"
```

---

## 4. Defect Density

### Metric

**Bugs per 1000 lines of code (KLOC).**

### Formula

```
Defect Density = (Total Bugs / Total Lines of Code) * 1000
```

### Industry Benchmarks

| Defect Density | Quality Level |
|----------------|---------------|
| <0.5 defects/KLOC | Excellent |
| 0.5-1.0 defects/KLOC | Good |
| 1.0-5.0 defects/KLOC | Average |
| >5.0 defects/KLOC | Poor |

### Tracking

```bash
# Count lines of code (exclude tests, docs, vendored)
cloc packages/*/src --exclude-dir=tests,docs,vendor

# Track defects in issue tracker with severity
# High priority bugs / KLOC
```

### Use in CI

Log defects found in production vs lines changed:

```yaml
# GitHub Actions example
- name: Track defect density
  run: |
    BUGS=$(gh issue list --label bug --state closed --search "closed:>$(date -d '30 days ago' +%Y-%m-%d)" | wc -l)
    LOC=$(cloc packages/*/src --csv --quiet | tail -1 | cut -d',' -f5)
    DENSITY=$(echo "scale=2; ($BUGS / $LOC) * 1000" | bc)
    echo "Defect density: $DENSITY defects/KLOC"
```

---

## 5. Mean Time to Detect (MTTD)

### Metric

**How long until tests catch a bug.**

### Target Times

| Test Tier | MTTD Target |
|-----------|-------------|
| Unit tests | ~seconds (immediate feedback) |
| Contract tests | ~1-2 minutes (fast CI) |
| Integration tests | ~5-10 minutes (Docker/K8s startup) |
| E2E tests | ~10-15 minutes (full pipeline) |

### Goal

**Catch bugs in unit/contract tests (fast feedback), not E2E.**

### Measurement

```bash
# Time from commit to test failure notification
git log --oneline --since="1 week ago" | while read commit; do
  # Check when tests failed
  gh run list --commit $commit --json status,createdAt
done
```

### Improvement Strategies

| Slow Detection | Solution |
|----------------|----------|
| Bug found in E2E tests | Add unit test for same scenario |
| Bug found in integration tests | Add contract test for interface |
| Bug found in manual QA | Add automated test at appropriate tier |
| Bug found in production | Incident postmortem → new tests |

---

## 6. Test Flakiness Rate

### Metric

**% of tests that fail intermittently (pass/fail without code changes).**

### Target

**0% flakiness.**

### Measurement

```bash
# Run tests multiple times
for i in {1..10}; do
  uv run pytest tests/ --quiet
done | grep FAILED | sort | uniq -c

# Tests failing <10 times = flaky
```

### Quarantine Pattern

If you must ship with flaky tests (not recommended):

```python
@pytest.mark.xfail(reason="Flaky due to race condition, tracking in #1234", strict=False)
def test_known_flaky():
    """Known flaky test - fix in progress."""
    # ...
```

**Better**: Fix the flakiness (add retries, fix race condition, use polling).

---

## Summary: Test Quality Dashboard

Track these metrics in CI:

```
===========================================
TEST QUALITY METRICS
===========================================
Requirement Traceability: 100% (24/24) ✅
Code Coverage:            87%          ✅
Mutation Score:           82%          ✅ (critical modules only)
Defect Density:           0.8/KLOC     ✅
MTTD (avg):               3.2 minutes  ✅
Flakiness Rate:           0%           ✅
===========================================
```

---

## External Resources

- **Mutation Testing**: https://mutmut.readthedocs.io/
- **Hypothesis**: https://hypothesis.readthedocs.io/
- **Property-Based Testing**: https://hypothesis.works/articles/what-is-property-based-testing/
- **Test Quality Metrics**: https://martinfowler.com/articles/testing-culture.html
