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

# 3. Implement tasks
/speckit.implement       # One at a time (with confirmation)
/speckit.implement-epic  # ALL tasks (auto-continues)

# 4. Sync back to Linear
bd linear sync --pull

# 5. Check Linear for team progress
# Initiative: https://linear.app/obsidianowl/initiative/floe-platform-delivery-25020298255a/overview
# Epic docs: docs/plans/epics/
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
- Epic organization via Linear Initiative > Projects hierarchy
  - Initiative: "floe Platform Delivery" (all Epics)
  - Projects: Individual Epics (21 Projects, e.g., floe-01-plugin-registry)
  - Issues: Tasks under each Project

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
- **Epic Organization**: Linear Initiative > Projects for visual grouping and progress tracking
- **Full Traceability**: Requirements → Linear Projects → Issues → Beads → Git → Tests

---

## Traceability Chain

This workflow maintains full traceability from original requirements through to tests:

```
Combined Requirements (REQ-042 or 003#FR-015)
  ↓
Linear Projects (floe-03a-policy-enforcer, floe-04a-compute-plugin, etc.)
  ↓
Tasks (T001 in specs/epic-3a/tasks.md)
  ↓
Linear Issues (FLO-123, under Project floe-03a-policy-enforcer)
  ↓
Beads Cache (floe-abc123)
  ↓
Git Commits (feat(plugin-api): add PluginMetadata ABC (T001, FLO-123))
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
- Creates Linear issues under the appropriate Project (e.g., floe-03a-policy-enforcer)
- Includes requirements in issue description
- Example: Linear issue "Add PluginMetadata ABC" → Description includes "Requirements: REQ-042"
- Maps dependencies via Linear relations (blocks, blockedBy)
- Project mapping via `.linear-mapping.json` or automatic Epic → Project resolution

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
- Requirement (REQ-XXX or spec#FR-XXX) → Project → Task → Linear issue → Beads issue → Commit → Test
- Every requirement has a test (via @pytest.mark.requirement)
- Every commit traceable to requirement (via Linear issue ID in commit message)
- Every Linear issue traceable to Epic (via Project membership)
- All Projects visible under "floe Platform Delivery" Initiative
- Requirements documented in ADRs and `docs/plans/epics/` documentation

---

## Workflow Examples

### Basic Implementation Flow

```bash
# 1. Generate tasks from plan
/speckit.tasks

# 2. Create Linear issues from tasks (under Project with requirements)
/speckit.taskstolinear
# Creates Linear issues under appropriate Project (e.g., floe-03a-policy-enforcer)
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

# Alternative: Auto-implement ALL tasks
/speckit.implement-epic  # No confirmation, stops when blocked or complete
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
- Visual kanban board per Project
- Team member assignments
- Initiative progress (all 21 Projects under "floe Platform Delivery")
- Project dependency graphs
- Milestone tracking

**Initiative URL**: https://linear.app/obsidianowl/initiative/floe-platform-delivery-25020298255a/overview
**Epic Documentation**: `docs/plans/epics/` for detailed context

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
  "feature": "epic-3a-policy-enforcer-core",
  "project_id": "08a4f4df-013c-xxxx-xxxx-xxxxxxxxxxxx",
  "project_name": "floe-03a-policy-enforcer",
  "project_url": "https://linear.app/obsidianowl/project/floe-03a-policy-enforcer-08a4f4df013c",
  "initiative_id": "25020298-255a-xxxx-xxxx-xxxxxxxxxxxx",
  "initiative_name": "floe Platform Delivery",
  "created_at": "2026-01-05T10:30:00Z",
  "last_sync": "2026-01-05T11:45:00Z",
  "mappings": {
    "T001": {
      "linear_id": "FLO-123",
      "bead_id": "floe-abc123",
      "status": "completed",
      "title": "Add PolicyEnforcer ABC",
      "url": "https://linear.app/obsidianowl/issue/FLO-123",
      "requirements": ["REQ-200", "REQ-201"]
    }
  }
}
```

**Fields**:
- `feature`: Feature directory name (matches Epic)
- `project_id`: Linear Project UUID
- `project_name`: Linear Project name (e.g., floe-03a-policy-enforcer)
- `project_url`: Direct link to Project in Linear
- `initiative_id`: Parent Initiative UUID ("floe Platform Delivery")
- `initiative_name`: Initiative name
- `created_at`: Mapping creation timestamp
- `last_sync`: Last sync with Linear
- `mappings`: Task ID → issue details
  - `linear_id`: Linear issue ID (FLO-123)
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

  # Initiative and Project configuration
  initiative_id: 25020298-255a-xxxx-xxxx-xxxxxxxxxxxx  # "floe Platform Delivery"

  # Project mapping (Epic → Linear Project)
  # Projects are created under the Initiative
  project_map:
    epic-1: floe-01-plugin-registry
    epic-2a: floe-02a-manifest-schema
    epic-2b: floe-02b-compilation
    epic-3a: floe-03a-policy-enforcer
    epic-3b: floe-03b-policy-validation
    epic-3c: floe-03c-data-contracts
    epic-3d: floe-03d-contract-monitoring
    epic-4a: floe-04a-compute-plugin
    epic-4b: floe-04b-orchestrator-plugin
    epic-4c: floe-04c-catalog-plugin
    epic-4d: floe-04d-storage-plugin
    epic-5a: floe-05a-dbt-plugin
    epic-5b: floe-05b-dataquality-plugin
    epic-6a: floe-06a-opentelemetry
    epic-6b: floe-06b-openlineage
    epic-7a: floe-07a-identity-secrets
    epic-7b: floe-07b-k8s-rbac
    epic-7c: floe-07c-network-pod-security
    epic-8a: floe-08a-oci-client
    epic-8b: floe-08b-artifact-signing
    epic-8c: floe-08c-promotion-lifecycle
    epic-9a: floe-09a-k8s-deployment
    epic-9b: floe-09b-helm-charts
    epic-9c: floe-09c-testing-infra

  # Label mapping (for type categorization)
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
- `initiative_id`: "floe Platform Delivery" Initiative containing all Projects
- `project_map`: Maps Epic directories to Linear Project names
- `id_mode: hash`: Use 6-character hash IDs (consistent with Linear identifiers)
- Mappings handle priority/status translation between Linear and Beads

**Initiative URL**: https://linear.app/obsidianowl/initiative/floe-platform-delivery-25020298255a/overview

---

## Task Creation & Reconciliation

### Issue Creation Pattern

All Linear issues created from tasks.md follow this structure:

**Title**: `{TaskID}: {Description}` (truncated to 80 chars)

**Description Template**:
```markdown
**Task ID**: T001
**Project**: floe-03a-policy-enforcer
**Phase**: Phase 3: User Story Implementation
**Parallel**: Yes/No

**Requirements Mapping**:
- Implements: REQ-200, REQ-201

**Description**:
{Full task description from tasks.md}

---

**Source**: tasks.md from feature {feature_name}
**Created by**: /speckit.taskstolinear
```

**Metadata**:
- **Project**: Linear Project (e.g., "floe-03a-policy-enforcer") - issues belong to Projects
- **Priority**: Extracted from task markers ([P0], [P1], etc.) or description keywords
- **State**: "Todo" (pending), "Done" (completed), or "In Progress"

### Bidirectional Reconciliation

**tasks.md → Linear** (Create new issues):
- Parse tasks.md for new task IDs
- Create Linear issues under appropriate Project
- Store mapping in `.linear-mapping.json`
- Sync to Beads via `bd linear sync --pull`

**Linear → tasks.md** (Mark completed):
- Query Linear for issues in the Project
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
# Get all Linear issues for Project
ISSUES=$(mcp__plugin_linear_linear__list_issues --project="floe-03a-policy-enforcer")

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
- **Epic Documentation**: [docs/plans/epics/](../plans/epics/) - All 21 Epic specifications
- **Initiative Overview**: [docs/plans/EPIC-OVERVIEW.md](../plans/EPIC-OVERVIEW.md) - Dependency graph, parallelization
- **Requirements Traceability**: [docs/plans/REQUIREMENTS-TRACEABILITY.md](../plans/REQUIREMENTS-TRACEABILITY.md) - Full REQ→Epic mapping
- **Commands**:
  - [speckit.taskstolinear](../../.claude/commands/speckit.taskstolinear.md)
  - [speckit.implement](../../.claude/commands/speckit.implement.md)
  - [speckit.implement-epic](../../.claude/commands/speckit.implement-epic.md)
- **Linear Resources**:
  - Initiative: https://linear.app/obsidianowl/initiative/floe-platform-delivery-25020298255a/overview
  - Team: floe-runtime
- **Beads Documentation**: Run `bd --help` or `bd onboard`
