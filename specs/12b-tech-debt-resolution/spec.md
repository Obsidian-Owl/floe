# Feature Specification: Tech Debt Resolution (Epic 12B)

**Epic**: 12B (Tech Debt Q1 2026 - Improvement Opportunities)
**Feature Branch**: `12b-tech-debt-resolution`
**Created**: 2026-01-22
**Status**: Draft
**Input**: User description: "ensure you deeply research each debt to determine the right method to resolve each that aligns with strategic architecture"

## Overview

This specification details architecture-aligned resolution methods for the 37 technical debt issues identified in the January 2026 comprehensive audit. Each resolution is designed to align with the floe four-layer architecture and composability principles (ADR-0037).

**Source Audit**: `.claude/reviews/tech-debt-20260122-154004.json`
**Current Score**: 74/100 (Good)
**Target Score**: 90/100 (Excellent)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolve Circular Dependencies (Priority: P0)

**As a** platform maintainer
**I want** the circular dependency between schemas, telemetry, and plugins resolved
**So that** I can import any module independently without side effects

**Why this priority**: Circular dependencies cause import errors during testing, complicate the dependency graph, and violate the four-layer architecture principle where lower layers should not depend on higher layers.

**Independent Test**: Can be fully tested by verifying `import floe_core.schemas` works without importing telemetry or plugins, and all existing tests pass.

**Acceptance Scenarios**:

1. **Given** a fresh Python environment, **When** I run `python -c "from floe_core.schemas import CompiledArtifacts"`, **Then** no telemetry or plugin modules are imported as side effects
2. **Given** the refactored codebase, **When** I run `python -m mypy --strict packages/floe-core/`, **Then** there are 0 import cycle errors
3. **Given** the refactored codebase, **When** I run `pytest packages/floe-core/tests/`, **Then** all tests pass without import ordering dependencies

---

### User Story 2 - Remove Skipped Tests (Priority: P0)

**As a** platform maintainer
**I want** all skipped tests either implemented or removed
**So that** CI accurately reports test coverage and no functionality is silently untested

**Why this priority**: Skipped tests violate Constitution Principle V ("Tests FAIL, never skip") and hide missing functionality. The 3 skipped tests for `drop_table()` indicate incomplete Iceberg lifecycle implementation.

**Independent Test**: Can be fully tested by running `pytest --co -q | grep -c skip` and verifying the count is 0.

**Acceptance Scenarios**:

1. **Given** the current codebase, **When** I run `pytest packages/floe-iceberg/ -v`, **Then** 0 tests are skipped
2. **Given** the `drop_table()` implementation, **When** I call `manager.drop_table("test_table")`, **Then** the table is removed from the catalog
3. **Given** a non-existent table, **When** I call `manager.drop_table("missing")`, **Then** a `TableNotFoundError` is raised

---

### User Story 3 - Reduce Critical Complexity (Priority: P0)

**As a** platform maintainer
**I want** the `map_pyiceberg_error()` function refactored from CC 26 to CC ≤10
**So that** the error handling is maintainable and testable

**Why this priority**: Cyclomatic complexity of 26 is critically high (threshold: 20). The function has 16 consecutive if-statements making it error-prone and difficult to test comprehensively.

**Independent Test**: Can be fully tested by running complexity analysis and verifying CC ≤10, plus testing all error mappings.

**Acceptance Scenarios**:

1. **Given** the refactored function, **When** I measure cyclomatic complexity, **Then** CC ≤ 10
2. **Given** a `ServiceUnavailableError`, **When** mapped through the function, **Then** a `CatalogUnavailableError` is returned with correct message
3. **Given** an unknown exception type, **When** mapped through the function, **Then** a generic `CatalogError` is returned with the original message preserved

---

### User Story 4 - Split God Modules (Priority: P1)

**As a** platform maintainer
**I want** `plugin_registry.py` (1230 lines) and `oci/client.py` (1389 lines) split into focused classes
**So that** each module has a single responsibility and is independently testable

**Why this priority**: God modules violate Single Responsibility Principle, have high cognitive load, and create shotgun surgery risk where changes to one concern require modifications across the entire file.

**Independent Test**: Can be fully tested by verifying each new module has ≤400 lines and all existing tests pass.

**Acceptance Scenarios**:

1. **Given** the refactored plugin system, **When** I examine `plugin_registry.py`, **Then** it has ≤400 lines and delegates to focused helpers
2. **Given** the refactored OCI client, **When** I examine each file in `oci/`, **Then** no file exceeds 400 lines
3. **Given** the refactored modules, **When** I run the full test suite, **Then** all tests pass without modification

---

### User Story 5 - Pin Critical Dependencies (Priority: P1)

**As a** platform maintainer
**I want** all critical dependencies pinned with upper bounds
**So that** builds are reproducible and we're protected from breaking changes

**Why this priority**: Unpinned dependencies (11 total) can cause silent breakage when upstream releases incompatible versions. This is especially critical for pydantic (v3 will break v2 code) and kubernetes client.

**Independent Test**: Can be fully tested by verifying all `pyproject.toml` files have upper bounds on critical deps.

**Acceptance Scenarios**:

1. **Given** any `pyproject.toml`, **When** I check pydantic dependency, **Then** it has format `>=2.12.5,<3.0`
2. **Given** any `pyproject.toml`, **When** I check kubernetes dependency, **Then** it has format `>=35.0.0,<36.0`
3. **Given** a fresh `uv sync`, **When** I run `pip-audit`, **Then** 0 vulnerabilities are reported

---

### User Story 6 - Increase Test Coverage (Priority: P1)

**As a** platform maintainer
**I want** CLI RBAC commands and Plugin ABCs to have ≥80% test coverage
**So that** core functionality is verified and regressions are caught

**Why this priority**: Current coverage gaps (CLI 40%, Plugin ABCs 30%) leave critical code paths untested. These are high-risk areas that affect all platform users.

**Independent Test**: Can be fully tested by running coverage reports per module.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** I run `pytest --cov=floe_core.cli.rbac`, **Then** coverage is ≥80%
2. **Given** the test suite, **When** I run `pytest --cov=floe_core.plugins`, **Then** ABC coverage is ≥80%
3. **Given** any new CLI command, **When** added, **Then** it has positive and negative path tests

---

### User Story 7 - Reduce Remaining High Complexity (Priority: P2)

**As a** platform maintainer
**I want** the 7 HIGH complexity functions (CC 15-18) refactored to CC ≤12
**So that** all functions are maintainable

**Why this priority**: While not critical, these functions are harder to test and modify. Reducing complexity improves long-term maintainability.

**Independent Test**: Can be fully tested by running complexity analysis on each function.

**Acceptance Scenarios**:

1. **Given** `audit_command()`, **When** refactored, **Then** CC ≤ 12 and all tests pass
2. **Given** `enforce()`, **When** refactored, **Then** CC ≤ 12 and all tests pass
3. **Given** `validate()` in token_validator, **When** refactored, **Then** CC ≤ 12 and all tests pass

---

### User Story 8 - Reduce Test Duplication (Priority: P2)

**As a** platform maintainer
**I want** test duplication reduced from 31.6% to ≤15%
**So that** test maintenance is simplified and changes are localized

**Why this priority**: High duplication means changes to shared patterns require updates in multiple places, increasing maintenance burden and risk of inconsistency.

**Independent Test**: Can be fully tested by running duplication analysis on test files.

**Acceptance Scenarios**:

1. **Given** audit event tests, **When** deduplicated, **Then** shared fixtures are in conftest.py
2. **Given** plugin discovery tests, **When** deduplicated, **Then** they inherit from BasePluginDiscoveryTests
3. **Given** the test suite, **When** I run duplication analysis, **Then** ratio is ≤15%

---

### Edge Cases

- What happens when `drop_table()` is called during active queries? → **Deferred**: PyIceberg does not expose active query state; document as known limitation
- What happens when error mapping receives a chained exception? → Should preserve full chain
- What happens when plugin registry is accessed during shutdown? → **Deferred**: Shutdown sequencing handled by orchestrator; registry access during shutdown is undefined behavior
- How does system handle circular import during TYPE_CHECKING? → Use `if TYPE_CHECKING:` guards

---

## Requirements *(mandatory)*

### Functional Requirements

*Note: FR-### IDs are spec-internal. Each FR maps to a 12B-### backlog item (see Resolution Methods tables).*

#### Architecture (12B-ARCH)

- **FR-001**: System MUST NOT have circular import dependencies between `schemas`, `telemetry`, and `plugins` modules
- **FR-002**: `floe_core/__init__.py` MUST export ≤15 symbols (currently 76)
- **FR-003**: `plugin_registry.py` MUST be split into focused modules each ≤400 lines
- **FR-004**: `oci/client.py` MUST be split into focused modules each ≤400 lines
- **FR-005**: Each submodule `__init__.py` MUST export only public API symbols

**Resolution Methods (Architecture-Aligned)**:

| Requirement | Resolution Method | Alignment |
|-------------|-------------------|-----------|
| FR-001 | Move `TelemetryConfig` to `schemas/telemetry.py` or use `TYPE_CHECKING` imports | Layer separation: schemas (L1) should not import from services (L3) |
| FR-002 | Create explicit public API with `__all__` containing ~15 essentials | Composability: prefer explicit interfaces over implicit exports |
| FR-003 | Apply Single Responsibility: discovery.py, loader.py, lifecycle.py, deps.py | Plugin architecture: each plugin concern is independent |
| FR-004 | Apply Facade pattern: manifest.py, layers.py, client.py orchestrator | OCI registry is L2 configuration layer |
| FR-005 | Remove re-exports, require explicit imports from source modules | Explicit over implicit |

#### Complexity (12B-CX)

- **FR-006**: `map_pyiceberg_error()` MUST have cyclomatic complexity ≤10 (currently 26)
- **FR-007**: All HIGH complexity functions (CC 15-18) MUST be refactored to CC ≤12
- **FR-008**: All functions MUST have nesting depth ≤4 (13 functions exceed)
- **FR-009**: Long functions (>100 lines) MUST be reviewed for extraction opportunities

**Resolution Methods (Architecture-Aligned)**:

| Requirement | Resolution Method | Alignment |
|-------------|-------------------|-----------|
| FR-006 | Strategy Pattern: dispatch dictionary with type→handler mapping | Composability: handlers are pluggable |
| FR-007 | Extract Method: separate validation phases, flatten conditionals | Testability: each method independently testable |
| FR-008 | Extract inner loops to named methods | Readability: clear intent at each level |
| FR-009 | Apply command pattern for CLI, extract retry policies to decorators | Separation of concerns |

#### Testing (12B-TEST)

- **FR-010**: Test suite MUST have 0 skipped tests (currently 3)
- **FR-011**: CLI RBAC commands MUST have ≥80% test coverage (currently 40%)
- **FR-012**: Plugin ABCs MUST have ≥80% test coverage (currently 30%)
- **FR-013**: 100% of tests MUST have `@pytest.mark.requirement()` markers (currently 92.4%)
- **FR-014**: Test duplication ratio MUST be ≤15% (currently 31.6%)

**Resolution Methods (Architecture-Aligned)**:

| Requirement | Resolution Method | Alignment |
|-------------|-------------------|-----------|
| FR-010 | Implement `drop_table()` in IcebergTableManager or delete tests | Tests FAIL never skip (Constitution V) |
| FR-011 | Add unit tests for each Click command, integration tests for RBAC flows | CLI is thin layer delegating to core |
| FR-012 | Create BasePluginTests with compliance, discovery, lifecycle checks | All 11 plugin types follow same ABC contract |
| FR-013 | Automated marker insertion with traceability tool | Spec traceability requirement |
| FR-014 | Extract to conftest.py, create Base*Tests classes, parametrize | DRY principle |

#### Dependencies (12B-DEP)

- **FR-015**: All critical dependencies MUST have upper bounds (pydantic, kubernetes, pyiceberg)
- **FR-016**: No dependency MUST be more than 1 major version behind latest
- **FR-017**: `pip-audit` MUST report 0 vulnerabilities
- **FR-018**: Unused packages MUST be removed (investigate floe-cli)

**Resolution Methods (Architecture-Aligned)**:

| Requirement | Resolution Method | Alignment |
|-------------|-------------------|-----------|
| FR-015 | Add `<MAJOR+1.0` bounds: pydantic>=2.12.5,<3.0 | Reproducible builds |
| FR-016 | Schedule quarterly dependency updates | Continuous improvement |
| FR-017 | Add pip-audit to CI pre-commit | Security first |
| FR-018 | Audit package usage, deprecate empty packages | Clean architecture |

#### Performance (12B-PERF)

- **FR-019**: RBAC diff MUST validate resource counts before processing
- **FR-020**: String concatenation in recursive paths MUST use efficient patterns

**Resolution Methods (Architecture-Aligned)**:

| Requirement | Resolution Method | Alignment |
|-------------|-------------------|-----------|
| FR-019 | Add `max_resources` parameter with default 10000, fail fast if exceeded | Explicit limits |
| FR-020 | Use `os.path.join()` or pathlib instead of f-string concatenation | Standard library patterns |

### Key Entities

- **TelemetryConfig**: Configuration for OpenTelemetry emission, currently in wrong location
- **PluginRegistry**: Central registry for all 11 plugin types, needs decomposition
- **OCIClient**: OCI registry client, needs facade extraction
- **CompiledArtifacts**: Contract between packages (must remain stable during refactoring)

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Debt score improves from 74 to ≥85 after Phase 1 (critical issues)
- **SC-002**: Debt score improves from 85 to ≥90 after Phase 2 (high issues)
- **SC-003**: Zero circular import errors detected by `mypy --strict`
- **SC-004**: Zero skipped tests in pytest output
- **SC-005**: Maximum cyclomatic complexity ≤10 for critical functions (FR-006), ≤12 for high complexity functions (FR-007)
- **SC-006**: Test coverage ≥80% for CLI and Plugin ABCs
- **SC-007**: All dependencies have upper bounds in pyproject.toml
- **SC-008**: Test duplication ratio ≤15%
- **SC-009**: All 37 requirements addressed with appropriate resolution

### Verification Commands

```bash
# SC-001/SC-002: Debt score
/tech-debt-review --all

# SC-003: Circular imports
python -m mypy --strict packages/floe-core/

# SC-004: Skipped tests
pytest --co -q 2>/dev/null | grep -c "skip" || echo "0"

# SC-005: Complexity
python3 scripts/analyze_complexity.py | grep "CC > 15" | wc -l

# SC-006: Coverage
pytest --cov=floe_core.cli.rbac --cov-report=term-missing
pytest --cov=floe_core.plugins --cov-report=term-missing

# SC-007: Dependency bounds
grep -r "pydantic>=" packages/*/pyproject.toml | grep -v "<"

# SC-008: Duplication
# Run test duplication analyzer

# SC-009: All requirements
cat .claude/reviews/tech-debt-*.json | jq '.total_issues'
```

---

## Implementation Phases

### Phase 1: Critical Issues (P0) - Target: 80/100

| ID | Requirement | Resolution | Effort |
|----|-------------|------------|--------|
| 12B-ARCH-001 | Break circular dependency | Move TelemetryConfig to schemas/ | Low |
| 12B-TEST-001 | Remove skipped tests | Implement drop_table() | Medium |
| 12B-CX-001 | Reduce map_pyiceberg_error CC | Strategy pattern dispatch | Low |
| 12B-DEP-001 | Pin pydantic | Add <3.0 bound | Low |
| 12B-DEP-002 | Pin kubernetes | Add <36.0 bound | Low |

### Phase 2: High Priority (P1) - Target: 85/100

| ID | Requirement | Resolution | Effort |
|----|-------------|------------|--------|
| 12B-ARCH-002 | Reduce __init__.py exports | Create explicit __all__ | Medium |
| 12B-TEST-002 | CLI RBAC coverage | Add unit tests | High |
| 12B-TEST-003 | Plugin ABC coverage | Add compliance tests | High |
| 12B-CX-002-008 | Reduce 7 HIGH CC functions | Extract methods | Medium |
| 12B-TEST-005 | Requirement markers | Automated insertion | Medium |

### Phase 3: Medium Priority (P2) - Target: 88/100

| ID | Requirement | Resolution | Effort |
|----|-------------|------------|--------|
| 12B-ARCH-003 | Split plugin_registry.py | SRP decomposition | High |
| 12B-ARCH-004 | Split oci/client.py | Facade pattern | High |
| 12B-TEST-006 | Test duplication | Extract to base classes | Medium |
| 12B-PERF-001/002 | Performance hardening | Add limits, optimize | Low |

### Phase 4: Polish (P3) - Target: 90/100

| ID | Requirement | Resolution | Effort |
|----|-------------|------------|--------|
| 12B-ARCH-005-007 | Architecture refinement | Reduce re-exports | Medium |
| 12B-HOT-001-003 | Knowledge transfer | Documentation + sessions | Low |
| 12B-TODO-001-003 | TODO cleanup | Resolve or document | Low |
| 12B-DOC-001-002 | Documentation | Add issue links | Low |
| 12B-DEAD-001 | Dead code review | Document intent | Low |

---

## Architecture Alignment Summary

All resolutions align with floe's strategic architecture:

1. **Four-Layer Model**: Circular dependency fix ensures Layer 1 (schemas) doesn't depend on Layer 3 (services)
2. **Composability (ADR-0037)**: Strategy pattern for error handling allows pluggable handlers
3. **Plugin Architecture**: SRP decomposition of PluginRegistry aligns with 11 independent plugin types
4. **Contract-Driven**: CompiledArtifacts remains stable throughout refactoring
5. **K8s-Native Testing**: All test improvements maintain K8s-native execution model

---

## References

- **Audit Report**: `.claude/reviews/tech-debt-20260122-154004.json`
- **Epic 12B Backlog**: `docs/plans/epics/12-tech-debt/epic-12b-improvement-opportunities.md`
- **Complexity Analysis**: `docs/analysis/complexity-analysis-2026-01-22.md`
- **Architecture**: `docs/architecture/ARCHITECTURE-SUMMARY.md`
- **Constitution**: `.specify/memory/constitution.md`
- **Linear Project**: https://linear.app/obsidianowl/project/epic-12b-improvement-opportunities-0246800533dd
