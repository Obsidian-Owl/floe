# Data Quality Quickstart

The floe Data Quality Plugin system provides automated, tiered validation for your data products. By combining compile-time gate enforcement with runtime quality scoring, floe ensures that only high-quality data reaches your consumers.

## Overview

floe supports a two-tier configuration model:
1.  **Platform Team** defines the `manifest.yaml` with plugin providers and quality gate policies.
2.  **Data Team** defines the `floe.yaml` with specific quality checks and selects a quality tier.

Quality is enforced through three tiers:
-   **Bronze**: Basic schema validation (connectivity, null checks).
-   **Silver**: Standard business rules and coverage requirements (80%+ coverage).
-   **Gold**: Critical data contracts with 100% test coverage and strict thresholds.

## Working Examples by Tier

### 1. Bronze Tier: Basic Connectivity

The Bronze tier focuses on ensuring the pipeline is connected and basic fields are present.

```yaml
# floe.yaml
name: raw_sales
version: "0.1.0"
quality_tier: bronze

transforms:
  - type: dbt
    name: stg_sales
    quality:
      checks:
        - name: sale_id_not_null
          type: not_null
          column: sale_id
          dimension: completeness
          severity: critical
        - name: transaction_date_present
          type: not_null
          column: transaction_date
          dimension: completeness
          severity: critical
```

### 2. Silver Tier: Standard Business Rules

The Silver tier adds requirements for uniqueness and data freshness.

```yaml
# floe.yaml
name: int_sales
version: "0.1.0"
quality_tier: silver

transforms:
  - type: dbt
    name: int_sales
    quality:
      checks:
        - name: sale_id_unique
          type: unique
          column: sale_id
          dimension: consistency
          severity: critical
        - name: amount_positive
          type: expect_column_values_to_be_between
          column: amount
          parameters:
            min_value: 0
          dimension: accuracy
          severity: warning
        - name: recent_data
          type: expect_row_values_to_be_recent
          column: updated_at
          parameters:
            max_age_hours: 24
          dimension: timeliness
          severity: critical
```

### 3. Gold Tier: Data Contracts

Gold tier requires 100% test coverage and strict validation of business logic.

```yaml
# floe.yaml
name: fct_sales
version: "0.1.0"
quality_tier: gold

transforms:
  - type: dbt
    name: fct_sales
    quality:
      checks:
        - name: currency_code_valid
          type: accepted_values
          column: currency_code
          parameters:
            values: ['USD', 'EUR', 'GBP', 'JPY']
          dimension: validity
          severity: critical
        - name: email_format
          type: expect_column_values_to_match_regex
          column: customer_email
          parameters:
            regex: '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
          dimension: validity
          severity: warning
        - name: total_matches_parts
          type: expect_column_sum_to_be_between
          column: total_amount
          parameters:
            min_value: 0
          dimension: consistency
          severity: critical
```

## Provider Selection

Configure your preferred provider in the `manifest.yaml`.

### Great Expectations (GX)
Best for comprehensive validation and complex cross-column expectations.

```yaml
# manifest.yaml
plugins:
  quality:
    provider: great_expectations
```

### dbt-expectations
Best for teams heavily invested in the dbt ecosystem who want to leverage existing tests.

```yaml
# manifest.yaml
plugins:
  quality:
    provider: dbt_expectations
```

## Quality Scoring Explained

floe calculates a unified quality score (0-100) using a three-layer model:

1.  **Dimension Weights**: Determines the importance of each quality category.
    -   **Completeness (0.25)**: Are fields populated?
    -   **Accuracy (0.25)**: Are values correct?
    -   **Validity (0.20)**: Does data follow rules?
    -   **Consistency (0.15)**: Is data coherent across sources?
    -   **Timeliness (0.15)**: Is data up-to-date?

2.  **Severity Weights**: Determines the impact of a specific check failure.
    -   `critical`: 3.0 weight
    -   `warning`: 1.0 weight
    -   `info`: 0.5 weight

3.  **Influence Capping**: Constrains how much any single check can swing the overall score, typically centered around a **Baseline Score of 70**.

## Error Code Quick Reference

If a quality gate or check fails, floe will emit one of the following error codes:

| Code | Error Name | Resolution |
|------|------------|------------|
| **FLOE-DQ001** | Provider Not Found | Check `plugins.quality.provider` in manifest.yaml |
| **FLOE-DQ102** | Quality Check Failed | Review runtime logs; score is below `min_score` |
| **FLOE-DQ103** | Coverage Violation | Add more tests to reach tier minimum (e.g., 80% for Silver) |
| **FLOE-DQ104** | Missing Required Tests | Add required tests like `not_null` or `unique` |
| **FLOE-DQ105** | Invalid Column | Verify the column name in your quality check matches the model |
| **FLOE-DQ106** | Check Timeout | Increase `check_timeout_seconds` or optimize your checks |
| **FLOE-DQ107** | Locked Override | You attempted to override a quality setting locked by the Platform Team |
