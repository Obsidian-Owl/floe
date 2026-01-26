# Analysis Report: Epic 7C - Network and Pod Security

**Generated**: 2026-01-26
**Artifacts Analyzed**: spec.md, plan.md, tasks.md, data-model.md, contracts/, quickstart.md

## Executive Summary

The Epic 7C specification is **well-structured** with comprehensive requirements coverage. However, **critical integration inconsistencies** have been identified between the planning documents and the actual codebase structure that MUST be resolved before implementation to prevent orphaned code and tests.

### Critical Issues Found: 3
### Warnings: 2
### Recommendations: 5

---

## Integration Analysis (User-Requested Focus)

### 🚨 CRITICAL: CLI Path Discrepancy

**Issue**: tasks.md and plan.md reference a non-existent `floe-cli` package structure:

| Document Reference | Actual Codebase Structure |
|-------------------|--------------------------|
| `packages/floe-cli/src/floe_cli/commands/network/` | ❌ Does NOT exist |
| CLI commands expected in separate package | CLI is in `packages/floe-core/src/floe_core/cli/` |

**Evidence**:
- Glob search for `packages/floe-cli/**/*.py` returned: **No files found**
- Actual CLI location: `packages/floe-core/src/floe_core/cli/`
- RBAC commands pattern: `packages/floe-core/src/floe_core/cli/rbac/`

**Impact if Unresolved**:
- Tasks T003, T065-T078 reference wrong paths
- Code would be created in non-existent package
- Tests would not be discoverable
- CLI commands would never be wired into main CLI

**Required Fix**:
1. Update tasks.md: Change all `packages/floe-cli/src/floe_cli/commands/network/` references to `packages/floe-core/src/floe_core/cli/network/`
2. Update plan.md: Correct the "CLI commands (floe-cli)" section
3. Follow existing pattern in `packages/floe-core/src/floe_core/cli/rbac/__init__.py`

---

### 🚨 CRITICAL: SecurityConfig Path Inconsistency

**Issue**: plan.md states SecurityConfig location incorrectly:

| Document Reference | Actual Codebase Structure |
|-------------------|--------------------------|
| `packages/floe-core/src/floe_core/security.py` | ❌ Does NOT exist |
| - | ✅ `packages/floe-core/src/floe_core/schemas/security.py` |

**Evidence**:
- Grep for SecurityConfig found it at: `packages/floe-core/src/floe_core/schemas/security.py`
- No file exists at `packages/floe-core/src/floe_core/security.py`

**Impact if Unresolved**:
- Task T013 references wrong path
- Extension would create duplicate file
- Imports would fail

**Required Fix**:
1. Update tasks.md T013: Change path to `packages/floe-core/src/floe_core/schemas/security.py`
2. Update plan.md Project Structure section

---

### 🚨 CRITICAL: Plugin Exports Not Updated

**Issue**: NetworkSecurityPlugin ABC needs to be exported from `packages/floe-core/src/floe_core/plugins/__init__.py`

**Current State**:
- 12 plugin types exported: CatalogPlugin, ComputePlugin, DBTPlugin, IdentityPlugin, IngestionPlugin, OrchestratorPlugin, ProfileGenerator, RBACPlugin, SecretsPlugin, SemanticLayerPlugin, StoragePlugin, TelemetryBackendPlugin
- NetworkSecurityPlugin: ❌ **NOT in exports**

**Tasks Must Address**:
- T014 creates the ABC but no explicit task to add export to `__init__.py`
- T019 exports from `network/__init__.py` but not from `plugins/__init__.py`

**Required Fix**:
Add task or update T014 to include:
```python
# In packages/floe-core/src/floe_core/plugins/__init__.py
from floe_core.plugins.network_security import NetworkSecurityPlugin
__all__.append("NetworkSecurityPlugin")
```

---

## Warning: Entry Point Group Registration

**Issue**: Entry point `floe.network_security` must be registered in main floe-core pyproject.toml for discovery.

**Pattern from RBAC**:
```toml
# plugins/floe-rbac-k8s/pyproject.toml
[project.entry-points."floe.rbac"]
k8s = "floe_rbac_k8s:K8sRBACPlugin"
```

**Tasks T004 correctly addresses this**, but verify the entry point group name matches what the plugin discovery system expects.

---

## Warning: CLI Main Registration

**Issue**: New `network` command group must be registered in CLI main.py

**Pattern to follow** (from `packages/floe-core/src/floe_core/cli/main.py`):
```python
from floe_core.cli.network import network
# ...
cli.add_command(network)
```

**Task T078 addresses this**, but ensure it's not skipped during implementation.

---

## Integration Wiring Checklist

Before marking Epic 7C complete, verify ALL of these integration points:

| Integration Point | Location | Task |
|------------------|----------|------|
| NetworkSecurityPlugin ABC export | `floe_core/plugins/__init__.py` | Add to T014 |
| NetworkPoliciesConfig in SecurityConfig | `floe_core/schemas/security.py` | T013 (fix path) |
| Network schemas module export | `floe_core/network/__init__.py` | T019 |
| CLI network command group | `floe_core/cli/network/__init__.py` | T003 (fix path) |
| CLI main.py registration | `floe_core/cli/main.py` | T078 |
| Plugin entry point | `floe-network-security-k8s/pyproject.toml` | T004 |
| Contract tests at root level | `tests/contract/test_network_*.py` | T005, T006, T007, T048 |

---

## Duplicate Detection

**No significant duplication detected** between artifacts.

| Check | Result |
|-------|--------|
| Requirement ID duplicates | ✅ None found |
| User story overlap | ✅ Clean separation |
| Task description duplicates | ✅ Distinct tasks |

---

## Ambiguity Analysis

### Minor Ambiguity: US8 Test Paths

**Issue**: US8 test paths reference `packages/floe-cli/tests/unit/` which doesn't exist.

**Tasks affected**: T065, T066, T067, T068

**Fix**: Change to `packages/floe-core/tests/unit/cli/` following existing pattern:
```
packages/floe-core/tests/unit/cli/test_rbac_diff.py  # existing
packages/floe-core/tests/unit/cli/test_network_*.py  # new (correct path)
```

---

## Underspecification Analysis

| Area | Status | Notes |
|------|--------|-------|
| FR coverage in tasks | ✅ Complete | All 45 FRs mapped to tasks |
| Test coverage per US | ✅ Complete | Each US has unit + integration tests |
| Contract tests | ✅ Complete | T005-T007, T048 cover schemas and ABC |
| Error handling | ⚠️ Limited | No explicit error path tests |

### Recommendation: Add Error Path Tests

Consider adding tests for:
- Invalid CNI (no NetworkPolicy support)
- Malformed egress rules
- Missing required namespaces

---

## Constitution Alignment

| Principle | Compliance | Evidence |
|-----------|------------|----------|
| I. Technology Ownership | ✅ | No SQL, orchestration in plugin |
| II. Plugin-First | ✅ | NetworkSecurityPlugin ABC + entry point |
| III. Enforced vs Pluggable | ✅ | K8s-native enforced, policy content pluggable |
| IV. Contract-Driven | ✅ | SecurityConfig extension via Pydantic |
| V. K8s-Native Testing | ✅ | Integration tests in Kind cluster |
| VI. Security First | ✅ | No secrets in config, validation via Pydantic |
| VII. Four-Layer | ✅ | Config flows downward only |
| VIII. Observability | ⚠️ | No explicit OTel tracing for generator |

### Recommendation: Add OTel Instrumentation

Consider adding:
```python
# In NetworkPolicyManifestGenerator
@tracer.start_as_current_span("generate_network_policies")
def generate(self, config: SecurityConfig) -> ...:
```

---

## Coverage Gap Analysis

### Requirements → Tasks Mapping

| Requirement Group | Tasks | Coverage |
|------------------|-------|----------|
| FR-001 to FR-004 (Config) | T005-T019 | ✅ 100% |
| FR-010 to FR-012 (Jobs) | T020-T026 | ✅ 100% |
| FR-020 to FR-023 (Platform) | T027-T034 | ✅ 100% |
| FR-030 to FR-033 (Egress) | T023-T026 | ✅ 100% |
| FR-040 to FR-043 (Domain) | T079-T085 | ✅ 100% |
| FR-050 to FR-054 (PSS) | T035-T041 | ✅ 100% |
| FR-060 to FR-064 (Container) | T042-T047 | ✅ 100% |
| FR-070 to FR-073 (Generator) | T048-T055 | ✅ 100% |
| FR-080 to FR-084 (Audit) | T065-T077 | ✅ 100% |
| FR-091 to FR-093 (CNI) | T068, T076-T077 | ✅ 100% |

### Test Coverage by User Story

| User Story | Unit Tests | Integration Tests | Contract Tests |
|------------|------------|-------------------|----------------|
| US1 (Jobs) | T020, T021 | T022 | T005-T007 |
| US2 (Platform) | T027, T028 | T029 | T005-T007 |
| US3 (PSS) | T035 | T036 | T005-T007 |
| US4 (Container) | T042, T043 | - | T005-T007 |
| US5 (Generator) | T049 | - | T048 |
| US6 (DNS) | T056 | T057 | - |
| US7 (OTel) | T061 | T062 | - |
| US8 (CLI) | T065-T068 | - | - |
| US9 (Domain) | T079 | T080 | - |

---

## Inconsistency Detection

### Cross-Document Inconsistencies

| Inconsistency | Documents | Severity |
|---------------|-----------|----------|
| CLI package path | plan.md, tasks.md vs codebase | 🚨 CRITICAL |
| SecurityConfig path | plan.md, tasks.md vs codebase | 🚨 CRITICAL |
| Test path for US8 | tasks.md vs test structure | ⚠️ WARNING |

### Internal Consistency: ✅ PASS

- spec.md requirements match plan.md references
- data-model.md schemas match contracts/
- quickstart.md examples match spec.md config

---

## Recommendations

### 1. Fix Critical Path Issues (BLOCKING)

**Before implementation begins**, update these files:

```markdown
# tasks.md changes needed:

T003: Change `packages/floe-cli/src/floe_cli/commands/network/`
   to `packages/floe-core/src/floe_core/cli/network/`

T013: Change `packages/floe-core/src/floe_core/security.py`
   to `packages/floe-core/src/floe_core/schemas/security.py`

T065-T078: Change all `packages/floe-cli/` paths
   to `packages/floe-core/src/floe_core/cli/`
```

### 2. Add Plugin Export Task

Add sub-task to T014 or create T014a:
```
T014a: Export NetworkSecurityPlugin from packages/floe-core/src/floe_core/plugins/__init__.py
```

### 3. Add Cleanup Verification Task

Add to Phase 12:
```
T086a: Verify no orphaned code - run `floe network` command succeeds
T086b: Verify no orphaned tests - all tests discoverable via pytest
```

### 4. Add Integration Wiring Verification

Add to each phase checkpoint:
```
After Phase 2: Verify `from floe_core.network import *` works
After Phase 7: Verify `from floe_core.plugins import NetworkSecurityPlugin` works
After Phase 10: Verify `floe network --help` shows all commands
```

### 5. Consider Tech Debt Tracking

Create follow-up issue for:
- Consolidate `floe security` umbrella command (mentioned in plan.md cleanup)
- OTel instrumentation for generator

---

## Summary

| Category | Status |
|----------|--------|
| Requirements Coverage | ✅ 100% (45/45 FRs mapped) |
| Test Coverage | ✅ Comprehensive |
| Constitution Compliance | ✅ 7/8 principles (minor OTel gap) |
| Integration Wiring | 🚨 **3 CRITICAL issues** |
| Document Consistency | ⚠️ Path inconsistencies |

**Verdict**: Epic 7C is well-specified but **requires path corrections in tasks.md and plan.md before implementation** to prevent orphaned code and ensure proper integration with the existing codebase.

---

## Appendix: Files Analyzed

### Core Artifacts
- `specs/7c-network-pod-security/spec.md` - 9 user stories, 45 FRs
- `specs/7c-network-pod-security/plan.md` - Technical implementation plan
- `specs/7c-network-pod-security/tasks.md` - 90 tasks across 12 phases
- `specs/7c-network-pod-security/data-model.md` - Entity definitions
- `specs/7c-network-pod-security/contracts/` - Interface contracts
- `specs/7c-network-pod-security/quickstart.md` - Developer guide

### Codebase Integration Points Verified
- `packages/floe-core/src/floe_core/schemas/security.py` - SecurityConfig
- `packages/floe-core/src/floe_core/plugins/__init__.py` - Plugin exports
- `packages/floe-core/src/floe_core/plugins/rbac.py` - Pattern reference
- `packages/floe-core/src/floe_core/cli/main.py` - CLI entry point
- `packages/floe-core/src/floe_core/cli/rbac/` - Pattern reference
- `plugins/floe-rbac-k8s/pyproject.toml` - Entry point pattern
- `tests/contract/` - Contract test location
