# Parallel Agents

Git worktree management and parallelization strategy.

## Overview

Agents run in parallel using git worktrees for isolation. Each agent has its own working directory but shares the git history.

## Git Worktree Basics

### What is a Worktree?

A git worktree is a linked copy of your repository with its own working directory and branch. All worktrees share the same `.git` object database.

```
floe/                          # Main working tree
+-- .git/                      # Shared git database
+-- packages/
+-- plugins/

floe-agent-ep001-t001/         # Worktree for T001
+-- .git -> ../floe/.git       # Link to main
+-- packages/
+-- plugins/
+-- .agent/                    # Agent state files

floe-agent-ep001-t003/         # Worktree for T003
+-- .git -> ../floe/.git       # Link to main
+-- packages/
+-- plugins/
+-- .agent/
```

### Creating Worktrees

```bash
# Create worktree with new branch
git worktree add ../floe-agent-ep001-t001 -b feature/ep001-t001

# Create worktree from existing branch
git worktree add ../floe-agent-ep001-t001 feature/ep001-t001

# List all worktrees
git worktree list

# Remove worktree
git worktree remove ../floe-agent-ep001-t001
```

## Worktree Naming Convention

```
{project}-agent-{epic}-{task_slug}/

Examples:
floe-agent-ep001-auth/
floe-agent-ep001-catalog/
floe-agent-ep002-compute/
```

## Parallelization Strategy

### File Overlap Detection

Before spawning agents, predict which files each task will modify:

```python
def predict_files_modified(task: Task) -> set[str]:
    """Predict files a task will modify based on description and context."""
    files = set()

    # Parse task description for file hints
    if "models.py" in task.description:
        files.add("packages/floe-core/src/floe_core/models.py")

    if "plugin" in task.description.lower():
        plugin_name = extract_plugin_name(task)
        files.add(f"plugins/{plugin_name}/")

    # Use plan.md file references
    for file_ref in task.plan_references:
        files.add(file_ref)

    return files

def can_parallelize(task_a: Task, task_b: Task) -> bool:
    """Check if two tasks can run in parallel."""
    files_a = predict_files_modified(task_a)
    files_b = predict_files_modified(task_b)

    # Check for any overlap
    return not (files_a & files_b)
```

### Wave Execution

Tasks are grouped into parallel execution waves:

```
Wave 1: [T001 (models.py), T003 (cli.py), T005 (tests/)]
         |                  |                  |
         v                  v                  v
      Complete          Complete          Complete
         |                  |                  |
         +------------------+------------------+
                            |
                            v
Wave 2: [T002 (models.py), T004 (cli.py)]  # Overlaps with Wave 1
         |                  |
         v                  v
      Complete          Complete
         |                  |
         +------------------+
                            |
                            v
Wave 3: [T006 (integration)]  # Depends on T001-T005
         |
         v
      Complete
```

### Dynamic Wave Building

```python
def build_execution_waves(ready_tasks: list[Task]) -> list[list[Task]]:
    """Group tasks into parallel execution waves."""
    waves = []
    remaining = set(ready_tasks)

    while remaining:
        wave = []
        wave_files = set()

        for task in remaining:
            task_files = predict_files_modified(task)

            # No overlap with current wave
            if not task_files & wave_files:
                wave.append(task)
                wave_files |= task_files

        if not wave:
            # All remaining tasks have file conflicts
            # Pick one arbitrarily to break deadlock
            wave = [next(iter(remaining))]

        waves.append(wave)
        remaining -= set(wave)

    return waves
```

## Worktree Lifecycle

### 1. Creation (/ralph.spawn)

```bash
# For each task in parallel wave
git worktree add "../floe-agent-ep001-t001" -b "feature/ep001-t001" main

# Initialize agent state
mkdir -p "../floe-agent-ep001-t001/.agent"
cp .ralph/templates/plan.json "../floe-agent-ep001-t001/.agent/"
cp .ralph/templates/activity.md "../floe-agent-ep001-t001/.agent/"
cp .ralph/templates/PROMPT.md "../floe-agent-ep001-t001/.agent/"
cp .specify/memory/constitution.md "../floe-agent-ep001-t001/.agent/"
```

### 2. Agent Execution

Each agent runs independently in its worktree:

```bash
# Agent enters worktree
cd "../floe-agent-ep001-t001"

# Agent loop (per iteration)
# 1. Read state
cat .agent/plan.json
cat .agent/activity.md | tail -20

# 2. Implement next subtask
# ... code changes ...

# 3. Run quality gates
uv run ruff check . --fix && uv run ruff format .
uv run mypy --strict packages/ plugins/
uv run pytest tests/unit/ -v --tb=short

# 4. Commit
git add -A
git commit -m "feat(auth): add JWT validation (T001, FLO-33)"

# 5. Update state
# ... update plan.json, activity.md ...
```

### 3. Completion

```bash
# Agent signals COMPLETE in plan.json
{
  "status": "complete",
  "completion_signal": "COMPLETE"
}

# Agent pushes branch
git push -u origin feature/ep001-t001
```

### 4. Integration (/ralph.integrate)

```bash
# Switch to main
cd floe

# Fetch all branches
git fetch --all

# Rebase each feature branch
git worktree list | while read worktree branch _; do
    cd "$worktree"
    git rebase origin/main
    if [ $? -ne 0 ]; then
        echo "CONFLICT in $worktree"
        # Signal for human intervention
    fi
done
```

### 5. Cleanup (/ralph.cleanup)

```bash
# After PR merge, remove worktrees
git worktree remove "../floe-agent-ep001-t001"

# Prune stale worktrees
git worktree prune

# Delete merged branches
git branch -d feature/ep001-t001
git push origin --delete feature/ep001-t001
```

## Manifest Tracking

The orchestrator tracks all worktrees in `.ralph/manifest.json`:

```json
{
  "schema_version": "1.0.0",
  "active_agents": [
    {
      "worktree_path": "../floe-agent-ep001-t001",
      "task_id": "T001",
      "linear_id": "FLO-33",
      "branch": "feature/ep001-t001",
      "started_at": "2026-01-16T14:30:00Z",
      "iteration": 5,
      "status": "in_progress"
    },
    {
      "worktree_path": "../floe-agent-ep001-t003",
      "task_id": "T003",
      "linear_id": "FLO-35",
      "branch": "feature/ep001-t003",
      "started_at": "2026-01-16T14:32:00Z",
      "iteration": 3,
      "status": "in_progress"
    }
  ],
  "completed_today": [
    {
      "task_id": "T002",
      "linear_id": "FLO-34",
      "duration_minutes": 22,
      "iterations": 4,
      "completed_at": "2026-01-16T14:15:00Z"
    }
  ],
  "statistics": {
    "total_tasks_completed": 12,
    "average_duration_minutes": 42,
    "average_iterations": 6
  }
}
```

## Conflict Resolution

### Detecting Conflicts

```bash
# During rebase
git rebase origin/main

# If conflict occurs
if [ $? -ne 0 ]; then
    # List conflicting files
    git diff --name-only --diff-filter=U

    # Signal for human intervention
    echo "CONFLICT" > .agent/status
fi
```

### Manual Resolution

```bash
# 1. Navigate to worktree
cd ../floe-agent-ep001-t003

# 2. See conflicting files
git status

# 3. Resolve conflicts manually
# ... edit files ...

# 4. Continue rebase
git add -A
git rebase --continue

# 5. Or abort and reschedule
git rebase --abort
```

## Stale Worktree Detection

### Configuration

```yaml
# .ralph/config.yaml
orchestration:
  stale_worktree_hours: 24
  auto_cleanup: true
```

### Detection Script

```bash
#!/bin/bash
# Check for stale worktrees

STALE_HOURS=24
NOW=$(date +%s)

git worktree list --porcelain | grep "^worktree" | cut -d' ' -f2 | while read worktree; do
    if [[ "$worktree" == *"floe-agent"* ]]; then
        # Check last commit time
        LAST_COMMIT=$(cd "$worktree" && git log -1 --format=%ct 2>/dev/null || echo 0)
        AGE_HOURS=$(( (NOW - LAST_COMMIT) / 3600 ))

        if [ $AGE_HOURS -gt $STALE_HOURS ]; then
            echo "STALE: $worktree (${AGE_HOURS}h since last commit)"
        fi
    fi
done
```

## Monitoring

### /ralph.status Output

```
RALPH WIGGUM STATUS - floe

Active Agents: 4/5
Completed Today: 12 tasks
Average Duration: 42 minutes

+----------+--------+-------+--------+-------------+
| Task     | Agent  | Iter  | Status | Last Update |
+----------+--------+-------+--------+-------------+
| T001     | WK-001 | 5/15  | lint   | 2 min ago   |
| T003     | WK-002 | 3/15  | test   | 1 min ago   |
| T005     | WK-003 | 8/15  | sec    | 30s ago     |
| T007     | WK-004 | 1/15  | impl   | 5s ago      |
+----------+--------+-------+--------+-------------+

Blocked: 1 (T002 - waiting for human input)
Queued: 8 tasks ready after current wave

Wave Progress:
  Wave 1: [T001, T003, T005] - 2/3 complete
  Wave 2: [T002, T004, T007] - 0/3 complete (waiting)
  Wave 3: [T008] - blocked on Wave 1+2
```

## Best Practices

1. **Keep worktrees separate** - Don't create worktrees inside the main repo

2. **Clean up after merge** - Remove worktrees immediately after PR merge

3. **Monitor stale worktrees** - Run cleanup weekly

4. **Use consistent naming** - Follow the `{project}-agent-{epic}-{task}` pattern

5. **Avoid cross-worktree dependencies** - Each agent should be self-contained

6. **Commit frequently** - Small, atomic commits help with conflict resolution

7. **Push early** - Push branches as soon as work begins (for visibility)

## Troubleshooting

### Worktree Already Exists

```bash
# Error: 'worktree' already exists
git worktree remove ../floe-agent-ep001-t001 --force
git worktree add ../floe-agent-ep001-t001 -b feature/ep001-t001 main
```

### Locked Worktree

```bash
# Error: worktree is locked
git worktree unlock ../floe-agent-ep001-t001
```

### Orphaned Worktree

```bash
# Worktree directory deleted but git still tracks it
git worktree prune
```

### Branch Already Checked Out

```bash
# Error: branch already checked out in another worktree
git worktree list  # Find which worktree has the branch
git worktree remove <that-worktree>  # Remove it first
```
