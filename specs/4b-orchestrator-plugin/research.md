# Research: Epic 4B Dagster Orchestrator Plugin

**Date**: 2026-01-19
**Feature**: Dagster Orchestrator Plugin
**Branch**: `4b-orchestrator-plugin`

## Prior Decisions (from Agent Memory)

- OrchestratorPlugin is a pluggable interface for job scheduling and execution
- Plugin architecture allows platform teams to choose orchestration systems (Dagster, Airflow, Prefect)
- Technology ownership principle: Dagster owns orchestration, dbt owns SQL

## Decision 1: Dagster Version Targeting

**Decision**: Target Dagster 1.10+ minimum; default charts/tests use Dagster 1.12

**Rationale**:
- `@dbt_assets` decorator API stable since Dagster 1.4
- Dagster 1.10+ provides dbt Fusion readiness
- Current Dagster version is 1.12.11 (Jan 2026)
- Current dagster-dbt version is 0.28.9 (Jan 2026)

**Alternatives Considered**:
- Dagster 1.6+ (rejected: too old, missing dbt Fusion support)
- Dagster 1.12+ only (rejected: too restrictive for existing deployments)
- `DbtProjectComponent` pattern (rejected: too new, component system still maturing)

## Decision 2: dbt Execution Strategy

**Decision**: Use `dagster-dbt` native integration with `@dbt_assets` decorator

**Rationale**:
- Automatic manifest parsing and asset discovery
- Native dbt command execution
- Aligns with technology ownership (dbt owns SQL)
- Consistent with floe architecture principles
- DuckDB compute plugin already generates profiles.yml

**Alternatives Considered**:
- `DbtCliResource` direct CLI (rejected: more manual, less asset discovery)
- Hybrid approach (rejected: adds complexity without benefit)

## Decision 3: Plugin Package Structure

**Decision**: Follow established plugin pattern from `floe-compute-duckdb`

**Rationale**:
- Proven structure in existing codebase
- Entry point registration pattern established
- Test organization patterns established
- ResourceSpec preset dictionary pattern works well

**Package Structure**:
```
plugins/floe-orchestrator-dagster/
├── pyproject.toml              # Entry point: floe.orchestrators
├── src/
│   └── floe_orchestrator_dagster/
│       ├── __init__.py         # Export DagsterOrchestratorPlugin
│       └── plugin.py           # Main implementation
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── conftest.py
    │   ├── test_plugin.py
    │   ├── test_definitions.py
    │   └── test_scheduling.py
    └── integration/
        ├── conftest.py
        ├── test_discovery.py
        └── test_dagster.py
```

## Decision 4: CompiledArtifacts Integration

**Decision**: Use `CompiledArtifacts.transforms.models` for asset generation

**Rationale**:
- CompiledArtifacts is the SOLE cross-package contract
- `ResolvedTransforms.models` contains list of `ResolvedModel` with:
  - `name`: Model identifier
  - `compute`: Resolved compute target (never None)
  - `tags`: Optional tag list
  - `depends_on`: Optional dependency list
- Maps cleanly to `TransformConfig` dataclass

**Contract Fields Used**:
- `artifacts.transforms.models` → list of dbt models
- `artifacts.transforms.default_compute` → fallback compute
- `artifacts.dbt_profiles` → dbt profiles.yml configuration
- `artifacts.observability` → telemetry/lineage settings

## Decision 5: Helm Values Structure

**Decision**: Return Dagster community chart-compatible values

**Rationale**:
- Dagster community Helm chart is well-maintained
- Provides webserver, daemon, user-code components
- Resource presets (small/medium/large) follow existing pattern

**Helm Values Structure**:
```yaml
dagster-webserver:
  resources:
    requests: {cpu: "100m", memory: "256Mi"}
    limits: {cpu: "500m", memory: "512Mi"}
dagster-daemon:
  resources: {...}
dagster-user-code:
  resources: {...}
postgresql:
  enabled: true  # Or external connection
```

## Decision 6: OpenLineage Event Emission

**Decision**: Delegate to `LineageBackendPlugin` via plugin registry

**Rationale**:
- Follows technology ownership (lineage backend handles delivery)
- Allows pluggable lineage destinations (Marquez, Atlan, etc.)
- Graceful no-op when no lineage backend configured
- Event structure follows OpenLineage v1.0 spec

**Event Types**:
- `START`: Job execution started
- `COMPLETE`: Job execution succeeded
- `FAIL`: Job execution failed

## Decision 7: Connection Validation Strategy

**Decision**: HTTP health check to Dagster GraphQL API

**Rationale**:
- Dagster webserver exposes GraphQL API
- Standard health check pattern
- 10-second timeout matches spec requirement

**Endpoint**: `http://{dagster_host}:{port}/graphql` with simple query

## Technical Dependencies

### Required Packages
```toml
dependencies = [
    "floe-core>=0.1.0",
    "dagster>=1.10.0,<2.0.0",
    "dagster-dbt>=0.26.0",
    "openlineage-python>=1.0.0",
    "httpx>=0.24.0",  # For connection validation
    "croniter>=1.0.0",  # For cron validation
    "pytz>=2024.1",  # For timezone validation
]
```

### Development Dependencies
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "pytest-asyncio>=0.23.0",
    "mypy>=1.8",
    "ruff>=0.3",
]
```

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| How to map TransformConfig to Dagster assets? | Use `@dbt_assets` decorator with manifest |
| Where does schedule creation happen? | `schedule_job()` returns ScheduleDefinition |
| How to handle per-model compute override? | Include in asset metadata, resource selection at runtime |
| What if lineage backend not configured? | No-op, log debug message |

## References

- [Dagster dbt Integration Docs](https://docs.dagster.io/integrations/libraries/dbt)
- [dagster-dbt PyPI](https://pypi.org/project/dagster-dbt/)
- [OpenLineage Specification](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md)
- `packages/floe-core/src/floe_core/plugins/orchestrator.py` - OrchestratorPlugin ABC
- `plugins/floe-compute-duckdb/` - Reference plugin implementation
