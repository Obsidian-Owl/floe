# Epic 6A: OpenTelemetry

## Summary

OpenTelemetry integration provides distributed tracing, metrics, and logging across all floe components. This is ENFORCED as the observability standard - all floe packages emit OTel telemetry for unified monitoring.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-06a-opentelemetry](https://linear.app/obsidianowl/project/floe-06a-opentelemetry-0e2e698e1f9b)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-500 | OpenTelemetry SDK integration | CRITICAL |
| REQ-501 | Trace context propagation | CRITICAL |
| REQ-502 | Span creation for key operations | HIGH |
| REQ-503 | Metric instrumentation | HIGH |
| REQ-504 | Log correlation with traces | HIGH |
| REQ-505 | OTLP exporter configuration | CRITICAL |
| REQ-506 | Sampling configuration | MEDIUM |
| REQ-507 | Resource attributes | HIGH |
| REQ-508 | Semantic conventions | HIGH |
| REQ-509 | Baggage propagation | MEDIUM |
| REQ-510 | Auto-instrumentation | MEDIUM |
| REQ-511 | Custom span attributes | HIGH |
| REQ-512 | Error tracking | HIGH |
| REQ-513 | Performance metrics | HIGH |
| REQ-514 | Dashboard templates | MEDIUM |
| REQ-515 | Alert templates | MEDIUM |
| REQ-516 | Trace visualization | MEDIUM |
| REQ-517 | Metric aggregation | MEDIUM |
| REQ-518 | Log aggregation | MEDIUM |
| REQ-519 | Correlation identifiers | HIGH |

---

## Architecture References

### ADRs
- [ADR-0030](../../../architecture/adr/0030-observability.md) - Observability architecture
- [ADR-0031](../../../architecture/adr/0031-otel-conventions.md) - OpenTelemetry conventions

### Contracts
- `TelemetryProvider` - Telemetry configuration
- `SpanContext` - Trace context wrapper
- `MetricRecorder` - Metric recording interface

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── telemetry/
│   ├── __init__.py
│   ├── provider.py              # TelemetryProvider
│   ├── tracing.py               # Tracing utilities
│   ├── metrics.py               # Metric recording
│   ├── logging.py               # Log correlation
│   ├── propagation.py           # Context propagation
│   └── conventions.py           # Semantic conventions

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/telemetry.py        # TelemetryBackendPlugin test fixtures
testing/k8s/services/jaeger.yaml     # Jaeger K8s manifest for integration tests
testing/tests/unit/test_telemetry_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry for configuration |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
| Blocks | Epic 3D | Contract monitoring uses OTel metrics |
| Blocks | Epic 4B | Dagster emits OTel traces |
| Blocks | Epic 6B | OpenLineage correlates with OTel traces |
| Blocks | Epic 9B | Helm charts configure OTel collectors |

---

## User Stories (for SpecKit)

### US1: Trace Context Propagation (P0)
**As a** platform operator
**I want** traces propagated across services
**So that** I can follow requests end-to-end

**Acceptance Criteria**:
- [ ] W3C Trace Context headers propagated
- [ ] Baggage headers propagated
- [ ] Context available in all floe packages
- [ ] Cross-process correlation works

### US2: Span Creation (P0)
**As a** platform operator
**I want** spans for key operations
**So that** I can see what's happening in pipelines

**Acceptance Criteria**:
- [ ] Compilation spans
- [ ] dbt run/test spans
- [ ] Dagster asset materialization spans
- [ ] Custom attributes on spans

### US3: Metric Instrumentation (P1)
**As a** platform operator
**I want** metrics exported via OTel
**So that** I can monitor system health

**Acceptance Criteria**:
- [ ] Pipeline run duration
- [ ] Asset materialization count
- [ ] Error rate by component
- [ ] Resource utilization metrics

### US4: OTLP Exporter Configuration (P1)
**As a** platform operator
**I want** configurable OTel exporters
**So that** I can send telemetry to my backend

**Acceptance Criteria**:
- [ ] OTLP/gRPC exporter
- [ ] OTLP/HTTP exporter
- [ ] Endpoint configuration from manifest
- [ ] Authentication support

### US5: Log Correlation (P2)
**As a** platform operator
**I want** logs correlated with traces
**So that** I can debug issues efficiently

**Acceptance Criteria**:
- [ ] Trace ID in log records
- [ ] Span ID in log records
- [ ] Structured logging format
- [ ] Log level configuration

---

## Technical Notes

### Key Decisions
- OpenTelemetry is ENFORCED (not pluggable)
- OTLP is the only supported export format
- Semantic conventions follow OTel data conventions
- Sampling configurable per-environment

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Telemetry overhead | MEDIUM | MEDIUM | Sampling, async export |
| Backend compatibility | LOW | MEDIUM | OTLP standard format |
| Context loss | MEDIUM | HIGH | Comprehensive propagation |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_telemetry.py`
- **Integration**: `packages/floe-core/tests/integration/test_otel_export.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/06-observability-lineage/`
- `docs/architecture/observability/`
- `packages/floe-core/src/floe_core/telemetry/`

### Related Existing Code
- None (greenfield)

### External Dependencies
- `opentelemetry-api>=1.20.0`
- `opentelemetry-sdk>=1.20.0`
- `opentelemetry-exporter-otlp>=1.20.0`
