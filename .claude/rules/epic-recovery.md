# Epic Auto-Mode Recovery (CRITICAL)

**THIS IS CRITICAL**: After context compaction, skill instructions are lost but CLAUDE.md survives. Check for active workflows immediately.

## Check for Active Epic Auto-Mode

```bash
if [ -f ".agent/epic-auto-mode" ]; then
    cat .agent/epic-auto-mode  # Contains epic context
fi
```

**If `.agent/epic-auto-mode` exists, YOU MUST:**

1. **Read the state file** to understand current context
2. **Continue implementing automatically** - do NOT wait for user prompt
3. **Follow the workflow**:
   - Sync from Linear: `bd linear sync --pull`
   - Find next ready task (status: backlog/unstarted)
   - Implement (TDD, SOLID, atomic commits)
   - Update Linear status to Done
   - Create Linear comment with completion summary
   - Commit changes
   - **Loop to next task immediately** (no confirmation)

4. **Only stop for**:
   - Design questions → Use `AskUserQuestion` tool
   - All tasks completed → "EPIC COMPLETE" banner, remove state file
   - Task blocked → "EPIC BLOCKED" banner, keep state file

## State File Format

```json
{
  "mode": "epic-auto",
  "feature_dir": "specs/epic-name",
  "epic_name": "epic-name",
  "started_at": "2026-01-17T10:30:00Z",
  "last_task": "T005",
  "last_linear_id": "FLO-123",
  "total_tasks": 15,
  "completed_before_compact": 4
}
```

## Recovery Procedure

1. Read `.agent/epic-auto-mode` for context
2. Read `{feature_dir}/.linear-mapping.json` for task mappings
3. Query Linear for current status of all tasks
4. Find next task with status `backlog` or `unstarted`
5. **Resume implementation immediately** - you are in auto-mode

**DO NOT** ask "should I continue?" - the state file IS the instruction.

## Cancellation

User can cancel via:
1. Remove state file: `rm .agent/epic-auto-mode`
2. Send "cancel" or "stop" message
3. Ctrl+C

## Completion Cleanup

**CRITICAL**: Remove state file **BEFORE** any output:
```bash
rm -f .agent/epic-auto-mode  # FIRST
```
Then output completion banner.
