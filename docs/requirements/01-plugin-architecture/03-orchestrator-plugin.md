# REQ-021 to REQ-030: OrchestratorPlugin Standards

**Domain**: Plugin Architecture
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

OrchestratorPlugin defines the interface for all orchestration engines (Dagster, Airflow 3.x, Prefect). This enables platform teams to select a single orchestration platform that all data engineers inherit, while maintaining vendor neutrality.

**Key ADR**: ADR-0011 (Pluggable Orchestration)

## Requirements

### REQ-021: OrchestratorPlugin ABC Definition **[New]**

**Requirement**: OrchestratorPlugin MUST define abstract methods: create_assets_from_artifacts(), get_helm_values(), validate_connection(), get_resource_requirements().

**Rationale**: Enforces consistent interface across all orchestration implementations.

**Acceptance Criteria**:
- [ ] ABC defined in `floe-core/src/floe_core/plugin_interfaces.py`
- [ ] All 4 abstract methods defined with type hints
- [ ] Docstrings explain purpose, parameters, return values
- [ ] mypy --strict passes on interface definition

**Enforcement**: ABC enforcement tests, mypy strict mode, plugin compliance test suite
**Test Coverage**: `tests/contract/test_orchestrator_plugin.py::test_abc_compliance`
**Traceability**: plugin-architecture.md, ADR-0011

---

### REQ-022: OrchestratorPlugin Asset Creation **[New]**

**Requirement**: OrchestratorPlugin.create_assets_from_artifacts() MUST generate platform-specific asset definitions from CompiledArtifacts that pass platform validation.

**Rationale**: Bridges floe-core compilation to orchestration platform assets/jobs.

**Acceptance Criteria**:
- [ ] Accepts CompiledArtifacts as input
- [ ] Returns platform-specific asset/job definitions (dict or list)
- [ ] All dbt models converted to platform assets
- [ ] All schedules and sensors converted to platform triggers
- [ ] Asset lineage preserved from artifacts

**Enforcement**: Asset generation tests, lineage validation tests
**Test Coverage**: `tests/integration/test_orchestrator_asset_creation.py`
**Traceability**: plugin-architecture.md:142-165

---

### REQ-023: OrchestratorPlugin Helm Values **[New]**

**Requirement**: OrchestratorPlugin.get_helm_values() MUST return valid Helm chart values for deploying orchestration services to Kubernetes.

**Rationale**: Enables declarative infrastructure-as-code deployment via Helm.

**Acceptance Criteria**:
- [ ] Returns dict matching Helm chart schema
- [ ] Includes resource requests/limits appropriate for workload
- [ ] Includes service configuration (webserver, workers)
- [ ] Supports replicas, autoscaling configuration
- [ ] Helm values validate against chart

**Enforcement**: Helm validation tests, Helm dry-run tests
**Test Coverage**: `tests/unit/test_orchestrator_helm_values.py`
**Traceability**: plugin-architecture.md:165-195

---

### REQ-024: OrchestratorPlugin Connection Validation **[Preserved]**

**Requirement**: OrchestratorPlugin.validate_connection() MUST test connectivity to orchestration service and return ValidationResult within 10 seconds or timeout.

**Rationale**: Pre-deployment validation ensures environment is ready.

**Acceptance Criteria**:
- [ ] Connects to orchestration service endpoint
- [ ] Returns ValidationResult(success, message, details)
- [ ] Actionable error messages (not stack traces)
- [ ] Timeout enforced at 10 seconds
- [ ] Validates credentials without exposing them

**Enforcement**: Connection validation tests, timeout tests
**Test Coverage**: `tests/integration/test_orchestrator_connection_validation.py`
**Traceability**: plugin-architecture.md

---

### REQ-025: OrchestratorPlugin Resource Requirements **[New]**

**Requirement**: OrchestratorPlugin.get_resource_requirements() MUST return K8s ResourceRequirements (CPU, memory) with sensible defaults for orchestration workloads.

**Rationale**: Ensures platform services have adequate resources for job scheduling and execution.

**Acceptance Criteria**:
- [ ] Returns K8s ResourceRequirements dict with requests and limits
- [ ] Default values appropriate for orchestrator (webserver, workers)
- [ ] User can override via manifest.yaml
- [ ] Accounts for expected job concurrency

**Enforcement**: Resource requirement tests, K8s deployment validation
**Test Coverage**: `tests/unit/test_orchestrator_resources.py`
**Traceability**: plugin-architecture.md

---

### REQ-026: OrchestratorPlugin Job Execution **[New]**

**Requirement**: OrchestratorPlugin MUST support job execution with configurable parallelism, timeouts, and retry policies.

**Rationale**: Enables organizations to tune execution characteristics per environment.

**Acceptance Criteria**:
- [ ] Accepts job execution configuration (timeout, retries, parallelism)
- [ ] Enforces timeout on job execution
- [ ] Implements retry logic with exponential backoff
- [ ] Returns execution result with status and logs
- [ ] No job executions silently fail or hang

**Enforcement**: Job execution tests, timeout enforcement tests, retry tests
**Test Coverage**: `tests/integration/test_orchestrator_job_execution.py`
**Traceability**: plugin-architecture.md

---

### REQ-027: OrchestratorPlugin Observability Integration **[New]**

**Requirement**: OrchestratorPlugin MUST emit OpenTelemetry traces for all orchestration events (job start, completion, failure) and OpenLineage events for data lineage.

**Rationale**: Enables observability of orchestration execution and data lineage tracking.

**Acceptance Criteria**:
- [ ] Emits OTLP traces for job lifecycle events
- [ ] Includes job name, status, duration in spans
- [ ] Emits OpenLineage events for data transformations
- [ ] Traces include error context on job failure
- [ ] No PII or secrets in telemetry events

**Enforcement**: Telemetry capture tests, event validation tests
**Test Coverage**: `tests/integration/test_orchestrator_observability.py`
**Traceability**: ADR-0006, ADR-0035

---

### REQ-028: OrchestratorPlugin Error Handling **[New]**

**Requirement**: OrchestratorPlugin MUST handle orchestration failures gracefully with actionable error messages.

**Rationale**: Enables operators to diagnose and recover from failures.

**Acceptance Criteria**:
- [ ] Catches orchestration-specific exceptions
- [ ] Translates to PluginExecutionError with context
- [ ] Error messages suggest resolution steps
- [ ] No stack traces exposed to end users
- [ ] Includes job logs in error context

**Enforcement**: Error handling tests, error message validation
**Test Coverage**: `tests/unit/test_orchestrator_error_handling.py`
**Traceability**: ADR-0025 (Exception Handling)

---

### REQ-029: OrchestratorPlugin Type Safety **[New]**

**Requirement**: OrchestratorPlugin implementations MUST pass mypy --strict with full type annotations.

**Acceptance Criteria**:
- [ ] All methods have type hints
- [ ] Return types match ABC signature
- [ ] mypy --strict passes on plugin implementation
- [ ] No use of Any except for truly dynamic values

**Enforcement**: mypy in CI/CD, type checking tests
**Test Coverage**: CI/CD mypy validation
**Traceability**: python-standards.md

---

### REQ-030: OrchestratorPlugin Compliance Test Suite **[New]**

**Requirement**: System MUST provide BaseOrchestratorPluginTests class that all OrchestratorPlugin implementations inherit to validate compliance.

**Rationale**: Ensures all orchestrators meet minimum functionality requirements.

**Acceptance Criteria**:
- [ ] BaseOrchestratorPluginTests in testing/base_classes/
- [ ] Tests all ABC methods
- [ ] Tests asset creation from artifacts
- [ ] Tests Helm values generation
- [ ] Tests connection validation
- [ ] Tests error handling

**Enforcement**: Plugin compliance tests must pass for all orchestrators
**Test Coverage**: `testing/base_classes/base_orchestrator_plugin_tests.py`
**Traceability**: TESTING.md

---

## Domain Acceptance Criteria

OrchestratorPlugin Standards (REQ-021 to REQ-030) complete when:

- [ ] All 10 requirements documented with complete fields
- [ ] OrchestratorPlugin ABC defined in floe-core
- [ ] At least 2 reference implementations (Dagster, Airflow 3.x)
- [ ] Contract tests pass for all implementations
- [ ] Integration tests validate job execution
- [ ] Documentation backreferences all requirements

## Epic Mapping

**Epic 3: Plugin Interface Extraction** - Extract orchestration logic to plugins
