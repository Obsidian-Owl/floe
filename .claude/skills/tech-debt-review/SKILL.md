---
name: tech-debt-review
description: Comprehensive technical debt analysis with PR and full-audit modes. Use when reviewing code quality before PR, conducting periodic health checks, or investigating maintainability issues.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Usage Modes

| Mode | Command | Scope | When to Use |
|------|---------|-------|-------------|
| **PR Review** | `/tech-debt-review` | Changed files vs main | Before PR (default) |
| **Full Audit** | `/tech-debt-review --all` | Entire codebase | Periodic health check |
| **Targeted** | `/tech-debt-review path/to/dir` | Specific directory | Focused analysis |
| **Category** | `/tech-debt-review --category=deps` | Single category | Quick specific check |
| **Combined** | `/tech-debt-review --all --category=complexity` | Full audit, one category | Targeted deep dive |

### Category Filter Values

| Category | Agent(s) Invoked | Focus Area |
|----------|------------------|------------|
| `complexity` | code-complexity-analyzer | Cyclomatic/cognitive complexity |
| `dead-code` | dead-code-detector | Unreachable code, unused symbols |
| `deps` | dependency-debt-analyzer | Outdated/vulnerable dependencies |
| `docs` | documentation-debt-analyzer | Missing/stale documentation |
| `testing` | testing-debt-analyzer, test-duplication-detector | Coverage gaps, test quality |
| `todos` | todo-archaeology | TODO/FIXME/HACK archaeology |
| `hotspots` | git-hotspot-analyzer | Code churn, change patterns |
| `performance` | performance-debt-detector | Performance anti-patterns |
| `architecture` | code-pattern-reviewer | Coupling, cohesion, design smells |

## Goal

Perform a comprehensive technical debt analysis that answers: **What maintenance burden exists in this code?**

This skill orchestrates **10 specialized agents** in parallel to analyze:
- Code complexity and maintainability
- Dead code and unused symbols
- Dependency health and security
- Documentation gaps
- Testing debt
- TODO/FIXME archaeology
- Git hotspots and churn
- Performance anti-patterns
- Architecture smells

Results are synthesized into a prioritized, actionable report with trend tracking.

## Operating Constraints

**STRICTLY READ-ONLY**: Do **not** modify any files. Output analysis and recommendations.

**PARALLEL EXECUTION**: Launch all applicable agents in a single message for efficiency.

**TREND TRACKING**: Full audits are saved to `.claude/reviews/` for historical comparison.

## Constitution Alignment

This skill validates adherence to project principles:
- **Quality**: Maintain high code quality standards
- **Maintainability**: Keep technical debt manageable
- **Security**: No known vulnerabilities in dependencies

## Memory Integration

### After Completion (Full Audit Only)
Save audit findings for trend analysis:
```bash
./scripts/memory-save --decisions "Tech debt audit: Score {score}/100, {critical} critical issues, top areas: {categories}" --issues "{LinearIDs}"
```

## Execution Steps

### Phase 0: Scope Determination

**You handle this phase directly.**

**Parse user input to determine mode:**

1. **If `--all` flag present**: Full codebase audit
   ```bash
   # Get all Python files
   find packages/ plugins/ -name "*.py" -type f 2>/dev/null | wc -l
   ```

2. **If specific path provided**: Targeted directory
   ```bash
   # Verify path exists and count files
   find <provided-path> -name "*.py" -type f 2>/dev/null | wc -l
   ```

3. **If `--category=<name>` present**: Extract category for filtering

4. **Default (no args)**: Changed files only
   ```bash
   # Get changed Python files
   git diff --name-only main...HEAD | grep '\.py$'
   ```

**Report mode to user:**
- `--all` mode: "Running FULL CODEBASE audit on N Python files"
- Specific path: "Analyzing directory: <path> (N files)"
- `--category=X`: "Running single-category analysis: X"
- Default: "Analyzing N files changed vs main"

If no files to analyze in default mode, suggest using `--all` for full audit.

### Phase 1: Check for Prior Audits (Trend Tracking)

**Only for `--all` mode:**

```bash
# Find most recent audit
ls -t .claude/reviews/tech-debt-*.json 2>/dev/null | head -1
```

If prior audit exists, load it for trend comparison in Phase 3.

### Phase 2: Parallel Analysis

**Invoke agents IN PARALLEL (single message, multiple Task calls):**

Based on `--category` filter (or all if no filter):

```
# Haiku agents (fast, single-file analysis)
Task(todo-archaeology, "Analyze TODO/FIXME/HACK comments...
Files: [list or scope]
Return archaeology report with age analysis.")

Task(documentation-debt-analyzer, "Analyze documentation gaps...
Files: [list or scope]
Return documentation debt report.")

Task(code-complexity-analyzer, "Analyze code complexity...
Files: [list or scope]
Return complexity metrics report.")

# Sonnet agents (cross-file analysis)
Task(dead-code-detector, "Detect unreachable and unused code...
Files: [list or scope]
Return dead code report.")

Task(dependency-debt-analyzer, "Analyze dependency health...
Scope: [package dirs]
Return dependency health report.")

Task(testing-debt-analyzer, "Analyze test coverage and quality gaps...
Files: [list or scope]
Return testing debt report.")

Task(git-hotspot-analyzer, "Analyze git history for hotspots and churn...
Files: [list or scope]
Return hotspot analysis report.")

Task(performance-debt-detector, "Detect performance anti-patterns...
Files: [list or scope]
Return performance debt report.")

# Existing agents (reused)
Task(code-pattern-reviewer, "Analyze module patterns and architecture...
Files: [list or scope]
Return architecture pattern report.")

Task(test-duplication-detector, "Detect test duplication...
Files: [list or scope]
Return test duplication report.")
```

**Wait for all agents to return.**

### Phase 3: Synthesis

**You handle this phase directly.**

1. **Aggregate findings** from all agent reports
2. **Classify by severity** using `.claude/skills/tech-debt-review/references/severity-criteria.md`
3. **Calculate debt score** (0-100, where 100 = no debt):
   - Start at 100
   - CRITICAL issues: -10 each (max -40)
   - HIGH issues: -5 each (max -30)
   - MEDIUM issues: -2 each (max -20)
   - LOW issues: -1 each (max -10)
4. **Prioritize by** Risk x Impact / Effort (see `references/prioritization.md`)
5. **Compare trends** if prior audit exists

### Phase 4: Persistence (Full Audit Mode Only)

**Only for `--all` mode:**

Save audit snapshot:
```bash
# Generate timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Save audit to .claude/reviews/tech-debt-${TIMESTAMP}.json
```

**Storage Format:**
```json
{
  "timestamp": "2026-01-22T10:30:00Z",
  "scope": "full-audit",
  "branch": "main",
  "commit": "<git-hash>",
  "debt_score": 72,
  "categories": {
    "complexity": {"issues": 8, "critical": 1, "high": 2, "medium": 3, "low": 2},
    "dead_code": {"issues": 3, "critical": 0, "high": 1, "medium": 2, "low": 0},
    "dependencies": {"issues": 5, "critical": 2, "high": 1, "medium": 1, "low": 1},
    "documentation": {"issues": 7, "critical": 0, "high": 0, "medium": 4, "low": 3},
    "testing": {"issues": 12, "critical": 0, "high": 3, "medium": 5, "low": 4},
    "todos": {"issues": 15, "critical": 0, "high": 2, "medium": 8, "low": 5},
    "hotspots": {"issues": 4, "critical": 1, "high": 1, "medium": 2, "low": 0},
    "performance": {"issues": 6, "critical": 0, "high": 2, "medium": 3, "low": 1},
    "architecture": {"issues": 4, "critical": 1, "high": 1, "medium": 1, "low": 1}
  },
  "total_issues": 64,
  "critical_issues": 5,
  "remediation_days": 15
}
```

## Output Format

```markdown
## Technical Debt Review

**Scope**: [PR: 15 files | Full Audit: 234 files | Directory: path/ (45 files)]
**Debt Score**: 72/100 (Good)
**Estimated Remediation**: 15 person-days
**Trend**: [+5 vs last audit | First audit | N/A for PR mode]

---

### Executive Summary

| Category | Issues | Critical | High | Trend |
|----------|--------|----------|------|-------|
| Complexity | 8 | 1 | 2 | [arrow] |
| Dead Code | 3 | 0 | 1 | [arrow] |
| Dependencies | 5 | 2 | 1 | [arrow] |
| Documentation | 7 | 0 | 0 | [arrow] |
| Testing | 12 | 0 | 3 | [arrow] |
| TODOs | 15 | 0 | 2 | [arrow] |
| Hotspots | 4 | 1 | 1 | [arrow] |
| Performance | 6 | 0 | 2 | [arrow] |
| Architecture | 4 | 1 | 1 | [arrow] |

**Trend Legend**: [up-arrow] worse | [down-arrow] better | [right-arrow] stable | - no prior data

---

### Priority Actions (Fix These First)

| Priority | Issue | Category | File:Line | Impact | Effort |
|----------|-------|----------|-----------|--------|--------|
| P0 | CVE-2024-XXXXX in package X | Dependencies | pyproject.toml | Critical | Low |
| P0 | God class (15+ methods) | Architecture | compiler.py:45 | High | Medium |
| P1 | 45% test coverage gap | Testing | service.py | High | High |
| P1 | N+1 query pattern | Performance | repository.py:123 | High | Medium |
| P2 | TODO from 2024 | TODOs | utils.py:67 | Medium | Low |

---

### Detailed Findings by Category

#### Code Complexity (8 issues)

[Agent report summary]

**Critical/High Issues:**
- `file.py:123` - Cyclomatic complexity 25 (threshold: 10)
- `file.py:456` - Cognitive complexity 32 (threshold: 15)

#### Dead Code (3 issues)

[Agent report summary]

#### Dependencies (5 issues)

[Agent report summary]

**Security Vulnerabilities:**
- CVE-2024-XXXXX in `package==1.2.3` (CRITICAL)

#### Documentation (7 issues)

[Agent report summary]

#### Testing Debt (12 issues)

[Agent report summary]

#### TODO Archaeology (15 issues)

[Agent report summary]

**Oldest TODOs:**
- `file.py:45` - "TODO: Fix this" (18 months old)

#### Git Hotspots (4 issues)

[Agent report summary]

**High Churn Files:**
- `compiler.py` - 45 changes in 3 months

#### Performance (6 issues)

[Agent report summary]

#### Architecture (4 issues)

[Agent report summary]

---

### Debt Score Calculation

```
Starting Score: 100
- Critical Issues (5 x -10): -50 (capped at -40)
- High Issues (15 x -5): -75 (capped at -30)
- Medium Issues (27 x -2): -54 (capped at -20)
- Low Issues (17 x -1): -17 (capped at -10)
= Final Score: 72/100 (Good)
```

**Score Interpretation:**
| Range | Rating | Action |
|-------|--------|--------|
| 90-100 | Excellent | Maintain |
| 75-89 | Good | Address critical issues |
| 60-74 | Needs Work | Prioritize debt reduction |
| 40-59 | Poor | Urgent attention needed |
| 0-39 | Critical | Stop feature work, fix debt |

---

### Recommendations

1. **Immediate** (this PR/sprint):
   - Fix CVE-2024-XXXXX by upgrading package X
   - Address P0 architecture issue in compiler.py

2. **Short-term** (next 2-4 sprints):
   - Increase test coverage on service.py
   - Refactor N+1 query patterns

3. **Long-term** (roadmap):
   - Establish complexity budgets
   - Implement automated debt tracking

---

### Trend Comparison (Full Audit Only)

**Previous Audit**: 2026-01-15
**Score Change**: 72 -> 72 (stable)

| Category | Previous | Current | Change |
|----------|----------|---------|--------|
| Complexity | 6 | 8 | +2 [up-arrow] |
| Dead Code | 5 | 3 | -2 [down-arrow] |
| Dependencies | 5 | 5 | 0 [right-arrow] |

**New Issues Since Last Audit**: 4
**Resolved Issues Since Last Audit**: 2

---

### Next Steps

- [ ] Address P0 issues before PR
- [ ] Schedule P1 issues for next sprint
- [ ] Re-run `/tech-debt-review` to verify fixes
- [ ] Run `/tech-debt-review --all` monthly for trend tracking
```

## What This Review Checks

### From Specialized Agents

| Agent | Focus | Key Metrics |
|-------|-------|-------------|
| code-complexity-analyzer | Complexity metrics | Cyclomatic >10, cognitive >15, nesting >4 |
| dead-code-detector | Unused code | Unreachable statements, unused imports/functions |
| dependency-debt-analyzer | Dependency health | CVEs, outdated packages, unused deps |
| documentation-debt-analyzer | Documentation gaps | Missing docstrings, stale comments |
| testing-debt-analyzer | Test quality | Coverage gaps, flaky tests, missing assertions |
| todo-archaeology | TODO analysis | Age, context, linked issues |
| git-hotspot-analyzer | Code churn | High-change files, risky commits |
| performance-debt-detector | Performance issues | N+1 queries, sync blocks, memory leaks |
| code-pattern-reviewer | Architecture | Coupling, cohesion, circular deps |
| test-duplication-detector | Test duplication | Redundant tests, parametrization opportunities |

### What This Review Does NOT Check

- **Linting/style**: ruff handles this
- **Type safety**: mypy handles this
- **Security**: Aikido/SonarQube handle this (except dependency CVEs)
- **Runtime bugs**: Testing handles this

## When to Use

| Situation | Recommended Mode |
|-----------|------------------|
| Before creating a PR | `/tech-debt-review` (changed files) |
| Monthly health check | `/tech-debt-review --all` |
| Investigating slow area | `/tech-debt-review path/to/module --category=performance` |
| After major refactor | `/tech-debt-review --all` |
| Quick dependency check | `/tech-debt-review --category=deps` |
| Onboarding to codebase | `/tech-debt-review --all` |

## Handoff

After completing this skill:
- **Fix P0 issues**: Address critical issues immediately
- **Track P1 issues**: Create Linear tickets for high-priority debt
- **Continue workflow**: Run `/speckit.test-review`, `/speckit.wiring-check`, and `/speckit.merge-check` before PR

## References

- **`references/debt-taxonomy.md`** - Complete debt category definitions
- **`references/prioritization.md`** - Risk/impact/effort framework
- **`references/severity-criteria.md`** - Severity classification rules
