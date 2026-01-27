# Research Findings: Data Quality Plugin

**Epic**: 5B | **Date**: 2026-01-28

## Executive Summary

Research into the existing floe architecture, Great Expectations, dbt testing, and ODCS (Open Data Contract Standard) to inform the Data Quality Plugin design. Key findings:

1. **Existing QualityPlugin ABC** in `floe_core.plugins.quality` provides minimal interface (run_checks, validate_expectations, list_suites) - needs extension for compile-time validation and scoring
2. **Plugin System Integration** follows established patterns (entry points, PluginMetadata, lifecycle methods)
3. **Great Expectations 1.0** provides comprehensive expectation library with severity support via meta fields
4. **dbt-expectations** offers 40+ tests that integrate with dbt's test infrastructure
5. **ODCS** defines quality rules declaratively - already integrated via Epic 3C data contracts

---

## Existing Architecture Analysis

### 1. Plugin System Integration

**PluginMetadata Base Class** (`floe_core.plugin_metadata`):
```python
class PluginMetadata(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @property
    @abstractmethod
    def floe_api_version(self) -> str: ...

    @property
    def description(self) -> str: return ""

    @property
    def dependencies(self) -> list[str]: return []

    def get_config_schema(self) -> type[BaseModel] | None: return None

    def health_check(self) -> HealthStatus: ...

    def startup(self) -> None: ...

    def shutdown(self) -> None: ...
```

**Entry Point**: `floe.quality` (defined in `floe_core.plugin_types.PluginType.QUALITY`)

### 2. Existing QualityPlugin ABC

Location: `packages/floe-core/src/floe_core/plugins/quality.py`

```python
@dataclass
class QualityCheckResult:
    check_name: str
    passed: bool
    details: dict[str, Any]
    records_checked: int = 0
    records_failed: int = 0


@dataclass
class QualitySuiteResult:
    suite_name: str
    passed: bool
    checks: list[QualityCheckResult]
    summary: dict[str, Any]


class QualityPlugin(PluginMetadata):
    @abstractmethod
    def run_checks(
        self,
        suite_name: str,
        data_source: str,
        options: dict[str, Any] | None = None,
    ) -> QualitySuiteResult: ...

    @abstractmethod
    def validate_expectations(
        self,
        data_source: str,
        expectations: list[dict[str, Any]],
    ) -> list[QualityCheckResult]: ...

    @abstractmethod
    def list_suites(self) -> list[str]: ...
```

**Gap Analysis**:
- Missing: `validate_config()` for compile-time validation
- Missing: `validate_quality_gates()` for tier enforcement
- Missing: `calculate_quality_score()` for scoring
- Missing: `supports_dialect()` for SQL dialect support
- Missing: `get_lineage_emitter()` for OpenLineage integration
- Missing: Dimension and severity in result classes

### 3. DBTPlugin Interface

Location: `packages/floe-core/src/floe_core/plugins/dbt.py`

```python
@dataclass
class DBTRunResult:
    success: bool
    manifest_path: Path
    run_results_path: Path
    catalog_path: Path | None = None
    execution_time_seconds: float = 0.0
    models_run: int = 0
    tests_run: int = 0
    failures: int = 0
    metadata: dict[str, Any] = field(default_factory=lambda: {})


class DBTPlugin(PluginMetadata):
    @abstractmethod
    def test_models(
        self,
        project_dir: Path,
        profiles_dir: Path,
        target: str,
        select: str | None = None,
    ) -> DBTRunResult: ...
```

**Integration Point**: Unified quality score must incorporate `DBTRunResult.tests_run` and `failures` (FR-028).

### 4. ComputePlugin Connection Pattern

Location: `packages/floe-core/src/floe_core/plugins/compute.py`

```python
class ComputeConfig(BaseModel):
    plugin: str
    timeout_seconds: int = 3600
    threads: int = 4
    connection: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, SecretStr] = Field(default_factory=dict)


class ComputePlugin(PluginMetadata):
    @abstractmethod
    def validate_connection(self, config: ComputeConfig) -> ConnectionResult: ...
```

**Integration Point**: QualityPlugin receives connection configuration from ComputePlugin via runtime context (FR-026).

### 5. OrchestratorPlugin Integration

Location: `packages/floe-core/src/floe_core/plugins/orchestrator.py`

```python
class OrchestratorPlugin(PluginMetadata):
    @abstractmethod
    def emit_lineage_event(
        self,
        event_type: str,  # START, COMPLETE, FAIL
        job: str,
        inputs: list[Dataset],
        outputs: list[Dataset],
    ) -> None: ...
```

**Integration Point**: Quality check failures emit OpenLineage FAIL events (FR-029).

### 6. CompiledArtifacts Schema

Location: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`

Current version: 0.3.0. Key fields:
- `version`, `metadata`, `identity`, `mode`
- `plugins: ResolvedPlugins`
- `transforms: ResolvedTransforms`
- `dbt_profiles: dict[str, Any]`
- `governance: ResolvedGovernance`
- `enforcement_result: EnforcementResultSummary`
- `data_contracts: list[DataContract]`

**Required Extension** (v0.4.0):
- `quality_config: QualityConfig | None`
- `ResolvedModel.quality_checks: list[QualityCheck] | None`
- `ResolvedModel.quality_tier: Literal["bronze", "silver", "gold"] | None`

---

## External Framework Research

### Great Expectations (GX Core 1.0+)

**Architecture**:
```
Data Source → Batch Definition → Expectation Suite → Checkpoint → Results
                                      ↓
                               Validation Actions
                               (OpenLineage emit)
```

**Key Components**:
| Component | Purpose |
|-----------|---------|
| **Data Sources** | Connect to backends (PostgreSQL, DuckDB, Snowflake) |
| **Batches** | Define data subsets to validate |
| **Expectations** | Individual validation rules |
| **Suites** | Collections of expectations |
| **Checkpoints** | Orchestration combining data + expectations + actions |
| **Actions** | Post-validation behaviors |

**Expectation Types by Dimension**:
| Dimension | Expectations |
|-----------|-------------|
| **Completeness** | `expect_column_values_to_not_be_null`, `expect_column_to_exist`, `expect_table_columns_to_match_ordered_list` |
| **Accuracy** | `expect_column_values_to_be_between`, `expect_column_mean_to_be_between`, `expect_column_median_to_be_between` |
| **Validity** | `expect_column_values_to_be_in_set`, `expect_column_values_to_match_regex`, `expect_column_values_to_be_dateutil_parseable` |
| **Consistency** | `expect_compound_columns_to_be_unique`, `expect_column_pair_values_A_to_be_greater_than_B`, `expect_column_pair_values_to_be_equal` |
| **Timeliness** | Custom expectations (timestamps, freshness) |

**Severity Support**:
```python
from great_expectations.core import ExpectationConfiguration

config = ExpectationConfiguration(
    expectation_type="expect_column_values_to_not_be_null",
    kwargs={"column": "id"},
    meta={"severity": "critical"}  # Custom metadata for severity
)
```

**Supported Backends**:
- SQLAlchemy (PostgreSQL, MySQL, etc.)
- DuckDB (via duckdb-sqlalchemy)
- Snowflake
- BigQuery
- Databricks
- Pandas/Spark DataFrames

### dbt Testing

**Built-in Generic Tests** (schema.yml):
```yaml
models:
  - name: customers
    columns:
      - name: customer_id
        tests:
          - not_null
          - unique
      - name: status
        tests:
          - accepted_values:
              values: ['active', 'inactive', 'pending']
      - name: account_id
        tests:
          - relationships:
              to: ref('accounts')
              field: id
```

**Test Result Access** (run_results.json):
```json
{
  "results": [
    {
      "unique_id": "test.my_project.not_null_customers_customer_id.a1b2c3d4",
      "status": "pass",  // or "fail", "warn", "error"
      "failures": 0,
      "execution_time": 0.123,
      "adapter_response": {}
    }
  ]
}
```

### dbt-expectations Package

**40+ Great Expectations-inspired tests**:

| Category | Tests |
|----------|-------|
| **Column Values** | `expect_column_values_to_not_be_null`, `expect_column_values_to_be_unique`, `expect_column_values_to_be_in_set`, `expect_column_values_to_be_between`, `expect_column_values_to_match_regex` |
| **Column Aggregates** | `expect_column_mean_to_be_between`, `expect_column_median_to_be_between`, `expect_column_stdev_to_be_between`, `expect_column_sum_to_be_between` |
| **Table Shape** | `expect_table_row_count_to_be_between`, `expect_table_row_count_to_equal`, `expect_table_column_count_to_equal` |
| **Multi-Column** | `expect_compound_columns_to_be_unique`, `expect_multicolumn_sum_to_equal` |

**Usage in schema.yml**:
```yaml
models:
  - name: customers
    tests:
      - dbt_expectations.expect_table_row_count_to_be_between:
          min_value: 1000
          max_value: 10000
    columns:
      - name: age
        tests:
          - dbt_expectations.expect_column_values_to_be_between:
              min_value: 0
              max_value: 150
```

### ODCS (Open Data Contract Standard)

**Quality Rules in Data Contracts** (from datacontract-cli):
```yaml
quality:
  type: SodaCL
  specification:
    checks for orders:
      - freshness(order_date) < 1d
      - duplicate_count(order_id) = 0
      - row_count > 1000
      - missing_count(customer_id) = 0
```

**Quality Types Supported**:
- Completeness (`missing_count`, `missing_percent`)
- Uniqueness (`duplicate_count`, `duplicate_percent`)
- Validity (`invalid_count`, `invalid_percent`)
- Freshness (`freshness`)
- Volume (`row_count`)

**Integration**: Data contracts (Epic 3C) already in CompiledArtifacts. Quality plugin can validate against contract quality rules.

---

## Scoring Model Research

### Industry Approaches

**Great Expectations**:
- Per-expectation severity (meta field)
- No built-in aggregate scoring
- Custom actions can calculate scores

**Qualytics**:
- 8 quality dimensions
- Baseline score of 70
- Influence capping (max +30, max -50)
- Configurable weights per dimension
- Rule-level severity multipliers

**Ataccama**:
- Quality rules with severity levels
- Dimension-based scoring
- Weight-based aggregation

### Adopted Model: Three-Layer Scoring

**Layer 1: Dimension Weights** (Enterprise/Domain)
- completeness: 0.25 (default)
- accuracy: 0.25
- validity: 0.20
- consistency: 0.15
- timeliness: 0.15
- Must sum to 1.0

**Layer 2: Check Severity** (Per-Check)
- critical: 3.0 (data integrity, PKs/FKs)
- warning: 1.0 (business rules)
- info: 0.5 (nice-to-have)
- custom_weight: 0.1-10.0 (override)

**Layer 3: Calculation Parameters** (Enterprise)
- baseline_score: 70
- max_positive_influence: 30
- max_negative_influence: 50
- Final score always 0-100

**Algorithm**:
```python
# Per-dimension score (weighted by severity)
dimension_score = sum(check_result * severity_weight) / sum(severity_weight)

# Overall score (weighted by dimension)
raw_score = sum(dimension_score * dimension_weight)

# Apply influence capping
delta = raw_score - baseline
if delta > 0:
    delta = min(delta, max_positive_influence)
else:
    delta = max(delta, -max_negative_influence)

final_score = baseline + delta  # Always 0-100
```

---

## Key Design Decisions

1. **Extend existing QualityPlugin ABC** rather than create new class
2. **Reuse ComputePlugin connection pattern** for database access
3. **Unified scoring** combines dbt tests + plugin quality checks
4. **Three-tier inheritance** (Enterprise → Domain → Product) with lock control
5. **MINOR version bump** (0.3.0 → 0.4.0) for CompiledArtifacts
6. **Plugin packages in plugins/** directory following established patterns

---

## References

- [Great Expectations Documentation](https://docs.greatexpectations.io/)
- [dbt Testing](https://docs.getdbt.com/docs/build/tests)
- [dbt-expectations](https://github.com/calogica/dbt-expectations)
- [datacontract-cli](https://github.com/datacontract/datacontract-cli)
- [ODCS v3 Specification](https://datacontract.com/)
