# REQ-001 to REQ-010: Plugin Discovery and Lifecycle

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines the plugin registry, discovery mechanism, and lifecycle management that enables floe's extensibility.

**Key Principle**: Plugin architecture > configuration switches (ADR-0037)

## Requirements

### REQ-001: Plugin Registry Singleton Pattern **[New]**

**Requirement**: System MUST implement PluginRegistry as a singleton with thread-safe discovery and caching.

**Rationale**: Prevents duplicate plugin loading and ensures consistent plugin state across the application.

**Acceptance Criteria**:
- [ ] PluginRegistry implements singleton pattern
- [ ] Thread-safe for concurrent access
- [ ] Caches discovered plugins to avoid repeated filesystem scans
- [ ] Uses importlib.metadata.entry_points() for discovery

**Enforcement**:
- Unit tests verify singleton behavior
- Thread-safety tests validate concurrent access
- Performance tests validate caching behavior

**Constraints**:
- MUST use importlib.metadata.entry_points() for discovery
- MUST cache discovered plugins to avoid repeated filesystem scans
- MUST be thread-safe for concurrent access
- FORBIDDEN to use global mutable state without locks

**Test Coverage**: `tests/unit/test_plugin_registry.py::test_singleton_pattern`

**Traceability**:
- MIGRATION-ROADMAP.md lines 187-234
- plugin-architecture.md lines 62-99
- ADR-0008 (Repository Split)

---

### REQ-002: Plugin Discovery via Entry Points **[Updated]**

**Requirement**: System MUST discover plugins via setuptools entry_points mechanism in groups: floe.orchestrators, floe.computes, floe.catalogs, floe.dbt, floe.semantic_layers, floe.ingestion, floe.storage, floe.telemetry_backends, floe.lineage_backends, floe.identity, floe.secrets, floe.data_quality.

**Rationale**: Standard Python plugin discovery enables ecosystem extensibility.

> **Note:** PolicyEnforcer and DataContract are now **core modules** in floe-core, not plugins.

**Acceptance Criteria**:
- [ ] PluginRegistry discovers plugins from 12 entry point groups
- [ ] Entry point group names match specification
- [ ] Discovery works with editable installs (pip install -e)
- [ ] Discovery works with installed packages
- [ ] Invalid entry points are rejected with clear error messages
- [ ] Includes floe.dbt for dbt execution environment plugins (ADR-0043)
- [ ] Includes floe.data_quality for data quality framework plugins (ADR-0044)
- [ ] Includes floe.telemetry_backends for OTLP backend plugins (Jaeger, Datadog, Grafana)
- [ ] Includes floe.lineage_backends for OpenLineage backend plugins (Marquez, Atlan)

**Enforcement**:
- Plugin discovery tests with mock entry points
- Entry point validation tests
- Ecosystem integration tests

**Constraints**:
- MUST reject plugins with missing or invalid entry points
- MUST log discovery errors with actionable messages
- FORBIDDEN to use file-based discovery (unreliable)

**Test Coverage**: `tests/unit/test_plugin_registry.py::test_entry_point_discovery`

**Traceability**:
- plugin-architecture.md lines 40-59
- ADR-0037 (Composability Principle)

---

### REQ-003: Plugin Metadata Validation **[New]**

**Requirement**: System MUST validate PluginMetadata (name, version, floe_api_version, description, author) before loading.

**Rationale**: Ensures plugin compatibility with platform API version.

**Acceptance Criteria**:
- [ ] Metadata includes required fields: name, version, floe_api_version
- [ ] Metadata includes optional fields: description, author, url
- [ ] floe_api_version follows semver (MAJOR.MINOR.PATCH)
- [ ] API version compatibility check prevents loading incompatible plugins
- [ ] Clear error messages when metadata validation fails

**Enforcement**:
- Metadata validation tests
- API version compatibility tests
- Invalid metadata rejection tests

**Constraints**:
- MUST reject plugins with floe_api_version < FLOE_PLUGIN_API_MIN_VERSION
- MUST reject plugins with missing required metadata fields
- FORBIDDEN to load plugins without version information

**Test Coverage**: `tests/unit/test_plugin_registry.py::test_metadata_validation`

**Traceability**:
- plugin-architecture.md lines 271-303
- ADR-0008 (Repository Split)

---

### REQ-004: Plugin Failure Isolation **[New]**

**Requirement**: System MUST isolate plugin failures such that one plugin crash does not cascade to other plugins or core system.

**Rationale**: Resilience requirement for production deployments.

**Acceptance Criteria**:
- [ ] Plugin execution wrapped in try-except with PluginError hierarchy
- [ ] Plugin crash logged with full traceback
- [ ] Plugin crash does not terminate PluginRegistry
- [ ] Other plugins continue to function after one plugin fails
- [ ] Graceful degradation when plugin unavailable

**Enforcement**:
- Fault injection tests
- Plugin crash recovery tests
- Isolation verification tests

**Constraints**:
- MUST wrap plugin execution in try-except with PluginError hierarchy
- MUST log plugin errors with structured context (plugin_name, plugin_version)
- FORBIDDEN to suppress plugin errors silently

**Test Coverage**: `tests/unit/test_plugin_registry.py::test_failure_isolation`

**Traceability**:
- plugin-architecture.md lines 1-40
- ADR-0037 (Composability Principle)

---

### REQ-005: Inter-Plugin Communication via Core **[New]**

**Requirement**: Plugins MUST NOT directly communicate with each other. All inter-plugin data flow MUST go through floe-core interfaces.

**Rationale**: Prevents tight coupling and leaky abstractions.

**Acceptance Criteria**:
- [ ] No direct imports between plugin packages
- [ ] All plugin-to-plugin communication via floe-core contracts (e.g., CompiledArtifacts)
- [ ] Static analysis detects illegal plugin-to-plugin imports
- [ ] Architectural tests enforce import boundaries

**Enforcement**:
- Static analysis (import checks via AST inspection)
- Architectural tests (import graph validation)
- CI/CD import boundary verification

**Constraints**:
- FORBIDDEN for plugins to import from other plugin packages
- FORBIDDEN for plugins to directly call other plugin methods
- MUST use floe-core as communication layer

**Test Coverage**: `tests/contract/test_plugin_boundaries.py`

**Traceability**:
- plugin-architecture.md lines 1-40
- component-ownership.md
- ADR-0037 (Composability Principle)

---

### REQ-006: Plugin Security Validation **[New]**

**Requirement**: System MUST validate plugin signatures before loading (when signing is enabled).

**Rationale**: Prevents malicious plugin injection.

**Acceptance Criteria**:
- [ ] Plugin packages can be signed with cosign or equivalent
- [ ] PluginRegistry validates signatures when signing enabled
- [ ] Unsigned plugins rejected when signature validation enabled
- [ ] Clear error messages when signature validation fails
- [ ] Configuration option to disable signing (development mode)

**Enforcement**:
- Signature verification tests
- Unsigned plugin rejection tests
- Malicious plugin detection tests

**Constraints**:
- MUST use cosign or equivalent for signature verification
- MUST reject unsigned plugins when validation enabled
- FORBIDDEN to load plugins without valid signatures in production

**Test Coverage**: `tests/unit/test_plugin_registry.py::test_signature_validation`

**Traceability**:
- plugin-architecture.md
- oci-registry-requirements.md
- ADR-0008 (Repository Split)
- Domain 04 (Artifact Distribution) for OCI signing

---

### REQ-007: Plugin Lifecycle Management **[New]**

**Requirement**: System MUST support plugin lifecycle: discover → load → initialize → validate → execute → cleanup.

**Rationale**: Structured lifecycle enables resource management and error handling.

**Acceptance Criteria**:
- [ ] PluginRegistry implements lifecycle state machine
- [ ] Plugins can implement optional lifecycle hooks (initialize, cleanup)
- [ ] Cleanup called on plugin errors or system shutdown
- [ ] Lifecycle state tracked per plugin instance
- [ ] Lifecycle transitions logged for debugging

**Enforcement**:
- Lifecycle hook tests
- Cleanup verification tests
- State machine validation tests

**Constraints**:
- MUST call cleanup() on plugin errors or shutdown
- MUST handle cleanup exceptions gracefully
- FORBIDDEN to skip cleanup phase

**Test Coverage**: `tests/unit/test_plugin_registry.py::test_lifecycle_hooks`

**Traceability**:
- plugin-architecture.md lines 40-99
- ADR-0037 (Composability Principle)

---

### REQ-008: Plugin Logging Standards **[Preserved]**

**Requirement**: All plugins MUST use structlog for logging with plugin_name and plugin_version in context.

**Rationale**: Consistent logging enables debugging across plugin ecosystem.

**Acceptance Criteria**:
- [ ] All plugin log messages include plugin_name
- [ ] All plugin log messages include plugin_version
- [ ] Structured logging format (JSON) for production
- [ ] Human-readable format for development
- [ ] No secrets or PII in plugin logs

**Enforcement**:
- Logging tests validate plugin context
- Log format validation
- Security tests detect secrets in logs

**Constraints**:
- MUST NOT log secrets or PII
- MUST use structlog.get_logger(__name__)
- MUST bind plugin_name and plugin_version to logger context

**Test Coverage**: `tests/unit/test_plugin_logging.py`

**Traceability**:
- security.md
- python-standards.md
- ADR-0006 (OpenTelemetry Observability)

---

### REQ-009: Exception Hierarchy for Plugins **[Evolution]**

**Requirement**: System MUST define plugin exception hierarchy: PluginError (base) → PluginDiscoveryError, PluginLoadError, PluginExecutionError.

**Rationale**: Structured error handling enables targeted recovery strategies.

**Acceptance Criteria**:
- [ ] PluginError base exception defined
- [ ] PluginDiscoveryError for entry point discovery failures
- [ ] PluginLoadError for plugin import/initialization failures
- [ ] PluginExecutionError for plugin method execution failures
- [ ] Exception messages include plugin context

**Enforcement**:
- Exception handling tests
- Error message validation
- Exception hierarchy compliance tests

**Constraints**:
- MUST include plugin_name in exception context
- MUST include actionable error messages
- FORBIDDEN to raise generic Exception from plugin code

**Test Coverage**: `tests/unit/test_plugin_exceptions.py`

**Traceability**:
- ADR-0025 (Exception Handling)
- python-standards.md

**Evolution from MVP**:
- **MVP**: Simple FloeError → ValidationError, CompilationError hierarchy
- **Target**: Expanded with plugin-specific errors
- **Migration**: Add plugin error classes, update exception handlers
- **Breaking Change**: NO (additive change)

---

### REQ-010: Plugin API Versioning **[New]**

**Requirement**: System MUST define FLOE_PLUGIN_API_VERSION with semver semantics and reject plugins with incompatible API versions.

**Rationale**: Enables plugin ecosystem to evolve without breaking existing plugins.

**Acceptance Criteria**:
- [ ] FLOE_PLUGIN_API_VERSION defined in floe-core
- [ ] FLOE_PLUGIN_API_MIN_VERSION defines backward compatibility window
- [ ] Plugin metadata declares required floe_api_version
- [ ] PluginRegistry rejects plugins with API version < MIN
- [ ] Clear migration guide when API version changes

**Enforcement**:
- API version compatibility tests
- Plugin rejection tests
- Versioning policy validation

**Constraints**:
- MUST follow semver (MAJOR.MINOR.PATCH)
- MAJOR version change = breaking API change
- MINOR version change = backward compatible additions
- PATCH version change = bug fixes, no API changes
- MUST support 3-version backward compatibility window

**Test Coverage**: `tests/unit/test_plugin_api_versioning.py`

**Traceability**:
- plugin-architecture.md
- ADR-0008 (Repository Split)
- pydantic-contracts.md (versioning section)

---

## Domain Acceptance Criteria

Plugin Discovery and Lifecycle (REQ-001 to REQ-010) is complete when:

- [ ] All 10 requirements have complete template fields
- [ ] PluginRegistry implemented with all requirements satisfied
- [ ] Unit tests pass with >80% coverage
- [ ] Contract tests validate plugin boundaries
- [ ] Documentation updated:
  - [ ] plugin-architecture.md backreferences requirements
  - [ ] ADR-0008 backreferences requirements
  - [ ] ADR-0037 backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 3: Plugin Interface Extraction**:
- Phase 1: Implement PluginRegistry infrastructure
- Phase 2: Extract MVP hardcoded logic to plugins
- Phase 3: Enable third-party plugin development
