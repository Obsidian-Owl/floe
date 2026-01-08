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

**0a. Run Prerequisite Checks**

```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
PREREQ_SCRIPT="$REPO_ROOT/.specify/scripts/bash/check-prerequisites.sh"

# Run prerequisite checks (requires tasks.md for implementation)
PREREQ_RESULT=$("$PREREQ_SCRIPT" --json --require-tasks --include-tasks 2>&1)
PREREQ_EXIT=$?

if [ $PREREQ_EXIT -ne 0 ]; then
  echo "❌ ERROR: Prerequisites not met"
  echo "$PREREQ_RESULT"
  exit 1
fi

# Parse JSON output
FEATURE_DIR=$(echo "$PREREQ_RESULT" | jq -r '.FEATURE_DIR')
MAPPING_FILE="$FEATURE_DIR/.linear-mapping.json"

# Check Linear mapping exists
if [ ! -f "$MAPPING_FILE" ]; then
  echo "❌ ERROR: No Linear mapping found at $MAPPING_FILE"
  echo "   Run /speckit.taskstolinear first to create Linear issues"
  exit 1
fi

echo "✅ Prerequisites verified"
echo "   Feature: $FEATURE_DIR"
echo "   Mapping: $MAPPING_FILE"
```

**0b. Check Beads Installation (Optional)**

```bash
# Check if Beads CLI is available
if command -v bd &> /dev/null; then
  BEADS_AVAILABLE=true
  BEADS_VERSION=$(bd --version 2>/dev/null || echo "unknown")
  echo "✅ Beads CLI: $BEADS_VERSION"

  # Sync from Linear if Beads is available
  echo "🔄 Syncing from Linear (source of truth)..."
  bd linear sync --pull 2>/dev/null
  SYNC_EXIT=$?
  if [ $SYNC_EXIT -ne 0 ]; then
    echo "⚠️  Warning: Linear sync failed (network issue or not configured)"
    echo "   Proceeding with Linear MCP only"
  else
    echo "✅ Linear sync complete (Beads cache updated)"
  fi
else
  BEADS_AVAILABLE=false
  echo "ℹ️  Beads CLI not installed - using Linear MCP directly"
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
const { metadata, mappings } = mapping
// metadata contains: feature, project, project_id, created_at, total_issues
```

**Mapping format**: See [linear-workflow.md#mapping-file-format](../../../docs/guides/linear-workflow.md#mapping-file-format)

**1b. Query Linear for Issue Status (Primary Method)**

Use Linear MCP to get current status. Two approaches:

**Approach A: Query individual issues from mapping (RECOMMENDED for large projects)**

```javascript
// First, get team info and statuses to map status names to types
const team = mcp__plugin_linear_linear__get_team({ query: "floe" })
const statuses = mcp__plugin_linear_linear__list_issue_statuses({ team: team.id })

// Build status name → type lookup
const statusTypeMap = {}
for (const s of statuses) {
  statusTypeMap[s.name] = s.type  // e.g., "Backlog" → "backlog", "In Progress" → "started"
}

// For each task in mapping, query Linear for current status
// This avoids large list_issues response (can be 90k+ chars)
const statusMap = {}
for (const [taskId, taskInfo] of Object.entries(mappings)) {
  const issue = mcp__plugin_linear_linear__get_issue({ id: taskInfo.linear_id })
  statusMap[taskInfo.linear_id] = {
    state: issue.status,  // String like "Backlog", "In Progress", "Done"
    stateType: statusTypeMap[issue.status],
    assignee: issue.assignee
  }
}
```

**Approach B: Query all project issues (for small projects <50 issues)**

```javascript
// Query Linear directly for all issues in project
// WARNING: Response can be very large (90k+ chars for 76 issues)
const projectIssues = mcp__plugin_linear_linear__list_issues({
  project: metadata.project,
  limit: 250
})

// Build status map from Linear response
// NOTE: list_issues returns `status` as string (e.g., "Backlog"), not nested object
const statusMap = {}
for (const issue of projectIssues) {
  const statusName = issue.status  // String like "Backlog", "In Progress", "Done"
  statusMap[issue.id] = {
    state: statusName,
    stateType: statusTypeMap[statusName],  // 'unstarted', 'backlog', 'started', 'completed', 'canceled'
    assignee: issue.assignee
  }
}
```

**1c. Build Ready Tasks List**

```javascript
const readyTasks = []

// For each task in mapping, check Linear status
for (const [taskId, taskInfo] of Object.entries(mappings)) {
  const linearStatus = statusMap[taskInfo.linear_id]

  // Task is ready if: unstarted or backlog (not in progress, not completed)
  // Types: 'unstarted' (Todo), 'backlog' (Backlog), 'started', 'completed', 'canceled'
  if (linearStatus?.stateType === 'unstarted' || linearStatus?.stateType === 'backlog') {
    // Dependency checking is done in Step 2 via get_issue with includeRelations
    readyTasks.push({
      number: readyTasks.length + 1,
      taskId: taskId,
      linearId: taskInfo.linear_id,
      linearIdentifier: taskInfo.linear_identifier,
      title: taskInfo.title,
      url: `https://linear.app/issue/${taskInfo.linear_identifier}`
    })
  }
}

if (readyTasks.length === 0) {
  console.log("✅ No ready tasks - all tasks either in progress or completed!")
  console.log(`   View project: https://linear.app/project/${metadata.project}`)
  exit(0)
}
```

**1d. Display Ready Tasks**

```javascript
console.log(`📋 Ready Tasks (${readyTasks.length} available):\n`)

for (const task of readyTasks) {
  console.log(`  ${task.number}. [${task.taskId}] ${task.title}`)
  console.log(`     Linear: ${task.linearIdentifier}`)
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
  // Number selector (1-based index from displayed list)
  const index = parseInt(selector) - 1
  if (index < 0 || index >= readyTasks.length) {
    ERROR(`Invalid selection: ${selector}. Choose 1-${readyTasks.length}`)
  }
  selectedTask = readyTasks[index]
}
else if (selector.match(/^T\d+$/)) {
  // Task ID selector (e.g., T001, T042)
  selectedTask = readyTasks.find(t => t.taskId === selector)
  if (!selectedTask) {
    ERROR(`Task ${selector} not found in ready tasks`)
  }
}
else if (selector.match(/^FLO-\d+$/)) {
  // Linear identifier selector (e.g., FLO-33)
  selectedTask = readyTasks.find(t => t.linearIdentifier === selector)
  if (!selectedTask) {
    ERROR(`Linear issue ${selector} not found in ready tasks`)
  }
}
else {
  ERROR(`Invalid selector: ${selector}. Use number (1-${readyTasks.length}), Task ID (T###), or Linear ID (FLO-###)`)
}
```

**Selector types supported**:
- **Number**: `1`, `2`, `3` - position in displayed ready tasks list
- **Task ID**: `T001`, `T042` - from tasks.md
- **Linear ID**: `FLO-33`, `FLO-108` - Linear issue identifier

**Verify task not blocked** (optional - check Linear relations):

```javascript
// Query Linear for blocking relations
const issueDetails = mcp__plugin_linear_linear__get_issue({
  id: selectedTask.linearId,
  includeRelations: true
})

if (issueDetails.blockedBy && issueDetails.blockedBy.length > 0) {
  const blockers = issueDetails.blockedBy.map(b => b.identifier).join(", ")
  console.log(`❌ ERROR: Task ${selectedTask.taskId} is blocked by: ${blockers}`)
  console.log(`   Complete blockers first, or select a different task`)
  exit(1)
}
```

### Step 3: Claim Task

**Update Linear (source of truth)**:

```javascript
console.log(`🔄 Claiming task: ${selectedTask.linearIdentifier}...`)

// 1. Query team statuses to use correct status names (CRITICAL - never hardcode!)
// NOTE: Team name is "floe", not "floe-runtime"
const team = mcp__plugin_linear_linear__get_team({ query: "floe" })
const statuses = mcp__plugin_linear_linear__list_issue_statuses({ team: team.id })
const inProgressStatus = statuses.find(s => s.type === 'started' && s.name === 'In Progress')?.name || 'In Progress'

// 2. Update Linear (source of truth) with status and assignee
mcp__plugin_linear_linear__update_issue({
  id: selectedTask.linearId,
  state: inProgressStatus,
  assignee: "me"  // IMPORTANT: Take ownership of the task
})

console.log(`✅ Task claimed successfully`)
console.log(`   Status: ${inProgressStatus}`)
console.log(`   Assignee: You`)
console.log(`   Linear: ${selectedTask.linearIdentifier}`)
console.log()
```

**Pattern**: Linear is the source of truth. Update Linear directly via MCP. See [linear-workflow.md#architecture](../../../docs/guides/linear-workflow.md#architecture)

### Step 4: Show Task Context

```javascript
// Load task details from tasks.md
const tasksPath = `${FEATURE_DIR}/tasks.md`
const tasksContent = fs.readFileSync(tasksPath, 'utf8')

// Parse task details (phase, requirements, description)
// Look for: "- [ ] T001 [US1] Description" pattern
const taskDetails = parseTaskFromTasksMd(tasksContent, selectedTask.taskId)

console.log(`📋 Task Context:`)
console.log(`   Phase: ${taskDetails.phase}`)
console.log(`   User Story: ${taskDetails.userStory || "N/A"}`)
console.log(`   Parallel: ${taskDetails.hasParallelMarker ? "Yes (can run with other [P] tasks)" : "No"}`)
console.log(`   Description: ${taskDetails.fullDescription}`)
console.log()
console.log(`📍 Linear: ${selectedTask.url}`)
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

**Close task in Linear**:

**⚠️ MANDATORY: You MUST create a Linear comment when closing issues!**

Comments preserve closure context for team members viewing the Linear issue.

```javascript
console.log(`🔄 Closing task: ${selectedTask.linearIdentifier}...`)

// 1. Query statuses for correct Done status name (CRITICAL - never hardcode!)
const statuses = mcp__plugin_linear_linear__list_issue_statuses({ team: team.id })
const doneStatus = statuses.find(s => s.type === 'completed')?.name || 'Done'

// 2. Update Linear status (source of truth)
mcp__plugin_linear_linear__update_issue({
  id: selectedTask.linearId,
  state: doneStatus
})

// 3. MANDATORY: Create closure comment in Linear
//    This preserves context for team members!
const closureComment = buildClosureComment(selectedTask, implementationSummary, commitHash)
mcp__plugin_linear_linear__create_comment({
  issueId: selectedTask.linearId,
  body: closureComment
})

console.log(`✅ Task closed successfully`)
console.log(`   Status: ${doneStatus}`)
console.log(`   Comment: Added`)
console.log(`   Linear: ${selectedTask.linearIdentifier}`)
console.log()
```

**Closure Comment Template** (MANDATORY):
```javascript
function buildClosureComment(task, summary, commit) {
  return `**Completed**: ${task.taskId}

**Summary**: ${summary}

**Commit**: ${commit || 'See latest commit'}

**Files Changed**: [list key files]

---
*Closed via /speckit.implement*`
}
```

**Why this matters**: Linear is the source of truth for the team. Comments preserve closure context for team members reviewing progress.

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

```javascript
// Re-query Linear for remaining unstarted tasks
const remainingIssues = mcp__plugin_linear_linear__list_issues({
  project: metadata.project,
  state: "Todo",  // Or query by type: 'unstarted'
  limit: 10
})

const readyCount = remainingIssues.length

if (readyCount > 0) {
  console.log(`📋 ${readyCount} more tasks ready to implement`)
  console.log()

  const continueResponse = await askUser("Continue to next task?", ["Yes", "No"])

  if (continueResponse === "Yes") {
    console.log("♻️  Continuing to next task...")
    // Re-run /speckit.implement
  } else {
    console.log("✅ Session complete. Run /speckit.implement when ready to continue.")
  }
} else {
  console.log("✅ All tasks complete! 🎉")
  console.log()
  console.log(`Check Linear for project progress: https://linear.app/project/${metadata.project}`)
}
```

## Error Handling

**Common errors and solutions**:

| Error | Cause | Solution |
|-------|-------|----------|
| Prerequisites failed | Missing plan.md or tasks.md | Run `/speckit.plan` then `/speckit.tasks` |
| No Linear mapping | Haven't created Linear issues | Run `/speckit.taskstolinear` |
| Linear MCP unavailable | MCP not configured | Check `mcp__plugin_linear_linear__list_teams` |
| No ready tasks | All in progress or completed | Check Linear project view |
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
  - Best practices
  - Troubleshooting guide

**Related Commands**:
- [speckit.tasks](./speckit.tasks.md) - Generate tasks.md
- [speckit.taskstolinear](./speckit.taskstolinear.md) - Create Linear issues

**Configuration**:
- `.specify/memory/constitution.md` - Constitutional requirements (TDD, SOLID, atomic commits)
- `specs/{feature}/.linear-mapping.json` - Task to Linear issue mapping
