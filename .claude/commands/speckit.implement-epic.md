---
description: Implement ALL tasks in the current epic until completion (auto-loop, no confirmation)
handoffs:
  - label: "Review tests"
    agent: speckit.test-review
    prompt: "Epic complete. Review test quality?"
    send: false
---

## User Input

```text
$ARGUMENTS
```

## Overview

This command implements ALL tasks in an epic sequentially, auto-continuing
after each task completes. Use `/speckit.implement` instead if you want
manual confirmation between tasks.

**Stops only when:**
1. ALL tasks are Done (success)
2. A task is BLOCKED (requires human intervention)
3. Context window compacts (SessionStart hook will remind to continue)

## Setup

1. **Create state file** (for recovery after compaction):
   ```bash
   mkdir -p .agent
   echo "epic-auto-mode" > .agent/epic-auto-mode
   ```

2. **Run prerequisite checks**:
   - Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root
   - Parse JSON output for `FEATURE_DIR`
   - Verify `.linear-mapping.json` exists in FEATURE_DIR (run `/speckit.taskstolinear` if missing)

3. **Output banner**:
   ```
   ================================================================================
   EPIC AUTO-MODE STARTING
   ================================================================================
   Feature: {feature-name}
   Tasks: {total-count}

   Mode: Auto-continue (no confirmation between tasks)
   Recovery: .agent/epic-auto-mode
   ================================================================================
   ```

## Process Loop

**Repeat until ALL tasks complete or BLOCKED:**

### Step 1: Find Next Ready Task

- Load `$FEATURE_DIR/.linear-mapping.json` for task-to-Linear mappings
- For each task in mapping, query Linear via `mcp__plugin_linear_linear__get_issue` for current status
- Build ready list: issues with status type `backlog` or `unstarted`
- If no ready tasks:
  - Check if all tasks have status type `completed` → "EPIC COMPLETE"
  - Otherwise check for blocked tasks → "EPIC BLOCKED"

### Step 2: Output Progress Marker

```
[EPIC-AUTO-MODE] Task: {TaskID} ({LinearID}) | Remaining: {count} | {title}
```

### Step 3: Claim Task

- Query team statuses via `mcp__plugin_linear_linear__list_issue_statuses` (team: "floe")
- Update Linear via `mcp__plugin_linear_linear__update_issue`:
  - `id`: Linear issue ID
  - `state`: "In Progress"
  - `assignee`: "me"

### Step 4: Load Context

- Read task details from `$FEATURE_DIR/tasks.md`
- Load `spec.md` and `plan.md` from FEATURE_DIR
- Load `.specify/memory/constitution.md` for project principles
- Use Explore subagents for codebase understanding

### Step 5: Implement

- Follow constitution principles: TDD (tests first), SOLID, atomic commits
- Implement per task description from tasks.md
- Use project's existing patterns and tooling

### Step 6: Validate

- Run checks appropriate to what was implemented:
  - Python: `uv run mypy --strict`, `uv run ruff check`, `uv run pytest <relevant tests>`
  - Helm: `helm lint`, `helm template | kubectl apply --dry-run=client -f -`
- **If validation fails**: Fix issues before proceeding (do NOT skip)

### Step 7: Close Task

- Query statuses, find status with type `completed` (usually "Done")
- Update Linear status via `mcp__plugin_linear_linear__update_issue`
- **MANDATORY**: Create Linear comment via `mcp__plugin_linear_linear__create_comment`:
  ```
  **Completed**: {TaskID}
  **Summary**: {what was implemented}
  **Commit**: {commit hash}
  **Files Changed**: {key files}
  ---
  *Closed via /speckit.implement-epic*
  ```
- Commit changes: `{type}(scope): {title} ({TaskID}, {LinearID})`

### Step 8: Auto-Continue

**NO confirmation prompt** - Loop back to Step 1 immediately.

## Completion States

### EPIC COMPLETE

When all tasks have status type `completed`:

```
================================================================================
EPIC COMPLETE
================================================================================

Feature: {feature-name}
Tasks completed: {count}
Total commits: {count}

Next steps:
  1. /speckit.test-review - Review test quality
  2. /speckit.integration-check - Validate integration
  3. gh pr create - Create pull request
================================================================================
```

Then remove state file:
```bash
rm -f .agent/epic-auto-mode
```

### EPIC BLOCKED

If any task has non-empty `blockedBy` relation or encounters unrecoverable error:

```
================================================================================
EPIC BLOCKED
================================================================================

Task: {TaskID} ({LinearID})
Reason: {blocked-by issues or error description}

To resume after resolving:
  /speckit.implement-epic

State saved in: .agent/epic-auto-mode
================================================================================
```

**Do NOT remove state file** - allows resume after resolution.

## Context Recovery

After compaction, SessionStart hook fires and runs `scripts/session-recover`.
The script checks for `.agent/epic-auto-mode` and outputs:

```
================================================================================
EPIC AUTO-MODE DETECTED
================================================================================

You were implementing tasks in auto-mode.

To continue automatic implementation:
  /speckit.implement-epic

To implement tasks one at a time:
  /speckit.implement

================================================================================
```

## Tool Patterns

Same as `/speckit.implement` - see that command for Linear MCP tool reference.

## Key Differences from /speckit.implement

| Aspect | /speckit.implement | /speckit.implement-epic |
|--------|-------------------|------------------------|
| Confirmation | Asks after each task | Never asks |
| State file | None | `.agent/epic-auto-mode` |
| Recovery | Manual re-run | SessionStart hook detects |
| Use case | Single task or interactive | Batch processing |

## Error Handling

| Error | Cause | Behavior |
|-------|-------|----------|
| No ready tasks | All blocked or done | Check completion vs blocked |
| Task blocked | Dependency not complete | Stop with BLOCKED message |
| Validation fails | Tests/lint fail | Fix in-place, don't skip |
| API error | Linear/network issue | Retry once, then BLOCKED |

## References

- **[speckit.implement](./speckit.implement.md)** - Single-task implementation with confirmation
- **[Linear Workflow Guide](../../../docs/guides/linear-workflow.md)** - Architecture, traceability
- **`.specify/memory/constitution.md`** - Project principles
