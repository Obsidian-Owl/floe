# Tasks: OpenTelemetry Integration

**Input**: Design documents from `/specs/001-opentelemetry/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included using TDD approach per project standards.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Core telemetry**: `packages/floe-core/src/floe_core/telemetry/`
- **Plugin ABC**: `packages/floe-core/src/floe_core/interfaces/`
- **Backend plugins**: `plugins/floe-telemetry-*/`
- **Unit tests**: `packages/floe-core/tests/unit/test_telemetry/`
- **Integration tests**: `packages/floe-core/tests/integration/`
- **Contract tests**: `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and telemetry module structure

- [ ] T001 Create telemetry module directory structure: `packages/floe-core/src/floe_core/telemetry/`
- [ ] T002 Add OpenTelemetry dependencies to pyproject.toml: `opentelemetry-api>=1.20.0`, `opentelemetry-sdk>=1.20.0`, `opentelemetry-exporter-otlp-proto-grpc>=1.20.0`, `opentelemetry-exporter-otlp-proto-http>=1.20.0`
- [ ] T003 [P] Copy contract models from specs to implementation: `packages/floe-core/src/floe_core/telemetry/config.py` (from contracts/telemetry_config.py)
- [ ] T004 [P] Copy span attributes from specs to implementation: `packages/floe-core/src/floe_core/telemetry/conventions.py` (from contracts/span_attributes.py)
- [ ] T005 [P] Create TelemetryBackendPlugin ABC in `packages/floe-core/src/floe_core/interfaces/telemetry_backend.py`
- [ ] T006 Create telemetry module `__init__.py` with public API exports in `packages/floe-core/src/floe_core/telemetry/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

- [ ] T007 [P] Unit test for TelemetryConfig validation in `packages/floe-core/tests/unit/test_telemetry/test_config.py`
- [ ] T008 [P] Unit test for ResourceAttributes.to_otel_dict() in `packages/floe-core/tests/unit/test_telemetry/test_config.py`
- [ ] T009 [P] Unit test for SamplingConfig.get_ratio() in `packages/floe-core/tests/unit/test_telemetry/test_config.py`
- [ ] T010 [P] Contract test for TelemetryBackendPlugin ABC in `tests/contract/test_telemetry_backend_contract.py`

### Implementation for Foundational Phase

- [ ] T011 Implement TelemetryProvider class in `packages/floe-core/src/floe_core/telemetry/provider.py` (SDK initialization, graceful shutdown)
- [ ] T012 [P] Implement no-op mode detection via OTEL_SDK_DISABLED in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T013 [P] Unit test for TelemetryProvider initialization and shutdown in `packages/floe-core/tests/unit/test_telemetry/test_provider.py`
- [ ] T014 Unit test for no-op mode (OTEL_SDK_DISABLED=true) in `packages/floe-core/tests/unit/test_telemetry/test_provider.py`

**Checkpoint**: Foundation ready - TelemetryProvider can initialize SDK with config, user story implementation can now begin

---

## Phase 3: User Story 1 - Trace Context Propagation (Priority: P0) 🎯 MVP

**Goal**: Enable W3C Trace Context and Baggage propagation across all floe services

**Independent Test**: Trigger a multi-service operation and verify all spans share the same trace ID

### Tests for User Story 1

- [ ] T015 [P] [US1] Unit test for W3C propagator setup in `packages/floe-core/tests/unit/test_telemetry/test_propagation.py`
- [ ] T016 [P] [US1] Unit test for Baggage propagation (floe.namespace) in `packages/floe-core/tests/unit/test_telemetry/test_propagation.py`
- [ ] T017 [P] [US1] Unit test for trace context injection/extraction in `packages/floe-core/tests/unit/test_telemetry/test_propagation.py`
- [ ] T018 [US1] Integration test for cross-service propagation in `packages/floe-core/tests/integration/test_otel_propagation.py`

### Implementation for User Story 1

- [ ] T019 [US1] Implement propagation module with W3C Trace Context + Baggage in `packages/floe-core/src/floe_core/telemetry/propagation.py`
- [ ] T020 [US1] Add setup_propagators() function to configure global propagators in `packages/floe-core/src/floe_core/telemetry/propagation.py`
- [ ] T021 [US1] Add inject_context() and extract_context() helpers in `packages/floe-core/src/floe_core/telemetry/propagation.py`
- [ ] T022 [US1] Add set_floe_baggage() helper for floe.namespace propagation in `packages/floe-core/src/floe_core/telemetry/propagation.py`
- [ ] T023 [US1] Integrate propagator setup into TelemetryProvider.initialize() in `packages/floe-core/src/floe_core/telemetry/provider.py`

**Checkpoint**: W3C Trace Context and Baggage propagate across service boundaries (FR-002, FR-003, FR-007a)

---

## Phase 4: User Story 2 - Span Creation for Key Operations (Priority: P0)

**Goal**: Automatic span creation for compilation, dbt, and Dagster operations with Floe semantic conventions

**Independent Test**: Run a compilation/pipeline and verify spans are created with names, timing, and attributes

### Tests for User Story 2

- [ ] T024 [P] [US2] Unit test for @traced decorator in `packages/floe-core/tests/unit/test_telemetry/test_tracing.py`
- [ ] T025 [P] [US2] Unit test for create_span() context manager in `packages/floe-core/tests/unit/test_telemetry/test_tracing.py`
- [ ] T026 [P] [US2] Unit test for FloeSpanAttributes.to_otel_dict() in `packages/floe-core/tests/unit/test_telemetry/test_conventions.py`
- [ ] T027 [P] [US2] Unit test for error recording on spans in `packages/floe-core/tests/unit/test_telemetry/test_tracing.py`
- [ ] T028 [US2] Integration test for span creation with real OTel SDK in `packages/floe-core/tests/integration/test_otel_tracing.py`

### Implementation for User Story 2

- [ ] T029 [US2] Implement tracing module with @traced decorator in `packages/floe-core/src/floe_core/telemetry/tracing.py`
- [ ] T030 [US2] Implement create_span() context manager in `packages/floe-core/src/floe_core/telemetry/tracing.py`
- [ ] T031 [US2] Implement get_current_span() helper in `packages/floe-core/src/floe_core/telemetry/tracing.py`
- [ ] T032 [US2] Implement record_exception() helper for error recording in `packages/floe-core/src/floe_core/telemetry/tracing.py`
- [ ] T033 [US2] Add Floe semantic attribute injection to spans in `packages/floe-core/src/floe_core/telemetry/tracing.py`
- [ ] T034 [US2] Add child span support with proper parent context in `packages/floe-core/src/floe_core/telemetry/tracing.py`

**Checkpoint**: Spans created for operations with floe.namespace, floe.product.name, floe.product.version, floe.mode (FR-004 through FR-007d, FR-022)

---

## Phase 5: User Story 3 - OTLP Exporter Configuration (Priority: P1)

**Goal**: Configure OTLP export to user's observability backend with authentication support

**Independent Test**: Configure OTLP endpoint in manifest, verify traces appear in backend

### Tests for User Story 3

- [ ] T035 [P] [US3] Unit test for BatchSpanProcessor configuration in `packages/floe-core/tests/unit/test_telemetry/test_provider.py`
- [ ] T036 [P] [US3] Unit test for OTLP/gRPC exporter setup in `packages/floe-core/tests/unit/test_telemetry/test_provider.py`
- [ ] T037 [P] [US3] Unit test for OTLP/HTTP exporter setup in `packages/floe-core/tests/unit/test_telemetry/test_provider.py`
- [ ] T038 [P] [US3] Unit test for TelemetryAuth header injection in `packages/floe-core/tests/unit/test_telemetry/test_config.py`
- [ ] T039 [US3] Integration test for OTLP export to collector in `packages/floe-core/tests/integration/test_otel_export.py`

### Implementation for User Story 3

- [ ] T040 [US3] Implement OTLP/gRPC exporter configuration in TelemetryProvider in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T041 [US3] Implement OTLP/HTTP exporter configuration in TelemetryProvider in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T042 [US3] Implement authentication header injection (api_key, bearer) in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T043 [US3] Implement BatchSpanProcessor with configurable queue sizes in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T044 [US3] Add async export (non-blocking) verification in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T045 [US3] Implement graceful degradation when backend unavailable in `packages/floe-core/src/floe_core/telemetry/provider.py`

**Checkpoint**: Telemetry exports to configured OTLP endpoint with authentication (FR-008 through FR-011, FR-024)

---

## Phase 6: User Story 4 - Metric Instrumentation (Priority: P1)

**Goal**: Export key operational metrics (duration, counts, error rates) via OTLP

**Independent Test**: Run pipelines and verify metrics appear in backend with correct values and labels

### Tests for User Story 4

- [ ] T046 [P] [US4] Unit test for MetricRecorder.increment() in `packages/floe-core/tests/unit/test_telemetry/test_metrics.py`
- [ ] T047 [P] [US4] Unit test for MetricRecorder.set_gauge() in `packages/floe-core/tests/unit/test_telemetry/test_metrics.py`
- [ ] T048 [P] [US4] Unit test for MetricRecorder.record_histogram() in `packages/floe-core/tests/unit/test_telemetry/test_metrics.py`
- [ ] T049 [P] [US4] Unit test for metric labels/attributes in `packages/floe-core/tests/unit/test_telemetry/test_metrics.py`
- [ ] T050 [US4] Integration test for metric export to OTLP in `packages/floe-core/tests/integration/test_otel_metrics.py`

### Implementation for User Story 4

- [ ] T051 [US4] Implement MetricRecorder class in `packages/floe-core/src/floe_core/telemetry/metrics.py`
- [ ] T052 [US4] Implement increment() for counter metrics in `packages/floe-core/src/floe_core/telemetry/metrics.py`
- [ ] T053 [US4] Implement set_gauge() for gauge metrics in `packages/floe-core/src/floe_core/telemetry/metrics.py`
- [ ] T054 [US4] Implement record_histogram() for duration metrics in `packages/floe-core/src/floe_core/telemetry/metrics.py`
- [ ] T055 [US4] Add MeterProvider setup to TelemetryProvider in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T056 [US4] Add metric export to OTLP endpoint in `packages/floe-core/src/floe_core/telemetry/provider.py`

**Checkpoint**: Pipeline duration, asset counts, error rates exported as metrics (FR-012 through FR-014)

---

## Phase 7: User Story 5 - Log Correlation with Traces (Priority: P2)

**Goal**: Inject trace_id and span_id into log entries for debugging correlation

**Independent Test**: Generate logs during traced operation, verify log entries contain trace_id and span_id

### Tests for User Story 5

- [ ] T057 [P] [US5] Unit test for structlog trace context processor in `packages/floe-core/tests/unit/test_telemetry/test_logging.py`
- [ ] T058 [P] [US5] Unit test for trace_id injection in `packages/floe-core/tests/unit/test_telemetry/test_logging.py`
- [ ] T059 [P] [US5] Unit test for span_id injection in `packages/floe-core/tests/unit/test_telemetry/test_logging.py`
- [ ] T060 [US5] Integration test for log-trace correlation in `packages/floe-core/tests/integration/test_otel_logging.py`

### Implementation for User Story 5

- [ ] T061 [US5] Implement add_trace_context structlog processor in `packages/floe-core/src/floe_core/telemetry/logging.py`
- [ ] T062 [US5] Implement configure_logging() with trace context injection in `packages/floe-core/src/floe_core/telemetry/logging.py`
- [ ] T063 [US5] Add JSON output format with trace_id, span_id fields in `packages/floe-core/src/floe_core/telemetry/logging.py`
- [ ] T064 [US5] Integrate logging setup into TelemetryProvider in `packages/floe-core/src/floe_core/telemetry/provider.py`
- [ ] T065 [US5] Add log level configuration support in `packages/floe-core/src/floe_core/telemetry/logging.py`

**Checkpoint**: Logs include trace_id, span_id when within traced context (FR-015 through FR-018)

---

## Phase 8: Backend Plugins (Three-Layer Architecture)

**Purpose**: Implement pluggable backend plugins per FR-025 through FR-030

### Tests for Backend Plugins

- [ ] T066 [P] Unit test for ConsoleTelemetryPlugin in `plugins/floe-telemetry-console/tests/test_plugin.py`
- [ ] T067 [P] Unit test for JaegerTelemetryPlugin in `plugins/floe-telemetry-jaeger/tests/test_plugin.py`
- [ ] T068 Contract test for plugin ABC compliance in `tests/contract/test_telemetry_backend_contract.py`

### Implementation for Backend Plugins

- [ ] T069 Create console plugin package structure `plugins/floe-telemetry-console/`
- [ ] T070 [P] Implement ConsoleTelemetryPlugin in `plugins/floe-telemetry-console/src/floe_telemetry_console/plugin.py`
- [ ] T071 [P] Add entry point to console plugin pyproject.toml: `floe.telemetry_backends`
- [ ] T072 Create Jaeger plugin package structure `plugins/floe-telemetry-jaeger/`
- [ ] T073 [P] Implement JaegerTelemetryPlugin in `plugins/floe-telemetry-jaeger/src/floe_telemetry_jaeger/plugin.py`
- [ ] T074 [P] Add entry point to Jaeger plugin pyproject.toml: `floe.telemetry_backends`
- [ ] T075 Implement plugin loading via entry points in `packages/floe-core/src/floe_core/telemetry/provider.py`

**Checkpoint**: Backend plugins selectable via manifest.yaml, no code changes required (FR-027, FR-029, FR-030)

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T076 [P] Add TelemetryConfig to CompiledArtifacts schema in `packages/floe-core/src/floe_core/schemas.py`
- [ ] T077 Update manifest.yaml schema to include `plugins.telemetry_backend` in `packages/floe-core/src/floe_core/manifest.py`
- [ ] T078 [P] Add docstrings to all public APIs per Google style
- [ ] T079 [P] Add type hints and run mypy --strict on telemetry module
- [ ] T080 Run quickstart.md validation scenarios
- [ ] T081 Performance validation: verify <5% latency overhead (SC-004)
- [ ] T082 [P] Add telemetry module to floe-core public exports in `packages/floe-core/src/floe_core/__init__.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P0) and US2 (P0) can proceed in parallel after Foundational
  - US3 (P1) and US4 (P1) can proceed in parallel, may need US1/US2 for full integration
  - US5 (P2) can proceed independently after Foundational
- **Backend Plugins (Phase 8)**: Depends on Phase 5 (OTLP export) for integration testing
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Priority | Can Start After | Dependencies |
|-------|----------|-----------------|--------------|
| US1 - Trace Propagation | P0 | Foundational | None |
| US2 - Span Creation | P0 | Foundational | None (integrates with US1 but independently testable) |
| US3 - OTLP Export | P1 | Foundational | None (requires US1/US2 spans to export) |
| US4 - Metrics | P1 | Foundational | None (independent signal) |
| US5 - Log Correlation | P2 | Foundational | None (integrates with US2 spans but independently testable) |

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Config models before providers
- Providers before integrations
- Core implementation before polish
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
- T003, T004, T005 can run in parallel (different files)

**Phase 2 (Foundational)**:
- T007, T008, T009, T010 can run in parallel (test files)
- T012, T013 can run in parallel (different aspects of provider)

**User Stories**:
- US1 and US2 can be worked on in parallel by different developers
- US3 and US4 can be worked on in parallel after P0 stories
- All test tasks within a story marked [P] can run in parallel

**Phase 8 (Plugins)**:
- T066, T067 can run in parallel (different plugin tests)
- T070, T071, T073, T074 can run in parallel (different plugin packages)

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task: "T024 [P] [US2] Unit test for @traced decorator"
Task: "T025 [P] [US2] Unit test for create_span() context manager"
Task: "T026 [P] [US2] Unit test for FloeSpanAttributes.to_otel_dict()"
Task: "T027 [P] [US2] Unit test for error recording on spans"
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Trace Propagation
4. Complete Phase 4: US2 - Span Creation
5. **STOP and VALIDATE**: Test US1/US2 independently
6. Deploy/demo with console exporter

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (Trace Propagation) → Test independently → MVP tracing!
3. Add US2 (Span Creation) → Test independently → Full P0 tracing
4. Add US3 (OTLP Export) → Test independently → Production export
5. Add US4 (Metrics) → Test independently → Full observability
6. Add US5 (Log Correlation) → Test independently → Complete integration
7. Add Backend Plugins → Test independently → Pluggable backends

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (Trace Propagation) + US3 (OTLP Export)
   - Developer B: US2 (Span Creation) + US5 (Log Correlation)
   - Developer C: US4 (Metrics) + Backend Plugins
3. Stories complete and integrate independently

---

## Requirement Traceability

| Task Range | User Story | Requirements Covered |
|------------|------------|----------------------|
| T001-T006 | Setup | Project structure |
| T007-T014 | Foundational | FR-001, FR-023 |
| T015-T023 | US1 | FR-002, FR-003, FR-007a |
| T024-T034 | US2 | FR-004, FR-005, FR-006, FR-007, FR-007b-d, FR-019, FR-020, FR-022 |
| T035-T045 | US3 | FR-008, FR-009, FR-010, FR-011, FR-024, FR-026 |
| T046-T056 | US4 | FR-012, FR-013, FR-014 |
| T057-T065 | US5 | FR-015, FR-016, FR-017, FR-018 |
| T066-T075 | Plugins | FR-025, FR-027, FR-028, FR-029, FR-030 |
| T076-T082 | Polish | FR-021, SC-004 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All tests MUST use `@pytest.mark.requirement()` decorator
