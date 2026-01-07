# Domain 06: Observability and Lineage

**Priority**: CRITICAL
**Total Requirements**: 31
**Status**: Complete specification

## Overview

This domain defines observability (tracing, metrics, logs) and data lineage standards that enable monitoring, debugging, and compliance across the platform. Observability is a first-class requirement enforced through OpenTelemetry SDK integration and OpenLineage event emission.

**Core Architectural Principles**:
- **Vendor-neutral observability** (ADR-0006) - OpenTelemetry SDK for traces, metrics, logs
- **Standard lineage** (ADR-0007) - OpenLineage for data lineage events
- **Namespace context** - Every span and lineage event includes `floe.namespace`
- **Layered architecture** - Emission (enforced) → Collection (enforced) → Backend (pluggable)

## Observability Types (2 Total)

| Capability | Component | Purpose | Requirements |
|------------|-----------|---------|--------------|
| Distributed Tracing | OpenTelemetry SDK | Request flow tracking across services | REQ-500 to REQ-515 |
| Data Lineage | OpenLineage | Input/output tracking, impact analysis | REQ-516 to REQ-530 |

## Key Architectural Decisions

- **ADR-0006**: OpenTelemetry standard for vendor-neutral observability
- **ADR-0007**: OpenLineage for standard data lineage
- **ADR-0035**: ObservabilityPlugin interface for pluggable backends (Jaeger, Datadog, Grafana Cloud)
- **ADR-0019**: OTLP Collector as central collection point

## Requirements Files

- [01-opentelemetry.md](01-opentelemetry.md) - REQ-500 to REQ-515: OTel SDK, traces, metrics, logs
- [02-openlineage.md](02-openlineage.md) - REQ-516 to REQ-530: OpenLineage events, namespace strategy

## Traceability Matrix

| Requirement Range | ADR | Architecture Doc | Test Spec |
|------------------|-----|------------------|-----------|
| REQ-500 to REQ-515 | ADR-0006, ADR-0035 | four-layer-overview.md, platform-services.md | tests/contract/test_observability_otel.py |
| REQ-516 to REQ-530 | ADR-0007, ADR-0035 | lineage-architecture.md | tests/contract/test_openlineage.py |

## Epic Mapping

This domain's requirements are satisfied across Epics:

- **Epic 3: Plugin Interfaces** (Phase 3A/3B)
  - REQ-500 to REQ-515: OTel SDK integration
  - REQ-516 to REQ-530: OpenLineage event emission

- **Epic 6: OCI Registry** (Phase 4B)
  - Observability configuration distribution (OTLP Collector config)

- **Epic 7: Enforcement Engine** (Phase 5A/5B)
  - Observability requirement enforcement (all pipelines MUST emit OTel)
  - Lineage requirement enforcement (all pipelines MUST emit OpenLineage)

## Validation Criteria

Domain 06 is complete when:

- [ ] All 31 requirements documented with complete template fields
- [ ] OTel SDK integration tested across all Layer 3/4 components
- [ ] OTLP Collector deployment validated in Kind cluster
- [ ] OpenLineage event emission tested end-to-end
- [ ] Lineage namespace strategy enforced in floe.yaml validation
- [ ] Contract tests validate OTel baggage and trace context propagation
- [ ] Contract tests validate OpenLineage event schema compliance
- [ ] ADRs backreference requirements
- [ ] Architecture docs backreference requirements
- [ ] Test coverage > 80% for observability infrastructure

## Notes

- **Backward Compatibility**: Observability is additive, no breaking changes to existing APIs
- **Enforce-by-Default**: All pipelines MUST emit OTel and OpenLineage events (enforcement engine validates)
- **Pluggable Backends**: ObservabilityPlugin interface enables Jaeger, Datadog, Grafana Cloud backend selection
- **Namespace Propagation**: `floe.namespace` MUST be set on all traces and lineage events for filtering by data product

## Layer 3/4 Integration

**Layer 3 (Services)**:
- OTLP Collector deployment (OpenTelemetry collector)
- Observability plugin deployment (e.g., Jaeger, Prometheus, Grafana)
- Service mesh instrumentation (optional, e.g., Istio)

**Layer 4 (Data/Jobs)**:
- dbt run jobs emit OTel traces (via dbtRunner instrumentation)
- dlt ingestion jobs emit OTel traces (via dlt SDK)
- Quality check jobs emit OTel traces (custom instrumentation)
- All jobs emit OpenLineage events (via LineageEmitter)

## References

- **ADR-0006**: OpenTelemetry for Observability
- **ADR-0007**: OpenLineage from Start
- **ADR-0035**: Observability Plugin Interface
- **ADR-0019**: Platform Services Lifecycle
- **four-layer-overview.md**: Architecture model
- **platform-services.md**: Service layer specifications
