# Feature Specification: dbt Plugin Abstraction

**Epic**: 5A (dbt Plugin)
**Feature Branch**: `5a-dbt-plugin`
**Created**: 2026-01-24
**Status**: Draft
**Input**: User description: "floe-05a-dbt-plugin - ensure you deeply research dbt (both core and fusion) as well as our existing implementation and target architecture"

## Overview

This epic implements the DBTPlugin abstraction layer that enables floe to support multiple dbt execution environments while maintaining the core principle: **dbt owns ALL SQL compilation**.

### Background

dbt (data build tool) is the **ENFORCED** SQL transformation framework in floe. However, the **execution environment** (where dbt compiles and runs) is **PLUGGABLE**:

| Environment | Technology | Use Case |
|-------------|------------|----------|
| **Local** | dbt-core (Python) + SQLFluff | Development, CI/CD, single-threaded |
| **Fusion** | dbt Fusion CLI (Rust) | High-performance, production, parallel-safe |
| **Cloud** | dbt Cloud API (REST) | Enterprise, managed infrastructure |

**Key Insight**: dbt is a **compiler** (Jinja+SQL → pure SQL), NOT an execution engine. The compiled SQL is executed by the compute adapter (DuckDB, Snowflake, etc.).

### Architecture Reference

- **ADR-0043**: dbt Runtime Abstraction (defines DBTPlugin interface)
- **Entry Point**: `floe.dbt` (local, fusion, cloud)
- **Integration**: OrchestratorPlugin → DBTPlugin (never direct dbtRunner)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local dbt Development (Priority: P1)

As a **data engineer**, I want to compile and run dbt models locally using dbt-core, so that I can develop and test transformations on my machine before deploying to production.

**Why this priority**: This is the foundational use case - every data engineer starts with local development. Without this, no other features can be tested or used.

**Independent Test**: Run `floe compile && floe run` with a simple dbt project containing one model. The model compiles, executes against DuckDB, and produces output.

**Acceptance Scenarios**:

1. **Given** a dbt project with models and a floe.yaml, **When** I run `floe compile`, **Then** the system compiles dbt models using dbt-core and produces manifest.json
2. **Given** a compiled dbt project, **When** I run `floe run`, **Then** models execute in dependency order and I see success/failure status for each
3. **Given** a dbt project with tests, **When** I run `floe test`, **Then** dbt tests execute and report pass/fail results
4. **Given** dbt compilation fails, **When** I view the error, **Then** I see the original dbt error message with file/line information

---

### User Story 2 - dbt Fusion High-Performance Compilation (Priority: P2)

As a **platform engineer**, I want to use dbt Fusion for production pipelines, so that I get ~30x faster parsing (vs dbt-core on 100-model projects) and can safely run parallel compilations.

**Why this priority**: Production workloads require performance and thread safety. dbt-core is NOT thread-safe, making Fusion essential for scaled deployments.

**Independent Test**: Configure `plugins.dbt_runtime: fusion` in manifest.yaml, run `floe compile` on a 100-model project. Compilation completes in <2s (vs ~30s with dbt-core).

**Acceptance Scenarios**:

1. **Given** manifest.yaml with `plugins.dbt_runtime: fusion`, **When** I run `floe compile`, **Then** compilation uses dbt Fusion CLI subprocess
2. **Given** dbt Fusion is not installed, **When** I run `floe compile`, **Then** I see a clear error message with installation instructions
3. **Given** multiple parallel compilation requests, **When** Fusion is used, **Then** all complete successfully without thread conflicts
4. **Given** a dbt project with SQL issues, **When** I run `floe lint`, **Then** Fusion's built-in static analysis reports issues

---

### User Story 3 - SQL Linting with Dialect Awareness (Priority: P3)

As a **data engineer**, I want SQL linting that understands my target dialect (Snowflake, DuckDB, etc.), so that I catch issues before runtime.

**Why this priority**: SQL linting prevents runtime errors and enforces team standards. This is valuable but not blocking for basic functionality.

**Independent Test**: Run `floe lint` on a project with intentional SQL anti-patterns. The linter reports issues with file locations and suggested fixes.

**Acceptance Scenarios**:

1. **Given** a dbt project targeting Snowflake, **When** I run `floe lint`, **Then** SQLFluff uses Snowflake dialect rules
2. **Given** SQL with fixable issues, **When** I run `floe lint --fix`, **Then** files are automatically corrected
3. **Given** a clean SQL project, **When** I run `floe lint`, **Then** I see "No issues found" message
4. **Given** Fusion is configured, **When** I run `floe lint`, **Then** Fusion's built-in linter is used instead of SQLFluff

---

### User Story 4 - Orchestrator Integration (Priority: P1)

As a **platform engineer**, I want Dagster (or Airflow) to invoke dbt through the DBTPlugin abstraction, so that orchestration is decoupled from dbt execution details.

**Why this priority**: This is the architectural core - orchestrators MUST NOT directly invoke dbtRunner. Without this abstraction, we can't swap execution environments.

**Independent Test**: Deploy a Dagster job that materializes dbt assets. The job uses DBTPlugin.run_models() internally, and execution details are opaque to Dagster.

**Acceptance Scenarios**:

1. **Given** a Dagster asset backed by dbt models, **When** I materialize the asset, **Then** Dagster delegates to DBTPlugin.run_models()
2. **Given** DBTPlugin returns DBTRunResult, **When** Dagster processes it, **Then** asset metadata is populated from run_results.json
3. **Given** dbt run fails, **When** Dagster handles the error, **Then** the asset shows failure with dbt error details
4. **Given** an Airflow DAG with dbt tasks, **When** tasks execute, **Then** they use the same DBTPlugin abstraction

---

### User Story 5 - Manifest and Artifacts Retrieval (Priority: P2)

As a **platform engineer**, I want to programmatically retrieve dbt artifacts (manifest.json, run_results.json, catalog.json), so that downstream systems can process them.

**Why this priority**: Artifacts are essential for lineage, documentation, and observability integration.

**Independent Test**: After `floe compile`, call `DBTPlugin.get_manifest()`. Returns parsed manifest.json with nodes, sources, and exposures.

**Acceptance Scenarios**:

1. **Given** a compiled dbt project, **When** I call `get_manifest()`, **Then** I receive the parsed manifest.json dictionary
2. **Given** a completed dbt run, **When** I call `get_run_results()`, **Then** I receive run_results.json with timing and status
3. **Given** dbt docs generated, **When** I call `get_catalog()`, **Then** I receive catalog.json with column-level metadata
4. **Given** artifacts don't exist, **When** I call get_* methods, **Then** I receive a clear error indicating which artifact is missing

---

### Edge Cases

- What happens when dbt-core and dbt Fusion are both installed? → Use the one specified in manifest.yaml
- How does system handle partial dbt run failures (some models succeed, some fail)? → Return DBTRunResult with per-model status
- What happens when dbt version mismatches between local and CI? → Emit warning, document version in artifacts
- How does system handle dbt packages (packages.yml dependencies)? → Plugin runs `dbt deps` before compile; network/version errors raise DBTConfigurationError with original dbt message
- What happens when profile target doesn't exist? → Clear error with available targets listed
- ~~How does system handle dbt Cloud rate limits?~~ (Out of scope - DBTCloudPlugin deferred to Epic 8+)
- What happens when Fusion requires Rust adapters not available for target? → Fallback to dbt-core with warning

## Requirements *(mandatory)*

### Functional Requirements

#### Core Plugin Interface

- **FR-001**: System MUST implement DBTPlugin ABC with standardized interface per ADR-0043
- **FR-002**: DBTPlugin MUST expose `compile_project(project_dir, profiles_dir, target) -> Path` returning manifest.json path
- **FR-003**: DBTPlugin MUST expose `run_models(project_dir, profiles_dir, target, select, exclude, full_refresh) -> DBTRunResult`
- **FR-004**: DBTPlugin MUST expose `test_models(project_dir, profiles_dir, target, select) -> DBTRunResult`
- **FR-005**: DBTPlugin MUST expose `lint_project(project_dir, profiles_dir, target, fix) -> LintResult`
- **FR-006**: DBTPlugin MUST expose `get_manifest(project_dir) -> dict[str, Any]`
- **FR-007**: DBTPlugin MUST expose `get_run_results(project_dir) -> dict[str, Any]`
- **FR-008**: DBTPlugin MUST expose `supports_parallel_execution() -> bool` for thread safety indication
- **FR-009**: DBTPlugin MUST expose `supports_sql_linting() -> bool` for capability detection
- **FR-010**: DBTPlugin MUST expose `get_runtime_metadata() -> dict[str, Any]` for observability

#### DBTCorePlugin (dbt-core)

- **FR-011**: DBTCorePlugin MUST use dbtRunner from dbt-core for all operations
- **FR-012**: DBTCorePlugin MUST return `supports_parallel_execution() = False` (dbtRunner is NOT thread-safe)
- **FR-013**: DBTCorePlugin MUST delegate SQL linting to SQLFluff with dialect from profiles.yml
- **FR-014**: DBTCorePlugin MUST handle dbt packages.yml by running `dbt deps` automatically
- **FR-015**: DBTCorePlugin MUST capture and parse dbt stdout/stderr for structured error reporting
- **FR-016**: DBTCorePlugin MUST support all dbtRunner callbacks (on_event, on_warning, on_error)

#### DBTFusionPlugin (dbt Fusion CLI)

- **FR-017**: DBTFusionPlugin MUST invoke dbt Fusion via subprocess (CLI binary)
- **FR-018**: DBTFusionPlugin MUST return `supports_parallel_execution() = True`
- **FR-019**: DBTFusionPlugin MUST use Fusion's built-in static analysis for linting
- **FR-020**: DBTFusionPlugin MUST detect Fusion binary availability and version
- **FR-021**: DBTFusionPlugin MUST detect when Rust adapters are unavailable for target
- **FR-039**: System MUST automatically fall back to DBTCorePlugin when Fusion adapters are unavailable
- **FR-040**: System MUST emit warning log when automatic fallback occurs

#### Result Schemas

- **FR-022**: DBTRunResult MUST include: success (bool), elapsed_time (float), nodes (list of node results)
- **FR-023**: DBTRunResult.nodes MUST include: unique_id, status (success/error/skipped), timing, error_message
- **FR-024**: LintResult MUST include: passed (bool), violations (list), fixed_count (int if fix=True)
- **FR-025**: LintViolation MUST include: file_path, line, column, code, message, severity

#### Plugin Discovery and Configuration

- **FR-026**: System MUST discover DBTPlugin implementations via `floe.dbt` entry point
- **FR-027**: System MUST read `plugins.dbt_runtime` from manifest.yaml to select implementation
- **FR-028**: System MUST default to `core` if `plugins.dbt_runtime` is not specified
- **FR-029**: System MUST validate that selected DBTPlugin is installed and functional

#### Orchestrator Integration

- **FR-030**: OrchestratorPlugin MUST delegate dbt operations to DBTPlugin, never invoke dbtRunner directly
- **FR-031**: OrchestratorPlugin MUST use DBTRunResult to populate asset/task metadata
- **FR-032**: OrchestratorPlugin MUST pass `select` and `exclude` patterns to DBTPlugin for partial runs
- **FR-037**: System MUST provide DBTPlugin as a Dagster ConfigurableResource for asset injection
- **FR-038**: DBTResource MUST be configurable via manifest.yaml `plugins.dbt_runtime` setting

#### Error Handling

- **FR-033**: DBTPlugin MUST raise DBTCompilationError for compilation failures with original dbt message
- **FR-034**: DBTPlugin MUST raise DBTExecutionError for runtime failures with model-specific details
- **FR-035**: DBTPlugin MUST raise DBTConfigurationError for invalid profiles or missing dependencies
- **FR-036**: All errors MUST preserve dbt's file/line information when available
- **FR-041**: DBTPlugin MUST raise DBTLintError when linting process itself fails (not SQL issues)

### Key Entities

- **DBTPlugin**: Abstract base class defining the dbt execution environment interface
- **DBTCorePlugin**: Implementation using dbt-core Python API (dbtRunner) - package: `floe-dbt-core`
- **DBTFusionPlugin**: Implementation using dbt Fusion CLI subprocess - package: `floe-dbt-fusion`
- **DBTRunResult**: Standardized result from run/test operations
- **LintResult**: Standardized result from lint operations
- **DBTCompilationError**: Exception for compilation failures
- **DBTExecutionError**: Exception for runtime failures

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: DBTCorePlugin can compile a 50-model project in <30s
- **SC-002**: DBTFusionPlugin can compile a 50-model project in <2s (15x faster than local)
- **SC-003**: All DBTPlugin implementations pass the compliance test suite (100% interface coverage)
- **SC-004**: Orchestrator tests pass without ANY direct dbtRunner imports
- **SC-005**: SQL linting detects 100% of intentionally planted dialect-specific issues
- **SC-006**: Error messages include file path and line number for 100% of parsing errors
- **SC-007**: Plugin discovery finds all installed implementations within 100ms

## Non-Functional Requirements

### Performance

- **NFR-001**: Plugin initialization MUST complete in <500ms
- **NFR-002**: Artifact retrieval (get_manifest, get_run_results) MUST complete in <100ms for 10MB files

### Compatibility

- **NFR-003**: DBTCorePlugin MUST support dbt-core 1.6+ (current LTS)
- **NFR-004**: DBTFusionPlugin MUST support dbt Fusion 0.1+ (current beta)
- **NFR-005**: All plugins MUST work with Python 3.10+

### Observability

- **NFR-006**: All plugin operations MUST emit OpenTelemetry spans
- **NFR-007**: Compilation/run operations MUST emit OpenLineage events

## Out of Scope (Epic 5A)

The following are explicitly **NOT** in scope for Epic 5A:

- **DBTCloudPlugin**: dbt Cloud API integration (deferred to Epic 8+)
- **Incremental model optimization**: Beyond dbt's native incremental handling
- **Custom materializations**: Plugin for custom dbt materializations
- **Multi-project compilation**: Single project per invocation only
- **dbt Semantic Layer**: Metrics layer integration (separate epic)

## Dependencies

### Upstream (Required Before Epic 5A)

- **Epic 1**: Plugin Registry (completed) - For plugin discovery via entry points
- **Epic 2B**: Compilation Pipeline (completed) - For CompiledArtifacts integration

### Downstream (Depends on Epic 5A)

- **Epic 6**: OrchestratorPlugin implementations (Dagster, Airflow) will use DBTPlugin
- **Epic 8+**: DBTCloudPlugin (dbt Cloud API integration)

## Technical Notes

### dbt-core Thread Safety Warning

From dbt-core documentation and testing:
> dbtRunner is **NOT thread-safe**. Multiple concurrent invocations in the same process will cause undefined behavior.

This is why `DBTCorePlugin.supports_parallel_execution()` returns `False` and why DBTFusionPlugin is critical for production.

### dbt Fusion Adapter Compatibility

dbt Fusion requires Rust-based adapters. As of 2026-01:
- **Supported**: DuckDB (duckdb-rs), Snowflake (snowflake-connector-rust)
- **Not Supported**: BigQuery, Databricks, Redshift (Python adapters only)

When a target requires an unsupported adapter, the system should:
1. Emit a warning
2. Fall back to DBTCorePlugin if available
3. Fail with clear error if fallback not possible

### SQLFluff Dialect Mapping

SQLFluff dialect is derived from the dbt profile target:
| dbt Adapter | SQLFluff Dialect |
|-------------|------------------|
| duckdb | duckdb |
| snowflake | snowflake |
| bigquery | bigquery |
| postgres | postgres |
| redshift | redshift |

### Package Structure

Plugin implementations live in separate packages under `plugins/`:
- `plugins/floe-dbt-core/` - DBTCorePlugin (dbt-core + SQLFluff)
- `plugins/floe-dbt-fusion/` - DBTFusionPlugin (dbt Fusion CLI)

Each package has its own entry point registered under `floe.dbt`.

## Clarifications

- Q: Where should DBTCorePlugin and DBTFusionPlugin implementations live? A: Separate plugin packages under `plugins/` (`plugins/floe-dbt-core/` and `plugins/floe-dbt-fusion/`)
- Q: What should Epic 5A deliver for orchestrator integration? A: Interface contract + implementations. Epic 5A defines DBTPlugin interface, provides contract tests, and creates the integration mechanism (Dagster resource) that the existing orchestrator can use. The current DagsterOrchestratorPlugin creates placeholder assets - Epic 5A wires up actual dbt execution.
- Q: Should the plugin enforce a specific dbt-core version range? A: Range with minimum - require `dbt-core>=1.6,<2.0` to ensure dbtRunner API compatibility while allowing patch updates for security fixes.
- Q: How should DBTPlugin integrate with Dagster? A: ConfigurableResource pattern - DBTPlugin wrapped as Dagster ConfigurableResource, injected into assets. This provides type-safe configuration, dependency injection, and clean testing while keeping orchestrator decoupled from dbt execution details.
- Q: Should Fusion fallback to dbt-core be automatic or require explicit configuration? A: Automatic with warning - fall back to DBTCorePlugin automatically when Fusion adapters are unavailable, emit warning log for visibility.
