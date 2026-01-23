# Epic 12A: January 2026 Tech Debt Reduction

> **Audience**: floe platform contributors and maintainers
>
> **Purpose**: Address critical technical debt identified in the 2026-01-22 full codebase audit

## Summary

Systematic reduction of technical debt across the floe codebase, targeting the **5 CRITICAL** and **12 HIGH** priority issues identified in the January 2026 tech debt audit. Focus areas include architecture (circular dependencies), performance (N+1 patterns), code complexity, and test quality.

## Status

- [x] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: Tech Debt Q1 2026

**Audit Reference**: `.claude/reviews/tech-debt-20260122-110030.json`

---

## Requirements Covered

| Requirement ID | Description | Priority | Category |
|----------------|-------------|----------|----------|
| **Architecture** |
| 12A-FR-001 | Break circular dependency floe_core ↔ floe_rbac_k8s | CRITICAL | Architecture |
| 12A-FR-002 | Plan package extraction roadmap (floe-schemas, floe-oci) | HIGH | Architecture |
| 12A-FR-003 | Reduce OCIClient class to < 500 LOC via extraction | HIGH | Architecture |
| **Performance** |
| 12A-FR-004 | Fix N+1 HTTP calls in OCI client.list() | CRITICAL | Performance |
| 12A-FR-005 | Fix N+1 I/O in OCI client.pull() | CRITICAL | Performance |
| 12A-FR-006 | Add limit parameter to plugin_registry.list() | HIGH | Performance |
| 12A-FR-007 | Add max_violations to PolicyEnforcer.enforce() | MEDIUM | Performance |
| 12A-FR-008 | Add caching to RBAC aggregate_permissions() | MEDIUM | Performance |
| **Complexity** |
| 12A-FR-009 | Refactor diff_command() CC 30→10 | CRITICAL | Complexity |
| 12A-FR-010 | Refactor pull() method CC 27→12 | HIGH | Complexity |
| 12A-FR-011 | Split IcebergTableManager into 5 focused classes | HIGH | Complexity |
| 12A-FR-012 | Apply Strategy pattern to _generate_impl() | MEDIUM | Complexity |
| **Testing** |
| 12A-FR-013 | Remove pytest.skip() calls (4 occurrences) | HIGH | Testing |
| 12A-FR-014 | Add tests for oci/errors.py | HIGH | Testing |
| 12A-FR-015 | Add tests for oci/metrics.py | HIGH | Testing |
| 12A-FR-016 | Create base test classes for plugin tests | MEDIUM | Testing |
| 12A-FR-017 | Parametrize duplicated test patterns | MEDIUM | Testing |
| **Dependencies** |
| 12A-FR-018 | Remove unused croniter, pytz dependencies | LOW | Dependencies |
| 12A-FR-019 | Review plugin ABCs without implementations | LOW | Dead Code |

---

## Architecture References

### ADRs
- Existing ADRs remain valid; this Epic addresses implementation drift

### Audit Data
- Full audit: `.claude/reviews/tech-debt-20260122-110030.json`
- Skill used: `/tech-debt-review --all`

### Key Metrics (Baseline)
- Debt Score: 68/100 (Needs Work)
- Critical Issues: 5
- High Issues: 12
- Estimated Remediation: 18 person-days

---

## File Ownership (Exclusive)

```text
packages/floe-core/src/floe_core/
├── rbac/generator.py           # 12A-FR-001: Remove direct plugin import
├── cli/rbac/generate.py        # 12A-FR-001: Use registry lookup
├── cli/rbac/diff.py            # 12A-FR-009: Refactor diff_command()
├── oci/client.py               # 12A-FR-003, 04, 05, 10: OCI refactoring
├── plugin_registry.py          # 12A-FR-006: Add limit parameter
├── enforcement/policy_enforcer.py  # 12A-FR-007: Add max_violations

packages/floe-core/tests/unit/
├── oci/test_errors.py          # 12A-FR-014: NEW
├── oci/test_metrics.py         # 12A-FR-015: NEW

packages/floe-iceberg/src/floe_iceberg/
├── manager.py                  # 12A-FR-011: Split into focused classes
├── lifecycle.py                # 12A-FR-011: NEW (extracted)
├── schema_manager.py           # 12A-FR-011: NEW (extracted)
├── snapshot_manager.py         # 12A-FR-011: NEW (extracted)
├── compaction_manager.py       # 12A-FR-011: NEW (extracted)

plugins/floe-orchestrator-dagster/
├── tests/integration/test_iceberg_io_manager.py  # 12A-FR-013: Remove skips
├── pyproject.toml              # 12A-FR-018: Remove unused deps

testing/base_classes/
├── plugin_metadata_tests.py    # 12A-FR-016: NEW
├── plugin_lifecycle_tests.py   # 12A-FR-016: NEW
├── plugin_discovery_tests.py   # 12A-FR-016: NEW
```

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Blocked By | None | Independent maintenance work |
| Blocks | None | Improves existing code |
| Related | All | Touches core infrastructure |

**Note**: This Epic is maintenance-focused and can proceed independently. Changes are backward-compatible.

---

## User Stories (for SpecKit)

### US1: Break Circular Dependency (P0)
**As a** platform maintainer
**I want** floe_core to use plugin registry instead of direct imports
**So that** packages can be versioned and tested independently

**Acceptance Criteria**:
- [ ] `rbac/generator.py` uses `RBACPlugin` ABC only (no K8sRBACPlugin import)
- [ ] `cli/rbac/generate.py` gets plugin via registry lookup
- [ ] No import cycle detected by `python -c "import floe_core; import floe_rbac_k8s"`
- [ ] All existing tests pass
- [ ] mypy --strict passes

### US2: Fix N+1 Performance Issues (P0)
**As a** platform user
**I want** OCI operations to complete quickly
**So that** listing and pulling artifacts doesn't timeout

**Acceptance Criteria**:
- [ ] `client.list()` uses parallel fetching (ThreadPoolExecutor, max_workers=10)
- [ ] `client.pull()` uses dict lookup instead of loop search
- [ ] Benchmark shows >5x improvement for list() with 100 tags
- [ ] No functional regression in tests

### US3: Reduce Code Complexity (P1)
**As a** platform maintainer
**I want** complex functions refactored
**So that** code is testable and maintainable

**Acceptance Criteria**:
- [ ] `diff_command()` CC reduced from 30 to ≤10
- [ ] `pull()` CC reduced from 27 to ≤12
- [ ] `_generate_impl()` uses Strategy pattern
- [ ] All refactored functions have 100% test coverage
- [ ] No behavior changes (golden test validation)

### US4: Split IcebergTableManager (P1)
**As a** platform maintainer
**I want** IcebergTableManager split into focused classes
**So that** each class has single responsibility and is testable

**Acceptance Criteria**:
- [ ] IcebergTableManager becomes a facade (≤5 methods)
- [ ] IcebergTableLifecycle handles create/drop/exists
- [ ] IcebergSchemaManager handles schema evolution
- [ ] IcebergSnapshotManager handles snapshots
- [ ] IcebergCompactionManager handles compaction
- [ ] Each extracted class has dedicated test file
- [ ] Public API unchanged (facade delegates)

### US5: Fix Test Policy Violations (P1)
**As a** platform maintainer
**I want** tests to fail rather than skip
**So that** CI accurately reports infrastructure issues

**Acceptance Criteria**:
- [ ] All `pytest.skip()` calls removed from `test_iceberg_io_manager.py`
- [ ] Tests use `IntegrationTestBase.check_infrastructure()` pattern
- [ ] Stub tests (`pass`) implemented with actual assertions
- [ ] Tests fail with clear message when infrastructure unavailable

### US6: Add Missing Test Coverage (P1)
**As a** platform maintainer
**I want** OCI error and metrics modules tested
**So that** we have confidence in error handling

**Acceptance Criteria**:
- [ ] `tests/unit/oci/test_errors.py` covers exception hierarchy
- [ ] `tests/unit/oci/test_metrics.py` covers metric emission
- [ ] Coverage for oci/ module >80%
- [ ] Requirement markers on all new tests

### US7: Reduce Test Duplication (P2)
**As a** platform maintainer
**I want** shared base test classes for plugins
**So that** plugin tests are consistent and maintainable

**Acceptance Criteria**:
- [ ] `BasePluginMetadataTests` in `testing/base_classes/`
- [ ] `BasePluginLifecycleTests` in `testing/base_classes/`
- [ ] `BasePluginDiscoveryTests` in `testing/base_classes/`
- [ ] At least 3 plugin test files migrated to use base classes
- [ ] Test count reduced by >50% for migrated plugins

### US8: Clean Up Dependencies (P3)
**As a** platform maintainer
**I want** unused dependencies removed
**So that** install size and security surface is minimized

**Acceptance Criteria**:
- [ ] `croniter` removed from floe-orchestrator-dagster
- [ ] `pytz` removed from floe-orchestrator-dagster
- [ ] Tests still pass after removal
- [ ] No import errors

---

## Technical Notes

### Key Decisions
- Circular dependency fix via dependency injection (not package extraction yet)
- Performance fixes use ThreadPoolExecutor (not asyncio) for compatibility
- IcebergTableManager refactoring uses Facade pattern (backward compatible)
- Test base classes use pytest fixtures (not inheritance-heavy approach)

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Regression in refactored code | MEDIUM | HIGH | Golden tests, comprehensive test coverage |
| Performance fix complexity | LOW | MEDIUM | Benchmark before/after, gradual rollout |
| Test migration breaks CI | LOW | HIGH | Migrate one plugin at a time |

### Test Strategy
- **Unit**: All refactored functions have unit tests
- **Contract**: Existing contract tests validate no API changes
- **Integration**: Existing integration tests validate behavior
- **Benchmark**: Performance tests for N+1 fixes

---

## Success Criteria

### Debt Score Improvement
- **Target**: 68 → 80 (+12 points)
- **Critical Issues**: 5 → 0
- **High Issues**: 12 → 3

### Metrics
- Max cyclomatic complexity: 30 → 15
- Max class methods: 30 → 15
- Test skip count: 4 → 0
- OCI list() latency (100 tags): 30s → 3s

---

## SpecKit Context

### Relevant Codebase Paths
- `packages/floe-core/src/floe_core/` - Primary refactoring target
- `packages/floe-iceberg/src/floe_iceberg/` - Manager split
- `plugins/floe-orchestrator-dagster/tests/` - Test fixes
- `testing/base_classes/` - New test infrastructure

### Related Existing Code
- `.claude/reviews/tech-debt-*.json` - Audit history
- `.claude/skills/tech-debt-review/` - Review tooling
- `testing/base_classes/integration_test_base.py` - Pattern to follow

### External Dependencies
- None (internal maintenance work)
