# Data Model: Data Quality Plugin

**Epic**: 5B | **Date**: 2026-01-28 | **Contract Version**: 0.4.0

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CONFIGURATION                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌───────────────┐         ┌───────────────────┐                      │
│   │ QualityConfig │────────►│   QualityGates    │                      │
│   │               │         │                   │                      │
│   │ - provider    │         │ - bronze: GateTier│                      │
│   │ - quality_gates│        │ - silver: GateTier│                      │
│   │ - dimension_   │        │ - gold: GateTier  │                      │
│   │   weights     │         └───────────────────┘                      │
│   │ - calculation │                                                     │
│   │ - thresholds  │         ┌───────────────────┐                      │
│   └───────┬───────┘         │    GateTier       │                      │
│           │                 │                   │                      │
│           │                 │ - min_test_coverage│                     │
│           ▼                 │ - required_tests  │                      │
│   ┌───────────────┐         │ - min_score       │                      │
│   │DimensionWeights│        │ - overridable     │                      │
│   │               │         └───────────────────┘                      │
│   │ - completeness│                                                     │
│   │ - accuracy    │         ┌───────────────────┐                      │
│   │ - validity    │         │CalculationParams  │                      │
│   │ - consistency │         │                   │                      │
│   │ - timeliness  │         │ - baseline_score  │                      │
│   │ [sum=1.0]     │         │ - max_positive_   │                      │
│   └───────────────┘         │   influence       │                      │
│                             │ - max_negative_   │                      │
│                             │   influence       │                      │
│                             │ - severity_weights│                      │
│                             └───────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           EXECUTION                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌───────────────┐         ┌───────────────────┐                      │
│   │ QualitySuite  │────────►│   QualityCheck    │                      │
│   │               │   1:N   │                   │                      │
│   │ - model_name  │         │ - name            │                      │
│   │ - checks[]    │         │ - type            │                      │
│   │ - timeout_    │         │ - column          │                      │
│   │   seconds     │         │ - dimension       │───► Dimension (enum) │
│   │ - fail_fast   │         │ - severity        │───► SeverityLevel    │
│   └───────────────┘         │ - custom_weight   │                      │
│                             │ - parameters      │                      │
│                             │ - enabled         │                      │
│                             └───────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           RESULTS                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌───────────────┐         ┌───────────────────┐                      │
│   │QualitySuite   │────────►│QualityCheckResult │                      │
│   │   Result      │   1:N   │                   │                      │
│   │               │         │ - check_name      │                      │
│   │ - suite_name  │         │ - passed          │                      │
│   │ - model_name  │         │ - dimension       │                      │
│   │ - passed      │         │ - severity        │                      │
│   │ - checks[]    │         │ - records_checked │                      │
│   │ - execution_  │         │ - records_failed  │                      │
│   │   time_ms     │         │ - execution_time_ms│                     │
│   │ - summary     │         │ - details         │                      │
│   │ - timestamp   │         │ - error_message   │                      │
│   └───────┬───────┘         └───────────────────┘                      │
│           │                                                             │
│           ▼                                                             │
│   ┌───────────────┐                                                     │
│   │ QualityScore  │         ┌───────────────────┐                      │
│   │               │         │ ValidationResult  │                      │
│   │ - overall     │         │                   │                      │
│   │ - dimension_  │         │ - success         │                      │
│   │   scores      │         │ - errors[]        │                      │
│   │ - checks_     │         │ - warnings[]      │                      │
│   │   passed/failed│        └───────────────────┘                      │
│   │ - dbt_tests_  │                                                     │
│   │   passed/failed│        ┌───────────────────┐                      │
│   │ - model_name  │         │   GateResult      │                      │
│   │ - timestamp   │         │                   │                      │
│   └───────────────┘         │ - passed          │                      │
│                             │ - tier            │                      │
│                             │ - coverage_actual │                      │
│                             │ - coverage_required│                     │
│                             │ - missing_tests[] │                      │
│                             │ - violations[]    │                      │
│                             └───────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Entity Definitions

### Enums

#### Dimension

Quality dimension classification for checks.

| Value | Description | Example Checks |
|-------|-------------|----------------|
| `completeness` | Data is present where expected | not_null, expect_column_to_exist |
| `accuracy` | Data values are correct | expect_column_values_to_be_between |
| `validity` | Data conforms to rules | regex, accepted_values |
| `consistency` | Data is consistent | relationships, compound_unique |
| `timeliness` | Data is current | timestamp freshness |

#### SeverityLevel

Impact level for quality checks.

| Value | Default Weight | Use Case |
|-------|----------------|----------|
| `critical` | 3.0 | Data integrity (PKs, FKs, not_null on required) |
| `warning` | 1.0 | Business rule violations |
| `info` | 0.5 | Nice-to-have validations |

---

### Configuration Entities

#### QualityConfig

Top-level quality configuration with three-tier inheritance.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | `str` | Yes | - | Plugin name ("great_expectations", "dbt_expectations") |
| `quality_gates` | `QualityGates` | No | defaults | Bronze/silver/gold requirements |
| `dimension_weights` | `DimensionWeights` | No | defaults | Layer 1 scoring weights |
| `calculation` | `CalculationParameters` | No | defaults | Layer 3 scoring parameters |
| `thresholds` | `QualityThresholds` | No | defaults | min_score, warn_score |
| `check_timeout_seconds` | `int` | No | 300 | Default check timeout |
| `enabled` | `bool` | No | true | Enable quality validation |

**Inheritance**: Enterprise → Domain → Product. Settings with `overridable: false` cannot be changed.

---

#### QualityGates

Tier-based quality requirements.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bronze` | `GateTier` | No | defaults | Minimum tier requirements |
| `silver` | `GateTier` | No | defaults | Standard tier requirements |
| `gold` | `GateTier` | No | defaults | Strictest tier requirements |

---

#### GateTier

Single tier quality gate definition.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `min_test_coverage` | `float` | No | 0 | Min % columns with tests (0-100) |
| `required_tests` | `list[str]` | No | [] | Mandatory test types |
| `min_score` | `int` | No | 0 | Minimum quality score (0-100) |
| `overridable` | `bool` | No | true | Can lower levels modify |

**Default Values by Tier**:
| Tier | Coverage | Required Tests | Min Score |
|------|----------|----------------|-----------|
| Bronze | 0% | none | 0 |
| Silver | 80% | not_null, unique | 75 |
| Gold | 100% | not_null, unique, accepted_values, relationships | 90 |

---

#### DimensionWeights

Layer 1 scoring weights.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `completeness` | `float` | No | 0.25 | Completeness weight |
| `accuracy` | `float` | No | 0.25 | Accuracy weight |
| `validity` | `float` | No | 0.20 | Validity weight |
| `consistency` | `float` | No | 0.15 | Consistency weight |
| `timeliness` | `float` | No | 0.15 | Timeliness weight |

**Constraint**: All weights must sum to 1.0.

---

#### CalculationParameters

Layer 3 scoring parameters.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `baseline_score` | `int` | No | 70 | Starting score (0-100) |
| `max_positive_influence` | `int` | No | 30 | Max increase from baseline |
| `max_negative_influence` | `int` | No | 50 | Max decrease from baseline |
| `severity_weights` | `dict` | No | defaults | Severity → weight mapping |

**Default Severity Weights**:
```python
{
    "critical": 3.0,
    "warning": 1.0,
    "info": 0.5,
}
```

---

#### QualityThresholds

Score enforcement thresholds.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `min_score` | `int` | No | 70 | Below this blocks deployment |
| `warn_score` | `int` | No | 85 | Below this emits warning |

---

### Execution Entities

#### QualityCheck

Individual quality check definition.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | `str` | Yes | - | Unique identifier within model |
| `type` | `str` | Yes | - | Check type (not_null, expect_*) |
| `column` | `str` | No | None | Target column (None for table-level) |
| `dimension` | `Dimension` | Yes | - | Quality dimension |
| `severity` | `SeverityLevel` | No | warning | Check severity |
| `custom_weight` | `float` | No | None | Override severity weight (0.1-10.0) |
| `parameters` | `dict` | No | {} | Check-specific parameters |
| `enabled` | `bool` | No | true | Whether check is active |

**Example**:
```yaml
name: age_reasonable_range
type: expect_column_values_to_be_between
column: age
dimension: accuracy
severity: warning
parameters:
  min_value: 0
  max_value: 150
```

---

#### QualitySuite

Collection of checks for a model.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model_name` | `str` | Yes | - | Target dbt model |
| `checks` | `list[QualityCheck]` | Yes | - | Checks to execute |
| `timeout_seconds` | `int` | No | 300 | Execution timeout |
| `fail_fast` | `bool` | No | false | Stop on first failure |

---

### Result Entities

#### QualityCheckResult

Single check execution result.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `check_name` | `str` | Yes | - | Executed check name |
| `passed` | `bool` | Yes | - | Whether check passed |
| `dimension` | `Dimension` | Yes | - | Quality dimension |
| `severity` | `SeverityLevel` | Yes | - | Check severity |
| `records_checked` | `int` | No | 0 | Records evaluated |
| `records_failed` | `int` | No | 0 | Records that failed |
| `execution_time_ms` | `float` | No | 0 | Execution time |
| `details` | `dict` | No | {} | Additional details |
| `error_message` | `str` | No | None | Error if failed |

---

#### QualitySuiteResult

Aggregated suite execution result.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `suite_name` | `str` | Yes | - | Suite identifier |
| `model_name` | `str` | Yes | - | Target model |
| `passed` | `bool` | Yes | - | All checks passed |
| `checks` | `list[QualityCheckResult]` | Yes | - | Individual results |
| `execution_time_ms` | `float` | No | 0 | Total execution time |
| `summary` | `dict` | No | {} | Summary statistics |
| `timestamp` | `datetime` | No | now | Execution timestamp |

---

#### QualityScore

Unified quality score.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `overall` | `float` | Yes | - | Overall score (0-100) |
| `dimension_scores` | `dict[Dimension, float]` | Yes | - | Per-dimension scores |
| `checks_passed` | `int` | No | 0 | Plugin checks passed |
| `checks_failed` | `int` | No | 0 | Plugin checks failed |
| `dbt_tests_passed` | `int` | No | 0 | dbt tests passed |
| `dbt_tests_failed` | `int` | No | 0 | dbt tests failed |
| `model_name` | `str` | Yes | - | Target model |
| `timestamp` | `datetime` | No | now | Calculation timestamp |

---

#### ValidationResult

Compile-time validation result.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `success` | `bool` | Yes | - | Validation passed |
| `errors` | `list[str]` | No | [] | Error messages |
| `warnings` | `list[str]` | No | [] | Warning messages |

---

#### GateResult

Quality gate validation result.

| Attribute | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `passed` | `bool` | Yes | - | All gates passed |
| `tier` | `str` | Yes | - | Evaluated tier |
| `coverage_actual` | `float` | Yes | - | Actual coverage % |
| `coverage_required` | `float` | Yes | - | Required coverage % |
| `missing_tests` | `list[str]` | No | [] | Missing test types |
| `violations` | `list[str]` | No | [] | Violation descriptions |

---

## CompiledArtifacts Extension

**Version**: 0.3.0 → 0.4.0 (MINOR - additive)

### New Fields

```python
class CompiledArtifacts(BaseModel):
    # ... existing fields ...

    # Epic 5B additions (v0.4.0)
    quality_config: QualityConfig | None = Field(
        default=None,
        description="Resolved quality configuration",
    )
```

### ResolvedModel Extension

```python
class ResolvedModel(BaseModel):
    # ... existing fields ...

    # Epic 5B additions (v0.4.0)
    quality_checks: list[QualityCheck] | None = Field(
        default=None,
        description="Quality checks for this model",
    )
    quality_tier: Literal["bronze", "silver", "gold"] | None = Field(
        default=None,
        description="Quality tier for this model",
    )
```

---

## Error Codes

| Code | Condition | Resolution |
|------|-----------|------------|
| FLOE-DQ001 | Invalid/missing quality provider | Check plugins.quality.provider |
| FLOE-DQ102 | Quality checks failed at runtime | Review failed checks |
| FLOE-DQ103 | Coverage below tier minimum | Add more tests |
| FLOE-DQ104 | Missing required test types | Add required tests |
| FLOE-DQ105 | Invalid column reference | Verify column exists |
| FLOE-DQ106 | Check timeout exceeded | Increase timeout |
| FLOE-DQ107 | Override of locked setting | Remove override |
