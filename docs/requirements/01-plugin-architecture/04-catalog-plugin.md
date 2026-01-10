# REQ-031 to REQ-041: CatalogPlugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

CatalogPlugin defines the interface for all data catalogs (Polaris, AWS Glue, Hive, Bigquery Dataplex). This enables data governance enforcement at the catalog layer while maintaining flexibility in catalog implementation choice.

**Key ADR**: ADR-0005 (Apache Iceberg as Enforced Table Format) - CatalogPlugin manages Iceberg catalog metadata

## Requirements

### REQ-031: CatalogPlugin ABC Definition **[New]**

**Requirement**: CatalogPlugin MUST define abstract methods: create_catalog(), load_catalog(), list_namespaces(), create_namespace(), create_table(), vend_credentials().

**Rationale**: Enforces consistent interface across all catalog implementations.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 6 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_catalog_plugin.py::test_abc_compliance`
**Traceability**: interfaces/catalog-plugin.md, ADR-0005

---

### REQ-032: CatalogPlugin Catalog Creation **[New]**

**Requirement**: CatalogPlugin.create_catalog() MUST create a new Iceberg catalog in the underlying storage backend.

**Rationale**: Enables multi-tenant isolation by creating separate catalogs per domain.

**Acceptance Criteria**:
- [ ] Creates catalog with specified name and location
- [ ] Returns catalog reference (URI or identifier)
- [ ] Catalog is queryable immediately after creation
- [ ] Idempotent: creating same catalog twice returns same reference

**Enforcement**: Catalog creation tests, idempotency tests
**Test Coverage**: `tests/integration/test_catalog_creation.py`
**Traceability**: plugin-architecture.md

---

### REQ-033: CatalogPlugin Catalog Loading **[New]**

**Requirement**: CatalogPlugin.load_catalog() MUST load an existing Iceberg catalog and return a PyIceberg Catalog instance.

**Rationale**: Enables interaction with existing catalogs created elsewhere.

**Acceptance Criteria**:
- [ ] Returns PyIceberg Catalog instance
- [ ] Catalog is immediately usable for queries
- [ ] Handles invalid catalog names gracefully
- [ ] Returns ValidationResult on failure

**Enforcement**: Catalog loading tests, error handling tests
**Test Coverage**: `tests/integration/test_catalog_loading.py`
**Traceability**: plugin-architecture.md

---

### REQ-034: CatalogPlugin Namespace Management **[Preserved]**

**Requirement**: CatalogPlugin MUST support namespace operations: list_namespaces(), create_namespace(), delete_namespace().

**Rationale**: Enables data organization within catalogs (bronze/silver/gold pattern).

**Acceptance Criteria**:
- [ ] Lists all namespaces in catalog
- [ ] Creates new namespace with properties
- [ ] Deletes empty namespaces
- [ ] Prevents deletion of non-empty namespaces
- [ ] Handles invalid names with clear errors

**Enforcement**: Namespace operation tests, error handling tests
**Test Coverage**: `tests/integration/test_catalog_namespaces.py`
**Traceability**: plugin-architecture.md

---

### REQ-035: CatalogPlugin Credential Vending **[New]**

**Requirement**: CatalogPlugin.vend_credentials() MUST return short-lived credentials for accessing Iceberg tables in the catalog's warehouse.

**Rationale**: Enables least-privilege access by vending credentials scoped to specific namespaces or tables.

**Acceptance Criteria**:
- [ ] Returns temporary credentials (S3 tokens, GCS signed URLs, etc.)
- [ ] Credentials expire within 24 hours
- [ ] Can scope credentials to specific namespaces or tables
- [ ] Credentials not logged or exposed in errors
- [ ] Supports delegation from data catalog service to compute engine

**Enforcement**: Credential vending tests, expiration tests, security tests
**Example**: Polaris returns S3 tokens via X-Iceberg-Access-Delegation header
**Test Coverage**: `tests/integration/test_credential_vending.py`
**Traceability**: plugin-architecture.md, ADR-0023

---

### REQ-036: CatalogPlugin Table Operations **[New]**

**Requirement**: CatalogPlugin MUST support table operations: create_table(), list_tables(), drop_table(), update_table_metadata().

**Rationale**: Enables dynamic table lifecycle management without manual catalog operations.

**Acceptance Criteria**:
- [ ] Creates Iceberg tables with schema validation
- [ ] Lists tables in namespace with filtering
- [ ] Drops tables and cleanup metadata
- [ ] Updates table metadata (properties, schema evolution)
- [ ] Prevents operations on non-existent tables

**Enforcement**: Table operation tests, metadata validation tests
**Test Coverage**: `tests/integration/test_catalog_table_operations.py`
**Traceability**: plugin-architecture.md

---

### REQ-037: CatalogPlugin Connection Validation **[Preserved]**

**Requirement**: CatalogPlugin.validate_connection() MUST test connectivity to catalog backend and return ValidationResult within 10 seconds or timeout.

**Rationale**: Pre-deployment validation ensures catalog is reachable and authenticated.

**Acceptance Criteria**:
- [ ] Connects to catalog endpoint
- [ ] Returns ValidationResult(success, message, details)
- [ ] Actionable error messages (not stack traces)
- [ ] Timeout enforced at 10 seconds
- [ ] Validates credentials without exposing them

**Enforcement**: Connection validation tests, timeout tests
**Test Coverage**: `tests/integration/test_catalog_connection_validation.py`
**Traceability**: plugin-architecture.md

---

### REQ-038: CatalogPlugin Observability Integration **[New]**

**Requirement**: CatalogPlugin MUST emit OpenTelemetry traces for all catalog operations and support request/response tracing.

**Rationale**: Enables debugging of catalog integration issues and performance monitoring.

**Acceptance Criteria**:
- [ ] Emits OTLP spans for create_catalog, create_table, etc.
- [ ] Includes operation duration and status in spans
- [ ] Traces include catalog name, namespace, table name
- [ ] Errors include exception context in traces
- [ ] No PII or credentials in traces

**Enforcement**: Telemetry capture tests, event validation tests
**Test Coverage**: `tests/integration/test_catalog_observability.py`
**Traceability**: ADR-0006, ADR-0035

---

### REQ-039: CatalogPlugin Error Handling **[New]**

**Requirement**: CatalogPlugin MUST handle catalog operation failures gracefully with actionable error messages.

**Rationale**: Enables operators to diagnose and recover from catalog issues.

**Acceptance Criteria**:
- [ ] Catches catalog-specific exceptions (e.g., NamespaceAlreadyExists)
- [ ] Translates to PluginExecutionError with context
- [ ] Error messages suggest resolution (e.g., "Namespace already exists, choose different name")
- [ ] No stack traces exposed to end users
- [ ] Includes debug context in logs

**Enforcement**: Error handling tests, error message validation
**Test Coverage**: `tests/unit/test_catalog_error_handling.py`
**Traceability**: ADR-0025 (Exception Handling)

---

### REQ-040: CatalogPlugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseCatalogPluginTests class that all CatalogPlugin implementations inherit to validate compliance.

**Rationale**: Ensures all catalogs meet minimum functionality requirements.

**Acceptance Criteria**:
- [ ] BaseCatalogPluginTests in testing/base_classes/
- [ ] Tests all ABC methods
- [ ] Tests catalog CRUD operations
- [ ] Tests namespace operations
- [ ] Tests credential vending
- [ ] Tests error handling and validation

**Enforcement**: Plugin compliance tests must pass for all catalogs
**Test Coverage**: `testing/base_classes/base_catalog_plugin_tests.py`
**Traceability**: TESTING.md

---

### REQ-041: CatalogPlugin Test Fixtures **[New]**

**Requirement**: System MUST provide test fixtures for CatalogPlugin implementations that extend the Epic 9C testing framework.

**Rationale**: Integration tests for catalog adapters (AWS Glue, Hive) require catalog connectivity fixtures to validate catalog operations, namespace management, and credential vending.

**Acceptance Criteria**:
- [ ] Fixture module: `testing/fixtures/catalog.py` (extends 9C patterns)
- [ ] `CatalogTestConfig(BaseModel)` with `frozen=True`
- [ ] Context manager: `catalog_connection_context()` for lifecycle
- [ ] Adapter-specific fixtures: `glue_fixture()`, `hive_fixture()` for testing
- [ ] Mock fixtures for unit tests (no real catalog required)
- [ ] Extends: `IntegrationTestBase` from Epic 9C
- [ ] Type hints: mypy --strict passes
- [ ] Test coverage: >80% of fixture code

**Constraints**:
- MUST extend Epic 9C testing framework (`testing.base_classes`)
- MUST follow fixture pattern from `testing/fixtures/__init__.py`
- MUST use Pydantic v2 `ConfigDict(frozen=True)` for config
- MUST NOT duplicate Polaris fixture from Epic 9C (reference implementation)
- MUST support credential injection via environment variables

**Test Coverage**: `testing/tests/unit/test_catalog_fixtures.py`

**Traceability**:
- Epic 9C (Testing Framework dependency)
- Epic 4C (CatalogPlugin)
- ADR-0065 (K8s-native testing)

---

## Domain Acceptance Criteria

CatalogPlugin Standards (REQ-031 to REQ-041) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] CatalogPlugin ABC defined in floe-core
- [ ] At least 2 reference implementations (Polaris, AWS Glue)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate catalog operations
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract catalog operations to plugins
