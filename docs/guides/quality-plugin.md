# Data Quality Plugin Configuration Reference

The floe Data Quality Plugin system allows platform teams to enforce data quality standards across the enterprise while giving data teams the flexibility to define specific checks for their data products.

## Overview

Configuration is managed at two levels:
1.  **`manifest.yaml`**: Managed by the Platform Team. Defines the quality provider, global dimension weights, and quality gate policies (Bronze, Silver, Gold).
2.  **`floe.yaml`**: Managed by Data Teams. Defines specific quality checks for models and selects the desired quality tier.

## manifest.yaml Configuration

The `quality` section in `manifest.yaml` controls the global behavior of the quality system.

```yaml
plugins:
  quality:
    provider: great_expectations      # required: great_expectations or dbt_expectations
    enabled: true                     # default: true
    check_timeout_seconds: 300        # default: 300
    
    # Layer 1: Global Dimension Weights (must sum to 1.0)
    dimension_weights:
      completeness: 0.25
      accuracy: 0.25
      validity: 0.20
      consistency: 0.15
      timeliness: 0.15
      
    # Layer 3: Score Calculation Parameters
    calculation:
      baseline_score: 70              # starting score before checks
      max_positive_influence: 30       # max increase (70 + 30 = 100)
      max_negative_influence: 50       # max decrease (70 - 50 = 20)
      severity_weights:
        critical: 3.0
        warning: 1.0
        info: 0.5
        
    # Global Thresholds
    thresholds:
      min_score: 70                   # score below this blocks deployment/run
      warn_score: 85                  # score below this emits warnings
      
    # Quality Gate Policies
    quality_gates:
      bronze:
        min_test_coverage: 0          # % of columns that must have tests
        required_tests: []            # tests that must be present
        min_score: 0                  # minimum score for this tier
      silver:
        min_test_coverage: 80
        required_tests: ["not_null", "unique"]
        min_score: 75
      gold:
        min_test_coverage: 100
        required_tests: ["not_null", "unique", "accepted_values", "relationships"]
        min_score: 90
        overridable: false            # prevent lower levels from weakening gold tier
```

### QualityGateConfig Options

| Option | Type | Description |
|--------|------|-------------|
| `min_test_coverage` | `float` | Minimum percentage of columns that must have at least one quality check. |
| `required_tests` | `list[str]` | List of test types (e.g., `not_null`, `unique`) that MUST be present for every model in this tier. |
| `min_score` | `int` | The minimum `QualityScore` (0-100) required for models in this tier. |
| `overridable` | `bool` | If `false`, lower levels (Domain/Product) cannot modify these settings. |

## floe.yaml Configuration

Data teams define specific checks for their transforms in the `quality` section.

```yaml
transforms:
  - name: dim_customers
    type: dbt
    quality_tier: gold                # selects policy from manifest.yaml
    quality:
      checks:
        - name: id_not_null           # unique identifier for the check
          type: not_null              # check type (provider-specific)
          column: customer_id         # target column
          dimension: completeness     # completeness, accuracy, validity, consistency, timeliness
          severity: critical          # critical, warning, info
          parameters:                 # optional parameters for the check
            custom_arg: value
          enabled: true               # default: true
```

### QualityCheck Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Unique identifier for the check within the model. |
| `type` | `str` | Yes | The type of check (e.g., `not_null`, `unique`, `expect_column_values_to_be_between`). |
| `column` | `str` | No | Target column name. Omit for table-level checks. |
| `dimension` | `Dimension` | Yes | The quality dimension: `completeness`, `accuracy`, `validity`, `consistency`, or `timeliness`. |
| `severity` | `Severity` | No | Impact of failure: `critical` (default), `warning`, or `info`. |
| `custom_weight`| `float` | No | Override the default severity weight (0.1 - 10.0). |
| `parameters` | `dict` | No | Dictionary of parameters passed to the quality provider. |
| `enabled` | `bool` | No | Whether the check should be executed (default: `true`). |

## Three-Tier Inheritance Model

floe uses a hierarchical configuration model that allows for central governance with local flexibility.

1.  **Enterprise Level (`manifest.yaml`)**: Sets global standards and "locked" policies.
2.  **Domain Level (`domain.yaml`)**: (Optional) Refines standards for a specific business domain.
3.  **Product Level (`floe.yaml`)**: Implements specific checks within the guardrails set by the Enterprise and Domain.

Settings can be locked using `overridable: false`. Any attempt to weaken a locked setting at a lower level will result in a **FLOE-DQ107** error.

## OpenLineage Integration

The quality plugin automatically emits OpenLineage `FAIL` events when quality checks fail. This integration allows you to track data quality issues in tools like Marquez or Atlan.

To enable OpenLineage emission, ensure your `LineageBackend` is configured in `manifest.yaml`:

```yaml
lineage:
  backend: marquez
  url: http://marquez:5000
```

The `QualityPlugin` will then use the `OpenLineageEmitter` to report:
- The failed `job_name` and `dataset_name`.
- Specific check results that caused the failure.
- Impacted quality dimensions.

## Troubleshooting & Error Codes

| Code | Message | Resolution |
|------|---------|------------|
| **FLOE-DQ001** | Quality Provider Not Found | Ensure the `provider` in `manifest.yaml` matches an installed plugin (`great_expectations` or `dbt_expectations`). |
| **FLOE-DQ102** | Quality Check Failed | Achievement score was below `min_score`. Review the runtime results for specific check failures. |
| **FLOE-DQ103** | Coverage Violation | Your model has fewer tests than the tier minimum. Add checks to more columns. |
| **FLOE-DQ104** | Missing Required Tests | One or more tests required by the tier (e.g., `unique`) are missing from your configuration. |
| **FLOE-DQ105** | Invalid Column Reference | The check refers to a column that does not exist in the source data or dbt model. |
| **FLOE-DQ106** | Quality Check Timeout | The checks took longer than `check_timeout_seconds`. Optimize your queries or increase the timeout. |
| **FLOE-DQ107** | Locked Setting Override | You tried to override a setting that the Platform Team has marked as `overridable: false`. |
