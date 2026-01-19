# Feature Specification: Dagster Orchestrator Plugin

**Epic**: 4B (Orchestrator Plugin)
**Feature Branch**: `4b-orchestrator-plugin`
**Created**: 2026-01-19
**Status**: Draft
**Input**: User description: "Implement Dagster orchestrator plugin with OrchestratorPlugin ABC implementing asset creation from CompiledArtifacts, OpenLineage event emission, Helm values generation, and job scheduling"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Team Configures Dagster Orchestration (Priority: P1)

A platform engineer wants to enable Dagster as the orchestration platform for their organization's data pipelines. They select Dagster in the manifest.yaml configuration, and the floe platform automatically discovers and loads the Dagster orchestrator plugin, making it available for data product compilation.

**Why this priority**: Orchestration platform selection is the foundational capability that enables all other orchestration features. Without this, no pipelines can be scheduled or executed.

**Independent Test**: Can be fully tested by configuring Dagster in manifest.yaml and verifying the plugin is discovered and registered in the plugin registry.

**Acceptance Scenarios**:

1. **Given** a manifest.yaml with `orchestrator: dagster`, **When** floe loads the configuration, **Then** the DagsterOrchestratorPlugin is discovered via entry points and registered in the plugin registry.
2. **Given** the Dagster plugin is registered, **When** a developer queries available orchestrators, **Then** "dagster" appears in the list with version and API compatibility information.
3. **Given** an invalid orchestrator name in manifest.yaml, **When** floe loads the configuration, **Then** a clear error message lists available orchestrator options.

---

### User Story 2 - Data Engineer Generates Pipeline Definitions (Priority: P1)

A data engineer has a compiled data product (CompiledArtifacts) containing dbt models. They need to generate Dagster definitions (assets, jobs, resources) that represent the data pipeline for deployment to the Dagster webserver.

**Why this priority**: Definition generation from compiled artifacts is the core function of the orchestrator plugin - it bridges floe's declarative configuration with Dagster's execution model.

**Independent Test**: Can be tested by passing CompiledArtifacts to the plugin and verifying it returns valid Dagster Definitions with appropriate assets and dependencies.

**Acceptance Scenarios**:

1. **Given** CompiledArtifacts with 5 dbt models, **When** `create_definitions()` is called, **Then** a Dagster Definitions object is returned containing 5 software-defined assets.
2. **Given** CompiledArtifacts with model dependencies (model_a -> model_b -> model_c), **When** `create_definitions()` is called, **Then** the generated assets reflect the correct dependency graph.
3. **Given** CompiledArtifacts with invalid schema, **When** `create_definitions()` is called, **Then** a ValidationError is raised with actionable error message.

---

### User Story 3 - Data Engineer Creates Assets from dbt Transforms (Priority: P1)

A data engineer needs to convert individual dbt model configurations into Dagster software-defined assets. Each asset should respect the transform's compute target selection, allowing per-model compute override (e.g., run heavy aggregations on Spark while keeping simple transforms on DuckDB).

**Why this priority**: Per-transform asset creation with compute selection enables the core value proposition of multi-compute orchestration, allowing cost optimization and workload-appropriate compute assignment.

**Independent Test**: Can be tested by providing TransformConfig objects with varying compute targets and verifying the generated assets include correct resource selection.

**Acceptance Scenarios**:

1. **Given** a TransformConfig with name "stg_customers" and depends_on ["raw_customers"], **When** `create_assets_from_transforms()` is called, **Then** a Dagster asset is returned with the correct upstream dependency.
2. **Given** a TransformConfig with compute="spark", **When** `create_assets_from_transforms()` is called, **Then** the asset metadata includes the compute target for resource selection.
3. **Given** a TransformConfig with tags ["daily", "core"], **When** `create_assets_from_transforms()` is called, **Then** the Dagster asset includes matching tags.

---

### User Story 4 - Platform Team Deploys Dagster Services (Priority: P2)

A platform team needs to deploy Dagster services (webserver, daemon, workers) to Kubernetes. The orchestrator plugin provides Helm values that configure resource requests/limits and service settings appropriate for the selected workload size.

**Why this priority**: Kubernetes deployment is essential for production use but can initially be validated with default values while core functionality is established.

**Independent Test**: Can be tested by calling `get_helm_values()` and validating the returned dictionary against the floe-dagster Helm chart schema.

**Acceptance Scenarios**:

1. **Given** the Dagster plugin is loaded, **When** `get_helm_values()` is called, **Then** a dictionary is returned with keys for dagster-webserver, dagster-daemon, and dagster-user-code.
2. **Given** a medium workload configuration, **When** `get_resource_requirements("medium")` is called, **Then** ResourceSpec is returned with appropriate CPU and memory settings (e.g., 500m/2000m CPU, 1Gi/4Gi memory).
3. **Given** an invalid workload size "extra-large", **When** `get_resource_requirements("extra-large")` is called, **Then** a ValueError is raised listing valid options.

---

### User Story 5 - Data Engineer Schedules Pipeline Execution (Priority: P2)

A data engineer needs to schedule a data pipeline to run daily at 8 AM Eastern time. They configure the schedule in floe.yaml, and the orchestrator plugin creates the corresponding Dagster schedule.

**Why this priority**: Job scheduling is critical for production workflows but depends on pipeline definitions being stable first.

**Independent Test**: Can be tested by calling `schedule_job()` with cron expression and timezone, then verifying schedule creation.

**Acceptance Scenarios**:

1. **Given** a valid cron expression "0 8 * * *" and timezone "America/New_York", **When** `schedule_job()` is called, **Then** a Dagster schedule is created with the correct timing.
2. **Given** an invalid cron expression "invalid", **When** `schedule_job()` is called, **Then** a ValueError is raised with message explaining valid cron format.
3. **Given** an invalid timezone "Fake/Zone", **When** `schedule_job()` is called, **Then** a ValueError is raised listing valid timezone options.

---

### User Story 6 - Platform Team Tracks Data Lineage (Priority: P2)

A platform team needs visibility into data lineage across all orchestrated pipelines. When jobs start, complete, or fail, the orchestrator emits OpenLineage events that are captured by the configured lineage backend (Marquez, Atlan, etc.).

**Why this priority**: Data lineage provides governance and debugging capabilities but is not blocking for basic pipeline execution.

**Independent Test**: Can be tested by calling `emit_lineage_event()` with datasets and verifying the event structure matches OpenLineage spec.

**Acceptance Scenarios**:

1. **Given** a job "dbt_run_customers" with input Dataset "raw.customers" and output Dataset "staging.stg_customers", **When** `emit_lineage_event("COMPLETE", ...)` is called, **Then** an OpenLineage event is emitted with correct job and dataset references.
2. **Given** a job failure, **When** `emit_lineage_event("FAIL", ...)` is called, **Then** the event includes error facets for debugging.
3. **Given** no lineage backend configured, **When** `emit_lineage_event()` is called, **Then** the call succeeds silently (no-op) without raising an exception.

---

### User Story 7 - Operations Team Validates Dagster Connectivity (Priority: P3)

An operations team member needs to verify that the floe platform can connect to the Dagster services before deploying pipelines. The plugin provides a health check that tests connectivity with timeout protection.

**Why this priority**: Connection validation is useful for troubleshooting but is not blocking for development workflows.

**Independent Test**: Can be tested by calling `validate_connection()` with/without Dagster services running and verifying appropriate responses.

**Acceptance Scenarios**:

1. **Given** Dagster services are running and accessible, **When** `validate_connection()` is called, **Then** ValidationResult with success=True is returned within 10 seconds.
2. **Given** Dagster services are unreachable, **When** `validate_connection()` is called, **Then** ValidationResult with success=False is returned with actionable error message.
3. **Given** Dagster services are slow to respond, **When** `validate_connection()` is called, **Then** the call times out after 10 seconds with timeout error message.

---

### Edge Cases

- What happens when CompiledArtifacts contains zero transforms? (Return empty Definitions with no assets)
- What happens when a transform has circular dependencies? (Raise ValidationError during create_definitions)
- What happens when two transforms have the same name? (Raise ValidationError with duplicate name error)
- What happens when schedule timezone has daylight saving time transitions? (Dagster handles DST via IANA timezone library)
- What happens when lineage event emission fails? (Log warning, do not fail the job)

## Requirements *(mandatory)*

### Functional Requirements

#### Plugin Discovery & Registration

- **FR-001**: System MUST register the Dagster plugin via entry point `floe.orchestrators` with key `dagster`
- **FR-002**: System MUST implement all abstract methods from `OrchestratorPlugin` ABC
- **FR-003**: Plugin MUST declare `name`, `version`, and `floe_api_version` properties
- **FR-004**: Plugin MUST inherit from both `OrchestratorPlugin` and `PluginMetadata` base classes

#### Definition Generation

- **FR-005**: System MUST generate valid Dagster `Definitions` object from `CompiledArtifacts`
- **FR-006**: System MUST create Dagster software-defined assets from `TransformConfig` list
- **FR-007**: System MUST preserve dbt model dependency graph as Dagster asset dependencies
- **FR-008**: System MUST include transform metadata (tags, compute target, schema) in asset metadata
- **FR-009**: System MUST validate CompiledArtifacts schema before generating definitions

#### Resource Management

- **FR-010**: System MUST return valid Helm values for floe-dagster chart via `get_helm_values()`
- **FR-011**: System MUST provide resource presets for "small", "medium", and "large" workload sizes
- **FR-012**: System MUST return `ResourceSpec` with cpu_request, cpu_limit, memory_request, memory_limit

#### Scheduling

- **FR-013**: System MUST support cron-based job scheduling via `schedule_job()`
- **FR-014**: System MUST validate cron expressions before creating schedules
- **FR-015**: System MUST support IANA timezone names for schedule execution

#### Lineage

- **FR-016**: System MUST emit OpenLineage events for job START, COMPLETE, and FAIL states
- **FR-017**: System MUST include input and output Dataset references in lineage events
- **FR-018**: System MUST delegate lineage event delivery to configured `LineageBackendPlugin`

#### Connectivity

- **FR-019**: System MUST validate Dagster service connectivity via `validate_connection()`
- **FR-020**: System MUST complete connection validation within 10 seconds
- **FR-021**: System MUST return actionable error messages when connection fails

### Non-Functional Requirements

- **NFR-001**: Plugin MUST load within 500ms during plugin registry initialization
- **NFR-002**: Definition generation MUST complete within 5 seconds for up to 500 transforms
- **NFR-003**: All validation methods MUST be idempotent
- **NFR-004**: Plugin MUST emit OpenTelemetry spans for observability

### Key Entities

- **DagsterOrchestratorPlugin**: Main plugin class implementing `OrchestratorPlugin` ABC
- **TransformConfig**: Configuration for a single dbt transform (name, path, schema, dependencies, compute target)
- **ValidationResult**: Result of connection/configuration validation (success, message, errors, warnings)
- **Dataset**: OpenLineage dataset representation (namespace, name, facets)
- **ResourceSpec**: Kubernetes resource requirements (cpu_request, cpu_limit, memory_request, memory_limit)
- **CompiledArtifacts**: Contract from floe-core containing compiled dbt configuration

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Plugin passes all 7 abstract method compliance tests defined in `OrchestratorPlugin` ABC
- **SC-002**: Generated Dagster Definitions load successfully in Dagster webserver without errors
- **SC-003**: Asset dependency graph matches source dbt model dependencies with 100% accuracy
- **SC-004**: Connection validation completes within 10 seconds for both success and failure cases
- **SC-005**: Helm values generate valid YAML that passes `helm lint` for floe-dagster chart
- **SC-006**: OpenLineage events conform to OpenLineage v1.0 specification
- **SC-007**: Schedule jobs execute at correct times accounting for timezone and DST
- **SC-008**: Test coverage exceeds 80% for all plugin methods

## Clarifications

- Q: Which Dagster version range should the plugin target? A: Minimum Dagster 1.10+ with `@dbt_assets` decorator for stability; default Helm charts and tests target Dagster 1.12.
- Q: Which dbt execution strategy should the orchestrator plugin use? A: Use `dagster-dbt` native integration with `@dbt_assets` decorator (automatic manifest parsing, native dbt commands).

## Assumptions

1. **Dagster Version**: Plugin targets Dagster 1.10+ minimum (for `@dbt_assets` stability and dbt Fusion readiness); default Helm charts and integration tests target Dagster 1.12
2. **dbt Integration**: Plugin uses `dagster-dbt` native integration with `@dbt_assets` decorator for automatic manifest parsing and asset creation; dbt owns SQL execution per technology ownership principles
3. **Helm Chart**: floe-dagster Helm chart exists and follows Dagster community chart structure
4. **LineageBackend**: OpenLineage events are routed through configured `LineageBackendPlugin` (may be no-op if unconfigured)
5. **K8s Deployment**: Plugin generates Helm values but does not directly deploy to K8s (handled by Epic 9A/9B)
6. **CompiledArtifacts Schema**: Plugin depends on CompiledArtifacts v2.0.0 schema from Epic 2B

## Out of Scope

- Airflow orchestrator plugin implementation (separate future epic)
- Prefect orchestrator plugin implementation (separate future epic)
- Direct K8s deployment (handled by Epic 9A/9B)
- Dagster Cloud integration (community Helm chart only)
- Custom Dagster resource types (uses standard dbt resources)
- Sensor-based scheduling (cron schedules only for v1)
