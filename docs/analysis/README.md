# Code Complexity Analysis Reports

This directory contains complexity analysis reports for the floe codebase.

## Reports

### 2026-01-22 Analysis (Latest)

- **Summary**: `complexity-analysis-2026-01-22.md` - Executive summary with key findings and refactoring recommendations
- **Raw Metrics**: `complexity-metrics-2026-01-22.json` - Detailed metrics data in JSON format for trending and tooling

## Key Findings (2026-01-22)

| Metric | Value | Status |
|--------|-------|--------|
| Total Functions | 982 | - |
| Total Classes | 282 | - |
| Critical Complexity (>20) | 1 | CRITICAL |
| High Complexity (15-20) | 7 | HIGH |
| Medium Complexity (10-15) | 22 | MEDIUM |
| Low Complexity (≤10) | 952 | GOOD |
| Average Cyclomatic | 2.1 | EXCELLENT |

## Critical Issue

**map_pyiceberg_error()** - Cyclomatic 26
- File: `plugins/floe-catalog-polaris/src/floe_catalog_polaris/errors.py:51`
- Refactoring: Use error mapping dictionary (Strategy Pattern)
- Effort: 1-2 hours | Risk: LOW

See `complexity-analysis-2026-01-22.md` for full details and refactoring guidance.

## High Priority Functions (7)

1. `__getattr__()` - Cyclomatic 18
2. `audit_command()` - Cyclomatic 18
3. `validate_security_policy_not_weakened()` - Cyclomatic 17
4. `enforce()` - Cyclomatic 17
5. `validate()` (token_validator) - Cyclomatic 17
6. `list_secrets()` - Cyclomatic 16
7. `pull()` (OCI client) - Cyclomatic 15

Total refactoring effort: 4-6 hours across all high-complexity functions.

## Trend Analysis

Run monthly analysis to track complexity trends:

```bash
# Generate new analysis
python3 /tmp/analyze_complexity_filtered.py > docs/analysis/complexity-metrics-YYYY-MM-DD.json

# Compare against baseline
# Are we improving or degrading?
```

## Next Steps

1. **Immediate** (This Sprint):
   - Create Linear issues for CRITICAL and HIGH refactorings
   - Schedule work

2. **Priority 1** (Next Sprint - 1-2 hours):
   - Refactor `map_pyiceberg_error()` to use error mapping dictionary

3. **Priority 2** (Following Sprint - 4-6 hours):
   - Refactor remaining HIGH complexity functions

4. **Ongoing** (Monitoring):
   - Monthly complexity analysis
   - Code review standards: flag functions >10 cyclomatic
   - CI/CD integration: fail PR if new critical complexity

## Understanding the Metrics

**Cyclomatic Complexity**: Count of linearly independent paths
- Threshold: 10 (MEDIUM), 20 (CRITICAL)
- Counts: if/elif/else (+1), for/while (+1), try/except (+1), and/or operators (+1)

**Cognitive Complexity**: Mental effort to understand code
- Threshold: 15 (MEDIUM), 25 (CRITICAL)

**Nesting Depth**: Maximum levels of nested control structures
- Threshold: 4 (MEDIUM), 6 (CRITICAL)

**Function Length**: Lines of code
- Threshold: 50 (MEDIUM), 100 (HIGH)

**Class Size**: Method count
- Threshold: 10 (MEDIUM), 20 (HIGH)

## References

- Full report: `complexity-analysis-2026-01-22.md`
- Raw metrics: `complexity-metrics-2026-01-22.json`
- Generated: 2026-01-22
- Next analysis: 2026-02-22
