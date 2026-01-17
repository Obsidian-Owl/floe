---
name: speckit-pr
description: Create PR with Linear integration and quality summary. Use when ready to merge an Epic branch to main.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Overview

Automate PR creation with:
- Link all completed Linear issues
- Generate PR description from spec.md + tasks summary
- Run quality gates automatically
- Create standardized PR format

## Prerequisites

Before running this skill:
1. All tasks in `.linear-mapping.json` should be marked Done (or manual override)
2. `/speckit.test-review` should pass (or run automatically)
3. `/speckit.integration-check` should pass (or run automatically)
4. On a feature branch (not main)

## Memory Integration

### After Completion
Save PR decisions:
```bash
./scripts/memory-save --decisions "PR created for {epic}: {summary}" --issues "{LinearIDs}"
```

## Constitution Alignment

This skill enforces project principles:
- **Traceability**: Every PR links to Linear issues
- **Quality Gates**: Tests and integration checks pass before PR

## Workflow

### 1. Detect Epic Context

```bash
# Get current branch
git rev-parse --abbrev-ref HEAD

# Find feature directory
.specify/scripts/bash/check-prerequisites.sh --json --paths-only
```

Parse:
- Branch name (e.g., `2a-manifest-validation`)
- Feature directory path
- Epic identifier

### 2. Load Linear Mapping

Read `$FEATURE_DIR/.linear-mapping.json` to get:
- All task mappings (TaskID: Linear ID)
- Feature metadata (project, epic label)

### 3. Verify Task Completion

Query Linear for each task status:
```
mcp__plugin_linear_linear__get_issue({id: linearId})
```

**If tasks remain incomplete:**
- List incomplete tasks with Linear URLs
- Ask user: "Continue with partial completion?" via AskUserQuestion
- If no, stop and suggest `/speckit.implement`

### 4. Run Quality Gates (if not already run)

**Test Review:**
```
/speckit.test-review
```
- If P0 issues exist: STOP and show issues
- If P1/P2 only: WARN but allow continue

**Integration Check:**
```
/speckit.integration-check
```
- If Blocked: STOP and show issues
- If Caution: WARN but allow continue
- If Ready: Continue

### 5. Generate PR Description

Build PR body from:

**Summary** (from spec.md):
- Extract Overview/Context section
- Summarize to 2-3 bullet points

**Changes** (from tasks.md):
- List completed tasks with task IDs
- Group by phase/user story

**Linear Issues**:
- List all Linear identifiers with URLs
- Format: `- [FLO-123](url): Task description`

**Test Plan** (from tasks.md test tasks):
- Extract test-related tasks
- List as verification checklist

### 6. Create Pull Request

```bash
gh pr create --title "{type}({scope}): {epic-title}" --body "$(cat <<'EOF'
## Summary

{2-3 bullet summary from spec.md}

## Changes

{List of completed tasks}

## Linear Issues

{List of FLO-### links}

## Test Plan

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Contract tests pass
- [ ] /speckit.test-review clean
- [ ] /speckit.integration-check Ready

---

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 7. Update Linear Issues

For each completed task:
```
mcp__plugin_linear_linear__create_comment({
  issueId: linearId,
  body: "PR created: {PR_URL}"
})
```

### 8. Report Completion

Output:
- PR URL
- Linear issues linked
- Quality gate summary
- Next steps (review, merge)

## Output Format

```markdown
## Pull Request Created

**PR**: {PR_URL}
**Branch**: {branch} -> main
**Epic**: {epic-identifier}

---

### Linear Issues Linked

| Task | Linear | Status |
|------|--------|--------|
| T001 | [FLO-33](url) | Done |
| T002 | [FLO-34](url) | Done |
| ...  | ... | ... |

---

### Quality Gates

| Gate | Status | Details |
|------|--------|---------|
| Test Review | status | {summary} |
| Integration Check | status | {summary} |
| All Tasks Done | status | {count}/{total} |

---

### Next Steps

1. Request review from team
2. Address review feedback
3. Merge when approved
4. Delete feature branch after merge
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Not on feature branch | On main or detached HEAD | Checkout feature branch |
| No Linear mapping | Tasks not synced to Linear | Run `/speckit.taskstolinear` |
| Tasks incomplete | Work not finished | Run `/speckit.implement` |
| Quality gate failed | Tests/checks failing | Fix issues first |
| PR already exists | PR created previously | Show existing PR URL |

## Handoff

After completing this skill:
- **Get review**: Share PR URL with team
- **Address feedback**: Make changes as needed
- **Merge**: Merge when approved

## References

- **[Linear Workflow Guide](../../../docs/guides/linear-workflow.md)** - Full workflow documentation
- **[speckit.test-review](../speckit-test-review/SKILL.md)** - Test quality review
- **[speckit.integration-check](../speckit-integration-check/SKILL.md)** - Pre-PR validation
