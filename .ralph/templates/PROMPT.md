# Agent Instructions for Task ${TASK_ID}

## Context

You are implementing task **${TASK_ID}** (Linear: ${LINEAR_ID}) for the floe project.
Your worktree is isolated - you cannot affect other agents working in parallel.

**Epic**: ${EPIC}
**Task Description**: ${TASK_DESCRIPTION}
**Iteration**: ${ITERATION} of ${MAX_ITERATIONS}

## State Files

| File | Purpose |
|------|---------|
| `.agent/plan.json` | Current subtask status (passes: true/false) |
| `.agent/activity.md` | Your progress log (append-only) |
| `.agent/constitution.md` | Architecture principles to validate |

## Your Workflow (ONE ITERATION)

### Step 1: Read Current State
```bash
cat .agent/plan.json
cat .agent/activity.md | tail -20
```

### Step 2: Identify Next Subtask
Find the first subtask where `"passes": false` in plan.json.
If all subtasks pass, signal COMPLETE.

### Step 3: Implement Subtask
- Make atomic, focused changes
- Follow TDD: write test first, then implementation
- Use existing patterns from the codebase

### Step 4: Run All Quality Gates

```bash
# 1. Lint
uv run ruff check . --fix
uv run ruff format .

# 2. Type Check
uv run mypy --strict packages/ plugins/

# 3. Unit Tests
uv run pytest tests/unit/ -v --tb=short

# 4. Security Review
/security-review

# 5. Constitution Validation
python .ralph/scripts/validate-constitution.py --files $(git diff --name-only HEAD~1)
```

### Step 5: Update State

**If ALL gates pass:**
1. Update `.agent/plan.json`: Set subtask `"passes": true`
2. Create atomic git commit:
   ```bash
   git add -A
   git commit -m "${COMMIT_TYPE}(${SCOPE}): ${DESCRIPTION} (${TASK_ID}, ${LINEAR_ID})"
   ```
3. Log completion in `.agent/activity.md`

**If ANY gate fails:**
1. Log failure in `.agent/activity.md`
2. Attempt fix (max 3 retries per gate)
3. If still failing: Create sub-task and signal BLOCKED

### Step 6: Check Completion

If ALL subtasks in plan.json have `"passes": true`:
```
<promise>COMPLETE</promise>
```

If blocked and need human help:
```
<promise>BLOCKED</promise>
Reason: [describe the blocking issue]
```

## Constitution Validation Checklist

Before completing ANY iteration, verify:

- [ ] **I. Technology Ownership**: No SQL parsing in Python (dbt owns SQL)
- [ ] **II. Plugin-First**: Using entry points, not hardcoded implementations
- [ ] **III. Enforced Standards**: Iceberg, OTel, OpenLineage, dbt, K8s
- [ ] **IV. Contract-Driven**: Changes to CompiledArtifacts are versioned
- [ ] **V. K8s-Native Testing**: Integration tests run in Kind
- [ ] **VI. Security First**: SecretStr for credentials, no eval/exec/shell=True
- [ ] **VII. Four-Layer Architecture**: No Layer 4 modifying Layer 2
- [ ] **VIII. Observability**: OTel traces for new operations

## Files You May Modify

${ALLOWED_FILES}

## Files You MUST NOT Modify

- Any file outside your worktree
- `.git/` directory
- Other agents' `.agent/` directories
- `.ralph/manifest.json` (orchestrator owns this)

## Sub-Task Creation

If you discover an issue during implementation:

1. Create sub-task in plan.json:
   ```json
   {
     "id": "${TASK_ID}.N",
     "description": "Handle edge case X",
     "parent": "${TASK_ID}",
     "passes": false,
     "discovered_during": "iteration_${ITERATION}"
   }
   ```

2. Complete sub-task before continuing with parent task

3. Max 5 sub-tasks per task (prevents scope creep)

## Commit Message Format

```
${TYPE}(${SCOPE}): ${DESCRIPTION} (${TASK_ID}, ${LINEAR_ID})

Types: feat, fix, test, refactor, docs, chore
Scope: Package or module name
Description: Imperative mood, max 50 chars
```

Examples:
- `feat(catalog-polaris): add namespace creation (T001, FLO-33)`
- `test(compute-duckdb): add profile generation tests (T002.1, FLO-34)`
- `fix(core): handle empty manifest gracefully (T003, FLO-35)`

## Activity Log Format

Append to `.agent/activity.md`:

```markdown
## Iteration ${ITERATION} - ${TIMESTAMP}

**Subtask**: ${SUBTASK_ID} - ${SUBTASK_DESCRIPTION}
**Status**: ${PASS|FAIL|BLOCKED}

### Changes Made
- [file1.py]: Added X
- [file2.py]: Modified Y

### Gate Results
- Lint: PASS
- Type: PASS
- Test: PASS (12 passed, 0 failed)
- Security: PASS
- Constitution: PASS

### Notes
[Any observations, decisions, or issues encountered]
```

## Remember

1. **One subtask per iteration** - Stay focused
2. **All gates must pass** - No shortcuts
3. **Fresh context each iteration** - Don't assume prior state
4. **Log everything** - Traceability is critical
5. **Signal clearly** - COMPLETE or BLOCKED, nothing ambiguous
