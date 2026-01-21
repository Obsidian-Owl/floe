# Technical Debt Prioritization Framework

This document defines how technical debt findings are prioritized for remediation.

## Priority Formula

```
Priority Score = (Risk x Impact) / Effort
```

Where:
- **Risk**: Likelihood of causing problems (1-5)
- **Impact**: Severity when problems occur (1-5)
- **Effort**: Work required to fix (1-5, where 1 = easy)

### Priority Tiers

| Score | Priority | Action |
|-------|----------|--------|
| >= 5.0 | P0 (Critical) | Fix immediately, block PR if present |
| 2.5 - 4.9 | P1 (High) | Fix this sprint |
| 1.0 - 2.4 | P2 (Medium) | Schedule for backlog |
| < 1.0 | P3 (Low) | Address opportunistically |

---

## Risk Assessment

### Risk Level Definitions

| Level | Score | Definition | Examples |
|-------|-------|------------|----------|
| Critical | 5 | Will cause failure | Security vuln, data loss |
| High | 4 | Likely to cause issues | Flaky tests, memory leak |
| Moderate | 3 | May cause issues | High complexity, missing docs |
| Low | 2 | Unlikely to cause issues | Minor code smell |
| Minimal | 1 | No direct risk | Style inconsistency |

### Risk by Category

| Category | Default Risk | Adjustments |
|----------|--------------|-------------|
| Security Vulnerabilities | 5 | - |
| Circular Dependencies | 4 | +1 if in critical path |
| N+1 Queries | 4 | +1 in high-traffic code |
| Flaky Tests | 4 | +1 if blocking CI |
| Missing Tests | 3 | +1 for critical paths |
| High Complexity | 3 | +1 if frequently changed |
| Dead Code | 2 | +1 if confuses developers |
| TODOs | 2 | +1 if > 1 year old |
| Documentation | 2 | +1 for public APIs |

---

## Impact Assessment

### Impact Level Definitions

| Level | Score | Definition | Examples |
|-------|-------|------------|----------|
| Critical | 5 | System failure | Production outage, data breach |
| High | 4 | Major degradation | Feature broken, significant slowdown |
| Moderate | 3 | Noticeable issues | User confusion, minor slowdown |
| Low | 2 | Minor inconvenience | Developer friction |
| Minimal | 1 | Cosmetic | Style inconsistency |

### Impact Multipliers

| Factor | Multiplier | Condition |
|--------|------------|-----------|
| Critical Path | x1.5 | Code in main business flow |
| High Traffic | x1.5 | Code handling > 1000 req/min |
| External API | x1.3 | Affects public interfaces |
| Data Handling | x1.3 | Touches sensitive data |
| Shared Code | x1.2 | Used by multiple teams |

---

## Effort Assessment

### Effort Level Definitions

| Level | Score | Time | Examples |
|-------|-------|------|----------|
| Trivial | 1 | < 30 min | Delete unused import |
| Low | 2 | 30 min - 2 hr | Add docstring, simple fix |
| Medium | 3 | 2 hr - 1 day | Refactor function, add tests |
| High | 4 | 1-5 days | Major refactor, new tests |
| Very High | 5 | > 5 days | Architecture change |

### Effort Estimation Guidelines

| Category | Typical Effort | Notes |
|----------|----------------|-------|
| Update dependency | 1-2 | If no breaking changes |
| Delete dead code | 1-2 | Verify no hidden usage |
| Add docstring | 1 | If code is understood |
| Fix N+1 query | 2-3 | Depends on ORM complexity |
| Break circular dep | 3-4 | May require design change |
| Increase coverage | 3-4 | Per 10% coverage increase |
| Reduce complexity | 3-4 | Extract method/class |
| Address TODOs | 2-4 | Depends on TODO scope |

---

## Priority Matrix

### Quick Reference

| Risk | Impact | Effort | Score | Priority |
|------|--------|--------|-------|----------|
| 5 | 5 | 1 | 25.0 | P0 |
| 5 | 5 | 3 | 8.3 | P0 |
| 5 | 3 | 2 | 7.5 | P0 |
| 4 | 4 | 3 | 5.3 | P0 |
| 4 | 3 | 3 | 4.0 | P1 |
| 3 | 3 | 3 | 3.0 | P1 |
| 3 | 3 | 4 | 2.25 | P2 |
| 2 | 3 | 4 | 1.5 | P2 |
| 2 | 2 | 3 | 1.3 | P2 |
| 2 | 2 | 5 | 0.8 | P3 |
| 1 | 2 | 4 | 0.5 | P3 |

### Category Defaults

| Category | Typical Priority | Rationale |
|----------|------------------|-----------|
| CVE (Critical) | P0 | High risk, high impact, low effort |
| CVE (High) | P0-P1 | High risk, varies by effort |
| Circular Dependency | P1 | High impact, medium effort |
| God Class | P1-P2 | High impact, high effort |
| N+1 Query | P1 | High risk in production |
| Flaky Test | P1 | Blocks development |
| Missing Critical Test | P1 | Risk of regression |
| High Complexity | P2 | Moderate risk, varies |
| Ancient TODO | P2-P3 | Low risk, low effort |
| Missing Docstring | P3 | Low impact, low effort |
| Unused Import | P3 | Trivial fix |

---

## Batch Prioritization

When reviewing multiple issues, consider:

### Dependencies Between Issues

```
Issue A blocks Issue B → Prioritize A higher
Issue A + Issue B in same file → Batch together
Issue A affects Issue B's area → Consider together
```

### Effort Optimization

```
3 x P3 issues in same file → May be worth P2 effort
P1 issue near P3 issue → Fix P3 while there
Related issues → Single refactoring session
```

### Sprint Planning

| Sprint Goal | Prioritization Approach |
|-------------|------------------------|
| Stability | P0 and P1 first |
| Velocity | P2 and P3 batches |
| Quality | Coverage and doc debt |
| Performance | Performance category first |

---

## Priority Overrides

### Always P0 (Regardless of Formula)

- Active security vulnerability (CVE with exploit)
- Data loss risk
- Production incident related
- Compliance violation

### Always P3 (Unless Explicitly Escalated)

- Style-only issues (handled by linters)
- Single unused import
- Minor documentation formatting
- Cosmetic inconsistencies

---

## Tracking and Trends

### When to Re-prioritize

| Trigger | Action |
|---------|--------|
| New CVE announced | Re-assess dependency debt |
| Production incident | Re-assess related areas |
| Code churn increase | Re-assess hotspot priorities |
| Sprint planning | Review P2 backlog |

### Debt Budget

Recommended allocation per sprint:
- 10-20% of capacity for P1-P2 debt
- P0 debt: Immediate, outside budget
- P3 debt: Opportunistic only

---

## Examples

### Example 1: CVE in Production Dependency

```
Category: Dependency Debt
Issue: CVE-2024-XXXXX (CVSS 9.1) in requests==2.25.0
Risk: 5 (Critical - known exploit)
Impact: 5 (Critical - data breach possible)
Effort: 1 (Trivial - just update version)
Score: (5 x 5) / 1 = 25.0
Priority: P0
```

### Example 2: Complex Function

```
Category: Code Complexity
Issue: Cyclomatic complexity 25 in process_order()
Risk: 3 (Moderate - may cause bugs)
Impact: 4 (High - core business logic)
Effort: 4 (High - needs careful refactoring)
Score: (3 x 4) / 4 = 3.0
Priority: P1
```

### Example 3: Missing Docstring

```
Category: Documentation Debt
Issue: Missing docstring on internal helper
Risk: 1 (Minimal - no direct risk)
Impact: 2 (Low - developer confusion)
Effort: 1 (Trivial - quick to add)
Score: (1 x 2) / 1 = 2.0
Priority: P2
```

### Example 4: Ancient TODO

```
Category: TODO Archaeology
Issue: TODO from 2023-01-15, unclear context
Risk: 2 (Low - no immediate risk)
Impact: 2 (Low - technical debt indicator)
Effort: 3 (Medium - need to research context)
Score: (2 x 2) / 3 = 1.3
Priority: P2
```
