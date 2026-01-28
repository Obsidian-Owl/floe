# Feature Specification: Data Quality Plugin

**Epic**: 5B (Data Quality)
**Feature Branch**: `5b-dataquality-plugin`
**Created**: 2026-01-28
**Status**: Draft
**Input**: User description: "Implement Data Quality Plugin interface and reference implementations (Great Expectations, dbt-expectations) supporting compile-time validation and runtime data quality checks with quality scoring and OpenLineage emission"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Team Configures Data Quality Provider (Priority: P1)

As a Platform Team member, I want to select and configure a data quality provider (Great Expectations, Soda, or dbt-expectations) in the platform manifest so that all data products inherit consistent quality validation capabilities.

**Why this priority**: Without provider configuration, no quality validation can occur. This is the foundational capability that enables all other user stories.

**Independent Test**: Can be fully tested by configuring a manifest.yaml with quality plugin settings and validating the configuration is accepted without errors.

**Acceptance Scenarios**:

1. **Given** a manifest.yaml with `plugins.quality.provider: great_expectations`, **When** I run `floe validate manifest.yaml`, **Then** the manifest validation succeeds with no errors.
2. **Given** a manifest.yaml with quality_gates configured for bronze/silver/gold tiers, **When** I run `floe compile`, **Then** the CompiledArtifacts contains the resolved quality gate configuration.
3. **Given** a manifest.yaml with an invalid quality provider name, **When** I run `floe validate manifest.yaml`, **Then** the system returns error code FLOE-DQ001 with available providers listed.

---

### User Story 2 - Data Engineer Defines Quality Checks (Priority: P1)

As a Data Engineer, I want to define data quality checks in my floe.yaml or schema.yml so that my data product's output tables are validated against business rules.

**Why this priority**: Quality check definitions are core to the value proposition. Without defining checks, there's nothing to validate.

**Independent Test**: Can be fully tested by adding quality check definitions to floe.yaml and verifying they are parsed and included in compiled artifacts.

**Acceptance Scenarios**:

1. **Given** a floe.yaml with quality_checks defined for a model, **When** I run `floe compile`, **Then** the CompiledArtifacts includes the quality check definitions.
2. **Given** quality checks using dbt's generic tests (not_null, unique, accepted_values, relationships), **When** I run `floe compile`, **Then** the checks are recognized and mapped to the quality plugin format.
3. **Given** quality checks with custom expectations (e.g., expect_column_values_to_be_between), **When** I run `floe compile`, **Then** the custom expectations are preserved in the CompiledArtifacts.

---

### User Story 3 - Data Engineer Runs Quality Checks at Runtime (Priority: P1)

As a Data Engineer, I want quality checks to execute automatically after my dbt models run so that I know immediately if my data meets quality expectations.

**Why this priority**: Runtime execution is where quality validation delivers value. This is the primary use case for the plugin.

**Independent Test**: Can be fully tested by running a Dagster job that includes dbt models with quality checks and verifying the checks execute and return results.

**Acceptance Scenarios**:

1. **Given** a Dagster job with dbt models and quality checks defined, **When** the job runs successfully, **Then** quality checks execute automatically after model materialization.
2. **Given** quality checks that pass, **When** the checks complete, **Then** the run log shows check results with passed status.
3. **Given** quality checks that fail, **When** the checks complete, **Then** the run fails with detailed failure messages and FLOE-DQ102 error code.

---

### User Story 4 - Platform Team Enforces Quality Gates (Priority: P2)

As a Platform Team member, I want to enforce minimum quality coverage requirements per data tier so that critical data products meet governance standards before promotion.

**Why this priority**: Quality gates ensure governance is enforced. Important but builds on P1 stories.

**Independent Test**: Can be fully tested by configuring quality gates and attempting to compile/promote a data product that doesn't meet requirements.

**Acceptance Scenarios**:

1. **Given** a gold-tier data product with min_test_coverage of 100%, **When** the data product has only 80% coverage, **Then** compilation fails with FLOE-DQ103 and coverage gap details.
2. **Given** a silver-tier data product requiring not_null and unique tests, **When** a required test type is missing, **Then** compilation fails with FLOE-DQ104 listing missing test types.
3. **Given** a bronze-tier data product with min_test_coverage of 50%, **When** the data product has 60% coverage, **Then** compilation succeeds.

---

### User Story 5 - Data Engineer Views Quality Score (Priority: P2)

As a Data Engineer, I want to see a quality score (0-100) for my data product so that I can understand the overall health of my data at a glance.

**Why this priority**: Quality scoring provides actionable feedback. Enhances P1 stories with visibility.

**Independent Test**: Can be fully tested by running quality checks and viewing the calculated score in the run output.

**Acceptance Scenarios**:

1. **Given** quality checks that all pass, **When** the quality score is calculated, **Then** the score equals 100.
2. **Given** quality checks with some failures, **When** the quality score is calculated, **Then** the score reflects the weighted pass rate based on check criticality.
3. **Given** a quality score below the warn_score threshold (default 85), **When** the run completes, **Then** a warning is emitted in the logs.

---

### User Story 6 - Operations Team Monitors Quality via OpenLineage (Priority: P3)

As an Operations Team member, I want quality check failures to emit OpenLineage FAIL events so that I can monitor data quality issues in my lineage tool (Marquez, DataHub).

**Why this priority**: Observability integration is important for operations but builds on core functionality.

**Independent Test**: Can be fully tested by running a job with failing quality checks and verifying OpenLineage events are emitted.

**Acceptance Scenarios**:

1. **Given** a quality check that fails, **When** the failure is recorded, **Then** an OpenLineage FAIL event is emitted with facet containing check details.
2. **Given** multiple quality checks with mixed results, **When** the run completes, **Then** individual OpenLineage events are emitted for each failed check.
3. **Given** an OpenLineage backend is not configured, **When** quality checks run, **Then** checks still execute and log results locally without error.

---

### Edge Cases

- What happens when a quality check references a column that doesn't exist? System returns FLOE-DQ105 with column name and table at compile-time if schema is available, or at runtime with detailed error message.
- How does the system handle when the quality plugin is not installed? System returns FLOE-DQ001 with installation instructions (pip install floe-quality-gx).
- What happens when quality checks timeout? Configurable timeout (default 300s) with FLOE-DQ106 error after timeout, including which checks were pending.
- How does the system handle when the data source is empty? Quality checks run but report 0 records checked; checks like not_null pass on empty tables.
- What happens when dbt tests and plugin quality checks are both defined? Both execute; dbt tests via DBTPlugin.test_models(), plugin checks via QualityPlugin.run_checks(). Results are aggregated into a unified quality score.
- What happens when the same check is defined in both dbt and floe.yaml? Deduplicated by check signature; dbt definition takes precedence.
- What happens when a Product tries to override a locked Enterprise setting? Compilation fails with FLOE-DQ107 listing the locked setting and which level locked it.
- What happens when fail_fast is enabled on a QualitySuite? Execution stops on first check failure, remaining checks are skipped, and partial results are returned with clear indication of early termination.

## Requirements *(mandatory)*

### Functional Requirements

**Plugin Interface (FR-001 to FR-010)**

- **FR-001**: System MUST provide a QualityPlugin abstract base class in `floe_core.plugins.quality` that extends PluginMetadata.
- **FR-002**: QualityPlugin MUST define abstract method `validate_config(config: QualityConfig) -> ValidationResult` for compile-time configuration validation.
- **FR-003**: QualityPlugin MUST define abstract method `validate_quality_gates(models: list[ModelConfig], gates: QualityGates) -> GateResult` for enforcing coverage thresholds.
- **FR-004**: QualityPlugin MUST define abstract method `run_checks(suite: QualitySuite, connection: ConnectionConfig) -> QualitySuiteResult` for runtime execution.
- **FR-005**: QualityPlugin MUST define abstract method `calculate_quality_score(results: QualitySuiteResult, weights: ScoreWeights) -> QualityScore` for score computation.
- **FR-006**: QualityPlugin MUST define abstract method `get_lineage_emitter() -> OpenLineageEmitter | None` for observability integration.
- **FR-007**: QualityPlugin MUST define method `supports_dialect(dialect: str) -> bool` to indicate SQL dialect support.
- **FR-008**: QualityPlugin implementations MUST register via entry point `floe.quality`.
- **FR-009**: QualityPlugin MUST implement health_check() returning HealthStatus with connectivity and configuration state.
- **FR-010**: QualityPlugin MUST implement get_config_schema() returning the Pydantic config model for validation.

**Quality Configuration (FR-011 to FR-018)**

- **FR-011**: System MUST support quality provider configuration in manifest.yaml under `plugins.quality.provider`.
- **FR-012**: System MUST support quality_gates configuration with bronze/silver/gold tiers.
- **FR-013**: Quality gates MUST specify min_test_coverage as a percentage (0-100).
- **FR-014**: Quality gates MUST support required_tests list specifying mandatory test types (not_null, unique, etc.).
- **FR-015**: System MUST support a three-layer scoring model: (1) Dimension weights, (2) Check-level severity, (3) Calculation parameters.
- **FR-015a**: Layer 1 - System MUST support configurable dimension weights (completeness, accuracy, validity, consistency, timeliness) with weights summing to 1.0.
- **FR-015b**: Layer 2 - System MUST support check-level severity (critical, warning, info) or custom numeric weight (0.1-10.0), with each check mapped to a dimension.
- **FR-015c**: Layer 3 - System MUST support calculation parameters: baseline score (default 70), influence caps (max_positive, max_negative), and severity-to-weight mapping.
- **FR-016**: System MUST support thresholds configuration with min_score (blocks deployment) and warn_score (emits warning) at Enterprise, Domain, and Product levels.
- **FR-016a**: Each scoring configuration setting MUST support an `overridable: true/false` flag that controls whether lower levels can modify the setting.
- **FR-016b**: When a setting has `overridable: false`, lower levels (Domain or Product) MUST NOT be able to change that setting; compilation MUST fail with FLOE-DQ107 if override is attempted.
- **FR-016c**: Quality configuration inheritance MUST follow Enterprise → Domain → Product hierarchy, with each level inheriting non-overridden settings from parent.
- **FR-016d**: System MUST calculate quality score using formula: dimension_score = (passed/total)*100, weighted by dimension weight, with influence capping, constrained to 0-100.
- **FR-017**: Quality checks MUST be definable in floe.yaml under `models[].quality_checks[]`.
- **FR-018**: System MUST support referencing dbt test definitions as quality checks without duplication.

**Compile-Time Validation (FR-019 to FR-024)**

- **FR-019**: Compiler MUST invoke `QualityPlugin.validate_config()` during compilation.
- **FR-020**: Compiler MUST invoke `QualityPlugin.validate_quality_gates()` for each model with quality gates.
- **FR-021**: Compilation MUST fail with FLOE-DQ103 if quality coverage is below tier minimum.
- **FR-022**: Compilation MUST fail with FLOE-DQ104 if required test types are missing.
- **FR-023**: CompiledArtifacts MUST include quality_config section with resolved quality settings.
- **FR-024**: CompiledArtifacts MUST include quality_checks list for each model with check definitions.

**Runtime Execution (FR-025 to FR-032)**

- **FR-025**: OrchestratorPlugin MUST invoke quality checks after EACH dbt model materialization completes (not after all models), enabling early failure detection.
- **FR-026**: Runtime MUST pass connection configuration from ComputePlugin to QualityPlugin.
- **FR-027**: QualityPlugin.run_checks() MUST return QualitySuiteResult with individual check results.
- **FR-028**: Runtime MUST calculate a unified quality score that includes BOTH dbt test results (from DBTPlugin.test_models()) and plugin quality check results, providing a comprehensive data quality view.
- **FR-029**: Runtime MUST emit OpenLineage FAIL events for failed checks when lineage backend is configured.
- **FR-030**: Runtime MUST fail the job if quality score is below min_score threshold.
- **FR-031**: Runtime MUST emit warning if quality score is below warn_score threshold.
- **FR-032**: Runtime MUST support configurable timeout for quality check execution (default: 300 seconds).

**Reference Implementations (FR-033 to FR-040)**

- **FR-033**: System MUST provide floe-quality-gx plugin implementing QualityPlugin using Great Expectations.
- **FR-034**: floe-quality-gx MUST support ExpectationSuite creation from floe.yaml quality_checks.
- **FR-035**: floe-quality-gx MUST support all GX Core expectations (not_null, unique, values_between, etc.).
- **FR-036**: System MUST provide floe-quality-dbt plugin wrapping dbt-expectations macros.
- **FR-037**: floe-quality-dbt MUST execute quality checks as dbt tests via DBTPlugin.test_models().
- **FR-038**: floe-quality-dbt MUST support all dbt-expectations tests (expect_column_values_to_not_be_null, etc.).
- **FR-039**: Both implementations MUST pass plugin compliance tests (discovery, metadata, health_check).
- **FR-040**: Both implementations MUST support DuckDB, PostgreSQL, and Snowflake SQL dialects.

**Error Handling (FR-041 to FR-046)**

- **FR-041**: System MUST emit error code FLOE-DQ001 for missing or invalid quality provider.
- **FR-042**: System MUST emit error code FLOE-DQ102 for quality check failures at runtime.
- **FR-043**: System MUST emit error code FLOE-DQ103 for quality gate coverage violations.
- **FR-044**: System MUST emit error code FLOE-DQ104 for missing required test types.
- **FR-045**: System MUST emit error code FLOE-DQ105 for references to non-existent columns.
- **FR-046**: System MUST emit error code FLOE-DQ106 for quality check timeout.
- **FR-047**: System MUST emit error code FLOE-DQ107 when a lower level attempts to override a locked setting (overridable: false).

### Key Entities

- **QualityPlugin**: Abstract base class defining the plugin interface. Extends PluginMetadata with quality-specific methods for compile-time validation and runtime execution.
- **QualityConfig**: Pydantic model for quality provider configuration. Supports three-tier inheritance (Enterprise → Domain → Product). Each setting includes an `overridable` flag controlling whether lower levels can modify it. Includes provider name, quality gates, weights, and thresholds.
- **QualityGates**: Configuration for bronze/silver/gold tier quality requirements. Defines min_test_coverage and required_tests per tier. Each gate setting supports `overridable` flag for inheritance control.
- **QualitySuite**: Collection of quality checks to execute against a data source. Maps to a model and contains QualityCheck definitions.
- **QualityCheck**: Individual quality check definition. Contains check type (not_null, unique, custom), target column, parameters, severity (critical/warning/info or custom weight), and dimension mapping (completeness/accuracy/validity/consistency/timeliness).
- **QualitySuiteResult**: Result of running a quality suite. Contains individual check results, summary statistics, and execution metadata.
- **QualityCheckResult**: Result of a single check execution. Contains passed/failed status, records_checked, records_failed, and details.
- **QualityScore**: Computed unified quality score (0-100) incorporating both dbt test results and plugin quality check results. Includes overall score, per-dimension scores (completeness, accuracy, validity, consistency, timeliness), and source breakdown (dbt_tests, plugin_checks). Calculated using three-layer model with influence capping.
- **DimensionWeights**: Layer 1 of scoring model. Configures weights for quality dimensions (completeness, accuracy, validity, consistency, timeliness). Weights must sum to 1.0. Each dimension supports `overridable` flag.
- **SeverityWeights**: Layer 2 mapping. Maps severity levels to numeric weights (critical: 3.0, warning: 1.0, info: 0.5). Supports custom weights per check.
- **CalculationParameters**: Layer 3 of scoring model. Configures baseline score (default 70), influence_caps (max_positive: 30, max_negative: 50), and final score thresholds. Supports `overridable` flag per parameter.
- **ValidationResult**: Result of compile-time validation. Contains success status and list of validation errors/warnings.
- **GateResult**: Result of quality gate validation. Contains pass/fail status and coverage metrics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform teams can configure a quality provider and quality gates in under 5 configuration lines.
- **SC-002**: Data engineers can define quality checks for a model using the same syntax as dbt tests.
- **SC-003**: Quality checks execute within 2x the time of equivalent dbt test execution (baseline: single dbt generic test ~0.5-2s, so plugin check target <4s per check).
- **SC-004**: Quality score calculation completes in under 100ms for up to 1000 individual check results.
- **SC-005**: 100% of quality check failures result in OpenLineage FAIL events when lineage backend is configured.
- **SC-006**: Plugin discovery and loading completes in under 2 seconds.
- **SC-007**: Plugin health_check() returns within 5 seconds with meaningful connectivity status.
- **SC-008**: Both reference implementations pass 100% of plugin compliance tests.
- **SC-009**: Documentation includes working examples for all three tiers (bronze/silver/gold).
- **SC-010**: System handles 100+ quality checks per model without degradation.

### Integration Points

**Entry Point**: `floe.quality` entry point group for plugin discovery (floe-core plugin registry)

**Dependencies**:
- floe-core: PluginMetadata, PluginRegistry, CompiledArtifacts schema
- floe-core/plugins/quality.py: QualityPlugin ABC (existing minimal interface to be extended)
- floe-dbt: DBTPlugin for dbt-expectations execution
- ComputePlugin: Connection configuration for runtime checks
- OrchestratorPlugin: Post-model-run hooks for quality check execution
- LineageBackend (optional): OpenLineage event emission

**Produces**:
- Enhanced QualityPlugin ABC (extended from current minimal interface in floe-core)
- QualityConfig, QualityGates, QualityScore Pydantic schemas (added to floe-core)
- CompiledArtifacts.quality_config and quality_checks fields (schema extension)
- floe-quality-gx plugin package (plugins/floe-quality-gx/)
- floe-quality-dbt plugin package (plugins/floe-quality-dbt/)

**Consumed By**:
- Compiler: Invokes validate_config() and validate_quality_gates()
- OrchestratorPlugin (Dagster): Invokes run_checks() and calculate_quality_score()
- ContractMonitor (Epic 3D): May use quality results for SLA monitoring
- CLI: `floe quality run` command for manual quality check execution

## Clarifications

- Q: When should quality checks execute in a multi-model Dagster job? A: After EACH model completes (early failure detection, check per model)
- Q: Should dbt test results be included in the quality score calculation? A: Yes, unified score - dbt tests and plugin checks both contribute to quality score
- Q: At what level(s) can quality scoring be configured? A: Three-tier inheritance (Enterprise → Domain → Product) with explicit lock control - higher levels declare whether settings can be overridden via `overridable: true/false` flag; locked settings cannot be changed by lower levels
- Q: How are quality checks assigned to criticality categories for score weighting? A: Three-layer scoring model: (1) Dimension weights at Enterprise/Domain/Product level (completeness, accuracy, validity, consistency, timeliness), (2) Check-level severity/weight (critical/warning/info or custom numeric weight) mapped to dimensions, (3) Calculation parameters (baseline score, influence caps, severity weights, thresholds). All layers support three-tier inheritance with lock control.

## Assumptions

1. **dbt Tests Are Not Replaced**: This plugin complements dbt's built-in testing, not replaces it. dbt tests (via schema.yml) continue to work; plugin quality checks add additional capabilities.
2. **Single Provider Per Platform**: Each platform instance uses ONE quality provider (not mixing GX and Soda). This follows ADR-0037 composability principle.
3. **Connection Reuse**: Quality plugins reuse connection configuration from ComputePlugin rather than defining their own connections.
4. **Great Expectations Version**: floe-quality-gx targets GX Core 1.0+ (not legacy 0.x API).
5. **dbt-expectations Installation**: floe-quality-dbt assumes dbt-expectations package is installed in the dbt project's packages.yml.
6. **Quality Checks Are Additive**: Defining quality checks in floe.yaml adds to (not replaces) any existing dbt tests in schema.yml.
