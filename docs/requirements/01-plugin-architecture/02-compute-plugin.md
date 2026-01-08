# REQ-011 to REQ-024: ComputePlugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

ComputePlugin defines the interface for all compute engines (DuckDB, Snowflake, Spark, BigQuery, Databricks, Redshift, Trino). The multi-compute architecture enables:

1. **Platform teams** approve N compute targets (e.g., DuckDB, Spark, Snowflake)
2. **Data engineers** select compute per-transform from the approved list
3. **Hierarchical governance** (Enterprise → Domain → Product) restricts available computes
4. **Environment parity** preserved - each transform uses the SAME compute across dev/staging/prod

**Key ADR**: ADR-0010 (Multi-Compute Pipeline Architecture)

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

### REQ-021: ComputeRegistry Multi-Compute Support **[New]**

**Requirement**: System MUST support ComputeRegistry with multiple approved compute configurations and a default selection.

**Acceptance Criteria**:
- [ ] ComputeRegistry holds N compute configurations (dict[str, ComputeConfig])
- [ ] Default compute specified for fallback when transform doesn't specify
- [ ] All approved computes load their respective ComputePlugin implementations
- [ ] Validation ensures default is in approved list

**Enforcement**: Schema validation, compile-time checking
**Example**:
```yaml
plugins:
  compute:
    approved:
      - name: duckdb
        config: { threads: 8 }
      - name: spark
        config: { cluster: "spark.svc" }
    default: duckdb
```
**Test Coverage**: `tests/unit/test_compute_registry.py`
**Traceability**: ADR-0010, compiled-artifacts.md

---

### REQ-022: Per-Transform Compute Selection **[New]**

**Requirement**: Data engineers MUST be able to select compute per-transform from the platform's approved list.

**Acceptance Criteria**:
- [ ] `transforms[].compute` field accepts compute name string
- [ ] Compile-time validation ensures compute is in approved list
- [ ] When not specified, transform uses platform default compute
- [ ] InvalidComputeError raised when compute not in approved list

**Enforcement**: Compile-time validation, schema validation
**Example**:
```yaml
transforms:
  - type: dbt
    path: models/staging/
    compute: spark  # Heavy processing

  - type: dbt
    path: models/marts/
    compute: duckdb  # Analytics

  - type: dbt
    path: models/seeds/
    # Uses default from platform
```
**Test Coverage**: `tests/unit/test_per_transform_compute.py`
**Traceability**: ADR-0010, floe-yaml-schema.md

---

### REQ-023: Hierarchical Compute Governance **[New]**

**Requirement**: System MUST support hierarchical compute governance where each level can restrict available computes.

**Acceptance Criteria**:
- [ ] Enterprise manifest defines global approved set
- [ ] Domain manifest can restrict to subset of enterprise set
- [ ] Data product cannot use compute not in effective approved list
- [ ] Compile-time validation checks inheritance chain
- [ ] Clear error messages when compute not in any ancestor's approved list

**Enforcement**: Manifest inheritance validation, compile-time checking
**Example**:
```yaml
# Enterprise: approved: [duckdb, spark, snowflake, bigquery]
# Domain:     approved: [duckdb, spark]  # Subset only
# Product:    compute: spark  # Must be in domain's approved list
```
**Test Coverage**: `tests/unit/test_hierarchical_compute_governance.py`
**Traceability**: ADR-0010, ADR-0038 (Data Mesh Architecture)

---

### REQ-024: Environment Parity for Compute **[New]**

**Requirement**: System MUST enforce that each transform uses the SAME compute across all environments (dev/staging/prod).

**Acceptance Criteria**:
- [ ] Per-environment compute selection is FORBIDDEN (prevents drift)
- [ ] Validation fails if environments[].transforms.compute is specified
- [ ] Each transform's compute is resolved ONCE, used across all environments
- [ ] Clear error message explains why per-environment compute causes drift

**Enforcement**: Schema validation, compile-time checking
**Anti-Pattern** (FORBIDDEN):
```yaml
# ❌ This causes environment drift
environments:
  - name: development
    transforms:
      compute: duckdb
  - name: production
    transforms:
      compute: snowflake
```
**Test Coverage**: `tests/unit/test_environment_parity.py`
**Traceability**: ADR-0010

---

## Domain Acceptance Criteria

ComputePlugin Standards (REQ-011 to REQ-024) complete when:

- [ ] All 14 requirements documented with complete fields
- [ ] ComputePlugin ABC defined in floe-core
- [ ] At least 3 reference implementations (DuckDB, Snowflake, Spark)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate dbt execution
- [ ] Multi-compute pipeline execution validated end-to-end
- [ ] Hierarchical governance validated (Enterprise → Domain → Product)
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 4A: ComputePlugin Architecture** - Multi-compute pipeline support with hierarchical governance
