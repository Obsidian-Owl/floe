# Feature Specification: Compute Plugin ABC with Multi-Compute Pipeline Support

**Feature Branch**: `001-compute-plugin`
**Created**: 2026-01-09
**Status**: Draft
**Input**: Epic 04A - Compute Plugin breakdown

## Clarifications

### Session 2026-01-09

- Q: Should ComputePlugin execute SQL directly or delegate to dbt? → A: **Hybrid approach** - ComputePlugin generates dbt profiles.yml (dbt handles ALL SQL execution via its adapters) AND provides lightweight `validate_connection()` using native database drivers for fast health checks. No execute/connect/disconnect methods - dbt adapters handle SQL execution.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin Developer Creates New Compute Adapter (Priority: P0)

As a plugin developer, I want a clear abstract interface (ABC) for compute plugins so that I can implement adapters for new query execution engines (Spark, Snowflake, BigQuery, etc.) without ambiguity about the required methods and contracts.

**Why this priority**: This is the foundational capability - without the ABC definition, no compute plugins can be built. All other functionality depends on this interface being well-defined.

**Independent Test**: Can be fully tested by creating a mock implementation of the ABC and verifying all required methods are properly defined. Delivers value by enabling third-party plugin development.

**Acceptance Scenarios**:

1. **Given** a plugin developer wants to create a new compute adapter, **When** they inherit from ComputePlugin ABC, **Then** they receive clear guidance on all required methods (generate_dbt_profile, get_required_dbt_packages, validate_connection, get_resource_requirements, get_catalog_attachment_sql) with typed signatures.

2. **Given** a plugin developer creates an incomplete implementation, **When** they attempt to instantiate the plugin, **Then** they receive a clear error identifying which abstract methods are not implemented.

3. **Given** a plugin developer implements all required methods, **When** they register the plugin via entry points, **Then** the plugin registry discovers and loads the plugin successfully.

---

### User Story 2 - Data Engineer Uses DuckDB for Local Development (Priority: P0)

As a data engineer, I want DuckDB as the default compute engine so that I can develop and test data pipelines locally without requiring cloud services or external database connections.

**Why this priority**: DuckDB provides zero-configuration local development, which is critical for developer productivity and reducing infrastructure costs during development.

**Independent Test**: Can be fully tested by running dbt models against DuckDB locally and verifying query execution succeeds. Delivers value by enabling offline development.

**Acceptance Scenarios**:

1. **Given** a data engineer has a dbt project, **When** they run transforms without specifying a compute target, **Then** DuckDB is used as the default engine.

2. **Given** a data engineer wants to query Iceberg tables, **When** they execute SQL via DuckDB, **Then** the DuckDB Iceberg extension is used to read/write Iceberg table format.

3. **Given** a data engineer needs memory-constrained execution, **When** they configure memory limits, **Then** DuckDB respects those limits and fails gracefully if exceeded.

4. **Given** a data engineer completes development, **When** they generate dbt profiles, **Then** the plugin produces a valid profiles.yml for dbt-duckdb adapter.

---

### User Story 3 - Platform Engineer Configures Multi-Compute Pipeline (Priority: P0)

As a platform engineer, I want to define N approved compute targets with a default so that data engineers can choose from a governed set of compute engines based on their transform requirements.

**Why this priority**: Multi-compute support is a key differentiator, allowing organizations to use the right tool for each job while maintaining governance.

**Independent Test**: Can be fully tested by configuring multiple compute targets in manifest.yaml and verifying all are loaded and validated. Delivers value by enabling flexible compute selection.

**Acceptance Scenarios**:

1. **Given** a platform engineer configures manifest.yaml with `compute.approved: [duckdb, spark, snowflake]`, **When** the manifest is loaded, **Then** all three compute plugins are discovered, loaded, and validated.

2. **Given** a platform engineer specifies `compute.default: duckdb`, **When** a data engineer omits compute selection, **Then** DuckDB is used for that transform.

3. **Given** a compute target is not in the approved list, **When** a data engineer tries to use it, **Then** a clear validation error is raised at compile time (not runtime).

---

### User Story 4 - Data Engineer Selects Compute Per Transform (Priority: P0)

As a data engineer, I want to select different compute engines for different pipeline steps so that I can use the right tool for each job (Spark for heavy ETL, DuckDB for lightweight analytics).

**Why this priority**: Per-transform compute selection enables cost optimization and performance tuning within a single pipeline.

**Independent Test**: Can be fully tested by defining multiple transforms with different compute selections and verifying each executes on the correct engine.

**Acceptance Scenarios**:

1. **Given** a data engineer specifies `compute: spark` on a transform, **When** the pipeline compiles, **Then** that transform is configured to execute on Spark.

2. **Given** a transform has no compute specified, **When** the pipeline compiles, **Then** the platform default compute is used.

3. **Given** the same pipeline runs in dev and prod, **When** comparing compute assignments, **Then** each transform uses the SAME compute engine across all environments (environment parity enforced).

---

### User Story 5 - Enterprise Architect Enforces Hierarchical Compute Governance (Priority: P1)

As an enterprise architect, I want domain teams to restrict available computes to a subset of the enterprise-approved list so that different business units can enforce different standards based on their compliance or cost requirements.

**Why this priority**: Hierarchical governance enables Data Mesh patterns where domains have autonomy within enterprise guardrails.

**Independent Test**: Can be fully tested by defining enterprise and domain manifests with different compute subsets and verifying the restriction is enforced.

**Acceptance Scenarios**:

1. **Given** an enterprise manifest approves `[duckdb, spark, snowflake, bigquery]`, **When** a domain manifest specifies `compute.approved: [duckdb, spark]`, **Then** only DuckDB and Spark are available to that domain's data products.

2. **Given** a domain tries to approve a compute not in the enterprise list, **When** the manifest is validated, **Then** a clear error is raised explaining the governance violation.

3. **Given** a data product tries to use a compute not in its domain's approved list, **When** the floe.yaml is compiled, **Then** a clear error is raised with the allowed options.

---

### User Story 6 - Platform Operator Monitors Connection Health (Priority: P1)

As a platform operator, I want connection health monitored so that I can detect issues proactively before they impact data pipelines.

**Why this priority**: Production reliability requires proactive monitoring and automatic recovery from transient failures.

**Independent Test**: Can be fully tested by simulating connection failures and verifying health check detection and reconnection behavior.

**Acceptance Scenarios**:

1. **Given** a compute plugin has an active connection, **When** the health check is invoked, **Then** it returns connection status, latency, and any warnings.

2. **Given** a connection becomes unhealthy, **When** the next operation is attempted, **Then** the plugin automatically attempts reconnection before failing.

3. **Given** health check metrics are emitted, **When** monitoring is configured, **Then** connection status, pool size, and error rates are observable.

---

### User Story 7 - Platform Operator Enforces Query Timeouts (Priority: P1)

As a platform operator, I want query timeouts enforced so that runaway queries don't consume resources indefinitely and impact other workloads.

**Why this priority**: Resource protection is critical for multi-tenant environments and cost control.

**Independent Test**: Can be fully tested by executing a long-running query with a short timeout and verifying graceful cancellation.

**Acceptance Scenarios**:

1. **Given** a default timeout is configured in manifest.yaml, **When** a query exceeds that duration, **Then** it is cancelled gracefully with a timeout error.

2. **Given** a specific query needs a longer timeout, **When** override is specified, **Then** the query-specific timeout is used.

3. **Given** a query is cancelled due to timeout, **When** the event is logged, **Then** it includes query ID, duration, and configured timeout for debugging.

---

### Edge Cases

- What happens when a compute plugin fails to load? Clear error message identifying the plugin and failure reason.
- What happens when all approved computes fail validation? Compilation fails with aggregate error listing all failures.
- How does the system handle credential refresh during long-running connections? Plugins must support credential refresh without connection restart where possible.
- What happens when environment parity is violated (different compute in dev vs prod)? Compilation fails with clear error - this is a hard constraint.
- How does the system handle concurrent queries to the same compute? Connection pooling per-plugin with configurable pool size.
- What happens when DuckDB memory limit is exceeded? Graceful failure with clear error, not OOM crash.

## Requirements *(mandatory)*

### Functional Requirements

**ComputePlugin ABC**
- **FR-001**: System MUST define a ComputePlugin abstract base class with:
  - `generate_dbt_profile(config: ComputeConfig) -> dict` - Generate dbt profiles.yml configuration for this compute target
  - `get_required_dbt_packages() -> list[str]` - Return required dbt packages (e.g., dbt-duckdb, dbt-snowflake)
  - `validate_connection(config: ComputeConfig) -> ConnectionResult` - Test connection using native database driver (lightweight health check)
  - `get_resource_requirements(workload_size: str) -> ResourceSpec` - Return K8s resource requirements for dbt job pods
  - `get_catalog_attachment_sql(catalog_config: CatalogConfig) -> list[str] | None` - Return SQL to attach compute engine to Iceberg catalog (DuckDB only)
- **FR-002**: System MUST enforce type safety with typed method signatures using Python type hints and Pydantic models for configuration.
- **FR-003**: System MUST support plugin registration via Python entry points (`floe.computes` group).
- **FR-004**: System MUST provide a PluginMetadata model including name, version, and floe_api_version.
- **FR-004a**: ComputePlugin MUST NOT execute SQL directly - dbt adapters handle all SQL execution via profiles.yml configuration.

**DuckDB Reference Implementation**
- **FR-005**: System MUST provide a DuckDBComputePlugin that implements the ComputePlugin ABC.
- **FR-006**: System MUST support both in-memory and file-based DuckDB modes.
- **FR-007**: System MUST support Iceberg table read/write via DuckDB's Iceberg extension.
- **FR-008**: System MUST generate valid dbt-duckdb profiles via generate_dbt_profile() method.
- **FR-009**: System MUST support configurable memory limits for DuckDB execution.

**Multi-Compute Pipeline Support**
- **FR-010**: System MUST support `compute.approved[]` configuration in manifest.yaml for defining N approved compute targets.
- **FR-011**: System MUST support `compute.default` configuration to specify fallback when not explicitly set.
- **FR-012**: System MUST support `transforms[].compute` field in floe.yaml for per-transform compute selection.
- **FR-013**: System MUST validate compute selections at compile time (not runtime).
- **FR-014**: System MUST enforce environment parity - each transform uses the SAME compute across dev/staging/prod.

**Hierarchical Governance**
- **FR-015**: System MUST support hierarchical compute restriction (Enterprise -> Domain -> Product).
- **FR-016**: System MUST validate that domain compute.approved is a subset of enterprise compute.approved.
- **FR-017**: System MUST provide clear error messages when governance constraints are violated.

**Connection Validation & Health Monitoring**
- **FR-018**: System MUST provide validate_connection() method using native database drivers for lightweight health checks (not via dbt debug).
- **FR-019**: validate_connection() MUST return ConnectionResult with status, latency_ms, and optional warnings.
- **FR-020**: System MUST support configurable query timeouts via generate_dbt_profile() output (dbt adapter handles enforcement).
- **FR-021**: System MUST support connection pooling configuration via generate_dbt_profile() output (dbt adapter handles pooling).

**Error Handling**
- **FR-022**: System MUST provide structured error types for compute failures (ConnectionError, TimeoutError, QueryError).
- **FR-023**: System MUST log all compute errors with correlation IDs for debugging.
- **FR-024**: System MUST emit compute metrics via OpenTelemetry (query duration, error rate, pool utilization).

### Key Entities

- **ComputePlugin**: Abstract interface for compute target configuration. Generates dbt profiles.yml (dbt handles SQL execution), validates connections via native drivers, and provides K8s resource requirements. Does NOT execute SQL directly.

- **ComputeConfig**: Single compute target configuration including plugin name, connection settings, resource limits, and timeout configuration. Passed to generate_dbt_profile() and validate_connection().

- **ConnectionResult**: Return type from validate_connection() containing status (healthy/unhealthy/degraded), latency_ms, and optional warnings list.

- **ResourceSpec**: K8s resource requirements (CPU/memory requests and limits) returned by get_resource_requirements() for dbt job pod sizing.

- **ComputeRegistry**: Configuration holder containing the list of approved compute targets and the default selection. Supports hierarchical inheritance (Enterprise -> Domain -> Product).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Plugin developers can create a new compute adapter and have it discovered by the registry within 1 hour of first attempt, following documentation alone.

- **SC-002**: Data engineers can execute a complete dbt project against DuckDB locally with zero external service dependencies.

- **SC-003**: Platform engineers can configure 3+ compute targets and have all validated and loaded within 5 seconds of manifest parsing.

- **SC-004**: Per-transform compute selection is validated at compile time, with validation errors appearing within 2 seconds of running `floe compile`.

- **SC-005**: Environment parity violations are detected at compile time with 100% accuracy - no drift between environments is permitted.

- **SC-006**: Query timeout enforcement cancels queries within 1 second of timeout expiration.

- **SC-007**: Connection health degradation is detected within 30 seconds via health check polling.

- **SC-008**: All compute plugins pass the compliance test suite with 100% of ABC methods implemented correctly.

- **SC-009**: Hierarchical governance violations produce clear error messages that identify the specific constraint violated and list allowed options.

## Assumptions

- The plugin registry from Epic 1 is available and provides the discovery mechanism for compute plugins.
- **dbt adapters handle ALL SQL execution** - ComputePlugin generates profiles.yml configuration; dbt-duckdb, dbt-snowflake, dbt-spark etc. handle actual query execution via their native drivers.
- dbt handles all SQL dialect translation - compute plugins do not parse or transform SQL.
- Credentials are managed externally (environment variables or Kubernetes secrets) and accessed via SecretReference.
- All compute plugins are stateless for query caching - caching is handled by the compute engine itself.
- DuckDB version 0.9.0 or higher is required for Iceberg extension support.
- Native database drivers (duckdb, snowflake-connector-python, PyHive, etc.) are available for validate_connection() health checks.

## Dependencies

| Type       | Item                         | Reason                                         |
|------------|------------------------------|------------------------------------------------|
| Blocked By | Epic 1 (Plugin Registry)     | Uses PluginRegistry for compute plugin discovery |
| Blocks     | Epic 5A (dbt Integration)    | dbt uses compute for execution                 |
| Blocks     | Epic 9A (K8s Deployment)     | K8s deployment needs compute configuration     |
| External   | duckdb>=0.9.0                | Required for DuckDB reference implementation   |
| External   | duckdb-iceberg (extension)   | Required for Iceberg table support             |
