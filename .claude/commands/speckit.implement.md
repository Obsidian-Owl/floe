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

This command bridges SpecKit planning with Linear/Beads execution tracking, enabling incremental task-by-task implementation.

**Architecture**: Linear-first (see [Linear Workflow Guide](../../../docs/guides/linear-workflow.md))
- Linear is source of truth for issue status, assignments, priorities
- Beads is local cache synced from Linear via `bd linear sync`
- tasks.md is planning artifact that generates Linear issues

**Modes**:
1. **Without arguments**: Automatically implement first ready task
2. **With selector**: Implement specific task (number, Task ID, Linear ID, identifier, or Beads ID)

**Full workflow examples**: [docs/guides/linear-workflow.md#workflow-examples](../../../docs/guides/linear-workflow.md#workflow-examples)

## Execution Algorithm

### Step 0: Startup & Sync

**0a. Run Startup Checks**

```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
STARTUP_SCRIPT="$REPO_ROOT/.specify/scripts/bash/startup-checks.sh"

if [ ! -f "$STARTUP_SCRIPT" ]; then
  echo "❌ ERROR: Startup checks script not found"
  exit 1
fi

# Run checks: Beads installed, issues exist, Linear MCP available, feature dir exists
STARTUP_RESULT=$("$STARTUP_SCRIPT")
STARTUP_EXIT=$?

if [ $STARTUP_EXIT -ne 0 ]; then
  echo "$STARTUP_RESULT"
  exit $STARTUP_EXIT
fi

# Parse JSON output
BEADS_VERSION=$(echo "$STARTUP_RESULT" | tail -1 | jq -r '.beads_version')
ISSUE_COUNT=$(echo "$STARTUP_RESULT" | tail -1 | jq -r '.issue_count')
FEATURE_DIR=$(echo "$STARTUP_RESULT" | tail -1 | jq -r '.feature_dir')
MAPPING_FILE=$(echo "$STARTUP_RESULT" | tail -1 | jq -r '.mapping_file')
```

**0b. Sync from Linear (CRITICAL)**

```bash
echo "🔄 Syncing from Linear (source of truth)..."

bd linear sync --pull

SYNC_EXIT=$?
if [ $SYNC_EXIT -ne 0 ]; then
  echo "⚠️  Warning: Linear sync failed (network issue or Linear down)"
  echo "   Proceeding with cached Beads data"
else
  echo "✅ Linear sync complete (Beads cache updated)"
fi
```

**Why sync first**: Linear may have updates from team members. Ensures working with latest status.

### Step 1: Load Mapping & Find Ready Tasks

**1a. Load Linear Mapping**

```javascript
const mappingPath = `${FEATURE_DIR}/.linear-mapping.json`

if (!fs.existsSync(mappingPath)) {
  ERROR("No Linear mapping found. Run /speckit.taskstolinear first.")
}

const mapping = JSON.parse(fs.readFileSync(mappingPath, 'utf8'))
const { feature, epic_label, mappings } = mapping
```

**Mapping format**: See [linear-workflow.md#mapping-file-format](../../../docs/guides/linear-workflow.md#mapping-file-format)

**1b. Query Beads for Ready Tasks**

```bash
# Get all open issues for this feature
BEADS_READY=$(bd ready 2>/dev/null)

# Get all issue details
BEADS_LIST=$(bd list --status=open --format=json 2>/dev/null)
```

**1c. Build Ready Tasks List**

```javascript
const readyTasks = []

// For each task in mapping
for (const [taskId, taskInfo] of Object.entries(mappings)) {
  const beadId = taskInfo.bead_id

  // Check if task is ready (not blocked, not in progress, not completed)
  const beadStatus = getBeadStatus(beadId, BEADS_LIST)

  if (beadStatus === 'open') {
    // Check dependencies - task is ready if no blockers
    const isBlocked = checkIfBlocked(beadId, BEADS_READY)

    if (!isBlocked) {
      readyTasks.push({
        number: readyTasks.length + 1,
        taskId: taskId,
        beadId: beadId,
        linearId: taskInfo.linear_id,
        linearIdentifier: taskInfo.linear_identifier,
        title: taskInfo.title,
        status: taskInfo.status,
        url: taskInfo.url
      })
    }
  }
}

if (readyTasks.length === 0) {
  // No ready tasks - show guidance
  showNoReadyTasksMessage(epic_label, mapping.epic_url)
  exit(0)
}
```

**1d. Display Ready Tasks**

```javascript
console.log(`📋 Ready Tasks (${readyTasks.length} available):\n`)

for (const task of readyTasks) {
  console.log(`  ${task.number}. [${task.taskId}] ${task.title}`)
  console.log(`     Linear: ${task.linearIdentifier} (${task.url})`)
  console.log(`     Beads: ${task.beadId}`)
  console.log()
}
```

### Step 2: Task Selection

**Parse selector from $ARGUMENTS**:

```javascript
const selector = $ARGUMENTS.trim().split(/\s+/)[0] || ""  // First token

let selectedTask = null

if (selector === "") {
  // No argument → auto-select first ready task
  selectedTask = readyTasks[0]
  console.log(`🎯 Auto-selected: ${selectedTask.taskId} - ${selectedTask.title}\n`)
}
else if (selector.match(/^\d+$/)) {
  // Number selector (1-based index)
  const index = parseInt(selector) - 1
  if (index < 0 || index >= readyTasks.length) {
    ERROR(`Invalid selection: ${selector}. Choose 1-${readyTasks.length}`)
  }
  selectedTask = readyTasks[index]
}
else if (selector.match(/^T\d+$/)) {
  // Task ID selector
  selectedTask = readyTasks.find(t => t.taskId === selector)
  if (!selectedTask) {
    ERROR(`Task ${selector} not found in ready tasks`)
  }
}
else if (selector.match(/^FLO-\d+$/)) {
  // Linear ID selector
  selectedTask = readyTasks.find(t => t.linearId === selector)
  if (!selectedTask) {
    ERROR(`Linear issue ${selector} not found in ready tasks`)
  }
}
else if (selector.match(/^epic-\d+-[a-z0-9]+$/)) {
  // Linear identifier selector
  selectedTask = readyTasks.find(t => t.linearIdentifier === selector)
  if (!selectedTask) {
    ERROR(`Linear identifier ${selector} not found in ready tasks`)
  }
}
else if (selector.match(/^floe-runtime-[a-zA-Z0-9]+$/)) {
  // Beads ID selector
  selectedTask = readyTasks.find(t => t.beadId === selector)
  if (!selectedTask) {
    ERROR(`Beads issue ${selector} not found in ready tasks`)
  }
}
else {
  ERROR(`Invalid selector: ${selector}. Use number, Task ID (T###), Linear ID (FLO-###), Linear identifier (epic-#-xxx), or Beads ID (floe-runtime-xxx)`)
}
```

**Selector types**: See [linear-workflow.md#task-selection-methods](../../../docs/guides/linear-workflow.md#task-selection-methods)

**Verify task not blocked**:

```bash
# Double-check task isn't blocked (Linear may have updated)
BLOCKED_CHECK=$(bd show ${selectedTask.beadId} | grep -i "blocked by")

if [ ! -z "$BLOCKED_CHECK" ]; then
  echo "❌ ERROR: Task ${selectedTask.taskId} is blocked"
  echo "$BLOCKED_CHECK"
  echo ""
  echo "View in Linear: ${selectedTask.url}"
  exit 1
fi
```

### Step 3: Claim Task

**Update Linear first, then Beads**:

```bash
echo "🔄 Claiming task: ${selectedTask.linearIdentifier}..."

# 1. Update Linear (source of truth)
mcp__plugin_linear_linear__update_issue({
  id: "${selectedTask.linearId}",
  state: "In Progress"
})

# 2. Update Beads (cache)
bd update ${selectedTask.beadId} --status=in_progress

# 3. Sync to ensure consistency
bd linear sync --pull

echo "✅ Task claimed successfully"
echo ""
```

**Pattern**: Always Linear first, then Beads, then sync. See [linear-workflow.md#architecture](../../../docs/guides/linear-workflow.md#architecture)

### Step 4: Show Task Context

```javascript
// Load task details from tasks.md
const tasksPath = `${FEATURE_DIR}/tasks.md`
const tasksContent = fs.readFileSync(tasksPath, 'utf8')

// Parse task details (phase, requirements, description)
const taskDetails = parseTaskFromTasksMd(tasksContent, selectedTask.taskId)

console.log(`📋 Task Context:`)
console.log(`   Phase: ${taskDetails.phase}`)
console.log(`   Requirements: ${taskDetails.requirements.join(", ") || "N/A"}`)
console.log(`   Parallel: ${taskDetails.hasParallelMarker ? "Yes" : "No"}`)
console.log(`   Description: ${taskDetails.fullDescription}`)
console.log()
console.log(`📍 Linear: ${selectedTask.url}`)
console.log(`📍 Beads: ${selectedTask.beadId}`)
console.log()
```

**Requirements traceability**: See [linear-workflow.md#traceability-chain](../../../docs/guides/linear-workflow.md#traceability-chain)

### Step 5: Execute Implementation

**Load constitution and spec**:

```javascript
const constitutionPath = `${REPO_ROOT}/.specify/memory/constitution.md`
const constitution = fs.readFileSync(constitutionPath, 'utf8')

const specPath = `${FEATURE_DIR}/spec.md`
const spec = fs.readFileSync(specPath, 'utf8')

const planPath = `${FEATURE_DIR}/plan.md`
const plan = fs.readFileSync(planPath, 'utf8')
```

**Implement task following constitution**:

```javascript
console.log(`🛠️  Implementing task: ${selectedTask.title}`)
console.log()

// CONSTITUTIONAL REQUIREMENTS (enforced):
// 1. TDD: Write tests before implementation
// 2. SOLID: Single responsibility per file
// 3. Atomic commits: 300-600 LOC max
// 4. No skipped tests: pytest.skip() forbidden
//
// See: .specify/memory/constitution.md

// Implement the task
// - Follow TDD: tests first
// - Follow SOLID: single responsibility
// - Follow task description from tasks.md
// - Update relevant files
// - Run tests to verify

// Your implementation here...
```

**Constitutional requirements**: See [linear-workflow.md#best-practices](../../../docs/guides/linear-workflow.md#best-practices) and `.specify/memory/constitution.md`

### Step 6: Verify & Close Task

**Ask user if task is complete**:

```javascript
const isComplete = await askUser("Is this task complete? (yes/wait)")

if (isComplete === "wait") {
  console.log("⏸️  Task remains in progress")
  console.log("   Run /speckit.implement again when ready to close")
  exit(2)  // Warning exit code
}
```

**Close task (Linear first, then Beads)**:

```bash
echo "🔄 Closing task: ${selectedTask.linearIdentifier}..."

# 1. Close Linear (source of truth)
mcp__plugin_linear_linear__update_issue({
  id: "${selectedTask.linearId}",
  state: "Done"
})

# 2. Close Beads (cache) with reason
bd close ${selectedTask.beadId} --reason "Implemented and verified"

# 3. IMPORTANT: Add closure comment to Linear
# bd close --reason does NOT sync to Linear automatically
mcp__plugin_linear_linear__create_comment({
  issueId: "${selectedTask.linearId}",
  body: "**Completed**: Implemented and verified (${selectedTask.taskId})"
})

# 4. Sync to ensure consistency
bd linear sync --pull

# 5. Verify closure
status=$(bd show ${selectedTask.beadId} | grep "Status:" | awk '{print $2}')
if [ "$status" = "closed" ]; then
  echo "✅ Task closed successfully"
  echo "   Linear: Done (comment added)"
  echo "   Beads: closed (synced)"
  echo "   URL: ${selectedTask.url}"
else
  echo "⚠️  Warning: Task may not have closed properly"
  echo "   Run: bd linear sync --pull"
fi

echo ""
```

**⚠️ Comment Syncing Limitation**: `bd close --reason` stores the reason in Beads but does NOT create a Linear comment. You must manually create the comment via `mcp__plugin_linear_linear__create_comment` to preserve closure context in Linear.

### Step 7: Commit Changes

**Generate commit message with Linear identifier**:

```bash
# Determine commit type from task description
COMMIT_TYPE="feat"  # or fix, refactor, test, docs, etc.

# Include task ID and Linear identifier
COMMIT_MSG="${COMMIT_TYPE}(scope): ${selectedTask.title} (${selectedTask.taskId}, ${selectedTask.linearIdentifier})"

# Example output:
# feat(plugin-api): add PluginMetadata ABC (T001, epic-3-abc123)
```

**Commit with constitutional validation**:

```bash
git add .

git commit -m "${COMMIT_MSG}"

COMMIT_EXIT=$?

if [ $COMMIT_EXIT -ne 0 ]; then
  echo "❌ ERROR: Commit failed (likely pre-commit hook rejection)"
  echo ""
  echo "Common causes:"
  echo "  - TDD violation (tests not written first)"
  echo "  - SOLID violation (too many responsibilities in one file)"
  echo "  - Atomic commit violation (>600 LOC changed)"
  echo "  - Skipped tests detected"
  echo ""
  echo "Fix violations and run /speckit.implement again"
  exit 1
fi

echo "✅ Changes committed: ${COMMIT_MSG}"
echo ""
```

**Pre-commit hooks enforce constitution**: Tests before code, SOLID, atomic commits, no skips.

### Step 8: Auto-Continue

**Check for more ready tasks**:

```bash
echo "🔄 Syncing from Linear before checking for next task..."
bd linear sync --pull

# Re-query ready tasks
READY_COUNT=$(bd ready | wc -l)

if [ $READY_COUNT -gt 0 ]; then
  echo "📋 ${READY_COUNT} more tasks ready to implement"
  echo ""
  echo "Continue? (yes/no)"
  read CONTINUE_RESPONSE

  if [ "$CONTINUE_RESPONSE" = "yes" ]; then
    echo "♻️  Continuing to next task..."
    exec /speckit.implement  # Recursive call
  else
    echo "✅ Session complete. Run /speckit.implement when ready to continue."
  fi
else
  echo "✅ All tasks complete! 🎉"
  echo ""
  echo "Check Linear for Epic progress: ${mapping.epic_url}"
fi
```

## Error Handling

**Common errors and solutions**:

| Error | Cause | Solution |
|-------|-------|----------|
| Prerequisites failed | Missing spec.md or tasks.md | Run `/speckit.tasks` |
| No Linear issues | Haven't created Linear issues | Run `/speckit.taskstolinear` |
| Linear MCP unavailable | MCP not configured | Check `mcp__plugin_linear_linear__list_teams` |
| No ready tasks | All blocked or completed | Check `bd blocked` or Linear app |
| Task blocked | Dependency not complete | Work on blocker first, or select different task |
| Commit rejected | Constitutional violation | Fix TDD/SOLID/atomic/no-skip violation |

**Full troubleshooting**: [docs/guides/linear-workflow.md#troubleshooting](../../../docs/guides/linear-workflow.md#troubleshooting)

## Exit Codes

- **0**: Success (task implemented and closed)
- **1**: Error (prerequisites failed, task not found, commit rejected)
- **2**: Warning (task implemented but not closed, user said "wait")

## References

**Essential Reading**:
- **Linear Workflow Guide**: [docs/guides/linear-workflow.md](../../../docs/guides/linear-workflow.md)
  - Architecture explanation
  - Traceability chain details
  - Workflow examples
  - Parallel workflow patterns
  - Best practices
  - Troubleshooting guide

**Related Commands**:
- [speckit.tasks](./speckit.tasks.md) - Generate tasks.md
- [speckit.taskstolinear](./speckit.taskstolinear.md) - Create Linear issues

**Configuration**:
- `.beads/config.yaml` - Beads + Linear integration config
- `.specify/memory/constitution.md` - Constitutional requirements (TDD, SOLID, atomic commits)
- `docs/plan/COMBINED-REQUIREMENTS.md` - Requirements for traceability

**ADR**:
- [ADR-0042: Linear + Beads Traceability](../../../docs/adr/0042-linear-beads-traceability.md)
