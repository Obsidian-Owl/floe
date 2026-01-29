# Agent/Skill Optimization Plan v2

**Date**: 2026-01-30
**Goal**: Simplify without redesigning. Maintain SpecKit workflow. Reduce token overhead.

---

## Current State

| Category | Count | Lines | Issue |
|----------|-------|-------|-------|
| Skills | 27 | ~7,470 | 5 unused, heavy redundancy |
| Agents | 25 | ~5,000 | 13 overlap with OMC |
| Chains | 6 | ~70 | Good |
| Hooks | 5 | ~80 | Good |

**Critical Path**: Linear → Beads → SpecKit → Implementation → PR

---

## P0: Remove Unused Tech Skills (HIGH IMPACT)

Skills rarely/never invoked in sessions:

| Skill | Lines | Action |
|-------|-------|--------|
| `cube-skill` | 502 | Move to `docs/reference/` |
| `duckdb-lakehouse` | 380 | Move to `docs/reference/` |
| `pyiceberg-skill` | 414 | Move to `docs/reference/` |
| `polaris-skill` | 255 | Move to `docs/reference/` |
| `arch-review` | 182 | Merge into `tech-debt-review --arch` |

**Savings**: ~1,733 lines from active skill system

---

## P1: Consolidate Test Agents (HIGH IMPACT)

`speckit-test-review` spawns 4 agents that duplicate OMC:

| Remove | Keep | Rationale |
|--------|------|-----------|
| `test-reviewer` | Use OMC `code-reviewer` | Generic quality |
| `architecture-compliance` | Use OMC `code-reviewer` | Generic patterns |
| - | `plugin-quality` | Floe-specific |
| - | `contract-stability` | Floe-specific |

**Savings**: 2 agents (~400 lines)

---

## P2: Consolidate Test Debt Agents (MEDIUM IMPACT)

6 specialized agents → 1 unified:

```
DELETE: test-flakiness-predictor
DELETE: test-isolation-checker
DELETE: test-edge-case-analyzer
DELETE: test-duplication-detector
DELETE: testing-debt-analyzer
KEEP:   test-requirement-mapper (traceability)
KEEP:   test-design-reviewer (pre-implementation)
```

**Savings**: 5 agents (~300 lines)

---

## P3: Consolidate Code Quality Agents (MEDIUM IMPACT)

8 overlapping → 3 focused:

```
DELETE: code-pattern-reviewer-low (use OMC haiku)
DELETE: code-complexity-analyzer
DELETE: dependency-debt-analyzer
DELETE: docstring-validator
DELETE: documentation-debt-analyzer
DELETE: git-hotspot-analyzer
DELETE: todo-archaeology
KEEP:   code-pattern-reviewer (comprehensive)
KEEP:   dead-code-detector (distinct)
KEEP:   security-scanner (distinct)
```

**Savings**: 7 agents (~500 lines)

---

## P4: Update Skill Chains

```json
{
  "chains": {
    "epic-planning": ["specify", "clarify", "plan", "tasks", "taskstolinear"],
    "pre-pr": ["test-review", "wiring-check", "merge-check"],
    "dbt-work": ["dbt-skill", "pydantic-skill"],
    "plugin-dev": ["pydantic-skill", "dagster-skill", "testing-skill"],
    "k8s-deploy": ["helm-k8s-skill"]
  }
}
```

Remove: `iceberg-work` chain (skills moved to docs)

---

## P5: OMC Integration Patterns

Use OMC agents instead of custom for generic tasks:

| Task | Use OMC Agent |
|------|---------------|
| Quick code lookup | `oh-my-claudecode:explore` |
| Generic code review | `oh-my-claudecode:code-reviewer` |
| Architecture analysis | `oh-my-claudecode:architect` |
| Build fixes | `oh-my-claudecode:build-fixer` |
| Security review | `oh-my-claudecode:security-reviewer` |

Keep custom agents for floe-specific concerns only.

---

## Summary: Before → After

| Category | Before | After | Reduction |
|----------|--------|-------|-----------|
| Skills | 27 | 22 | -19% |
| Agents | 25 | 12 | -52% |
| Lines | ~12,500 | ~8,500 | -32% |

### Final Agents (12)
1. `contract-stability` - Cross-package contracts
2. `plugin-quality` - Plugin test coverage
3. `critic` - Final review gate
4. `docker-log-analyser` - Container logs
5. `helm-debugger` - K8s debugging
6. `code-pattern-reviewer` - Architecture patterns
7. `dead-code-detector` - Unused code
8. `security-scanner` - OWASP vulnerabilities
9. `test-design-reviewer` - Test architecture
10. `test-requirement-mapper` - Traceability
11. `performance-debt-detector` - N+1, O(n²)
12. `test-debt-analyzer` - Consolidated (NEW)

### Final Skills (22)
**SpecKit (11)**: specify, clarify, plan, tasks, taskstolinear, implement, implement-epic, test-review, wiring-check, merge-check, pr
**Tech (5)**: dbt-skill, pydantic-skill, dagster-skill, testing-skill, helm-k8s-skill
**Analysis (2)**: tech-debt-review, speckit-analyze
**Infra (3)**: beads, speckit-constitution, speckit-checklist
**Deprecated (1)**: speckit-architecture-check → merge into wiring-check

---

## Implementation Order

| Phase | Tasks | Effort |
|-------|-------|--------|
| 1 | Move unused skills to docs/ | 30m |
| 2 | Delete redundant agents (14) | 30m |
| 3 | Update speckit-test-review to use OMC | 1h |
| 4 | Update skill-chains.json | 15m |
| 5 | Validate SpecKit workflow | 30m |

**Total**: ~3 hours

---

## Validation

```bash
# Count after optimization
ls -1 .claude/skills/ | wc -l      # Target: 22
ls -1 .claude/agents/*.md | wc -l  # Target: 12

# Test SpecKit workflow
bd linear sync --pull
/speckit.implement

# Test pre-PR gates
/speckit.test-review
/speckit.wiring-check
/speckit.merge-check
```
