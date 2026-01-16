# Beads Workflow Context

> **Context Recovery**: Run `bd prime` after compaction, clear, or new session
> Hooks auto-call this in Claude Code when .beads/ detected

## Source of Truth Hierarchy

```
Linear (team source of truth)
  ↓ bd linear sync --pull
Beads (.beads/ - local cache)
  ↓ git commits
Code + Documentation
```

**Key Principle**: Linear owns status, priorities, assignments. Beads is a local cache for offline work.

---

# SESSION START PROTOCOL

**At session start, run these checks:**

```bash
# 1. Sync from Linear (CRITICAL - get team updates first)
bd linear sync --pull

# 2. Check available work:
bd ready                        # Show issues ready to work
bd list --status=in_progress    # Find active work

# 3. If in_progress exists:
bd show <issue-id>              # Read notes from previous session
```

**Report to user**: "X items ready. [In-progress issue] left off at: [summary from notes]"

---

# ISSUE CLOSURE PROTOCOL (CRITICAL)

**When closing an issue, you MUST follow ALL steps to ensure Linear gets the closure context:**

```
1. Update Linear status:
   mcp__plugin_linear_linear__update_issue({id: "<LINEAR_ID>", state: "Done"})

2. Create Linear comment (MANDATORY - this preserves closure context for team):
   mcp__plugin_linear_linear__create_comment({
     issueId: "<LINEAR_ID>",
     body: "**Completed**: <summary of what was done>"
   })

3. Close in Beads:
   bd close <BEAD_ID> --reason "<summary>"

4. Sync to ensure consistency:
   bd linear sync --pull
```

**Why all steps?** `bd close --reason` stores context in Beads ONLY. Without step 2, team members viewing the Linear issue see no closure context.

---

# SESSION CLOSE PROTOCOL

**CRITICAL**: Before saying "done" or "complete", you MUST run this checklist:

```
[ ] 1. git status                  (check what changed)
[ ] 2. git add <files>             (stage code changes)
[ ] 3. bd sync --from-main         (pull beads updates from main)
[ ] 4. git commit -m "..."         (commit code changes)
[ ] 5. bd linear sync --pull       (sync latest Linear updates)
```

**Note:** This is an ephemeral branch (no upstream). Code is merged to main locally, not pushed.

---

## Two Sync Operations (IMPORTANT)

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `bd linear sync --pull` | Pull from Linear API | Session start, after team updates |
| `bd linear sync --push` | Push to Linear API | After local changes (status, priority) |
| `bd sync --from-main` | Git-based sync | Session end, branch collaboration |

**What syncs to Linear:**
- ✅ Status changes (open/in_progress/closed)
- ✅ Priority changes
- ✅ Assignments
- ❌ Comments/closure reasons (use MCP `create_comment`)

---

## Essential Commands

### Finding Work
- `bd ready` - Show issues ready to work (no blockers)
- `bd list --status=open` - All open issues
- `bd list --status=in_progress` - Your active work
- `bd show <id>` - Detailed issue view with dependencies

### Creating & Updating
- `bd create --title="..." --type=task|bug|feature --priority=2` - New issue
- `bd update <id> --status=in_progress` - Claim work
- `bd close <id> --reason="..."` - Close (but follow ISSUE CLOSURE PROTOCOL above!)

### Sync & Collaboration
- `bd linear sync --pull` - Pull from Linear (team updates)
- `bd linear sync --push` - Push to Linear (local changes)
- `bd sync --from-main` - Pull beads from main (git)
- `bd linear status` - Check Linear sync status

### Project Health
- `bd stats` - Project statistics
- `bd doctor` - Check for issues

---

## Common Workflows

**Starting work:**
```bash
bd linear sync --pull      # Get team updates
bd ready                   # Find available work
bd show <id>               # Review issue details
bd update <id> --status=in_progress  # Claim it
```

**Completing work (follow ISSUE CLOSURE PROTOCOL):**
```
1. mcp__plugin_linear_linear__update_issue({id: "FLO-XXX", state: "Done"})
2. mcp__plugin_linear_linear__create_comment({issueId: "FLO-XXX", body: "**Completed**: ..."})
3. bd close <bead-id> --reason="..."
4. bd linear sync --pull
5. git add . && git commit -m "..."
```

**Creating dependent work:**
```bash
bd create --title="Implement feature X" --type=feature
bd create --title="Write tests for X" --type=task
bd dep add <tests-id> <feature-id>  # Tests depend on Feature
```
