# Data Quality Plugin Quickstart

**Epic**: 5B | **Status**: Planning Complete

## Overview

The Data Quality Plugin provides compile-time validation and runtime quality checks for floe data products. It supports a three-tier scoring model (dimensions → severity → calculation parameters) with inheritance control (Enterprise → Domain → Product).

## Quick Setup

### 1. Configure Quality Provider (Platform Team)

In `manifest.yaml`:

```yaml
plugins:
  quality:
    provider: great_expectations  # or: dbt_expectations
    quality_gates:
      bronze:
        min_test_coverage: 50
        required_tests: []
        min_score: 60
      silver:
        min_test_coverage: 80
        required_tests: [not_null, unique]
        min_score: 75
      gold:
        min_test_coverage: 100
        required_tests: [not_null, unique, accepted_values, relationships]
        min_score: 90
        overridable: false  # Lock for gold tier
```

### 2. Define Quality Checks (Data Engineer)

In `floe.yaml`:

```yaml
models:
  - name: dim_customers
    tier: gold
    quality_checks:
      - name: customer_id_not_null
        type: not_null
        column: customer_id
        dimension: completeness
        severity: critical

      - name: email_valid_format
        type: expect_column_values_to_match_regex
        column: email
        dimension: validity
        severity: warning
        parameters:
          regex: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

      - name: age_reasonable_range
        type: expect_column_values_to_be_between
        column: age
        dimension: accuracy
        severity: warning
        parameters:
          min_value: 0
          max_value: 150
```

### 3. Run Quality Checks

```bash
# Compile (validates quality gates)
floe compile

# Run pipeline (quality checks execute after each model)
floe run
```

## Quality Dimensions

| Dimension | Example Checks | Default Weight |
|-----------|----------------|----------------|
| **Completeness** | not_null, expect_column_to_exist | 0.25 |
| **Accuracy** | expect_column_values_to_be_between, expect_column_mean_to_be_between | 0.25 |
| **Validity** | expect_column_values_to_match_regex, accepted_values | 0.20 |
| **Consistency** | expect_compound_columns_to_be_unique, relationships | 0.15 |
| **Timeliness** | Custom timestamp checks | 0.15 |

## Severity Levels

| Level | Weight | Use Case |
|-------|--------|----------|
| `critical` | 3.0 | Data integrity issues (PKs, FKs) |
| `warning` | 1.0 | Business rule violations |
| `info` | 0.5 | Nice-to-have validations |

## Score Calculation

```
1. Per-dimension score = weighted average of check results (by severity)
2. Overall score = weighted average of dimension scores (by dimension weights)
3. Final score = baseline ± influence (capped to prevent extreme swings)
```

**Default Parameters**:
- Baseline: 70
- Max positive influence: +30 (max score: 100)
- Max negative influence: -50 (min score: 20)

## Three-Tier Inheritance

```
Enterprise (manifest.yaml - Platform Team)
    ↓
Domain (domain-manifest.yaml - optional)
    ↓
Product (floe.yaml - Data Engineer)
```

**Lock Control**: Settings with `overridable: false` cannot be changed at lower levels.

```yaml
# Enterprise manifest
quality_gates:
  gold:
    min_score: 90
    overridable: false  # Products cannot lower this
```

## Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| FLOE-DQ001 | Invalid quality provider | Check `plugins.quality.provider` |
| FLOE-DQ102 | Quality checks failed | Review failed checks in output |
| FLOE-DQ103 | Coverage below tier minimum | Add more tests |
| FLOE-DQ104 | Missing required tests | Add required test types |
| FLOE-DQ105 | Invalid column reference | Verify column exists |
| FLOE-DQ106 | Check timeout | Increase timeout or optimize |
| FLOE-DQ107 | Override of locked setting | Remove override from floe.yaml |

## Provider Implementations

### Great Expectations (`floe-quality-gx`)

```bash
pip install floe-quality-gx
```

- Native GX Core 1.0+ integration
- Supports DuckDB, PostgreSQL, Snowflake
- Full expectation suite support

### dbt-expectations (`floe-quality-dbt`)

```bash
pip install floe-quality-dbt
```

- Executes via `DBTPlugin.test_models()`
- Leverages existing dbt test infrastructure
- Unified scoring with dbt tests

## Integration with dbt Tests

Both dbt generic tests (schema.yml) and floe quality checks contribute to the unified quality score:

```yaml
# schema.yml (dbt tests)
models:
  - name: dim_customers
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique

# floe.yaml (additional quality checks)
models:
  - name: dim_customers
    quality_checks:
      - name: email_valid
        type: expect_column_values_to_match_regex
        # ...
```

Both are aggregated into a single `QualityScore`:
- `dbt_tests_passed` / `dbt_tests_failed` - from dbt
- `checks_passed` / `checks_failed` - from quality plugin
- `overall` - weighted combination

## Next Steps

1. Install your preferred quality provider
2. Configure quality gates in manifest.yaml
3. Add quality checks to your models
4. Run `floe compile` to validate
5. Run `floe run` to execute with quality checks
