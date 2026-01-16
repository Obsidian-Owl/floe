# Phase B: Automated Implementation

Fully automated parallel agent execution using the Ralph Wiggum pattern with git worktrees.

## Overview

Phase B runs without human intervention. AI agents work in parallel on non-overlapping tasks, with embedded quality gates ensuring high-quality output.

## Architecture

```
                    +-------------------------------------------+
                    |         ORCHESTRATOR (main)               |
                    |  - Reads Linear for ready tasks           |
                    |  - Spawns agents in worktrees             |
                    |  - Monitors completion signals            |
                    +---------------------+---------------------+
                                          |
           +------------------------------+------------------------------+
           |                              |                              |
           v                              v                              v
+------------------+          +------------------+          +------------------+
|  WORKTREE 1      |          |  WORKTREE 2      |          |  WORKTREE N      |
|  ep001/auth      |          |  ep001/catalog   |          |  ep00N/compute   |
|                  |          |                  |          |                  |
|  Agent Loop:     |          |  Agent Loop:     |          |  Agent Loop:     |
|  1. Read state   |          |  1. Read state   |          |  1. Read state   |
|  2. Implement    |          |  2. Implement    |          |  2. Implement    |
|  3. Validate*    |          |  3. Validate*    |          |  3. Validate*    |
|  4. Commit       |          |  4. Commit       |          |  4. Commit       |
|  5. Log          |          |  5. Log          |          |  5. Log          |
+------------------+          +------------------+          +------------------+
```

## Commands

### /ralph.spawn [epic]

Creates worktrees for all ready tasks in an epic.

**Process**:
1. Query Linear for tasks with status `backlog` or `unstarted`
2. Build dependency graph from blockedBy relations
3. Detect file overlaps to determine parallelization
4. Create worktrees for non-overlapping tasks
5. Initialize each worktree with `.agent/` state files
6. Start agent loops

**Worktree Structure**:
```
floe-agent-ep001-auth/
+-- .agent/
|   +-- plan.json           # Subtask status
|   +-- activity.md         # Progress log
|   +-- constitution.md     # Principles copy
|   +-- PROMPT.md           # Agent instructions
+-- [source files]
+-- .git                    # Linked to main
```

### /ralph.status

Monitors all active agents and their progress.

**Output**:
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
```

## Agent Loop (Per Iteration)

Each agent runs the Ralph Wiggum pattern: fresh context per iteration.

### Step 1: Read State
```bash
cat .agent/plan.json
cat .agent/activity.md | tail -20
```

### Step 2: Identify Next Subtask
Find first subtask where `"passes": false` in plan.json.

### Step 3: Implement
- Make atomic, focused changes
- Follow TDD: test first, then implementation
- Use existing patterns from codebase

### Step 4: Run All Quality Gates
```bash
# All gates must pass
uv run ruff check . --fix && uv run ruff format .
uv run mypy --strict packages/ plugins/
uv run pytest tests/unit/ -v --tb=short
/security-review
python .ralph/scripts/validate-constitution.py --files $(git diff --name-only HEAD~1)
```

### Step 5: Update State
- Update `plan.json`: Set subtask `"passes": true`
- Create atomic git commit
- Log completion in `activity.md`

### Step 6: Signal Completion
```
COMPLETE  - All subtasks pass
BLOCKED   - Need human intervention
```

## State Files

### plan.json

```json
{
  "task_id": "T001",
  "linear_id": "FLO-33",
  "epic": "EP001",
  "status": "in_progress",
  "iteration": 3,
  "max_iterations": 15,
  "subtasks": [
    {"id": "T001.1", "description": "Write tests", "passes": true},
    {"id": "T001.2", "description": "Implement feature", "passes": false},
    {"id": "T001.3", "description": "Validate constitution", "passes": false}
  ],
  "discovered_subtasks": [],
  "gate_results": {
    "lint": "pass",
    "typecheck": "pass",
    "unit_tests": "pass",
    "security": "pass",
    "constitution": "pass"
  }
}
```

### activity.md

```markdown
## Iteration 3 - 2026-01-16T14:32:00Z

**Subtask**: T001.2 - Implement authentication middleware
**Status**: PASS

### Changes Made
- [src/middleware/auth.py]: Added JWT validation
- [tests/unit/test_auth.py]: Added test cases

### Gate Results
- Lint: PASS
- Type: PASS
- Test: PASS (12 passed, 0 failed)
- Security: PASS
- Constitution: PASS
```

## Parallelization Strategy

### File Overlap Detection

Before spawning agents, orchestrator checks:
```python
def can_parallelize(task_a, task_b) -> bool:
    files_a = predict_files_modified(task_a)
    files_b = predict_files_modified(task_b)
    return not (files_a & files_b)  # No overlap
```

### Wave Execution

Tasks are grouped into waves:
```
Wave 1: [T001 (models.py), T003 (cli.py), T005 (tests/)]
Wave 2: [T002 (models.py), T004 (cli.py)]  # Overlaps Wave 1
Wave 3: [T006 (integration)]  # Depends on T001-T005
```

### Dependency Resolution

Linear blockedBy relations determine execution order:
- Task with no blockers: Ready
- Task with completed blockers: Ready
- Task with incomplete blockers: Wait

## Sub-Task Creation

When agents discover issues during implementation:

```json
{
  "id": "T001.4",
  "description": "Handle edge case X",
  "parent": "T001",
  "passes": false,
  "discovered_during": "iteration_3"
}
```

**Rules**:
- Max 5 sub-tasks per task (prevents scope creep)
- Sub-tasks must complete before parent
- Logged in activity.md for review

## Commit Message Format

```
{type}(scope): {description} ({task_id}, {linear_id})

Types: feat, fix, test, refactor, docs, chore
```

**Examples**:
- `feat(catalog-polaris): add namespace creation (T001, FLO-33)`
- `test(compute-duckdb): add profile generation tests (T002.1, FLO-34)`

## Monitoring

Human can check progress anytime:
```
/ralph.status
```

### Notification Events

| Event | Notification |
|-------|-------------|
| Task complete | Linear comment |
| Task blocked | Slack/Terminal alert |
| Security finding | Urgent alert |
| All complete | Ready for review signal |

## Configuration

See `.ralph/config.yaml`:
```yaml
orchestration:
  max_iterations_per_task: 15
  stale_worktree_hours: 24
  auto_cleanup: true

quality_gates:
  per_iteration:
    - lint
    - typecheck
    - unit_tests
    - security
    - constitution
```

## Next Step

When all agents signal COMPLETE:
```
READY_FOR_REVIEW
```

Proceed to [Phase C: Pre-PR Review](03-pre-pr-review.md)
