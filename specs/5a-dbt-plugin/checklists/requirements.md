# Epic 5A: dbt Plugin - Requirements Checklist

Generated: 2026-01-24

## Functional Requirements

### Core Plugin Interface
- [ ] FR-001: System MUST implement DBTPlugin ABC with standardized interface per ADR-0043
- [ ] FR-002: DBTPlugin MUST expose `compile_project(project_dir, profiles_dir, target) -> Path`
- [ ] FR-003: DBTPlugin MUST expose `run_models(project_dir, profiles_dir, target, select, exclude, full_refresh) -> DBTRunResult`
- [ ] FR-004: DBTPlugin MUST expose `test_models(project_dir, profiles_dir, target, select) -> DBTRunResult`
- [ ] FR-005: DBTPlugin MUST expose `lint_project(project_dir, profiles_dir, target, fix) -> LintResult`
- [ ] FR-006: DBTPlugin MUST expose `get_manifest(project_dir) -> dict[str, Any]`
- [ ] FR-007: DBTPlugin MUST expose `get_run_results(project_dir) -> dict[str, Any]`
- [ ] FR-008: DBTPlugin MUST expose `supports_parallel_execution() -> bool`
- [ ] FR-009: DBTPlugin MUST expose `supports_sql_linting() -> bool`
- [ ] FR-010: DBTPlugin MUST expose `get_runtime_metadata() -> dict[str, Any]`

### LocalDBTPlugin (dbt-core)
- [ ] FR-011: LocalDBTPlugin MUST use dbtRunner from dbt-core for all operations
- [ ] FR-012: LocalDBTPlugin MUST return `supports_parallel_execution() = False`
- [ ] FR-013: LocalDBTPlugin MUST delegate SQL linting to SQLFluff with dialect from profiles.yml
- [ ] FR-014: LocalDBTPlugin MUST handle dbt packages.yml by running `dbt deps` automatically
- [ ] FR-015: LocalDBTPlugin MUST capture and parse dbt stdout/stderr for structured error reporting
- [ ] FR-016: LocalDBTPlugin MUST support all dbtRunner callbacks (on_event, on_warning, on_error)

### DBTFusionPlugin (dbt Fusion CLI)
- [ ] FR-017: DBTFusionPlugin MUST invoke dbt Fusion via subprocess (CLI binary)
- [ ] FR-018: DBTFusionPlugin MUST return `supports_parallel_execution() = True`
- [ ] FR-019: DBTFusionPlugin MUST use Fusion's built-in static analysis for linting
- [ ] FR-020: DBTFusionPlugin MUST detect Fusion binary availability and version
- [ ] FR-021: DBTFusionPlugin MUST emit clear error when Rust adapters are unavailable

### Result Schemas
- [ ] FR-022: DBTRunResult MUST include: success, elapsed_time, nodes
- [ ] FR-023: DBTRunResult.nodes MUST include: unique_id, status, timing, error_message
- [ ] FR-024: LintResult MUST include: passed, violations, fixed_count
- [ ] FR-025: LintViolation MUST include: file_path, line, column, code, message, severity

### Plugin Discovery and Configuration
- [ ] FR-026: System MUST discover DBTPlugin implementations via `floe.dbt` entry point
- [ ] FR-027: System MUST read `plugins.dbt_runtime` from manifest.yaml to select implementation
- [ ] FR-028: System MUST default to `local` if `plugins.dbt_runtime` is not specified
- [ ] FR-029: System MUST validate that selected DBTPlugin is installed and functional

### Orchestrator Integration
- [ ] FR-030: OrchestratorPlugin MUST delegate dbt operations to DBTPlugin
- [ ] FR-031: OrchestratorPlugin MUST use DBTRunResult to populate asset/task metadata
- [ ] FR-032: OrchestratorPlugin MUST pass `select` and `exclude` patterns to DBTPlugin

### Error Handling
- [ ] FR-033: DBTPlugin MUST raise DBTCompilationError for compilation failures
- [ ] FR-034: DBTPlugin MUST raise DBTExecutionError for runtime failures
- [ ] FR-035: DBTPlugin MUST raise DBTConfigurationError for invalid profiles
- [ ] FR-036: All errors MUST preserve dbt's file/line information

## Success Criteria

- [ ] SC-001: LocalDBTPlugin can compile a 50-model project in <30s
- [ ] SC-002: DBTFusionPlugin can compile a 50-model project in <2s
- [ ] SC-003: All DBTPlugin implementations pass compliance test suite (100%)
- [ ] SC-004: Orchestrator tests pass without ANY direct dbtRunner imports
- [ ] SC-005: SQL linting detects 100% of planted dialect-specific issues
- [ ] SC-006: Error messages include file path and line number (100%)
- [ ] SC-007: Plugin discovery finds all implementations within 100ms

## Non-Functional Requirements

### Performance
- [ ] NFR-001: Plugin initialization MUST complete in <500ms
- [ ] NFR-002: Artifact retrieval MUST complete in <100ms for 10MB files

### Compatibility
- [ ] NFR-003: LocalDBTPlugin MUST support dbt-core 1.6+
- [ ] NFR-004: DBTFusionPlugin MUST support dbt Fusion 0.1+
- [ ] NFR-005: All plugins MUST work with Python 3.10+

### Observability
- [ ] NFR-006: All plugin operations MUST emit OpenTelemetry spans
- [ ] NFR-007: Compilation/run operations MUST emit OpenLineage events

## User Stories

- [ ] US1: Local dbt Development (P1) - Compile and run dbt models locally
- [ ] US2: dbt Fusion High-Performance Compilation (P2) - 30x faster, parallel-safe
- [ ] US3: SQL Linting with Dialect Awareness (P3) - Dialect-specific linting
- [ ] US4: Orchestrator Integration (P1) - Dagster/Airflow via DBTPlugin
- [ ] US5: Manifest and Artifacts Retrieval (P2) - Programmatic artifact access

## Edge Cases

- [ ] Both dbt-core and Fusion installed → Use manifest.yaml selection
- [ ] Partial run failures → Return per-model status in DBTRunResult
- [ ] dbt version mismatch → Emit warning, document in artifacts
- [ ] packages.yml dependencies → Run `dbt deps` before compile
- [ ] Profile target doesn't exist → Clear error with available targets
- [ ] Fusion adapter unavailable → Fallback to dbt-core with warning
