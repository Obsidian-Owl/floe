# Implementation Plan: IcebergTableManager (Epic 4D)

**Branch**: `4d-storage-plugin` | **Date**: 2026-01-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/4d-storage-plugin/spec.md`

## Summary

Implement `IcebergTableManager`, an internal utility class in `packages/floe-iceberg/` that wraps PyIceberg table operations. The manager accepts CatalogPlugin and StoragePlugin via dependency injection, providing methods for table creation, schema evolution, snapshot management, and ACID writes. Additionally, implement `IcebergIOManager` for Dagster asset integration.

**Key architectural decision**: IcebergTableManager is NOT a plugin ABC. Iceberg is enforced (ADR-0005), not pluggable. The existing StoragePlugin (FileIO) and CatalogPlugin (catalog management) remain unchanged.

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: PyIceberg >=0.10.0,<0.11.0 (pinned in pyproject.toml; required for native upsert and API stability), Pydantic >=2.12.5,<3.0, structlog, opentelemetry-api >=1.20.0, pyarrow
**Storage**: Iceberg tables via PyIceberg (S3/GCS/Azure via StoragePlugin FileIO)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Kubernetes (Linux containers)
**Project Type**: Monorepo package (`packages/floe-iceberg/`)
**Performance Goals**: Table creation <5s, single-partition writes <5s, schema evolution <2s
**Constraints**: ACID guarantees required, optimistic concurrency with retry
**Scale/Scope**: Production data platform - 100s of tables, TB+ of data

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (`packages/floe-iceberg/`)
- [x] No SQL parsing/validation in Python (dbt owns SQL) - N/A for this feature
- [x] No orchestration logic outside floe-dagster - IOManager integrates but doesn't orchestrate

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC) - N/A: IcebergTableManager is internal utility, not plugin
- [x] Plugin registered via entry point - N/A: Not a plugin
- [x] PluginMetadata declares name, version, floe_api_version - N/A: Not a plugin

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml - N/A: Iceberg is enforced

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling) - N/A: Uses CatalogPlugin/StoragePlugin injection
- [x] Pydantic v2 models for all schemas - All models use ConfigDict(frozen=True, extra="forbid")
- [x] Contract changes follow versioning rules - API contract versioned at 1.0.0

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage - Tests FAIL if infrastructure missing
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic - All configs validated
- [x] Credentials use SecretStr - Via CatalogPlugin/StoragePlugin (existing)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only
- [x] Layer ownership respected - Layer 1 (floe-iceberg package)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted - All operations instrumented
- [x] OpenLineage events for data transformations - Emitted on writes

## Project Structure

### Documentation (this feature)

```text
specs/4d-storage-plugin/
├── plan.md              # This file
├── research.md          # Phase 0: PyIceberg research, existing plugins analysis
├── data-model.md        # Phase 1: Pydantic models
├── quickstart.md        # Phase 1: Developer guide
├── contracts/           # Phase 1: API contracts
│   ├── iceberg_table_manager_api.md
│   └── iceberg_io_manager_api.md
├── checklists/
│   └── requirements.md  # Spec quality validation
└── tasks.md             # Phase 2: Task breakdown (/speckit.tasks)
```

### Source Code (repository root)

```text
packages/floe-iceberg/
├── src/
│   └── floe_iceberg/
│       ├── __init__.py           # Public exports
│       ├── manager.py            # IcebergTableManager class
│       ├── models.py             # Pydantic models (TableConfig, etc.)
│       ├── errors.py             # Custom exceptions
│       ├── compaction.py         # Compaction strategies
│       └── telemetry.py          # OTel instrumentation
├── tests/
│   ├── conftest.py               # NO __init__.py (namespace collision)
│   ├── unit/
│   │   ├── test_manager.py       # IcebergTableManager unit tests
│   │   ├── test_io_manager.py    # IcebergIOManager unit tests
│   │   └── test_models.py        # Pydantic model tests
│   └── integration/
│       ├── test_manager_integration.py     # Real Polaris + S3
│       └── test_io_manager_integration.py  # Real Dagster materialization
└── pyproject.toml                # Package config (no entry points - not a plugin)

tests/contract/                   # ROOT LEVEL - cross-package contracts
└── test_floe_iceberg_contract.py # Validate manager accepts plugin interfaces
```

**IcebergIOManager Location**: IcebergIOManager lives in `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/io_manager.py`, NOT in `packages/floe-iceberg/`. Per component ownership (Principle I), Dagster-specific integration code belongs in the orchestrator plugin. The `io_manager.py` was intentionally omitted from `packages/floe-iceberg/` above.

**Structure Decision**: Single package in `packages/floe-iceberg/`. Not a plugin, so no entry points. Contract tests at root level validate integration with CatalogPlugin and StoragePlugin interfaces.

## Complexity Tracking

| Aspect | Justification |
|--------|---------------|
| IcebergTableManager is NOT a plugin | Iceberg is ENFORCED (ADR-0005), no abstraction needed. StoragePlugin/CatalogPlugin provide the pluggable layers. |
| Dependency injection pattern | SOLID principles - enables testing with mock plugins, clear separation |
| Retry logic for concurrent writes | PyIceberg doesn't auto-retry; production requirement for ACID |
| Governance-aware retention | Policy Enforcer (Epic 3A-3D) validates; manager accepts validated values |

## Phase 0: Research (Complete)

See `research.md` for:
- Existing StoragePlugin ABC analysis
- Existing CatalogPlugin ABC analysis
- PyIceberg best practices (table creation, writes, schema evolution, snapshots)
- Design decisions with rationale
- Dependencies and integration points

## Phase 1: Design (Complete)

### Artifacts Generated

| Artifact | Purpose |
|----------|---------|
| `data-model.md` | Pydantic models: TableConfig, TableSchema, SchemaChange, WriteConfig, SnapshotInfo, etc. |
| `contracts/iceberg_table_manager_api.md` | Full API contract for IcebergTableManager |
| `contracts/iceberg_io_manager_api.md` | Full API contract for IcebergIOManager |
| `quickstart.md` | Developer guide with code examples |

### Key Design Decisions

1. **IcebergTableManager is internal utility** - Not a plugin ABC (Iceberg enforced)
2. **Dependency injection** - Accepts CatalogPlugin + StoragePlugin in constructor
3. **Fast append default** - Configurable commit strategy with fast append as default
4. **Fail-fast table creation** - `if_not_exists=True` for idempotent behavior
5. **7-day retention default** - Governance-aware, accepts Policy Enforcer values
6. **Compaction execution only** - Orchestrator schedules, manager executes

### Constitution Re-Check (Post-Design)

All 8 principles verified:
- [x] Technology ownership respected
- [x] Not a plugin (Iceberg enforced)
- [x] Enforced standards preserved
- [x] Pydantic v2 contracts
- [x] K8s-native testing planned
- [x] Security via plugin delegation
- [x] Layer 1 placement
- [x] OTel instrumentation designed

## Phase 2: Implementation Plan

**Next Step**: Run `/speckit.tasks` to generate detailed task breakdown.

### High-Level Implementation Order

1. **Package Setup** (T001-T002)
   - Create `packages/floe-iceberg/` structure
   - Configure `pyproject.toml`

2. **Models** (T003-T008)
   - Implement Pydantic models from `data-model.md`
   - Unit tests for all models

3. **Core Manager** (T009-T015)
   - `IcebergTableManager.__init__` with plugin injection
   - Table creation with `if_not_exists`
   - Write operations with retry
   - Schema evolution
   - Snapshot management

4. **Dagster Integration** (T016-T019)
   - `IcebergIOManager` implementation
   - Partitioned asset support
   - Integration tests

5. **Observability** (T020-T022)
   - OTel span instrumentation
   - Structured logging

6. **Contract Tests** (T023-T024)
   - Root-level contract tests
   - Plugin interface validation

7. **Wiring & Integration** (T108-T114)
   - Wire IcebergIOManager into DagsterOrchestratorPlugin.create_definitions()
   - Create reusable factory function `create_iceberg_resources()`
   - Load CatalogPlugin and StoragePlugin via PluginRegistry
   - Instantiate IcebergTableManager and IcebergIOManager
   - Document no concrete StoragePlugin exists yet; create MockStoragePlugin test fixture

8. **Integration Test Phase** (T115-T118)
   - Contract test for full wiring chain (artifacts → registry → manager → io_manager → definitions)
   - Contract test that create_definitions() returns Definitions with "iceberg" resource
   - Negative test for graceful degradation when no storage/catalog configured
   - E2E wiring test (compile → discover → create → materialize → verify)

### Requirement Traceability

| FR | Task | Description |
|----|------|-------------|
| FR-001-007 | T009-T015 | IcebergTableManager methods |
| FR-008-011 | T009 | PyIceberg integration |
| FR-012-016 | T010 | Table creation |
| FR-017-021 | T012 | Schema evolution |
| FR-022-025 | T013-T014 | Snapshot management |
| FR-026-029 | T011 | ACID transactions |
| FR-030-032 | T015 | Compaction |
| FR-033-036 | T010 | Partitioning |
| FR-037-040 | T016-T019, T108-T112 | Dagster IOManager + Wiring |
| FR-041-044 | T020-T022 | Observability |
| FR-045-047 | T003-T008 | Configuration models |
| WIRING-001 | T115-T118 | End-to-end wiring integration tests |

## Next Steps

1. **Generate tasks**: Run `/speckit.tasks` to create `tasks.md`
2. **Create Linear issues**: Run `/speckit.taskstolinear` to sync with Linear
3. **Begin implementation**: Follow task order with TDD

## Checks and Balances

Four quality gates that MUST pass before Epic 4D can be considered complete:

### Gate 1: Version Alignment

All spec documents MUST reference `pyiceberg>=0.10.0,<0.11.0`. No references to `>=0.5.0` or `>=0.9.0` may remain.

**Verification**: `grep -rn "pyiceberg>=0.5.0\|pyiceberg>=0.9.0" specs/4d-storage-plugin/` returns no output.

### Gate 2: Wiring Completeness

The full chain MUST be validated end-to-end before US8 (Dagster integration) is considered complete:

```
CompiledArtifacts → PluginRegistry → CatalogPlugin + StoragePlugin
  → IcebergTableManager → IcebergIOManager → Dagster Definitions
```

**Verification**: T115 contract test passes — `create_definitions()` returns Definitions containing an "iceberg" resource key.

### Gate 3: Component Boundary

IcebergIOManager MUST live in `plugins/floe-orchestrator-dagster/`, NOT in `packages/floe-iceberg/`. No cross-boundary imports that violate component ownership.

**Verification**: `grep -rn "packages/floe-iceberg.*io_manager" specs/4d-storage-plugin/` returns no matches (or only explicit notes about where it does NOT go).

### Gate 4: Test Coverage

- All FRs (FR-001 through FR-047) have at least one test with `@pytest.mark.requirement()` marker
- Contract tests exist for cross-package integration points
- Integration tests use `IntegrationTestBase` and unique namespaces
- No `pytest.skip()`, no `time.sleep()`, no hardcoded float equality

**Verification**: `python -m testing.traceability --all --threshold 100` passes.

## References

- [research.md](./research.md) - Full research findings
- [data-model.md](./data-model.md) - Pydantic model definitions
- [contracts/](./contracts/) - API contracts
- [quickstart.md](./quickstart.md) - Developer guide
- [spec.md](./spec.md) - Feature specification
- [ADR-0005](../../docs/architecture/adr/0005-iceberg-table-format.md) - Iceberg ENFORCED
- [ADR-0036](../../docs/architecture/adr/0036-storage-plugin-interface.md) - StoragePlugin (FileIO)
