# Tasks: Epic 4B Dagster Orchestrator Plugin

**Branch**: `4b-orchestrator-plugin`
**Created**: 2026-01-19
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

## Overview

This task breakdown implements the Dagster orchestrator plugin following the 7-phase implementation plan. Tasks are organized by phase with dependencies clearly marked.

**Total Tasks**: 25
**Estimated Complexity**: Medium (leverages existing plugin patterns from floe-compute-duckdb)

---

## Phase 1: Plugin Skeleton (Story 1 - P1)

Creates the plugin package structure, entry point registration, and plugin metadata.

- [ ] **T001** [P1] [Story-1] Create plugin package structure with pyproject.toml
  - File: `plugins/floe-orchestrator-dagster/pyproject.toml`
  - Creates package with entry point `[project.entry-points."floe.orchestrators"]`
  - Dependencies: floe-core, dagster>=1.10.0,<2.0.0, dagster-dbt>=0.26.0
  - FR-001

- [ ] **T002** [P1] [Story-1] Implement DagsterOrchestratorPlugin class skeleton
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Inherits from OrchestratorPlugin ABC
  - Implements name, version, floe_api_version properties
  - FR-002, FR-003, FR-004

- [ ] **T003** [P1] [Story-1] Create package __init__.py with public exports
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/__init__.py`
  - Exports: DagsterOrchestratorPlugin, __version__
  - FR-001

- [ ] **T004** [P1] [Story-1] Add unit tests for plugin metadata
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py`
  - Tests: name property, version property, floe_api_version property
  - Tests: ABC compliance verification
  - SC-001

- [ ] **T005** [P1] [Story-1] Add integration test for entry point discovery
  - File: `plugins/floe-orchestrator-dagster/tests/integration/test_discovery.py`
  - Tests: Plugin discovered via importlib.metadata.entry_points
  - Tests: Plugin instantiation succeeds
  - SC-001
  - Depends: T001, T002, T003

---

## Phase 2: Definition Generation (Stories 2, 3 - P1)

Implements create_definitions() and create_assets_from_transforms() using dagster-dbt.

- [ ] **T006** [P1] [Story-2] Implement create_definitions() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Accepts CompiledArtifacts dict, returns Dagster Definitions
  - Uses @dbt_assets decorator for manifest parsing
  - FR-005, FR-009

- [ ] **T007** [P1] [Story-3] Implement create_assets_from_transforms() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Accepts list[TransformConfig], returns list[AssetsDefinition]
  - Preserves dependency graph from depends_on field
  - FR-006, FR-007

- [ ] **T008** [P1] [Story-3] Add transform metadata to asset metadata
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Includes: tags, compute target, schema_name, materialization
  - FR-008
  - Depends: T007

- [ ] **T009** [P1] [Story-2] Add CompiledArtifacts validation
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Validates artifacts dict before definition generation
  - Raises ValidationError with actionable message
  - FR-009
  - Depends: T006

- [ ] **T010** [P1] [Story-2] Add unit tests for definition generation
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_definitions.py`
  - Tests: create_definitions with valid artifacts
  - Tests: create_definitions with empty transforms
  - Tests: create_definitions with invalid artifacts
  - SC-002
  - Depends: T006, T009

- [ ] **T011** [P1] [Story-3] Add unit tests for asset creation
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_assets.py`
  - Tests: create_assets_from_transforms with dependencies
  - Tests: Asset metadata includes compute target
  - Tests: Asset tags match TransformConfig tags
  - SC-003
  - Depends: T007, T008

---

## Phase 3: Resource Management (Story 4 - P2)

Implements get_helm_values() and get_resource_requirements() for K8s deployment.

- [ ] **T012** [P2] [Story-4] Implement get_helm_values() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Returns dict with dagster-webserver, dagster-daemon, dagster-user-code
  - Follows Helm values schema from contracts/helm-values-schema.md
  - FR-010

- [ ] **T013** [P2] [Story-4] Implement get_resource_requirements() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Accepts workload_size: "small" | "medium" | "large"
  - Returns ResourceSpec with cpu/memory requests and limits
  - Raises ValueError for invalid workload_size
  - FR-011, FR-012

- [ ] **T014** [P2] [Story-4] Add resource preset definitions
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Class constant _RESOURCE_PRESETS: dict[str, ResourceSpec]
  - Small: 100m/500m CPU, 256Mi/512Mi memory
  - Medium: 250m/1000m CPU, 512Mi/1Gi memory
  - Large: 500m/2000m CPU, 1Gi/2Gi memory
  - FR-011
  - Depends: T013

- [ ] **T015** [P2] [Story-4] Add unit tests for Helm values
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_helm_values.py`
  - Tests: get_helm_values returns valid structure
  - Tests: Values contain all required Dagster components
  - SC-005
  - Depends: T012

- [ ] **T016** [P2] [Story-4] Add unit tests for resource requirements
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_helm_values.py`
  - Tests: get_resource_requirements for small/medium/large
  - Tests: ValueError for invalid workload_size
  - SC-005
  - Depends: T013, T014

---

## Phase 4: Scheduling (Story 5 - P2)

Implements schedule_job() with cron expression and timezone validation.

- [ ] **T017** [P2] [Story-5] Implement schedule_job() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Accepts job_name, cron expression, timezone
  - Creates Dagster ScheduleDefinition
  - FR-013

- [ ] **T018** [P2] [Story-5] Add cron expression validation
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Uses croniter library for validation
  - Raises ValueError with cron format guidance
  - FR-014
  - Depends: T017

- [ ] **T019** [P2] [Story-5] Add timezone validation
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Uses pytz library for IANA timezone validation
  - Raises ValueError listing valid timezone examples
  - FR-015
  - Depends: T017

- [ ] **T020** [P2] [Story-5] Add unit tests for scheduling
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_scheduling.py`
  - Tests: schedule_job creates ScheduleDefinition
  - Tests: Invalid cron raises ValueError
  - Tests: Invalid timezone raises ValueError
  - SC-007
  - Depends: T017, T018, T019

---

## Phase 5: Lineage (Story 6 - P2)

Implements emit_lineage_event() with OpenLineage v1.0 compliance.

- [ ] **T021** [P2] [Story-6] Implement emit_lineage_event() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Accepts event_type (START/COMPLETE/FAIL), job, inputs, outputs
  - Constructs OpenLineage event structure
  - Delegates to LineageBackendPlugin via plugin registry
  - FR-016, FR-017, FR-018

- [ ] **T022** [P2] [Story-6] Add graceful no-op for unconfigured lineage backend
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - Logs debug message when no lineage backend configured
  - Never raises exception for missing backend
  - FR-018
  - Depends: T021

- [ ] **T023** [P2] [Story-6] Add unit tests for lineage events
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_lineage.py`
  - Tests: emit_lineage_event with START/COMPLETE/FAIL
  - Tests: Event includes correct input/output datasets
  - Tests: No-op behavior when backend unconfigured
  - SC-006
  - Depends: T021, T022

---

## Phase 6: Connectivity (Story 7 - P3)

Implements validate_connection() with HTTP health check and timeout.

- [ ] **T024** [P3] [Story-7] Implement validate_connection() method
  - File: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`
  - HTTP health check to Dagster GraphQL API
  - 10-second timeout
  - Returns ValidationResult with success/message/errors
  - FR-019, FR-020, FR-021

- [ ] **T025** [P3] [Story-7] Add unit tests for connection validation
  - File: `plugins/floe-orchestrator-dagster/tests/unit/test_plugin.py`
  - Tests: validate_connection success case (mocked)
  - Tests: validate_connection failure with actionable error
  - Tests: validate_connection timeout handling
  - SC-004
  - Depends: T024

---

## Phase 7: Integration Testing

Integration tests with real Dagster service and cross-package contract tests.

- [ ] **T026** [P1] [Story-2] Add contract test for CompiledArtifacts consumption
  - File: `tests/contract/test_core_to_dagster_contract.py`
  - Tests: Dagster plugin can consume floe-core CompiledArtifacts
  - Tests: Schema version compatibility
  - SC-002, SC-003
  - Depends: T006, T007

- [ ] **T027** [P2] [Story-4] Add integration test for Dagster service
  - File: `plugins/floe-orchestrator-dagster/tests/integration/test_dagster.py`
  - Tests: validate_connection with real Dagster service
  - Tests: Generated definitions load in Dagster
  - Requires K8s with Dagster deployed
  - SC-002, SC-004
  - Depends: T006, T024

- [ ] **T028** [P1] [Story-1] Add root conftest.py for integration fixtures
  - File: `plugins/floe-orchestrator-dagster/tests/conftest.py`
  - OTEL reset fixtures
  - Test isolation utilities
  - NFR-004

- [ ] **T029** [P1] [Story-1] Add unit conftest.py with mock fixtures
  - File: `plugins/floe-orchestrator-dagster/tests/unit/conftest.py`
  - Mock CompiledArtifacts fixtures
  - Mock TransformConfig fixtures
  - NFR-003

---

## Dependency Graph

```
T001 (pyproject.toml)
  └─► T002 (plugin class)
        ├─► T003 (__init__.py)
        │     └─► T004 (unit tests metadata)
        │           └─► T005 (discovery integration test)
        │
        ├─► T006 (create_definitions)
        │     ├─► T009 (validation)
        │     │     └─► T010 (unit tests definitions)
        │     └─► T026 (contract test)
        │
        ├─► T007 (create_assets_from_transforms)
        │     ├─► T008 (asset metadata)
        │     │     └─► T011 (unit tests assets)
        │     └─► T026 (contract test)
        │
        ├─► T012 (get_helm_values)
        │     └─► T015 (unit tests helm)
        │
        ├─► T013 (get_resource_requirements)
        │     ├─► T014 (resource presets)
        │     │     └─► T016 (unit tests resources)
        │
        ├─► T017 (schedule_job)
        │     ├─► T018 (cron validation)
        │     ├─► T019 (timezone validation)
        │     │     └─► T020 (unit tests scheduling)
        │
        ├─► T021 (emit_lineage_event)
        │     ├─► T022 (no-op handling)
        │     │     └─► T023 (unit tests lineage)
        │
        └─► T024 (validate_connection)
              └─► T025 (unit tests connection)
                    └─► T027 (integration test dagster)

T028 (root conftest) - independent
T029 (unit conftest) - independent
```

---

## Task Priority Summary

| Priority | Count | Description |
|----------|-------|-------------|
| P1 | 14 | Core plugin functionality, discovery, definitions, testing infrastructure |
| P2 | 10 | Resource management, scheduling, lineage, integration tests |
| P3 | 2 | Connection validation |

---

## Story Coverage

| Story | Tasks | Requirements Covered |
|-------|-------|---------------------|
| Story 1 (Platform configures Dagster) | T001-T005, T028, T029 | FR-001 to FR-004 |
| Story 2 (Generate pipeline definitions) | T006, T009, T010, T026 | FR-005, FR-009 |
| Story 3 (Create assets from transforms) | T007, T008, T011 | FR-006, FR-007, FR-008 |
| Story 4 (Deploy Dagster services) | T012-T016, T027 | FR-010, FR-011, FR-012 |
| Story 5 (Schedule pipeline execution) | T017-T020 | FR-013, FR-014, FR-015 |
| Story 6 (Track data lineage) | T021-T023 | FR-016, FR-017, FR-018 |
| Story 7 (Validate connectivity) | T024, T025 | FR-019, FR-020, FR-021 |

---

## Success Criteria Traceability

| Criterion | Tasks |
|-----------|-------|
| SC-001: ABC compliance | T004, T005 |
| SC-002: Definitions load in Dagster | T010, T026, T027 |
| SC-003: Dependency graph accuracy | T011, T026 |
| SC-004: Connection validation timing | T025, T027 |
| SC-005: Helm values pass lint | T015, T016 |
| SC-006: OpenLineage v1.0 compliance | T023 |
| SC-007: Schedule timezone handling | T020 |
| SC-008: >80% test coverage | All test tasks |
