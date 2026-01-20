---
name: speckit-implement-epic
description: Implement ALL tasks in the current epic until completion (auto-loop, no confirmation). Use when batch processing tasks, automating implementation, or running unattended task completion.
---

## User Input

```text
$ARGUMENTS
```

## Overview

This skill implements ALL tasks in an epic sequentially, auto-continuing after each task completes. Use `/speckit.implement` instead if you want manual confirmation between tasks.

**Stops only when:**
1. ALL tasks are Done (success)
2. A task is BLOCKED (requires human intervention)
3. Context window compacts (SessionStart hook will remind to continue)

---

## CRITICAL: Spec Context Loading (MANDATORY)

**You MUST load ALL spec artifacts into context and KEEP THEM LOADED throughout the entire epic.**

This is NON-NEGOTIABLE. Implementation without full spec context leads to:
- Deviations from agreed design
- Missing requirements
- Inconsistent architecture decisions
- Wasted rework

### Required Artifacts (Load All, Keep All)

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

**At the START of epic auto-mode (before any task):**

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

**After EVERY context compaction**: Re-read ALL artifacts immediately. The summary WILL lose critical details. This is your FIRST action after recovery.

**Throughout the epic**: These artifacts define the "what" and "why" of every task. Reference them continuously. Every implementation decision must align with the documented design.

---

## Memory Integration

### Before Starting
Search for epic-level context:
```bash
./scripts/memory-search "epic {epic-name} architecture decisions"
```

### After Completion
Save all decisions made during the epic:
```bash
./scripts/memory-save --decisions "{all key decisions from epic}" --issues "{all LinearIDs}"
```

What to save:
- Architecture patterns established during epic
- Reusable implementation patterns discovered
- Gotchas and lessons learned

## Constitution Alignment

This skill enforces project principles:
- **TDD**: Every task includes tests first
- **SOLID**: Clean interfaces and single responsibility
- **Atomic Commits**: Each task commits independently (300-600 LOC)

## Setup

1. **Create state file** (for recovery after compaction):
   ```bash
   mkdir -p .agent
   ```
   Then write JSON state file using Python or inline:
   ```python
   import json
   from datetime import datetime

   state = {
       "mode": "epic-auto",
       "feature_dir": "{FEATURE_DIR from prerequisites}",
       "epic_name": "{basename of feature_dir}",
       "branch": "{current git branch}",
       "started_at": datetime.utcnow().isoformat() + "Z",
       "total_tasks": {count from .linear-mapping.json},
       "completed_before_compact": 0,
       "compaction_count": 0
   }

   with open(".agent/epic-auto-mode", "w") as f:
       json.dump(state, f, indent=2)
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
  - Check if all tasks have status type `completed`: "EPIC COMPLETE"
  - Otherwise check for blocked tasks: "EPIC BLOCKED"

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

### Step 4: Load Context (CRITICAL - See "Spec Context Loading" above)

- **Load ALL spec artifacts** per the CRITICAL section above:
  - `$FEATURE_DIR/spec.md` - Full feature specification
  - `$FEATURE_DIR/plan.md` - Architecture and design decisions
  - `$FEATURE_DIR/tasks.md` - Task details for current task
  - `$FEATURE_DIR/research.md` - Technology research (if exists)
  - `$FEATURE_DIR/data-model.md` - Schema design (if exists)
  - `$FEATURE_DIR/contracts/*.md` - Contract definitions (if exists)
  - `.specify/memory/constitution.md` - Project principles
- **This is NON-NEGOTIABLE** - do NOT proceed without full context
- Use Explore subagents for codebase understanding
- **After compaction recovery**: This step is your FIRST action - re-read ALL artifacts

### Step 5: Implement

- Follow constitution principles: TDD (tests first), SOLID, atomic commits
- Implement per task description from tasks.md
- Use project's existing patterns and tooling

### Step 6: Validate

- Run checks appropriate to what was implemented:
  - Python: `uv run mypy --strict`, `uv run ruff check`, `uv run pytest <relevant tests>`
  - Helm: `helm lint`, `helm template | kubectl apply --dry-run=client -f -`
- **If validation fails**: Fix issues before proceeding (do NOT skip)

### Step 6.5: Quality Verification Loop (NEW)

**Pattern**: Verify implementation quality before closing task. Loop until pass.

1. **Invoke Quality Agents** on changed files:
   ```
   # For test files
   Task(test-edge-case-analyzer, "{test_file}")
   Task(test-isolation-checker, "{test_file}")

   # For source files
   Task(code-pattern-reviewer-low, "{source_file}")
   Task(docstring-validator, "{source_file}")
   ```

2. **Review Agent Findings**:
   - CRITICAL issues: Must fix before proceeding
   - WARNING issues: Should fix if straightforward
   - SUGGESTIONS: Note for future improvement

3. **Fix Critical Issues**:
   - Address each critical finding
   - Re-run validation (Step 6)
   - Re-run quality agents

4. **Verification Pass Criteria**:
   - Zero CRITICAL findings
   - Zero BLOCKER issues from architecture drift check
   - All tests pass
   - Type check passes

5. **Maximum Iterations**: 3
   - If still failing after 3 iterations, mark task as BLOCKED
   - Create Linear comment explaining blockers

**Output during verification**:
```
[QUALITY-LOOP] Iteration {n}/3 | Critical: {count} | Warnings: {count}
```

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

### Step 8: Update State File

Update `.agent/epic-auto-mode` with progress:
```python
import json

with open(".agent/epic-auto-mode") as f:
    state = json.load(f)

state["last_task"] = "{TaskID}"
state["last_linear_id"] = "{LinearID}"
state["completed_before_compact"] = {current completed count}

with open(".agent/epic-auto-mode", "w") as f:
    json.dump(state, f, indent=2)
```

### Step 9: Auto-Continue

**NO confirmation prompt** - Loop back to Step 1 immediately.

## Completion States

### EPIC COMPLETE

When all tasks have status type `completed`:

**CRITICAL: Remove state file IMMEDIATELY before any other output:**
```bash
rm -f .agent/epic-auto-mode
```

**Why first?** If compaction happens after the banner but before cleanup, the file would still exist and Claude would try to resume. Removing first ensures clean state.

Then output the completion banner:
```
================================================================================
EPIC COMPLETE
================================================================================

Feature: {feature-name}
Tasks completed: {count}
Total commits: {count}

Epic auto-mode has ended. State file removed.

Next steps:
  1. /speckit.test-review - Review test quality
  2. /speckit.integration-check - Validate integration
  3. /speckit.pr - Create pull request with Linear links
================================================================================
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

After compaction, Claude automatically recovers via **CLAUDE.md instructions** (which survive compaction verbatim).

### How It Works

1. **PreCompact hook** (`scripts/save-epic-checkpoint`) captures current state before compaction
2. **Compaction occurs** - conversation summarized, but files survive
3. **CLAUDE.md is reloaded** from disk (verbatim, not summarized)
4. **CLAUDE.md instructs Claude** to check for `.agent/epic-auto-mode`
5. **If file exists**, Claude reads state and **continues implementing automatically**

### State File Contents

```json
{
  "mode": "epic-auto",
  "feature_dir": "specs/epic-name",
  "epic_name": "epic-name",
  "branch": "feat/epic-name",
  "started_at": "2026-01-17T10:30:00Z",
  "last_task": "T005",
  "last_linear_id": "FLO-123",
  "total_tasks": 15,
  "completed_before_compact": 4,
  "compaction_count": 1
}
```

### Recovery Behavior

**Claude MUST NOT ask the user "should I continue?"** - the existence of the state file IS the user's instruction to continue automatically.

After compaction, Claude:
1. Reads `.agent/epic-auto-mode` for recovery state
2. **IMMEDIATELY re-reads ALL spec artifacts** (spec.md, plan.md, tasks.md, research.md, data-model.md, contracts/*, constitution.md)
3. Queries Linear for current task status
4. Finds next ready task
5. **Resumes implementation immediately** without prompting

**CRITICAL**: Step 2 (reloading spec artifacts) is NON-NEGOTIABLE. The compaction summary WILL lose critical design details. You MUST re-read the full files to maintain implementation quality.

## Tool Patterns

Same as `/speckit.implement` - see that skill for Linear MCP tool reference.

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

## Handoff

After completing this skill:
- **Review tests**: Run `/speckit.test-review` to validate test quality
- **Check integration**: Run `/speckit.integration-check` before PR
- **Create PR**: Run `/speckit.pr` to create pull request with Linear links

## References

- **[speckit.implement](../speckit-implement/SKILL.md)** - Single-task implementation with confirmation
- **[Linear Workflow Guide](../../../docs/guides/linear-workflow.md)** - Architecture, traceability
- **`.specify/memory/constitution.md`** - Project principles
