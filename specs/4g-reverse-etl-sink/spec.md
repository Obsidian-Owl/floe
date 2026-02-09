# Feature Specification: Reverse ETL (SinkConnector)

**Epic**: 4G (Reverse ETL - SinkConnector)
**Feature Branch**: `4g-reverse-etl-sink`
**Created**: 2026-02-10
**Status**: Draft
**Input**: User description: "Epic 4G: Reverse ETL (SinkConnector) - Add SinkConnector mixin ABC for reverse ETL capabilities, enabling plugins to push curated data from the Iceberg Gold layer to external SaaS APIs and databases via dlt destination decorator"

---

## Scope

### What This Feature Does

Reverse ETL is the inverse of data ingestion: it pushes curated data FROM the lakehouse (Iceberg Gold layer) TO external operational systems (SaaS APIs, databases, services). This feature adds the `SinkConnector` mixin ABC to the plugin system and provides a default implementation using dlt's `@dlt.destination` decorator.

**Key architectural decision** (made during Epic 4F research, Option C scored 8.2/10): SinkConnector is an **opt-in ABC mixin**, not a new plugin type. Plugins that support both ingestion and egress implement `IngestionPlugin + SinkConnector`. This requires zero breaking changes to existing code, schemas, or the 12 plugin type count.

### Integration Points

**Entry Point**: No new entry point. The existing `floe.ingestion` entry point serves both directions. Runtime capability detection via `isinstance(plugin, SinkConnector)` determines egress support.

**Dependencies**:
- `floe-core`: `PluginMetadata` ABC, `IngestionPlugin` ABC, `IngestionConfig`/`IngestionResult` dataclasses (Epic 4F)
- `floe-core/plugins/__init__.py`: Must export new `SinkConnector`, `SinkConfig`, `EgressResult`
- `floe-core/schemas/floe_spec.py`: Must accept optional `destinations:` configuration
- Plugin Registry (Epic 1): Discovery mechanism for ingestion plugins
- Polaris Catalog (Epic 4C): Reads Iceberg Gold tables as egress source
- Iceberg Storage (Epic 4D): Provides data files for egress

**Produces**:
- `SinkConnector` ABC mixin (new, added to `floe-core/plugins/sink.py`)
- `SinkConfig` dataclass (new, in `floe-core/plugins/sink.py`)
- `EgressResult` dataclass (new, in `floe-core/plugins/sink.py`)
- `DltIngestionPlugin` gains `SinkConnector` capability (modified, in `floe-ingestion-dlt`)
- Optional `destinations:` schema section in `FloeSpec` (additive change)
- Used by: Orchestrator plugins (Dagster) to schedule egress jobs

### Out of Scope

- **New plugin type** -- SinkConnector is a mixin, not a 13th plugin type
- **CompiledArtifacts breaking changes** -- egress configuration is additive only
- **Streaming/CDC egress** -- future `StreamConnector`/`CDCConnector` mixins
- **Airbyte sink support** -- only dlt implementation in this epic
- **Orchestration scheduling of egress** -- managed by Epic 4B (Orchestrator Plugin)
- **Pull/staging delivery model** -- only push (active write to destination) is in scope
- **PII-aware egress gates** -- PII classification checks on egress are deferred to governance epics (3A-D)

---

## User Scenarios & Testing

### User Story 1 -- SinkConnector ABC Definition (Priority: P0)

A plugin developer needs a clear, well-defined interface for reverse ETL capabilities. The SinkConnector mixin allows any IngestionPlugin to optionally declare egress support without requiring a separate plugin type or entry point.

**Why this priority**: Foundation for all reverse ETL work. Without the ABC, no implementation can proceed.

**Independent Test**: Can be fully tested by creating a mock class implementing `SinkConnector`, verifying all abstract methods are enforced, and confirming `isinstance()` capability detection works. Delivers value as a contract that third-party plugin developers can code against.

**Acceptance Scenarios**:

1. **Given** the `SinkConnector` ABC is defined in `floe-core`, **When** a class inherits from both `IngestionPlugin` and `SinkConnector`, **Then** it must implement all 4 abstract methods (`list_available_sinks`, `create_sink`, `write`, `get_source_config`) or raise `TypeError`.
2. **Given** a plugin implementing `IngestionPlugin` only, **When** `isinstance(plugin, SinkConnector)` is checked, **Then** it returns `False`.
3. **Given** a plugin implementing both `IngestionPlugin` and `SinkConnector`, **When** `isinstance(plugin, SinkConnector)` is checked, **Then** it returns `True`.
4. **Given** `SinkConfig` and `EgressResult` dataclasses are defined, **When** they are instantiated with valid data, **Then** they validate correctly and are importable from `floe_core.plugins`.

---

### User Story 2 -- dlt Reverse ETL Implementation (Priority: P0)

A data engineer wants to push curated data from the Iceberg Gold layer to external SaaS APIs and databases using dlt's `@dlt.destination` decorator. The DltIngestionPlugin gains SinkConnector capability, making it a bidirectional data movement plugin.

**Why this priority**: Core feature delivery. Without the dlt implementation, SinkConnector is an abstract interface with no concrete value.

**Independent Test**: Can be tested by configuring a dlt sink to write to a mock HTTP endpoint, executing a write operation with sample data, and verifying the data arrives correctly with proper OTel tracing spans.

**Acceptance Scenarios**:

1. **Given** `DltIngestionPlugin` implements `SinkConnector`, **When** `list_available_sinks()` is called, **Then** it returns a list of available dlt destination types (e.g., `["rest_api", "sql_database"]`).
2. **Given** a valid `SinkConfig` with destination type and connection details, **When** `create_sink(config)` is called, **Then** it returns a configured dlt destination pipeline ready for writing.
3. **Given** a configured sink and an Arrow table of Gold layer data, **When** `write(sink, data)` is called, **Then** it pushes data to the external destination and returns an `EgressResult` with rows_delivered, bytes_transmitted, checksum, delivery_timestamp, idempotency_key, and destination_record_ids.
4. **Given** the external destination is temporarily unavailable, **When** `write()` is called, **Then** it retries according to the configured retry policy and raises a descriptive error after exhausting retries.
5. **Given** OTel tracing is enabled, **When** any SinkConnector method executes, **Then** it produces spans with egress-specific attributes (sink_type, destination, rows_written, duration_ms).

---

### User Story 3 -- Egress Configuration in floe.yaml (Priority: P1)

A data engineer wants to define reverse ETL destinations alongside ingestion sources in `floe.yaml`, so that the complete data flow (ingest + egress) is declared in a single configuration file.

**Why this priority**: Important for user experience but not blocking core functionality. Sinks can be invoked programmatically without floe.yaml config.

**Independent Test**: Can be tested by writing a `floe.yaml` with a `destinations:` section, loading it via `FloeSpec`, and verifying the schema validates correctly.

**Acceptance Scenarios**:

1. **Given** a `floe.yaml` with a top-level `destinations:` list, **When** the file is loaded as `FloeSpec`, **Then** each destination validates with required fields: `name`, `sink_type`, `connection_secret_ref` (K8s Secret name), and optional `source_table`, `config`, `field_mapping`, and `batch_size`.
2. **Given** a `floe.yaml` without a `destinations:` section, **When** the file is loaded, **Then** it validates successfully (backwards compatible, fully optional).
3. **Given** a destination config with an invalid `sink_type`, **When** validation runs, **Then** it raises a `ValidationError` with a clear message identifying the invalid sink type.

---

### User Story 4 -- Egress Governance via Manifest Whitelist (Priority: P1)

A platform engineer wants to control which external destinations data engineers are allowed to push data to, ensuring that sensitive data only flows to approved systems.

**Why this priority**: Essential for production readiness but not blocking the ABC/implementation work. Governance can be layered on after the core push mechanism works.

**Independent Test**: Can be tested by defining an `approved_sinks` whitelist in a manifest fixture, then verifying the compiler rejects destinations not on the whitelist and accepts those that are.

**Acceptance Scenarios**:

1. **Given** a `manifest.yaml` with `approved_sinks: ["salesforce", "postgres"]`, **When** a `floe.yaml` defines a destination with `sink_type: hubspot`, **Then** compilation raises a `SinkWhitelistError` naming the disallowed sink type.
2. **Given** a `manifest.yaml` with `approved_sinks: ["salesforce", "postgres"]`, **When** a `floe.yaml` defines a destination with `sink_type: salesforce`, **Then** compilation succeeds.
3. **Given** a `manifest.yaml` without an `approved_sinks` field, **When** a `floe.yaml` defines any destination, **Then** compilation succeeds (no whitelist means all sinks allowed -- backwards compatible).
4. **Given** a destination config in `floe.yaml` with hardcoded credentials instead of `connection_secret_ref`, **When** validation runs, **Then** it rejects the config with a clear error requiring K8s Secret references.

---

### Edge Cases

- What happens when a plugin implements `SinkConnector` but NOT `IngestionPlugin`? The mixin should work independently (no forced inheritance from IngestionPlugin).
- What happens when `write()` is called with an empty dataset? It should succeed with `EgressResult(rows_written=0)` and not error.
- What happens when `write()` encounters rate limiting from the SaaS API? The implementation should respect rate limits via configurable backoff. Retry attempts are recorded in OTel span attributes and structured error messages, not as a dedicated EgressResult field.
- What happens when the Iceberg source table does not exist? `get_source_config()` should raise a descriptive error rather than returning invalid config.
- What happens when `create_sink()` receives invalid connection credentials? It should fail fast at creation time with a clear authentication error, not at write time.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST define a `SinkConnector` ABC mixin in `floe-core` with four abstract methods: `list_available_sinks()`, `create_sink(config)`, `write(sink, data: pyarrow.Table, **kwargs)`, and `get_source_config(catalog_config)`.
- **FR-002**: System MUST define a `SinkConfig` dataclass in `floe-core` with fields for sink type, connection configuration, optional field mapping, optional retry configuration, and optional batch size (`batch_size: int | None`, default None meaning write all rows at once).
- **FR-003**: System MUST define an `EgressResult` dataclass in `floe-core` with rich delivery receipt fields: rows_delivered (int), bytes_transmitted (int), duration_seconds (float), success (bool), checksum (SHA-256 of payload), delivery_timestamp (datetime), idempotency_key (str for duplicate detection on retry), destination_record_ids (list of IDs returned by destination API), and errors (list of error messages).
- **FR-004**: System MUST support runtime capability detection via `isinstance(plugin, SinkConnector)` to determine if a plugin supports reverse ETL.
- **FR-005**: `DltIngestionPlugin` MUST implement the `SinkConnector` mixin, gaining bidirectional data movement capability without altering its existing ingestion behaviour.
- **FR-006**: `DltIngestionPlugin.list_available_sinks()` MUST return sink types supported by the dlt framework (at minimum: REST API and SQL database destinations).
- **FR-007**: `DltIngestionPlugin.create_sink(config)` MUST create a configured dlt destination using `@dlt.destination` or equivalent dlt API, validated against `SinkConfig`.
- **FR-008**: `DltIngestionPlugin.write(sink, data: pyarrow.Table)` MUST write the Arrow table to the configured destination, auto-chunking into batches when `SinkConfig.batch_size` is set, handle rate limiting via configurable backoff, and return an `EgressResult` with accurate metrics.
- **FR-009**: `DltIngestionPlugin.get_source_config(catalog_config)` MUST return configuration for reading from the Iceberg Gold layer via the Polaris catalog (inverse of `get_destination_config()`).
- **FR-010**: All `SinkConnector` operations MUST emit OpenTelemetry spans with egress-specific attributes: `sink.type`, `sink.destination`, `sink.rows_written`, `sink.duration_ms`, and `sink.status`.
- **FR-011**: System MUST support an optional `destinations:` top-level field on `FloeSpec` in `floe.yaml` with Pydantic validation for destination name, sink type, connection secret reference, and optional source table reference.
- **FR-012**: The `destinations:` schema MUST be fully optional -- existing `floe.yaml` files without it MUST continue to validate without changes (backwards compatible).
- **FR-013**: Write failures MUST produce structured errors with the destination name, sink type, HTTP status (if applicable), and retry attempt count for diagnosability.
- **FR-014**: `SinkConfig` MUST support field mapping configuration to translate Iceberg column names to destination-specific field names.
- **FR-015**: `SinkConnector` ABC MUST be independently implementable -- it MUST NOT require inheritance from `IngestionPlugin` (the mixin must work standalone for future use cases).
- **FR-016**: The delivery model MUST be push-only -- `write()` actively pushes data to destination APIs/databases. No staging-area/pull model is required in this epic.
- **FR-017**: Platform engineers MUST be able to define an `approved_sinks` whitelist in `manifest.yaml` that restricts which sink types data engineers can target in `floe.yaml`. The compiler MUST validate `destinations[].sink_type` against this whitelist and raise a clear error if an unapproved sink is used.
- **FR-018**: `SinkConfig.connection` MUST reference credentials via `connection_secret_ref` (K8s Secret name), consistent with the existing `PluginSelection` pattern. Hardcoded credentials in `floe.yaml` MUST be rejected by validation.

### Key Entities

- **SinkConnector**: ABC mixin interface for reverse ETL capabilities. Defines the contract for egress operations. Four abstract methods: list sinks, create sink, write data, get source config.
- **SinkConfig**: Runtime configuration model for a single egress destination. Contains sink_type (string identifier), connection_config (dict), field mapping (optional dict of source-to-destination column names), retry policy (optional, reuses existing RetryConfig), and batch size (optional int, controls auto-chunking of large datasets).
- **EgressResult**: Rich delivery receipt for an egress operation. Contains rows_delivered (int), bytes_transmitted (int), duration_seconds (float), success (bool), checksum (SHA-256 of delivered payload), delivery_timestamp (datetime), idempotency_key (str for retry deduplication), destination_record_ids (list of IDs returned by destination API), and errors (list of error messages). Mirrors `IngestionResult` symmetry with additional load-assurance fields.
- **Destination (DestinationConfig)**: A configured external system in `floe.yaml` under `destinations:`. Has a name, sink_type, connection_secret_ref (K8s Secret name), and optional source_table, config, field_mapping, and batch_size.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A plugin developer can define a new SinkConnector implementation in under 30 minutes by following the ABC contract and example code.
- **SC-002**: Data engineers can push Gold layer data to an external REST API endpoint with fewer than 10 lines of sink configuration in `floe.yaml`.
- **SC-003**: All egress operations produce OTel spans with latency, row count, and status -- enabling end-to-end observability from ingestion through egress.
- **SC-004**: Existing ingestion-only plugins and `floe.yaml` files continue to work with zero modifications after SinkConnector is added (full backwards compatibility).
- **SC-005**: Unit test coverage for SinkConnector ABC and dlt implementation exceeds 80%.
- **SC-006**: Contract tests validate that the SinkConnector interface is stable and implementable by third-party plugins.
- **SC-007**: Write operations to a mock endpoint complete within 5 seconds for datasets of 1000 rows or fewer.

---

## Clarifications

- Q: What data format should `write(sink, data)` accept as its `data` parameter? A: PyArrow Table. Matches Iceberg's native format (PyIceberg returns Arrow), zero-copy columnar, well-typed. dlt supports Arrow natively.
- Q: Should `write()` support batch size limits for large datasets? A: Yes, configurable batch size in SinkConfig. Add optional `batch_size: int | None` field. `write()` auto-chunks the Arrow table to handle SaaS API row limits and memory constraints.
- Q: What load assurance metadata should EgressResult provide? A: Rich delivery receipt -- includes rows_delivered, bytes_transmitted, checksum (SHA-256), delivery_timestamp, idempotency_key, destination_record_ids, and errors. Mirrors IngestionResult symmetry with destination-specific confirmation.
- Q: Push, pull, or both for delivery model? A: Push only. `write()` actively pushes data to destination APIs/databases. Matches dlt's `@dlt.destination` pattern and industry standard (Census, Hightouch, Fivetran all push).
- Q: How should platform engineers govern egress destinations? A: Manifest whitelist. Platform team defines `approved_sinks` in `manifest.yaml` (same pattern as `approved_plugins`). Compiler validates `sink_type` against whitelist. Credentials via `connection_secret_ref` only.

---

## Assumptions

- Epic 4F (IngestionPlugin + DltIngestionPlugin) is complete and the `IngestionPlugin` ABC is stable.
- dlt >= 1.20.0 supports `@dlt.destination` decorator or equivalent API for custom destinations.
- The Polaris catalog (Epic 4C) can provide read access to Iceberg Gold layer tables.
- Rate limiting for SaaS APIs is handled via dlt's built-in mechanisms plus configurable retry policies.
- The `destinations:` section in `floe.yaml` is NOT compiled into `CompiledArtifacts` in this epic -- that integration is deferred to orchestrator wiring (Epic 4B or future work).
