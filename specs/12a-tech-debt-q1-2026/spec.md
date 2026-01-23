# Feature Specification: January 2026 Tech Debt Reduction

**Epic**: 12A (Tech Debt Q1 2026)
**Feature Branch**: `12a-tech-debt-q1-2026`
**Created**: 2026-01-22
**Status**: Draft
**Input**: User description: "January 2026 Tech Debt Reduction - Address 5 CRITICAL and 12 HIGH priority issues from codebase audit"

## Overview

Systematic reduction of technical debt across the floe codebase, targeting the **5 CRITICAL** and **12 HIGH** priority issues identified in the January 2026 tech debt audit. This work enables faster development velocity, reduces maintenance burden, and improves overall code quality.

**Audit Reference**: `.claude/reviews/tech-debt-20260122-110030.json`

**Baseline Metrics**:
- Debt Score: 68/100 (Needs Work)
- Critical Issues: 5
- High Issues: 12
- Estimated Remediation: 18 person-days

## User Scenarios & Testing

### User Story 1 - Break Circular Dependency (Priority: P0)

**As a** platform maintainer, **I want** floe_core to use the plugin registry instead of direct imports, **so that** packages can be versioned and tested independently.

**Why this priority**: Circular dependencies prevent independent package versioning and make refactoring dangerous. This is the highest architectural risk.

**Independent Test**: Import both packages and verify no cycle: `python -c "import floe_core; import floe_rbac_k8s"`

**Acceptance Scenarios**:

1. **Given** the rbac/generator.py file, **When** I inspect its imports, **Then** it uses only the `RBACPlugin` ABC (no direct `K8sRBACPlugin` import)
2. **Given** the cli/rbac/generate.py file, **When** it needs an RBAC plugin instance, **Then** it retrieves it via the plugin registry lookup
3. **Given** both floe_core and floe_rbac_k8s packages, **When** I import them in sequence, **Then** no ImportError or circular import warning occurs
4. **Given** the refactored code, **When** I run the full test suite, **Then** all existing tests pass
5. **Given** the refactored code, **When** I run mypy --strict, **Then** no type errors are reported

---

### User Story 2 - Fix N+1 Performance Issues (Priority: P0)

**As a** platform user, **I want** OCI operations to complete quickly, **so that** listing and pulling artifacts doesn't timeout during normal operations.

**Why this priority**: N+1 patterns in OCI client cause exponential latency growth, making the system unusable with many artifacts.

**Independent Test**: Benchmark `client.list()` with 100 tags and measure total latency improvement.

**Acceptance Scenarios**:

1. **Given** an OCI registry with 100 tags, **When** I call `client.list()`, **Then** it completes within 6 seconds (vs 30s baseline)
2. **Given** the updated `client.list()` implementation, **When** I inspect the code, **Then** it uses parallel fetching with a thread pool
3. **Given** the updated `client.pull()` implementation, **When** I inspect the code, **Then** it uses dictionary lookup instead of linear search
4. **Given** the performance-optimized code, **When** I run the existing test suite, **Then** no functional regressions occur

---

### User Story 3 - Reduce Code Complexity (Priority: P1)

**As a** platform maintainer, **I want** complex functions refactored to lower cyclomatic complexity, **so that** code is testable and maintainable.

**Why this priority**: High complexity functions are bug-prone and difficult to test. These are the second-highest maintenance burden.

**Independent Test**: Run a complexity analyzer and verify CC scores meet targets.

**Acceptance Scenarios**:

1. **Given** the `diff_command()` function, **When** I measure cyclomatic complexity, **Then** it is 10 or lower (was 30)
2. **Given** the `pull()` method, **When** I measure cyclomatic complexity, **Then** it is 12 or lower (was 27)
3. **Given** the `_generate_impl()` function, **When** I inspect the code, **Then** it uses a Strategy pattern for variant handling
4. **Given** any refactored function, **When** I run golden tests with known inputs, **Then** outputs match the original behavior exactly
5. **Given** all refactored functions, **When** I run coverage, **Then** each has 100% test coverage

---

### User Story 4 - Split IcebergTableManager (Priority: P1)

**As a** platform maintainer, **I want** the IcebergTableManager split into focused classes, **so that** each class has single responsibility and is independently testable.

**Why this priority**: God classes (30 methods, 1,269 lines) violate single responsibility and are maintenance nightmares.

**Independent Test**: Verify the facade class has 5 or fewer public methods, and each extracted class has a dedicated test file.

**Acceptance Scenarios**:

1. **Given** the refactored IcebergTableManager, **When** I count its public methods, **Then** it has 5 or fewer (facade only)
2. **Given** the new `_IcebergTableLifecycle` internal class, **When** I inspect its responsibilities, **Then** it handles only create, drop, and exists operations
3. **Given** the new `_IcebergSchemaManager` internal class, **When** I inspect its responsibilities, **Then** it handles schema evolution operations (evolve, get_schema, add_column, drop_column)
4. **Given** the new `_IcebergSnapshotManager` internal class, **When** I inspect its responsibilities, **Then** it handles only snapshot operations
5. **Given** the new `_IcebergCompactionManager` internal class, **When** I inspect its responsibilities, **Then** it handles only compaction operations
6. **Given** any consumer of IcebergTableManager, **When** they use the existing public API, **Then** behavior is unchanged (facade delegates to internal classes)
7. **Given** each internal extracted class, **When** I look for test files, **Then** each has a dedicated test file (testing via facade or direct internal access)

---

### User Story 5 - Fix Test Policy Violations (Priority: P1)

**As a** platform maintainer, **I want** tests to fail explicitly rather than skip, **so that** CI accurately reports infrastructure issues.

**Why this priority**: Skipped tests create false confidence. CI shows "All tests pass" when infrastructure is missing.

**Independent Test**: Search for `pytest.skip()` calls in the test file and verify count is zero.

**Acceptance Scenarios**:

1. **Given** the `test_iceberg_io_manager.py` file, **When** I search for `pytest.skip()` calls, **Then** none are found
2. **Given** tests requiring infrastructure, **When** infrastructure is unavailable, **Then** tests fail with a clear message (not skip)
3. **Given** tests that were previously stubs (containing only `pass`), **When** I run them, **Then** they contain actual assertions
4. **Given** integration tests, **When** I inspect their implementation, **Then** they use the `IntegrationTestBase.check_infrastructure()` pattern

---

### User Story 6 - Add Missing Test Coverage (Priority: P1)

**As a** platform maintainer, **I want** OCI error and metrics modules fully tested, **so that** we have confidence in error handling.

**Why this priority**: Untested error handling paths are a reliability risk.

**Independent Test**: Run coverage on oci/ module and verify it exceeds 80%.

**Acceptance Scenarios**:

1. **Given** the new `tests/unit/oci/test_errors.py` file, **When** I run it, **Then** it covers the full exception hierarchy
2. **Given** the new `tests/unit/oci/test_metrics.py` file, **When** I run it, **Then** it covers metric emission for all scenarios
3. **Given** the oci/ module, **When** I run coverage analysis, **Then** coverage exceeds 80%
4. **Given** all new test functions, **When** I inspect their markers, **Then** each has a `@pytest.mark.requirement()` marker

---

### User Story 7 - Reduce Test Duplication (Priority: P2)

**As a** platform maintainer, **I want** shared base test classes for plugins, **so that** plugin tests are consistent and maintainable.

**Why this priority**: Test duplication (35% of test code) increases maintenance burden and inconsistency.

**Independent Test**: Verify new base classes exist and at least 3 plugin test files use them.

**Acceptance Scenarios**:

1. **Given** the testing/base_classes/ directory, **When** I look for base classes, **Then** `BasePluginMetadataTests`, `BasePluginLifecycleTests`, and `BasePluginDiscoveryTests` exist
2. **Given** the base test classes, **When** plugins extend them, **Then** they get consistent test coverage for common plugin behaviors
3. **Given** at least 3 plugin test files, **When** I inspect them after migration, **Then** they inherit from the new base classes
4. **Given** migrated plugin test files, **When** I count test functions, **Then** the count is reduced by more than 50%

---

### User Story 8 - Clean Up Dependencies (Priority: P3)

**As a** platform maintainer, **I want** unused dependencies removed, **so that** install size and security surface is minimized.

**Why this priority**: Unused dependencies increase attack surface and install time, but have low immediate impact.

**Independent Test**: Verify packages are removed from pyproject.toml and tests still pass.

**Acceptance Scenarios**:

1. **Given** the floe-orchestrator-dagster pyproject.toml, **When** I check dependencies, **Then** `croniter` is not listed
2. **Given** the floe-orchestrator-dagster pyproject.toml, **When** I check dependencies, **Then** `pytz` is not listed
3. **Given** the updated dependencies, **When** I run the full test suite, **Then** all tests pass
4. **Given** the updated dependencies, **When** I run any module that previously might have used these, **Then** no ImportError occurs

---

### Edge Cases

- What happens if a refactoring introduces a subtle behavioral change?
  - *Golden tests with known inputs validate exact output matching*
- How do we handle if performance benchmarks are environment-dependent?
  - *Measure relative improvement (5x faster), not absolute thresholds*
- What if removing pytest.skip() causes CI to fail on missing infrastructure?
  - *Tests fail with clear message indicating infrastructure requirement*
- What happens if an extracted class from IcebergTableManager is imported directly?
  - *Public API through facade; internal classes prefixed with underscore*

## Requirements

### Functional Requirements

**Architecture**

- **FR-001**: System MUST have no circular import dependencies between floe_core and floe_rbac_k8s packages
- **FR-002**: rbac/generator.py MUST use only the RBACPlugin ABC (no concrete plugin imports)
- **FR-003**: cli/rbac/generate.py MUST retrieve plugin instances via registry lookup
- **FR-004**: OCIClient class MUST be less than 500 lines of code after extraction

**Performance**

- **FR-005**: OCI `client.list()` MUST use parallel fetching with configurable concurrency
- **FR-006**: OCI `client.pull()` MUST use dictionary lookup instead of loop-based search
- **FR-007**: plugin_registry.list() MUST accept an optional `limit` parameter to bound results
- **FR-008**: PolicyEnforcer.enforce() MUST accept an optional `max_violations` parameter for early exit
- **FR-009**: RBAC aggregate_permissions() MUST use caching for repeated permission lookups

**Complexity**

- **FR-010**: `diff_command()` function MUST have cyclomatic complexity of 10 or lower
- **FR-011**: `pull()` method MUST have cyclomatic complexity of 12 or lower
- **FR-012**: IcebergTableManager MUST be a facade with 5 or fewer public methods
- **FR-013**: `_IcebergTableLifecycle` (internal) MUST handle table create, drop, and exists operations only
- **FR-014**: `_IcebergSchemaManager` (internal) MUST handle schema evolution operations only
- **FR-015**: `_IcebergSnapshotManager` (internal) MUST handle snapshot operations only
- **FR-016**: `_IcebergCompactionManager` (internal) MUST handle compaction operations only
- **FR-017**: `_generate_impl()` MUST use Strategy pattern for variant handling

**Testing**

- **FR-018**: No `pytest.skip()` calls SHALL exist in test_iceberg_io_manager.py
- **FR-019**: tests/unit/oci/test_errors.py MUST cover the full OCI exception hierarchy
- **FR-020**: tests/unit/oci/test_metrics.py MUST cover all metric emission scenarios
- **FR-021**: All new tests MUST have `@pytest.mark.requirement()` markers
- **FR-022**: BasePluginMetadataTests MUST exist in testing/base_classes/
- **FR-023**: BasePluginLifecycleTests MUST exist in testing/base_classes/
- **FR-024**: BasePluginDiscoveryTests MUST exist in testing/base_classes/

**Dependencies**

- **FR-025**: floe-orchestrator-dagster MUST NOT depend on `croniter`
- **FR-026**: floe-orchestrator-dagster MUST NOT depend on `pytz`

### Key Entities

- **TechDebtAudit**: Represents a point-in-time assessment of codebase quality, with debt score, issue counts by severity, and categorized findings
- **PluginRegistry**: Central registry for discovering and loading plugin implementations via entry points
- **RBACPlugin**: Abstract base class defining the interface for RBAC implementations
- **IcebergTableManager**: Facade class delegating to internal specialized managers (`_IcebergTableLifecycle`, `_IcebergSchemaManager`, `_IcebergSnapshotManager`, `_IcebergCompactionManager`) for table lifecycle, schema, snapshots, and compaction
- **OCIClient**: Client for interacting with OCI registries to list, pull, and push artifacts

## Clarifications

- Q: Should the extracted IcebergTableManager classes be internal (underscore-prefixed) or public? A: Internal (underscore-prefixed) - `_IcebergTableLifecycle`, `_IcebergSchemaManager`, `_IcebergSnapshotManager`, `_IcebergCompactionManager`. This enforces facade pattern encapsulation and prevents direct imports.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Tech debt score improves from 68 to 80 or higher (+12 points)
- **SC-002**: Critical issue count reduced from 5 to 0
- **SC-003**: High issue count reduced from 12 to 3 or fewer
- **SC-004**: Maximum cyclomatic complexity in codebase reduced from 30 to 15 or lower
- **SC-005**: Maximum methods per class reduced from 30 to 15 or lower (IcebergTableManager)
- **SC-006**: Test skip count reduced from 4 to 0
- **SC-007**: OCI list() latency with 100 tags reduced from 30s to under 6s (5x improvement)
- **SC-008**: OCI module test coverage exceeds 80%
- **SC-009**: All existing tests continue to pass (no regressions)
- **SC-010**: mypy --strict passes on all modified files
