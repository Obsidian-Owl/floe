# Troubleshooting

Common issues and solutions for the Ralph Wiggum workflow.

## Agent Issues

### Agent Stuck in Loop

**Symptom**: Agent keeps retrying same subtask, iteration count climbing

**Causes**:
1. Flaky test
2. Non-deterministic behavior
3. Gate that can't pass

**Solutions**:

```bash
# 1. Check activity log
cd ../floe-agent-ep001-t001
cat .agent/activity.md | tail -50

# 2. Check which gate is failing
cat .agent/plan.json | jq '.gate_results'

# 3. Manually run the failing gate
uv run pytest tests/unit/ -v --tb=long  # If test failing

# 4. Fix issue and update plan.json
# Set iteration back if needed
```

### Agent Not Starting

**Symptom**: /ralph.spawn runs but no worktrees created

**Causes**:
1. No ready tasks in Linear
2. All tasks have unmet dependencies
3. Git worktree creation failed

**Solutions**:

```bash
# 1. Check Linear for ready tasks
# Query via MCP for backlog/unstarted status

# 2. Check for blocked dependencies
# Query with includeRelations: true

# 3. Check git worktree errors
git worktree list
git worktree prune
```

### Agent Blocked

**Symptom**: Agent signals BLOCKED, stops making progress

**Causes**:
1. Security finding requires human review
2. Gate can't be fixed automatically
3. Architecture violation

**Solutions**:

```bash
# 1. Check block reason
cd ../floe-agent-ep001-t001
cat .agent/plan.json | jq '.status, .block_reason'

# 2. Check activity log for details
cat .agent/activity.md | grep -A20 "BLOCKED"

# 3. Fix the issue manually
# ... make changes ...

# 4. Reset agent state
# Update plan.json: status = "in_progress"
# Run gate manually to verify fix
```

## Worktree Issues

### Worktree Already Exists

**Error**: `fatal: 'path' already exists`

**Solutions**:

```bash
# Remove and recreate
git worktree remove ../floe-agent-ep001-t001 --force
git worktree add ../floe-agent-ep001-t001 -b feature/ep001-t001 main
```

### Branch Already Checked Out

**Error**: `fatal: 'feature/ep001-t001' is already checked out`

**Solutions**:

```bash
# Find which worktree has the branch
git worktree list

# Remove that worktree first
git worktree remove <conflicting-worktree>

# Or delete the branch and recreate
git branch -D feature/ep001-t001
git worktree add ../floe-agent-ep001-t001 -b feature/ep001-t001 main
```

### Worktree Locked

**Error**: `fatal: 'path' is locked`

**Solutions**:

```bash
# Unlock the worktree
git worktree unlock ../floe-agent-ep001-t001

# If that fails, check for lock file
rm ../floe-agent-ep001-t001/.git/worktrees/*/locked 2>/dev/null
```

### Orphaned Worktree

**Symptom**: Worktree directory deleted but `git worktree list` still shows it

**Solutions**:

```bash
# Prune orphaned worktrees
git worktree prune

# Verify
git worktree list
```

## Quality Gate Issues

### Lint Keeps Failing

**Symptom**: Ruff check fails repeatedly

**Solutions**:

```bash
# 1. Run with verbose output
uv run ruff check . --verbose

# 2. Check for unfixable issues
uv run ruff check . --show-fixes

# 3. Fix specific issue
uv run ruff check . --select E501  # Specific rule

# 4. Update ruff if needed
uv sync --upgrade-package ruff
```

### Type Check Failures

**Symptom**: mypy errors persist after fixes

**Causes**:
1. Missing type stubs
2. Incorrect type annotations
3. Third-party library issues

**Solutions**:

```bash
# 1. Get detailed error
uv run mypy --strict packages/ --show-error-codes

# 2. Install missing stubs
uv add types-requests types-PyYAML

# 3. Check if issue is in dependencies
uv run mypy --strict packages/ --ignore-missing-imports

# 4. For stubborn third-party issues
# Add to pyproject.toml:
# [tool.mypy]
# [[tool.mypy.overrides]]
# module = "problematic_library.*"
# ignore_missing_imports = true
```

### Test Failures

**Symptom**: pytest fails intermittently

**Causes**:
1. Flaky test (timing issues)
2. Test pollution (shared state)
3. Missing fixtures

**Solutions**:

```bash
# 1. Run single test with verbose output
uv run pytest tests/unit/test_file.py::test_name -vvv

# 2. Check for shared state issues
uv run pytest tests/unit/ --forked  # Run each test in subprocess

# 3. Check fixture availability
uv run pytest tests/unit/ --fixtures

# 4. Run with random order to find pollution
uv run pytest tests/unit/ -p random_order
```

### Security Finding False Positive

**Symptom**: /security-review flags non-issue

**Solutions**:

```markdown
# Document in PR description
## Security Notes
- LOW finding in client.py:112 - Accepted: Input is internal constant
- Reason: The input parameter is not user-controlled

# Or add inline comment (for future reference)
# nosec: B108 - hardcoded tmp path is intentional for tests
```

### Constitution Violation

**Symptom**: Constitution check fails but code seems correct

**Causes**:
1. False positive in pattern matching
2. Legitimate exception case
3. Constitution needs updating

**Solutions**:

```bash
# 1. Check which principle failed
python .ralph/scripts/validate-constitution.py --files <file> --verbose

# 2. If legitimate exception, document it
# Add to plan.md Complexity Tracking section

# 3. If false positive, fix detection script
# Update .ralph/scripts/validate-constitution.py
```

## Linear Integration Issues

### MCP Connection Failed

**Error**: Linear MCP tool returns error

**Solutions**:

```bash
# 1. Check MCP server status
# Restart Claude Code session

# 2. Verify Linear API access
# Check Linear API token in environment

# 3. Fall back to cached state
# Use .linear-mapping.json if available
```

### Issue Not Found

**Error**: `Issue not found: FLO-XXX`

**Causes**:
1. Issue deleted in Linear
2. Wrong team/project
3. Typo in issue ID

**Solutions**:

```bash
# 1. Search by title instead
mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "query": "task title keywords"
})

# 2. Check issue was created
mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "project": "floe-01-plugin-system"
})

# 3. Recreate if needed
```

### Dependency Cycle

**Error**: Tasks have circular dependencies

**Solutions**:

```python
# 1. Query all issues and check blockedBy
issues = mcp__plugin_linear_linear__list_issues({
    "team": "floe",
    "project": project_id,
    "includeRelations": True
})

# 2. Build graph and detect cycle
# Find the cycle and break it

# 3. Update Linear to remove cyclic dependency
mcp__plugin_linear_linear__update_issue({
    "id": "FLO-33",
    "blockedBy": []  # Clear and re-add correct dependencies
})
```

## Integration Issues

### Rebase Conflicts

**Symptom**: `git rebase origin/main` fails with conflicts

**Solutions**:

```bash
# 1. See conflicting files
git status

# 2. Option A: Resolve manually
# Edit conflicting files
git add -A
git rebase --continue

# 3. Option B: Abort and retry later
git rebase --abort

# 4. Option C: Use merge instead (preserves history)
git merge origin/main
# Resolve conflicts
git commit
```

### PR CI Fails

**Symptom**: All local gates passed but CI fails

**Causes**:
1. Environment differences
2. Missing dependencies in CI
3. Cached local state not in commit

**Solutions**:

```bash
# 1. Check CI logs for specific error

# 2. Reproduce locally with clean state
git stash
git clean -fd
uv sync --frozen
make check

# 3. Ensure all changes committed
git status
git diff
```

## Recovery Procedures

### Recover From Crashed Agent

```bash
# 1. Check agent state
cd ../floe-agent-ep001-t001
cat .agent/plan.json

# 2. Determine last successful subtask
cat .agent/activity.md | grep "PASS"

# 3. Update plan.json to resume
# Set next incomplete subtask

# 4. Run gates manually to verify state
make check

# 5. Resume agent or manual completion
```

### Recover From Main Branch Divergence

```bash
# If main has moved significantly
cd ../floe-agent-ep001-t001

# 1. Fetch latest
git fetch origin main

# 2. Check divergence
git log --oneline HEAD..origin/main | wc -l

# 3. If minor, rebase
git rebase origin/main

# 4. If major, consider squash merge
git checkout -b temp-merge
git merge --squash origin/main
# Resolve conflicts, test, then replace original branch
```

### Complete Reset

```bash
# If everything is broken, start fresh

# 1. Remove all worktrees
git worktree list | grep "floe-agent" | cut -d' ' -f1 | xargs -I{} git worktree remove {} --force

# 2. Prune git state
git worktree prune
git gc

# 3. Reset Linear status
# Update issues to backlog state

# 4. Clear manifest
echo '{"schema_version":"1.0.0","active_agents":[],"completed_today":[]}' > .ralph/manifest.json

# 5. Re-spawn agents
/ralph.spawn [epic]
```

## Debugging Tips

### Enable Verbose Logging

```bash
# In agent worktree
export FLOE_DEBUG=1
export LOG_LEVEL=DEBUG
```

### Check System Resources

```bash
# Disk space (worktrees can grow)
df -h

# Memory (many agents = many processes)
free -h

# Open file handles
ulimit -n
```

### Validate Manifest

```bash
# Check manifest.json is valid
python -c "import json; json.load(open('.ralph/manifest.json'))"

# Check for stale entries
python -c "
import json
import os
manifest = json.load(open('.ralph/manifest.json'))
for agent in manifest['active_agents']:
    if not os.path.exists(agent['worktree_path']):
        print(f'STALE: {agent[\"worktree_path\"]}')
"
```

### Contact Points

- **Workflow issues**: Check `docs/guides/workflow/`
- **Linear issues**: Check Linear app directly
- **Git issues**: `git status`, `git log`, `git worktree list`
- **Quality gate issues**: Run gates manually with `--verbose`
