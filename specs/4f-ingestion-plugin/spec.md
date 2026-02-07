# Feature Specification: Ingestion Plugin (dlt)

**Epic**: 4F (Ingestion Plugin)
**Feature Branch**: `4f-ingestion-plugin`
**Created**: 2026-02-07
**Status**: Draft
**Input**: User description: "Create the dlt ingestion plugin that implements the existing IngestionPlugin ABC from floe-core. Uses dlt (data load tool) v1.21.0 as the concrete implementation for data ingestion pipelines."

## Clarifications

### Session 2026-02-07

- Q: Which data sources to prioritize for initial implementation? A: REST API (generic, declarative), SQL Database (via SQLAlchemy), and Filesystem (S3/GCS/Azure). REST API covers the widest range of SaaS integrations via dlt's declarative REST API source.
- Q: Default write_mode for ingestion pipelines? A: `append` (safest default; prevents accidental data loss). Users can override to `replace` or `merge` per-source in floe.yaml.
- Q: Should incremental loading state be dlt-managed or floe-managed? A: dlt-managed. dlt has battle-tested cursor state management. Floe delegates state to dlt and reads metrics from IngestionResult.
- Q: Credential management approach? A: K8s Secrets via existing platform patterns (environment variables). dlt reads credentials from environment variables (highest priority in dlt's config hierarchy). No custom SecretsPlugin wiring needed.
- Q: CLI for ad-hoc ingestion runs? A: Deferred. Not in 4F scope. Ingestion runs are orchestrated via the configured orchestrator plugin.
- Q: SinkConnector (reverse ETL) scope? A: Deferred to Epic 4G. The architectural decision (SinkConnector mixin) is documented but implementation is out of scope.
- Q: Should the plugin handle dlt source installation? A: No. dlt sources are Python packages installed as dependencies of the user's project. The plugin assumes sources are importable at runtime.
- Q: How should the plugin handle multiple ingestion sources in a single pipeline? A: Each source defined in floe.yaml becomes a separate orchestrator execution unit (one per dlt resource). The orchestrator plugin maps these to its native construct (e.g., Dagster assets, Airflow tasks).

### Session 2026-02-07 (Clarification Round 2 — Orchestrator Abstraction)

- Q: Should `dagster/` subdirectory with DagsterDltTranslator and asset factory live inside floe-ingestion-dlt or in floe-orchestrator-dagster? A: Move ALL Dagster-specific code to `plugins/floe-orchestrator-dagster/`. The ingestion plugin MUST have zero Dagster dependencies, matching the Epic 4E pattern where Cube plugin is orchestrator-agnostic and all Dagster wiring lives in the orchestrator plugin.
- Q: Should FR-059 to FR-066, User Story 4, and User Story 8 Scenario 4 use orchestrator-agnostic language? A: Yes. Rewrite using generic terms (orchestrator execution unit, orchestrator scheduling, retry mechanism). Dagster specifics belong in the orchestrator wiring section as implementation notes. This matches the 4E clarification that explicitly rejected coupling Dagster into the semantic layer ABC.
- Q: Should Data Flow diagrams and architectural references use orchestrator-agnostic language? A: Yes. Data flow uses "Orchestrator (one execution unit per dlt resource)". Dagster-specific mapping documented only in the Orchestrator Wiring section.
- Q: Are there other tight-coupling concerns beyond Dagster? A: No. dlt-managed state and env var credentials are correct technology ownership (dlt owns its state, K8s owns secrets). Only orchestrator coupling needed fixing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin Discovery and ABC Compliance (Priority: P0)

A plugin developer needs the dlt ingestion plugin to be discoverable by the floe platform and to fully implement the IngestionPlugin ABC. The plugin must register via entry points, provide correct metadata, and pass all plugin compliance tests.

**Why this priority**: Plugin discovery is the foundation. Without it, the platform cannot load the ingestion plugin, and no other functionality works.

**Independent Test**: Can be fully tested by checking `issubclass(DltIngestionPlugin, IngestionPlugin)`, verifying entry point registration, and running `BasePluginDiscoveryTests`.

**Acceptance Scenarios**:

1. **Given** the `DltIngestionPlugin` class, **When** checked against `IngestionPlugin` ABC, **Then** `issubclass(DltIngestionPlugin, IngestionPlugin)` returns True
2. **Given** the plugin is registered in pyproject.toml under `floe.ingestion`, **When** `PluginDiscovery.discover_all()` runs, **Then** the plugin appears under `PluginType.INGESTION` with name "dlt"
3. **Given** the `PluginLoader`, **When** `loader.get(PluginType.INGESTION, "dlt")` is called, **Then** a valid `DltIngestionPlugin` instance is returned with `name="dlt"`, `version="0.1.0"`, `floe_api_version="1.0"`
4. **Given** the `DltIngestionPlugin` instance, **When** `is_external` is queried, **Then** it returns `False` (dlt runs in-process, not as an external service)

---

### User Story 2 - Create and Run Ingestion Pipeline (Priority: P0)

A data engineer configures an ingestion source in floe.yaml and expects the plugin to create a dlt pipeline, execute it, and return structured results. This is the core ingestion workflow.

**Why this priority**: Pipeline creation and execution is the primary value proposition of the ingestion plugin. Without it, no data can be ingested.

**Independent Test**: Can be fully tested by creating an `IngestionConfig` with a known source type, calling `create_pipeline()` and `run()`, and verifying `IngestionResult` contains expected metrics.

**Acceptance Scenarios**:

1. **Given** a valid `IngestionConfig` with `source_type="rest_api"`, **When** `create_pipeline(config)` is called, **Then** a dlt pipeline object is returned configured with the correct source and Iceberg destination
2. **Given** a created pipeline, **When** `run(pipeline)` executes successfully, **Then** `IngestionResult.success` is True and `rows_loaded > 0`
3. **Given** a pipeline with `write_mode="append"`, **When** run twice, **Then** data accumulates (rows double) rather than replacing
4. **Given** a pipeline with `write_mode="merge"` and primary key, **When** run with updated records, **Then** existing records are updated and new records are inserted
5. **Given** an invalid `IngestionConfig` (empty source_type), **When** `create_pipeline()` is called, **Then** a `ValidationError` is raised with descriptive message

---

### User Story 3 - Load Data to Iceberg via Polaris (Priority: P0)

A data engineer expects ingested data to land in Iceberg tables managed by the Polaris REST catalog. The plugin must configure dlt's Iceberg destination with Polaris connection details from the platform's catalog configuration.

**Why this priority**: Iceberg via Polaris is the enforced storage format. Without destination configuration, data has nowhere to go.

**Independent Test**: Can be fully tested by calling `get_destination_config()` with Polaris catalog config and verifying the returned dict contains correct Iceberg destination parameters.

**Acceptance Scenarios**:

1. **Given** a catalog config with `uri="http://polaris:8181/api/catalog"` and `warehouse="floe_warehouse"`, **When** `get_destination_config(catalog_config)` is called, **Then** it returns a dict with `destination="iceberg"`, catalog URI, and warehouse name
2. **Given** valid destination config, **When** a pipeline runs, **Then** data is written as Parquet files to Iceberg tables registered in Polaris
3. **Given** a schema contract of `evolve`, **When** the source schema changes (new column), **Then** the Iceberg table schema evolves automatically
4. **Given** a schema contract of `freeze`, **When** the source schema changes, **Then** the pipeline raises an error (schema change rejected)

---

### User Story 4 - Orchestrator Integration (Priority: P1)

A data engineer expects each ingestion source to become a schedulable, monitorable execution unit in the orchestrator, enabling scheduling, monitoring, and lineage tracking. The orchestrator plugin provides a factory function that creates execution units from CompiledArtifacts.

**Why this priority**: Orchestrator integration enables production scheduling and observability. Without it, ingestion pipelines cannot be orchestrated.

**Independent Test**: Can be fully tested by calling the orchestrator's ingestion resource factory with mock CompiledArtifacts and verifying execution unit definitions are returned with correct metadata.

**Acceptance Scenarios**:

1. **Given** `CompiledArtifacts.plugins.ingestion` with a configured dlt plugin, **When** `try_create_ingestion_resources(plugins)` is called, **Then** orchestrator resources are returned for use in orchestrator definitions
2. **Given** ingestion sources configured in floe.yaml, **When** the orchestrator generates execution units, **Then** each dlt resource becomes a separate orchestrator execution unit with correct naming convention (`ingestion__{source_name}__{resource_name}`)
3. **Given** a running orchestrator instance with ingestion execution units, **When** units are materialized/executed, **Then** data flows from source through dlt to Iceberg tables
4. **Given** `CompiledArtifacts.plugins.ingestion` is None, **When** the orchestrator loads, **Then** no ingestion resources are created (graceful degradation)

---

### User Story 5 - Schema Contract Enforcement (Priority: P1)

A data engineer configures schema contracts (evolve, freeze, discard_value) to control how the pipeline handles source schema changes. This prevents unexpected schema drift from breaking downstream dbt models.

**Why this priority**: Schema contracts protect data quality. Without them, upstream schema changes propagate silently and break downstream transforms.

**Independent Test**: Can be fully tested by configuring different schema contracts and running pipelines with schema-changing data.

**Acceptance Scenarios**:

1. **Given** `schema_contract="evolve"` (default), **When** a new column appears in source data, **Then** the column is added to the Iceberg table schema
2. **Given** `schema_contract="freeze"`, **When** a new column appears, **Then** the pipeline raises a schema violation error
3. **Given** `schema_contract="discard_value"`, **When** a new column appears, **Then** the column's values are discarded but existing schema is preserved
4. **Given** any schema contract, **When** a column is removed from source, **Then** existing columns in Iceberg are preserved (never deleted)

---

### User Story 6 - Incremental Loading (Priority: P1)

A data engineer configures incremental loading to efficiently ingest only new or changed data, avoiding full reloads for large datasets. dlt manages cursor state automatically.

**Why this priority**: Incremental loading is essential for production pipelines with large or frequently-updated data sources.

**Independent Test**: Can be fully tested by running a pipeline twice with incrementally-changing data and verifying only new records are loaded on the second run.

**Acceptance Scenarios**:

1. **Given** a source configured with `write_mode="append"` and a cursor field (e.g., `updated_at`), **When** the pipeline runs incrementally, **Then** only records newer than the last cursor value are loaded
2. **Given** a successful incremental run, **When** `IngestionResult` is returned, **Then** `rows_loaded` reflects only the incremental records (not full table)
3. **Given** a source configured with `write_mode="merge"` and a primary key, **When** records with existing keys are re-ingested, **Then** they are upserted (update existing, insert new)
4. **Given** dlt state from a previous run, **When** the pipeline restarts, **Then** it resumes from the last cursor position without data loss or duplication

---

### User Story 7 - Observability (Priority: P2)

A platform operator monitors ingestion pipeline execution through OpenTelemetry traces, OpenLineage lineage, and structured logs. The plugin emits custom OTel spans since dlt has no native OTel support.

**Why this priority**: Observability is important for production monitoring but not required for basic ingestion functionality.

**Independent Test**: Can be fully tested by running a pipeline with OTel tracing enabled and verifying spans are created with expected attributes.

**Acceptance Scenarios**:

1. **Given** OTel tracing is enabled, **When** a pipeline executes, **Then** spans are emitted for pipeline creation, data extraction, and data loading phases
2. **Given** completed spans, **When** inspected, **Then** they contain `rows_loaded`, `bytes_written`, `duration_seconds`, `source_type`, and `destination_table` attributes
3. **Given** a failed pipeline, **When** the error span is emitted, **Then** it contains `error.type` and `error.message` attributes
4. **Given** structlog is configured, **When** a pipeline runs, **Then** structured log entries include `pipeline_id`, `source_type`, and execution status without exposing secrets

---

### User Story 8 - Error Handling with Retry (Priority: P2)

A data engineer expects transient errors (network timeouts, rate limits) to be retried automatically, while permanent errors (invalid credentials, missing resources) fail immediately with clear messages.

**Why this priority**: Robust error handling is essential for production reliability but basic ingestion works without it.

**Independent Test**: Can be fully tested by injecting transient and permanent errors and verifying retry behavior and error categorization.

**Acceptance Scenarios**:

1. **Given** a transient error (network timeout), **When** the pipeline encounters it, **Then** the operation is retried with exponential backoff (configurable max retries)
2. **Given** a permanent error (invalid credentials), **When** the pipeline encounters it, **Then** it fails immediately without retrying
3. **Given** a pipeline failure, **When** `IngestionResult` is returned, **Then** `success=False` and `errors` list contains categorized error messages
4. **Given** orchestrator-managed execution, **When** a pipeline fails with a transient error, **Then** the orchestrator's retry mechanism triggers automatic re-execution

---

### Edge Cases

- What happens when the dlt source package is not installed (ImportError)? → `startup()` raises `ImportError` with installation instructions (FR-009)
- How does the system handle an empty source (0 rows extracted)? → `run()` returns `IngestionResult(success=True, rows_loaded=0)` (FR-030)
- What happens when Polaris catalog is unreachable during pipeline creation? → `health_check()` returns UNHEALTHY; `create_pipeline()` raises `SourceConnectionError` (FR-007, FR-058)
- What happens when source credentials expire mid-pipeline? → Caught by `categorize_error()` as TRANSIENT (credential refresh may succeed); reported in `IngestionResult.errors` (FR-051, US8)
- What happens when Iceberg write fails mid-transaction (partial load)? → dlt/Iceberg rollback via snapshot isolation; plugin wraps in `DestinationWriteError` (FR-057, US8)

## Requirements *(mandatory)*

### Functional Requirements

**Plugin Foundation (FR-001 to FR-010)**

- **FR-001**: System MUST provide `DltIngestionPlugin` class implementing `IngestionPlugin` ABC with all 3 abstract methods and 1 abstract property
- **FR-002**: Plugin MUST be registered as entry point `floe.ingestion` with name "dlt" in pyproject.toml
- **FR-003**: Plugin MUST be discoverable via `PluginDiscovery.discover_all()` and `PluginLoader.get(PluginType.INGESTION, "dlt")`
- **FR-004**: Plugin MUST expose `name="dlt"`, `version="0.1.0"`, `floe_api_version="1.0"` metadata properties
- **FR-005**: Plugin MUST return `is_external=False` (dlt runs in-process)
- **FR-006**: Plugin MUST accept configuration via `DltIngestionConfig` Pydantic model with `model_config = ConfigDict(frozen=True, extra="forbid")`
- **FR-007**: Plugin MUST implement `health_check()` returning `HealthStatus` (HEALTHY when dlt is importable and destination is reachable)
- **FR-008**: Plugin MUST implement `startup()` and `shutdown()` lifecycle methods
- **FR-009**: Plugin MUST validate that required dlt source packages are importable at startup and raise `ImportError` with installation instructions if missing
- **FR-010**: Plugin MUST expose its capabilities via plugin metadata (supported source types, supported write modes, supported schema contracts)

**Pipeline Creation (FR-011 to FR-020)**

- **FR-011**: `create_pipeline()` MUST accept `IngestionConfig` and return a configured dlt pipeline object
- **FR-012**: Pipeline MUST be configured with Iceberg destination using catalog config from `get_destination_config()`
- **FR-013**: Pipeline MUST support `source_type` values: `rest_api`, `sql_database`, `filesystem` (minimum viable set)
- **FR-014**: Pipeline MUST validate `source_config` against source-specific schemas before pipeline creation
- **FR-015**: Pipeline MUST resolve source credentials from environment variables (dlt's default config hierarchy)
- **FR-016**: Pipeline MUST raise `ValidationError` if `IngestionConfig` is invalid (empty source_type, invalid write_mode)
- **FR-017**: Pipeline MUST use `pipeline_name` derived from `destination_table` for dlt state isolation
- **FR-018**: Pipeline MUST configure `dataset_name` from the Iceberg namespace portion of `destination_table`
- **FR-019**: `get_destination_config()` MUST accept catalog config dict and return dlt Iceberg destination configuration including `catalog_uri`, `catalog_type="rest"`, and `warehouse` name
- **FR-020**: `get_destination_config()` MUST support MinIO/S3 storage configuration for Iceberg file storage

**Data Loading (FR-021 to FR-030)**

- **FR-021**: `run()` MUST execute the dlt pipeline and return `IngestionResult` with `success`, `rows_loaded`, `bytes_written`, `duration_seconds`
- **FR-022**: `run()` MUST support `write_mode="append"` for additive loading
- **FR-023**: `run()` MUST support `write_mode="replace"` for full refresh loading
- **FR-024**: `run()` MUST support `write_mode="merge"` with primary key for upsert operations
- **FR-025**: Merge operations MUST support delete-insert and upsert strategies via dlt merge dispositions
- **FR-026**: `run()` MUST write data as Parquet files to Iceberg tables via Polaris REST catalog
- **FR-027**: `run()` MUST ensure ACID guarantees for writes (via Iceberg snapshot isolation)
- **FR-028**: `run()` MUST populate `IngestionResult.errors` with categorized error messages on failure
- **FR-029**: `run()` MUST record `duration_seconds` as wall-clock execution time
- **FR-030**: `run()` MUST handle empty source data gracefully (0 rows = success with `rows_loaded=0`)

**Schema Contracts (FR-031 to FR-037)**

- **FR-031**: Pipeline MUST enforce `schema_contract="evolve"` (default) allowing all schema changes
- **FR-032**: Pipeline MUST enforce `schema_contract="freeze"` rejecting any schema changes with error
- **FR-033**: Pipeline MUST enforce `schema_contract="discard_value"` dropping non-conforming column values
- **FR-034**: Schema contract MUST be configurable per-source in `IngestionConfig`
- **FR-035**: Schema contract enforcement MUST log schema changes at INFO level (evolve) or ERROR level (freeze violation)
- **FR-036**: Schema evolution MUST propagate to Iceberg table schema via dlt's automatic schema management
- **FR-037**: Columns removed from source MUST NOT be removed from Iceberg schema (additive-only evolution)

**Incremental Loading (FR-038 to FR-043)**

- **FR-038**: Pipeline MUST support cursor-based incremental loading via dlt's `dlt.sources.incremental()` mechanism
- **FR-039**: Incremental cursor state MUST be managed by dlt (not floe-managed)
- **FR-040**: Pipeline MUST support configurable cursor field via `source_config.cursor_field`
- **FR-041**: Pipeline MUST resume from last cursor position after restart (no data loss, no duplication)
- **FR-042**: Incremental state MUST be isolated per pipeline name (no state collision between sources)
- **FR-043**: `IngestionResult.rows_loaded` MUST reflect only incrementally-loaded rows (not total table size)

**Observability (FR-044 to FR-050)**

- **FR-044**: Plugin MUST emit OpenTelemetry spans for `create_pipeline`, `run`, and `get_destination_config` operations
- **FR-045**: Spans MUST include attributes: `ingestion.source_type`, `ingestion.destination_table`, `ingestion.write_mode`
- **FR-046**: Completed run spans MUST include: `ingestion.rows_loaded`, `ingestion.bytes_written`, `ingestion.duration_seconds`
- **FR-047**: Failed run spans MUST include: `error.type`, `error.message`, `error.category` (TRANSIENT|PERMANENT|PARTIAL)
- **FR-048**: Plugin MUST use structured logging via `structlog` for all operations
- **FR-049**: Plugin MUST NOT log secret values (credentials, API keys, connection strings)
- **FR-050**: Plugin MUST emit pipeline execution metrics compatible with the platform's metrics collection

**Error Handling (FR-051 to FR-058)**

- **FR-051**: Plugin MUST categorize dlt exceptions into error taxonomy using concrete criteria: TRANSIENT (HTTP 429/503, network timeout, connection reset — retryable), PERMANENT (HTTP 401/403, missing resource, permission denied — not retryable), PARTIAL (incomplete batch load — partially retryable), CONFIGURATION (HTTP 400/404, invalid config, missing source package — setup error). Categorization implemented in `categorize_error()` function.
- **FR-052**: TRANSIENT errors (network timeout, rate limit, temporary unavailability) MUST be retried with exponential backoff
- **FR-053**: PERMANENT errors (invalid credentials, missing resource, permission denied) MUST fail immediately without retry
- **FR-054**: Retry logic MUST use configurable `max_retries` (default: 3) and `initial_delay_seconds` (default: 1.0)
- **FR-055**: Plugin MUST provide custom exception hierarchy: `IngestionError`, `SourceConnectionError`, `DestinationWriteError`, `SchemaContractViolation`
- **FR-056**: All errors MUST include source context (source_type, destination_table, pipeline_name) for debugging
- **FR-057**: Pipeline MUST handle Iceberg write failures gracefully — dlt/Iceberg handle transaction rollback via snapshot isolation; the plugin MUST catch the failure, wrap it in `DestinationWriteError`, and report it in `IngestionResult.errors`. The plugin does NOT implement its own rollback logic.
- **FR-058**: Plugin MUST raise `SourceConnectionError` when source is unreachable during `create_pipeline()`

**Orchestrator Wiring (FR-059 to FR-066)**

- **FR-059**: Orchestrator plugin MUST load the ingestion plugin as an orchestrator resource via `try_create_ingestion_resources(plugins)` when `CompiledArtifacts.plugins.ingestion` is configured
- **FR-060**: Orchestrator MUST create execution unit definitions from ingestion source configuration (one execution unit per dlt resource)
- **FR-061**: Each dlt resource MUST become a separate orchestrator execution unit with naming convention `ingestion__{source_name}__{resource_name}`
- **FR-062**: Ingestion resource factory MUST follow the established wiring pattern (`try_create_iceberg_resources`, `try_create_semantic_resources`)
- **FR-063**: Orchestrator MUST gracefully degrade when `plugins.ingestion` is None (no ingestion configured)
- **FR-064**: Ingestion execution units MUST provide metadata to the orchestrator including `rows_loaded`, `source_type`, and execution duration
- **FR-065**: Ingestion execution units MUST support orchestrator scheduling (cron-based) and event-based triggering
- **FR-066**: Ingestion execution units MUST emit OpenLineage events automatically via the orchestrator's lineage integration

> **Implementation Note (Dagster)**: In the current Dagster orchestrator implementation, FR-060 maps to `@dlt_assets` definitions, FR-061 maps to Dagster assets, FR-059 returns a `DagsterDltResource`, and FR-066 uses `openlineage-dagster`. A custom `DagsterDltTranslator` handles asset naming. All Dagster-specific code lives in `plugins/floe-orchestrator-dagster/`.

**Configuration (FR-067 to FR-073)**

- **FR-067**: Plugin MUST accept configuration through `DltIngestionConfig` Pydantic model
- **FR-068**: Config MUST include `sources: list[IngestionSourceConfig]` defining data sources to ingest
- **FR-069**: Each `IngestionSourceConfig` MUST include `name`, `source_type`, `source_config`, `destination_table`, `write_mode`, `schema_contract`
- **FR-070**: Config MUST include `catalog_config: dict[str, Any]` for Polaris connection (inherited from platform config)
- **FR-071**: Config MUST include optional `retry_config: RetryConfig` with `max_retries` and `initial_delay_seconds`
- **FR-072**: Config MUST validate all fields using Pydantic v2 field validators
- **FR-073**: Config MUST use `SecretStr` for any credential fields

**Test Infrastructure (FR-074 to FR-079)**

- **FR-074**: System MUST provide `testing/fixtures/ingestion.py` with dlt-specific test fixtures
- **FR-075**: Fixtures MUST include `dlt_config` (session-scoped), `dlt_plugin` (connected instance)
- **FR-076**: Fixtures MUST integrate with existing `IntegrationTestBase` and `BasePluginDiscoveryTests`
- **FR-077**: System MUST provide a mock dlt source fixture for unit testing without external dependencies
- **FR-078**: Integration tests MUST use real Polaris catalog and MinIO/S3 storage (no mocks for integration tier)
- **FR-079**: Plugin MUST pass all `BasePluginDiscoveryTests` (11 tests) and `BaseHealthCheckTests` (11 tests)

### Key Entities

- **DltIngestionPlugin**: Concrete implementation of `IngestionPlugin` ABC for dlt. Handles pipeline creation, execution, and Iceberg destination configuration. Registered via `floe.ingestion` entry point with name "dlt". Lives in `plugins/floe-ingestion-dlt/`.

- **DltIngestionConfig**: Pydantic v2 configuration model for the dlt ingestion plugin. Includes `sources` (list of source definitions), `catalog_config` (Polaris connection), `retry_config` (retry parameters). Uses `ConfigDict(frozen=True, extra="forbid")`.

- **IngestionSourceConfig**: Pydantic v2 model defining a single ingestion source. Includes `name` (unique identifier), `source_type` (rest_api|sql_database|filesystem), `source_config` (source-specific params), `destination_table` (Iceberg table path), `write_mode` (append|replace|merge), `schema_contract` (evolve|freeze|discard_value), `cursor_field` (optional, for incremental).

- **IngestionConfig**: Existing dataclass in floe-core defining pipeline configuration. Used as the parameter for `create_pipeline()`. Not modified.

- **IngestionResult**: Existing dataclass in floe-core defining pipeline execution results. Used as the return type for `run()`. Not modified.

- **DagsterDltTranslator**: *(lives in `plugins/floe-orchestrator-dagster/`, not in the ingestion plugin)* Custom translator that maps dlt resource names to orchestrator execution unit names following floe's naming convention (`ingestion__{source}__{resource}`). Dagster-specific implementation detail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `DltIngestionPlugin` passes all `BasePluginDiscoveryTests` (11 inherited tests) confirming entry point registration and discovery
- **SC-002**: `DltIngestionPlugin` passes all `BaseHealthCheckTests` (11 inherited tests) confirming health check compliance
- **SC-003**: `test_all_plugin_types_discoverable` E2E test passes with `INGESTION` type present
- **SC-004**: Pipeline successfully loads data from a REST API source to an Iceberg table via Polaris in under 30 seconds (integration test)
- **SC-005**: All 3 write modes (append, replace, merge) produce correct results verified by Iceberg table scans
- **SC-006**: All 3 schema contracts (evolve, freeze, discard_value) behave correctly when source schema changes
- **SC-007**: Incremental loading loads only new records on subsequent runs (verified by row count comparison)
- **SC-008**: Contract test validates `CompiledArtifacts.plugins.ingestion` round-trip (serialize + deserialize preserves all fields)
- **SC-009**: Unit test coverage for `plugins/floe-ingestion-dlt/` exceeds 80%
- **SC-010**: All new code passes `mypy --strict`, `ruff`, `bandit` checks
- **SC-011**: OTel spans are emitted for pipeline creation and execution with required attributes
- **SC-012**: Error categorization correctly classifies transient vs permanent errors (verified by unit tests)

## Assumptions

- IngestionPlugin ABC already exists in `packages/floe-core/src/floe_core/plugins/ingestion.py` with 3 abstract methods and 1 abstract property (no ABC changes needed)
- CompiledArtifacts v0.5.0 already has `plugins.ingestion` field as `PluginRef | None` (no schema changes needed)
- Entry point group `floe.ingestion` is registered in `PluginType` enum with `INGESTION = "floe.ingestion"`
- Plugin registry from Epic 1 is available for plugin discovery
- Catalog plugin (Epic 4C, Polaris) is available and provides REST catalog
- Storage plugin (Epic 4D, Iceberg) provides table management and IOManager
- dlt v1.21.0+ is available with Iceberg destination support
- dagster-dlt v0.25.0+ is available with first-class Dagster integration (dependency of `plugins/floe-orchestrator-dagster/`, NOT of the ingestion plugin)
- PyIceberg v0.10.0+ is available for Iceberg table operations
- Polaris REST catalog is deployed and accessible in K8s
- MinIO/S3-compatible storage is available for Iceberg data files
- dlt manages its own incremental state (no external state store needed)
- dlt sources (rest_api, sql_database, filesystem) are importable as Python packages
- Environment variables are the primary credential delivery mechanism (K8s Secrets mounted as env vars)

## Out of Scope

- Airbyte ingestion plugin (alternative implementation - future epic)
- SinkConnector / reverse ETL (deferred to Epic 4G per architectural decision; SinkConnector mixin pattern documented in research)
- CLI for ad-hoc ingestion runs outside the orchestrator
- dlt source package management (installation, versioning)
- Custom dlt source development tooling
- Ingestion pipeline versioning or migration
- Cross-source schema unification or deduplication
- Real-time / streaming ingestion (dlt is batch-oriented)
- Partition evolution for Iceberg tables (dlt limitation)
- dlt state backup or recovery beyond dlt's built-in mechanisms
- Ingestion scheduling UI (orchestrator provides this)
- Source-specific pagination configuration beyond dlt defaults
- Multi-destination writing (single pipeline writes to one Iceberg table)
- Source API rate limiting (dlt handles rate limiting automatically for supported sources)
- Extremely large payload memory management (dlt manages chunking and memory internally)
- dlt state file corruption recovery (dlt manages its own state; beyond dlt's built-in mechanisms is out of scope)
- Duplicate record handling in append mode (deduplication is a downstream dbt concern, not ingestion)
- Concurrent pipeline execution for the same destination table (orchestrator manages concurrency via scheduling)

## Integration & Wiring

### Full Wiring Path

The complete integration chain from configuration to data landing:

```
CompiledArtifacts (floe-core)
  -> PluginRegistry.get(INGESTION, "dlt")  -> DltIngestionPlugin
  -> plugin.get_destination_config(catalog_config) -> dlt Iceberg config
  -> plugin.create_pipeline(config) -> dlt pipeline object
  -> plugin.run(pipeline) -> IngestionResult (rows_loaded, bytes_written)

Orchestrator (runtime wiring, lives in orchestrator plugin):
  -> try_create_ingestion_resources(plugins) -> orchestrator ingestion resource
  -> execution unit definitions (one per dlt resource)
     -> each dlt resource becomes an orchestrator execution unit
     -> units materialize: source -> dlt -> Iceberg via Polaris
  -> lineage integration emits OpenLineage events automatically
```

> **Dagster Implementation**: `try_create_ingestion_resources()` returns a `DagsterDltResource`. Execution units are `@dlt_assets`-decorated functions. A custom `DagsterDltTranslator` handles naming. Lineage via `openlineage-dagster`. All code lives in `plugins/floe-orchestrator-dagster/`.

### Data Flow

```
External Sources (SaaS APIs, Databases, Files)
    |
    v
floe.yaml (data engineer configures sources)
    |
    v
Compiler -> CompiledArtifacts.plugins.ingestion: PluginRef
    |
    v
Orchestrator execution units (one per dlt resource)
    |
    v
dlt pipeline (extract -> normalize -> load)
    |
    v
Iceberg tables (Bronze layer) via Polaris REST catalog
    |
    v
dbt models (Silver/Gold layers) - downstream orchestrator assets
```

### Component Boundary Summary

| Component | Package | Responsibility |
|-----------|---------|---------------|
| IngestionPlugin ABC | `packages/floe-core/` | Interface definition (3 methods + 1 property) - NO CHANGES |
| IngestionConfig | `packages/floe-core/` | Pipeline config dataclass - NO CHANGES |
| IngestionResult | `packages/floe-core/` | Execution result dataclass - NO CHANGES |
| DltIngestionPlugin | `plugins/floe-ingestion-dlt/` | dlt implementation of ABC |
| DltIngestionConfig | `plugins/floe-ingestion-dlt/` | Pydantic configuration model |
| IngestionSourceConfig | `plugins/floe-ingestion-dlt/` | Per-source configuration model |
| Error hierarchy | `plugins/floe-ingestion-dlt/` | IngestionError, SourceConnectionError, etc. |
| OTel tracing | `plugins/floe-ingestion-dlt/` | Custom span helpers (dlt has no native OTel) |
| Retry logic | `plugins/floe-ingestion-dlt/` | tenacity-based retry with error categorization |
| Orchestrator ingestion wiring | `plugins/floe-orchestrator-dagster/` | `try_create_ingestion_resources()` + asset factory + DagsterDltTranslator |
| Test fixtures | `testing/fixtures/ingestion.py` | dlt-specific test infrastructure |

### Existing Contract

`CompiledArtifacts.plugins.ingestion` is already present as `PluginRef | None` in v0.5.0. No schema changes required. The dlt plugin populates this field:

```python
PluginRef(
    type="dlt",
    version="0.1.0",
    config={
        "sources": [...],
        "catalog_config": {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse"
        }
    }
)
```

### File Ownership (Exclusive)

```text
# floe-core (NO CHANGES - existing ABC is sufficient)
packages/floe-core/src/floe_core/plugins/
  ingestion.py                     # IngestionPlugin ABC - UNCHANGED

# dlt Plugin (NEW)
plugins/floe-ingestion-dlt/
  pyproject.toml                   # Entry point: floe.ingestion
  src/floe_ingestion_dlt/
    __init__.py
    plugin.py                      # DltIngestionPlugin
    config.py                      # DltIngestionConfig, IngestionSourceConfig
    credentials.py                 # SecretStr credential handling
    models.py                      # PipelineConfig, RetryConfig
    errors.py                      # IngestionError hierarchy
    retry.py                       # tenacity retry logic + error categorization
    tracing.py                     # OTel span helpers
    py.typed                       # PEP 561 marker
  tests/
    conftest.py
    unit/
      conftest.py
      test_plugin.py
      test_config.py
      test_models.py
      test_errors.py
      test_retry.py
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
