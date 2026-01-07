# ADR-0044: Unified Data Quality Plugin Architecture

## Status

Accepted

## Context

Data quality is a cross-cutting concern that spans multiple execution contexts:

- **Compile-time**: Configuration validation, quality gate enforcement, coverage checks
- **Runtime**: Live data validation, continuous monitoring, quality scoring

### The Composability Question

Should data quality be:
1. **Multiple separate plugins**: CompileTimeQualityPlugin + RuntimeQualityPlugin + QualityMonitorPlugin
2. **Unified plugin**: DataQualityPlugin with compile-time and runtime methods

The fragmented approach creates "Why 3 places for 1 concept?" problem and violates ADR-0037 (Composability Principle).

### Options Considered

**Option 1: Separate Compile-Time and Runtime Plugins**
- CompileTimeQualityPlugin: Config validation, quality gates
- RuntimeQualityPlugin: Data checks, scoring
- Rationale: Different execution contexts require different interfaces

**Option 2: Fragmented Responsibilities**
- PolicyEnforcer: Config validation
- QualityGateValidator: Threshold enforcement
- DataContractPlugin: Runtime execution
- Rationale: Separation of concerns

**Option 3: Unified DataQualityPlugin (CHOSEN)**
- Single plugin interface with compile-time and runtime methods
- Clear method contracts separate execution contexts
- Rationale: Composability, simplicity, single responsibility

## Decision

**Create unified DataQualityPlugin interface** that handles ALL data quality concerns with separated methods for compile-time and runtime execution.

### Key Insight

Execution context difference (compile vs runtime) does NOT require separate plugin interfaces. Methods can be clearly separated within a SINGLE interface through:
- Method naming conventions (validate_* vs execute_*)
- Parameter requirements (dbt_manifest vs DatabaseConnection)
- Documentation contracts (what each method can/cannot do)

### Rationale

**Composability (ADR-0037)**:
- Platform team chooses Great Expectations vs Soda in ONE place
- Single entry point: `floe.data_quality`
- Single configuration: `plugins.data_quality.provider`

**Simplicity**:
- "How do I add quality checks?" → "Implement DataQualityPlugin"
- No mental overhead deciding which interface to use
- Easier onboarding for plugin developers

**Single Responsibility**:
- DataQualityPlugin owns ALL data quality concerns
- Clear boundary: PolicyEnforcer handles CODE quality (SQL linting)
- dbt tests remain enforced (wrapped for unified scoring)

**Testing**:
- Mock single interface instead of 3 separate ones
- Easier to test compile-time vs runtime behavior
- Clear contracts in method signatures

## Consequences

### Positive

- **Composability**: Switch from Great Expectations to Soda by changing ONE config line
- **Developer Experience**: Clear mental model for adding quality checks
- **Unified Scoring**: Combine dbt tests + GX/Soda checks + custom checks with configurable weights
- **Maintainability**: Single interface to evolve and version

### Negative

- **Plugin Complexity**: Implementations must handle both compile-time and runtime contexts
- **Connection Management**: Runtime methods require database connection handling
- **Weight Tuning**: Quality score calculation needs careful configuration

### Neutral

- dbt tests remain enforced (ADR-0009), wrapped by DBTExpectationsPlugin for unified scoring
- SQL linting stays in PolicyEnforcer (CODE quality, not DATA quality)
- OrchestratorPlugin post-hook sends dbt test results to ContractMonitor

## Interface Design

### DataQualityPlugin ABC

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from floe_core.schemas import ValidationResult, QualityCheckResult, QualityExpectation


class DataQualityPlugin(ABC):
    """Unified interface for data quality frameworks.

    Implementations: GreatExpectationsPlugin, SodaPlugin, DBTExpectationsPlugin
    Entry point: floe.data_quality
    Platform config: plugins.data_quality.provider

    Responsibilities:
    - Validate quality check configuration at compile-time
    - Enforce quality gate thresholds at compile-time
    - Execute quality checks against live data at runtime
    - Calculate quality scores at runtime
    - Provide OpenLineage integration
    """

    # Plugin metadata
    name: str  # e.g., "great_expectations", "soda", "dbt_expectations"
    version: str
    floe_api_version: str

    # COMPILE-TIME METHODS (No data access required)

    @abstractmethod
    def validate_config(
        self,
        config_path: Path,
        dbt_manifest: dict[str, Any]
    ) -> ValidationResult:
        """Validate quality check configuration at compile-time.

        Validates configuration syntax and structure WITHOUT accessing data.

        Examples:
        - Great Expectations: Validate expectation suite YAML syntax
        - Soda: Validate soda.yml checks configuration
        - Custom: Validate proprietary check definitions

        Args:
            config_path: Path to quality check configuration file
            dbt_manifest: Parsed dbt manifest.json for column reference validation

        Returns:
            ValidationResult with success/failure and error messages

        Validates:
        - Configuration file syntax (YAML/JSON)
        - Expectation/check types are valid
        - Column references exist in dbt manifest
        - Configuration completeness (required fields present)

        Does NOT validate:
        - Actual data values
        - Database connectivity
        - Query performance

        Raises:
            ValidationError: If configuration is invalid
        """
        pass

    @abstractmethod
    def validate_quality_gates(
        self,
        manifest: dict[str, Any],
        required_coverage: dict[str, float]
    ) -> ValidationResult:
        """Enforce quality gate thresholds at compile-time.

        Validates that quality gate requirements are met based on
        static analysis of dbt manifest and quality check definitions.

        Examples:
        - Bronze tier: ≥50% of models have quality checks
        - Silver tier: ≥80% coverage + required check types [not_null, unique]
        - Gold tier: 100% coverage + all required check types

        Args:
            manifest: Parsed dbt manifest.json
            required_coverage: Coverage requirements per tier
                Example: {"bronze": 0.5, "silver": 0.8, "gold": 1.0}

        Returns:
            ValidationResult with pass/fail and coverage statistics

        Checks:
        - Test coverage percentage meets thresholds
        - Required test types are present (not_null, unique, etc.)
        - Threshold values are sane (0-100 range)

        Raises:
            ValidationError: If quality gates not met
        """
        pass

    # RUNTIME METHODS (Require data access)

    @abstractmethod
    def execute_checks(
        self,
        connection: DatabaseConnection,
        expectations: list[QualityExpectation]
    ) -> QualityCheckResult:
        """Execute quality checks against live data at runtime.

        Runs data validation checks that require database access.

        Runtime context:
        - Database connection is available
        - Can query actual data
        - Emits OpenLineage FAIL events on violations
        - May take seconds/minutes for large datasets

        Args:
            connection: Database connection for querying data
            expectations: List of quality checks to execute

        Returns:
            QualityCheckResult with pass/fail per check and error details

        Examples:
        - Great Expectations: Run expectation suite validations
        - Soda: Execute soda.yml checks
        - Custom: Run proprietary data validation logic

        Raises:
            RuntimeError: If checks cannot be executed
        """
        pass

    @abstractmethod
    def calculate_quality_score(
        self,
        check_results: list[QualityCheckResult],
        weights: dict[str, float]
    ) -> float:
        """Calculate overall quality score (0-100) with weighted formula.

        Combines multiple quality check results into a single score
        using configurable weights.

        Formula:
            score = sum(result.passed * weight) / sum(weight) * 100

        Args:
            check_results: Results from execute_checks() and dbt tests
            weights: Weight multipliers per check type
                Example: {
                    "critical_checks": 3.0,
                    "standard_checks": 1.0,
                    "statistical_checks": 0.5
                }

        Returns:
            Quality score from 0 (all checks failed) to 100 (all checks passed)

        Combines:
        - dbt test results (from OrchestratorPlugin post-hook)
        - Great Expectations check results
        - Soda check results
        - Custom check results

        Raises:
            ValueError: If weights are invalid or check_results is empty
        """
        pass

    # INTEGRATION METHODS

    @abstractmethod
    def get_lineage_emitter(self) -> LineageEmitter:
        """Get OpenLineage emitter for this data quality tool.

        Returns OpenLineage emitter that knows how to emit:
        - FAIL events when quality checks fail
        - Dataset facets with quality metadata
        - Job facets with check execution details

        Returns:
            LineageEmitter configured for this DQ tool
        """
        pass

    @abstractmethod
    def supports_sql_dialect(self, dialect: str) -> bool:
        """Check if data quality tool supports given SQL dialect.

        Args:
            dialect: SQL dialect (snowflake, bigquery, postgres, etc.)

        Returns:
            True if dialect is supported, False otherwise
        """
        pass
```

### Entry Point Configuration

```toml
# Plugin registration in pyproject.toml
[project.entry-points."floe.data_quality"]
great_expectations = "floe_dq_great_expectations:GreatExpectationsPlugin"
soda = "floe_dq_soda:SodaPlugin"
dbt_expectations = "floe_dq_dbt:DBTExpectationsPlugin"
custom = "floe_dq_custom:CustomPlugin"
```

### Platform Configuration

```yaml
# platform-manifest.yaml
apiVersion: floe.dev/v1
kind: Manifest
metadata:
  name: acme-platform
  version: "1.0.0"

plugins:
  compute: snowflake
  orchestrator: dagster
  catalog: polaris

  data_quality:
    provider: great_expectations  # Single choice per platform
    config:
      # Quality gate thresholds
      quality_gates:
        bronze:
          min_test_coverage: 50%
        silver:
          min_test_coverage: 80%
          required_tests: [not_null, unique]
        gold:
          min_test_coverage: 100%
          required_tests: [not_null, unique, relationships]

      # Scoring weights
      weights:
        critical_checks: 3.0
        standard_checks: 1.0
        statistical_checks: 0.5

      # Deployment gates
      thresholds:
        min_score: 70.0  # Block deployment if score < 70
        warn_score: 85.0  # Warn if score < 85
```

## Delegation Architecture

### DataQualityPlugin and DataContractPlugin Interaction

Data quality checking involves two plugins working together:

- **DataQualityPlugin** (this ADR) - Executes data quality checks using frameworks like Great Expectations or Soda
- **DataContractPlugin** (ADR-0026) - Defines quality rules as part of contract definitions

The relationship is a **delegation pattern**:

```
                     COMPILE TIME                        RUNTIME
                     ─────────────                        ───────
                          │                                  │
  FloeSpec + Manifest ────┤                                  │
                          │                                  ▼
                          │                          ContractMonitor
  PolicyEnforcer ────────►├─ Validate config              (ADR-0028)
  (ADR-0015)              │─ Validate quality gates             │
                          │         │                      Registered contracts
                          │         │                           │
                          │         ▼                      ┌────┤
                          │    CompiledArtifacts           │    │
                          │    (contracts + expectations)  │    │
                          │         │                      │    │
                          └─────────┼──────────────────────┘    │
                                    │                           │
                                    │   RUNTIME DELEGATION      │
                                    │   ──────────────────      │
                                    │                           │
                          DataQualityPlugin                     │
                          (This ADR - ABC)                      │
                          ──────────────────                    │
                          ├─ execute_checks() ◄────────────────┘
                          ├─ calculate_quality_score()
                          ├─ validate_config()
                          ├─ validate_quality_gates()
                          └─ get_lineage_emitter()
                                    │
                                    ▼
                          OpenLineage FAIL events
                          (Quality check violations)
```

### Method Separation

| Method | Owner | Timing | Requires Data? | Called By |
|--------|-------|--------|----------------|-----------|
| `validate_config()` | DataQualityPlugin | Compile | No | PolicyEnforcer |
| `validate_quality_gates()` | DataQualityPlugin | Compile | No | PolicyEnforcer |
| `execute_checks()` | DataQualityPlugin | Runtime | **Yes** | ContractMonitor |
| `calculate_quality_score()` | DataQualityPlugin | Runtime | No (uses results) | OrchestratorPlugin |

### Boundary Rules

1. **DataQualityPlugin owns:**
   - Configuration validation (compile-time)
   - Quality gate enforcement (compile-time)
   - Data quality checks (runtime)
   - Quality score calculation (runtime)
   - OpenLineage integration (runtime)

2. **DataContractPlugin owns:**
   - Contract parsing (compile & runtime)
   - Schema validation (compile & runtime)
   - SLA definitions (compile & runtime)
   - Contract versioning (lifecycle)
   - **DELEGATES quality checks to DataQualityPlugin** (runtime)

3. **Clear responsibility separation:**
   - DataContractPlugin: "What quality checks should run?" (schema + SLA)
   - DataQualityPlugin: "How do we run them?" (framework integration)

## Responsibility Boundaries

### DataQualityPlugin (This ADR)
✅ Validate quality check configuration at compile-time
✅ Enforce quality gate thresholds at compile-time
✅ Execute data checks against live data at runtime
✅ Calculate quality scores at runtime
✅ Provide OpenLineage integration

### PolicyEnforcer (ADR-0015)
✅ SQL linting (SQLFluff, dbt-checkpoint)
✅ CODE quality checks (syntax, style, anti-patterns)
❌ NOT data quality validation

### dbt Tests (ADR-0009)
✅ ENFORCED (native to dbt framework)
✅ NOT pluggable (dbt owns SQL)
✅ Wrapped by DBTExpectationsPlugin for unified scoring

### OrchestratorPlugin
✅ Post-run hook sends dbt test results to ContractMonitor
✅ ContractMonitor ingests results for quality score calculation

## Requirements Mapping

### REQ-207: Great Expectations Integration
**Compile-time**: `DataQualityPlugin.validate_config()` validates GX expectation suite configuration
**Runtime**: `DataQualityPlugin.execute_checks()` runs GX validations against live data

### REQ-241-244: Quality Gates
**Compile-time**: `DataQualityPlugin.validate_quality_gates()` enforces coverage thresholds
**Configuration**: Platform-level config defines bronze/silver/gold tier requirements

### REQ-248: Quality Monitoring via Great Expectations
**Runtime**: ContractMonitor calls `DataQualityPlugin.execute_checks()` every 6 hours
**Observability**: Continuous monitoring emits OpenLineage FAIL events on violations

### NEW: Quality Score Calculation
**Runtime**: `DataQualityPlugin.calculate_quality_score()` provides 0-100 score
**Integration**: Combines dbt tests + GX/Soda checks + custom checks with configurable weights

## Implementation Roadmap

### Epic 3: Foundation (Current)
- Create `DataQualityPlugin` ABC in `floe-core`
- Define entry point: `floe.data_quality`
- Add `DataQualityPlugin` to plugin discovery in `floe-core/src/floe_core/plugin_registry.py`
- Document interface in `docs/architecture/plugin-architecture.md`
- Update requirements documentation (REQ-207, REQ-241-244, REQ-248)

### Epic 7: Great Expectations Implementation
- Implement `GreatExpectationsPlugin` in `plugins/floe-dq-great-expectations/`
- **Compile-time**: `validate_config()` for expectation suite syntax validation
- **Compile-time**: `validate_quality_gates()` for coverage enforcement
- **Runtime**: `execute_checks()` for live data validation via GX Python API
- **Integration**: `get_lineage_emitter()` for OpenLineage integration
- **Testing**: Unit tests (compile-time), integration tests (runtime with real data)

### Epic 8+: Additional Providers
- Implement `SodaPlugin` in `plugins/floe-dq-soda/`
- Implement `DBTExpectationsPlugin` in `plugins/floe-dq-dbt/` (wraps dbt native tests)
- Implement `CustomPlugin` for proprietary quality checks
- Add provider comparison documentation

## Migration from Fragmented Design

This ADR represents the TARGET STATE design. If any fragmented interfaces exist (QualityGateValidator, PolicyEnforcer GX validation), they should be consolidated into DataQualityPlugin.

**No legacy refactoring** - this is the clean target state architecture.

## Related ADRs

- [ADR-0009: dbt Owns SQL](0009-dbt-owns-sql.md) - dbt tests are enforced
- [ADR-0015: Policy Enforcement](0015-policy-enforcement.md) - PolicyEnforcer handles SQL linting
- [ADR-0037: Composability Principle](0037-composability-principle.md) - Plugin interface > configuration switch
- [ADR-0038: Data Mesh Architecture](0038-data-mesh-architecture.md) - Enterprise → Domain → Product inheritance

## References

- REQ-207: Great Expectations Integration
- REQ-241-244: Quality Gates
- REQ-248: Quality Monitoring via Great Expectations
- [Great Expectations Documentation](https://docs.greatexpectations.io/)
- [Soda Documentation](https://docs.soda.io/)
- [OpenLineage Specification](https://openlineage.io/)
