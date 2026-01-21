# Technical Debt Taxonomy

This document defines the complete taxonomy of technical debt categories analyzed by the `/tech-debt-review` skill.

## Overview

Technical debt is categorized into **9 primary categories**, each with specific subcategories and detection methods.

---

## 1. Code Complexity

**Agent**: code-complexity-analyzer (Haiku)

### Subcategories

| Type | Definition | Threshold |
|------|------------|-----------|
| Cyclomatic Complexity | Number of linearly independent paths | > 10 |
| Cognitive Complexity | Mental effort to understand code | > 15 |
| Nesting Depth | Levels of indentation | > 4 |
| Method Length | Lines of code in function | > 50 |
| Parameter Count | Number of function parameters | > 5 |
| Class Size | Methods + attributes in class | > 20 |

### Examples

```python
# HIGH cyclomatic complexity (multiple branches)
def process(data):
    if data.type == "A":
        if data.status == "active":
            if data.valid:
                ...  # Many more branches

# HIGH cognitive complexity (hard to understand)
def calculate(x, y, z, a, b, c, flag1, flag2):
    result = x if flag1 else y
    return (result * z if flag2 else result / a) + (b if flag1 and flag2 else c)
```

---

## 2. Dead Code

**Agent**: dead-code-detector (Sonnet)

### Subcategories

| Type | Definition | Detection |
|------|------------|-----------|
| Unreachable Code | Code after return/raise/break | Control flow analysis |
| Unused Functions | Functions never called | Import graph + call analysis |
| Unused Imports | Imports never referenced | AST analysis |
| Commented Code | Large blocks of commented code | Pattern matching (>5 lines) |
| Dead Branches | Conditions always true/false | Static analysis |
| Unused Variables | Variables assigned but not used | Scope analysis |
| Obsolete Features | Feature flags always on/off | Configuration analysis |

### Examples

```python
# Unreachable code
def example():
    return 42
    print("Never executed")  # Dead

# Unused function
def helper():  # Never called anywhere
    pass

# Commented code block
# def old_implementation():
#     do_something()
#     do_something_else()
#     return result
```

---

## 3. Dependency Debt

**Agent**: dependency-debt-analyzer (Sonnet)

### Subcategories

| Type | Definition | Risk Level |
|------|------------|------------|
| Security Vulnerabilities | Known CVEs | CRITICAL |
| Major Version Behind | >1 major version outdated | HIGH |
| Minor Version Behind | >3 minor versions outdated | MEDIUM |
| Unused Dependencies | Installed but not imported | LOW |
| Unpinned Dependencies | No version constraint | MEDIUM |
| Deprecated Packages | No longer maintained | HIGH |
| License Issues | Incompatible licenses | MEDIUM |

### Examples

```toml
# pyproject.toml issues
[tool.poetry.dependencies]
requests = "*"           # Unpinned (MEDIUM)
django = "^2.0"         # Major behind (HIGH)
leftpad = "^1.0"        # Deprecated (HIGH)
```

---

## 4. Documentation Debt

**Agent**: documentation-debt-analyzer (Haiku)

### Subcategories

| Type | Definition | Severity |
|------|------------|----------|
| Missing Module Docstring | No module-level documentation | MEDIUM |
| Missing Function Docstring | Public function undocumented | MEDIUM |
| Missing Class Docstring | Public class undocumented | MEDIUM |
| Stale Comments | Comments referencing old code | LOW |
| Missing Type Hints | Functions without type annotations | MEDIUM |
| Outdated README | README doesn't match current state | LOW |
| Missing ADRs | Architecture decisions undocumented | HIGH |

### Examples

```python
# Missing docstrings
def process_data(data, config, options):  # What does this do?
    return transform(data)

# Stale comment
# TODO: Use the new API (v2 released 2023)
response = old_api.call()
```

---

## 5. Testing Debt

**Agents**: testing-debt-analyzer (Sonnet), test-duplication-detector (Sonnet)

### Subcategories

| Type | Definition | Severity |
|------|------------|----------|
| Coverage Gap | Untested code paths | HIGH if critical path |
| Missing Edge Cases | No boundary testing | MEDIUM |
| Flaky Tests | Non-deterministic tests | HIGH |
| Slow Tests | Tests > 10s | MEDIUM |
| Tests Without Assertions | Tests that pass trivially | HIGH |
| Test Duplication | Redundant tests | LOW |
| Integration in Unit | Wrong test tier | MEDIUM |

### Examples

```python
# Test without assertion
def test_something():
    result = process()  # No assert!

# Flaky test
def test_timing():
    time.sleep(0.1)  # Race condition risk
    assert ready()
```

---

## 6. TODO Archaeology

**Agent**: todo-archaeology (Haiku)

### Subcategories

| Type | Age | Severity |
|------|-----|----------|
| Recent TODO | < 1 month | LOW |
| Aging TODO | 1-6 months | MEDIUM |
| Ancient TODO | > 6 months | HIGH |
| FIXME | Any age | +1 severity |
| HACK | Any age | +1 severity |
| XXX | Any age | HIGH |

### Context Analysis

| Pattern | Interpretation |
|---------|----------------|
| Links to closed issues | Orphaned TODO |
| References removed code | Stale TODO |
| No context | Unclear TODO |
| "Temporary" | Likely permanent |

### Examples

```python
# Ancient TODO (HIGH)
# TODO: Fix this when we upgrade to Python 3.8 (2020-01-15)

# Orphaned TODO (MEDIUM)
# TODO: See GH-123 for details  # Issue closed 6 months ago

# Unclear TODO (MEDIUM)
# TODO: Fix this
```

---

## 7. Git Hotspots

**Agent**: git-hotspot-analyzer (Sonnet)

### Subcategories

| Type | Definition | Indicator |
|------|------------|-----------|
| High Churn | Frequently modified files | > 10 changes/3 months |
| Bug Magnet | Files with many fix commits | > 50% fix commits |
| Large Commits | Commits with many changes | > 500 lines |
| Long-Lived Branches | Branches not merged | > 2 weeks |
| Merge Conflict Prone | Files often conflicting | > 3 conflicts/month |

### Churn Analysis

```
High churn + High complexity = Technical debt priority
High churn + Low complexity = Normal active development
Low churn + High complexity = Potential hidden debt
```

---

## 8. Performance Debt

**Agent**: performance-debt-detector (Sonnet)

### Subcategories

| Type | Definition | Severity |
|------|------------|----------|
| N+1 Query | Loop with database calls | HIGH |
| Sync in Async | Blocking calls in async code | HIGH |
| Missing Cache | Repeated expensive operations | MEDIUM |
| Unbounded Collection | Growing collections without limits | HIGH |
| Inefficient Algorithm | O(n^2) or worse patterns | MEDIUM |
| Missing Index | ORM queries without DB indexes | MEDIUM |
| Memory Leak Pattern | Resources not released | HIGH |

### Examples

```python
# N+1 query pattern (HIGH)
for user in users:
    orders = db.query(Order).filter(Order.user_id == user.id).all()

# Sync in async (HIGH)
async def handler():
    time.sleep(1)  # Blocks event loop!

# Unbounded collection (HIGH)
cache = {}
def add_to_cache(key, value):
    cache[key] = value  # Never cleared!
```

---

## 9. Architecture Debt

**Agent**: code-pattern-reviewer (Sonnet)

### Subcategories

| Type | Definition | Severity |
|------|------------|----------|
| Circular Dependencies | Modules import each other | HIGH |
| God Class/Module | Too many responsibilities | HIGH |
| Feature Envy | Class uses another's data | MEDIUM |
| Shotgun Surgery | Change requires many edits | HIGH |
| Inappropriate Intimacy | Direct access to internals | MEDIUM |
| High Coupling | Too many dependencies | MEDIUM |
| Low Cohesion | Unrelated code grouped | MEDIUM |

### Coupling Metrics

| Metric | Threshold | Meaning |
|--------|-----------|---------|
| Fan-out | > 10 | Module imports too many |
| Fan-in | > 15 | Module imported by too many |
| Instability | < 0.3 or > 0.7 | Coupling imbalance |

---

## Cross-Category Correlations

Certain combinations indicate systemic issues:

| Pattern | Categories | Interpretation |
|---------|------------|----------------|
| High churn + High complexity | Hotspots + Complexity | Refactoring priority |
| Many TODOs + Low coverage | TODOs + Testing | Technical debt avoidance |
| Circular deps + God class | Architecture x2 | Architecture overhaul needed |
| Security vulns + Outdated deps | Dependencies x2 | Maintenance neglect |

---

## Remediation Effort Estimation

| Category | Low Effort | Medium Effort | High Effort |
|----------|------------|---------------|-------------|
| Complexity | Extract method | Split class | Redesign module |
| Dead Code | Delete unused | Analyze dependencies | Refactor callers |
| Dependencies | Update minor | Update major | Replace package |
| Documentation | Add docstring | Write guide | Create ADR |
| Testing | Add test | Increase coverage | Refactor flaky |
| TODOs | Address or delete | Implement feature | Major change |
| Hotspots | Code review | Refactor | Redesign |
| Performance | Add cache | Optimize query | Rearchitect |
| Architecture | Extract interface | Break cycle | Restructure |

---

## References

- [Code Climate Technical Debt Assessment](https://codeclimate.com/blog/10-point-technical-debt-assessment)
- [SonarQube Technical Debt Guide](https://www.sonarsource.com/learn/measuring-and-identifying-code-level-technical-debt-a-practical-guide/)
- [CodeScene Technical Debt Analysis](https://codescene.com/technical-debt)
