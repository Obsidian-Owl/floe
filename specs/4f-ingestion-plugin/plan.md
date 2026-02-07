# Implementation Plan: Ingestion Plugin (dlt)

**Branch**: `4f-ingestion-plugin` | **Date**: 2026-02-07 | **Spec**: specs/4f-ingestion-plugin/spec.md

## Summary

Implement the `DltIngestionPlugin` as the default ingestion plugin for floe, providing data pipeline creation via dlt v1.21.0, execution with structured results, and Iceberg destination configuration via Polaris REST catalog. The plugin implements the existing `IngestionPlugin` ABC (no ABC changes), supports 3 source types (REST API, SQL Database, Filesystem), 3 write modes (append, replace, merge), 3 schema contracts (evolve, freeze, discard_value), cursor-based incremental loading, custom OTel spans, structured logging, and error categorization with tenacity-based retry. Orchestrator wiring follows the Epic 4E pattern — all Dagster-specific code (resource factory, asset factory, DagsterDltTranslator) lives in `plugins/floe-orchestrator-dagster/`.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: dlt[iceberg]>=1.20.0 (framework), pydantic>=2.0 (config), structlog>=24.0 (logging), opentelemetry-api>=1.0 (tracing), tenacity>=8.0 (retry), httpx>=0.25.0 (health checks)
**Storage**: Iceberg tables via Polaris REST catalog, MinIO/S3 for data files (dlt handles destination config)
**Testing**: pytest, testing.base_classes (BasePluginDiscoveryTests, BaseHealthCheckTests), IntegrationTestBase
**Target Platform**: K8s (dlt runs in-process within orchestrator pods)
**Project Type**: Monorepo plugin package
**Performance Goals**: Pipeline creation <1s, REST API ingestion <30s for integration tests (SC-004)
**Constraints**: Must follow plugin ABC pattern, Pydantic v2, mypy --strict, ruff, bandit, >80% coverage
**Scale/Scope**: 1 new plugin package (`plugins/floe-ingestion-dlt/`), orchestrator wiring additions (`plugins/floe-orchestrator-dagster/`), 1 test fixture file, 2 contract test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package: dlt plugin in `plugins/floe-ingestion-dlt/`, Dagster wiring in `plugins/floe-orchestrator-dagster/`, ABC unchanged in `packages/floe-core/`
- [x] No SQL parsing/validation in Python — dlt handles data extraction/loading; SQL is dbt's domain
- [x] No orchestration logic outside floe-dagster — ingestion plugin is orchestrator-agnostic; all Dagster code in orchestrator plugin

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface: DltIngestionPlugin inherits IngestionPlugin ABC
- [x] Plugin registered via entry point: `[project.entry-points."floe.ingestion"]` with `dlt = "floe_ingestion_dlt:DltIngestionPlugin"`
- [x] PluginMetadata declares name ("dlt"), version ("0.1.0"), floe_api_version ("1.0")

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved: Iceberg (destination), OTel (custom spans), K8s (deployment)
- [x] Pluggable choices documented: Ingestion is pluggable (dlt is default; Airbyte future); orchestrator is pluggable (Dagster wiring is one implementation)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts: `CompiledArtifacts.plugins.ingestion` is `PluginRef | None` (already in v0.5.0, no changes)
- [x] Pydantic v2 models for all schemas: `DltIngestionConfig` with `ConfigDict(frozen=True, extra="forbid")`, `SecretStr` for credentials
- [x] Contract changes follow versioning rules: No contract changes needed (existing schema sufficient)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster: Real Polaris + MinIO for pipeline tests
- [x] No `pytest.skip()` usage: Tests FAIL if infrastructure unavailable
- [x] `@pytest.mark.requirement()` on all integration tests: Mapped to FR-xxx identifiers

**Principle VI: Security First**
- [x] Input validation via Pydantic: `DltIngestionConfig`, `IngestionSourceConfig` validate all fields
- [x] Credentials use SecretStr: `SecretStr` for any credential fields in config  <!-- pragma: allowlist secret -->
- [x] No shell=True, no dynamic code execution on untrusted data: dlt uses Python API, no subprocess

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only: Plugin config from CompiledArtifacts; credentials from K8s Secrets as env vars
- [x] Layer ownership respected: Plugin (Layer 1: Foundation), orchestrator wiring (Layer 3: Services)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted: Custom spans for `create_pipeline`, `run`, `get_destination_config` (dlt has no native OTel)
- [x] OpenLineage events for data transformations: Automatic via orchestrator's lineage integration (e.g., `openlineage-dagster`)

## Project Structure

### Documentation (this feature)

```text
specs/4f-ingestion-plugin/
├── spec.md              # Feature specification (exists)
├── plan.md              # This file
├── research.md          # Phase 0 output (exists)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# floe-core (NO CHANGES — existing ABC is sufficient)
packages/floe-core/src/floe_core/plugins/
  ingestion.py                     # IngestionPlugin ABC — UNCHANGED

# dlt Plugin (NEW)
plugins/floe-ingestion-dlt/
  pyproject.toml                   # Entry point: floe.ingestion -> dlt
  src/floe_ingestion_dlt/
    __init__.py                    # Exports: DltIngestionPlugin, DltIngestionConfig
    plugin.py                      # DltIngestionPlugin (ABC implementation)
    config.py                      # DltIngestionConfig, IngestionSourceConfig, RetryConfig
    errors.py                      # IngestionError hierarchy
    retry.py                       # tenacity retry logic + error categorization
    tracing.py                     # OTel span helpers
    py.typed                       # PEP 561 marker
  tests/
    conftest.py
    unit/
      conftest.py
      test_plugin.py               # ABC compliance, metadata, lifecycle
      test_config.py               # Config validation, edge cases
      test_errors.py               # Error hierarchy
      test_retry.py                # Retry logic, error categorization
    integration/
      conftest.py
      test_discovery.py            # Inherits BasePluginDiscoveryTests
      test_health_check.py         # Inherits BaseHealthCheckTests
      test_pipeline.py             # Real dlt pipeline with Iceberg
      test_iceberg_load.py         # Data landing verification

# Orchestrator Wiring (MODIFY EXISTING)
plugins/floe-orchestrator-dagster/
  src/floe_orchestrator_dagster/
    resources/
      ingestion.py                 # try_create_ingestion_resources() (NEW)
    assets/
      ingestion.py                 # ingestion asset factory + DagsterDltTranslator (NEW)
  tests/
    unit/
      test_ingestion_resources.py  # Unit tests for resource factory (NEW)
      test_ingestion_translator.py # Unit tests for DagsterDltTranslator (NEW)
    integration/
      test_ingestion_wiring.py     # Integration test for full wiring chain (NEW)

# Test Fixtures (NEW)
testing/fixtures/ingestion.py

# Contract Tests (NEW)
tests/contract/test_ingestion_plugin_abc.py
tests/contract/test_core_to_ingestion_contract.py
```

**Structure Decision**: Plugin package at `plugins/floe-ingestion-dlt/` following the established pattern from `plugins/floe-semantic-cube/` (Epic 4E) and `plugins/floe-catalog-polaris/`. Uses `hatchling` build system with `src/` layout and `[project.entry-points."floe.ingestion"]`.

## Integration Design

### Entry Point Integration

- Feature reachable from: Plugin Registry via entry point `floe.ingestion`
- Entry point declaration: `plugins/floe-ingestion-dlt/pyproject.toml` -> `[project.entry-points."floe.ingestion"]` -> `dlt = "floe_ingestion_dlt:DltIngestionPlugin"`
- Discovery path: `PluginDiscovery.discover_all()` -> `PluginLoader.get(PluginType.INGESTION, "dlt")` -> `DltIngestionPlugin` instance
- Wiring verification: `test_all_plugin_types_discoverable` E2E test must pass with `INGESTION` type present (SC-003)

### Dependency Integration

| From Package | What Is Used | Import Path |
|---|---|---|
| `floe-core` | `IngestionPlugin` ABC | `floe_core.plugins.ingestion.IngestionPlugin` |
| `floe-core` | `IngestionConfig`, `IngestionResult` | `floe_core.plugins.ingestion` |
| `floe-core` | `PluginMetadata`, `HealthStatus`, `HealthState` | `floe_core.plugin_metadata` |
| `floe-core` | OTel tracer factory | `floe_core.telemetry.tracer_factory.get_tracer` |
| `pydantic` | `BaseModel`, `ConfigDict`, `Field`, `SecretStr`, `field_validator` | `pydantic` |
| `structlog` | Structured logging | `structlog` |
| `opentelemetry-api` | Span creation, attributes | `opentelemetry.trace` |
| `dlt` | Pipeline API, Iceberg destination, sources | `dlt` |
| `tenacity` | Retry decorator, stop/wait strategies | `tenacity` |

### Produces for Others

| What Is Produced | Consumer | Integration Point |
|---|---|---|
| `DltIngestionPlugin` instance | Plugin Registry | Entry point `floe.ingestion` |
| dlt pipeline object | Orchestrator (via run()) | `create_pipeline()` return value |
| `IngestionResult` | Orchestrator, observability | `run()` return value |
| Iceberg destination config | dlt pipeline | `get_destination_config()` return value |
| Orchestrator ingestion resources | Dagster Definitions | `try_create_ingestion_resources()` in orchestrator plugin |
| Dagster assets per dlt resource | Dagster asset graph | Asset factory in orchestrator plugin |
| Test fixtures (`dlt_config`, `dlt_plugin`) | Integration tests | `testing/fixtures/ingestion.py` |

### Cleanup Required

- None (new code, no refactoring of existing code; ABC and CompiledArtifacts are unchanged)

## Implementation Phases

### Phase 0: Foundation (Package Scaffold + Config + Errors + Tracing)

This phase establishes the plugin package and shared infrastructure.

**T001: Create plugin package scaffold (pyproject.toml, __init__.py, py.typed)**
- File: `plugins/floe-ingestion-dlt/pyproject.toml`
  - Build system: `hatchling`
  - Entry point: `[project.entry-points."floe.ingestion"]` -> `dlt = "floe_ingestion_dlt:DltIngestionPlugin"`
  - Dependencies: `floe-core>=0.1.0`, `dlt[iceberg]>=1.20.0,<2.0.0`, `pydantic>=2.0,<3.0`, `structlog>=24.0,<26.0`, `opentelemetry-api>=1.0,<2.0`, `tenacity>=8.0,<10.0`
  - Dev dependencies: `pytest`, `pytest-cov`, `mypy`, `ruff`
  - Tool config: mypy strict, ruff, pytest markers
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/__init__.py` (exports DltIngestionPlugin, DltIngestionConfig)
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/py.typed` (empty PEP 561 marker)
- Requirements: FR-002

**T002: Create DltIngestionConfig and IngestionSourceConfig Pydantic models**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/config.py`
- `DltIngestionConfig(BaseModel)` with `model_config = ConfigDict(frozen=True, extra="forbid")`
- Fields:
  - `sources: list[IngestionSourceConfig]` (data sources to ingest)
  - `catalog_config: dict[str, Any]` (Polaris connection details)
  - `retry_config: RetryConfig | None` (optional retry parameters)
- `IngestionSourceConfig(BaseModel)` with frozen=True, extra="forbid":
  - `name: str` (unique identifier, min_length=1)
  - `source_type: str` (rest_api|sql_database|filesystem)
  - `source_config: dict[str, Any]` (source-specific parameters)
  - `destination_table: str` (Iceberg table path)
  - `write_mode: str` (append|replace|merge, default "append")
  - `schema_contract: str` (evolve|freeze|discard_value, default "evolve")
  - `cursor_field: str | None` (for incremental loading)
  - `primary_key: str | list[str] | None` (for merge mode)
- `RetryConfig(BaseModel)`:
  - `max_retries: int` (default 3, ge=0)
  - `initial_delay_seconds: float` (default 1.0, gt=0)
- Field validators: `source_type` in allowed set, `write_mode` in allowed set, `schema_contract` in allowed set
- Requirements: FR-006, FR-067, FR-068, FR-069, FR-070, FR-071, FR-072, FR-073

**T003: Create error type hierarchy**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/errors.py`
- `IngestionError(Exception)` — base error with `source_type`, `destination_table`, `pipeline_name` context
- `SourceConnectionError(IngestionError)` — source unreachable
- `DestinationWriteError(IngestionError)` — Iceberg write failure
- `SchemaContractViolation(IngestionError)` — schema freeze/discard violations
- `PipelineConfigurationError(IngestionError)` — invalid config or missing dependencies
- Error taxonomy enum: `ErrorCategory(Enum)` with TRANSIENT, PERMANENT, PARTIAL, CONFIGURATION
- Requirements: FR-055, FR-056

**T004: Create OTel tracing helpers**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/tracing.py`
- Follow pattern from `plugins/floe-catalog-polaris/src/floe_catalog_polaris/tracing.py`
- Span name prefix: `floe.ingestion`
- Helper functions: `start_ingestion_span(operation)`, `record_ingestion_result(span, result)`, `record_ingestion_error(span, error)`
- Attributes: `ingestion.source_type`, `ingestion.destination_table`, `ingestion.write_mode`, `ingestion.pipeline_name`
- Requirements: FR-044, FR-045, FR-046, FR-047

**T005: Create retry logic with error categorization**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/retry.py`
- `categorize_error(error: Exception) -> ErrorCategory` — maps dlt exceptions to taxonomy
  - `PipelineStepFailed` with network/timeout → TRANSIENT
  - `PipelineStepFailed` with auth/permission → PERMANENT
  - `ValidationError` → CONFIGURATION
  - Other → TRANSIENT (default retryable)
- `create_retry_decorator(retry_config: RetryConfig)` — returns tenacity retry decorator
  - `stop=stop_after_attempt(max_retries)`
  - `wait=wait_exponential(multiplier=initial_delay_seconds)`
  - `retry=retry_if_exception(is_transient_error)`
  - `reraise=True`
- Requirements: FR-051, FR-052, FR-053, FR-054

### Phase 1: Core Plugin (DltIngestionPlugin)

This phase implements the plugin class with all ABC methods plus lifecycle.

**T006: Implement DltIngestionPlugin class skeleton**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Class: `DltIngestionPlugin(IngestionPlugin)`
- Constructor accepts `DltIngestionConfig` instance
- Metadata properties: `name="dlt"`, `version="0.1.0"`, `floe_api_version="1.0"`, `description="dlt ingestion plugin for floe data platform"`
- `is_external` property returns `False` (dlt runs in-process)
- `get_config_schema()` returns `DltIngestionConfig`
- Requirements: FR-001, FR-003, FR-004, FR-005, FR-006, FR-010

**T007: Implement startup/shutdown lifecycle**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- `startup()`: Validate config, verify dlt is importable, verify required source packages, log startup
- `shutdown()`: Cleanup any resources, log shutdown
- OTel spans on both operations
- Raise `ImportError` with installation instructions if dlt source packages missing
- Requirements: FR-008, FR-009

**T008: Implement health_check()**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Verify dlt is importable → HEALTHY
- Verify Iceberg destination is reachable (test catalog connection) → HEALTHY
- Return UNHEALTHY with message on failure
- OTel span: `floe.ingestion.health_check`
- Requirements: FR-007

**T009: Implement create_pipeline()**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Accept `IngestionConfig`, return dlt pipeline object
- Configure dlt pipeline with:
  - `pipeline_name` derived from `destination_table`
  - `destination="iceberg"`
  - `dataset_name` from namespace portion of `destination_table`
- Validate source_config against source-specific requirements
- Raise `ValidationError` on invalid config
- Raise `SourceConnectionError` when source unreachable
- OTel span: `floe.ingestion.create_pipeline`
- Requirements: FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-058

**T010: Implement get_destination_config()**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Accept catalog config dict, return dlt Iceberg destination configuration
- Map catalog config to dlt destination params:
  - `catalog_type: "rest"`
  - `credentials.uri` from catalog_config
  - `credentials.warehouse` from catalog_config
- Support MinIO/S3 storage configuration
- OTel span: `floe.ingestion.get_destination_config`
- Requirements: FR-019, FR-020

**T011: Implement run()**
- File: `plugins/floe-ingestion-dlt/src/floe_ingestion_dlt/plugin.py`
- Execute dlt pipeline, return `IngestionResult`
- Support 3 write dispositions: append, replace, merge
- Apply schema contract from config
- Handle incremental loading via dlt's cursor mechanism
- Populate result metrics: `rows_loaded`, `bytes_written`, `duration_seconds`
- Handle empty source data (0 rows = success)
- On failure: populate `errors` list, set `success=False`
- Ensure ACID via Iceberg snapshot isolation
- OTel span: `floe.ingestion.run` with result attributes
- Structured logging: pipeline_id, source_type, execution status
- Requirements: FR-021 to FR-030, FR-031 to FR-037, FR-038 to FR-043, FR-048, FR-049, FR-050, FR-057

### Phase 2: Orchestrator Wiring

This phase wires the ingestion plugin into the Dagster orchestrator, following the Epic 4E semantic layer pattern.

**T012: Create ingestion resource factory**
- File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/resources/ingestion.py` (NEW)
- Function: `create_ingestion_resources(ingestion_ref: PluginRef) -> dict[str, Any]`
  - Load ingestion plugin via `get_registry().get(PluginType.INGESTION, ingestion_ref.type)`
  - Configure plugin from `PluginRef.config`
  - Return `{"dlt": configured_plugin_instance}`
- Function: `try_create_ingestion_resources(plugins: ResolvedPlugins | None) -> dict[str, Any]`
  - Return `{}` if `plugins` is None or `plugins.ingestion` is None
  - Delegate to `create_ingestion_resources()`
  - Re-raise exceptions (don't swallow)
- Follow exact pattern from `resources/semantic.py`
- Requirements: FR-059, FR-062, FR-063

**T013: Create ingestion asset factory and DagsterDltTranslator**
- File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/assets/ingestion.py` (NEW)
- Class: `FloeIngestionTranslator(DagsterDltTranslator)`
  - Override `get_asset_spec()` to produce `ingestion__{source_name}__{resource_name}` naming
  - Include metadata: source_type, destination_table, write_mode
- Function: `create_ingestion_assets(artifacts: CompiledArtifacts, dlt_plugin: IngestionPlugin) -> list[AssetsDefinition]`
  - For each source in ingestion config: create `@dlt_assets`-decorated function
  - Each dlt resource becomes a separate Dagster asset
  - Wire DagsterDltResource and FloeIngestionTranslator
  - OTel span: `floe.orchestrator.ingestion`
- Requirements: FR-060, FR-061, FR-064, FR-065, FR-066

**T014: Wire ingestion resources into create_definitions()**
- File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py` (MODIFY)
- Add `_create_ingestion_resources()` method (delegates to `try_create_ingestion_resources()`)
- In `create_definitions()`:
  - Call `_create_ingestion_resources(validated.plugins)`
  - Merge returned dict into resources
  - If "dlt" resource present, call `create_ingestion_assets()` and extend assets list
  - Log `has_ingestion` in Definitions summary
- Requirements: FR-059, FR-063

**T015: Update orchestrator plugin dependencies**
- File: `plugins/floe-orchestrator-dagster/pyproject.toml` (MODIFY)
- Add `dagster-dlt>=0.25.0` to dependencies
- Requirements: FR-059

### Phase 3: Testing & Quality

This phase creates all test infrastructure and test files.

**T016: Create test fixtures for dlt plugin**
- File: `testing/fixtures/ingestion.py`
- Fixtures (follow pattern from `testing/fixtures/semantic.py`):
  - `dlt_config() -> DltIngestionConfig` (session-scoped, from env vars or defaults)
  - `dlt_plugin(dlt_config) -> DltIngestionPlugin` (function-scoped, with startup/shutdown lifecycle)
  - `sample_ingestion_source_config() -> IngestionSourceConfig` (valid REST API source config)
  - `mock_dlt_source()` (mock source for unit testing without external dependencies)
- Requirements: FR-074, FR-075, FR-076, FR-077

**T017: Create unit tests for DltIngestionConfig**
- File: `plugins/floe-ingestion-dlt/tests/unit/test_config.py`
- Tests:
  - Valid config creation with all fields
  - Config is frozen (immutable) and rejects extra fields
  - `source_type` validation (only allowed values)
  - `write_mode` validation (only allowed values)
  - `schema_contract` validation (only allowed values)
  - `RetryConfig` defaults and validation
  - `SecretStr` fields not exposed in string representation
  - Edge cases: empty sources list, missing required fields
- Requirements: FR-006, FR-067-FR-073

**T018: Create unit tests for DltIngestionPlugin**
- File: `plugins/floe-ingestion-dlt/tests/unit/test_plugin.py`
- Tests:
  - Plugin inherits from IngestionPlugin
  - Metadata properties (name, version, floe_api_version, description)
  - `is_external` returns False
  - `get_config_schema()` returns DltIngestionConfig
  - `create_pipeline()` with valid config returns pipeline object (mocked dlt)
  - `create_pipeline()` with invalid config raises ValidationError
  - `run()` returns IngestionResult with correct metrics (mocked dlt)
  - `run()` handles empty source data (0 rows)
  - `run()` handles pipeline failure (mocked error)
  - `get_destination_config()` with Polaris catalog config returns correct dict
  - `health_check()` with mocked dlt (healthy, unhealthy)
  - `startup()` and `shutdown()` lifecycle
  - OTel spans emitted for all operations (traced test)
- Requirements: FR-001-FR-010, FR-044-FR-050

**T019: Create unit tests for error types and retry logic**
- File: `plugins/floe-ingestion-dlt/tests/unit/test_errors.py`
- File: `plugins/floe-ingestion-dlt/tests/unit/test_retry.py`
- Error tests:
  - Each error inherits from IngestionError
  - Errors carry context (source_type, destination_table, pipeline_name)
  - Error categorization returns correct ErrorCategory
- Retry tests:
  - TRANSIENT errors are retried up to max_retries
  - PERMANENT errors fail immediately without retry
  - Exponential backoff timing is correct
  - create_retry_decorator respects RetryConfig
- Requirements: FR-051-FR-058

**T020: Create contract tests**
- File: `tests/contract/test_ingestion_plugin_abc.py`
  - `IngestionPlugin` cannot be instantiated directly (TypeError)
  - ABC has exactly 3 abstract methods + 1 abstract property
  - Abstract methods have correct signatures (inspect.signature)
  - Type hints are complete (get_type_hints)
  - ABC inherits from PluginMetadata
- File: `tests/contract/test_core_to_ingestion_contract.py`
  - `CompiledArtifacts.plugins.ingestion` accepts `PluginRef` with type="dlt"
  - Serialize -> deserialize preserves all fields (round-trip)
  - None value serializes correctly
  - PluginRef config dict with dlt-specific fields round-trips
- Requirements: SC-008

**T021: Create integration tests for plugin discovery**
- File: `plugins/floe-ingestion-dlt/tests/integration/test_discovery.py`
- Inherits `BasePluginDiscoveryTests`:
  - `entry_point_group = "floe.ingestion"`
  - `expected_name = "dlt"`
  - `expected_module_prefix = "floe_ingestion_dlt"`
  - `expected_class_name = "DltIngestionPlugin"`
  - `expected_plugin_abc = IngestionPlugin`
- Implement `create_plugin_instance()` method
- Requirements: SC-001, SC-003, FR-079

**T022: Create integration tests for health check**
- File: `plugins/floe-ingestion-dlt/tests/integration/test_health_check.py`
- Inherits `BaseHealthCheckTests`
- Requires `unconnected_plugin` fixture (plugin not yet started)
- Requires `connected_plugin` fixture (plugin with dlt configured)
- Requirements: SC-002, FR-079

**T023: Create integration tests for pipeline execution**
- File: `plugins/floe-ingestion-dlt/tests/integration/test_pipeline.py`
- Tests with real Polaris catalog and MinIO:
  - Create pipeline from REST API source config
  - Run pipeline with append mode — data lands in Iceberg
  - Run pipeline with replace mode — data replaces
  - Run pipeline with merge mode — upsert behavior
  - Schema contract evolve — new column added
  - Schema contract freeze — error on schema change
  - Incremental loading — only new records on second run
  - Error handling — source connection failure
- Requirements: SC-004, SC-005, SC-006, SC-007, FR-078

**T024: Create unit tests for orchestrator wiring**
- File: `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_resources.py` (NEW)
- Tests:
  - `try_create_ingestion_resources()` with valid PluginRef returns dict with "dlt" key
  - `try_create_ingestion_resources()` with None plugins returns empty dict
  - `try_create_ingestion_resources()` with None ingestion returns empty dict
  - Resources correctly merged in `create_definitions()` alongside Iceberg and semantic
- File: `plugins/floe-orchestrator-dagster/tests/unit/test_ingestion_translator.py` (NEW)
- Tests:
  - `FloeIngestionTranslator` produces correct asset keys
  - Naming convention: `ingestion__{source}__{resource}`
  - Asset metadata includes source_type, destination_table
- Requirements: FR-059-FR-066

**T025: Create integration test for orchestrator wiring chain**
- File: `plugins/floe-orchestrator-dagster/tests/integration/test_ingestion_wiring.py` (NEW)
- Tests:
  - Full chain: CompiledArtifacts with `plugins.ingestion` configured → orchestrator loads plugin → resource available in Definitions
  - Definitions includes "dlt" resource when ingestion configured
  - Definitions works without ingestion (graceful degradation)
- Inherits `IntegrationTestBase`
- Requirements: FR-059, FR-063

### Phase 4: Quality Gates

**T026: Static analysis verification**
- Run `mypy --strict plugins/floe-ingestion-dlt/src/` — must pass
- Run `ruff check plugins/floe-ingestion-dlt/` — must pass
- Run `bandit -r plugins/floe-ingestion-dlt/src/` — must pass (no security issues)
- Requirements: SC-010

**T027: Coverage verification**
- Run `pytest plugins/floe-ingestion-dlt/tests/unit/ --cov=floe_ingestion_dlt --cov-report=term-missing`
- Unit test coverage must exceed 80% for `plugins/floe-ingestion-dlt/`
- Requirements: SC-009

**T028: Test conftest files and package wiring**
- File: `plugins/floe-ingestion-dlt/tests/conftest.py` (package root conftest)
- File: `plugins/floe-ingestion-dlt/tests/unit/conftest.py` (unit test conftest with fixtures)
- File: `plugins/floe-ingestion-dlt/tests/integration/conftest.py` (integration conftest)
- Verify `uv pip install -e plugins/floe-ingestion-dlt` succeeds
- Verify `pytest plugins/floe-ingestion-dlt/tests/unit/` passes

## Task Dependency Graph

```
T001 (package scaffold)
  └─> T002 (config) ─> T006 (plugin skeleton)
  └─> T003 (errors) ─> T005 (retry)
  └─> T004 (tracing) ─> T006

T006 (plugin skeleton)
  └─> T007 (lifecycle) ─> T008 (health check)
  └─> T009 (create_pipeline)
  └─> T010 (get_destination_config)
  └─> T011 (run) — depends on T009, T010

T012 (resource factory) depends on T006
T013 (asset factory + translator) depends on T012
T014 (wire into create_definitions) depends on T012
T015 (update deps) — independent

T016 (test fixtures) depends on T006
T017..T019 (unit tests) depend on their implementation tasks
T020 (contract tests) — depends on T001 only (ABC is unchanged)
T021..T022 (integration discovery/health) depend on T016 + T006
T023 (integration pipeline) depends on T016 + T011
T024 (orchestrator unit tests) depends on T012 + T013 + T014
T025 (orchestrator integration) depends on T012 + T014
T026..T027 (quality gates) depend on all previous tasks
T028 (conftest wiring) depends on T001 + T016
```

## Complexity Tracking

No constitution violations. All checkboxes passed. No complexity justification needed.

## Implementation Task Breakdown

For implementation-level task breakdown and granular work items, see `tasks.md`.
That document decomposes these 28 high-level deliverables into 52+ user story-based tasks,
enabling parallel development and faster iteration cycles.

See `tasks.md` header sections "Relationship to plan.md" and "Testing Standards and Requirements"
for reconciliation mapping and quality guidelines.
