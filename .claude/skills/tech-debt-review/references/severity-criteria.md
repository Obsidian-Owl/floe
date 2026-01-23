# Severity Classification Criteria

This document defines the criteria for classifying technical debt findings by severity.

## Severity Levels

| Level | Definition | Action Required |
|-------|------------|-----------------|
| **CRITICAL** | Immediate risk to production or security | Fix before merge |
| **HIGH** | Significant maintainability or reliability risk | Fix this sprint |
| **MEDIUM** | Noticeable quality issue | Schedule in backlog |
| **LOW** | Minor improvement opportunity | Address opportunistically |

---

## Classification by Category

### Code Complexity

| Severity | Criteria |
|----------|----------|
| CRITICAL | Cyclomatic complexity > 30 OR cognitive > 40 |
| HIGH | Cyclomatic 20-30 OR cognitive 25-40 OR nesting > 6 |
| MEDIUM | Cyclomatic 10-20 OR cognitive 15-25 OR nesting 5-6 |
| LOW | Cyclomatic < 10 but > 7 OR method > 40 lines |

**Context Adjustments:**
- +1 severity if in critical business path
- +1 severity if high git churn
- -1 severity if well-documented and tested

### Dead Code

| Severity | Criteria |
|----------|----------|
| CRITICAL | Dead code in security-critical path |
| HIGH | Unreachable code after control flow OR unused public API |
| MEDIUM | Unused private functions OR > 10 lines commented code |
| LOW | Single unused import OR < 5 lines commented code |

**Context Adjustments:**
- +1 severity if dead code confuses active developers
- +1 severity if referenced in documentation
- -1 severity if clearly marked for future use

### Dependency Debt

| Severity | Criteria |
|----------|----------|
| CRITICAL | CVE with CVSS >= 9.0 OR known active exploit |
| HIGH | CVE with CVSS 7.0-8.9 OR > 2 major versions behind |
| MEDIUM | CVE with CVSS 4.0-6.9 OR 1-2 major versions behind |
| LOW | CVE with CVSS < 4.0 OR minor versions behind |

**Context Adjustments:**
- +1 severity if dependency is in request path
- +1 severity if handles user input
- -1 severity if only in dev dependencies

### Documentation Debt

| Severity | Criteria |
|----------|----------|
| CRITICAL | (Not typically critical) |
| HIGH | Missing docs on public API OR missing ADR for architecture |
| MEDIUM | Missing docstring on public function/class OR stale README |
| LOW | Missing docstring on private function OR minor comment issues |

**Context Adjustments:**
- +1 severity if external-facing API
- +1 severity if onboarding friction reported
- -1 severity if well-typed (types self-document)

### Testing Debt

| Severity | Criteria |
|----------|----------|
| CRITICAL | No tests for security-critical code |
| HIGH | < 50% coverage on critical paths OR flaky tests blocking CI |
| MEDIUM | < 80% coverage OR tests without assertions OR wrong tier |
| LOW | < 90% coverage OR minor test duplication |

**Context Adjustments:**
- +1 severity if recent production bug in untested area
- +1 severity if high complexity untested
- -1 severity if manual testing documented

### TODO Archaeology

| Severity | Criteria |
|----------|----------|
| CRITICAL | TODO blocking security fix OR data integrity |
| HIGH | XXX marker OR FIXME > 6 months OR TODO > 1 year |
| MEDIUM | FIXME < 6 months OR TODO 6-12 months OR HACK marker |
| LOW | TODO < 6 months with context |

**Context Adjustments:**
- +1 severity if linked issue is closed/resolved
- +1 severity if references deprecated API
- -1 severity if clearly scheduled in roadmap

### Git Hotspots

| Severity | Criteria |
|----------|----------|
| CRITICAL | > 30 changes in 3 months + high complexity + bug history |
| HIGH | > 20 changes in 3 months + high complexity |
| MEDIUM | > 10 changes in 3 months OR > 50% fix commits |
| LOW | > 5 changes in 3 months (watch list) |

**Context Adjustments:**
- +1 severity if merge conflicts frequent
- +1 severity if multiple developers struggling
- -1 severity if active feature development explains churn

### Performance Debt

| Severity | Criteria |
|----------|----------|
| CRITICAL | Memory leak pattern OR unbounded growth in production |
| HIGH | N+1 query in request path OR sync block in async code |
| MEDIUM | Missing cache for expensive operation OR inefficient algorithm |
| LOW | Minor optimization opportunity |

**Context Adjustments:**
- +1 severity if in high-traffic path
- +1 severity if user-facing latency
- -1 severity if only in background jobs

### Architecture Debt

| Severity | Criteria |
|----------|----------|
| CRITICAL | Circular dependency causing runtime issues |
| HIGH | Circular dependency OR god class (> 20 methods) |
| MEDIUM | High coupling (fan-out > 10) OR low cohesion |
| LOW | Minor pattern inconsistency |

**Context Adjustments:**
- +1 severity if blocking team velocity
- +1 severity if causing frequent merge conflicts
- -1 severity if isolated module

---

## Aggregation Rules

### When Multiple Issues Exist

```
Multiple CRITICAL → CRITICAL (aggregate)
CRITICAL + HIGH → CRITICAL with HIGH context
Multiple HIGH → HIGH (consider CRITICAL if > 5)
Multiple MEDIUM → MEDIUM (consider HIGH if > 10)
Multiple LOW → LOW (consider MEDIUM if > 20)
```

### Cross-Category Escalation

| Combination | Resulting Severity |
|-------------|-------------------|
| High complexity + Low coverage | +1 to both |
| High churn + Any debt | +1 to debt |
| Security vuln + Missing tests | CRITICAL |
| Circular dep + High complexity | +1 to architecture |

---

## Debt Score Impact

Severity contributes to overall debt score:

| Severity | Points Deducted | Cap |
|----------|-----------------|-----|
| CRITICAL | -10 each | -40 total |
| HIGH | -5 each | -30 total |
| MEDIUM | -2 each | -20 total |
| LOW | -1 each | -10 total |

**Score Ranges:**

| Score | Rating | Interpretation |
|-------|--------|----------------|
| 90-100 | Excellent | Minimal debt, maintain vigilance |
| 75-89 | Good | Manageable debt, address criticals |
| 60-74 | Needs Work | Growing debt, prioritize reduction |
| 40-59 | Poor | Significant debt, urgent attention |
| 0-39 | Critical | Severe debt, consider feature freeze |

---

## Override Conditions

### Always CRITICAL

- Active security exploit in the wild
- Data loss or corruption risk
- Compliance violation (GDPR, SOC2, etc.)
- Production incident root cause

### Never CRITICAL

- Style/formatting issues (linter handles)
- Single unused import
- Minor documentation gaps
- Cosmetic inconsistencies

---

## Evidence Requirements

Each severity classification should include:

| Severity | Evidence Required |
|----------|-------------------|
| CRITICAL | Specific file:line, reproduction steps, risk assessment |
| HIGH | Specific file:line, impact description |
| MEDIUM | File:line, category justification |
| LOW | File:line, improvement suggestion |

---

## Examples

### CRITICAL Example

```markdown
**Issue**: CVE-2024-12345 in requests==2.25.0
**Severity**: CRITICAL
**Evidence**:
- CVE: https://nvd.nist.gov/vuln/detail/CVE-2024-12345
- CVSS: 9.8 (Critical)
- Exploit: Publicly available
- Location: pyproject.toml:15
**Risk**: Remote code execution via crafted HTTP response
**Fix**: Update to requests>=2.31.0
```

### HIGH Example

```markdown
**Issue**: Cyclomatic complexity 28 in process_order()
**Severity**: HIGH
**Evidence**:
- Location: services/orders.py:145
- Complexity: 28 (threshold: 10)
- Git churn: 15 changes in 3 months
**Risk**: Bug introduction, difficult maintenance
**Fix**: Extract validation, payment, shipping into separate methods
```

### MEDIUM Example

```markdown
**Issue**: TODO older than 6 months
**Severity**: MEDIUM
**Evidence**:
- Location: utils/parser.py:67
- Comment: "TODO: Handle edge case for empty input"
- Age: 8 months (git blame: 2025-05-15)
- Linked issue: GH-234 (still open)
**Risk**: Potential bug if edge case encountered
**Fix**: Implement edge case handling or document as known limitation
```

### LOW Example

```markdown
**Issue**: Missing docstring on private helper
**Severity**: LOW
**Evidence**:
- Location: utils/helpers.py:23
- Function: _normalize_key()
- Type hints: Present
**Risk**: Minor documentation gap
**Fix**: Add docstring explaining normalization rules
```
