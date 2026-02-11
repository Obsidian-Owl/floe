# Feature Specification: OTel Code Instrumentation

**Epic**: 6C (OTel Code Instrumentation)
**Feature Branch**: `6c-otel-code-instrumentation`
**Created**: 2026-02-10
**Status**: Draft
**Input**: User description: "Epic 6C: OTel Code Instrumentation - we are getting close to finalising the platform for its first alpha release. We now need to ensure EVERY system and plugin within the floe platform has proper OpenTelemetry instrumentation with strong tests to prove there are no structural bugs."

## Context

Epic 6A delivered the OpenTelemetry SDK infrastructure:
- `TelemetryProvider` (SDK lifecycle management)
- `TracerFactory` (thread-safe tracer creation with NoOp fallback)
- `FloeSpanAttributes` / conventions (floe.namespace, floe.product.name, etc.)
- `TelemetryConfig` in CompiledArtifacts (OTLP endpoint, sampling, auth)
- `TelemetryBackendPlugin` ABC with console and Jaeger implementations
- `MetricRecorder` (counters, gauges, histograms)
- W3C Trace Context + Baggage propagation
- structlog + OTel trace context injection

Epic 6C ensures that every package and plugin in the platform **actually uses** that infrastructure — closing instrumentation gaps, unifying inconsistent APIs, and proving correctness through comprehensive tests.

### Current Instrumentation Audit

**Fully Instrumented** (5 of 21 plugins + 2 packages):
- floe-core (telemetry subsystem, OCI, compilation, observability)
- floe-iceberg (table manager operations via `@traced`)
- floe-catalog-polaris (`catalog_span()` context manager)
- floe-dbt-core (`dbt_span()` context manager)
- floe-semantic-cube (`semantic_span()` context manager)
- floe-ingestion-dlt (`ingestion_span()` + `egress_span()`)
- floe-identity-keycloak (inline tracing)

**Partially Instrumented** (6 plugins — have tracer imports but no dedicated tracing module; all get full tracing.py treatment per clarification):
- floe-compute-duckdb, floe-orchestrator-dagster, floe-quality-dbt, floe-quality-gx, floe-dbt-fusion, floe-secrets-infisical

**Zero Instrumentation** (10 plugins):
- floe-alert-alertmanager, floe-alert-email, floe-alert-slack, floe-alert-webhook
- floe-lineage-marquez, floe-secrets-k8s
- floe-network-security-k8s, floe-rbac-k8s
- floe-telemetry-console, floe-telemetry-jaeger

### Known Structural Issues

1. **Two divergent `@traced` decorator APIs**: `floe_core.telemetry.tracing.traced` (uses `floe_attributes`) vs `floe_iceberg.telemetry.traced` (uses `attributes_fn`). Different signatures for the same purpose.
2. **No programmatic audit mechanism**: Plugin ABCs have no OTel hooks — impossible to verify at startup that all loaded plugins are instrumented.
3. **Metrics only from floe-core**: No plugins emit their own domain-specific metrics despite `MetricRecorder` being available.
4. **Inconsistent error sanitization**: Only floe-ingestion-dlt has credential redaction in span error messages.

### Scope

**Entry Points**: No new CLI commands — this epic instruments existing code paths.

**Dependencies**:
- floe-core telemetry subsystem (Epic 6A — complete)
- All 21 plugins and 2 core packages

**Produces**:
- `tracing.py` modules in all uninstrumented plugins
- Unified `@traced` decorator in floe-core
- Test coverage proving every critical operation creates spans
- Plugin instrumentation audit capability

---

## Clarifications

### Session 2026-02-10

- Q: Should partially instrumented plugins (compute-duckdb, orchestrator-dagster, quality-dbt, quality-gx, dbt-fusion, secrets-infisical) get full tracing.py treatment or lighter touch? A: Full treatment — create tracing.py with domain context manager for ALL partially-instrumented plugins, same as zero-instrumentation ones. Consistent pattern across entire platform.
- Q: Which plugins should be excluded from instrumentation requirements? A: Exclude only console and jaeger telemetry backends (infinite loop risk). dbt-fusion still gets tracing.py for its fallback paths. SC-001 target: 19 of 21 plugins + 2 core packages.
- Q: Should instrumentation audit be a new CLI command or integrated into existing compilation? A: Warnings during compilation — no new CLI command. Audit runs automatically during `floe compile` and emits structured warnings. Zero new surface area.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every Plugin Operation Creates Spans (Priority: P0)

As a platform operator, I want every plugin operation to create OTel spans so that when something goes wrong in my data pipeline, I can see exactly which component failed and how long each step took.

**Why this priority**: This is the core deliverable. Without spans from every component, operators have blind spots — they can see compilation and some dbt operations, but alert delivery, lineage emission, secret resolution, and data quality checks are invisible. For alpha, every operation must be traceable.

**Independent Test**: Can be tested by running unit tests with `InMemorySpanExporter` and verifying that each plugin's key operations produce spans with correct names, attributes, and error recording.

**Acceptance Scenarios**:

1. **Given** an alert plugin sends a notification, **When** the delivery completes (or fails), **Then** a span is created with `alert.channel`, `alert.destination`, delivery status, and duration.
2. **Given** the lineage plugin emits an OpenLineage event, **When** the emission completes, **Then** a span is created with `lineage.job_name`, `lineage.event_type`, and success/failure status.
3. **Given** a secrets plugin resolves a secret, **When** resolution completes, **Then** a span is created with `secrets.provider` and `secrets.key_name` (but NOT the secret value).
4. **Given** a quality plugin runs data validation, **When** checks complete, **Then** a span is created with `quality.check_name`, `quality.rows_checked`, and pass/fail count.
5. **Given** any plugin operation fails with an exception, **When** the span closes, **Then** the exception type and sanitized message are recorded on the span (no credentials or PII).

---

### User Story 2 - Unified @traced Decorator (Priority: P1)

As a plugin developer, I want a single `@traced` decorator with a consistent API so that I can instrument new code without learning different APIs for different packages.

**Why this priority**: The current two-API situation (floe-core's `traced` vs floe-iceberg's `traced`) creates confusion and inconsistency. Unifying the API prevents divergence as more plugins are added and reduces the learning curve for contributors.

**Independent Test**: Can be tested by decorating functions with the unified `@traced` and verifying that static FloeSpanAttributes AND dynamic `attributes_fn` both work.

**Acceptance Scenarios**:

1. **Given** a developer uses `@traced(name="my.operation")`, **When** the function executes, **Then** a span is created with the given name, the function's return value is preserved, and exceptions are recorded.
2. **Given** a developer provides `floe_attributes=FloeSpanAttributes(...)`, **When** the span is created, **Then** the semantic convention attributes are set on the span.
3. **Given** a developer provides `attributes_fn=lambda args: {...}`, **When** the span is created, **Then** the dynamic attributes from the function are set on the span.
4. **Given** a developer uses `@traced` on an async function, **When** the async function executes, **Then** the span correctly wraps the coroutine with proper context propagation.
5. **Given** the floe-iceberg package currently uses its own `@traced`, **When** Epic 6C is complete, **Then** floe-iceberg uses the unified decorator from floe-core instead.

---

### User Story 3 - Plugin Instrumentation Audit at Startup (Priority: P1)

As a platform operator, I want the platform to verify at startup that all loaded plugins have OTel instrumentation so that I am warned about observability blind spots before running pipelines.

**Why this priority**: Without programmatic verification, instrumentation gaps are only discovered when debugging production incidents. An audit mechanism catches gaps early and prevents regression as new plugins are added.

**Independent Test**: Can be tested by loading a plugin registry with both instrumented and uninstrumented plugins, running the audit, and verifying warnings are emitted for uninstrumented ones.

**Acceptance Scenarios**:

1. **Given** all loaded plugins report a tracer name, **When** the platform starts, **Then** the audit passes silently.
2. **Given** a loaded plugin does NOT report a tracer name, **When** the platform starts, **Then** a structured warning is logged identifying the uninstrumented plugin.
3. **Given** the audit finds uninstrumented plugins, **When** the results are reported, **Then** each warning includes the plugin type, name, and a suggestion to add a `tracing.py` module.
4. **Given** a plugin implements the optional `get_tracer_name()` method on `PluginMetadata`, **When** the audit runs, **Then** that plugin is considered instrumented.

---

### User Story 4 - Span Error Sanitization Across All Plugins (Priority: P2)

As a platform operator, I want all span error messages to be sanitized so that credentials, connection strings, and PII are never exposed in my observability backend.

**Why this priority**: Currently only floe-ingestion-dlt sanitizes errors in spans. All other plugins use raw `span.record_exception()` which can leak database URLs with embedded passwords, API keys in error messages, or customer data. This is a security requirement for production.

**Independent Test**: Can be tested by triggering errors containing credential patterns (e.g., `postgresql://user:password@host`) and verifying the span's exception message has credentials redacted.

**Acceptance Scenarios**:

1. **Given** a plugin operation fails with an exception containing a URL with credentials, **When** the error is recorded on the span, **Then** the credentials are replaced with `<REDACTED>`.
2. **Given** a plugin operation fails with an exception containing `password=secret123`, **When** the error is recorded on the span, **Then** the value after `password=` is replaced with `<REDACTED>`.
3. **Given** a plugin operation fails with a long exception message (>500 chars), **When** the error is recorded on the span, **Then** the message is truncated to 500 characters.
4. **Given** the `sanitize_error_message()` utility exists in floe-core, **When** any plugin records an error, **Then** it uses the shared utility rather than implementing its own sanitization.

---

### User Story 5 - Comprehensive Test Coverage Proving No Structural Bugs (Priority: P0)

As a platform owner, I want comprehensive tests for every instrumentation point so that I have proof that OTel integration works correctly and will not silently break during future development.

**Why this priority**: The write() no-op incident (Epic 4G) proved that instrumentation without behavioral tests is meaningless. Every span creation must have a test that verifies the span was actually created with correct attributes — not just that the function returned successfully.

**Independent Test**: Can be tested by running the full test suite and verifying >80% coverage of tracing code, with every plugin's tracing module covered by at least one unit test using `InMemorySpanExporter`.

**Acceptance Scenarios**:

1. **Given** every plugin has a `tracing.py` module, **When** the test suite runs, **Then** there is at least one test per plugin that captures spans via `InMemorySpanExporter` and asserts span name, attributes, and status.
2. **Given** a plugin's operation succeeds, **When** the test verifies the span, **Then** the span has `StatusCode.OK` and correct domain attributes.
3. **Given** a plugin's operation fails, **When** the test verifies the span, **Then** the span has `StatusCode.ERROR`, the exception type is recorded, and the error message is sanitized.
4. **Given** the `@traced` decorator is unified, **When** the test suite runs, **Then** there are tests covering: sync functions, async functions, static attributes, dynamic attributes_fn, exception recording, and nested spans.
5. **Given** a new plugin is added in the future, **When** it lacks a tracing test, **Then** the contract test suite detects the gap (plugin without corresponding tracing test).

---

### Edge Cases

- What happens when a plugin's tracing module fails to import OTel? The TracerFactory returns a NoOp tracer; the plugin still functions without spans.
- What happens when `attributes_fn` raises an exception? The span is still created with a warning attribute; the original function still executes.
- What if a plugin is loaded but OTel SDK is not initialized? NoOp tracer produces no spans; no errors or side effects.
- What happens when two plugins use the same tracer name? Each gets the same cached tracer instance; spans are still distinguishable by span name and attributes.
- How are secrets handled in span attributes? Span attributes MUST NOT contain secret values — only key names, provider types, and resolution status.

## Requirements *(mandatory)*

### Functional Requirements

#### Plugin Instrumentation (Closing Gaps)

- **FR-001**: All 4 alert plugins (alertmanager, email, slack, webhook) MUST have a `tracing.py` module with an `alert_span()` context manager that creates spans for notification delivery
- **FR-002**: floe-lineage-marquez MUST have a `tracing.py` module with a `lineage_span()` context manager that creates spans for OpenLineage event emission
- **FR-003**: floe-secrets-k8s MUST have a `tracing.py` module with a `secrets_span()` context manager that creates spans for secret resolution (matching floe-secrets-infisical's pattern)
- **FR-004**: floe-quality-dbt and floe-quality-gx MUST have `tracing.py` modules with a `quality_span()` context manager that creates spans for data quality check execution
- **FR-005**: floe-compute-duckdb MUST have a `tracing.py` module with a `compute_span()` context manager (currently has integration test but no production tracing module)
- **FR-006**: floe-orchestrator-dagster MUST instrument IO manager operations and asset execution beyond the current `semantic_sync.py` tracing
- **FR-007**: floe-network-security-k8s and floe-rbac-k8s MUST have a `tracing.py` module with a `security_span()` context manager that creates spans for policy/manifest generation

#### Unified @traced Decorator

- **FR-008**: The `@traced` decorator in `floe_core.telemetry.tracing` MUST support both `floe_attributes` (static FloeSpanAttributes) AND `attributes_fn` (dynamic callable) parameters
- **FR-009**: The `@traced` decorator MUST support both sync and async functions
- **FR-010**: The `@traced` decorator MUST sanitize exception messages before recording them on spans using `sanitize_error_message()`
- **FR-011**: floe-iceberg MUST migrate from its local `@traced` implementation to the unified one from floe-core

#### Error Sanitization

- **FR-012**: `sanitize_error_message()` MUST be a public function in `floe_core.telemetry` (promoted from floe-ingestion-dlt's private `_sanitize_message`)
- **FR-013**: All plugin `tracing.py` context managers MUST use `sanitize_error_message()` when recording exceptions on spans
- **FR-014**: `sanitize_error_message()` MUST redact URL credentials (`://user:pass@host`), key-value secrets (`password=`, `secret_key=`, `access_key=`, `token=`, `api_key=`), and truncate to 500 characters

#### Plugin Instrumentation Audit

- **FR-015**: `PluginMetadata` (or equivalent base) MUST include an optional `tracer_name` property that instrumented plugins override to return their tracer name string
- **FR-016**: A `verify_plugin_instrumentation()` function MUST exist that iterates loaded plugins and logs a structured warning for any plugin that does NOT report a tracer name
- **FR-017**: The instrumentation audit MUST run automatically during `floe compile` and emit structured warnings for uninstrumented plugins; it MUST also be callable programmatically via `verify_plugin_instrumentation()`

#### Span Semantic Conventions

- **FR-018**: Each plugin category MUST define semantic attribute constants with a consistent prefix: `alert.*`, `lineage.*`, `secrets.*`, `quality.*`, `compute.*`, `security.*`
- **FR-019**: All span context managers MUST set `FloeSpanAttributes` (floe.namespace, floe.product.name) in addition to domain-specific attributes, following the pattern established by floe-catalog-polaris

#### Testing

- **FR-020**: Every plugin with a `tracing.py` module MUST have a corresponding `test_tracing.py` (or `test_otel_tracing.py`) unit test using `InMemorySpanExporter`
- **FR-021**: Each tracing test MUST assert: span name, span status (OK/ERROR), domain-specific attributes, and error recording behavior
- **FR-022**: A contract test MUST verify that all registered plugins have a `tracer_name` (instrumentation completeness contract)
- **FR-023**: The unified `@traced` decorator MUST have tests covering: sync, async, static attributes, dynamic attributes, exception sanitization, and nested spans
- **FR-024**: A performance benchmark MUST verify that tracing overhead remains below 5% of operation time (extending existing `benchmarks/test_tracing_perf.py`)

### Key Entities

- **Plugin Tracing Module** (`tracing.py`): Per-plugin module containing a domain-specific span context manager, semantic attribute constants, and a `TRACER_NAME` constant. Follows the pattern established by floe-catalog-polaris.
- **Unified @traced Decorator**: Single decorator in `floe_core.telemetry.tracing` that replaces both the floe-core and floe-iceberg variants, supporting static and dynamic attributes plus async.
- **Instrumentation Audit**: Startup-time verification that all loaded plugins report a tracer name, logging warnings for any gaps.
- **sanitize_error_message()**: Public utility in `floe_core.telemetry` that strips credentials and PII from error messages before they are recorded on spans.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 19 of 21 plugins and 2 core packages have a dedicated tracing module with at least one span context manager (telemetry-console and telemetry-jaeger excluded to avoid infinite loop)
- **SC-002**: 100% of tracing modules have corresponding unit tests using `InMemorySpanExporter` that verify span names, attributes, and error recording
- **SC-003**: The unified `@traced` decorator is used by all packages — zero local `@traced` implementations remain
- **SC-004**: `sanitize_error_message()` is used by all span error recording — zero raw `span.record_exception(e)` calls remain outside the utility
- **SC-005**: The instrumentation audit reports zero warnings when all platform plugins are loaded
- **SC-006**: Tracing overhead benchmark passes (<5% latency increase) after all instrumentation is added
- **SC-007**: All new tracing tests use behavioral assertions (verify spans were created with correct attributes) not just return-value checks — zero Accomplishment Simulator patterns

## Assumptions

- Telemetry backend plugins (console, jaeger) do not need their own operational tracing — they ARE the telemetry system. Meta-tracing would create infinite loops.
- floe-dbt-fusion delegates to floe-dbt-core for most operations; it needs minimal additional tracing only for its fallback code paths.
- The `tracer_name` property on `PluginMetadata` is optional (not breaking) — existing plugins that don't implement it are flagged by audit but still function.
- YAML/manifest generation plugins (network-security-k8s, rbac-k8s) are lower priority but still need instrumentation for completeness and because generation failures must be traceable.
- The existing `InMemorySpanExporter` test pattern from floe-core is the standard for all plugin tracing tests.
