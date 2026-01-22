# Epic 12: Technical Debt Management

> **Purpose**: Systematic identification and reduction of technical debt across the floe platform

## Overview

Epic 12 focuses on maintaining code quality and reducing technical debt through regular audits and targeted remediation. This is an ongoing effort with quarterly review cycles.

## Sub-Epics

| Epic | Focus | Status | Debt Score Impact |
|------|-------|--------|-------------------|
| [12A](epic-12a-jan2026-tech-debt.md) | January 2026 Critical Issues | In Progress | 68 → 74 (+6) |
| [12B](epic-12b-improvement-opportunities.md) | Improvement Opportunities Backlog | Planned | 74 → 90 (target) |

## Audit History

| Date | Audit File | Score | Critical | High | Notes |
|------|------------|-------|----------|------|-------|
| 2026-01-22 11:00 | `.claude/reviews/tech-debt-20260122-110030.json` | 68/100 | 5 | 12 | Initial baseline |
| 2026-01-22 15:40 | `.claude/reviews/tech-debt-20260122-154004.json` | 74/100 | 5 | 19 | Post-12A improvements |

## Categories Tracked

1. **Architecture** - Circular dependencies, god modules, cohesion
2. **Complexity** - Cyclomatic complexity, cognitive complexity, nesting
3. **Testing** - Coverage gaps, policy violations, duplication
4. **Dependencies** - CVEs, outdated packages, unpinned versions
5. **Performance** - N+1 patterns, unbounded collections, caching
6. **Hotspots** - High churn, bus factor, coupling
7. **TODOs** - Age analysis, orphaned markers
8. **Documentation** - Missing docstrings, stale comments
9. **Dead Code** - Unused imports, unreachable code

## Running Audits

```bash
# PR mode (changed files only)
/tech-debt-review

# Full codebase audit
/tech-debt-review --all

# Targeted directory
/tech-debt-review packages/floe-core/

# Single category
/tech-debt-review --category=complexity
```

## Score Interpretation

| Range | Rating | Action |
|-------|--------|--------|
| 90-100 | Excellent | Maintain current practices |
| 75-89 | Good | Address critical issues |
| 60-74 | Needs Work | Prioritize debt reduction |
| 40-59 | Poor | Urgent attention needed |
| 0-39 | Critical | Stop feature work, fix debt |

## Related Resources

- **Tech Debt Skill**: `.claude/skills/tech-debt-review/`
- **Testing Standards**: `.claude/rules/testing-standards.md`
- **Architecture Docs**: `docs/architecture/`
- **Linear Project (12A)**: [Epic 12A: Tech Debt Q1 2026](https://linear.app/obsidianowl/project/epic-12a-tech-debt-q1-2026-3797f63d2107)
- **Linear Project (12B)**: [Epic 12B: Improvement Opportunities](https://linear.app/obsidianowl/project/epic-12b-improvement-opportunities-0246800533dd)

## Review Cadence

- **Weekly**: PR-level reviews before merge
- **Monthly**: Full codebase audit (`/tech-debt-review --all`)
- **Quarterly**: Epic planning based on audit findings
