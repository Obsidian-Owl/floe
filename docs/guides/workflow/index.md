# floe Development Workflow

This guide describes the three-phase development workflow for floe, combining collaborative design with automated implementation.

## Overview

The floe workflow optimizes for:
- **Quality**: All gates per iteration (lint, type, test, security, constitution)
- **Speed**: Parallel agent execution via git worktrees
- **Alignment**: Human-AI collaboration at design and review checkpoints
- **Traceability**: Full audit trail from requirement to commit

## Three-Phase Architecture

```
Phase A: Collaborative Design     [Human + AI]
    |
    v
Phase B: Automated Implementation [AI Only]
    |
    v
Phase C: Collaborative Pre-PR     [Human + AI]
```

## Phase A: Collaborative Design & Planning

Human-AI partnership for specification and planning.

| Command | Purpose | Output |
|---------|---------|--------|
| `/speckit.specify` | Create feature specification | `spec.md` |
| `/speckit.clarify` | Reduce ambiguity (optional) | Updated `spec.md` |
| `/speckit.plan` | Technical design + constitution gates | `plan.md`, `research.md`, `contracts/` |
| `/speckit.tasks` | Task decomposition | `tasks.md` with T### IDs |
| `/speckit.taskstolinear` | Create Linear issues | `.linear-mapping.json` |

**Key Principle**: Every decision point uses `AskUserQuestion` for alignment.

[Read more: Design & Planning](01-design-planning.md)

## Phase B: Automated Implementation

Fully automated parallel agent execution.

| Command | Purpose |
|---------|---------|
| `/ralph.spawn [epic]` | Create worktrees for ready tasks |
| `/ralph.status` | Monitor agent progress |

**Key Features**:
- One agent per worktree (isolated)
- Fresh context each iteration (Ralph Wiggum pattern)
- All quality gates per iteration
- Sub-task creation for discovered issues

[Read more: Automated Implementation](02-automated-implementation.md)

## Phase C: Collaborative Pre-PR Review

Human-AI session for quality validation.

| Command | Purpose |
|---------|---------|
| `/ralph.integrate [epic]` | Rebase and prepare for review |
| `/speckit.test-review` | Semantic test quality analysis |
| `/security-review` | Security vulnerability scan |
| `/arch-review` | Architecture alignment check |

**Key Principle**: Claude presents analysis, human makes decisions.

[Read more: Pre-PR Review](03-pre-pr-review.md)

## Quick Reference

### Starting Work

```bash
# 1. Design phase (collaborative)
/speckit.specify
/speckit.plan
/speckit.tasks
/speckit.taskstolinear

# 2. Implementation phase (automated)
/ralph.spawn [epic]
/ralph.status  # Monitor progress

# 3. Review phase (collaborative)
/ralph.integrate [epic]
/speckit.test-review
/security-review
```

### Linear Integration

All issue tracking uses Linear MCP directly (no caching layer):

```
mcp__plugin_linear_linear__list_issues({state: "backlog", team: "floe"})
mcp__plugin_linear_linear__update_issue({id, state: "Done"})
mcp__plugin_linear_linear__create_comment({issueId, body: "Completed: ..."})
```

## Documentation Index

1. [Design & Planning](01-design-planning.md) - Collaborative specification and planning
2. [Automated Implementation](02-automated-implementation.md) - Ralph Wiggum + worktrees
3. [Pre-PR Review](03-pre-pr-review.md) - Quality validation before PR
4. [Quality Gates](04-quality-gates.md) - All gates: lint, type, test, security, constitution
5. [Linear Integration](05-linear-integration.md) - Direct MCP integration patterns
6. [Parallel Agents](06-parallel-agents.md) - Worktree management and parallelization
7. [Troubleshooting](07-troubleshooting.md) - Agent recovery and blocked tasks

## Configuration

See `.ralph/config.yaml` for orchestration settings.
