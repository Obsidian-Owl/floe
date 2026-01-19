# Implementation Plan: Dagster Orchestrator Plugin

**Branch**: `4b-orchestrator-plugin` | **Date**: 2026-01-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/4b-orchestrator-plugin/spec.md`

## Summary

Implement a Dagster orchestrator plugin that extends `OrchestratorPlugin` ABC from floe-core. The plugin enables Dagster as the orchestration platform for floe data pipelines by:

1. Converting CompiledArtifacts to Dagster Definitions using `dagster-dbt` native integration
2. Generating software-defined assets from dbt transforms with per-model compute selection
3. Providing Helm values for K8s deployment of Dagster services
4. Emitting OpenLineage events for data lineage tracking
5. Supporting cron-based job scheduling with timezone support

Technical approach uses `@dbt_assets` decorator for automatic manifest parsing (per clarification), targeting Dagster 1.10+ minimum with 1.12 as default test/chart version.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: floe-core>=0.1.0, dagster>=1.10.0,<2.0.0, dagster-dbt>=0.26.0, openlineage-python>=1.0.0, httpx>=0.24.0, croniter>=1.0.0, pytz>=2024.1
**Storage**: N/A (plugin is stateless; Dagster uses PostgreSQL for run storage)
**Testing**: pytest with pytest-cov, pytest-asyncio; mypy --strict; ruff
**Target Platform**: Linux/K8s (Kind for local testing, managed K8s for production)
**Project Type**: Plugin package (single package in plugins/ directory)
**Performance Goals**: Plugin load <500ms; Definition generation <5s for 500 transforms
**Constraints**: Connection validation <10s; All methods idempotent
**Scale/Scope**: Support up to 500 dbt models per data product

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`plugins/floe-orchestrator-dagster/`)
- [x] No SQL parsing/validation in Python (dbt owns SQL via dagster-dbt)
- [x] Orchestration logic in floe-dagster plugin only

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (`OrchestratorPlugin` ABC)
- [x] Plugin registered via entry point (`floe.orchestrators`)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (OpenTelemetry spans, OpenLineage events, K8s deployment)
- [x] Pluggable choice (Dagster) documented via entry point registration

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (sole contract)
- [x] Pydantic v2 models for all schemas (uses existing floe-core models)
- [x] Contract changes follow versioning rules (existing dataclasses stable)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage (tests FAIL when services unavailable)
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (cron/timezone validation)
- [x] Credentials use SecretStr (for Dagster connection if needed)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → CompiledArtifacts → plugin)
- [x] Layer ownership respected (Platform Team selects orchestrator)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (validation spans, definition generation)
- [x] OpenLineage events for data transformations (emit_lineage_event)

## Project Structure

### Documentation (this feature)

```text
specs/4b-orchestrator-plugin/
├── plan.md              # This file
├── research.md          # Phase 0: Research findings and decisions
├── data-model.md        # Phase 1: Entity definitions and relationships
├── quickstart.md        # Phase 1: Usage guide
├── contracts/           # Phase 1: Interface contracts
│   ├── plugin-interface.md
│   └── helm-values-schema.md
└── tasks.md             # Phase 2: Task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
plugins/floe-orchestrator-dagster/
├── pyproject.toml                    # Package metadata, entry points, dependencies
├── src/
│   └── floe_orchestrator_dagster/
│       ├── __init__.py               # Export DagsterOrchestratorPlugin, __version__
│       └── plugin.py                 # Main plugin implementation
└── tests/
    ├── conftest.py                   # Root test configuration
    ├── unit/
    │   ├── conftest.py               # Unit test fixtures
    │   ├── test_plugin.py            # Plugin metadata tests
    │   ├── test_definitions.py       # Definition generation tests
    │   ├── test_assets.py            # Asset creation tests
    │   ├── test_helm_values.py       # Helm values tests
    │   ├── test_scheduling.py        # Schedule validation tests
    │   └── test_lineage.py           # Lineage event tests
    └── integration/
        ├── conftest.py               # Integration fixtures (OTEL reset)
        ├── test_discovery.py         # Entry point discovery tests
        └── test_dagster.py           # Dagster service integration

tests/contract/                       # Root-level contract tests
└── test_core_to_dagster_contract.py  # Cross-package contract validation
```

**Structure Decision**: Standard plugin package structure following `floe-compute-duckdb` pattern. Plugin lives in `plugins/` directory with dedicated package structure. Contract tests at root level in `tests/contract/` because they validate cross-package integration.

## Implementation Phases

### Phase 1: Plugin Skeleton (FR-001 to FR-004)

1. Create plugin package structure
2. Implement entry point registration
3. Implement PluginMetadata properties (name, version, floe_api_version)
4. Add discovery tests

### Phase 2: Definition Generation (FR-005 to FR-009)

1. Implement `create_definitions()` using `@dbt_assets`
2. Implement `create_assets_from_transforms()`
3. Add dependency graph preservation
4. Add transform metadata in asset metadata
5. Add CompiledArtifacts validation

### Phase 3: Resource Management (FR-010 to FR-012)

1. Implement `get_helm_values()` with resource presets
2. Implement `get_resource_requirements()` for small/medium/large
3. Add Helm values schema validation tests

### Phase 4: Scheduling (FR-013 to FR-015)

1. Implement `schedule_job()` with Dagster ScheduleDefinition
2. Add cron expression validation (croniter)
3. Add timezone validation (pytz)

### Phase 5: Lineage (FR-016 to FR-018)

1. Implement `emit_lineage_event()` for START/COMPLETE/FAIL
2. Integrate with LineageBackendPlugin via plugin registry
3. Handle no-op case when lineage backend not configured

### Phase 6: Connectivity (FR-019 to FR-021)

1. Implement `validate_connection()` with HTTP health check
2. Add 10-second timeout
3. Return actionable error messages

### Phase 7: Integration Testing

1. Add integration tests with real Dagster service
2. Add contract tests for cross-package validation
3. Verify >80% test coverage

## Key Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| floe-core | >=0.1.0 | OrchestratorPlugin ABC, CompiledArtifacts |
| dagster | >=1.10.0,<2.0.0 | Orchestration framework |
| dagster-dbt | >=0.26.0 | dbt integration with @dbt_assets |
| openlineage-python | >=1.0.0 | OpenLineage event construction |
| httpx | >=0.24.0 | HTTP client for connection validation |
| croniter | >=1.0.0 | Cron expression validation |
| pytz | >=2024.1 | Timezone validation |

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Dagster API changes | Pin to 1.10-1.x range, test against 1.12 |
| dbt manifest format changes | Use dagster-dbt abstraction layer |
| LineageBackend not configured | Graceful no-op with debug logging |
| Connection timeout in CI | Mock HTTP responses in unit tests |

## Complexity Tracking

No constitution violations. Design follows all 8 principles.

## References

- [research.md](./research.md) - Research findings and technology decisions
- [data-model.md](./data-model.md) - Entity definitions
- [quickstart.md](./quickstart.md) - Usage guide
- [contracts/plugin-interface.md](./contracts/plugin-interface.md) - Plugin ABC contract
- [contracts/helm-values-schema.md](./contracts/helm-values-schema.md) - Helm values schema
