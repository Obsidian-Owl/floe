# Implementation Plan: Data Quality Plugin

**Branch**: `5b-dataquality-plugin` | **Date**: 2026-01-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/5b-dataquality-plugin/spec.md`

## Summary

Extend the existing QualityPlugin ABC (`floe_core.plugins.quality`) to support compile-time validation, runtime quality checks, quality gates enforcement, and quality scoring with OpenLineage emission. Provide reference implementations using Great Expectations (`floe-quality-gx`) and dbt-expectations (`floe-quality-dbt`). Quality checks execute after EACH model materialization for early failure detection, with results aggregated into a unified quality score that includes both dbt test results and plugin quality checks.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**:
- floe-core (PluginMetadata, CompiledArtifacts, existing QualityPlugin ABC)
- great-expectations>=1.0.0 (GX Core 1.0+ for floe-quality-gx)
- dbt-expectations>=0.10.0 (for floe-quality-dbt)
- Pydantic v2 (all schemas)
- structlog (logging)
- opentelemetry-api (tracing)

**Storage**: N/A (quality results flow through CompiledArtifacts and runtime state)
**Testing**: pytest with K8s-native integration tests (Kind cluster), `@pytest.mark.requirement()` markers
**Target Platform**: Kubernetes (floe-platform)
**Project Type**: Plugin packages extending floe-core
**Performance Goals**: Quality score calculation in <100ms for 1000 checks; plugin discovery in <2s
**Constraints**: Plugin health_check() returns within 5s; quality check timeout configurable (default 300s)
**Scale/Scope**: Support 100+ quality checks per model; three-tier inheritance hierarchy

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core for ABC/schemas, plugins/ for implementations)
- [x] No SQL parsing/validation in Python (dbt owns SQL; quality checks execute via compute engine)
- [x] No orchestration logic outside floe-dagster (OrchestratorPlugin invokes quality checks)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (extends existing QualityPlugin ABC)
- [x] Plugin registered via entry point (`floe.quality`)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (OpenTelemetry traces, OpenLineage for failures)
- [x] Pluggable choices documented in manifest.yaml (`plugins.quality.provider`)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (quality_config, quality_checks fields added)
- [x] Pydantic v2 models for all schemas (QualityConfig, QualityGates, QualityScore, etc.)
- [x] Contract changes follow versioning rules (MINOR bump for new optional fields)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (all quality configuration)
- [x] Credentials use SecretStr (inherited from ComputePlugin connection)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (Enterprise → Domain → Product with lock control)
- [x] Layer ownership respected (Platform Team configures quality gates in manifest.yaml)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (quality check execution spans)
- [x] OpenLineage events for quality check failures (FR-029)

## Project Structure

### Documentation (this feature)

```text
specs/5b-dataquality-plugin/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 research findings (embedded below)
├── data-model.md        # Entity definitions (embedded below)
├── quickstart.md        # Developer quickstart guide
├── contracts/           # Pydantic schema definitions
│   ├── quality_config.py
│   ├── quality_gates.py
│   ├── quality_score.py
│   └── quality_check.py
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
packages/floe-core/src/floe_core/
├── plugins/
│   └── quality.py           # EXTEND existing QualityPlugin ABC
├── schemas/
│   ├── quality_config.py    # NEW: QualityConfig, QualityGates, DimensionWeights
│   ├── quality_score.py     # NEW: QualityScore, QualityCheckResult (enhanced)
│   └── compiled_artifacts.py # MODIFY: Add quality_config, quality_checks fields

plugins/
├── floe-quality-gx/         # NEW: Great Expectations implementation
│   ├── pyproject.toml
│   ├── src/
│   │   └── floe_quality_gx/
│   │       ├── __init__.py
│   │       ├── plugin.py    # GreatExpectationsPlugin
│   │       └── config.py    # GX-specific config
│   └── tests/
│       ├── conftest.py
│       ├── unit/
│       └── integration/
│
└── floe-quality-dbt/        # NEW: dbt-expectations implementation
    ├── pyproject.toml
    ├── src/
    │   └── floe_quality_dbt/
    │       ├── __init__.py
    │       ├── plugin.py    # DBTExpectationsPlugin
    │       └── config.py    # dbt-expectations specific config
    └── tests/
        ├── conftest.py
        ├── unit/
        └── integration/

tests/
└── contract/
    └── test_quality_plugin_contract.py  # Cross-package contract tests
```

**Structure Decision**: Plugin packages in `plugins/` directory following existing patterns (floe-compute-duckdb, floe-catalog-polaris). Core schemas in `floe-core/schemas/`. Quality ABC extended in existing `floe_core/plugins/quality.py`.

## Complexity Tracking

> No constitution violations. Standard plugin pattern with established inheritance from existing QualityPlugin ABC.

---

## Phase 0: Research Findings

### Existing Architecture Analysis

#### 1. Plugin System Integration

**PluginMetadata Base Class** (`floe_core.plugin_metadata`):
- Abstract properties: `name`, `version`, `floe_api_version`
- Optional: `description`, `dependencies`
- Lifecycle: `startup()`, `shutdown()`, `health_check()`
- Configuration: `get_config_schema() -> type[BaseModel] | None`

**Existing QualityPlugin ABC** (`floe_core.plugins.quality`):
```python
class QualityPlugin(PluginMetadata):
    @abstractmethod
    def run_checks(self, suite_name: str, data_source: str, options: dict | None = None) -> QualitySuiteResult

    @abstractmethod
    def validate_expectations(self, data_source: str, expectations: list[dict]) -> list[QualityCheckResult]

    @abstractmethod
    def list_suites(self) -> list[str]
```

**Extension Required**: Add compile-time methods (`validate_config`, `validate_quality_gates`), scoring (`calculate_quality_score`), dialect support (`supports_dialect`), and lineage (`get_lineage_emitter`).

**Entry Point**: `floe.quality` (already defined in `floe_core.plugin_types.PluginType.QUALITY`)

#### 2. DBTPlugin Interface (Integration Point)

The `DBTPlugin.test_models()` method returns `DBTRunResult`:
```python
@dataclass
class DBTRunResult:
    success: bool
    manifest_path: Path
    run_results_path: Path
    tests_run: int
    failures: int
    metadata: dict[str, Any]
```

**Key Integration**: Unified quality score must incorporate `DBTRunResult.tests_run` and `failures` into overall quality calculation (FR-028).

#### 3. ComputePlugin Connection Pattern

Quality checks need database connections. The `ComputePlugin.validate_connection()` pattern shows:
```python
def validate_connection(self, config: ComputeConfig) -> ConnectionResult
```

**Key Integration**: QualityPlugin receives connection configuration from ComputePlugin via runtime context (FR-026).

#### 4. OrchestratorPlugin Integration

Runtime quality check execution is triggered by OrchestratorPlugin:
```python
def emit_lineage_event(self, event_type: str, job: str, inputs: list[Dataset], outputs: list[Dataset]) -> None
```

**Key Integration**: Quality check failures emit OpenLineage FAIL events (FR-029). OrchestratorPlugin calls `QualityPlugin.run_checks()` after each model materialization (FR-025).

#### 5. CompiledArtifacts Schema (Contract)

Current version: 0.3.0. Needs MINOR bump to 0.4.0 for:
- `quality_config: QualityConfig | None` - Resolved quality settings
- Per-model `quality_checks: list[QualityCheck]` in `ResolvedModel`

### External Framework Research

#### Great Expectations (GX Core 1.0+)

**Architecture**:
- **Data Sources**: Connect to various data backends (PostgreSQL, DuckDB, Snowflake, etc.)
- **Batches**: Define data subsets to validate
- **Expectations**: Individual validation rules (expect_column_values_to_not_be_null, etc.)
- **Suites**: Collections of expectations for a dataset
- **Checkpoints**: Orchestration unit combining data, expectations, and actions
- **Actions**: Post-validation behaviors (emit events, send alerts)

**Key Expectations for Quality Dimensions**:
| Dimension | Expectations |
|-----------|-------------|
| Completeness | `expect_column_values_to_not_be_null`, `expect_column_to_exist` |
| Accuracy | `expect_column_values_to_be_between`, `expect_column_mean_to_be_between` |
| Validity | `expect_column_values_to_be_in_set`, `expect_column_values_to_match_regex` |
| Consistency | `expect_column_pair_values_A_to_be_greater_than_B`, `expect_compound_columns_to_be_unique` |
| Timeliness | Custom expectations comparing timestamps to current time |

**Severity Support**: GX supports severity levels via `meta` field:
```python
ExpectationConfiguration(
    expectation_type="expect_column_values_to_not_be_null",
    kwargs={"column": "id"},
    meta={"severity": "critical"}  # custom metadata
)
```

#### dbt Testing & dbt-expectations

**Built-in dbt Generic Tests**:
- `not_null`: Column contains no nulls
- `unique`: Column values are unique
- `accepted_values`: Column values in allowed list
- `relationships`: Foreign key integrity

**dbt-expectations Package** (40+ tests):
- `expect_column_values_to_not_be_null`
- `expect_column_values_to_be_unique`
- `expect_column_values_to_be_between`
- `expect_column_values_to_match_regex`
- `expect_table_row_count_to_be_between`
- `expect_column_mean_to_be_between`

**Test Result Access**: via `run_results.json`:
```json
{
  "results": [
    {
      "unique_id": "test.my_project.not_null_customers_id",
      "status": "pass",
      "failures": 0,
      "execution_time": 0.123
    }
  ]
}
```

#### ODCS (Open Data Contract Standard)

From `datacontract-cli` GitHub research:
- Defines data contracts with schema, quality, and SLA properties
- Quality section specifies rules declaratively
- Supports `type: completeness`, `type: uniqueness`, etc.
- SLA section defines availability, latency, freshness requirements

**Integration**: Data contracts (Epic 3C) already in CompiledArtifacts. Quality plugin validates against contract quality rules.

### Three-Tier Scoring Model Design

Based on Great Expectations severity and Qualytics research:

**Layer 1: Dimension Weights** (Enterprise/Domain level)
```python
class DimensionWeights(BaseModel):
    completeness: float = Field(default=0.25, ge=0, le=1.0)
    accuracy: float = Field(default=0.25, ge=0, le=1.0)
    validity: float = Field(default=0.20, ge=0, le=1.0)
    consistency: float = Field(default=0.15, ge=0, le=1.0)
    timeliness: float = Field(default=0.15, ge=0, le=1.0)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> Self:
        total = self.completeness + self.accuracy + self.validity + self.consistency + self.timeliness
        if not math.isclose(total, 1.0, rel_tol=1e-9):
            raise ValueError("Dimension weights must sum to 1.0")
        return self
```

**Layer 2: Check-Level Severity**
```python
class SeverityLevel(str, Enum):
    CRITICAL = "critical"  # weight: 3.0
    WARNING = "warning"    # weight: 1.0
    INFO = "info"          # weight: 0.5

class QualityCheck(BaseModel):
    name: str
    type: str  # not_null, unique, custom, etc.
    column: str | None = None
    dimension: Dimension  # completeness, accuracy, validity, consistency, timeliness
    severity: SeverityLevel = SeverityLevel.WARNING
    custom_weight: float | None = None  # Override severity weight
    parameters: dict[str, Any] = Field(default_factory=dict)
```

**Layer 3: Calculation Parameters**
```python
class CalculationParameters(BaseModel):
    baseline_score: int = Field(default=70, ge=0, le=100)
    max_positive_influence: int = Field(default=30, ge=0, le=100)
    max_negative_influence: int = Field(default=50, ge=0, le=100)
    severity_weights: dict[SeverityLevel, float] = Field(default={
        SeverityLevel.CRITICAL: 3.0,
        SeverityLevel.WARNING: 1.0,
        SeverityLevel.INFO: 0.5,
    })
```

**Score Calculation Algorithm**:
```python
def calculate_quality_score(results: QualitySuiteResult, config: QualityConfig) -> QualityScore:
    dimension_scores = {}
    for dimension in Dimension:
        checks = [c for c in results.checks if c.dimension == dimension]
        if not checks:
            dimension_scores[dimension] = 100.0  # No checks = assumed good
            continue

        weighted_sum = 0.0
        weight_total = 0.0
        for check in checks:
            weight = check.custom_weight or config.calculation.severity_weights[check.severity]
            score = 100.0 if check.passed else 0.0
            weighted_sum += score * weight
            weight_total += weight

        dimension_scores[dimension] = weighted_sum / weight_total if weight_total > 0 else 100.0

    # Apply dimension weights
    overall = sum(
        dimension_scores[d] * getattr(config.dimension_weights, d.value)
        for d in Dimension
    )

    # Apply influence capping relative to baseline
    delta = overall - config.calculation.baseline_score
    if delta > 0:
        delta = min(delta, config.calculation.max_positive_influence)
    else:
        delta = max(delta, -config.calculation.max_negative_influence)

    final_score = config.calculation.baseline_score + delta
    return QualityScore(
        overall=max(0, min(100, final_score)),
        dimension_scores=dimension_scores,
        checks_passed=sum(1 for c in results.checks if c.passed),
        checks_failed=sum(1 for c in results.checks if not c.passed),
    )
```

---

## Phase 1: Data Model

### Entity Definitions

#### QualityPlugin (Extended ABC)

**Purpose**: Abstract base class for quality validation plugins. Extends existing minimal interface with compile-time validation, scoring, and lineage capabilities.

**Attributes**: Inherited from PluginMetadata (name, version, floe_api_version, description, dependencies)

**Methods** (NEW additions to existing ABC):
| Method | Signature | Purpose |
|--------|-----------|---------|
| `validate_config` | `(config: QualityConfig) -> ValidationResult` | Compile-time configuration validation |
| `validate_quality_gates` | `(models: list[ModelConfig], gates: QualityGates) -> GateResult` | Enforce coverage thresholds |
| `run_checks` | `(suite: QualitySuite, connection: ConnectionConfig) -> QualitySuiteResult` | Execute quality checks at runtime |
| `calculate_quality_score` | `(results: QualitySuiteResult, weights: ScoreWeights) -> QualityScore` | Compute unified quality score |
| `supports_dialect` | `(dialect: str) -> bool` | Check SQL dialect support |
| `get_lineage_emitter` | `() -> OpenLineageEmitter | None` | Get lineage event emitter |

**Relationships**:
- Extends: `PluginMetadata` (inheritance)
- Uses: `QualityConfig` for configuration
- Produces: `QualitySuiteResult`, `QualityScore`
- Consumes: `ConnectionConfig` from `ComputePlugin`

---

#### QualityConfig

**Purpose**: Top-level quality configuration with three-tier inheritance (Enterprise → Domain → Product).

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `provider` | `str` | Quality plugin name (e.g., "great_expectations", "dbt_expectations") |
| `quality_gates` | `QualityGates` | Bronze/silver/gold tier requirements |
| `dimension_weights` | `DimensionWeights` | Layer 1 weights for quality dimensions |
| `calculation` | `CalculationParameters` | Layer 3 scoring parameters |
| `thresholds` | `QualityThresholds` | min_score and warn_score |
| `overrides` | `dict[str, OverrideConfig]` | Per-setting override control |

**Inheritance Rules**:
- Enterprise settings propagate to Domain and Product
- Domain settings propagate to Product
- Settings with `overridable: false` cannot be changed at lower levels
- Attempted override of locked setting → FLOE-DQ107

---

#### QualityGates

**Purpose**: Tier-based quality requirements (bronze/silver/gold).

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `bronze` | `GateTier` | Minimum requirements for bronze tier |
| `silver` | `GateTier` | Requirements for silver tier |
| `gold` | `GateTier` | Strictest requirements for gold tier |

**GateTier Sub-Entity**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `min_test_coverage` | `float` | Minimum percentage of columns with tests (0-100) |
| `required_tests` | `list[str]` | Mandatory test types (not_null, unique, etc.) |
| `min_score` | `int` | Minimum quality score (0-100) |
| `overridable` | `bool` | Whether lower levels can modify (default: true) |

---

#### DimensionWeights

**Purpose**: Layer 1 of scoring model - weights for quality dimensions.

**Attributes**:
| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `completeness` | `float` | 0.25 | Weight for completeness dimension |
| `accuracy` | `float` | 0.25 | Weight for accuracy dimension |
| `validity` | `float` | 0.20 | Weight for validity dimension |
| `consistency` | `float` | 0.15 | Weight for consistency dimension |
| `timeliness` | `float` | 0.15 | Weight for timeliness dimension |

**Validation**: Weights must sum to 1.0 (enforced via `@model_validator`)

---

#### QualityCheck

**Purpose**: Individual quality check definition with dimension mapping and severity.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Check identifier (unique within model) |
| `type` | `str` | Check type (not_null, unique, expect_column_values_to_be_between, etc.) |
| `column` | `str | None` | Target column (None for table-level checks) |
| `dimension` | `Dimension` | Quality dimension (completeness, accuracy, validity, consistency, timeliness) |
| `severity` | `SeverityLevel` | critical/warning/info (default: warning) |
| `custom_weight` | `float | None` | Override severity weight (0.1-10.0) |
| `parameters` | `dict[str, Any]` | Check-specific parameters |
| `enabled` | `bool` | Whether check is active (default: true) |

---

#### QualitySuite

**Purpose**: Collection of quality checks for a model.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `model_name` | `str` | Target dbt model name |
| `checks` | `list[QualityCheck]` | Quality checks to execute |
| `timeout_seconds` | `int` | Execution timeout (default: 300) |
| `fail_fast` | `bool` | Stop on first failure (default: false) |

---

#### QualityCheckResult

**Purpose**: Result of a single quality check execution (enhanced from existing).

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `check_name` | `str` | Name of executed check |
| `passed` | `bool` | Whether check passed |
| `dimension` | `Dimension` | Quality dimension |
| `severity` | `SeverityLevel` | Check severity |
| `records_checked` | `int` | Number of records evaluated |
| `records_failed` | `int` | Number of records that failed |
| `execution_time_ms` | `float` | Check execution time |
| `details` | `dict[str, Any]` | Additional result details |
| `error_message` | `str | None` | Error message if check failed |

---

#### QualitySuiteResult

**Purpose**: Aggregated result of running a quality suite (enhanced from existing).

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `suite_name` | `str` | Suite identifier |
| `model_name` | `str` | Target model |
| `passed` | `bool` | Whether all checks passed |
| `checks` | `list[QualityCheckResult]` | Individual check results |
| `execution_time_ms` | `float` | Total execution time |
| `summary` | `dict[str, Any]` | Summary statistics |
| `timestamp` | `datetime` | Execution timestamp |

---

#### QualityScore

**Purpose**: Unified quality score incorporating dbt tests and plugin checks.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `overall` | `float` | Overall quality score (0-100) |
| `dimension_scores` | `dict[Dimension, float]` | Per-dimension scores |
| `checks_passed` | `int` | Total checks passed |
| `checks_failed` | `int` | Total checks failed |
| `dbt_tests_passed` | `int` | dbt tests passed (from DBTRunResult) |
| `dbt_tests_failed` | `int` | dbt tests failed |
| `model_name` | `str` | Target model |
| `timestamp` | `datetime` | Score calculation timestamp |

---

#### ValidationResult

**Purpose**: Result of compile-time validation.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `success` | `bool` | Whether validation passed |
| `errors` | `list[str]` | Error messages |
| `warnings` | `list[str]` | Warning messages |

---

#### GateResult

**Purpose**: Result of quality gate validation.

**Attributes**:
| Attribute | Type | Description |
|-----------|------|-------------|
| `passed` | `bool` | Whether all gates passed |
| `tier` | `str` | Evaluated tier (bronze/silver/gold) |
| `coverage_actual` | `float` | Actual test coverage percentage |
| `coverage_required` | `float` | Required test coverage |
| `missing_tests` | `list[str]` | Missing required test types |
| `violations` | `list[str]` | Gate violation descriptions |

---

### Error Code Catalog

| Code | Trigger | Resolution |
|------|---------|------------|
| FLOE-DQ001 | Missing or invalid quality provider | Check manifest.yaml plugins.quality.provider; install plugin |
| FLOE-DQ102 | Quality check failures at runtime | Review failed checks in run output; fix data issues |
| FLOE-DQ103 | Quality gate coverage violations | Add more tests to meet min_test_coverage |
| FLOE-DQ104 | Missing required test types | Add missing tests (not_null, unique, etc.) |
| FLOE-DQ105 | Reference to non-existent column | Verify column exists in model schema |
| FLOE-DQ106 | Quality check timeout | Increase timeout or optimize checks |
| FLOE-DQ107 | Override of locked setting | Remove override; setting is locked at higher level |

---

### CompiledArtifacts Extension

**Contract Version Bump**: 0.3.0 → 0.4.0 (MINOR - additive)

**New Fields**:
```python
class CompiledArtifacts(BaseModel):
    # ... existing fields ...

    # Epic 5B additions (v0.4.0)
    quality_config: QualityConfig | None = Field(
        default=None,
        description="Resolved quality configuration (v0.4.0+, optional for backward compat)",
    )
```

**ResolvedModel Extension**:
```python
class ResolvedModel(BaseModel):
    # ... existing fields ...

    # Epic 5B addition
    quality_checks: list[QualityCheck] | None = Field(
        default=None,
        description="Quality checks for this model (v0.4.0+)",
    )
    quality_tier: Literal["bronze", "silver", "gold"] | None = Field(
        default=None,
        description="Quality tier for this model (v0.4.0+)",
    )
```

---

## Implementation Phases

### Phase A: Core Schemas (floe-core)

1. Create `floe_core/schemas/quality_config.py`:
   - `Dimension` enum
   - `SeverityLevel` enum
   - `DimensionWeights` model
   - `CalculationParameters` model
   - `QualityThresholds` model
   - `GateTier` model
   - `QualityGates` model
   - `QualityConfig` model with inheritance support

2. Create `floe_core/schemas/quality_score.py`:
   - `QualityCheck` model (enhanced)
   - `QualityCheckResult` model (enhanced)
   - `QualitySuiteResult` model (enhanced)
   - `QualityScore` model

3. Extend `floe_core/plugins/quality.py`:
   - Add new abstract methods
   - Update existing methods with enhanced signatures
   - Add compile-time validation methods

4. Extend `floe_core/schemas/compiled_artifacts.py`:
   - Bump version to 0.4.0
   - Add `quality_config` field
   - Extend `ResolvedModel` with `quality_checks` and `quality_tier`

### Phase B: Reference Implementation - floe-quality-gx

1. Create plugin package structure
2. Implement `GreatExpectationsPlugin(QualityPlugin)`
3. Map floe quality checks to GX expectations
4. Implement scoring integration
5. Add dialect support (DuckDB, PostgreSQL, Snowflake)
6. Unit and integration tests

### Phase C: Reference Implementation - floe-quality-dbt

1. Create plugin package structure
2. Implement `DBTExpectationsPlugin(QualityPlugin)`
3. Execute quality checks as dbt tests via `DBTPlugin.test_models()`
4. Parse `run_results.json` for check results
5. Implement unified scoring with dbt test aggregation
6. Unit and integration tests

### Phase D: Compiler Integration

1. Add quality configuration parsing to compiler
2. Implement `validate_config()` invocation
3. Implement `validate_quality_gates()` invocation
4. Generate quality_config in CompiledArtifacts
5. Add quality checks to ResolvedModel

### Phase E: Runtime Integration

1. OrchestratorPlugin hooks for post-model quality checks
2. Connection configuration passthrough
3. Quality score calculation and aggregation
4. OpenLineage FAIL event emission
5. Threshold enforcement (min_score, warn_score)

### Phase F: Contract Tests

1. `tests/contract/test_quality_plugin_contract.py`
2. Plugin compliance tests (discovery, metadata, health_check)
3. CompiledArtifacts schema stability tests
4. Cross-package integration tests

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| GX 1.0 API changes | Pin version, abstract via adapter pattern |
| dbt-expectations compatibility | Test with multiple dbt versions in CI |
| Performance with 100+ checks | Parallel execution, timeout configuration |
| Inheritance conflict resolution | Clear precedence rules, FLOE-DQ107 error |
| Connection credential handling | Reuse ComputePlugin pattern (SecretStr) |

---

## Next Steps

1. Run `/speckit.tasks` to generate tasks.md with implementation order
2. Sync tasks to Linear
3. Begin Phase A: Core Schemas implementation
