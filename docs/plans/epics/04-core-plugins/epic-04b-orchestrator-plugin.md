# Epic 4B: Orchestrator Plugin

## Summary

The OrchestratorPlugin ABC defines the interface for workflow orchestration engines. The reference implementation uses Dagster for software-defined assets, with an adapter interface for Airflow 3.x compatibility.

## Status

- [ ] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [floe-04b-orchestrator-plugin](https://linear.app/obsidianowl/project/floe-04b-orchestrator-plugin-1eb3abdc05d5)

---

## Requirements Covered

| Requirement ID | Description | Priority |
|----------------|-------------|----------|
| REQ-021 | OrchestratorPlugin ABC definition | CRITICAL |
| REQ-022 | Dagster reference implementation | CRITICAL |
| REQ-023 | Asset generation from CompiledArtifacts | CRITICAL |
| REQ-024 | Schedule configuration | HIGH |
| REQ-025 | Sensor configuration | HIGH |
| REQ-026 | Airflow adapter interface | MEDIUM |
| REQ-027 | Run history tracking | HIGH |
| REQ-028 | Backfill support | MEDIUM |
| REQ-029 | Partition handling | HIGH |
| REQ-030 | Cross-asset dependencies | HIGH |

---

## Architecture References

### ADRs
- [ADR-0001](../../../architecture/adr/0001-plugin-architecture.md) - Plugin architecture
- [ADR-0005](../../../architecture/adr/0005-orchestration-abstraction.md) - Orchestration abstraction

### Interface Docs
- [plugin-interfaces.md](../../../architecture/plugin-system/plugin-interfaces.md) - Plugin interface definitions

### Contracts
- `OrchestratorPlugin` - Orchestration ABC
- `AssetDefinition` - Asset generation model
- `ScheduleConfig` - Schedule configuration model

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── plugin_interfaces.py         # OrchestratorPlugin ABC (shared)
└── plugins/
    └── orchestrator/
        └── __init__.py

plugins/floe-orchestrator-dagster/
├── src/floe_orchestrator_dagster/
│   ├── __init__.py
│   ├── plugin.py                # DagsterOrchestratorPlugin
│   ├── assets.py                # Asset generation
│   ├── schedules.py             # Schedule generation
│   ├── sensors.py               # Sensor generation
│   └── resources.py             # Dagster resources
└── tests/
    ├── unit/
    └── integration/

# Test Fixtures (extends Epic 9C framework)
testing/fixtures/orchestrator.py     # OrchestratorPlugin test fixtures
testing/tests/unit/test_orchestrator_fixtures.py  # Fixture tests
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | Epic 1 | Uses plugin registry |
| Blocked By | Epic 2B | Loads CompiledArtifacts |
| Blocked By | Epic 9C | Uses testing framework for fixtures |
| Blocks | Epic 5A | dbt plugin generates Dagster assets |
| Blocks | Epic 6A | OpenTelemetry traces from orchestrator |
| Blocks | Epic 6B | OpenLineage events from orchestrator |

---

## User Stories (for SpecKit)

### US1: OrchestratorPlugin ABC (P0)
**As a** plugin developer
**I want** a clear ABC for orchestrator plugins
**So that** I can implement adapters for new engines

**Acceptance Criteria**:
- [ ] `OrchestratorPlugin.generate_assets(artifacts)` defined
- [ ] `OrchestratorPlugin.generate_schedules(artifacts)` defined
- [ ] `OrchestratorPlugin.generate_sensors(artifacts)` defined
- [ ] Configuration via Pydantic models

### US2: Dagster Reference Implementation (P0)
**As a** data engineer
**I want** Dagster as the default orchestrator
**So that** I get software-defined assets out of the box

**Acceptance Criteria**:
- [ ] `DagsterOrchestratorPlugin` implements ABC
- [ ] Assets generated from CompiledArtifacts
- [ ] dbt models become Dagster assets
- [ ] IOManager for Iceberg tables (implemented HERE, not in floe-iceberg)

### US3: Schedule Generation (P1)
**As a** data engineer
**I want** schedules generated from floe.yaml
**So that** pipelines run automatically

**Acceptance Criteria**:
- [ ] Cron-based schedules supported
- [ ] Partition-based schedules supported
- [ ] Schedule timezone configuration
- [ ] Schedule dependencies respected

### US4: Cross-Asset Dependencies (P1)
**As a** data engineer
**I want** asset dependencies inferred
**So that** the execution order is correct

**Acceptance Criteria**:
- [ ] Dependencies from dbt refs
- [ ] Dependencies from explicit config
- [ ] Circular dependency detection
- [ ] Dependency graph visualization

---

## Technical Notes

### Key Decisions
- Dagster is the default (best-in-class asset orchestration)
- Assets are generated at compile-time, not runtime
- Dagster resources wrap compute/catalog/storage plugins
- Airflow adapter uses TaskFlow API (Airflow 3.x)

### Architectural Learnings from Epic 4D

**IOManager Placement Decision (from Epic 4D review):**

During Epic 4D implementation, IcebergIOManager was incorrectly placed in floe-iceberg.
This violated the pluggable architecture principle and was removed in a cleanup commit.

| What Happened | Why It's Wrong | Correct Approach |
|---------------|----------------|------------------|
| IOManager in floe-iceberg | floe-iceberg is orchestrator-agnostic storage | IOManager in orchestrator plugin |
| Hardcoded Dagster imports | Violates manifest-driven plugin selection | Plugin creates IOManager via create_definitions() |
| Storage package depends on orchestrator | Inverts dependency direction | Orchestrator depends on storage |

**Correct Architecture (implement in Epic 4B):**
- `floe-iceberg` provides `IcebergTableManager` (pure storage utility)
- `floe-orchestrator-dagster` creates `IcebergIOManager` using IcebergTableManager
- IOManager is instantiated by `OrchestratorPlugin.create_definitions()`
- Manifest configuration determines which orchestrator plugin is loaded

**Note**: FR-037 to FR-040 (IOManager requirements) were deferred from Epic 4D to this epic.

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Dagster version churn | MEDIUM | MEDIUM | Pin major version, abstraction layer |
| Complex asset graphs | MEDIUM | MEDIUM | Modular definitions, graph partitioning |
| Airflow compatibility | HIGH | MEDIUM | Limited scope, clear boundaries |

### Test Strategy
- **Unit**: `plugins/floe-orchestrator-dagster/tests/unit/test_assets.py`
- **Integration**: `plugins/floe-orchestrator-dagster/tests/integration/test_dagster_run.py`
- **Contract**: `tests/contract/test_orchestrator_plugin_abc.py`

---

## SpecKit Context

### Relevant Codebase Paths
- `docs/requirements/01-plugin-architecture/`
- `docs/architecture/plugin-system/`
- `plugins/floe-orchestrator-dagster/`

### Related Existing Code
- PluginRegistry from Epic 1
- CompiledArtifacts from Epic 2B

### External Dependencies
- `dagster>=1.5.0`
- `dagster-dbt>=0.21.0`
