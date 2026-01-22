# Implementation Plan: January 2026 Tech Debt Reduction

**Branch**: `12a-tech-debt-q1-2026` | **Date**: 2026-01-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/12a-tech-debt-q1-2026/spec.md`

## Summary

Address 5 CRITICAL and 12 HIGH priority technical debt issues identified in the January 2026 codebase audit. Primary focus areas:

1. **Architecture**: Break circular dependency (floe_core ↔ floe_rbac_k8s) via registry lookup
2. **Performance**: Fix N+1 patterns in OCI client via parallel fetching and dictionary lookup
3. **Complexity**: Refactor high-CC functions (diff_command, pull) and split IcebergTableManager god class into facade + internal classes
4. **Testing**: Remove pytest.skip() violations, add missing coverage, create base test classes

**Target**: Debt score 68 → 80, Critical issues 5 → 0, High issues 12 → 3

## Technical Context

**Language/Version**: Python 3.10+ (required for `importlib.metadata.entry_points()` improved API)
**Primary Dependencies**: Pydantic v2, structlog, pytest, concurrent.futures (ThreadPoolExecutor), PyIceberg
**Storage**: N/A (refactoring existing code, no new storage)
**Testing**: pytest with pytest-cov, K8s-native testing via Kind cluster
**Target Platform**: Linux server, macOS development
**Project Type**: Monorepo with multiple packages
**Performance Goals**: OCI list() 5x faster (30s → 6s for 100 tags), CC max 30 → 15
**Constraints**: Zero behavioral regression, backward-compatible public APIs
**Scale/Scope**: ~2,600 Python files, 26 functional requirements, 8 user stories

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Principle I: Technology Ownership**
- [x] Code is placed in correct package (floe-core, floe-iceberg, plugins/)
- [x] No SQL parsing/validation in Python (N/A - no SQL changes)
- [x] No orchestration logic outside floe-dagster (N/A - no orchestration changes)

**Principle II: Plugin-First Architecture**
- [x] New configurable component uses plugin interface (ABC) - circular dep fix uses RBACPlugin ABC
- [x] Plugin registered via entry point (not direct import) - registry lookup enforced
- [x] PluginMetadata declares name, version, floe_api_version (N/A - no new plugins)

**Principle III: Enforced vs Pluggable**
- [x] Enforced standards preserved (Iceberg, OTel, OpenLineage, dbt, K8s)
- [x] Pluggable choices documented in manifest.yaml (N/A - no new pluggable)

**Principle IV: Contract-Driven Integration**
- [x] Cross-package data uses CompiledArtifacts (not direct coupling)
- [x] Pydantic v2 models for all schemas
- [x] Contract changes follow versioning rules (N/A - no schema changes)

**Principle V: K8s-Native Testing**
- [x] Integration tests run in Kind cluster
- [x] No `pytest.skip()` usage - **ACTIVELY REMOVING** (FR-018)
- [x] `@pytest.mark.requirement()` on all integration tests (FR-021)

**Principle VI: Security First**
- [x] Input validation via Pydantic (existing patterns preserved)
- [x] Credentials use SecretStr (existing patterns preserved)
- [x] No shell=True, no dynamic code execution on untrusted data

**Principle VII: Four-Layer Architecture**
- [x] Configuration flows downward only (N/A - no layer changes)
- [x] Layer ownership respected (Data Team vs Platform Team)

**Principle VIII: Observability By Default**
- [x] OpenTelemetry traces emitted (existing patterns preserved)
- [x] OpenLineage events for data transformations (N/A - no new transforms)

**Constitution Check Result**: PASSED - All principles satisfied or N/A

## Project Structure

### Documentation (this feature)

```text
specs/12a-tech-debt-q1-2026/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (files to modify)

```text
# Architecture Refactoring (US1: Circular Dependency)
packages/floe-core/src/floe_core/
├── rbac/generator.py           # FR-001, FR-002: Remove direct K8sRBACPlugin import
├── cli/rbac/generate.py        # FR-003: Use registry lookup
└── plugin_registry.py          # FR-007: Add limit parameter

# Performance Refactoring (US2: N+1 Fixes)
packages/floe-core/src/floe_core/oci/
├── client.py                   # FR-004, FR-005, FR-006: Parallel fetch, dict lookup
└── [new] batch_fetcher.py      # Extracted parallel fetching logic

# Complexity Refactoring (US3, US4: CC Reduction, God Class Split)
packages/floe-core/src/floe_core/cli/rbac/
└── diff.py                     # FR-010: Refactor diff_command() CC 30→10

packages/floe-core/src/floe_core/oci/
└── client.py                   # FR-011: Refactor pull() CC 27→12

packages/floe-iceberg/src/floe_iceberg/
├── manager.py                  # FR-012: Facade with ≤5 public methods
├── [new] _lifecycle.py         # FR-013: _IcebergTableLifecycle
├── [new] _schema_manager.py    # FR-014: _IcebergSchemaManager
├── [new] _snapshot_manager.py  # FR-015: _IcebergSnapshotManager
└── [new] _compaction_manager.py# FR-016: _IcebergCompactionManager

packages/floe-core/src/floe_core/
└── enforcement/policy_enforcer.py  # FR-008: Add max_violations parameter

# Test Fixes (US5, US6, US7)
plugins/floe-orchestrator-dagster/tests/integration/
└── test_iceberg_io_manager.py  # FR-018: Remove pytest.skip() calls

packages/floe-core/tests/unit/oci/
├── [new] test_errors.py        # FR-019: Exception hierarchy tests
└── [new] test_metrics.py       # FR-020: Metric emission tests

testing/base_classes/
├── [new] plugin_metadata_tests.py   # FR-022: BasePluginMetadataTests
├── [new] plugin_lifecycle_tests.py  # FR-023: BasePluginLifecycleTests
└── [new] plugin_discovery_tests.py  # FR-024: BasePluginDiscoveryTests

# Dependency Cleanup (US8)
plugins/floe-orchestrator-dagster/
└── pyproject.toml              # FR-025, FR-026: Remove croniter, pytz
```

**Structure Decision**: Monorepo with existing package layout. All changes are refactoring within existing packages. New files are internal modules (underscore-prefixed) or test infrastructure.

## Complexity Tracking

> No constitution violations requiring justification. All refactoring follows established patterns.

| Decision | Rationale | Simpler Alternative |
|----------|-----------|---------------------|
| Facade pattern for IcebergTableManager | Maintains backward compatibility while enabling SRP | Direct split would break consumers |
| ThreadPoolExecutor for parallel fetch | Compatible with sync codebase, no asyncio migration needed | asyncio requires broader refactoring |
| Internal classes with underscore prefix | Enforces facade encapsulation, prevents accidental coupling | Public classes allow bypass of facade |

## Implementation Approach

### Phase 1: Architecture & Performance (P0 - Week 1)

**US1: Break Circular Dependency**
1. Extract `RBACPlugin` interface usage in generator.py
2. Replace direct import with registry lookup in cli/rbac/generate.py
3. Add import cycle detection test
4. Verify with `python -c "import floe_core; import floe_rbac_k8s"`

**US2: Fix N+1 Performance**
1. Create `_BatchFetcher` class for parallel HTTP calls
2. Refactor `client.list()` to use ThreadPoolExecutor (max_workers=10)
3. Refactor `client.pull()` to build tag→layer dict for O(1) lookup
4. Add performance benchmark tests (100 tags in <6s)

### Phase 2: Complexity Reduction (P1 - Week 2)

**US3: Reduce Code Complexity**
1. Apply Extract Method to diff_command() (CC 30→10)
2. Apply Extract Method to pull() (CC 27→12)
3. Apply Strategy pattern to _generate_impl()
4. Create golden tests before refactoring
5. Verify exact output match after refactoring

**US4: Split IcebergTableManager**
1. Create `_IcebergTableLifecycle` (create, drop, exists)
2. Create `_IcebergSchemaManager` (evolve, get_schema)
3. Create `_IcebergSnapshotManager` (snapshot, rollback)
4. Create `_IcebergCompactionManager` (compact, rewrite)
5. Convert IcebergTableManager to facade (≤5 public methods)
6. Add test files for each extracted class

### Phase 3: Testing Improvements (P1 - Week 3)

**US5: Fix Test Policy Violations**
1. Remove pytest.skip() from test_iceberg_io_manager.py
2. Convert to IntegrationTestBase.check_infrastructure() pattern
3. Implement stub tests with actual assertions

**US6: Add Missing Coverage**
1. Create test_errors.py covering OCI exception hierarchy
2. Create test_metrics.py covering metric emission
3. Add @pytest.mark.requirement() markers

**US7: Create Base Test Classes**
1. Create BasePluginMetadataTests
2. Create BasePluginLifecycleTests
3. Create BasePluginDiscoveryTests
4. Migrate 3 plugin test files to use base classes

### Phase 4: Cleanup (P3 - Week 4)

**US8: Remove Unused Dependencies**
1. Remove croniter from floe-orchestrator-dagster
2. Remove pytz from floe-orchestrator-dagster
3. Run tests to verify no import errors

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Behavioral regression | MEDIUM | HIGH | Golden tests before refactoring, comprehensive test coverage |
| Performance benchmark variability | LOW | MEDIUM | Measure relative improvement (5x), not absolute thresholds |
| Test migration breaks CI | LOW | HIGH | Migrate one test file at a time, verify CI green |
| Circular dep fix incomplete | LOW | MEDIUM | Import cycle detection test catches any remaining cycles |

## Verification Strategy

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Debt Score | 68 | 80+ | /tech-debt-review --all |
| Critical Issues | 5 | 0 | /tech-debt-review --all |
| Max CC | 30 | ≤15 | radon cc --show-complexity |
| Max Class Methods | 30 | ≤15 | Manual count on IcebergTableManager |
| pytest.skip() Count | 4 | 0 | rg "pytest.skip" --type py tests/ |
| OCI list() Latency | 30s | <6s | Benchmark test with 100 tags |
| OCI Coverage | <80% | >80% | pytest --cov=floe_core.oci |
| mypy --strict | N/A | 0 errors | mypy --strict on modified files |
