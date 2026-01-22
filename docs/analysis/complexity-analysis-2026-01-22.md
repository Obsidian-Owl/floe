# Code Complexity Analysis Report: floe Codebase

**Generated:** 2026-01-22
**Scope:** packages/ and plugins/ directories (982 functions, 282 classes)
**Status:** GOOD - 87% of functions have LOW complexity (≤5)

## Executive Summary

| Metric | Count | Status |
|--------|-------|--------|
| Critical Complexity (>20) | 1 | CRITICAL |
| High Complexity (15-20) | 7 | HIGH |
| Medium Complexity (10-15) | 22 | MEDIUM |
| Deep Nesting (>4) | 13 | MEDIUM |
| Long Functions (>100 lines) | 25 | HIGH |
| Large Classes (>20 methods) | 3 | HIGH |

## Critical Issue (Immediate Action)

### map_pyiceberg_error() - Cyclomatic 26
**File:** plugins/floe-catalog-polaris/src/floe_catalog_polaris/errors.py:51
**Issue:** 16 consecutive if-statements for exception mapping
**Refactoring:** Apply strategy pattern with dispatch dictionary
**Effort:** 1-2 hours

**Suggested refactor:**
```python
ERROR_HANDLERS = {
    ServiceUnavailableError: _handle_unavailable,
    UnauthorizedError: _handle_unauthorized,
    # ... map each error type
}

def map_pyiceberg_error(error, catalog_uri=None, operation=None):
    handler = ERROR_HANDLERS.get(type(error))
    return handler(error, catalog_uri, operation) if handler else _handle_unknown(error)
```

## High Complexity Functions (7 total)

| Function | File | Cyclomatic | Nesting | Length | Refactoring |
|----------|------|-----------|---------|--------|-------------|
| __getattr__ | rbac/__init__.py | 18 | 1 | 75 | Dispatch table (30 min) |
| audit_command | cli/rbac/audit.py | 18 | 4 | 129 | Flatten nesting + extract (1-2 hrs) |
| validate_security_policy_not_weakened | schemas/validation.py | 17 | 2 | 85 | Extract validators (1 hr) |
| enforce | enforcement/policy_enforcer.py | 17 | 3 | 124 | Separate validation phases (1-2 hrs) |
| validate | identity-keycloak/token_validator.py | 17 | 3 | 144 | Extract sub-methods (1 hr) |
| list_secrets | secrets-infisical/plugin.py | 16 | 2 | 99 | Extract pagination/filtering (1 hr) |
| pull | oci/client.py | 15 | 5 | 166 | Extract retry logic (1 hr) |

## Distribution Analysis

**Cyclomatic Complexity Distribution:**
- 1-5 (Low): 862 functions (87.8%)
- 6-10 (Medium): 98 functions (10.0%)
- 11-20 (High): 21 functions (2.1%)
- 21-30 (Critical): 1 function (0.1%)

**Assessment:** Excellent distribution - most functions are simple.

## Class Size Analysis

**Top 5 Classes by Method Count:**
1. OCIClient - 27 methods (floe-core/oci/client.py)
2. IcebergTableManager - 23 methods (floe-iceberg/manager.py)
3. KeycloakIdentityPlugin - 22 methods (floe-identity-keycloak/plugin.py)
4. PluginRegistry - 20 methods (floe-core/plugin_registry.py)
5. PolicyEnforcer - 20 methods (floe-core/enforcement/policy_enforcer.py)

**Observation:** These are facade/orchestrator classes. Consider splitting if methods are independent.

## Nesting Depth Issues (13 functions)

Functions with nesting > 4 levels:
- _analyze_files_for_compaction (depth 7) - iceberg/compaction.py:174
- pull (depth 5) - oci/client.py:660
- audit_command (depth 4) - cli/rbac/audit.py:68

**Refactoring:** Extract inner loop logic to separate methods to reduce depth.

## Action Plan

### Priority 1 (This Sprint)
- [ ] Refactor map_pyiceberg_error() to use dispatch pattern
- [ ] Create Linear issue for refactoring

### Priority 2 (Next Sprint)
- [ ] Simplify __getattr__() with dispatch table
- [ ] Flatten nesting in audit_command()
- [ ] Extract validators in validate_security_policy_not_weakened()

### Priority 3 (Future)
- [ ] Review 123 functions > 50 lines for extraction
- [ ] Consider breaking OCIClient into focused classes
- [ ] Monitor functions > 100 lines during code review

## Quality Assessment

**Overall Grade: GOOD**

Strengths:
- 87% of functions are simple (cyclomatic ≤ 5)
- Minimal nesting issues (1.3% exceed depth 4)
- Good class design (only 1.1% have >20 methods)

Improvements:
- 1 critical cyclomatic issue (map_pyiceberg_error)
- 7 high complexity functions need refactoring
- 25 functions exceed 100 lines

**Conclusion:** Codebase is maintainable with focused improvements needed on error handling and validation logic.

---

See full report in: `/docs/analysis/complexity-analysis-full-2026-01-22.md`
