# REQ-101 to REQ-110: DataQualityPlugin Standards

**Domain**: Plugin Architecture
**Priority**: HIGH
**Status**: Complete specification

## Overview

DataQualityPlugin defines the interface for data quality frameworks (Great Expectations, Soda, dbt Expectations). This enables platform teams to select a data quality tool while maintaining consistent quality validation patterns.

**Key ADR**: ADR-0044 (Unified Data Quality Plugin)

## Requirements

### REQ-101: DataQualityPlugin ABC Definition **[New]**

**Requirement**: DataQualityPlugin MUST define abstract methods: `validate_config()`, `validate_quality_gates()`, `execute_checks()`, `calculate_quality_score()`, `get_lineage_emitter()`, `supports_sql_dialect()`.

**Rationale**: Enforces consistent interface across all data quality implementations.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 6 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition
- [ ] Plugin metadata: name, version, floe_api_version

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_data_quality_plugin.py::test_abc_compliance`
**Traceability**: interfaces/data-quality-plugin.md, ADR-0044

---

### REQ-102: DataQualityPlugin Configuration Validation **[New]**

**Requirement**: DataQualityPlugin.validate_config() MUST validate quality check configuration syntax at compile-time without data access.

**Rationale**: Catches configuration errors before runtime, reducing failed job executions.

**Acceptance Criteria**:
- [ ] Accepts config_path (Path) and dbt_manifest (dict)
- [ ] Returns ValidationResult with success status and errors
- [ ] Validates check syntax per framework specification
- [ ] Cross-references dbt manifest for model existence
- [ ] No database connectivity required (compile-time only)

**Enforcement**: Configuration validation tests, schema validation tests
**Test Coverage**: `tests/unit/test_data_quality_config_validation.py`
**Traceability**: ADR-0044, plugin-system/interfaces.md

---

### REQ-103: DataQualityPlugin Quality Gate Enforcement **[New]**

**Requirement**: DataQualityPlugin.validate_quality_gates() MUST enforce quality gate thresholds defined in manifest.yaml at compile-time.

**Rationale**: Ensures data products meet minimum quality standards before deployment.

**Acceptance Criteria**:
- [ ] Validates against quality_gates config from manifest.yaml
- [ ] Layer-specific thresholds (bronze: 50%, silver: 80%, gold: 100%)
- [ ] Required tests per layer (not_null, unique, relationships)
- [ ] Returns ValidationResult with gate violations
- [ ] Clear error messages with required vs actual coverage

**Enforcement**: Quality gate tests per layer, threshold validation tests
**Test Coverage**: `tests/unit/test_data_quality_gates.py`
**Traceability**: ADR-0044, platform-enforcement.md

**Configuration Example**:
```yaml
# manifest.yaml
plugins:
  data_quality:
    provider: great_expectations
    config:
      quality_gates:
        bronze: {min_test_coverage: 50%}
        silver: {min_test_coverage: 80%, required_tests: [not_null, unique]}
        gold: {min_test_coverage: 100%, required_tests: [not_null, unique, relationships]}
```

---

### REQ-104: DataQualityPlugin Runtime Execution **[New]**

**Requirement**: DataQualityPlugin.execute_checks() MUST execute quality checks against live data and return QualityCheckResult.

**Rationale**: Validates actual data quality at runtime, not just configuration correctness.

**Acceptance Criteria**:
- [ ] Accepts DatabaseConnection and list of QualityExpectation
- [ ] Executes checks against live database
- [ ] Returns QualityCheckResult with pass/fail per expectation
- [ ] Includes row counts, failure details, execution time
- [ ] Supports timeout and cancellation

**Enforcement**: Integration tests with real database, execution timeout tests
**Test Coverage**: `tests/integration/test_data_quality_execution.py`
**Traceability**: ADR-0044

---

### REQ-105: DataQualityPlugin Quality Scoring **[New]**

**Requirement**: DataQualityPlugin.calculate_quality_score() MUST compute overall quality score (0-100) using configurable weights.

**Rationale**: Provides single quality metric for dashboards and alerts.

**Acceptance Criteria**:
- [ ] Accepts list of QualityCheckResult and weights dict
- [ ] Returns float score between 0 and 100
- [ ] Weights configurable per check type (critical: 3.0, standard: 1.0, statistical: 0.5)
- [ ] Score formula documented and consistent
- [ ] Zero score if any critical check fails

**Enforcement**: Scoring calculation tests, weight configuration tests
**Test Coverage**: `tests/unit/test_data_quality_scoring.py`
**Traceability**: ADR-0044

**Scoring Formula**:
```
score = sum(weight * pass_rate) / sum(weights) * 100
```

---

### REQ-106: DataQualityPlugin OpenLineage Integration **[New]**

**Requirement**: DataQualityPlugin.get_lineage_emitter() MUST return LineageEmitter for emitting quality check events to OpenLineage backend.

**Rationale**: Enables data quality visibility in lineage graphs and governance dashboards.

**Acceptance Criteria**:
- [ ] Returns LineageEmitter configured for quality events
- [ ] Emits DataQualityMetrics facet per OpenLineage spec
- [ ] Includes pass/fail status per dataset
- [ ] Links quality events to producing job via run_id
- [ ] Integrates with LineageBackendPlugin transport

**Enforcement**: Lineage emission tests, facet validation tests
**Test Coverage**: `tests/integration/test_data_quality_lineage.py`
**Traceability**: ADR-0044, ADR-0035

---

### REQ-107: DataQualityPlugin SQL Dialect Support **[New]**

**Requirement**: DataQualityPlugin.supports_sql_dialect() MUST indicate whether the quality tool supports a given SQL dialect.

**Rationale**: Enables compile-time validation that quality tool matches compute engine.

**Acceptance Criteria**:
- [ ] Accepts dialect string (duckdb, snowflake, bigquery, etc.)
- [ ] Returns bool indicating support
- [ ] Compiler validates dialect compatibility before deployment
- [ ] Clear error if dialect not supported

**Enforcement**: Dialect support tests per implementation
**Test Coverage**: `tests/unit/test_data_quality_dialect_support.py`
**Traceability**: ADR-0044

---

### REQ-108: DataQualityPlugin Error Handling **[New]**

**Requirement**: DataQualityPlugin MUST handle quality check failures gracefully with actionable error messages.

**Rationale**: Enables operators to diagnose and fix quality issues.

**Acceptance Criteria**:
- [ ] Catches framework-specific exceptions
- [ ] Translates to PluginExecutionError with context
- [ ] Error messages include failed expectation details
- [ ] No stack traces exposed to end users
- [ ] Includes query that failed (sanitized)

**Enforcement**: Error handling tests, error message validation
**Test Coverage**: `tests/unit/test_data_quality_error_handling.py`
**Traceability**: ADR-0025 (Exception Handling)

---

### REQ-109: DataQualityPlugin Type Safety **[New]**

**Requirement**: DataQualityPlugin implementations MUST pass mypy --strict with full type annotations.

**Acceptance Criteria**:
- [ ] All methods have type hints
- [ ] Return types match ABC signature
- [ ] mypy --strict passes on plugin implementation
- [ ] No use of Any except for truly dynamic values

**Enforcement**: mypy in CI/CD, type checking tests
**Test Coverage**: CI/CD mypy validation
**Traceability**: python-standards.md

---

### REQ-110: DataQualityPlugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseDataQualityPluginTests class that all DataQualityPlugin implementations inherit to validate compliance.

**Rationale**: Ensures all quality tools meet minimum functionality requirements.

**Acceptance Criteria**:
- [ ] BaseDataQualityPluginTests in testing/base_classes/
- [ ] Tests all ABC methods
- [ ] Tests config validation (compile-time)
- [ ] Tests quality gate enforcement
- [ ] Tests runtime execution with mock database
- [ ] Tests scoring calculation

**Enforcement**: Plugin compliance tests must pass for all quality tools
**Test Coverage**: `testing/base_classes/base_data_quality_plugin_tests.py`
**Traceability**: TESTING.md

---

## Entry Points

```toml
[project.entry-points."floe.data_quality"]
great_expectations = "floe_dq_great_expectations:GreatExpectationsPlugin"
soda = "floe_dq_soda:SodaPlugin"
dbt_expectations = "floe_dq_dbt:DBTExpectationsPlugin"
```

## Reference Implementations

| Plugin | Description | Priority |
|--------|-------------|----------|
| `GreatExpectationsPlugin` | Great Expectations Python API wrapper | Epic 7 |
| `SodaPlugin` | Soda Core integration | Epic 8+ |
| `DBTExpectationsPlugin` | Wraps dbt native tests for unified scoring | Epic 8+ |

## Domain Acceptance Criteria

DataQualityPlugin Standards (REQ-101 to REQ-110) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] DataQualityPlugin ABC defined in floe-core
- [ ] At least 1 reference implementation (Great Expectations)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate runtime execution
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 7: Data Quality Infrastructure** - Implement DataQualityPlugin and Great Expectations integration
