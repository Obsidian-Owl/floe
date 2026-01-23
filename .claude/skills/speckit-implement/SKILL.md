---
name: speckit-implement
description: Implement the next ready task from Linear issue tracker with SpecKit integration. Use when implementing tasks, working on Linear issues, or continuing feature development.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This skill bridges SpecKit planning with Linear/Beads execution tracking.

**Architecture**: Linear is the source of truth. Beads is a local cache. See [Linear Workflow Guide](../../../docs/guides/linear-workflow.md).

**Modes**:
- **No arguments**: Auto-select first ready task
- **With selector**: Implement specific task (number, Task ID `T###`, or Linear ID `FLO-###`)

---

## CRITICAL: Spec Context Loading (MANDATORY)

**You MUST load ALL spec artifacts into context BEFORE implementing any task.**

This is NON-NEGOTIABLE. Implementation without full spec context leads to:
- Deviations from agreed design
- Missing requirements
- Inconsistent architecture decisions
- Wasted rework

### Required Artifacts (Load All)

| Artifact | Purpose | Location |
|----------|---------|----------|
| **spec.md** | Feature requirements, acceptance criteria | `$FEATURE_DIR/spec.md` |
| **plan.md** | Architecture decisions, component design | `$FEATURE_DIR/plan.md` |
| **tasks.md** | Task breakdown with dependencies | `$FEATURE_DIR/tasks.md` |
| **research.md** | Technology research, patterns (if exists) | `$FEATURE_DIR/research.md` |
| **data-model.md** | Schema design, contracts (if exists) | `$FEATURE_DIR/data-model.md` |
| **contracts/** | Contract definitions (if exists) | `$FEATURE_DIR/contracts/*.md` |
| **.linear-mapping.json** | Task-to-Linear ID mappings | `$FEATURE_DIR/.linear-mapping.json` |
| **constitution.md** | Project principles (TDD, SOLID) | `.specify/memory/constitution.md` |

### Loading Protocol

**At the START of every implementation session:**

```bash
# 1. Identify feature directory
FEATURE_DIR=$(./specify/scripts/bash/check-prerequisites.sh --json | jq -r '.feature_dir')

# 2. Load ALL spec artifacts (use Read tool for each)
Read: $FEATURE_DIR/spec.md
Read: $FEATURE_DIR/plan.md
Read: $FEATURE_DIR/tasks.md
Read: $FEATURE_DIR/research.md       # if exists
Read: $FEATURE_DIR/data-model.md     # if exists
Read: $FEATURE_DIR/contracts/*.md    # if exists
Read: .specify/memory/constitution.md
```

**After context compaction**: Re-read ALL artifacts immediately. The summary may lose critical details.

**During implementation**: Reference spec.md and plan.md continuously. Every decision must align with the documented design.

---

## Memory Integration

### Before Starting
Search for relevant implementation patterns:
```bash
./scripts/memory-search "implementation patterns for {component type}"
```

Query patterns:
- For plugins: `"plugin implementation patterns"`
- For schemas: `"Pydantic schema patterns"`
- For tests: `"testing patterns for {feature}"`

### After Completion
Save key decisions for future sessions:
```bash
./scripts/memory-save --decisions "{key decisions made}" --issues "{LinearIDs}"
```

What to save:
- Implementation patterns that worked well
- Gotchas and edge cases discovered
- Architecture decisions made during implementation

## Constitution Alignment

This skill enforces project principles from `.specify/memory/constitution.md`:
- **TDD**: Tests first, implementation second
- **SOLID**: Single responsibility, clean interfaces
- **Atomic Commits**: 300-600 LOC per commit, focused changes

## Outline

1. **Setup & Sync**
   - Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root
   - Parse JSON output for `FEATURE_DIR`
   - Verify `.linear-mapping.json` exists in FEATURE_DIR (run `/speckit.taskstolinear` if missing)
   - If Beads CLI available (`bd`), sync from Linear: `bd linear sync --pull`

2. **Find Ready Tasks**
   - Load `$FEATURE_DIR/.linear-mapping.json` for task-to-Linear mappings
   - For each task in mapping, query Linear via `mcp__plugin_linear_linear__get_issue` for current status
   - Build ready list: issues with status type`backlog`
   - Display ready tasks with: number, Task ID, Linear identifier, title

3. **Task Selection**
   - Parse $ARGUMENTS for selector (first token):
     - Empty: auto-select first ready task
     - Number (`1`, `2`, `3`): position in displayed ready list
     - Task ID (`T001`, `T042`): match by task ID in mapping
     - Linear ID (`FLO-33`, `FLO-108`): match by Linear identifier
   - Verify task not blocked: query with `includeRelations: true`, check `blockedBy` is empty
   - ERROR if blocked and show which issues block it

4. **Claim Task**
   - Query team statuses via `mcp__plugin_linear_linear__list_issue_statuses` (team: "floe")
   - You MUST update Linear via `mcp__plugin_linear_linear__update_issue`:
     - `id`: Linear issue ID
     - `state`: "In Progress"
     - `assignee`: "me"
   - Display confirmation with Linear URL

5. **Load Context (CRITICAL - See "Spec Context Loading" above)**
   - **Load ALL spec artifacts** per the CRITICAL section above:
     - `$FEATURE_DIR/spec.md` - Full feature specification
     - `$FEATURE_DIR/plan.md` - Architecture and design decisions
     - `$FEATURE_DIR/tasks.md` - Parse task line for phase, user story, description
     - `$FEATURE_DIR/research.md` - Technology research (if exists)
     - `$FEATURE_DIR/data-model.md` - Schema design (if exists)
     - `$FEATURE_DIR/contracts/*.md` - Contract definitions (if exists)
     - `.specify/memory/constitution.md` - Project principles
   - **This is NON-NEGOTIABLE** - do NOT proceed without full context
   - Display: phase, user story, task description, Linear URL
   - Use Explore subagents to ensure you deeply understand the codebase and target architecture
   - Validate any ambiguity with the AskUserQuestions tool

6. **Implementation**
   - Follow constitution principles: TDD (tests first), SOLID, atomic commits (300-600 LOC)
   - Implement per task description from tasks.md
   - Use project's existing patterns and tooling
   - Reference spec.md and plan.md for context

   **Cleanup (REQUIRED for refactors)**:
   When changing existing code, you MUST clean up:
   - Remove replaced code - don't leave old implementations behind
   - Remove orphaned tests - tests for removed code should be deleted
   - Remove unused imports - `ruff check --select F401` on changed files
   - Update `__all__` exports - remove exports that no longer exist

   **Quick cleanup check:**
   ```bash
   # Find unused imports in changed files
   git diff HEAD~1 --name-only -- '*.py' | xargs -I{} uv run ruff check {} --select F401,F811
   ```

   **Principle**: Leave the codebase cleaner than you found it.

7. **Integration Check (Per-Task)**
   Before closing a task, verify deliverables are integrated into the system:

   **For new modules/classes:**
   - [ ] Imported by at least one other file in `src/` (not just tests)
   - [ ] Has a path to an entry point (CLI command, plugin registry, or package `__all__`)

   **For plugin implementations:**
   - [ ] Entry point registered in `pyproject.toml` under `[project.entry-points]`
   - [ ] Plugin discoverable via `PluginRegistry.get_plugins()`

   **For new schemas:**
   - [ ] Added to `CompiledArtifacts` or exported from package
   - [ ] Has a consumer that imports it

   **Quick integration check:**
   ```bash
   # Verify new files are imported somewhere in src/
   for f in $(git diff HEAD~1 --name-only --diff-filter=A -- '*.py' | grep '/src/'); do
     basename="${f##*/}"
     module="${basename%.py}"
     grep -r "from.*import.*$module\|import.*$module" $(dirname $f)/.. --include="*.py" | grep -v test | head -1
   done
   ```

   **If new code isn't reachable**: Wire it up before closing the task. Add a wiring commit if needed.

8. **Validation**
   - Run checks appropriate to what was implemented:
     - Python: `uv run mypy --strict`, `uv run ruff check`, `uv run pytest <relevant tests>`
     - Helm: `helm lint`, `helm template | kubectl apply --dry-run=client -f -`
     - General: verify code imports, builds, integrates with existing code
   - **Block closure if validation fails** - fix issues first

9. **Close Task**
   - Ask user confirmation via AskUserQuestion tool
   - Query statuses again, find status with type `completed` (usually "Done")
   - You MUST update Linear status via `mcp__plugin_linear_linear__update_issue`
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

10. **Continue or Complete**
   - Query Linear for remaining ready tasks (status type `unstarted` or `backlog`)
   - If more tasks: ask user "Continue to next task?" via AskUserQuestion
   - If yes: loop back to step 2
   - If no or none remaining: display session summary and Linear project URL

11. **Save Session Decisions** (end of session):
    - If implementation involved significant decisions, save them for future reference:
      ```bash
      ./scripts/memory-save --decisions "{key decisions made}" --issues "{LinearIDs}"
      ```
    - This enables future sessions to recover context and maintain consistency
    - If agent-memory unavailable, decisions are captured in Linear comments (step 8)

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
- `unstarted`: "Todo" (ready to work)
- `backlog`: "Backlog" (ready to work)
- `started`: "In Progress" (claimed)
- `completed`: "Done" (finished)
- `canceled`: "Canceled" (abandoned)

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

## Handoff

After completing this skill:
- **Review tests**: Run `/speckit.test-review` to validate test quality
- **Continue implementing**: Run `/speckit.implement` again for next task
- **Batch implementation**: Run `/speckit.implement-epic` for automatic continuation

## References

- **[Linear Workflow Guide](../../../docs/guides/linear-workflow.md)** - Architecture, traceability, detailed patterns
- **[speckit.tasks](../speckit-tasks/SKILL.md)** - Generate tasks.md
- **[speckit.taskstolinear](../speckit-taskstolinear/SKILL.md)** - Create Linear issues from tasks
- **`.specify/memory/constitution.md`** - Project principles (TDD, SOLID, atomic commits)
- **Memory Scripts** - `./scripts/memory-{search,save,add}` for knowledge graph integration
