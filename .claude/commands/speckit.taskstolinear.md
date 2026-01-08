---
description: Convert tasks.md to Linear issues and reconcile completed work bidirectionally.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

This command creates Linear issues from tasks.md with Project organization, requirements traceability, and bidirectional reconciliation.

**What it does**:
1. Validates tasks.md (duplicates, format)
2. Creates Linear issues under the appropriate Project
3. Reconciles bidirectionally (Linear status ↔ tasks.md checkboxes)
4. Sets up blocking dependencies between issues
5. Syncs to Beads cache

**Detailed patterns**: [Linear Workflow Guide](../../../docs/guides/linear-workflow.md)

## Outline

1. **Setup & Validation**
   - Run `.specify/scripts/bash/check-prerequisites.sh --json --require-tasks --include-tasks` from repo root
   - Parse JSON output for `FEATURE_DIR`
   - Test Linear MCP connection: `mcp__plugin_linear_linear__list_teams`
   - Get team ID via `mcp__plugin_linear_linear__get_team({query: "floe"})`

2. **Determine Project**
   - Extract feature info from directory path (e.g., `specs/001-plugin-registry/`)
   - Build project slug: `floe-{NN}-{feature-slug}` (e.g., `floe-01-plugin-registry`)
   - Query Linear projects via `mcp__plugin_linear_linear__list_projects`
   - Find matching project by name or slug
   - ERROR if project not found - must be created in Linear first
   - Optionally create epic label (e.g., `epic-1`) for filtering if it doesn't exist

3. **Load or Initialize Mapping**
   - Check for existing `$FEATURE_DIR/.linear-mapping.json`
   - If exists: load and use for reconciliation
   - If not: initialize new mapping structure with metadata (feature name, project ID, timestamps)

4. **Parse & Validate tasks.md**
   - Parse tasks matching format: `- [x] T### [P] [US#] Description with file path`
   - Extract: task ID, completed status, parallel marker, user story, requirements, description
   - **Duplicate detection**: ERROR if same task ID appears twice
   - **TDD warning**: Warn if implementation task doesn't have preceding test task

5. **Query Linear for Existing Issues**
   - Query project issues via `mcp__plugin_linear_linear__list_issues({project: projectId})`
   - Query status names via `mcp__plugin_linear_linear__list_issue_statuses` (never hardcode!)
   - Build status → type mapping (e.g., "Done" → `completed`)
   - Build reverse map: Linear ID → Task ID from existing mapping
   - Identify tasks marked complete in Linear but not in tasks.md

6. **Create Linear Issues**
   - For each task NOT already in mapping:
     - Build title: `{TaskID}: {truncated description}`
     - Build description with: Task ID, phase, parallel status, requirements, full description
     - Add GitHub links for traceability (spec.md, plan.md, tasks.md URLs)
     - Set priority from task (default: 2/High)
     - Set initial state based on tasks.md checkbox
     - Create via `mcp__plugin_linear_linear__create_issue`:
       - `team`: team ID
       - `project`: project ID
       - `title`, `description`, `priority`, `state`
       - `links`: GitHub doc URLs
     - Store mapping: task ID → Linear ID, identifier, URL

7. **Create Dependencies**
   - **After all issues exist** (Linear IDs required)
   - Parse explicit dependencies: "Depends on T###" in descriptions
   - For each task with dependencies:
     - Collect Linear IDs of blocking tasks
     - Update via `mcp__plugin_linear_linear__update_issue({id, blockedBy: [linearIds]})`
   - Verify at least one dependency via `get_issue({includeRelations: true})`

8. **Update tasks.md from Linear**
   - For tasks marked "Done" in Linear but `[ ]` in tasks.md:
     - Update checkbox to `[x]` in tasks.md
   - Write updated tasks.md

9. **Save Mapping & Sync**
   - Update `last_sync` timestamp in mapping
   - Write mapping to `$FEATURE_DIR/.linear-mapping.json`
   - If Beads available: `bd linear sync --pull`

10. **Report Summary**
    - Total tasks in tasks.md
    - Issues created (with Linear identifiers and URLs)
    - Tasks marked complete from Linear
    - Dependencies created
    - Next steps: `/speckit.implement` to start work

## Tool Patterns

**Linear MCP tools**:

| Tool | Purpose |
|------|---------|
| `mcp__plugin_linear_linear__get_team({query: "floe"})` | Get team ID |
| `mcp__plugin_linear_linear__list_projects({team: teamId})` | Find project |
| `mcp__plugin_linear_linear__list_issue_statuses({team: teamId})` | Get status names |
| `mcp__plugin_linear_linear__list_issues({project: projectId})` | Get existing issues |
| `mcp__plugin_linear_linear__create_issue({...})` | Create new issue |
| `mcp__plugin_linear_linear__update_issue({id, blockedBy})` | Set dependencies |
| `mcp__plugin_linear_linear__create_issue_label({...})` | Create epic label |

**Mapping file format** (`$FEATURE_DIR/.linear-mapping.json`):
```json
{
  "metadata": {
    "feature": "001-plugin-registry",
    "project": "floe-01-plugin-registry",
    "project_id": "uuid",
    "created_at": "ISO timestamp",
    "last_sync": "ISO timestamp"
  },
  "mappings": {
    "T001": {
      "linear_id": "uuid",
      "linear_identifier": "FLO-33",
      "title": "T001: Create plugin interfaces",
      "url": "https://linear.app/...",
      "status": "Todo"
    }
  }
}
```

## Key Rules

1. **Project must exist first** - Create the Linear Project via Linear UI before running this command. Project naming: `floe-{NN}-{feature-slug}`.

2. **Never hardcode status names** - Query `list_issue_statuses` and match by `type` field.

3. **Dependencies after creation** - `blockedBy` requires Linear IDs, so all issues must exist first.

4. **GitHub links for traceability** - Each issue gets links to spec.md, plan.md, tasks.md in the repo.

5. **Bidirectional sync** - Linear "Done" status propagates back to tasks.md checkboxes.

## Task Format

Tasks in tasks.md must follow this format:
```
- [ ] T001 [P] [US1] Description with file path
```

Components:
- `- [ ]` or `- [x]`: Checkbox (required)
- `T###`: Task ID (required, sequential)
- `[P]`: Parallel marker (optional, means safe to run concurrently)
- `[US#]`: User story reference (optional)
- Description: Should include file path

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Project not found | Project doesn't exist in Linear | Create project in Linear UI first |
| Duplicate task IDs | Same T### appears twice | Fix duplicates in tasks.md |
| Linear MCP unavailable | MCP not configured | Check API key configuration |
| Dependencies failed | Blocking task not in mapping | Ensure all tasks have issues first |

## References

- **[Linear Workflow Guide](../../../docs/guides/linear-workflow.md)** - Architecture, mapping format, detailed patterns
- **[speckit.tasks](./speckit.tasks.md)** - Generate tasks.md
- **[speckit.implement](./speckit.implement.md)** - Execute tasks after Linear sync
