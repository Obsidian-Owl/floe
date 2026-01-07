# REQ-500 to REQ-515: OpenTelemetry Observability

**Domain**: Observability and Lineage
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines OpenTelemetry (OTel) SDK integration for distributed tracing, metrics collection, and structured logging. OTel provides vendor-neutral observability enabling platform teams to choose backends (Jaeger, Datadog, Grafana Cloud, etc.) without changing application code.

**Key Principle**: Vendor-neutral observability through OpenTelemetry (ADR-0006)

## Requirements

### REQ-500: OpenTelemetry SDK Initialization **[New]**

**Requirement**: System MUST initialize OpenTelemetry SDK with TracerProvider, MeterProvider, and LoggerProvider in every Layer 3 (service) and Layer 4 (job) component.

**Rationale**: Ensures consistent telemetry emission across all platform components.

**Acceptance Criteria**:
- [ ] TracerProvider initialized with OTLP exporter
- [ ] MeterProvider initialized with OTLP exporter
- [ ] LoggerProvider initialized with OTLP exporter
- [ ] All providers configured with batching and sampling
- [ ] Initialization fails fast with clear error messages if OTLP Collector unreachable

**Enforcement**:
- Unit tests verify provider initialization
- Integration tests validate OTLP payload emission
- E2E tests validate end-to-end trace collection

**Constraints**:
- MUST use opentelemetry-api and opentelemetry-sdk packages
- MUST use OTLP protocol (gRPC or HTTP) for export
- MUST support configurable sampling (default: 100% for dev, 10% for prod)
- FORBIDDEN to use proprietary observability SDKs without fallback to OTel

**Test Coverage**: `tests/contract/test_observability_otel.py::test_otel_initialization`

**Traceability**:
- ADR-0006 (OpenTelemetry for Observability)
- four-layer-overview.md lines 79, 100
- platform-services.md (observability services section)

---

### REQ-501: Trace Context Propagation (W3C) **[New]**

**Requirement**: System MUST propagate W3C Trace Context (traceparent, tracestate) across all service boundaries and inter-process calls.

**Rationale**: Enables request tracing across distributed services (Dagster → Polaris → dbt jobs).

**Acceptance Criteria**:
- [ ] W3C Trace Context headers automatically propagated in HTTP requests
- [ ] Trace context propagated in AMQP/RabbitMQ message headers (if used)
- [ ] Trace context propagated in Kubernetes pod environment variables
- [ ] trace_id and span_id consistent across service boundaries
- [ ] trace_id used for log correlation (all logs for same request have same trace_id)

**Enforcement**:
- Integration tests validate trace context in service-to-service calls
- Log analysis confirms trace_id consistency
- Cross-service tracing tests in E2E suite

**Constraints**:
- MUST use W3C Trace Context format (RFC 9110)
- MUST use opentelemetry-instrumentation packages for automatic propagation
- FORBIDDEN to use proprietary trace header formats

**Test Coverage**: `tests/contract/test_observability_otel.py::test_w3c_trace_context`

**Traceability**:
- ADR-0006 section "Standard propagation"
- W3C Trace Context specification

---

### REQ-502: Namespace Context Baggage **[New]**

**Requirement**: System MUST include `floe.namespace` in W3C Baggage on all traces and propagate it across service boundaries.

**Rationale**: Enables filtering and aggregation by data product (critical for multi-tenant platforms).

**Acceptance Criteria**:
- [ ] `floe.namespace` set on all root spans from Layer 4 jobs
- [ ] `floe.namespace` propagated via W3C Baggage to child spans
- [ ] All OTLP events include `floe.namespace` in resource/span attributes
- [ ] Namespace context available in logs via context variables
- [ ] Grafana/Jaeger dashboards can filter by namespace

**Enforcement**:
- Context propagation tests validate baggage headers
- Span inspection confirms `floe.namespace` attribute present
- Dashboard filters work for namespace-based queries

**Constraints**:
- MUST use W3C Baggage format (RFC 9110)
- MUST set `floe.namespace` before span creation in Layer 4
- FORBIDDEN to use custom header formats for namespace

**Test Coverage**: `tests/contract/test_observability_otel.py::test_namespace_baggage`

**Traceability**:
- ADR-0006 section "Semantic Conventions"
- platform-manifest.yaml validation (namespace field required)

---

### REQ-503: Semantic Conventions for Floe **[New]**

**Requirement**: System MUST define and enforce Floe-specific semantic conventions for span and metric attributes.

**Rationale**: Standardizes observability data structure for analysis and dashboard creation.

**Acceptance Criteria**:
- [ ] Span attributes include: floe.namespace, floe.product.name, floe.product.version, floe.mode (dev/prod)
- [ ] Attributes include OpenTelemetry semantic conventions (service.name, service.version, etc.)
- [ ] Metrics labeled with same attributes as spans
- [ ] Log entries structured with same attributes via context variables
- [ ] Documentation defines all Floe-specific conventions

**Enforcement**:
- Span schema validation (Pydantic models for attributes)
- Metric labeling tests
- Log structure tests

**Constraints**:
- MUST use OpenTelemetry standard conventions (semconv package)
- MUST define Floe conventions in floe-core/src/floe_core/observability/conventions.py
- FORBIDDEN to use non-standard attribute names

**Test Coverage**: `tests/contract/test_observability_otel.py::test_semantic_conventions`

**Traceability**:
- ADR-0006 section "Semantic Conventions"
- opentelemetry-instrumentation-* documentation

---

### REQ-504: Distributed Tracing (Traces) **[New]**

**Requirement**: System MUST emit distributed traces for all Layer 3 (service) and Layer 4 (job) operations, including spans for request handling, database queries, and external API calls.

**Rationale**: Enables debugging and performance analysis of data pipelines.

**Acceptance Criteria**:
- [ ] HTTP request spans (entry point, handlers, exits)
- [ ] Database query spans (connection, query execution, commit)
- [ ] External API call spans (request, response, errors)
- [ ] dbt model run spans (model execution, lineage context)
- [ ] Span names follow OpenTelemetry conventions (e.g., "GET /catalog", "db.query")
- [ ] Span status set correctly (OK, ERROR, with error details)
- [ ] Span events recorded for significant events (dbt test failure, API timeout)

**Enforcement**:
- Integration tests capture and validate trace structure
- Trace completeness tests (all database queries traced)
- E2E traces exported to OTLP Collector

**Constraints**:
- MUST use opentelemetry-instrumentation-* for automatic tracing
- MUST set span status on completion
- MUST record exception details on span for errors
- FORBIDDEN to create excessive spans (sampling may be applied)

**Test Coverage**: `tests/contract/test_observability_otel.py::test_distributed_tracing`

**Traceability**:
- ADR-0006 section "Implementation Pattern"
- four-layer-overview.md Layer 3/4 components

---

### REQ-505: Metrics Collection (Metrics) **[New]**

**Requirement**: System MUST collect application metrics (counters, gauges, histograms) for platform health monitoring.

**Rationale**: Enables alerting and performance monitoring.

**Acceptance Criteria**:
- [ ] Counter metrics: pipeline_runs_total, dataset_materialized_total, errors_total
- [ ] Gauge metrics: pipeline_duration_seconds, active_connections, queue_depth
- [ ] Histogram metrics: request_duration_seconds, database_query_duration_seconds
- [ ] All metrics labeled with floe.namespace and other semantic conventions
- [ ] Metrics export to OTLP Collector in 60-second intervals
- [ ] Metrics queryable in Prometheus/Grafana

**Enforcement**:
- Metric collection tests validate metric emission
- OTLP metric payload validation
- Prometheus scrape endpoint tests (if applicable)

**Constraints**:
- MUST use opentelemetry-sdk.metrics package
- MUST export via OTLP protocol
- MUST use standard metric naming (snake_case, _total suffix for counters)
- FORBIDDEN to emit unbounded cardinality metrics (e.g., metric per user)

**Test Coverage**: `tests/contract/test_observability_otel.py::test_metrics_collection`

**Traceability**:
- OpenTelemetry Metrics specification
- Prometheus best practices

---

### REQ-506: Structured Logging with Context **[New]**

**Requirement**: System MUST emit structured logs with OpenTelemetry context (trace_id, span_id, namespace) for all significant operations.

**Rationale**: Enables log aggregation and correlation with traces.

**Acceptance Criteria**:
- [ ] All logs include trace_id and span_id (from active span context)
- [ ] All logs include floe.namespace (from baggage context)
- [ ] Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- [ ] Log format: JSON with standardized fields (timestamp, level, message, attributes)
- [ ] Logs exported to OTLP Collector via OTLP LogRecord exporter
- [ ] Logs queryable in Grafana Loki/ELK/etc.

**Enforcement**:
- Structured logging middleware tests
- Context injection tests (trace_id, namespace in logs)
- Log export validation

**Constraints**:
- MUST use structlog or similar for structured logging
- MUST include trace context automatically (via context variables)
- MUST NOT log sensitive data (passwords, API keys, PII)
- FORBIDDEN to emit unstructured logs (all logs must be JSON)

**Test Coverage**: `tests/contract/test_observability_otel.py::test_structured_logging`

**Traceability**:
- OpenTelemetry Logs specification
- structlog documentation

---

### REQ-507: OTLP Collector Integration **[New]**

**Requirement**: System MUST configure OTLP Collector as the central collection point for all telemetry (traces, metrics, logs).

**Rationale**: Standardizes telemetry routing and enables switching observability backends without code changes.

**Acceptance Criteria**:
- [ ] OTLP Collector deployed in Layer 3 (K8s Deployment)
- [ ] OpenTelemetry SDK in all components sends to OTLP Collector
- [ ] OTLP Collector configuration supports trace, metric, and log receivers
- [ ] Collector performs batching (default: 200 spans/batch, 5s timeout)
- [ ] Collector performs sampling (default: 100% dev, 10% prod)
- [ ] Collector supports backend-specific exporters (Jaeger, Datadog, etc.)

**Enforcement**:
- OTLP Collector deployment tests (Helm chart validation)
- OTLP receiver health checks
- End-to-end data flow tests (SDK → Collector → backend)

**Constraints**:
- MUST use OpenTelemetry Collector (official distribution)
- MUST expose OTLP gRPC receiver on port 4317
- MUST expose OTLP HTTP receiver on port 4318 (for browser/lambda)
- FORBIDDEN to use legacy metrics formats (Prometheus scrape only via Collector exporter)

**Test Coverage**: `tests/integration/test_otlp_collector.py`

**Traceability**:
- ADR-0006 section "Backend Configuration"
- OpenTelemetry Collector documentation
- four-layer-overview.md Layer 3 (OTLP Collector service)

---

### REQ-508: OTLP Collector Helm Chart **[New]**

**Requirement**: System MUST provide Helm chart for deploying OTLP Collector to Kubernetes.

**Rationale**: Enables consistent, reproducible observability infrastructure deployment.

**Acceptance Criteria**:
- [ ] Helm chart: `charts/otel-collector/`
- [ ] Chart includes ConfigMap for collector configuration
- [ ] Chart configurable via values.yaml (sampling rate, batch size, backend)
- [ ] Chart deploys Collector as Deployment (2+ replicas)
- [ ] Chart creates Service for gRPC (4317) and HTTP (4318) endpoints
- [ ] Chart includes resource limits (CPU, memory)
- [ ] Chart includes health check probes

**Enforcement**:
- Helm chart lint passes
- Helm deployment tests in Kind cluster
- Service discovery tests (pods can reach OTLP Collector)

**Constraints**:
- MUST use official OpenTelemetry Collector image
- MUST support configurable backends via values.yaml
- FORBIDDEN to hardcode OTLP Collector endpoints in application code (use K8s DNS)

**Test Coverage**: `tests/integration/test_otel_collector_helm.py`

**Traceability**:
- charts/otel-collector/ (Helm chart implementation)
- four-layer-overview.md Layer 3 (OTLP Collector)

---

### REQ-509: Sampling Configuration **[New]**

**Requirement**: System MUST support configurable sampling rates for traces and metrics.

**Rationale**: Reduces observability costs in production while maintaining debug visibility in dev.

**Acceptance Criteria**:
- [ ] TracerProvider configured with TraceIDRatioBased sampler
- [ ] Default sampling: 100% for dev, 10% for prod
- [ ] Sampling rate configurable via environment variable: OTEL_TRACES_SAMPLER_ARG
- [ ] Sampling decision included in trace context (propagated to child spans)
- [ ] Metrics collected at 100% (no sampling) regardless of trace sampling
- [ ] Logs collected at 100% (no sampling) regardless of trace sampling

**Enforcement**:
- Sampling rate tests (validate trace count vs. configured rate)
- Configuration validation tests
- Environment variable override tests

**Constraints**:
- MUST use TraceIDRatioBased sampler (standard OTel sampler)
- MUST NOT sample metrics or logs (only traces)
- MUST support ParentBased sampler composition (inherit parent sampling decision)

**Test Coverage**: `tests/contract/test_observability_otel.py::test_sampling_configuration`

**Traceability**:
- OpenTelemetry Sampler specification
- ADR-0006 section "Implementation Pattern"

---

### REQ-510: Local Development (No-Op Collector) **[New]**

**Requirement**: System MUST support local development without OTLP Collector (graceful degradation to console/file export).

**Rationale**: Enables developers to work locally without full observability infrastructure.

**Acceptance Criteria**:
- [ ] When OTEL_EXPORTER_OTLP_ENDPOINT not set, use console exporter for dev
- [ ] Console exporter outputs JSON-formatted telemetry to stdout
- [ ] Alternatively, file exporter writes to `$PWD/.otel/traces.json`
- [ ] Sampling rate set to 100% when using console/file exporters
- [ ] No error on startup if OTLP Collector unreachable (dev mode)

**Enforcement**:
- Local development tests (run without OTLP Collector)
- Console exporter output validation
- File export validation

**Constraints**:
- MUST gracefully degrade (not fail) if OTLP Collector unavailable
- MUST log warning if running without OTLP export
- FORBIDDEN to throw exception on OTLP Collector unreachable during startup

**Test Coverage**: `tests/unit/test_observability_local_dev.py`

**Traceability**:
- OpenTelemetry SDK (SpanProcessor implementations)
- TESTING.md (local development guidance)

---

### REQ-511: dbt Model Run Tracing **[New]**

**Requirement**: System MUST emit traces for dbt model executions with model name, execution time, and status.

**Rationale**: Enables debugging and performance analysis of transformations.

**Acceptance Criteria**:
- [ ] Span created for each dbt model run (span.name = "dbt.model.run" or model name)
- [ ] Span attributes include: model_name, materialization, database, schema
- [ ] Span duration = model execution time
- [ ] Span events recorded for: model_compiled, model_executed, model_tested
- [ ] Span status set to ERROR if dbt test fails post-execution
- [ ] Nested spans for compilation and execution phases

**Enforcement**:
- dbt instrumentation integration tests
- Span structure validation
- E2E tests validate dbt traces in OTLP payload

**Constraints**:
- MUST hook into dbt run lifecycle via hooks or instrumentation
- MUST capture dbt manifest.json for model lineage context
- FORBIDDEN to parse dbt logs (use official dbt APIs)

**Test Coverage**: `tests/contract/test_observability_dbt_tracing.py`

**Traceability**:
- floe-dbt integration (dbt project configuration)
- ADR-0006 section "Implementation Pattern"

---

### REQ-512: Job Execution Tracing **[New]**

**Requirement**: System MUST emit traces for Layer 4 (job) executions including start, completion, and failure events.

**Rationale**: Enables monitoring and debugging of data pipelines.

**Acceptance Criteria**:
- [ ] Root span created for each job execution
- [ ] Span name: "{job_type}.{job_name}" (e.g., "dbt.run", "dlt.ingest", "quality.check")
- [ ] Span start time = job start time, end time = job completion time
- [ ] Span attributes include: job_id, product_name, namespace
- [ ] Span events: job_start, job_complete, job_fail (with error details)
- [ ] Child spans created for significant operations (table creation, query execution)

**Enforcement**:
- Job tracing integration tests
- Span hierarchy validation (parent-child relationships)
- E2E job execution tracing tests

**Constraints**:
- MUST create root span at K8s Job start
- MUST NOT create spans before OTLP initialization
- FORBIDDEN to use app-level timing (must use actual execution time)

**Test Coverage**: `tests/contract/test_observability_job_tracing.py`

**Traceability**:
- four-layer-overview.md Layer 4 (Data/Jobs)
- floe-cli run command implementation

---

### REQ-513: Error Tracking and Exception Spans **[New]**

**Requirement**: System MUST record exceptions and errors in spans with full context for debugging.

**Rationale**: Enables rapid issue diagnosis and root cause analysis.

**Acceptance Criteria**:
- [ ] On exception, span.status set to ERROR with error.kind, error.type
- [ ] Exception details (message, traceback) recorded on span
- [ ] Span event created with exception type and message
- [ ] Error severity mapped to log level (ERROR for span errors)
- [ ] Full exception traceback available in span attributes (not summary)
- [ ] PII redaction applied to exception messages and tracebacks

**Enforcement**:
- Error handling tests validate span status and events
- Exception detail tests
- PII redaction tests

**Constraints**:
- MUST use span.record_exception(exception) API
- MUST NOT include PII in exception messages (sanitize credentials, secrets)
- FORBIDDEN to suppress exception tracing

**Test Coverage**: `tests/contract/test_observability_errors.py`

**Traceability**:
- ADR-0006 section "Implementation Pattern"
- OpenTelemetry Spans specification (status, events)

---

### REQ-514: Observability Plugin Initialization **[New]**

**Requirement**: System MUST initialize ObservabilityPlugin during platform startup to configure backend-specific exporter.

**Rationale**: Enables switching observability backends (Jaeger, Datadog, Grafana Cloud) via plugin system.

**Acceptance Criteria**:
- [ ] ObservabilityPlugin ABC defines get_exporter() method
- [ ] OTLP Collector configured with backend-specific exporter
- [ ] Plugin selected via plugins.observability in platform-manifest.yaml
- [ ] Example plugins: JaegerPlugin, DatadogPlugin, GrafanaCloudPlugin
- [ ] Plugin initialization happens before first span creation
- [ ] Plugin failure logs warning but does not crash system (OTel SDK continues with console exporter)

**Enforcement**:
- Plugin discovery and initialization tests
- Backend-specific exporter configuration tests
- Contract tests validate ObservabilityPlugin ABC compliance

**Constraints**:
- MUST use PluginRegistry for discovery
- MUST NOT hardcode exporter configuration
- FORBIDDEN to require control plane for observability backend selection

**Test Coverage**: `tests/contract/test_observability_plugin.py`

**Traceability**:
- ADR-0006 section "Backend Configuration"
- ADR-0035 (Observability Plugin Interface)
- plugin-architecture.md (ObservabilityPlugin ABC)

---

### REQ-515: Observability Enforcement in Compilation **[New]**

**Requirement**: System MUST validate that compiled artifacts include observability configuration and enforce OTel SDK initialization during execution.

**Rationale**: Ensures all pipelines emit telemetry (non-optional).

**Acceptance Criteria**:
- [ ] floe compile validates observability configuration in platform-manifest.yaml
- [ ] Compilation fails if observability plugin not selected
- [ ] floe run enforces OTEL_EXPORTER_OTLP_ENDPOINT before job start
- [ ] Compilation includes observability SDK initialization code in generated artifacts
- [ ] Runtime validation confirms OTLP Collector reachable (or acceptable fallback)

**Enforcement**:
- Compilation validation tests
- Runtime validation tests
- E2E enforcement tests

**Constraints**:
- MUST reject compilation if observability disabled
- MUST provide clear error messages on validation failure
- FORBIDDEN to allow pipelines to run without observability initialization

**Test Coverage**: `tests/contract/test_observability_enforcement.py`

**Traceability**:
- Epic 7: Enforcement Engine (Phase 5A/5B)
- floe-core compilation (artifacts schema)
