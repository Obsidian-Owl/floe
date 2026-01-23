# Implementation Plan: Tech Debt Resolution (Epic 12B)

**Branch**: `12b-tech-debt-resolution` | **Date**: 2026-01-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/12b-tech-debt-resolution/spec.md`

## Summary

Systematic resolution of 37 technical debt items identified in the January 2026 comprehensive audit. The work is organized into 4 phases targeting debt score improvement from 74 to 90. Key technical approaches include:

1. **Circular Dependency Resolution**: Move `TelemetryConfig` to `schemas/` module to break schemas → telemetry → plugins cycle
2. **Complexity Reduction**: Apply Strategy Pattern with dispatch dictionaries for error mapping functions
3. **God Module Decomposition**: Split `plugin_registry.py` and `oci/client.py` using Single Responsibility Principle
4. **Test Compliance**: Implement missing `drop_table()` functionality, add CLI/Plugin ABC test coverage
5. **Dependency Hygiene**: Add upper bounds to all critical dependencies (pydantic, kubernetes, pyiceberg)

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: Pydantic v2, structlog, pytest, PyIceberg, kubernetes client
**Storage**: N/A (refactoring existing code, no new storage)
**Testing**: pytest with K8s-native execution (Kind cluster)
**Target Platform**: Linux/macOS (development), Kubernetes (production)
**Project Type**: Monorepo with packages/ and plugins/ directories
**Performance Goals**: Maintain existing performance; no regression in CI times
**Constraints**: All changes must maintain backward compatibility with existing tests
**Scale/Scope**: 37 debt items across 9 categories; 2,652 Python files in scope

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core, floe-dbt, plugins/, etc.)
- [x] No SQL parsing/validation in Python (dbt owns SQL) - N/A for refactoring
- [x] No orchestration logic outside floe-dagster - N/A for refactoring

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC) - N/A (no new plugins)
- [x] Plugin registered via entry point (not direct import) - existing pattern preserved
- [x] PluginMetadata declares name, version, floe_api_version - existing pattern preserved

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml - N/A for refactoring

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling)
- [x] Pydantic v2 models for all schemas - all existing models preserved
- [x] Contract changes follow versioning rules - TelemetryConfig move is internal

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage - removing 3 skipped tests is explicit goal
- [x] `@pytest.mark.requirement()` on all integration tests - adding markers is explicit goal

**Principle VI: Security First**
- [x] Input validation via Pydantic - existing pattern preserved
- [x] Credentials use SecretStr - existing pattern preserved
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only - circular dependency fix enforces this
- [x] Layer ownership respected (Data Team vs Platform Team)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted - existing pattern preserved
- [x] OpenLineage events for data transformations - existing pattern preserved

**Constitution Check Status**: PASSED - All principles satisfied. This is refactoring work that improves architecture compliance.

## Project Structure

### Documentation (this feature)

```text
specs/12b-tech-debt-resolution/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # N/A (no new entities)
├── quickstart.md        # Refactoring guide
├── contracts/           # N/A (no new contracts)
├── checklists/          # Quality checklists
│   └── spec-quality.md  # Spec validation (completed)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
# Affected packages (refactoring scope)
packages/floe-core/
├── src/floe_core/
│   ├── __init__.py           # 12B-ARCH-002: Reduce exports from 76 to ~15
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── compiled_artifacts.py  # 12B-ARCH-001: Import TelemetryConfig
│   │   └── telemetry.py      # NEW: Move TelemetryConfig here
│   ├── telemetry/
│   │   ├── config.py         # 12B-ARCH-001: Move TelemetryConfig out
│   │   └── provider.py       # Update import path
│   ├── plugin_registry.py    # 12B-ARCH-003: Split into focused modules
│   ├── plugins/
│   │   ├── discovery.py      # NEW: Entry point discovery
│   │   ├── loader.py         # NEW: Plugin instantiation
│   │   ├── lifecycle.py      # NEW: Activation, shutdown, health
│   │   └── dependencies.py   # NEW: Dependency resolution
│   ├── oci/
│   │   ├── client.py         # 12B-ARCH-004: Refactor to facade
│   │   ├── manifest.py       # NEW: Manifest operations
│   │   └── layers.py         # NEW: Layer operations
│   ├── cli/rbac/
│   │   ├── audit.py          # 12B-CX-003: Reduce complexity
│   │   └── validate.py       # Add test coverage
│   └── enforcement/
│       └── policy_enforcer.py # 12B-CX-005: Reduce complexity
└── tests/
    ├── unit/
    │   └── cli/rbac/         # 12B-TEST-002: Add CLI RBAC tests
    └── integration/

packages/floe-iceberg/
├── src/floe_iceberg/
│   ├── manager.py            # Implement drop_table()
│   └── compaction.py         # 12B-TODO-001: Document SORT TODO
└── tests/unit/
    └── test_lifecycle.py     # 12B-TEST-001: Remove skipped tests

plugins/floe-catalog-polaris/
└── src/floe_catalog_polaris/
    └── errors.py             # 12B-CX-001: Strategy pattern refactor

plugins/floe-identity-keycloak/
└── src/floe_identity_keycloak/
    └── token_validator.py    # 12B-CX-006: Reduce complexity

plugins/floe-secrets-infisical/
└── src/floe_secrets_infisical/
    └── plugin.py             # 12B-CX-007: Reduce complexity
```

**Structure Decision**: This is refactoring of existing packages. No new packages created. The god module splits (plugin_registry.py, oci/client.py) create new focused modules within existing package boundaries.

## Complexity Tracking

> No constitution violations requiring justification. All changes improve constitution compliance.

| Improvement | Before | After | Benefit |
|-------------|--------|-------|---------|
| Circular dependency | schemas → telemetry → plugins | schemas independent | Layer separation (Principle VII) |
| Skipped tests | 3 | 0 | Test compliance (Principle V) |
| Max cyclomatic complexity | 26 | ≤15 | Maintainability |
| Export count | 76 | ~15 | API clarity |

## Implementation Phases

### Phase 1: Critical Issues (P0)

**Target**: Debt score 74 → 80

| Task | Requirement | Effort | Risk |
|------|-------------|--------|------|
| Break circular dependency | 12B-ARCH-001, FR-001 | Low | Low (internal refactor) |
| Remove skipped tests | 12B-TEST-001, FR-010 | Medium | Medium (new functionality) |
| Refactor map_pyiceberg_error | 12B-CX-001, FR-006 | Low | Low (isolated function) |
| Pin pydantic | 12B-DEP-001, FR-015 | Low | Low (version constraint) |
| Pin kubernetes | 12B-DEP-002, FR-015 | Low | Low (version constraint) |

### Phase 2: High Priority (P1)

**Target**: Debt score 80 → 85

| Task | Requirement | Effort | Risk |
|------|-------------|--------|------|
| Reduce __init__.py exports | 12B-ARCH-002, FR-002 | Medium | Medium (import changes) |
| Add CLI RBAC tests | 12B-TEST-002, FR-011 | High | Low (additive) |
| Add Plugin ABC tests | 12B-TEST-003, FR-012 | High | Low (additive) |
| Reduce 7 HIGH CC functions | 12B-CX-002-008, FR-007 | Medium | Medium (behavior preservation) |
| Add requirement markers | 12B-TEST-005, FR-013 | Medium | Low (additive) |

### Phase 3: Medium Priority (P2)

**Target**: Debt score 85 → 88

| Task | Requirement | Effort | Risk |
|------|-------------|--------|------|
| Split plugin_registry.py | 12B-ARCH-003, FR-003 | High | Medium (many importers) |
| Split oci/client.py | 12B-ARCH-004, FR-004 | High | Medium (facade pattern) |
| Reduce test duplication | 12B-TEST-006, FR-014 | Medium | Low (test refactor) |
| Performance hardening | 12B-PERF-001/002, FR-019/020 | Low | Low (additive limits) |

### Phase 4: Polish (P3)

**Target**: Debt score 88 → 90

| Task | Requirement | Effort | Risk |
|------|-------------|--------|------|
| Architecture refinement | 12B-ARCH-005-007 | Medium | Low (cleanup) |
| Knowledge transfer | 12B-HOT-001-003 | Low | N/A (documentation) |
| TODO cleanup | 12B-TODO-001-003 | Low | Low (documentation) |
| Documentation polish | 12B-DOC-001-002 | Low | N/A (documentation) |

## Dependencies

### External Dependencies

| Package | Current | Target | Reason |
|---------|---------|--------|--------|
| pydantic | >=2.0 | >=2.12.5,<3.0 | Upper bound for v3 protection |
| kubernetes | >=28.0.0 | >=35.0.0,<36.0 | Upper bound for API stability |
| pyiceberg | >=0.9.0 | >=0.10.0,<0.11.0 | Upper bound for schema stability |
| opentelemetry-api | >=1.20.0 | >=1.39.0,<2.0 | Update + upper bound |

### Internal Dependencies

| Change | Depends On | Reason |
|--------|------------|--------|
| Move TelemetryConfig | None | First step, no dependencies |
| Remove skipped tests | drop_table() implementation | Tests require functionality |
| Split plugin_registry.py | Circular dependency resolved | Clean separation required first |
| Split oci/client.py | None | Independent refactor |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Import path changes break external code | Medium | High | Maintain re-exports during transition |
| drop_table() implementation incomplete | Low | Medium | Follow existing table operation patterns |
| Complexity refactoring changes behavior | Low | High | 100% test coverage on refactored functions |
| Dependency pins too restrictive | Low | Low | Use >= with reasonable upper bounds |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 | Final |
|--------|---------|---------|---------|---------|-------|
| Debt Score | 74 | 80 | 85 | 88 | 90 |
| Critical Issues | 5 | 0 | 0 | 0 | 0 |
| High Issues | 19 | 14 | 5 | 0 | 0 |
| Skipped Tests | 3 | 0 | 0 | 0 | 0 |
| Max CC | 26 | ≤15 | ≤12 | ≤10 | ≤10 |
| CLI Coverage | 40% | 40% | 80% | 80% | 80% |
| Plugin ABC Coverage | 30% | 30% | 80% | 80% | 80% |

## Next Steps

1. Run `/speckit.tasks` to generate task breakdown
2. Run `/speckit.taskstolinear` to create Linear issues
3. Begin Phase 1 implementation with circular dependency resolution
