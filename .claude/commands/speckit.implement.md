---
description: Implement the next ready task from Linear issue tracker with SpecKit integration
handoffs:
  - label: "Review tests"
    agent: speckit.test-review
    prompt: "Implementation complete. Review test quality?"
    send: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This command bridges SpecKit planning with Linear/Beads execution tracking.

**Architecture**: Linear is the source of truth. Beads is a local cache. See [Linear Workflow Guide](../../../docs/guides/linear-workflow.md).

**Modes**:
- **No arguments**: Auto-select first ready task
- **With selector**: Implement specific task (number, Task ID `T###`, or Linear ID `FLO-###`)

## Outline

1. **Setup & Sync**
   - Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root
   - Parse JSON output for `FEATURE_DIR`
   - Verify `.linear-mapping.json` exists in FEATURE_DIR (run `/speckit.taskstolinear` if missing)
   - If Beads CLI available (`bd`), sync from Linear: `bd linear sync --pull`

2. **Find Ready Tasks**
   - Load `$FEATURE_DIR/.linear-mapping.json` for task-to-Linear mappings
   - For each task in mapping, query Linear via `mcp__plugin_linear_linear__get_issue` for current status
   - Build ready list: issues with status type `unstarted` or `backlog` (not `started`, `completed`, `canceled`)
   - Display ready tasks with: number, Task ID, Linear identifier, title

3. **Task Selection**
   - Parse $ARGUMENTS for selector (first token):
     - Empty → auto-select first ready task
     - Number (`1`, `2`, `3`) → position in displayed ready list
     - Task ID (`T001`, `T042`) → match by task ID in mapping
     - Linear ID (`FLO-33`, `FLO-108`) → match by Linear identifier
   - Verify task not blocked: query with `includeRelations: true`, check `blockedBy` is empty
   - ERROR if blocked and show which issues block it

4. **Claim Task**
   - Query team statuses via `mcp__plugin_linear_linear__list_issue_statuses` (team: "floe")
   - Find status with type `started` (usually "In Progress")
   - Update Linear via `mcp__plugin_linear_linear__update_issue`:
     - `id`: Linear issue ID
     - `state`: the "In Progress" status name
     - `assignee`: "me"
   - Display confirmation with Linear URL

5. **Load Context**
   - Read task details from `$FEATURE_DIR/tasks.md` (parse task line for phase, user story, description)
   - Load `spec.md` and `plan.md` from FEATURE_DIR
   - Load `.specify/memory/constitution.md` for project principles
   - Display: phase, user story, task description, Linear URL

6. **Implementation**
   - Follow constitution principles: TDD (tests first), SOLID, atomic commits (300-600 LOC)
   - Implement per task description from tasks.md
   - Use project's existing patterns and tooling
   - Reference spec.md and plan.md for context

7. **Validation**
   - Run checks appropriate to what was implemented:
     - Python: `uv run mypy --strict`, `uv run ruff check`, `uv run pytest <relevant tests>`
     - Helm: `helm lint`, `helm template | kubectl apply --dry-run=client -f -`
     - General: verify code imports, builds, integrates with existing code
   - **Block closure if validation fails** - fix issues first

8. **Close Task**
   - Ask user confirmation via AskUserQuestion tool
   - Query statuses again, find status with type `completed` (usually "Done")
   - Update Linear status via `mcp__plugin_linear_linear__update_issue`
   - **MANDATORY**: Create Linear comment via `mcp__plugin_linear_linear__create_comment`:
     ```
     **Completed**: {TaskID}
     **Summary**: {what was implemented}
     **Commit**: {commit hash or "See latest commit"}
     **Files Changed**: {key files}
     ---
     *Closed via /speckit.implement*
     ```
   - Commit changes with message: `{type}(scope): {title} ({TaskID}, {LinearID})`
   - Example: `feat(plugin-api): add PluginMetadata ABC (T001, FLO-33)`

9. **Continue or Complete**
   - Query Linear for remaining ready tasks (status type `unstarted` or `backlog`)
   - If more tasks: ask user "Continue to next task?" via AskUserQuestion
   - If yes: loop back to step 2
   - If no or none remaining: display session summary and Linear project URL

## Tool Patterns

**Linear MCP tools** (never hardcode status names - always query first):

| Tool | Purpose |
|------|---------|
| `mcp__plugin_linear_linear__get_team({query: "floe"})` | Get team ID |
| `mcp__plugin_linear_linear__list_issue_statuses({team: teamId})` | Get status names by type |
| `mcp__plugin_linear_linear__get_issue({id, includeRelations: true})` | Get issue with blockers |
| `mcp__plugin_linear_linear__update_issue({id, state, assignee})` | Update status/assignee |
| `mcp__plugin_linear_linear__create_comment({issueId, body})` | Add closure comment |

**Status type mapping**:
- `unstarted` → "Todo" (ready to work)
- `backlog` → "Backlog" (ready to work)
- `started` → "In Progress" (claimed)
- `completed` → "Done" (finished)
- `canceled` → "Canceled" (abandoned)

## Key Rules

1. **Never hardcode status names** - Teams can customize "In Progress" to anything. Always query `list_issue_statuses` and match by `type` field.

2. **Always create Linear comment on closure** - The `bd close --reason` stores in Beads only. Team members viewing Linear need the comment for context.

3. **Include both IDs in commit message** - Format: `{type}(scope): {title} ({TaskID}, {LinearID})` enables traceability from git history.

4. **Block closure on validation failure** - Never mark a task "Done" if tests fail or code doesn't build.

5. **Verify not blocked before claiming** - Query with `includeRelations: true` to check `blockedBy` array.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No Linear mapping | Haven't created Linear issues | Run `/speckit.taskstolinear` |
| No ready tasks | All in progress or completed | Check Linear project view |
| Task blocked | Dependency not complete | Work on blocker first |
| Status not found | Team uses custom status names | Query statuses, match by `type` |
| Commit rejected | Pre-commit hook failure | Fix linting/type errors |

## References

- **[Linear Workflow Guide](../../../docs/guides/linear-workflow.md)** - Architecture, traceability, detailed patterns
- **[speckit.tasks](./speckit.tasks.md)** - Generate tasks.md
- **[speckit.taskstolinear](./speckit.taskstolinear.md)** - Create Linear issues from tasks
- **`.specify/memory/constitution.md`** - Project principles (TDD, SOLID, atomic commits)
