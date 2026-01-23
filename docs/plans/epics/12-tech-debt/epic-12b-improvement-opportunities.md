# Epic 12B: Improvement Opportunities Backlog

> **Audience**: floe platform contributors and maintainers
>
> **Purpose**: Document ALL improvement opportunities identified in the 2026-01-22 comprehensive tech debt audit

## Summary

This Epic captures the complete backlog of improvement opportunities identified during the January 2026 full codebase audit. Unlike Epic 12A (which addressed immediate critical issues), Epic 12B is a **longer-term roadmap** for continuous improvement across architecture, testing, dependencies, and code quality.

**Scope**: 37 issues across 9 categories
**Debt Score at Audit**: 74/100 (Good)
**Target Debt Score**: 90/100 (Excellent)

## Status

- [x] Specification created
- [ ] Tasks generated
- [ ] Linear issues created
- [ ] Implementation started
- [ ] Tests passing
- [ ] Complete

**Linear Project**: [Epic 12B: Improvement Opportunities](https://linear.app/obsidianowl/project/epic-12b-improvement-opportunities-0246800533dd)

**Audit Reference**: `.claude/reviews/tech-debt-20260122-154004.json`

---

## Requirements Overview

| Category | Issues | Critical | High | Medium | Low |
|----------|--------|----------|------|--------|-----|
| Architecture | 7 | 1 | 3 | 3 | 0 |
| Complexity | 8 | 1 | 7 | 0 | 0 |
| Testing | 7 | 3 | 4 | 0 | 0 |
| Dependencies | 4 | 0 | 2 | 2 | 0 |
| Performance | 2 | 0 | 2 | 0 | 0 |
| Hotspots | 3 | 0 | 0 | 3 | 0 |
| TODOs | 3 | 0 | 1 | 2 | 0 |
| Documentation | 2 | 0 | 0 | 2 | 0 |
| Dead Code | 1 | 0 | 0 | 0 | 1 |
| **Total** | **37** | **5** | **19** | **12** | **1** |

---

## Detailed Requirements

### Architecture (7 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-ARCH-001 | Break circular dependency: schemas ↔ telemetry ↔ plugins | CRITICAL | Low | schemas/compiled_artifacts.py:26 |
| 12B-ARCH-002 | Reduce floe-core/\_\_init\_\_.py exports from 76 to ~15 | HIGH | Medium | floe-core/\_\_init\_\_.py:197-291 |
| 12B-ARCH-003 | Split plugin_registry.py (1230 lines) into focused classes | HIGH | High | floe-core/plugin_registry.py |
| 12B-ARCH-004 | Split oci/client.py (1389 lines) into focused classes | HIGH | High | floe-core/oci/client.py |
| 12B-ARCH-005 | Reduce re-exports in submodule \_\_init\_\_.py files | MEDIUM | Medium | Various \_\_init\_\_.py files |
| 12B-ARCH-006 | Address low cohesion in floe-core (11 responsibility areas) | MEDIUM | Very High | packages/floe-core/ |
| 12B-ARCH-007 | Reduce shotgun surgery risk for plugin_metadata (19 importers) | MEDIUM | Medium | floe-core/plugin_metadata.py |

**Architecture Details:**

#### 12B-ARCH-001: Break Circular Dependency (CRITICAL)
**Current Cycle**: `schemas → telemetry → plugins → schemas`
- `schemas/compiled_artifacts.py:26` imports `TelemetryConfig` from `telemetry.config`
- `telemetry/provider.py:35` imports `TelemetryBackendPlugin` from `plugins.telemetry`
- `plugins/__init__.py` re-exports from `schemas`

**Recommended Fix**: Move `TelemetryConfig` to `schemas/telemetry.py`

#### 12B-ARCH-002: God Module - 76 Exports (HIGH)
**Current State**: `floe-core/__init__.py` exports 76 symbols
**Impact**: High cognitive load, import pollution, difficult API discovery

**Recommended Fix**:
```python
# Keep ONLY essentials (~15 exports):
from floe_core.schemas import FloeSpec, CompiledArtifacts
from floe_core.compilation import compile_pipeline
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.errors import PluginError, CompilationError
```

#### 12B-ARCH-003: Split plugin_registry.py (HIGH)
**Current State**: 1230 lines, 20 methods, too many responsibilities

**Recommended Split**:
- `plugin_discovery.py` (~200 lines) - Entry point discovery
- `plugin_loader.py` (~200 lines) - Plugin instantiation
- `plugin_lifecycle.py` (~250 lines) - Activation, shutdown, health
- `plugin_dependencies.py` (~200 lines) - Dependency resolution
- `plugin_registry.py` (~300 lines) - Facade orchestrating above

#### 12B-ARCH-004: Split oci/client.py (HIGH)
**Current State**: 1389 lines, 27 methods

**Recommended Split**:
- `oci/manifest_fetcher.py` - Manifest operations
- `oci/layer_downloader.py` - Layer operations
- `oci/client.py` - Facade composing above + existing auth.py, cache.py

---

### Complexity (8 issues)

| Requirement ID | Description | Priority | Effort | File:Line |
|----------------|-------------|----------|--------|-----------|
| 12B-CX-001 | Refactor map_pyiceberg_error() CC 26→10 | CRITICAL | Low | floe-catalog-polaris/errors.py:51 |
| 12B-CX-002 | Refactor \_\_getattr\_\_() CC 18→10 | HIGH | Low | floe-core/plugin_registry.py |
| 12B-CX-003 | Refactor audit_command() CC 18→10 | HIGH | Medium | floe-core/cli/rbac/audit.py |
| 12B-CX-004 | Refactor validate_security_policy_not_weakened() CC 17→10 | HIGH | Medium | floe-core/enforcement/ |
| 12B-CX-005 | Refactor enforce() CC 17→10 | HIGH | Medium | floe-core/enforcement/policy_enforcer.py |
| 12B-CX-006 | Refactor validate() (token) CC 17→10 | HIGH | Medium | floe-identity-keycloak/ |
| 12B-CX-007 | Refactor list_secrets() CC 16→10 | HIGH | Medium | floe-secrets-infisical/ |
| 12B-CX-008 | Refactor pull() (OCI) CC 15→10 | HIGH | Medium | floe-core/oci/client.py |

**Complexity Details:**

#### 12B-CX-001: map_pyiceberg_error() (CRITICAL)
**Current**: 16 consecutive if-statements for exception mapping
**Recommended**: Use error mapping dictionary (Strategy Pattern)

```python
# BEFORE: 16 if-statements
if isinstance(error, ServiceUnavailableError): ...
if isinstance(error, UnauthorizedError): ...

# AFTER: Dispatch table
ERROR_HANDLERS = {
    ServiceUnavailableError: _handle_unavailable,
    UnauthorizedError: _handle_unauthorized,
}
handler = ERROR_HANDLERS.get(type(error), _handle_unknown)
return handler(error)
```

---

### Testing (7 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-TEST-001 | Remove 3 skipped tests (policy violation) | CRITICAL | Low | floe-iceberg/tests/unit/test_lifecycle.py:408,428,440 |
| 12B-TEST-002 | Add tests for CLI RBAC commands (40% → 80% coverage) | HIGH | High | cli/rbac/*.py |
| 12B-TEST-003 | Add tests for Plugin ABCs (30% → 90% coverage) | HIGH | High | plugins/identity.py, orchestrator.py, storage.py |
| 12B-TEST-004 | Add tests for CLI platform commands | HIGH | High | cli/platform/deploy.py, publish.py, status.py |
| 12B-TEST-005 | Add requirement markers to 315 tests (92.4% → 100%) | HIGH | Medium | Various test files |
| 12B-TEST-006 | Reduce test duplication ratio (31.6% → 15%) | MEDIUM | Medium | Audit tests, discovery tests |
| 12B-TEST-007 | Migrate Keycloak/Infisical discovery tests to BasePluginDiscoveryTests | MEDIUM | Low | floe-identity-keycloak/, floe-secrets-infisical/ |

**Testing Details:**

#### 12B-TEST-001: Remove Skipped Tests (CRITICAL - POLICY VIOLATION)
**Location**: `floe-iceberg/tests/unit/test_lifecycle.py`
- Line 408: `test_drop_table_removes_existing_table`
- Line 428: `test_drop_table_raises_for_nonexistent_table`
- Line 440: `test_drop_table_with_purge_removes_data`

**Policy**: Constitution V states "Tests MUST FAIL, never skip"
**Action**: Either implement `drop_table()` or delete tests

#### 12B-TEST-006: Test Duplication (31.6%)
**Major Duplication Areas**:
- Audit event tests (3 files, ~350 lines overlap)
- Dry-run mode tests (2 files, ~300 lines overlap)
- Plugin discovery tests (Keycloak/Infisical not using BasePluginDiscoveryTests)
- Health check tests (2 files, ~500 lines similar)

**Recommended Actions**:
- Extract audit event fixtures to conftest.py
- Parametrize dry-run tests (unit vs integration layer)
- Create BaseHealthCheckTests
- Create BaseConfigValidationTests

---

### Dependencies (4 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-DEP-001 | Pin pydantic with upper bound (>=2.12.5,<3.0) | HIGH | Low | All pyproject.toml |
| 12B-DEP-002 | Pin kubernetes with upper bound (>=35.0.0,<36.0) | HIGH | Low | floe-core, K8s secrets plugin, K8s RBAC plugin |
| 12B-DEP-003 | Update opentelemetry-api (1.30.0 → 1.39.1) | MEDIUM | Low | floe-core, floe-iceberg, floe-catalog-polaris |
| 12B-DEP-004 | Investigate/deprecate floe-cli package (empty src/) | MEDIUM | Low | packages/floe-cli/ |

**Unpinned Dependencies (Risk Matrix)**:
| Package | Current | Risk | Recommendation |
|---------|---------|------|----------------|
| pydantic | >=2.0 | HIGH | >=2.12.5,<3.0 |
| kubernetes | >=28.0.0 | HIGH | >=35.0.0,<36.0 |
| opentelemetry-api | >=1.20.0 | HIGH | >=1.39.0,<2.0 |
| pyiceberg | >=0.9.0 | HIGH | >=0.10.0,<0.11.0 |
| pyarrow | >=14.0 | HIGH | >=22.0.0,<23.0 |
| structlog | >=24.0 | MEDIUM | >=25.0,<26.0 |
| click | >=8.1.0 | MEDIUM | >=8.3.0,<9.0 |
| httpx | >=0.25.0 | MEDIUM | >=0.28.0,<1.0 |

---

### Performance (2 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-PERF-001 | Add resource count validation to RBAC diff | HIGH | Low | floe-core/rbac/diff.py:204 |
| 12B-PERF-002 | Optimize string concatenation in recursive path building | HIGH | Medium | floe-core/rbac/diff.py:68-113 |

**Note**: Codebase demonstrates excellent performance patterns overall (94/100 score):
- Batch fetcher prevents N+1 queries
- LRU cache with TTL implemented
- Circuit breaker + retry + timeouts
- Lazy loading with caching
- Early exit optimization

---

### Git Hotspots (3 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-HOT-001 | Knowledge transfer for bus factor = 1 files | MEDIUM | Low | pyproject.toml, schemas/\_\_init\_\_.py |
| 12B-HOT-002 | Monitor schema system coupling | MEDIUM | Low | pyproject.toml ↔ schemas/\_\_init\_\_.py |
| 12B-HOT-003 | Post-Epic-12A regression monitoring | MEDIUM | Low | Recently changed files |

**Bus Factor Risk Files** (single contributor):
- `packages/floe-core/pyproject.toml`
- `packages/floe-core/src/floe_core/schemas/__init__.py`
- Various core `__init__.py` files

**Mitigation**: Schedule knowledge transfer sessions

---

### TODOs (3 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-TODO-001 | Evaluate SORT compaction implementation | HIGH | Medium | floe-iceberg/compaction.py:383 |
| 12B-TODO-002 | Complete ORAS connectivity (Epic 8A) | MEDIUM | High | floe-core/oci/client.py:1257 |
| 12B-TODO-003 | Replace PyIceberg issue "XXX" with real number | MEDIUM | Low | floe-iceberg/manager.py:61 |

**Note**: All TODOs are < 5 days old - no ancient technical debt

---

### Documentation (2 issues)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-DOC-001 | Complete GitHub issue reference placeholder | MEDIUM | Low | floe-iceberg/manager.py:61 |
| 12B-DOC-002 | Add date/issue link to SORT TODO | MEDIUM | Low | floe-iceberg/compaction.py:383 |

**Note**: Documentation is excellent overall (99.7% coverage)

---

### Dead Code (1 issue)

| Requirement ID | Description | Priority | Effort | File Location |
|----------------|-------------|----------|--------|---------------|
| 12B-DEAD-001 | Review intentional `if False:` block | LOW | Low | floe-core/rbac/audit.py:525 |

**Note**: This is an INTENTIONAL pattern to avoid runtime import overhead. No action required.

---

## User Stories

### US1: Architecture Cleanup (P0-P1)

**As a** platform maintainer
**I want** architecture issues resolved
**So that** the codebase is modular and testable

**Acceptance Criteria**:
- [ ] Circular dependency broken (schemas ↔ telemetry ↔ plugins)
- [ ] floe-core exports reduced to ~15 essential symbols
- [ ] plugin_registry.py split into 4 focused classes
- [ ] oci/client.py split into 3 focused classes
- [ ] All tests pass, mypy --strict passes

### US2: Complexity Reduction (P0-P1)

**As a** platform maintainer
**I want** high-complexity functions refactored
**So that** code is maintainable and testable

**Acceptance Criteria**:
- [ ] map_pyiceberg_error() CC reduced from 26 to ≤10
- [ ] All 8 high-complexity functions below CC 15
- [ ] Strategy/dispatch patterns applied where appropriate
- [ ] 100% test coverage on refactored functions

### US3: Testing Compliance (P0-P1)

**As a** platform maintainer
**I want** testing policy violations fixed
**So that** CI accurately reports test status

**Acceptance Criteria**:
- [ ] 0 skipped tests (currently 3)
- [ ] CLI RBAC test coverage ≥80%
- [ ] Plugin ABC test coverage ≥80%
- [ ] 100% tests have requirement markers
- [ ] Test duplication ratio ≤15%

### US4: Dependency Hygiene (P1)

**As a** platform maintainer
**I want** dependencies properly pinned
**So that** builds are reproducible and secure

**Acceptance Criteria**:
- [ ] All critical dependencies have upper bounds
- [ ] No dependencies more than 1 major version behind
- [ ] pip-audit shows 0 vulnerabilities
- [ ] Unused dependencies removed

### US5: Performance Hardening (P1)

**As a** platform user
**I want** edge cases handled gracefully
**So that** the system doesn't fail under load

**Acceptance Criteria**:
- [ ] RBAC diff validates resource count limits
- [ ] Error messages explain limits
- [ ] Performance tests validate limits

### US6: Knowledge Transfer (P2)

**As a** team lead
**I want** bus factor risks addressed
**So that** the team can maintain all code

**Acceptance Criteria**:
- [ ] Knowledge transfer sessions scheduled for critical files
- [ ] Documentation improved for complex modules
- [ ] Second contributor assigned to high-risk files

---

## Implementation Phases

### Phase 1: Critical Issues (Sprint 1-2)
- 12B-ARCH-001: Break circular dependency
- 12B-TEST-001: Remove skipped tests
- 12B-CX-001: Refactor map_pyiceberg_error()
- 12B-DEP-001/002: Pin critical dependencies

### Phase 2: High Priority (Sprint 3-4)
- 12B-ARCH-002: Reduce \_\_init\_\_.py exports
- 12B-TEST-002/003/004: Increase test coverage
- 12B-CX-002-008: Reduce complexity across codebase
- 12B-TEST-005: Add requirement markers

### Phase 3: Medium Priority (Sprint 5-6)
- 12B-ARCH-003/004: Split god modules
- 12B-TEST-006/007: Reduce test duplication
- 12B-DEP-003/004: Update dependencies
- 12B-PERF-001/002: Performance hardening

### Phase 4: Low Priority (Ongoing)
- 12B-ARCH-005/006/007: Architecture refinement
- 12B-HOT-001/002/003: Knowledge transfer
- 12B-TODO-001/002/003: TODO cleanup
- 12B-DOC-001/002: Documentation polish

---

## Success Criteria

### Debt Score Improvement
- **Current**: 74/100 (Good)
- **Phase 1 Target**: 80/100 (Good)
- **Phase 2 Target**: 85/100 (Good)
- **Final Target**: 90/100 (Excellent)

### Key Metrics
| Metric | Current | Target |
|--------|---------|--------|
| Critical issues | 5 | 0 |
| High issues | 19 | 0 |
| Max cyclomatic complexity | 26 | 15 |
| Test skip count | 3 | 0 |
| Test duplication ratio | 31.6% | 15% |
| Requirement marker coverage | 92.4% | 100% |
| CLI test coverage | 40% | 80% |
| Unpinned dependencies | 11 | 0 |

---

## Dependencies

| Type | Epic | Reason |
|------|------|--------|
| Continues | Epic 12A | Extends tech debt reduction work |
| Blocked By | None | Independent maintenance work |
| Blocks | None | Improves existing code |
| Related | All | Touches core infrastructure |

---

## References

- **Audit Report**: `.claude/reviews/tech-debt-20260122-154004.json`
- **Previous Audit**: `.claude/reviews/tech-debt-20260122-110030.json`
- **Tech Debt Skill**: `.claude/skills/tech-debt-review/`
- **Testing Standards**: `.claude/rules/testing-standards.md`
- **Architecture Docs**: `docs/architecture/`
