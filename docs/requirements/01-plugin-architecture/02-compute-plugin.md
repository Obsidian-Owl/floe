# REQ-011 to REQ-020: ComputePlugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

ComputePlugin defines the interface for all compute engines (DuckDB, Snowflake, Spark, BigQuery, Databricks, Redshift, Trino). This enables platform teams to select a single compute target that all data engineers inherit.

**Key ADR**: ADR-0010 (Target-Agnostic Compute)

## Requirements

### REQ-011: ComputePlugin ABC Definition **[New]**

**Requirement**: ComputePlugin MUST define abstract methods: generate_dbt_profile(), get_required_dbt_packages(), validate_connection(), get_resource_requirements(), get_catalog_attachment_sql().

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 5 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_compute_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md:103-142, ADR-0010

---

### REQ-012: ComputePlugin Profile Generation **[Evolution]**

**Requirement**: ComputePlugin.generate_dbt_profile() MUST return valid dbt profiles.yml target configuration that passes `dbt debug`.

**Acceptance Criteria**:
- [ ] Returns dict[str, Any] matching dbt profiles schema
- [ ] Includes type, threads, schema/database/dataset
- [ ] Supports SecretReference pattern for credentials
- [ ] dbt debug succeeds with generated profile

**Enforcement**: dbt debug integration tests for each compute plugin
**Test Coverage**: `tests/integration/test_compute_profile_generation.py`
**Traceability**: plugin-architecture.md:114-116, ADR-0009

**Evolution from MVP**:
- **MVP**: Hardcoded profile generation for 7 compute targets in floe-dbt
- **Target**: Plugin-based generation via ComputePlugin.generate_dbt_profile()
- **Migration**: Extract each compute target to separate plugin package

---

### REQ-013: ComputePlugin Catalog Attachment **[New]**

**Requirement**: ComputePlugin.get_catalog_attachment_sql() MUST return SQL statements to connect compute engine to Iceberg catalog, or None if not applicable.

**Acceptance Criteria**:
- [ ] DuckDB returns ATTACH statement with iceberg extension
- [ ] Snowflake/BigQuery return None (external table config)
- [ ] SQL statements are valid for compute engine
- [ ] Returns None for cloud data warehouses with native Iceberg support

**Enforcement**: SQL execution tests against real compute engines
**Example**: DuckDB returns `ATTACH 'iceberg://catalog' AS ice (TYPE ICEBERG)`
**Test Coverage**: `tests/integration/test_catalog_attachment.py`
**Traceability**: plugin-architecture.md:416-477, ADR-0034

---

### REQ-014: ComputePlugin Connection Validation **[Preserved]**

**Requirement**: ComputePlugin.validate_connection() MUST test connectivity and return ValidationResult within 10 seconds or timeout.

**Acceptance Criteria**:
- [ ] Connects to compute engine within timeout
- [ ] Returns ValidationResult(success, message, details)
- [ ] Actionable error messages (not stack traces)
- [ ] Validates credentials without exposing them in logs

**Enforcement**: Connection validation tests, timeout tests
**Test Coverage**: `tests/integration/test_compute_connection_validation.py`
**Traceability**: plugin-architecture.md:124-126

---

### REQ-015: ComputePlugin Resource Requirements **[New]**

**Requirement**: ComputePlugin.get_resource_requirements() MUST return K8s ResourceRequirements (CPU, memory, GPU) with sensible defaults.

**Acceptance Criteria**:
- [ ] Returns K8s ResourceRequirements dict
- [ ] Includes requests and limits
- [ ] Default values appropriate for compute engine
- [ ] User can override via platform.yaml

**Enforcement**: Resource requirement tests, K8s pod deployment validation
**Test Coverage**: `tests/unit/test_compute_resources.py`
**Traceability**: plugin-architecture.md:129-131

---

### REQ-016: ComputePlugin Credential Delegation **[New]**

**Requirement**: ComputePlugin MUST support short-lived credential delegation from CatalogPlugin via X-Iceberg-Access-Delegation header.

**Acceptance Criteria**:
- [ ] Accepts vended credentials from catalog
- [ ] Uses vended credentials for Iceberg table access
- [ ] Credentials expire and refresh automatically
- [ ] No credentials logged or in error messages

**Enforcement**: Credential rotation tests, token expiration tests
**Test Coverage**: `tests/integration/test_credential_vending.py`
**Traceability**: plugin-architecture.md, ADR-0023

---

### REQ-017: ComputePlugin Package Dependencies **[Preserved]**

**Requirement**: ComputePlugin.get_required_dbt_packages() MUST return list of required dbt adapter packages with version constraints.

**Acceptance Criteria**:
- [ ] Returns list[str] with package names
- [ ] Includes version constraints (>=, <)
- [ ] dbt adapter packages install successfully
- [ ] Version constraints avoid known conflicts

**Enforcement**: Package installation tests, dbt adapter detection tests
**Example**: `["dbt-duckdb>=1.9.0,<2.0.0"]`
**Test Coverage**: `tests/unit/test_compute_dependencies.py`
**Traceability**: plugin-architecture.md:119-121

---

### REQ-018: ComputePlugin Error Handling **[New]**

**Requirement**: ComputePlugin MUST handle compute engine errors gracefully with actionable error messages.

**Acceptance Criteria**:
- [ ] Catches compute-specific exceptions
- [ ] Translates to PluginExecutionError with context
- [ ] Error messages suggest resolution steps
- [ ] No stack traces exposed to end users

**Enforcement**: Error handling tests, error message validation
**Test Coverage**: `tests/unit/test_compute_error_handling.py`
**Traceability**: ADR-0025 (Exception Handling)

---

### REQ-019: ComputePlugin Type Safety **[New]**

**Requirement**: ComputePlugin implementations MUST pass mypy --strict with full type annotations.

**Acceptance Criteria**:
- [ ] All methods have type hints
- [ ] Return types match ABC signature
- [ ] mypy --strict passes on plugin implementation
- [ ] No use of Any except for truly dynamic values

**Enforcement**: mypy in CI/CD, type checking tests
**Test Coverage**: CI/CD mypy validation
**Traceability**: python-standards.md

---

### REQ-020: ComputePlugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseComputePluginTests class that all ComputePlugin implementations inherit to validate compliance.

**Acceptance Criteria**:
- [ ] BaseComputePluginTests in testing/base_classes/
- [ ] Tests all ABC methods
- [ ] Tests profile generation validity
- [ ] Tests connection validation
- [ ] Tests resource requirements structure

**Enforcement**: Plugin compliance tests must pass for all compute plugins
**Test Coverage**: `testing/base_classes/base_compute_plugin_tests.py`
**Traceability**: TESTING.md

---

## Domain Acceptance Criteria

ComputePlugin Standards (REQ-011 to REQ-020) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] ComputePlugin ABC defined in floe-core
- [ ] At least 3 reference implementations (DuckDB, Snowflake, Spark)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate dbt execution
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract 7 MVP compute targets to plugins
