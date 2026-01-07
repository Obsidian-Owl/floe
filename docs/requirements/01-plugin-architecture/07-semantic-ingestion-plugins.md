# REQ-061 to REQ-070: Semantic Layer and Ingestion Plugin Standards

**Domain**: Plugin Architecture
**Priority**: HIGH
**Status**: Complete specification

## Overview

SemanticLayerPlugin and IngestionPlugin enable consumption-layer configuration and data ingestion capabilities. Semantic layer (Cube, dbt Semantic Layer) makes data consumable via APIs; Ingestion plugins (dlt, Airbyte) handle external data loading.

**Key ADRs**: ADR-0032 (Semantic Layer), ADR-0033 (Data Ingestion)

## Requirements

### REQ-061: SemanticLayerPlugin ABC Definition **[New]**

**Requirement**: SemanticLayerPlugin MUST define abstract methods: generate_cube_config(), get_helm_values(), validate_connection().

**Rationale**: Enforces consistent interface for semantic layer implementations.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 3 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode
**Test Coverage**: `tests/contract/test_semantic_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0032

---

### REQ-062: SemanticLayerPlugin Cube Configuration **[New]**

**Requirement**: SemanticLayerPlugin.generate_cube_config() MUST generate Cube.js configuration for metrics and dimensions.

**Rationale**: Enables declarative semantic layer definitions that translate to API endpoints.

**Acceptance Criteria**:
- [ ] Generates cube.js schema from CompiledArtifacts
- [ ] Includes measures (metrics) and dimensions
- [ ] Includes pre-aggregations for performance
- [ ] Supports row-level security context
- [ ] Configuration validates with Cube SDK

**Enforcement**: Cube schema validation tests
**Test Coverage**: `tests/integration/test_semantic_cube_config.py`
**Traceability**: ADR-0032

---

### REQ-063: SemanticLayerPlugin Helm Values **[New]**

**Requirement**: SemanticLayerPlugin.get_helm_values() MUST return Helm chart values for deploying semantic layer services.

**Rationale**: Enables declarative infrastructure-as-code deployment.

**Acceptance Criteria**:
- [ ] Returns dict matching Helm chart schema
- [ ] Includes resource requests/limits
- [ ] Includes API endpoint configuration
- [ ] Supports scaling configuration
- [ ] Helm values validate against chart

**Enforcement**: Helm validation tests
**Test Coverage**: `tests/unit/test_semantic_helm_values.py`
**Traceability**: ADR-0032

---

### REQ-064: SemanticLayerPlugin Connection Validation **[Preserved]**

**Requirement**: SemanticLayerPlugin.validate_connection() MUST test connectivity to semantic layer service within 10 seconds.

**Rationale**: Pre-deployment validation ensures service is reachable.

**Acceptance Criteria**:
- [ ] Connects to semantic layer API endpoint
- [ ] Returns ValidationResult(success, message, details)
- [ ] Actionable error messages
- [ ] Timeout enforced at 10 seconds

**Enforcement**: Connection validation tests
**Test Coverage**: `tests/integration/test_semantic_connection_validation.py`
**Traceability**: ADR-0032

---

### REQ-065: IngestionPlugin ABC Definition **[New]**

**Requirement**: IngestionPlugin MUST define abstract methods: generate_connector_config(), get_helm_values(), validate_connection().

**Rationale**: Enforces consistent interface for data ingestion implementations.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 3 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode
**Test Coverage**: `tests/contract/test_ingestion_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0033

---

### REQ-066: IngestionPlugin Connector Configuration **[New]**

**Requirement**: IngestionPlugin.generate_connector_config() MUST generate platform-specific connector configuration for data sources.

**Rationale**: Enables declarative ingestion pipeline definitions.

**Acceptance Criteria**:
- [ ] Generates connector config from CompiledArtifacts
- [ ] Includes source system connection parameters
- [ ] Includes destination warehouse mapping
- [ ] Supports incremental and full load modes
- [ ] Credentials use ${env:VAR} references

**Enforcement**: Connector config validation tests
**Test Coverage**: `tests/integration/test_ingestion_connector_config.py`
**Traceability**: ADR-0033

---

### REQ-067: IngestionPlugin Helm Values **[New]**

**Requirement**: IngestionPlugin.get_helm_values() MUST return Helm chart values for deploying ingestion services.

**Rationale**: Enables declarative infrastructure deployment.

**Acceptance Criteria**:
- [ ] Returns dict matching Helm chart schema
- [ ] Includes resource requests/limits for ingestion workloads
- [ ] Includes scaling and concurrency configuration
- [ ] Helm values validate against chart

**Enforcement**: Helm validation tests
**Test Coverage**: `tests/unit/test_ingestion_helm_values.py`
**Traceability**: ADR-0033

---

### REQ-068: IngestionPlugin Connection Validation **[Preserved]**

**Requirement**: IngestionPlugin.validate_connection() MUST test connectivity to ingestion service within 10 seconds.

**Rationale**: Pre-deployment validation ensures service is reachable.

**Acceptance Criteria**:
- [ ] Connects to ingestion service API
- [ ] Returns ValidationResult(success, message, details)
- [ ] Actionable error messages
- [ ] Timeout enforced at 10 seconds

**Enforcement**: Connection validation tests
**Test Coverage**: `tests/integration/test_ingestion_connection_validation.py`
**Traceability**: ADR-0033

---

### REQ-069: Semantic and Ingestion Plugin Type Safety **[New]**

**Requirement**: Semantic and Ingestion plugin implementations MUST pass mypy --strict with full type annotations.

**Acceptance Criteria**:
- [ ] All methods have type hints
- [ ] Return types match ABC signatures
- [ ] mypy --strict passes on plugin implementations
- [ ] No use of Any except for truly dynamic values

**Enforcement**: mypy in CI/CD, type checking tests
**Test Coverage**: CI/CD mypy validation
**Traceability**: python-standards.md

---

### REQ-070: Semantic and Ingestion Plugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseSemanticLayerPluginTests and BaseIngestionPluginTests classes for compliance validation.

**Rationale**: Ensures all plugins meet minimum functionality requirements.

**Acceptance Criteria**:
- [ ] BaseSemanticLayerPluginTests in testing/base_classes/
- [ ] BaseIngestionPluginTests in testing/base_classes/
- [ ] Tests all ABC methods for each plugin type
- [ ] Tests configuration generation
- [ ] Tests Helm values generation
- [ ] Tests connection validation

**Enforcement**: Plugin compliance tests must pass for all implementations
**Test Coverage**: `testing/base_classes/base_semantic_plugin_tests.py`, `testing/base_classes/base_ingestion_plugin_tests.py`
**Traceability**: TESTING.md

---

## Domain Acceptance Criteria

Semantic Layer and Ingestion Standards (REQ-061 to REQ-070) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] SemanticLayerPlugin and IngestionPlugin ABCs defined
- [ ] At least 1 reference implementation per plugin type
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate configuration generation
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract semantic and ingestion configuration to plugins
