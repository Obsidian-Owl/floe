# Epic 6B: OpenLineage

## Summary

OpenLineage integration provides data lineage tracking across all floe pipelines. This is ENFORCED as the lineage standard - all data movements and transformations emit OpenLineage events for unified lineage graphs.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-06b-openlineage](https://linear.app/obsidianowl/project/floe-06b-openlineage-674cba04e924)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-520 | OpenLineage SDK integration | CRITICAL |
| REQ-521 | Run event emission | CRITICAL |
| REQ-522 | Dataset input/output tracking | CRITICAL |
| REQ-523 | Job facets | HIGH |
| REQ-524 | Dataset facets (schema, stats) | HIGH |
| REQ-525 | Run facets (parent, error) | HIGH |
| REQ-526 | HTTP transport configuration | CRITICAL |
| REQ-527 | Kafka transport configuration | MEDIUM |
| REQ-528 | Marquez integration | HIGH |
| REQ-529 | dbt lineage extraction | CRITICAL |
| REQ-530 | Dagster lineage extraction | CRITICAL |
| REQ-531 | Iceberg dataset facets | HIGH |
| REQ-532 | Column-level lineage | MEDIUM |
| REQ-533 | Custom facet definitions | MEDIUM |
| REQ-534 | Lineage visualization | MEDIUM |
| REQ-535 | Impact analysis | HIGH |
| REQ-536 | Root cause analysis | HIGH |
| REQ-537 | Lineage API | HIGH |
| REQ-538 | Event correlation with OTel | HIGH |
| REQ-539 | Namespace management | HIGH |
| REQ-540 | Lineage retention | MEDIUM |

---

## Architecture References

### ADRs
- [ADR-0030](../../../architecture/adr/0030-observability.md) - Observability architecture
- [ADR-0032](../../../architecture/adr/0032-openlineage-conventions.md) - OpenLineage conventions

### Contracts
- `LineageEmitter` - Lineage event emitter
- `RunEvent` - OpenLineage run event
- `DatasetEvent` - Dataset tracking event

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── lineage/
│   ├── __init__.py
│   ├── emitter.py               # LineageEmitter
│   ├── events.py                # Event builders
│   ├── facets.py                # Custom facets
│   ├── transport.py             # Transport configuration
│   └── extractors/
│       ├── __init__.py
│       ├── dbt.py               # dbt lineage extractor
│       └── dagster.py           # Dagster lineage extractor

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/lineage.py          # LineageBackendPlugin test fixtures
testing/k8s/services/marquez.yaml    # Marquez K8s manifest for integration tests
testing/tests/unit/test_lineage_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 4B | Extracts lineage from Dagster |
| Blocked By | Epic 5A | Extracts lineage from dbt |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
| Blocks | Epic 3D | Contract monitoring uses lineage |

---

## User Stories (for SpecKit)

### US1: Run Event Emission (P0)
**As a** platform operator
**I want** run events emitted for all pipelines
**So that** I can track pipeline executions

**Acceptance Criteria**:
- [ ] START event on run begin
- [ ] COMPLETE event on success
- [ ] FAIL event on failure
- [ ] Parent run tracking for nested runs

### US2: Dataset Tracking (P0)
**As a** data engineer
**I want** inputs and outputs tracked
**So that** I can see data flow

**Acceptance Criteria**:
- [ ] Input datasets identified
- [ ] Output datasets identified
- [ ] Schema facets included
- [ ] Iceberg snapshot facets included

### US3: dbt Lineage Extraction (P0)
**As a** data engineer
**I want** lineage extracted from dbt
**So that** SQL transformations are tracked

**Acceptance Criteria**:
- [ ] Model dependencies from manifest
- [ ] Source to model lineage
- [ ] Column-level lineage (when available)
- [ ] Test associations

### US4: Dagster Lineage Extraction (P1)
**As a** data engineer
**I want** lineage from Dagster assets
**So that** orchestration is captured

**Acceptance Criteria**:
- [ ] Asset dependencies captured
- [ ] Materialization events emitted
- [ ] Partition information included
- [ ] Run metadata included

### US5: OTel Correlation (P1)
**As a** platform operator
**I want** lineage events correlated with traces
**So that** I can link observability and lineage

**Acceptance Criteria**:
- [ ] Trace ID in lineage events
- [ ] Span ID in lineage events
- [ ] Unified correlation view
- [ ] Cross-system debugging

---

## Technical Notes

### Key Decisions
- OpenLineage is ENFORCED (not pluggable)
- HTTP transport is default, Kafka optional
- Marquez is recommended backend (but any OL consumer works)
- Namespace follows `floe.{environment}.{domain}` pattern

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Event volume | MEDIUM | MEDIUM | Sampling, batching |
| Backend availability | MEDIUM | LOW | Fire-and-forget, async |
| Schema complexity | MEDIUM | MEDIUM | Standard facets only |

### Test Strategy
- **Unit**: `packages/floe-core/tests/unit/test_lineage.py`
- **Integration**: `packages/floe-core/tests/integration/test_openlineage_emit.py`
- **Contract**: `tests/contract/test_lineage_contract.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/06-observability-lineage/`
- `docs/architecture/observability/`
- `packages/floe-core/src/floe_core/lineage/`

### Related Existing Code
- dbt manifest parsing from Epic 5A
- Dagster integration from Epic 4B

### External Dependencies
- `openlineage-python>=1.5.0`
- `marquez-python` (optional, for Marquez integration)
