# Epic 5B: Data Quality Plugin

## Summary

The DataQualityPlugin ABC defines the interface for data quality validation. It integrates with dbt tests, provides quality metrics collection, and supports pluggable quality frameworks like Great Expectations for advanced validation.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-05b-dataquality-plugin](https://linear.app/obsidianowl/project/floe-05b-dataquality-plugin-f4a912739ba9)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-066 | DataQualityPlugin ABC | CRITICAL |
| REQ-067 | dbt test integration | HIGH |
| REQ-068 | Great Expectations support | MEDIUM |
| REQ-069 | Quality metrics collection | HIGH |
| REQ-070 | Test result aggregation | HIGH |
| REQ-071 | Alert thresholds | MEDIUM |
| REQ-072 | Quality dashboards | MEDIUM |
| REQ-073 | Custom rule definition | MEDIUM |
| REQ-074 | Historical quality tracking | MEDIUM |
| REQ-075 | Quality gates enforcement | HIGH |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture
- [ADR-0025](../../../architecture/adr/0025-data-quality.md) - Data quality architecture

### Contracts
- `DataQualityPlugin` - Quality validation ABC
- `QualityResult` - Test result model
- `QualityMetrics` - Aggregated metrics model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_interfaces.py         # DataQualityPlugin ABC (shared)
└── plugins/
    └── quality/
        └── __init__.py

plugins/floe-quality-dbt/
├── src/floe_quality_dbt/
│   ├── __init__.py
│   ├── plugin.py                # DBTQualityPlugin
│   ├── tests.py                 # dbt test integration
│   ├── metrics.py               # Quality metrics
│   └── config.py                # Quality config
└── tests/
    ├── unit/
    └── integration/

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/quality.py          # DataQualityPlugin test fixtures
testing/fixtures/sample_expectations/  # Sample quality expectations for testing
testing/tests/unit/test_quality_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 5A | Wraps dbt test execution |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
| Blocks | Epic 3D | Contract monitoring uses quality metrics |
| Blocks | Epic 6A | Quality metrics exported to OTel |

---

## User Stories (for SpecKit)

### US1: DataQualityPlugin ABC (P0)
**As a** plugin developer
**I want** a clear ABC for quality plugins
**So that** I can implement alternative quality frameworks

**Acceptance Criteria**:
- [ ] `DataQualityPlugin.run_tests(tables)` defined
- [ ] `DataQualityPlugin.get_metrics(table)` defined
- [ ] `DataQualityPlugin.configure_alerts(config)` defined
- [ ] Configuration via Pydantic models

### US2: dbt Test Integration (P0)
**As a** data engineer
**I want** dbt tests as quality validation
**So that** I use familiar testing patterns

**Acceptance Criteria**:
- [ ] `DBTQualityPlugin` implements ABC
- [ ] dbt test results parsed
- [ ] Test failures mapped to quality events
- [ ] Integration with dbt test selection

### US3: Quality Metrics Collection (P1)
**As a** data engineer
**I want** quality metrics collected automatically
**So that** I can track quality over time

**Acceptance Criteria**:
- [ ] Row count metrics
- [ ] Null percentage metrics
- [ ] Freshness metrics
- [ ] Custom metric definitions

### US4: Quality Gates (P1)
**As a** platform operator
**I want** quality gates to block bad data
**So that** data quality issues are caught early

**Acceptance Criteria**:
- [ ] Configurable pass/fail thresholds
- [ ] Gate evaluation after dbt tests
- [ ] Failure blocks downstream assets
- [ ] Override capability for emergencies

---

## Technical Notes

### Key Decisions
- dbt tests are the primary quality mechanism
- Great Expectations is optional (for advanced use cases)
- Quality metrics are time-series data
- Quality gates are enforcement points, not monitoring

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test performance overhead | MEDIUM | MEDIUM | Sampling, parallel execution |
| False positive alerts | MEDIUM | HIGH | Tunable thresholds, calibration |
| Metric storage growth | MEDIUM | LOW | Retention policies, aggregation |

### Test Strategy
- **Unit**: `plugins/floe-quality-dbt/tests/unit/test_plugin.py`
- **Integration**: `plugins/floe-quality-dbt/tests/integration/test_quality_gates.py`
- **Contract**: `tests/contract/test_quality_plugin_abc.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/`
- `docs/architecture/quality/`
- `plugins/floe-quality-dbt/`

### Related Existing Code
- DBTPlugin from Epic 5A

### External Dependencies
- `dbt-core>=1.7.0`
- Optional: `great-expectations>=0.17.0`
