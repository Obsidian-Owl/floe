# REQ-516 to REQ-530: OpenLineage Data Lineage

**Domain**: Observability and Lineage
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines OpenLineage integration for data lineage tracking, input/output documentation, and data product lineage visualization. OpenLineage enables understanding data dependencies, impact analysis, and compliance auditing.

**Key Principle**: OpenLineage standard for vendor-neutral data lineage (ADR-0007)

## Requirements

### REQ-516: OpenLineage Event Emission **[New]**

**Requirement**: System MUST emit OpenLineage events for all Layer 4 (job) executions including RunStart, RunEnd, and RunFail events.

**Rationale**: Enables lineage graph construction and data flow visualization.

**Acceptance Criteria**:
- [ ] RunStart event emitted when job execution begins
- [ ] RunEnd event emitted on successful job completion with output datasets
- [ ] RunFail event emitted on job failure with error details
- [ ] Events include: run_id, job (namespace, name), inputs, outputs, timestamps
- [ ] Events serialized to OpenLineage JSON-LD format
- [ ] Events emitted to OpenLineage endpoint (via HTTP or OTLP)

**Enforcement**:
- Job execution tests validate event emission
- Event schema validation (JSON-LD compliance)
- End-to-end lineage tests (events received by lineage backend)

**Constraints**:
- MUST follow OpenLineage specification (1.0+)
- MUST use standard event types (RunStart, RunEnd, RunFail)
- MUST emit events in JSON-LD serialization
- FORBIDDEN to emit proprietary lineage formats

**Test Coverage**: `tests/contract/test_openlineage.py::test_lineage_event_emission`

**Traceability**:
- ADR-0007 (OpenLineage from Start)
- OpenLineage specification (https://openlineage.io/spec/)
- four-layer-overview.md Layer 4 (Data/Jobs)

---

### REQ-517: Lineage Namespace Strategy **[New]**

**Requirement**: System MUST support three lineage namespace modes (Simple, Centralized, Data Mesh) configurable via floe.yaml.

**Rationale**: Enables scaling from single platform to federated Data Mesh with proper lineage organization.

**Acceptance Criteria**:
- [ ] Simple mode: namespace = product_name (e.g., "customer-analytics")
- [ ] Centralized mode: namespace = product_name (same as simple, for clarity)
- [ ] Data Mesh mode: namespace = domain.product_name (e.g., "sales.customer-360")
- [ ] Namespace extracted from floe.yaml product configuration
- [ ] Namespace validated during compilation (must be valid identifier format)
- [ ] Namespace included in all OpenLineage events (Job.namespace field)

**Enforcement**:
- Namespace validation tests
- floe.yaml schema validation for namespace
- Event inspection confirms namespace field populated

**Constraints**:
- MUST follow OpenLineage namespace conventions (alphanumeric + underscore/dash)
- MUST validate namespace format at compilation time
- FORBIDDEN to allow empty or invalid namespace

**Test Coverage**: `tests/contract/test_openlineage_namespace.py`

**Traceability**:
- ADR-0007 section "Lineage Namespace Strategy"
- floe.yaml schema (product configuration)

---

### REQ-518: Job Identity in Lineage **[New]**

**Requirement**: System MUST include consistent job identity (namespace, name) in lineage events for deduplication and tracking.

**Rationale**: Enables lineage backend to group related executions and track job evolution.

**Acceptance Criteria**:
- [ ] Job namespace = product namespace (from floe.yaml)
- [ ] Job name = model name (dbt) or task name (custom jobs)
- [ ] Job identity stable across multiple executions
- [ ] Job identity unique within namespace
- [ ] Job identity included in RunStart, RunEnd, RunFail events
- [ ] Job identity enables linking to dbt model documentation (dbt docs URL)

**Enforcement**:
- Job identity consistency tests (same job → same identity)
- Uniqueness tests within namespace
- Lineage backend deduplication tests

**Constraints**:
- MUST use model_name for dbt jobs (from dbt manifest)
- MUST use task_name for custom jobs (from floe.yaml)
- MUST NOT include execution timestamp in job name (stability requirement)
- FORBIDDEN to change job name between executions (breaks lineage)

**Test Coverage**: `tests/contract/test_openlineage_job_identity.py`

**Traceability**:
- OpenLineage Job specification
- floe-dbt integration (model naming)

---

### REQ-519: Input Dataset Lineage **[New]**

**Requirement**: System MUST emit input datasets in OpenLineage RunStart event with namespace, name, and source information.

**Rationale**: Enables lineage graph to show data sources and upstream dependencies.

**Acceptance Criteria**:
- [ ] Input datasets extracted from dbt sources in floe.yaml or dbt manifest
- [ ] Dataset namespace = Iceberg catalog namespace (from catalog plugin)
- [ ] Dataset name = table_name or view_name (from catalog)
- [ ] Dataset includes facets: schema (column definitions), source (source name)
- [ ] Input datasets included in RunStart event (inputs[])
- [ ] Schema facet includes column names, types, and descriptions (from dbt)

**Enforcement**:
- Input extraction tests (validate datasets from sources)
- Schema facet validation
- Lineage graph tests (upstream dependencies visible)

**Constraints**:
- MUST extract inputs from dbt source definitions (prefer dbt manifest)
- MUST include schema information (column names and types)
- MUST use Iceberg naming conventions (catalog.namespace.table)
- FORBIDDEN to emit datasets without schema information

**Test Coverage**: `tests/contract/test_openlineage_inputs.py`

**Traceability**:
- OpenLineage Dataset and SchemaFacet specification
- floe-dbt integration (source definitions)
- floe-iceberg integration (catalog naming)

---

### REQ-520: Output Dataset Lineage **[New]**

**Requirement**: System MUST emit output datasets in OpenLineage RunEnd event with namespace, name, schema, and processing timing.

**Rationale**: Enables lineage graph to show produced tables and downstream consumers.

**Acceptance Criteria**:
- [ ] Output datasets extracted from dbt models in dbt manifest
- [ ] Dataset namespace = Iceberg catalog namespace (from catalog plugin)
- [ ] Dataset name = model name (materialized as table or view)
- [ ] Dataset includes facets: schema (columns from dbt), outputStatistics (row count, size)
- [ ] Output datasets included in RunEnd event (outputs[])
- [ ] OutputStatistics includes rowCount and dataSize (from Iceberg metadata)

**Enforcement**:
- Output extraction tests (validate tables created/updated)
- Statistics facet validation (row count, size populated)
- Lineage graph tests (downstream consumers visible)

**Constraints**:
- MUST extract outputs from dbt manifest (post-execution)
- MUST query Iceberg table metadata for statistics
- MUST include schema information (column names and types)
- FORBIDDEN to emit outputs without row count

**Test Coverage**: `tests/contract/test_openlineage_outputs.py`

**Traceability**:
- OpenLineage Dataset and OutputStatisticsFacet specification
- floe-dbt integration (model definitions)
- floe-iceberg integration (table metadata)

---

### REQ-521: Lineage Correlation with Traces **[New]**

**Requirement**: System MUST include trace_id in OpenLineage events to enable correlation between lineage and observability traces.

**Rationale**: Enables navigating from lineage graph to execution traces for debugging.

**Acceptance Criteria**:
- [ ] RunStart event includes trace_id in job facets
- [ ] RunEnd event includes trace_id in job facets (same trace_id as RunStart)
- [ ] RunFail event includes trace_id in job facets
- [ ] trace_id extracted from active span context (W3C Trace Context)
- [ ] trace_id enables linking to Jaeger/Grafana traces

**Enforcement**:
- Trace ID injection tests (validate in lineage events)
- Lineage-trace linking tests (can navigate between systems)

**Constraints**:
- MUST use W3C Trace Context trace_id (32-char hex)
- MUST populate trace_id from active span before event emission
- FORBIDDEN to emit lineage events without trace_id

**Test Coverage**: `tests/contract/test_openlineage_trace_correlation.py`

**Traceability**:
- ADR-0006 (OpenTelemetry) + ADR-0007 (OpenLineage) integration
- W3C Trace Context specification

---

### REQ-522: dbt Model Lineage Integration **[New]**

**Requirement**: System MUST extract and emit lineage for dbt models including source dependencies and intermediate transformations.

**Rationale**: Enables visibility into transformation logic and upstream dependencies.

**Acceptance Criteria**:
- [ ] RunStart inputs extracted from dbt source() definitions in dbt models
- [ ] RunEnd outputs emitted as dbt models (materialized in Iceberg)
- [ ] Intermediate tables (ephemeral models) not emitted as outputs
- [ ] Model-to-model dependencies visible in lineage graph (ref() relationships)
- [ ] dbt test dependencies included (test → model lineage)
- [ ] dbt docs URLs included in job facets (for navigation)

**Enforcement**:
- dbt manifest parsing tests (extract sources, models, dependencies)
- Lineage completeness tests (all models and dependencies represented)
- E2E dbt execution lineage tests

**Constraints**:
- MUST parse dbt manifest.json for accurate lineage
- MUST NOT include ephemeral models as outputs
- MUST handle circular dependencies gracefully
- FORBIDDEN to emit lineage without dbt model metadata

**Test Coverage**: `tests/contract/test_openlineage_dbt.py`

**Traceability**:
- floe-dbt integration (manifest parsing)
- ADR-0007 section "Integration Points"

---

### REQ-523: dlt Ingestion Lineage **[New]**

**Requirement**: System MUST emit lineage for dlt ingestion jobs including source system and target tables.

**Rationale**: Enables tracking external data sources and ingestion patterns.

**Acceptance Criteria**:
- [ ] RunStart inputs include source system (API, database, file)
- [ ] RunEnd outputs include target Iceberg table
- [ ] Ingestion dataset facets include source connector type (e.g., "salesforce", "postgres")
- [ ] Lineage includes metadata about ingestion (full vs. incremental load)
- [ ] Output statistics include extracted and loaded record counts

**Enforcement**:
- dlt instrumentation tests (capture ingestion metadata)
- Lineage emission tests (valid OpenLineage format)
- E2E ingestion lineage tests

**Constraints**:
- MUST hook into dlt run lifecycle (before/after hooks)
- MUST capture source metadata from dlt configuration
- MUST query Iceberg for target table statistics
- FORBIDDEN to emit lineage without source system identification

**Test Coverage**: `tests/contract/test_openlineage_dlt.py`

**Traceability**:
- floe-ingestion plugin integration (dlt)
- ADR-0007 section "Integration Points"

---

### REQ-524: Quality Check Lineage **[New]**

**Requirement**: System MUST emit lineage for data quality check jobs including tested tables and quality metrics.

**Rationale**: Enables tracking data quality processes and results.

**Acceptance Criteria**:
- [ ] RunStart inputs include tables being tested
- [ ] RunEnd includes quality check results (passed tests, failed tests)
- [ ] Output dataset includes quality metrics as facets (null counts, duplicate counts, etc.)
- [ ] Quality check job linked to source table lineage
- [ ] Quality test names and assertions included in lineage

**Enforcement**:
- Quality check instrumentation tests
- Result emission tests (passed/failed states)
- E2E quality check lineage tests

**Constraints**:
- MUST emit lineage for all quality check jobs
- MUST include test-level pass/fail information
- MUST populate schema facet with tested columns
- FORBIDDEN to suppress failed quality checks from lineage

**Test Coverage**: `tests/contract/test_openlineage_quality.py`

**Traceability**:
- Quality enforcement plugin
- ADR-0007 section "Integration Points"

---

### REQ-525: OpenLineage HTTP Transport **[New]**

**Requirement**: System MUST emit OpenLineage events to HTTP endpoint (default: OpenLineage Marquez server or backend-specific endpoint).

**Rationale**: Enables lineage backend integration without additional services.

**Acceptance Criteria**:
- [ ] LineageEmitter class sends POST requests to OPENLINEAGE_URL endpoint
- [ ] Events sent as JSON-LD with Content-Type: application/json
- [ ] HTTP endpoint configurable via environment variable OPENLINEAGE_URL
- [ ] Default endpoint: http://localhost:5000 (Marquez) for dev
- [ ] Endpoint configurable via manifest.yaml for prod
- [ ] Retry logic on transient failures (3 retries, exponential backoff)

**Enforcement**:
- HTTP endpoint tests (mock server validation)
- Retry logic tests
- Configuration validation tests

**Constraints**:
- MUST use HTTP POST (not PUT or PATCH)
- MUST respect OPENLINEAGE_URL environment variable
- MUST include Content-Type header
- FORBIDDEN to emit lineage events synchronously (must be non-blocking or async)

**Test Coverage**: `tests/contract/test_openlineage_http_transport.py`

**Traceability**:
- OpenLineage specification (HTTP API)
- Marquez HTTP API specification

---

### REQ-526: OpenLineage HTTP Transport (Initial Implementation) **[Updated]**

**Requirement**: System MUST support emitting OpenLineage events via HTTP transport to lineage backends (Marquez, Atlan, OpenMetadata). OTLP transport is deferred to Epic 8+ pending ecosystem support.

**Rationale**: HTTP transport aligns with OpenLineage ecosystem standards. All major lineage backends support HTTP ingestion ([research confirmed](https://openlineage.io/docs/integrations/spark/configuration/transport/)). OTLP transport for OpenLineage does not currently exist in the OpenLineage SDK ([confirmed via ecosystem research](https://github.com/OpenLineage/OpenLineage/discussions/1542)).

**Architectural Decision**:
- **Initial Implementation (Epic 3-6)**: HTTP transport only
- **Future Research (Epic 8+)**: OTLP transport design (pending OpenLineage community adoption)
- **Design Principle**: LineageBackendPlugin interface supports future OTLP transport without breaking changes

**Acceptance Criteria**:
- [ ] LineageEmitter supports HTTP transport (type="http")
- [ ] HTTP endpoint configured via LineageBackendPlugin.get_transport_config()
- [ ] Supports authentication headers (API keys, tokens) via transport config
- [ ] Supports timeout and retry configuration
- [ ] LineageBackendPlugin interface designed to accommodate future OTLP transport
- [ ] Graceful degradation if lineage backend unavailable (logs error, continues pipeline)

**Enforcement**:
- HTTP transport implementation tests
- Authentication header tests
- Graceful degradation tests
- Backend connectivity tests (Marquez, Atlan)

**Constraints**:
- MUST use HTTP transport (OTLP transport NOT supported in OpenLineage SDK)
- MUST support backend-specific authentication (API keys, OAuth tokens)
- MUST support configurable timeout (default: 5 seconds)
- FORBIDDEN to block pipeline execution on lineage failures

**Configuration Example**:
```yaml
# manifest.yaml
plugins:
  lineage_backend:
    provider: marquez  # or atlan, openmetadata
    config:
      endpoint: "http://marquez:5000/api/v1/lineage"
      timeout: 5.0
      headers:
        Content-Type: "application/json"
```

**Test Coverage**:
- `tests/integration/test_openlineage_http_transport.py`
- `tests/integration/test_lineage_backend_integration.py`

**Traceability**:
- [OpenLineage Transport Documentation](https://openlineage.io/docs/integrations/spark/configuration/transport/)
- ADR-0007 (OpenLineage from Start)
- ADR-0035 (LineageBackendPlugin Interface)
- **Cross-reference**: REQ-057 (LineageBackendPlugin.get_transport_config())

**Future Work (Deferred to Epic 8+)**:
OTLP transport for OpenLineage requires:
1. OpenLineage community to add native OTLP transport support, OR
2. Custom OTLPLineageTransport implementation wrapping events in OTLP LogRecord, AND
3. OTel Collector processor to unwrap OTLP Logs → OpenLineage JSON → HTTP backend

**See**: ADR-0035 revision for OTLP transport research track rationale

---

### REQ-527: Lineage Backend Plugin Integration **[Updated]**

**Requirement**: System MUST integrate with LineageBackendPlugin to enable backend-specific lineage routing (Marquez, Atlan, OpenMetadata).

**Rationale**: Enables switching lineage backends via plugin system. LineageBackendPlugin is independent from TelemetryBackendPlugin (split architecture per ADR-0035 revision).

**Acceptance Criteria**:
- [ ] LineageBackendPlugin.get_transport_config() returns configured OpenLineageTransport
- [ ] LineageEmitter endpoint determined by plugin (Marquez HTTP, Atlan HTTP, etc.)
- [ ] Plugin configuration in manifest.yaml: plugins.lineage_backend
- [ ] LineageEmitter initialized during platform startup with plugin transport config
- [ ] Example implementations: MarquezLineagePlugin, AtlanLineagePlugin

**Enforcement**:
- Plugin integration tests (verify get_transport_config() called)
- Backend-specific endpoint routing tests
- E2E tests with different backends (Marquez, Atlan)

**Constraints**:
- MUST use PluginRegistry for backend selection (entry point: floe.lineage_backends)
- MUST support HTTP transport (OTLP deferred to Epic 8+)
- MUST NOT hardcode lineage endpoints
- MUST configure via manifest.yaml (NOT separate config file)

**Configuration Example**:
```yaml
# manifest.yaml
plugins:
  lineage_backend:  # NOT observability
    provider: marquez  # or atlan, openmetadata
    config:
      endpoint: "http://marquez:5000/api/v1/lineage"
```

**Test Coverage**: `tests/contract/test_lineage_backend_plugin_integration.py`

**Traceability**:
- ADR-0035 (Telemetry and Lineage Backend Plugins) - **Revised**
- plugin-architecture.md (LineageBackendPlugin ABC)
- **Cross-reference**: REQ-056 to REQ-060 (LineageBackendPlugin requirements)

---

### REQ-528: Lineage Namespace Validation **[New]**

**Requirement**: System MUST validate lineage namespace during compilation and enforce at runtime.

**Rationale**: Ensures lineage namespace consistency across all events from a product.

**Acceptance Criteria**:
- [ ] floe compile validates namespace format (alphanumeric, dash, underscore)
- [ ] Namespace extracted from floe.yaml product.name or metadata.namespace
- [ ] Namespace cannot be empty or contain special characters
- [ ] Namespace consistent across all lineage events from single product
- [ ] Compilation fails with clear error if namespace invalid
- [ ] Runtime validation confirms namespace in all lineage events

**Enforcement**:
- Compilation validation tests
- Runtime validation tests
- Event inspection confirms namespace field

**Constraints**:
- MUST validate namespace at compilation time
- MUST enforce namespace at runtime
- MUST provide actionable error messages
- FORBIDDEN to emit lineage events with invalid namespace

**Test Coverage**: `tests/contract/test_openlineage_namespace_validation.py`

**Traceability**:
- Epic 7: Enforcement Engine (Phase 5A/5B)
- floe-core compilation (artifacts schema)

---

### REQ-529: Lineage Facets (Custom Metadata) **[New]**

**Requirement**: System MUST support OpenLineage facets for attaching custom metadata to lineage events and datasets.

**Rationale**: Enables capturing context-specific information (cost allocation, SLA, owner, etc.).

**Acceptance Criteria**:
- [ ] Job facets supported: job-type, owner, sla, cost
- [ ] Dataset facets supported: schema, ownership, quality-metrics, lineage-version
- [ ] Facets formatted per OpenLineage facet specifications
- [ ] Custom facets extensible via configuration in floe.yaml
- [ ] Facets included in JSON-LD serialization
- [ ] Facets validated against OpenLineage schema

**Enforcement**:
- Facet validation tests (schema compliance)
- Custom facet tests
- E2E facet emission tests

**Constraints**:
- MUST use OpenLineage standard facet types
- MUST support custom facets via floe.yaml configuration
- MUST validate facet structure at emission time
- FORBIDDEN to emit non-standard facet formats

**Test Coverage**: `tests/contract/test_openlineage_facets.py`

**Traceability**:
- OpenLineage Facets specification
- floe.yaml schema (custom facets configuration)

---

### REQ-530: Lineage Enforcement in Compilation **[New]**

**Requirement**: System MUST validate that compiled artifacts include lineage configuration and enforce OpenLineage initialization during execution.

**Rationale**: Ensures all pipelines emit lineage events (non-optional).

**Acceptance Criteria**:
- [ ] floe compile validates lineage configuration in manifest.yaml
- [ ] Compilation fails if lineage backend not configured
- [ ] floe run enforces OPENLINEAGE_URL or OTEL_EXPORTER_OTLP_ENDPOINT before job start
- [ ] LineageEmitter initialization happens before first job event emission
- [ ] Runtime validation confirms lineage endpoint reachable (or acceptable fallback)
- [ ] Lineage emission failures logged but do not crash pipeline

**Enforcement**:
- Compilation validation tests
- Runtime validation tests
- E2E lineage enforcement tests

**Constraints**:
- MUST require lineage backend configuration at compilation time
- MUST validate endpoint reachability at runtime
- MUST provide graceful degradation on lineage endpoint failure
- FORBIDDEN to silently skip lineage events on endpoint unavailable

**Test Coverage**: `tests/contract/test_openlineage_enforcement.py`

**Traceability**:
- Epic 7: Enforcement Engine (Phase 5A/5B)
- floe-core compilation (artifacts schema)
