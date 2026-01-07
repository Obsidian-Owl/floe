# Linear-First Workflow Guide

**For**: Developers and agents working with floe
**Purpose**: Complete guide to Linear + Beads issue tracking workflow
**Related**: [ADR-0042: Linear + Beads Traceability](../architecture/adr/0042-linear-beads-traceability.md)

---

## Quick Reference

**Workflow:**
```bash
# 1. Sync from Linear (source of truth)
bd linear sync --pull

# 2. See available work
bd ready

# 3. Implement a task
/speckit.implement

# 4. Sync back to Linear
bd linear sync --pull

# 5. Check Linear for team progress
# Visit: https://linear.app/floe
```

**Core Principle**: Linear is the source of truth. Beads is the local cache.

---

## Architecture

### Linear-First Design

This project uses a **Linear-first** architecture where Linear is the source of truth and Beads provides local caching for offline work.

**Linear (Source of Truth)**:
- Issue status, assignments, priorities stored in Linear
- Linear MCP provides real-time status via API
- All status updates happen in Linear first
- Team collaboration via Linear web/app
- Epic organization via Linear labels (epic-1 through epic-9)

**Beads (Local Cache)**:
- Cached copy of Linear issues for offline work
- Synced via `bd linear sync --pull`
- Enables local queries (`bd ready`, `bd show`, `bd list`)
- Git-backed storage (`.beads/issues.jsonl`)
- Automatically synced by SpecKit commands

**Workflow Pattern:**
```
Linear (source)
  → bd sync --pull
  → Beads (cache)
  → Implementation
  → Update Linear
  → Sync back
```

**Benefits:**
- **Team Collaboration**: Shared source of truth in Linear
- **Offline Work**: Beads cache enables local queries
- **Dependency Tracking**: Linear relations (blocks, blockedBy)
- **Epic Organization**: Linear labels for visual grouping
- **Full Traceability**: Requirements → Linear → Beads → Git → Tests

---

## Traceability Chain

This workflow maintains full traceability from original requirements through to tests:

```
Combined Requirements (REQ-042 or 003#FR-015)
  ↓
Tasks (T001 in specs/epic-3/tasks.md)
  ↓
Linear Issues (FLO-123, epic-3-abc123)
  ↓
Beads Cache (floe-abc123)
  ↓
Git Commits (feat(plugin-api): add PluginMetadata ABC (T001, epic-3-abc123))
  ↓
Tests (@pytest.mark.requirement("REQ-042"))
```

### How It Works

**1. Requirements** (embedded in ADRs and specs):
- Requirements may use REQ-XXX or spec#FR-XXX format (e.g., 003#FR-015)
- ADRs document architectural decisions and requirements
- Feature specs in `specs/` directory detail implementation requirements

**2. Tasks Generation** (`/speckit.tasks`):
- Creates tasks.md with requirements references
- Example: `Requirements: REQ-042, 003#FR-015`

**3. Linear Issue Creation** (`/speckit.taskstolinear`):
- Creates Linear issues with Epic labels (epic-1 to epic-9)
- Includes requirements in issue description
- Example: Linear issue "Add PluginMetadata ABC" → Description includes "Requirements: REQ-042 (replaces 001#FR-002)"
- Maps dependencies via Linear relations (blocks, blockedBy)

**4. Beads Sync** (`bd linear sync --pull`):
- Syncs Linear issues to Beads cache
- Preserves Linear ID, identifier, URL in mapping
- Mapping stored in `.linear-mapping.json`

**5. Implementation** (`/speckit.implement`):
- Commits include task ID and Linear identifier
- Example: `feat(plugin-api): add PluginMetadata ABC (T001, epic-3-abc123)`

**6. Test Traceability** (`@pytest.mark.requirement`):
- Tests marked with requirement IDs
- Example: `@pytest.mark.requirement("REQ-042")` or `@pytest.mark.requirement("003#FR-015")`

### Querying Traceability

```bash
# Find requirement details in ADRs
grep -r "REQ-" docs/architecture/adr/

# Find all tasks for a requirement (if tasks.md has requirement markers)
grep "REQ-042" specs/*/tasks.md

# Find Linear issues for a requirement
# Use Linear search: "REQ-042"

# Find git commits for a task
git log --grep="T001"

# Find git commits for a Linear issue
git log --grep="epic-3-abc123"

# Find tests for a requirement
grep -r "@pytest.mark.requirement(\"REQ-042\")" packages/*/tests/
```

### Audit Compliance

The full chain enables auditing:
- Requirement (REQ-XXX or spec#FR-XXX) → Task → Linear issue → Beads issue → Commit → Test
- Every requirement has a test (via @pytest.mark.requirement)
- Every commit traceable to requirement (via Linear identifier in commit message)
- Every Linear issue traceable to Epic (via epic-N label)
- Requirements documented in ADRs and feature specs

---

## Workflow Examples

### Basic Implementation Flow

```bash
# 1. Generate tasks from plan
/speckit.tasks

# 2. Create Linear issues from tasks (with Epic labels and requirements)
/speckit.taskstolinear
# Creates Linear issues with epic-1 to epic-9 labels
# Syncs to Beads via bd linear sync --pull

# 3. Show what's ready to work on
/speckit.implement
# Output: Shows tasks 1-3 are ready (synced from Linear)

# 4. Implement first task (auto-mode)
/speckit.implement
# Syncs from Linear, implements first ready task, updates Linear → Beads

# 5. Implement specific task by Linear ID
/speckit.implement FLO-123
# Implements Linear issue FLO-123

# 6. Implement specific task by Linear identifier
/speckit.implement epic-3-abc123
# Implements task with Linear identifier epic-3-abc123

# 7. Implement by task ID
/speckit.implement T010
# Implements T010 by task ID

# 8. Check what's ready
/speckit.implement
# Syncs from Linear, shows remaining ready tasks

# 9. Continue implementing
/speckit.implement  # Auto-implements next ready task
```

### Parallel Workflow

Multiple developers/agents can work simultaneously via Linear coordination:

```bash
# Agent A
/speckit.implement  # Syncs from Linear, auto-claims first ready task (T001)
# Updates Linear: T001 → In Progress

# Agent B (parallel execution)
bd linear sync --pull  # Get latest from Linear (sees T001 in progress)
/speckit.implement  # Auto-claims next ready task (T002, if parallel with T001)
# Updates Linear: T002 → In Progress

# Agent A completes T001
# Updates Linear: T001 → Done
# Syncs to Beads

# Agent B checks progress
bd linear sync --pull  # Get latest (sees T001 done, T002 in progress)
/speckit.implement  # Shows remaining ready tasks

# Linear automatically coordinates:
# - No duplicate claims (Linear tracks "In Progress")
# - Dependency resolution (Linear relations)
# - Real-time status visibility (Linear API)
```

### Task Selection Methods

```bash
# 1. By number (from ready tasks list)
/speckit.implement 2
# Selects second ready task from list

# 2. By Task ID
/speckit.implement T005
# Finds and implements task T005

# 3. By Linear ID
/speckit.implement FLO-123
# Implements Linear issue FLO-123

# 4. By Linear identifier
/speckit.implement epic-3-abc123
# Implements task with Linear identifier epic-3-abc123

# 5. By Beads ID
/speckit.implement floe-abc123
# Implements Beads issue floe-abc123

# 6. Auto-select (no argument)
/speckit.implement
# Automatically selects first ready task
```

---

## Best Practices

### 1. Sync from Linear Regularly

Run `bd linear sync --pull` to get latest status:

```bash
# Before starting work
bd linear sync --pull
bd ready

# After major changes
bd linear sync --pull

# When in doubt
bd linear sync --pull
```

**Why**: Ensures you're working with latest team status, avoids conflicts.

### 2. Run /speckit.implement Frequently

```bash
# See what's ready
/speckit.implement

# Implement next task
/speckit.implement

# Check progress
/speckit.implement
```

**Why**: Shows up-to-date ready tasks, syncs automatically.

### 3. Confirm Task Completion

When asked "Is this task complete?", be honest:
- ✅ "yes" → Closes Linear + Beads, commits code
- ⏸️ "wait" → Keeps in progress, allows more work
- ❌ Never leave tasks in_progress if truly done

**Why**: Accurate status enables team coordination and dependency resolution.

### 4. Let Linear Handle Dependencies

Don't manually select blocked tasks. Linear relations block them automatically.

```bash
# ✅ CORRECT
/speckit.implement  # Auto-selects only ready (unblocked) tasks

# ❌ WRONG
/speckit.implement T010  # May be blocked, will error
```

**Why**: Linear tracks dependencies via relations (blocks, blockedBy).

### 5. Use Linear Selectors for Clarity

```bash
# ✅ CLEAR - Linear ID
/speckit.implement FLO-123

# ✅ CLEAR - Linear identifier
/speckit.implement epic-3-abc123

# ✅ OK - Task ID
/speckit.implement T010

# ⚠️ FRAGILE - Number (changes as tasks complete)
/speckit.implement 3
```

**Why**: Linear IDs/identifiers are stable across syncs.

### 6. Trust Auto-Sync

The command syncs automatically:
- Before loading (Section 0b: Sync from Linear)
- After status updates (claim, close)
- Before auto-continue

You rarely need manual sync.

**Why**: Automatic sync maintains consistency without manual intervention.

### 7. Check Linear for Team Progress

Use Linear app/web to see full Epic view:
- Visual kanban board
- Team member assignments
- Epic progress (epic-1 through epic-9 labels)
- Dependency graphs

**Linear URL**: https://linear.app/floe

**Why**: Linear provides richer team collaboration features than CLI.

### 8. Trust Linear as Source of Truth

If Beads is stale or out of sync:

```bash
bd linear sync --pull  # Refresh from Linear
```

**Never** modify Beads directly via `bd update`. Always update Linear first (via `/speckit.implement` or Linear app).

**Why**: Linear is the source of truth. Beads is just a cache.

### 9. Understand Sync Operation Types

**Two different sync operations serve different purposes:**

1. **`bd linear sync --pull`**: Linear API sync
   - Pulls updates from Linear → Beads cache
   - Updates issue status, assignments, priorities from Linear
   - Run at session start and after Linear updates
   - **Use when**: Working with Linear issues

2. **`bd sync`**: Git-based sync
   - Syncs Beads database via git (for branch collaboration)
   - Commits `.beads/issues.jsonl` to git
   - Run when collaborating across branches
   - **Use when**: Ending session on ephemeral branches

**Why**: Different sync mechanisms serve different purposes - API for Linear integration, git for collaboration.

### 10. Preserve Closure Context in Linear

**CRITICAL**: `bd close --reason` stores closure context in Beads ONLY. It does NOT create Linear comments.

**Workaround** (automated by `/speckit.implement`):
```bash
# 1. Close in Linear
mcp__plugin_linear_linear__update_issue({id: "FLO-123", state: "Done"})

# 2. Close in Beads with reason
bd close issue-123 --reason "Implemented and verified"

# 3. IMPORTANT: Add closure comment to Linear manually
mcp__plugin_linear_linear__create_comment({
  issueId: "FLO-123",
  body: "**Completed**: Implemented and verified"
})

# 4. Sync to ensure consistency
bd linear sync --pull
```

**Why**: Without manual comment creation, closure context is lost in Linear when other team members view the issue. The `/speckit.implement` command automates this pattern in Step 6.

---

## Troubleshooting

### Error: Prerequisites Failed

**Symptom**: Command fails with "Prerequisites check failed"

**Cause**: Missing spec.md or tasks.md

**Solution**:
```bash
# Generate tasks first
/speckit.tasks

# Then create Linear issues
/speckit.taskstolinear

# Then implement
/speckit.implement
```

### Error: No Linear Issues Found

**Symptom**: "No Linear issues found for this feature"

**Cause**: Haven't created Linear issues from tasks.md yet

**Solution**:
```bash
/speckit.taskstolinear
```

### Error: Linear MCP Not Available

**Symptom**: "Linear MCP is not available"

**Cause**: Linear MCP server not running or not configured

**Solution**:
```bash
# Verify Linear MCP
mcp__plugin_linear_linear__list_teams

# If fails, check MCP configuration
# Linear API key should be in environment or config
```

### Error: No Ready Tasks

**Symptom**: "No ready tasks found"

**Cause**: All tasks blocked or completed

**Solution**:
```bash
# Check what's blocking
bd blocked

# Check Linear app for dependency graph
# URL from error message

# List all open tasks
bd list --status=open
```

### Error: Task Blocked

**Symptom**: "Task X is blocked by Y"

**Cause**: Dependency in Linear not yet completed

**Solution**:
1. Check blocker status in Linear (URL in error message)
2. Work on blocker first
3. Or select different task: `/speckit.implement`

### Sync Issues

**Symptom**: Beads status doesn't match Linear

**Cause**: Stale Beads cache

**Solution**:
```bash
# Force refresh from Linear
bd linear sync --pull

# Verify sync worked
bd ready
```

### Commit Rejected by Pre-Commit Hook

**Symptom**: Git commit fails with constitutional violation

**Cause**: TDD, SOLID, or atomic commit rules violated

**Solution**:
1. Check error message for specific violation
2. Fix code to comply with constitution
3. Re-run `/speckit.implement` to retry commit

See `.specify/memory/constitution.md` for full rules.

### Closure Comments Not Syncing to Linear

**Symptom**: Closed issues in Linear lack closure context comments that were provided via `bd close --reason`

**Cause**: `bd close --reason` stores the reason in Beads database only. It does NOT create Linear comments via API.

**Solution**:
```bash
# Manual workaround (when not using /speckit.implement)
bd close issue-123 --reason "Fixed in PR #42"

# Then manually create Linear comment
mcp__plugin_linear_linear__create_comment({
  issueId: "FLO-123",
  body: "**Completed**: Fixed in PR #42"
})
```

**Prevention**: Use `/speckit.implement` which automates this pattern in Step 6 (closes Linear, closes Beads, creates comment, syncs).

**Why this matters**: Other team members viewing the issue in Linear won't see closure context without the manual comment.

---

## Mapping File Format

The `.linear-mapping.json` file stores task ↔ Linear ↔ Beads mappings:

```json
{
  "feature": "epic-3-plugin-interface-foundation",
  "epic_label": "epic-3",
  "created_at": "2026-01-05T10:30:00Z",
  "last_sync": "2026-01-05T11:45:00Z",
  "mappings": {
    "T001": {
      "linear_id": "FLO-123",
      "linear_identifier": "epic-3-abc123",
      "bead_id": "floe-abc123",
      "status": "completed",
      "title": "Add PluginMetadata ABC",
      "url": "https://linear.app/floe/issue/FLO-123",
      "requirements": ["REQ-042", "001#FR-002"]
    }
  }
}
```

**Fields**:
- `feature`: Feature directory name
- `epic_label`: Linear Epic label (epic-1 to epic-9)
- `created_at`: Mapping creation timestamp
- `last_sync`: Last sync with Linear
- `mappings`: Task ID → issue details
  - `linear_id`: Linear issue ID (FLO-123)
  - `linear_identifier`: Linear short identifier (epic-3-abc123)
  - `bead_id`: Beads issue ID (floe-abc123)
  - `status`: Current Linear status
  - `title`: Issue title
  - `url`: Linear issue URL
  - `requirements`: Traced requirements

---

## Linear Configuration

Beads is configured for Linear integration in `.beads/config.yaml`:

```yaml
issue_prefix: floe
linear:
  api_key: lin_api_...  # From environment or config
  team_id: ea992060-a5a5-47dc-8aca-bd8984b26a73
  hash_length: 6
  id_mode: hash

  # Label mapping
  label_type_map:
    bug: bug
    epic: epic
    feature: feature
    task: task

  # Priority mapping (Beads → Linear)
  priority_map:
    0: 4  # Beads 0 (no priority) → Linear 4 (no priority)
    1: 0  # Beads 1 (urgent) → Linear 0 (urgent)
    2: 1  # Beads 2 (high) → Linear 1 (high)
    3: 2  # Beads 3 (medium) → Linear 2 (medium)
    4: 3  # Beads 4 (low) → Linear 3 (low)

  # Relation mapping
  relation_map:
    blocks: blocks
    blockedBy: blocks
    duplicate: duplicates
    related: related

  # State mapping (Linear → Beads)
  state_map:
    unstarted: open
    started: in_progress
    completed: closed
    canceled: closed
```

**Key Points**:
- `team_id`: floe Linear team UUID
- `id_mode: hash`: Use 6-character hash IDs (consistent with Linear identifiers)
- Mappings handle priority/status translation between Linear and Beads

---

## Mapping File Format

The `.linear-mapping.json` file tracks task ID ↔ Linear issue relationships:

```json
{
  "feature": "epic-3-plugin-interface-foundation",
  "epic_label": "epic-3",
  "epic_url": "https://linear.app/floe/label/epic-3",
  "created_at": "2026-01-05T10:30:00Z",
  "last_sync": "2026-01-05T11:45:00Z",
  "mappings": {
    "T001": {
      "linear_id": "FLO-123",
      "linear_identifier": "epic-3-abc123",
      "bead_id": "floe-abc123",
      "status": "completed",
      "title": "Setup project structure",
      "url": "https://linear.app/floe/issue/FLO-123"
    },
    "T002": {
      "linear_id": "FLO-124",
      "linear_identifier": "epic-3-def456",
      "bead_id": "floe-def456",
      "status": "started",
      "title": "Create authentication middleware",
      "url": "https://linear.app/floe/issue/FLO-124"
    }
  }
}
```

**Fields**:
- `feature`: Feature directory name
- `epic_label`: Linear label for this epic (e.g., "epic-3")
- `epic_url`: Link to Linear label view
- `created_at`: Initial mapping creation timestamp
- `last_sync`: Last reconciliation timestamp
- `mappings`: Task ID → Linear issue details

**Per-Task Mapping**:
- `linear_id`: Linear issue UUID (e.g., "FLO-123")
- `linear_identifier`: Human-readable identifier (e.g., "epic-3-abc123")
- `bead_id`: Beads issue ID (synced from Linear)
- `status`: Current status ("todo", "started", "completed", "canceled")
- `title`: Issue title (includes Task ID prefix)
- `url`: Direct link to Linear issue

---

## Task Creation & Reconciliation

### Issue Creation Pattern

All Linear issues created from tasks.md follow this structure:

**Title**: `{TaskID}: {Description}` (truncated to 80 chars)

**Description Template**:
```markdown
**Task ID**: T001
**Epic**: epic-3
**Phase**: Phase 3: User Story Implementation
**Parallel**: Yes/No

**Requirements Mapping**:
- Replaces: 003#FR-015 (old spec requirement)
- Implements: REQ-042 (combined requirement)

**Description**:
{Full task description from tasks.md}

---

**Source**: tasks.md from feature {feature_name}
**Created by**: /speckit.taskstolinear
```

**Metadata**:
- **Labels**: Epic label (e.g., "epic-3") for organization
- **Priority**: Extracted from task markers ([P0], [P1], etc.) or description keywords
- **State**: "Todo" (pending), "Done" (completed), or "In Progress"

### Bidirectional Reconciliation

**tasks.md → Linear** (Create new issues):
- Parse tasks.md for new task IDs
- Create Linear issues with epic label
- Store mapping in `.linear-mapping.json`
- Sync to Beads via `bd linear sync --pull`

**Linear → tasks.md** (Mark completed):
- Query Linear for issues with epic label
- Find tasks marked "Done" in Linear but `[ ]` in tasks.md
- Update tasks.md: `- [ ]` → `- [x]`
- Preserve all formatting and structure

**Completed Before Integration**:
- Tasks with `[x]` but no Linear mapping
- Create Linear issue in "Done" state for historical tracking
- Add note: "Completed before Linear integration"

### Dependency Handling

**Automatic Phase Dependencies**:
- Setup phase: No dependencies (runs first)
- Foundational phase: Blocks all User Story phases
- User Story phases: Follow priority order unless marked `[P]` (parallel)
- Polish phase: Depends on all User Story phases

**Explicit Dependencies**:
- Extract from task description: "Depends on T001"
- Create Linear `blockedBy` relations
- Validate all dependencies exist in tasks.md

---

## Audit Procedures

### Orphan Detection

Check for Linear issues without corresponding tasks:

```bash
# Get all Linear issues for epic
ISSUES=$(mcp__plugin_linear_linear__list_issues --label="epic-3")

# Compare with .linear-mapping.json
# Orphans = Linear issues not in mapping
```

**Orphan Scenarios**:
- Issue created manually in Linear (not from tasks.md)
- Task deleted from tasks.md but Linear issue remains
- Mapping file lost or corrupted

**Resolution**:
- Manual review of orphaned issues
- Either add to tasks.md or close in Linear
- Update mapping file

### Constitutional Compliance

Validate tasks follow constitutional principles:

**Layer Boundary Enforcement**:
- Tasks must respect Layer 1-4 boundaries
- No Layer 4 modifying Layer 2 configuration
- Check task descriptions for layer violations

**Plugin Abstraction**:
- No hardcoded plugin implementations
- Use abstract interfaces only
- Check for "hardcode" keywords in descriptions

**TDD Ordering**:
- Test tasks (T00N) before implementation tasks (T00N+1)
- Verify test-first pattern in task sequence
- Warn if implementation precedes tests

### Dependency Validation

Check dependency integrity:

**Missing Dependencies**:
- Task depends on non-existent task ID
- Circular dependencies detected
- Phase ordering violations

**Linear Sync Validation**:
- All Linear `blockedBy` relations match tasks.md
- All Beads dependencies synced from Linear
- No orphaned relations

---

## References

- **ADR**: [ADR-0042: Linear + Beads Traceability](../architecture/adr/0042-linear-beads-traceability.md)
- **Commands**:
  - [speckit.taskstolinear](../../.claude/commands/speckit.taskstolinear.md)
  - [speckit.implement](../../.claude/commands/speckit.implement.md)
- **Beads Documentation**: Run `bd --help` or `bd onboard`
