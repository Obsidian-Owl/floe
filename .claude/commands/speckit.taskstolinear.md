---
description: Convert tasks.md to Linear issues and reconcile completed work bidirectionally.
tools: ['linear/linear-mcp/issue_write']
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This command creates Linear issues from tasks.md with Epic organization, requirements traceability, and bidirectional reconciliation.

**What it does**:
1. Validates tasks.md (duplicates, TDD ordering)
2. Converts tasks → Linear issues (if not already done)
3. Reconciles bidirectionally (Linear ↔ tasks.md)
4. Tags with Epic labels (auto-discovered from feature dir)
5. Syncs to Beads cache

**Detailed patterns**: [Linear Workflow Guide - Task Creation & Reconciliation](../../../docs/guides/linear-workflow.md#task-creation--reconciliation)

## Execution Algorithm

### Step 1: Setup & Validation

Run startup checks from repo root:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
STARTUP_SCRIPT="$REPO_ROOT/.specify/scripts/bash/check-prerequisites.sh"

STARTUP_RESULT=$("$STARTUP_SCRIPT" --json --require-tasks --include-tasks)
STARTUP_EXIT=$?

if [ $STARTUP_EXIT -ne 0 ]; then
  echo "$STARTUP_RESULT"
  exit $STARTUP_EXIT
fi

# Parse JSON output
FEATURE_DIR=$(echo "$STARTUP_RESULT" | tail -1 | jq -r '.feature_dir')
```

**Verify Linear MCP**:
```bash
# Test Linear connection
mcp__plugin_linear_linear__list_teams

# Get team ID from Beads config
TEAM_ID=$(bd config list | grep linear.team_id | awk '{print $3}')
```

### Step 2: Determine Epic Label (Dynamic Discovery)

**Extract from feature directory path**:

```javascript
// Example: /path/to/specs/epic-3-plugin-interface-foundation/
// Extract: "epic-3"

featurePath = FEATURE_DIR
epicMatch = featurePath.match(/epic-(\d+)/)

if (epicMatch) {
  epicLabel = `epic-${epicMatch[1]}`
} else {
  // Fallback: Check spec.md
  specContent = readFile(`${FEATURE_DIR}/spec.md`)
  epicMatch = specContent.match(/Epic:\s*(\d+)/)
  epicLabel = epicMatch ? `epic-${epicMatch[1]}` : null
}

if (!epicLabel) {
  ERROR("Cannot determine Epic label from feature directory")
}
```

**Validate epic label exists in Linear**:

```javascript
// Query Linear for all issue labels
labels = mcp__plugin_linear_linear__list_issue_labels({team: TEAM_ID})

// Check if epic label exists
epicExists = labels.find(l => l.name === epicLabel)

if (!epicExists) {
  ERROR(`Epic label '${epicLabel}' not found in Linear.\n` +
        `Create it with: mcp__plugin_linear_linear__create_issue_label({` +
        `team: "${TEAM_ID}", name: "${epicLabel}", color: "#3B82F6"})`)
}
```

**No hardcoded epic list** - dynamically discovers and validates against Linear.

### Step 3: Load Mapping File

```javascript
mappingPath = `${FEATURE_DIR}/.linear-mapping.json`

if (fs.existsSync(mappingPath)) {
  mapping = JSON.parse(fs.readFileSync(mappingPath, 'utf8'))
} else {
  mapping = {
    feature: path.basename(FEATURE_DIR),
    epic_label: epicLabel,
    created_at: now(),
    last_sync: null,
    mappings: {}
  }
}
```

**Mapping structure**: See [Linear Workflow Guide - Mapping File Format](../../../docs/guides/linear-workflow.md#mapping-file-format)

### Step 4: Parse tasks.md & Validate

**Extract tasks with format**:
```
- [x] T001 [P] [REQ-042, 003#FR-015] Description with file path
- [ ] T002 [REQ-043] Another task
```

**Build task list**:
```javascript
tasks = []
seenTaskIds = {}
duplicates = []

// Parse each line matching task pattern
taskPattern = /^-\s+\[([ x])\]\s+(T\d+)\s+(?:\[P\]\s+)?(?:\[(.*?)\]\s+)?(.+)$/

for (line in tasksContent.split('\n')) {
  match = line.match(taskPattern)
  if (match) {
    taskId = match[2]

    // Duplicate detection
    if (seenTaskIds[taskId]) {
      duplicates.push({taskId, firstLine: seenTaskIds[taskId], currentLine: lineNum})
    }
    seenTaskIds[taskId] = lineNum

    tasks.push({
      id: taskId,
      completed: match[1] === 'x',
      parallel: line.includes('[P]'),
      requirements: match[3] ? match[3].split(',').map(r => r.trim()) : [],
      description: match[4].trim(),
      phase: currentPhase,
      line: lineNum
    })
  }
}

if (duplicates.length > 0) {
  ERROR("Duplicate task IDs:\n" +
        duplicates.map(d => `  ${d.taskId}: line ${d.firstLine} and ${d.currentLine}`).join('\n'))
}
```

**TDD Validation** (warn only):
```javascript
for (task in tasks) {
  if (task.description.match(/implement|create/i)) {
    prevTaskId = `T${String(parseInt(task.id.slice(1)) - 1).padStart(3, '0')}`
    prevTask = tasks.find(t => t.id === prevTaskId)

    if (prevTask && !prevTask.description.match(/test/i)) {
      WARN(`TDD: ${task.id} (impl) should have ${prevTaskId} (test) before it`)
    }
  }
}
```

### Step 5: Reconcile with Linear

**Query existing issues**:
```javascript
linearIssues = mcp__plugin_linear_linear__list_issues({
  team: TEAM_ID,
  label: epicLabel,
  includeArchived: false
})

// Build reverse map: Linear ID → Task ID
linearToTaskMap = {}
for (taskId in mapping.mappings) {
  linearId = mapping.mappings[taskId].linear_id
  if (linearId) linearToTaskMap[linearId] = taskId
}

// Update mapping from Linear status
tasksToMarkComplete = []
for (issue in linearIssues) {
  taskId = linearToTaskMap[issue.id]
  if (taskId && mapping.mappings[taskId]) {
    mapping.mappings[taskId].status = issue.state.name

    if (issue.state.name === "Done" && !tasks.find(t => t.id === taskId).completed) {
      tasksToMarkComplete.push(taskId)
    }
  }
}
```

### Step 6: Create Linear Issues

**Unified issue creation pattern**:

```javascript
createdIssues = []

for (task in tasks) {
  // Skip if already exists
  if (mapping.mappings[task.id]?.linear_id) continue

  // Prepare issue
  title = `${task.id}: ${truncate(task.description, 80 - task.id.length - 2)}`

  description = buildIssueDescription(task, epicLabel, FEATURE_DIR)

  priority = extractPriority(task.description)  // [P0]=1, [P1]=2, default=2, [P4]=4

  state = task.completed ? "Done" : "Todo"

  // Create in Linear
  linearIssue = mcp__plugin_linear_linear__create_issue({
    team: TEAM_ID,
    title: title,
    description: description,
    labels: [epicLabel],
    priority: priority,
    state: state
  })

  // Store mapping
  mapping.mappings[task.id] = {
    linear_id: linearIssue.id,
    linear_identifier: linearIssue.identifier,
    status: linearIssue.state.name,
    title: title,
    url: linearIssue.url,
    created_at: now()
  }

  createdIssues.push({
    taskId: task.id,
    linearId: linearIssue.identifier,
    url: linearIssue.url
  })
}
```

**Helper: buildIssueDescription**:
```javascript
function buildIssueDescription(task, epicLabel, featureDir) {
  return `**Task ID**: ${task.id}
**Epic**: ${epicLabel}
**Phase**: ${task.phase}
**Parallel**: ${task.parallel ? "Yes" : "No"}

**Requirements Mapping**:
${task.requirements.length > 0 ?
  task.requirements.map(r => `- Replaces: ${r}`).join('\n') :
  "- No requirements mapping"}

**Description**:
${task.description}

---

**Source**: tasks.md from feature ${path.basename(featureDir)}
**Created by**: /speckit.taskstolinear`
}
```

**Issue creation details**: See [Linear Workflow Guide - Issue Creation Pattern](../../../docs/guides/linear-workflow.md#issue-creation-pattern)

### Step 7: Handle Dependencies

**Automatic phase dependencies**:
```javascript
// Foundational phase blocks all User Story phases
if (task.phase.includes("Foundational")) {
  blocksTaskIds = tasks
    .filter(t => t.phase.includes("User Story"))
    .map(t => t.id)
}

// Extract explicit dependencies: "Depends on T001"
depMatches = task.description.match(/Depends on (T\d+)/g)
if (depMatches) {
  blockedByTaskIds = depMatches.map(m => m.match(/T\d+/)[0])
}

// Update Linear relations
if (blockedByTaskIds.length > 0) {
  mcp__plugin_linear_linear__update_issue({
    id: mapping.mappings[task.id].linear_id,
    blockedBy: blockedByTaskIds.map(tid => mapping.mappings[tid].linear_id)
  })
}
```

**Dependency rules**: See [Linear Workflow Guide - Dependency Handling](../../../docs/guides/linear-workflow.md#dependency-handling)

### Step 8: Update tasks.md

**Mark tasks complete from Linear**:
```javascript
if (tasksToMarkComplete.length > 0) {
  tasksContent = readFile(`${FEATURE_DIR}/tasks.md`)

  for (taskId in tasksToMarkComplete) {
    // Update checkbox: [ ] → [x]
    tasksContent = tasksContent.replace(
      new RegExp(`- \\[ \\] ${taskId}\\b`),
      `- [x] ${taskId}`
    )
  }

  writeFile(`${FEATURE_DIR}/tasks.md`, tasksContent)
}
```

### Step 9: Save Mapping & Sync

**Save mapping**:
```javascript
mapping.last_sync = now()
fs.writeFile(mappingPath, JSON.stringify(mapping, null, 2))
```

**Sync to Beads**:
```bash
# Pull Linear issues → Beads cache (Linear API sync)
bd linear sync --pull
```

**⚠️ Sync Operation Clarification**:
- `bd linear sync --pull`: Linear API sync (Linear → Beads cache)
- `bd sync`: Git-based sync for branch collaboration (not needed here)

**Note on Closure Context**: When closing issues via `/speckit.implement`, you must manually create Linear comments via `mcp__plugin_linear_linear__create_comment` to preserve closure context. The `bd close --reason` text is stored in Beads only. See [speckit.implement.md](./speckit.implement.md) Step 6 for details.

### Step 10: Run Audit

**Orphan detection, constitutional compliance, dependency validation**:

See [Linear Workflow Guide - Audit Procedures](../../../docs/guides/linear-workflow.md#audit-procedures)

```javascript
// Check for orphaned Linear issues
orphans = findOrphans(linearIssues, mapping)
if (orphans.length > 0) {
  WARN(`⚠️ Orphaned Linear issues: ${orphans.map(o => o.identifier).join(', ')}`)
}

// Validate constitutional compliance
violations = checkConstitutionalCompliance(tasks)
if (violations.length > 0) {
  WARN(`⚠️ Constitutional violations detected in ${violations.length} tasks`)
}

// Validate dependencies
invalidDeps = validateDependencies(tasks)
if (invalidDeps.length > 0) {
  ERROR(`❌ Invalid dependencies detected`)
}
```

### Step 11: Report Summary

```javascript
console.log(`✅ /speckit.taskstolinear Complete

📊 Summary:
- Epic: ${epicLabel}
- Total tasks in tasks.md: ${tasks.length}
- Tasks already completed: ${tasks.filter(t => t.completed).length}
- Linear issues created: ${createdIssues.length}
- Tasks marked complete from Linear: ${tasksToMarkComplete.length}

📋 Linear Issues Created:
${createdIssues.map(i => `- ${i.linearId}: ${i.taskId} → ${i.url}`).join('\n')}

📁 Files Updated:
- ${FEATURE_DIR}/tasks.md ${tasksToMarkComplete.length > 0 ? '(' + tasksToMarkComplete.length + ' tasks marked complete)' : ''}
- ${FEATURE_DIR}/.linear-mapping.json (mapping saved)

🎯 Next Steps:
1. Run \`bd linear sync --pull\` to sync to Beads cache
2. Run \`bd ready\` to see available work
3. Use \`/speckit.implement\` to start implementation

📎 Traceability:
- Linear label: ${epicLabel}
- Epic URL: ${mapping.epic_url || `https://linear.app/floe-runtime/label/${epicLabel}`}
- Requirements mapping preserved in issue descriptions`)
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Epic label not found | Directory doesn't match `epic-N` pattern | Check feature directory name or spec.md |
| Epic label missing in Linear | Label not created yet | Create with `mcp__plugin_linear_linear__create_issue_label` |
| Linear MCP unavailable | MCP not configured | Verify API key: `bd config set linear.api_key <key>` |
| Duplicate task IDs | Same task ID appears multiple times | Fix duplicates in tasks.md |
| Invalid dependencies | Task depends on non-existent task | Verify all dependency task IDs exist |
| Missing team ID | Beads config incomplete | Set team ID: `bd config set linear.team_id <uuid>` |

**Full troubleshooting**: [Linear Workflow Guide - Troubleshooting](../../../docs/guides/linear-workflow.md#troubleshooting)

## Exit Codes

- **0**: Success (issues created/reconciled)
- **1**: Error (validation failed, Linear error, duplicate IDs)

## References

- **Linear Workflow Guide**: [docs/guides/linear-workflow.md](../../../docs/guides/linear-workflow.md)
  - Mapping file format
  - Issue creation patterns
  - Audit procedures
  - Troubleshooting
- **Commands**:
  - [speckit.tasks](./speckit.tasks.md) - Generate tasks.md
  - [speckit.implement](./speckit.implement.md) - Execute tasks
- **Beads Configuration**: `.beads/config.yaml`
- **ADR**: [ADR-0042: Linear + Beads Traceability](../../../docs/adr/0042-linear-beads-traceability.md)
