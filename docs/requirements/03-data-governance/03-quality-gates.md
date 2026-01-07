# REQ-241 to REQ-250: Quality Gates and Runtime Monitoring

**Domain**: Data Governance
**Priority**: CRITICAL
**Status**: Complete specification

## Overview

This group of requirements defines quality gate validation, runtime SLA monitoring, and the ContractMonitor service that enforces data quality and contract compliance during pipeline execution.

**Key Principle**: Quality gates block non-compliant pipelines; ContractMonitor alerts on runtime violations (ADR-0012, ADR-0028)

## Requirements

### REQ-241: Quality Gate Validation via DataQualityPlugin **[New]**

**Requirement**: System MUST use DataQualityPlugin.validate_quality_gates() for pluggable quality gate enforcement at compile-time.

**Rationale**: Unified quality plugin interface enables custom quality gate implementations through composable plugins.

**Acceptance Criteria**:
- [ ] DataQualityPlugin ABC includes validate_quality_gates() method
- [ ] Method receives: dbt manifest, required_coverage dict (bronze/silver/gold thresholds)
- [ ] Returns: ValidationResult with pass/fail and detailed coverage statistics
- [ ] Quality plugins pluggable via entry points (floe.data_quality)
- [ ] PluginMetadata includes name, version, floe_api_version
- [ ] Platform config: plugins.data_quality.provider (single choice)

**Enforcement**:
- Interface validation tests
- Plugin loading tests
- Quality gate execution tests

**Constraints**:
- MUST use DataQualityPlugin interface (not separate QualityGateValidator)
- MUST define quality gate validation method
- FORBIDDEN to hardcode quality checks
- MUST support custom validators via plugins

**Test Coverage**:
- `tests/contract/test_data_quality_plugin.py`
- `plugins/floe-dq-*/tests/unit/test_quality_gates.py`

**Traceability**:
- ADR-0044 (Unified Data Quality Plugin Architecture)
- ADR-0012 (Data Classification and Governance) lines 211-244

**Files to Reference**:
- `floe-core/src/floe_core/plugin_interfaces/data_quality.py` - DataQualityPlugin ABC

---

### REQ-242: Compile-Time Quality Gate Validation **[New]**

**Requirement**: Compiler MUST invoke DataQualityPlugin.validate_quality_gates() during `floe compile` to enforce quality thresholds.

**Rationale**: Prevents non-compliant pipelines from being deployed through early validation.

**Acceptance Criteria**:
- [ ] Quality gates loaded from platform-manifest.yaml (plugins.data_quality.config)
- [ ] Compiler calls DataQualityPlugin.validate_quality_gates() after dbt manifest parsing
- [ ] Stateless validation only (no data access at compile-time)
- [ ] Gate violations reported with severity and remediation
- [ ] Compilation fails in strict mode if gates fail
- [ ] Per-layer quality requirements supported (bronze, silver, gold)
- [ ] Enforcement level configurable per gate

**Enforcement**:
- Gate loading tests
- Validation execution tests
- Compilation outcome tests

**Constraints**:
- MUST load all gates from manifest
- MUST validate before artifact generation
- FORBIDDEN to skip gates in strict mode
- MUST report all violations
- MUST NOT access data at compile-time (config validation only)

**Test Coverage**: `tests/integration/test_compile_quality_gates.py`

**Traceability**:
- ADR-0044 (Unified Data Quality Plugin Architecture)
- ADR-0012 (Data Classification and Governance) lines 305-331
- REQ-202 (Compile-Time Policy Validation Hook)

---

### REQ-243: Test Coverage Quality Gate **[New]**

**Requirement**: System MUST enforce minimum dbt test coverage per layer via quality gate.

**Rationale**: Ensures data quality through comprehensive testing.

**Acceptance Criteria**:
- [ ] Test coverage calculated: tested_columns / total_columns
- [ ] Layer-specific minimums: bronze (50%), silver (80%), gold (100%)
- [ ] Coverage excludes technical columns (id, created_at if not tested)
- [ ] Reports which columns lack tests
- [ ] Suggests test types (not_null, unique, freshness)
- [ ] Enforcement level: off, warn, strict

**Enforcement**:
- Coverage calculation tests
- Per-layer tests
- Suggestion generation tests

**Constraints**:
- MUST calculate coverage accurately
- MUST exclude technical columns (if configured)
- FORBIDDEN to allow gold layers with <100% coverage in strict mode
- MUST suggest remediation

**Test Coverage**: `tests/unit/test_coverage_quality_gate.py`

**Traceability**:
- REQ-216 (Test Coverage Enforcement)
- ADR-0012 (Data Classification and Governance)

---

### REQ-244: Documentation Quality Gate **[New]**

**Requirement**: System MUST enforce documentation requirements via quality gate.

**Rationale**: Documentation is compliance artifact.

**Acceptance Criteria**:
- [ ] Validates model descriptions exist
- [ ] Validates column descriptions for PII/classified columns
- [ ] Gold layers require 100% column documentation
- [ ] Rejects empty descriptions ("TBD", "TODO")
- [ ] Reports missing documentation
- [ ] Enforcement level: off, warn, strict

**Enforcement**:
- Documentation validation tests
- Description quality tests
- Layer-specific tests

**Constraints**:
- MUST require documentation for gold layers
- FORBIDDEN to allow empty descriptions
- MUST validate dbt YAML structure
- MUST support custom description requirements

**Test Coverage**: `tests/unit/test_documentation_quality_gate.py`

**Traceability**:
- REQ-217 (Documentation Validation)

---

### REQ-245: ContractMonitor Kubernetes Service **[New]**

**Requirement**: System MUST deploy ContractMonitor as long-lived Kubernetes service (Layer 3) for runtime monitoring.

**Rationale**: Enables continuous SLA monitoring without job execution.

**Acceptance Criteria**:
- [ ] ContractMonitor deployed as K8s Deployment (not Job)
- [ ] Deployment includes: replica count, resource requests, probes
- [ ] Helm chart: charts/floe-platform/templates/contract-monitor
- [ ] Service discovery via Kubernetes DNS (contract-monitor.floe-system.svc.cluster.local)
- [ ] Persistent state: PostgreSQL backend for contract history
- [ ] Scheduled monitoring configured via platform-manifest

**Enforcement**:
- Helm chart validation tests
- K8s deployment tests
- Service discovery tests

**Constraints**:
- MUST run as Deployment (Layer 3)
- MUST use persistent backend
- FORBIDDEN to run as batch Job
- MUST support horizontal scaling

**Test Coverage**: `tests/integration/test_contract_monitor_deployment.py`

**Traceability**:
- ADR-0016 (Platform Enforcement Architecture) lines 146-201
- ADR-0019 (Platform Services Lifecycle)
- ADR-0028 (Runtime Contract Monitoring)

**Files to Create**:
- `charts/floe-platform/templates/contract-monitor/deployment.yaml`
- `charts/floe-platform/templates/contract-monitor/service.yaml`
- `floe-core/src/floe_core/contract_monitor.py` - ContractMonitor service

---

### REQ-246: Freshness SLA Monitoring **[New]**

**Requirement**: ContractMonitor MUST periodically check data freshness against contract SLAs.

**Rationale**: Detects stale data that violates SLAs.

**Acceptance Criteria**:
- [ ] Freshness check interval: 15 minutes (configurable)
- [ ] Compares table's latest_update to current_time
- [ ] Compares against contract slaProperties.freshness
- [ ] Violations emitted as FAIL events (OpenLineage)
- [ ] Violations logged with table, SLA, age
- [ ] Support multiple timestamp column detection

**Enforcement**:
- Freshness calculation tests
- SLA comparison tests
- Event emission tests

**Constraints**:
- MUST check at configured interval
- MUST NOT block data access on violation
- FORBIDDEN to require manual intervention
- MUST support custom timestamp columns

**Test Coverage**: `tests/integration/test_freshness_monitoring.py`

**Traceability**:
- data-contracts.md lines 224-230
- ADR-0028 (Runtime Contract Monitoring)

---

### REQ-247: Schema Drift Monitoring **[New]**

**Requirement**: ContractMonitor MUST periodically detect schema drift between contract and actual table.

**Rationale**: Identifies unplanned schema evolution that violates contracts.

**Acceptance Criteria**:
- [ ] Schema drift check interval: 1 hour (configurable)
- [ ] Queries table schema via compute engine
- [ ] Compares against contract schema definition
- [ ] Detects: added columns, removed columns, type changes, constraint changes
- [ ] Violations emitted as FAIL events (OpenLineage)
- [ ] Reports actual vs expected schema

**Enforcement**:
- Schema extraction tests
- Drift detection tests
- Event emission tests

**Constraints**:
- MUST compare against actual schema
- MUST detect all schema changes
- FORBIDDEN to silently accept schema drift
- MUST support different compute targets

**Test Coverage**: `tests/integration/test_schema_drift_monitoring.py`

**Traceability**:
- REQ-229 (Contract Schema Drift Detection)
- ADR-0028 (Runtime Contract Monitoring)

---

### REQ-248: Quality Monitoring via DataQualityPlugin **[New]**

**Requirement**: ContractMonitor MUST execute DataQualityPlugin.execute_checks() for runtime data quality validation.

**Rationale**: Detects quality degradation at runtime through pluggable quality framework.

**Acceptance Criteria**:
- [ ] Quality check interval: 6 hours (configurable)
- [ ] ContractMonitor calls DataQualityPlugin.execute_checks() with database connection
- [ ] Passes configured expectations from data product
- [ ] Reports: row count, null %, uniqueness, value distributions (implementation-specific)
- [ ] Violations emitted as FAIL events (OpenLineage via get_lineage_emitter())
- [ ] Quality score calculated via DataQualityPlugin.calculate_quality_score()
- [ ] Weighted scoring: combines dbt tests + DQ plugin checks + custom checks
- [ ] Support threshold-based alerts

**Enforcement**:
- DataQualityPlugin integration tests
- Quality calculation tests
- Event emission tests
- ContractMonitor invocation tests

**Constraints**:
- MUST use DataQualityPlugin.execute_checks() (not direct GX calls)
- MUST execute stateful checks (require data access)
- MUST NOT block on violations
- FORBIDDEN to allow quality degradation silently
- MUST support custom expectations via plugins

**Test Coverage**:
- `tests/integration/test_quality_monitoring.py`
- `tests/integration/test_contract_monitor_dq_integration.py`

**Traceability**:
- ADR-0044 (Unified Data Quality Plugin Architecture)
- ADR-0028 (Runtime Contract Monitoring)
- REQ-207 (Great Expectations Integration)

---

### REQ-249: Availability Monitoring **[New]**

**Requirement**: ContractMonitor MUST periodically check data source availability.

**Rationale**: Detects upstream failures that violate availability SLAs.

**Acceptance Criteria**:
- [ ] Availability check interval: 5 minutes (configurable)
- [ ] Attempts to connect to data source (ping query)
- [ ] Tracks: availability %, last failure time, failure reason
- [ ] Violations emitted when availability < SLA threshold
- [ ] Reports: consecutive failures, uptime percentage
- [ ] Support for multiple compute targets

**Enforcement**:
- Availability check tests
- Timeout handling tests
- Metric calculation tests

**Constraints**:
- MUST check connectivity regularly
- MUST NOT block data access on unavailability detection
- FORBIDDEN to cascade failures
- MUST track availability trends

**Test Coverage**: `tests/integration/test_availability_monitoring.py`

**Traceability**:
- data-contracts.md lines 224-230
- ADR-0028 (Runtime Contract Monitoring)

---

### REQ-250: Contract Violation Alerting via OpenLineage **[New]**

**Requirement**: All contract violations MUST be emitted as OpenLineage FAIL events with contractViolation facet.

**Rationale**: Enables end-to-end lineage-based governance audit trail.

**Acceptance Criteria**:
- [ ] FAIL event emitted for each violation type (freshness, drift, quality, availability)
- [ ] contractViolation facet includes: contractName, contractVersion, violationType, severity, message
- [ ] Events include: job name, run ID, timestamp
- [ ] Events sent to OTLP collector configured in platform
- [ ] Events queryable in lineage tools (Marquez, Spline, etc.)
- [ ] No PII/sensitive data in event messages

**Enforcement**:
- Event formatting tests
- Facet structure tests
- OTLP integration tests

**Constraints**:
- MUST emit valid OpenLineage events
- MUST include all required fields
- FORBIDDEN to emit PII in events
- MUST use contractViolation facet format

**Test Coverage**: `tests/integration/test_contract_violation_events.py`

**Traceability**:
- data-contracts.md lines 393-413
- ADR-0007 (OpenLineage from Start)
- ADR-0028 (Runtime Contract Monitoring)

---

## Domain Acceptance Criteria

Quality Gates and Runtime Monitoring (REQ-241 to REQ-250) is complete when:

- [ ] All 10 requirements have complete template fields
- [ ] QualityGateValidator ABC defined
- [ ] All 5 monitoring modes working: freshness, schema drift, quality, availability, violations
- [ ] ContractMonitor Kubernetes service deployed
- [ ] Helm chart for ContractMonitor created
- [ ] PostgreSQL backend configured for monitoring state
- [ ] Freshness monitoring working with real tables
- [ ] Schema drift detection working with compute targets
- [ ] Quality monitoring via Great Expectations working
- [ ] Availability monitoring working
- [ ] OpenLineage FAIL events with contractViolation facet working
- [ ] Prometheus metrics exported for all checks
- [ ] Unit tests pass with >80% coverage
- [ ] Integration tests validate monitoring workflows
- [ ] K8s deployment tests validate Helm charts
- [ ] Documentation updated:
  - [ ] ADR-0028 backreferences requirements
  - [ ] ADR-0012 backreferences requirements

## Epic Mapping

These requirements are satisfied in **Epic 7: Contract Monitoring**:
- Phase 4: Implement ContractMonitor service
- Phase 5: Deploy monitoring components (freshness, drift, quality, availability)

---

## Monitoring Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ContractMonitor Service (K8s Deployment, Layer 3)                      │
│                                                                          │
│  ┌─ Scheduler ──────────────────────────────────┐                       │
│  │                                              │                       │
│  ├─► Freshness Check (15 min)                   │                       │
│  │   → Compare latest_update vs SLA             │                       │
│  │   → Emit OpenLineage FAIL if violated        │                       │
│  │                                              │                       │
│  ├─► Schema Drift (1 hour)                      │                       │
│  │   → Query actual table schema                │                       │
│  │   → Compare vs contract schema               │                       │
│  │   → Emit OpenLineage FAIL if drift detected  │                       │
│  │                                              │                       │
│  ├─► Quality Check (6 hours)                    │                       │
│  │   → Execute Great Expectations               │                       │
│  │   → Calculate quality score                  │                       │
│  │   → Emit OpenLineage FAIL if below threshold │                       │
│  │                                              │                       │
│  └─► Availability Check (5 min)                 │                       │
│      → Ping compute engine                      │                       │
│      → Track uptime %                           │                       │
│      → Emit OpenLineage FAIL if unavailable     │                       │
│                                                  │                       │
│  PostgreSQL Backend:                            │                       │
│  ├── contract_checks (results history)          │                       │
│  ├── violations (aggregated violations)         │                       │
│  └── metrics (freshness, availability, quality) │                       │
│                                                  │                       │
│  Observability:                                 │                       │
│  ├── OpenLineage FAIL events (contractViolation)│                       │
│  ├── Prometheus metrics (violations_total, %)   │                       │
│  └── Structured logs (JSON)                     │                       │
└─────────────────────────────────────────────────────────────────────────┘
```

## SLA Violation Severity Levels

| Severity | Description | Duration | Action |
|----------|-------------|----------|--------|
| INFO | Approaching SLA threshold (e.g., 2h away) | None | Log + alert |
| WARNING | Approaching SLA deadline (e.g., 30m away) | <30 min | Alert teams |
| ERROR | Violating SLA | Active | Alert critical path |
| CRITICAL | Repeated violations (>3 in 24h) | Trend | Escalate |

## Quality Gate Execution Timeline

```
floe compile
    │
    ├─► [PolicyEnforcer.validate_data_product]
    │   ├─► Naming enforcement
    │   ├─► Classification compliance
    │   ├─► Test coverage gate ◄── REQ-243
    │   ├─► Documentation gate ◄── REQ-244
    │   └─► Contract validation (compile-time)
    │
    └─► [Compilation succeeds]
            │
            ▼
        [floe run]
            │
            ├─► Execute dbt + quality tests
            │   │
            │   └─► ContractMonitor registers contract
            │
            ├─► [ContractMonitor continuous checks] ◄── REQ-245 onwards
            │   ├─► Freshness (15 min) ◄── REQ-246
            │   ├─► Schema drift (1 hour) ◄── REQ-247
            │   ├─► Quality checks (6 hours) ◄── REQ-248
            │   └─► Availability (5 min) ◄── REQ-249
            │
            └─► [Violations emitted via OpenLineage] ◄── REQ-250
```
