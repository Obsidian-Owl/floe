# Feature Specification: Compilation Pipeline

**Epic**: 2B (Compilation Pipeline)
**Feature Branch**: `2b-compilation-pipeline`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "Compilation pipeline that transforms FloeSpec and PlatformManifest into CompiledArtifacts"

## Clarifications

### Session 2026-01-14

- Q: Should FR-007 be clarified to respect technology ownership boundary (floe-core compiles data, floe-dagster generates Dagster config)? → A: Yes, CompiledArtifacts includes configuration DATA that floe-dagster uses to generate Dagster Definitions. floe-core provides data; floe-dagster owns code generation.
- Q: Should environment-agnostic compilation (REQ-151, ADR-0039) be an explicit requirement? → A: Yes, add FR-014. Compile once, deploy everywhere. Same artifact digest promoted across environments.
- Q: Should OCI output format be deferred to Epic 8A (OCI Client)? → A: Yes, defer OCI output to Epic 8A. Epic 2B outputs JSON/YAML only. OCI packaging/distribution is Epic 8A scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compile Data Product Configuration (Priority: P1)

As a data engineer, I want to compile my floe.yaml with the platform manifest so that I get validated, deployable artifacts without manual configuration of dbt or Dagster.

**Why this priority**: This is the core value proposition - transforming configuration into executable artifacts. Without compilation, no other features work.

**Independent Test**: Can be fully tested by running `floe compile` on a valid floe.yaml + manifest and verifying CompiledArtifacts JSON output with correct dbt profiles and Dagster configuration.

**Acceptance Scenarios**:

1. **Given** a valid floe.yaml and platform manifest, **When** I run `floe compile`, **Then** I receive a CompiledArtifacts JSON file containing dbt profiles, Dagster configuration, and metadata.
2. **Given** a floe.yaml with invalid schema, **When** I run `floe compile`, **Then** I receive an actionable error message indicating the validation failure and suggested fix.
3. **Given** a floe.yaml referencing unavailable plugins, **When** I run `floe compile`, **Then** I receive a clear error listing missing plugins and how to install them.

---

### User Story 2 - Generate dbt Profiles Automatically (Priority: P1)

As a data engineer, I want dbt profiles.yml generated automatically from my platform configuration so that I don't have to manually configure database connections for each environment.

**Why this priority**: dbt profiles are required for any transformation work. Manual profile setup is error-prone and environment-specific.

**Independent Test**: Can be tested by compiling a manifest with compute plugin configuration and verifying the generated profiles.yml is valid for the target compute (DuckDB, Snowflake, etc.).

**Acceptance Scenarios**:

1. **Given** a manifest with DuckDB compute plugin, **When** I compile, **Then** profiles.yml contains a valid DuckDB target with correct path configuration.
2. **Given** a manifest with Snowflake compute plugin, **When** I compile, **Then** profiles.yml contains credential placeholders using `{{ env_var('SECRET_NAME') }}` syntax for runtime resolution.
3. **Given** missing required compute credentials, **When** I compile, **Then** I receive an error listing the missing credential references.

---

### User Story 3 - Validate Before Deployment (Priority: P2)

As a data engineer, I want to validate my configuration without generating artifacts so that I can catch errors early in my development workflow.

**Why this priority**: Fast feedback during development prevents wasted time on full compilation when basic validation fails.

**Independent Test**: Can be tested by running `floe compile --dry-run` on configurations with various validation states.

**Acceptance Scenarios**:

1. **Given** a valid configuration, **When** I run `floe compile --dry-run`, **Then** I see "Validation successful" with no files written.
2. **Given** a configuration with policy violations, **When** I run `floe compile --validate-only`, **Then** I see all policy errors without dbt/Dagster compilation.
3. **Given** any dry-run mode, **When** compilation completes, **Then** no files are written to disk and no catalog changes occur.

---

### User Story 4 - CompiledArtifacts as Integration Contract (Priority: P2)

As a platform developer, I want CompiledArtifacts to be a stable, versioned contract so that floe-core and floe-dagster can evolve independently while maintaining compatibility.

**Why this priority**: Cross-package integration depends on stable contracts. Schema changes must be controlled and versioned.

**Independent Test**: Can be tested by serializing CompiledArtifacts to JSON, deserializing it, and verifying round-trip integrity with schema validation.

**Acceptance Scenarios**:

1. **Given** CompiledArtifacts with all fields populated, **When** I serialize to JSON and deserialize, **Then** all fields are preserved with identical values.
2. **Given** a CompiledArtifacts JSON from a previous version, **When** I load it with the current schema, **Then** backward compatibility is maintained for additive changes.
3. **Given** an attempt to modify a frozen CompiledArtifacts instance, **When** any field is changed, **Then** a validation error is raised.

---

### User Story 5 - Multiple Output Formats (Priority: P3)

As a data engineer, I want to output compiled artifacts in different formats (JSON, YAML) so that I can use the format most appropriate for my workflow.

**Why this priority**: JSON is default for machine consumption, YAML for human debugging.

**Independent Test**: Can be tested by compiling to each format and verifying data parity across formats.

**Acceptance Scenarios**:

1. **Given** a successful compilation, **When** I specify `--output=target/compiled.json`, **Then** a valid JSON file is created.
2. **Given** a successful compilation, **When** I specify `--output=target/compiled.yaml`, **Then** a valid YAML file with identical data is created.
3. **Given** JSON and YAML outputs from the same compilation, **When** I compare data content, **Then** they are semantically identical.

**Out of Scope**: OCI output format is deferred to Epic 8A (OCI Client).

---

### Edge Cases

- What happens when the platform manifest cannot be loaded from OCI registry? System should fail with network error and retry guidance.
- How does system handle circular manifest inheritance? Validation should detect cycles and fail with clear error.
- What happens when compile is interrupted mid-process? No partial files should be written; compilation is atomic.
- How does system handle compute plugins that are installed but misconfigured? Clear error with configuration example.

### Out of Scope

- **OCI Output Format**: Deferred to Epic 8A (OCI Client). Epic 2B outputs JSON/YAML only.
- **Compilation Caching**: Deferred to future epic per ADR-0045. Initial implementation focuses on correctness.
- **FloeSpec Schema Definition**: Prerequisite from Epic 2A (Manifest Schema) or defined as part of Epic 2B initial tasks.
- **Policy Enforcement Logic**: Epic 3A (Policy Enforcer) consumes CompiledArtifacts for enforcement.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `floe compile` command that executes a multi-stage pipeline: load, validate, resolve, enforce, compile, artifact generation.
- **FR-002**: System MUST stop compilation on first error and provide an actionable error message indicating the stage, cause, and suggested fix.
- **FR-003**: System MUST generate CompiledArtifacts as an immutable Pydantic model containing version, metadata, compute config, transforms config, and observability config.
- **FR-004**: System MUST serialize CompiledArtifacts via `to_json_file(path)` and deserialize via `from_json_file(path)`.
- **FR-005**: System MUST generate valid dbt profiles.yml from ComputePlugin configuration with credential placeholders for runtime resolution.
- **FR-006**: System MUST support multiple compute targets (DuckDB, Snowflake, BigQuery, Databricks) via the registered ComputePlugin.
- **FR-007**: System MUST include orchestrator configuration data in CompiledArtifacts (schedules, resource requirements, asset dependencies) that floe-dagster consumes to generate Dagster Definitions. Note: floe-core provides DATA; floe-dagster owns Dagster code generation per technology ownership boundaries.
- **FR-008**: System MUST include artifact metadata: version, product_version, platform_version, generated_at (ISO 8601), generated_by, git_commit.
- **FR-009**: System MUST support `--dry-run` flag that validates all stages without generating artifacts.
- **FR-010**: System MUST support `--validate-only` flag that checks policies without dbt/Dagster compilation.
- **FR-011**: System MUST support JSON output format (default) and YAML output format.
- **FR-012**: System MUST return non-zero exit code on any validation or compilation failure.
- **FR-013**: System MUST log clear progress for each compilation stage with timing information.
- **FR-014**: Compilation MUST be environment-agnostic. The same CompiledArtifacts digest MUST be promotable across dev/staging/prod without recompilation. Runtime behavior is determined by FLOE_ENV environment variable, not compile-time configuration. Credentials use placeholders (e.g., `${SNOWFLAKE_PASSWORD}`) resolved at runtime.

### Key Entities

- **CompiledArtifacts**: The sole contract between floe-core and downstream packages. Contains resolved configuration for compute, transforms, governance, and observability. Frozen (immutable) after creation.
- **FloeSpec**: Data engineer's configuration from floe.yaml. Defines data product, models, schedules, and quality requirements.
- **PlatformManifest**: Platform team's configuration defining plugin selection, policies, and governance rules.
- **CompilationStage**: Enumeration of pipeline stages (LOAD, VALIDATE, RESOLVE, ENFORCE, COMPILE, GENERATE) with associated handlers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Data engineers can compile a valid configuration in under 5 seconds for typical data products (10-50 models).
- **SC-002**: 100% of compilation errors include actionable remediation guidance (suggested fix or documentation link).
- **SC-003**: CompiledArtifacts maintains backward compatibility for at least 2 minor versions (additive changes only break on major version).
- **SC-004**: Generated dbt profiles.yml passes `dbt debug` validation for all supported compute plugins.
- **SC-005**: CompiledArtifacts consumed by floe-dagster produces Dagster Definitions that load successfully via `dagster dev` without modification.
- **SC-006**: Dry-run mode completes in under 2 seconds with zero side effects (no files written, no network calls to catalogs).
- **SC-007**: 90% of first-time users successfully compile their first data product without documentation reference (measured via onboarding feedback).
