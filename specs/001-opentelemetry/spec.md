# Feature Specification: OpenTelemetry Integration

**Feature Branch**: `001-opentelemetry`
**Created**: 2026-01-09
**Status**: Draft
**Input**: Epic 6A - OpenTelemetry integration for distributed tracing, metrics, and logging across all floe components

## Clarifications

### Session 2026-01-09

- Q: Should the spec explicitly require the Floe semantic conventions defined in ADR-0006 (floe.namespace, floe.product.name, floe.product.version, floe.mode)? → A: Yes, add explicit requirements for all Floe semantic conventions as they are part of the ENFORCED OpenTelemetry standard per ADR-0006.
- Q: Should the spec add requirements clarifying the three-layer architecture (Emission/Collection/Backend) and what is enforced vs pluggable? → A: Yes, add explicit requirements distinguishing enforced (SDK, Collector) from pluggable (backend) layers per ADR-0006 and ADR-0035.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trace Context Propagation (Priority: P0)

As a platform operator, I want traces propagated across all floe services so that I can follow requests end-to-end through the entire data pipeline.

**Why this priority**: This is the foundation of distributed tracing. Without context propagation, traces become isolated fragments that cannot be correlated, making debugging impossible across service boundaries.

**Independent Test**: Can be tested by triggering a multi-service operation (e.g., compilation + deployment) and verifying that all resulting spans share the same trace ID.

**Acceptance Scenarios**:

1. **Given** a request enters the system, **When** the request flows through multiple floe packages (core, dbt, dagster), **Then** all spans share the same trace ID and form a connected tree.
2. **Given** a trace context exists, **When** a new child operation starts, **Then** the child span correctly references the parent span.
3. **Given** a request crosses process boundaries, **When** using standard protocols, **Then** W3C Trace Context headers are automatically propagated.
4. **Given** baggage data is attached to a context, **When** the context propagates across services, **Then** the baggage values are preserved and accessible.

---

### User Story 2 - Span Creation for Key Operations (Priority: P0)

As a platform operator, I want spans automatically created for key pipeline operations so that I can see what is happening in my data pipelines and where time is being spent.

**Why this priority**: Spans provide visibility into system behavior. This is a P0 because tracing is useless without meaningful spans capturing actual operations.

**Independent Test**: Can be tested by running a compilation or pipeline execution and verifying that spans are created with appropriate names, timing, and attributes.

**Acceptance Scenarios**:

1. **Given** a compilation operation starts, **When** the compiler processes a floe spec, **Then** a span is created capturing the operation name, duration, and outcome.
2. **Given** a dbt operation executes, **When** models are run or tested, **Then** spans are created for each model/test with relevant attributes.
3. **Given** a Dagster asset materializes, **When** the materialization completes, **Then** a span captures the asset name, duration, and success/failure status.
4. **Given** an operation fails, **When** an exception occurs, **Then** the span records the error with appropriate attributes and status.

---

### User Story 3 - OTLP Exporter Configuration (Priority: P1)

As a platform operator, I want to configure where telemetry data is sent so that I can integrate floe with my existing observability backend (Jaeger, Grafana Tempo, Honeycomb, etc.).

**Why this priority**: Without export configuration, telemetry data has nowhere to go. This enables integration with the operator's chosen observability tooling.

**Independent Test**: Can be tested by configuring an OTLP endpoint in the manifest and verifying that traces/metrics appear in the configured backend.

**Acceptance Scenarios**:

1. **Given** an OTLP endpoint is configured in the platform manifest, **When** telemetry is generated, **Then** data is exported to that endpoint.
2. **Given** OTLP/gRPC is configured, **When** traces are exported, **Then** the gRPC protocol is used with proper connection handling.
3. **Given** OTLP/HTTP is configured, **When** traces are exported, **Then** the HTTP protocol is used with proper retry behavior.
4. **Given** authentication is required, **When** credentials are provided, **Then** exports include the configured authentication headers/tokens.

---

### User Story 4 - Metric Instrumentation (Priority: P1)

As a platform operator, I want key operational metrics exported so that I can monitor system health, track performance trends, and set up alerts.

**Why this priority**: Metrics enable proactive monitoring and alerting, essential for production operations but secondary to tracing for initial debugging capability.

**Independent Test**: Can be tested by running pipelines and verifying that metrics (counters, histograms) are recorded and exported with correct values and labels.

**Acceptance Scenarios**:

1. **Given** a pipeline runs, **When** the run completes, **Then** a duration metric is recorded with appropriate labels (pipeline name, status).
2. **Given** assets materialize, **When** materializations complete, **Then** counter metrics track total materializations by asset and status.
3. **Given** errors occur, **When** operations fail, **Then** error rate metrics are incremented with component/error-type labels.
4. **Given** metrics are configured for export, **When** the export interval passes, **Then** metrics are sent to the configured OTLP endpoint.

---

### User Story 5 - Log Correlation with Traces (Priority: P2)

As a platform operator, I want log entries to include trace and span IDs so that I can correlate logs with traces when debugging issues.

**Why this priority**: Log correlation enhances debugging but is supplementary to core tracing functionality. Operators can still debug with traces alone.

**Independent Test**: Can be tested by generating logs during a traced operation and verifying that log entries contain the correct trace_id and span_id fields.

**Acceptance Scenarios**:

1. **Given** a traced operation generates logs, **When** logs are emitted, **Then** each log entry includes the current trace_id.
2. **Given** a span is active, **When** logs are emitted within that span, **Then** each log entry includes the span_id.
3. **Given** structured logging is configured, **When** logs are output, **Then** trace context appears as structured fields (not embedded in message text).
4. **Given** log level is configured, **When** logs are emitted, **Then** only logs at or above the configured level are output.

---

### Edge Cases

- What happens when no OTLP endpoint is configured? System operates normally with telemetry disabled (no-op provider).
- How does the system handle OTLP endpoint unavailability? Exports fail gracefully with retries; application continues without blocking.
- What happens when trace context is malformed? Invalid context is logged and a new root trace is started.
- How are very long-running operations handled? Spans remain open until completion; configurable timeout for abandoned spans.
- What happens during high-volume scenarios? Sampling reduces data volume while preserving representative traces.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a TelemetryProvider that configures tracing, metrics, and logging initialization
- **FR-002**: System MUST propagate W3C Trace Context headers across all service boundaries
- **FR-003**: System MUST propagate W3C Baggage headers for cross-cutting concerns
- **FR-004**: System MUST create spans for compilation operations with operation name, duration, and status
- **FR-005**: System MUST create spans for dbt operations (run, test, build) with model/test identifiers
- **FR-006**: System MUST create spans for Dagster asset materializations with asset key and status
- **FR-007**: System MUST include `floe.namespace` attribute on ALL spans (mandatory per ADR-0006)
- **FR-007a**: System MUST propagate `floe.namespace` via W3C Baggage across service boundaries
- **FR-007b**: System MUST include `floe.product.name` attribute on spans identifying the data product
- **FR-007c**: System MUST include `floe.product.version` attribute on spans for version tracking
- **FR-007d**: System MUST include `floe.mode` attribute on spans (dev/staging/prod)
- **FR-008**: System MUST support OTLP/gRPC exporter protocol
- **FR-009**: System MUST support OTLP/HTTP exporter protocol
- **FR-010**: System MUST allow OTLP endpoint configuration via platform manifest
- **FR-011**: System MUST support authentication for OTLP exports (API keys, bearer tokens)
- **FR-012**: System MUST record pipeline run duration as histogram metric
- **FR-013**: System MUST record asset materialization counts as counter metric
- **FR-014**: System MUST record error rates by component as counter metric
- **FR-015**: System MUST inject trace_id into all log records when a trace is active
- **FR-016**: System MUST inject span_id into all log records when a span is active
- **FR-017**: System MUST support structured logging format with trace context as fields
- **FR-018**: System MUST support configurable log levels
- **FR-019**: System MUST follow OpenTelemetry semantic conventions for all telemetry
- **FR-020**: System MUST include resource attributes (service.name, service.version, deployment.environment)
- **FR-021**: System MUST support configurable sampling rates per environment
- **FR-022**: System MUST record errors on spans with exception details and stack traces
- **FR-023**: System MUST operate in no-op mode when telemetry is not configured (zero overhead)
- **FR-024**: System MUST export telemetry asynchronously to avoid blocking application code

#### Three-Layer Architecture Requirements (per ADR-0006, ADR-0035)

- **FR-025**: Layer 1 (Emission) - OpenTelemetry SDK is ENFORCED; all floe components MUST use OpenTelemetry SDK for telemetry emission
- **FR-026**: Layer 2 (Collection) - OTLP Collector is ENFORCED; all telemetry MUST be sent to OTLP Collector (not directly to backends)
- **FR-027**: Layer 3 (Backend) - Storage/visualization is PLUGGABLE via TelemetryBackendPlugin; platform teams select backend (Jaeger, Datadog, Grafana Cloud, etc.)
- **FR-028**: System MUST NOT allow data pipelines to bypass OTLP Collector and send telemetry directly to backends
- **FR-029**: TelemetryBackendPlugin MUST generate OTLP Collector exporter configuration (not SDK configuration)
- **FR-030**: Backend selection via `plugins.telemetry_backend` in manifest.yaml; changing backends requires NO code changes in data pipelines

### Key Entities

- **TelemetryProvider**: Central configuration object that initializes tracing, metrics, and logging. Configures exporters, samplers, and resource attributes.
- **SpanContext**: Wrapper around trace context, providing access to trace_id, span_id, and trace flags. Used for context propagation and log correlation.
- **MetricRecorder**: Interface for recording metrics (counters, histograms, gauges). Abstracts metric instrument creation and recording.
- **Resource**: Collection of attributes describing the service (name, version, environment). Applied to all telemetry signals.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Platform operators can trace a request from ingestion through transformation to consumption, with all spans visible in a single trace view
- **SC-002**: 100% of compilation, dbt execution, and asset materialization operations generate spans with timing and status
- **SC-003**: Platform operators can identify the root cause of pipeline failures within 5 minutes using trace data
- **SC-004**: Telemetry overhead adds less than 5% latency to pipeline operations under normal sampling
- **SC-005**: System continues operating normally when observability backend is unavailable (no application failures)
- **SC-006**: Platform operators can correlate logs with traces using shared identifiers within 30 seconds
- **SC-007**: All telemetry follows OpenTelemetry semantic conventions, enabling compatibility with any OTLP-compatible backend
- **SC-008**: Platform operators can configure telemetry export to their backend without code changes (configuration only)

## Assumptions

- OTLP is the only required export format (console exporter for development is acceptable)
- Platform operators have access to an OTLP-compatible observability backend
- Sampling configuration follows environment-based conventions (dev: 100%, staging: 50%, prod: 10%)
- The system uses Python's logging module which will be enhanced with trace context injection
- All floe packages will emit telemetry through the shared TelemetryProvider
