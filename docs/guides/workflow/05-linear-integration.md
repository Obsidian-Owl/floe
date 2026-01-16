# Linear Integration

Direct Linear MCP integration patterns for issue tracking.

## Overview

All issue tracking uses Linear MCP directly - no caching layer. Linear is the sole source of truth for task status.

## MCP Tools Reference

### Querying Issues

```python
# List issues in a team
mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "state": "backlog",
    "limit": 50
})

# Get issue details
mcp__plugin_linear_linear__get_issue({
    "id": "FLO-33",
    "includeRelations": True
})

# Filter by project (epic)
mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "project": "floe-01-plugin-system",
    "state": "unstarted"
})

# Filter by label
mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "label": "epic:01"
})
```

### Updating Issues

```python
# Update issue state
mcp__plugin_linear_linear__update_issue({
    "id": "FLO-33",
    "state": "started"
})

# Mark as complete
mcp__plugin_linear_linear__update_issue({
    "id": "FLO-33",
    "state": "completed"
})

# Add assignee
mcp__plugin_linear_linear__update_issue({
    "id": "FLO-33",
    "assignee": "me"
})
```

### Creating Comments

```python
# Add completion comment
mcp__plugin_linear_linear__create_comment({
    "issueId": "FLO-33",
    "body": """## Task Completed

**Duration**: 7 iterations, 38 minutes
**Commits**: 4

### Changes
- Added authentication middleware
- Implemented JWT validation
- Added test coverage (92%)

### Quality Gates
- Lint: PASS
- Type: PASS
- Tests: PASS (23/23)
- Security: PASS
- Constitution: PASS
"""
})
```

### Managing Dependencies

```python
# Create issue with blockers
mcp__plugin_linear_linear__create_issue({
    "title": "T003: Implement API endpoint",
    "team": "floe",
    "project": "floe-01-plugin-system",
    "blockedBy": ["FLO-31", "FLO-32"],  # Must complete these first
    "labels": ["epic:01"]
})

# Update blockers
mcp__plugin_linear_linear__update_issue({
    "id": "FLO-33",
    "blockedBy": ["FLO-31", "FLO-32", "FLO-35"]  # Replaces ALL blockers
})
```

## Status Mapping

| Linear State | Workflow Meaning |
|-------------|-----------------|
| `backlog` | Ready for automation |
| `unstarted` | Ready for automation |
| `started` | Agent claimed, in progress |
| `completed` | Agent finished successfully |
| `cancelled` | Blocked or abandoned |

## Epic Organization

### Project Naming Convention

```
floe-{NN}-{slug}

Examples:
floe-01-plugin-system
floe-02-oci-registry
floe-10a-agent-memory
```

### Label Convention

```
epic:{NN}

Examples:
epic:01
epic:02
epic:10a
```

### Query Ready Tasks for Epic

```python
# Get all ready tasks for Epic 01
mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "project": "floe-01-plugin-system",
    "state": "backlog",  # Or "unstarted"
    "includeArchived": False
})
```

## Workflow Integration

### Phase A: Task Creation (/speckit.taskstolinear)

```python
# 1. Query project
project = mcp__plugin_linear_linear__get_project({
    "query": "floe-01-plugin-system"
})

# 2. Create issues from tasks.md
for task in tasks:
    mcp__plugin_linear_linear__create_issue({
        "title": task.title,
        "team": "floe",
        "project": project.id,
        "description": task.description,
        "labels": ["epic:01"],
        "blockedBy": task.dependencies
    })
```

### Phase B: Agent Claiming (/ralph.spawn)

```python
# 1. Query ready tasks
ready = mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "project": epic_project,
    "state": "backlog"
})

# 2. Claim task (mark as started)
mcp__plugin_linear_linear__update_issue({
    "id": ready[0].id,
    "state": "started",
    "assignee": "me"
})

# 3. Add claim comment
mcp__plugin_linear_linear__create_comment({
    "issueId": ready[0].id,
    "body": "Agent claimed task. Worktree: floe-agent-ep001-t001"
})
```

### Phase B: Agent Completion

```python
# 1. Mark complete
mcp__plugin_linear_linear__update_issue({
    "id": task_id,
    "state": "completed"
})

# 2. Add completion summary
mcp__plugin_linear_linear__create_comment({
    "issueId": task_id,
    "body": completion_summary
})
```

### Phase B: Agent Blocked

```python
# 1. Add block comment
mcp__plugin_linear_linear__create_comment({
    "issueId": task_id,
    "body": """## Task Blocked

**Reason**: Security finding requires human review
**Iteration**: 5/15
**Last Gate Failed**: security

### Finding
HIGH: Hardcoded API key in src/auth.py:45

### Action Required
Human must review and approve remediation approach.
"""
})

# 2. Keep state as "started" (not completed or cancelled)
# Human will resume or reassign
```

## Sub-Task Creation

When agents discover issues during implementation:

```python
# 1. Create sub-task as comment (not separate issue)
mcp__plugin_linear_linear__create_comment({
    "issueId": parent_task_id,
    "body": """## Sub-Task Created: T001.1

**Description**: Add validation for edge case X
**Discovered During**: Iteration 3
**Status**: In Progress

This sub-task must complete before T001 can finish.
"""
})

# 2. Update plan.json locally
# Sub-tasks tracked in worktree, not Linear
```

## Dependency Resolution

### Query Dependency Graph

```python
# Get issue with relations
issue = mcp__plugin_linear_linear__get_issue({
    "id": "FLO-33",
    "includeRelations": True
})

# Check if blocked
blocked_by = issue.get("blockedBy", [])
if blocked_by:
    # Check if blockers are complete
    for blocker_id in blocked_by:
        blocker = mcp__plugin_linear_linear__get_issue({"id": blocker_id})
        if blocker["state"]["name"] != "Done":
            print(f"Blocked by incomplete task: {blocker_id}")
```

### Topological Sort for Execution

```python
def get_execution_order(issues: list[dict]) -> list[list[dict]]:
    """Group issues into execution waves based on dependencies."""
    waves = []
    completed = set()

    while issues:
        # Find tasks with no incomplete blockers
        wave = [
            issue for issue in issues
            if all(b in completed for b in issue.get("blockedBy", []))
        ]

        if not wave:
            raise Exception("Circular dependency detected")

        waves.append(wave)
        completed.update(issue["id"] for issue in wave)
        issues = [i for i in issues if i not in wave]

    return waves
```

## Error Handling

### Rate Limiting

```python
import time
from functools import wraps

def with_retry(max_retries=3, delay=1.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "rate limit" in str(e).lower():
                        time.sleep(delay * (attempt + 1))
                    else:
                        raise
            raise Exception(f"Failed after {max_retries} retries")
        return wrapper
    return decorator
```

### Connection Failures

```python
# Always handle MCP connection issues
try:
    result = mcp__plugin_linear_linear__list_issues({...})
except Exception as e:
    logger.error("Linear MCP unavailable", error=str(e))
    # Fall back to cached state or signal BLOCKED
```

## Best Practices

1. **Batch queries** - Get all needed data in one call where possible

2. **Use includeRelations** - Get blockedBy in single query

3. **Atomic updates** - Update state and add comment in sequence

4. **Log all changes** - Activity log should mirror Linear comments

5. **Handle rate limits** - Implement exponential backoff

6. **Check before update** - Verify issue exists before updating

## Configuration

See `.ralph/config.yaml`:

```yaml
linear:
  team: "floe"
  status_types:
    ready:
      - "backlog"
      - "unstarted"
    claimed:
      - "started"
    complete:
      - "completed"
    blocked:
      - "cancelled"

  label_format: "epic:{epic_number}"
  project_format: "floe-{epic_number}-{slug}"
```
