# Implementation Plan: dbt Plugin Abstraction

**Branch**: `5a-dbt-plugin` | **Date**: 2026-01-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/5a-dbt-plugin/spec.md`

## Summary

Implement the DBTPlugin abstraction layer enabling floe to support multiple dbt execution environments (dbt-core local, dbt Fusion, dbt Cloud) while maintaining the principle that dbt owns ALL SQL compilation. The DBTPlugin ABC already exists in floe-core; this epic creates the concrete implementations and Dagster integration.

**Key Deliverables**:
1. `floe-dbt-core` plugin package - dbt-core + SQLFluff implementation
2. `floe-dbt-fusion` plugin package - dbt Fusion CLI implementation
3. Dagster ConfigurableResource for DBTPlugin injection
4. Contract tests validating plugin interface compliance

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: dbt-core>=1.6,<2.0, SQLFluff>=2.0, structlog, opentelemetry-api
**Storage**: N/A (plugins invoke dbt CLI/API; dbt manages its own target/ directory)
**Testing**: pytest with K8s-native integration tests (Kind cluster)
**Target Platform**: Linux/macOS (K8s deployment)
**Project Type**: Plugin packages under `plugins/`
**Performance Goals**:
  - DBTCorePlugin: <30s for 50-model compile (SC-001)
  - DBTFusionPlugin: <2s for 50-model compile (SC-002)
  - Plugin initialization: <500ms (NFR-001)
  - Artifact retrieval: <100ms for 10MB files (NFR-002)
**Constraints**: dbt-core is NOT thread-safe; Fusion requires Rust adapters
**Scale/Scope**: Support projects with 50-500 models

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (plugins/floe-dbt-core/, plugins/floe-dbt-fusion/)
- [x] No SQL parsing/validation in Python (dbt owns SQL)
- [x] No orchestration logic outside floe-dagster

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (DBTPlugin ABC)
- [x] Plugin registered via entry point (`floe.dbt` group)
- [x] PluginMetadata declares name, version, floe_api_version

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (dbt is ENFORCED framework)
- [x] Pluggable choices documented in manifest.yaml (`plugins.dbt_runtime`)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (DBTPlugin consumes profiles from it)
- [x] Pydantic v2 models for all schemas (DBTRunResult, LintResult already defined)
- [x] Contract changes follow versioning rules (N/A - using existing ABC)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage
- [x] `@pytest.mark.requirement()` on all integration tests

**Principle VI: Security First**
- [x] Input validation via Pydantic (project paths, target names)
- [x] Credentials use SecretStr (via dbt's env_var() mechanism)
- [x] No shell=True (Fusion uses subprocess with list args)

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (manifest.yaml → plugin selection)
- [x] Layer ownership respected (Platform Team selects dbt_runtime)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (NFR-006)
- [x] OpenLineage events for data transformations (NFR-007, via dbt native)

## Project Structure

### Documentation (this feature)

```text
specs/5a-dbt-plugin/
├── plan.md              # This file
├── research.md          # dbt-core, Fusion, existing implementation research
├── spec.md              # Feature specification (40 FRs, 5 User Stories)
├── checklists/
│   └── requirements.md  # Requirements tracking checklist
└── tasks.md             # Task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Plugin packages (NEW)
plugins/
├── floe-dbt-core/
│   ├── pyproject.toml           # Entry point: floe.dbt = core
│   ├── src/
│   │   └── floe_dbt_core/
│   │       ├── __init__.py      # Export DBTCorePlugin
│   │       ├── plugin.py        # DBTCorePlugin implementation
│   │       ├── linting.py       # SQLFluff integration
│   │       └── errors.py        # dbt-core specific errors
│   └── tests/
│       ├── conftest.py
│       ├── unit/
│       │   ├── test_plugin.py
│       │   └── test_linting.py
│       └── integration/
│           └── test_dbt_core_integration.py
│
└── floe-dbt-fusion/
    ├── pyproject.toml           # Entry point: floe.dbt = fusion
    ├── src/
    │   └── floe_dbt_fusion/
    │       ├── __init__.py      # Export DBTFusionPlugin
    │       ├── plugin.py        # DBTFusionPlugin implementation
    │       ├── detection.py     # Binary/version detection
    │       └── fallback.py      # Automatic fallback to core
    └── tests/
        ├── conftest.py
        ├── unit/
        │   ├── test_plugin.py
        │   └── test_detection.py
        └── integration/
            └── test_fusion_integration.py

# Existing packages (MODIFY)
packages/floe-core/
└── src/floe_core/
    └── plugins/
        └── dbt.py               # DBTPlugin ABC (EXISTS - no changes)

plugins/floe-orchestrator-dagster/
└── src/floe_orchestrator_dagster/
    ├── resources/
    │   └── dbt_resource.py      # NEW: DBTResource ConfigurableResource
    └── plugin.py                # MODIFY: Wire DBTResource to assets

# Root-level tests
tests/
└── contract/
    └── test_dbt_plugin_contract.py  # NEW: Plugin compliance tests
```

**Structure Decision**: Two new plugin packages under `plugins/` following existing patterns (floe-compute-duckdb, floe-orchestrator-dagster). Entry point group is `floe.dbt` with implementations `core` and `fusion`.

## Key Design Decisions

### 1. dbtRunner Thread Safety

**Problem**: dbt-core dbtRunner is NOT thread-safe per official documentation.

**Decision**: `DBTCorePlugin.supports_parallel_execution()` returns `False`. For parallel execution, users must use DBTFusionPlugin or dbt Cloud.

### 2. Fusion Fallback Strategy

**Problem**: dbt Fusion requires Rust adapters not available for all targets.

**Decision**: Automatic fallback with warning (FR-039, FR-040):
```python
if not fusion_adapter_available(target):
    logger.warning("Fusion adapter unavailable, falling back to dbt-core")
    return DBTCorePlugin().run_models(...)
```

### 3. Dagster Integration Pattern

**Decision**: ConfigurableResource pattern for type-safe injection (FR-037, FR-038):
```python
class DBTResource(ConfigurableResource):
    plugin_type: str = "core"
    project_dir: str
    profiles_dir: str
    target: str = "dev"
```

### 4. SQLFluff Dialect Detection

**Decision**: Read `type:` from profiles.yml target configuration and map to SQLFluff dialect. Mapping defined in `floe_dbt_core/linting.py`.

## Error Codes

| Code | Exception | Description |
|------|-----------|-------------|
| FLOE-DBT-E001 | DBTCompilationError | Jinja/SQL compilation failed |
| FLOE-DBT-E002 | DBTExecutionError | Model execution failed |
| FLOE-DBT-E003 | DBTConfigurationError | Invalid profiles.yml or dbt_project.yml |
| FLOE-DBT-E004 | DBTLintError | Linting process failed (not SQL issues) |
| FLOE-DBT-E005 | DBTFusionNotFoundError | Fusion binary not installed |
| FLOE-DBT-E006 | DBTAdapterUnavailableError | Rust adapter not available for target |

## Complexity Tracking

> No constitution violations requiring justification.

| Decision | Why This Way | Alternative Rejected |
|----------|--------------|---------------------|
| Two plugin packages | Clean separation of dependencies (dbt-core vs CLI) | Single package with optional deps - harder to test |
| Subprocess for Fusion | Rust binary, no Python bindings | FFI bindings - complex, unmaintained |
| SQLFluff for linting | Industry standard, dialect-aware | Built-in linter - limited dialect support |

## Implementation Phases

### Phase 1: Core Plugin (P1)
- DBTCorePlugin implementation
- SQLFluff linting integration
- Unit tests with mocked dbtRunner

### Phase 2: Fusion Plugin (P2)
- DBTFusionPlugin implementation
- Binary detection and version checking
- Automatic fallback mechanism

### Phase 3: Dagster Integration (P1)
- DBTResource ConfigurableResource
- Wire to existing placeholder assets
- Integration tests

### Phase 4: Contract Tests
- Plugin compliance test suite
- Cross-package contract validation
- Performance benchmarks

## References

- [spec.md](./spec.md) - Feature specification
- [research.md](./research.md) - Technical research findings
- [ADR-0043](../../docs/architecture/adr/) - dbt Runtime Abstraction
- [DBTPlugin ABC](../../packages/floe-core/src/floe_core/plugins/dbt.py) - Existing interface
