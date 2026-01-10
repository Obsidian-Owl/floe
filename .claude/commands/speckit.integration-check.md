---
description: Validate this Epic branch against main and detect contract changes before PR creation
handoffs:
  - label: "Review tests"
    agent: speckit.test-review
    prompt: "Integration check passed. Review test quality?"
    send: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Goal

Validate that this Epic branch is ready to merge to main by detecting:
- Contract schema changes that may affect other Epics
- Merge conflicts with main
- Test failures when rebased on latest main
- Architecture compliance issues

This command answers: **Is this Epic safe to merge?**

## Operating Constraints

**READ-ONLY ANALYSIS**: Do not modify any files or create commits. Output analysis and recommendations only.

**CURRENT BRANCH FOCUS**: This command validates the current worktree's branch against main. It does not attempt to merge multiple Epic branches together (the user manages cross-Epic coordination via Linear).

**REBASE SIMULATION**: The validation simulates a rebase on main without actually modifying the branch. If conflicts are detected, report them without resolution.

## Execution Steps

### 1. Gather Context

Determine the current branch and its relationship to main.

**Information to collect:**
- Current branch name (typically a numbered feature branch like `001-plugin-registry` or `epic-1-*`)
- Current commit hash
- Main branch latest commit hash
- Commits ahead of main (this Epic's changes)
- Commits behind main (changes to rebase onto)

**Report to user:**
- Branch name and Epic identifier
- How many commits ahead/behind main
- Last sync date with main (when branch last rebased)

### 2. Detect Contract Changes

Identify changes to cross-package contracts that may affect other Epics.

**Contract files to check:**
- `packages/floe-core/src/floe_core/schemas.py` (CompiledArtifacts)
- `packages/floe-core/src/floe_core/plugin_interfaces.py` (Plugin ABCs)
- Any file matching `packages/*/src/**/schemas.py` or `packages/*/src/**/models.py` (package contracts)
- Any file matching `plugins/*/src/**/schemas.py` or `plugins/*/src/**/models.py` (plugin contracts)
- Any file in `tests/contract/` (contract test changes)

**For each contract file changed:**
- Determine if change is ADDITIVE (new optional field) or BREAKING (removed field, type change, required field added)
- List the specific changes (field names, type modifications)
- Assess impact: which other packages import from this file

**Classification:**
- **Safe**: Additive changes only (new optional fields, new methods with defaults)
- **Caution**: Changes to plugin ABCs that existing plugins must implement
- **Breaking**: Removed fields, type changes, new required fields without defaults

### 3. Check for Merge Conflicts

Simulate merging main into the current branch to detect conflicts.

**Process:**
- Fetch latest main without switching branches
- Use `git merge-tree` to detect conflicts without modifying working directory (requires Git 2.30+)
- Alternative for older Git: create temporary worktree, attempt merge, report conflicts, clean up
- Identify files with conflicts

**For each conflict:**
- File path
- Conflict type (content conflict, file deleted on one side, etc.)
- Lines affected (approximate)

**If no conflicts:** Report clean merge status

### 4. Validate Against Latest Main

Run validation checks as if the branch were rebased on latest main.

**Contract Tests:**
- Run contract tests from `tests/contract/` directory
- These validate cross-package integration points
- Report pass/fail for each test

**Type Checking:**
- Run mypy on changed packages
- Focus on interface compatibility, not internal implementation

**Architecture Compliance** (inline checks, not agent delegation):
- Verify import boundaries in changed files:
  - floe-core should not import from plugin packages
  - Plugin packages should only import from floe-core interfaces
  - No cross-plugin imports (plugin A importing from plugin B)
- Check for layer violations in new code:
  - No runtime config modification from data layer code
  - Plugin implementations use ABC interfaces correctly

### 5. Assess Merge Readiness

Based on findings, determine overall merge readiness.

**Readiness Levels:**

| Level | Criteria | Recommendation |
|-------|----------|----------------|
| **Ready** | No conflicts, no breaking changes, all tests pass | Proceed with PR |
| **Caution** | Additive contract changes or minor conflicts | Review changes, coordinate with team |
| **Blocked** | Breaking contract changes, test failures, or significant conflicts | Resolve issues before PR |

### 6. Generate Report

Produce a structured markdown report.

## Output Format

```markdown
## Integration Check Report

**Branch**: {branch-name}
**Epic**: {epic-identifier}
**Checked**: {timestamp}

---

### Summary

| Check | Status | Details |
|-------|--------|---------|
| Merge Conflicts | {status} | {count} files |
| Contract Changes | {status} | {classification} |
| Contract Tests | {status} | {pass}/{total} |
| Architecture | {status} | {summary} |

**Overall Readiness**: {Ready / Caution / Blocked}

---

### Merge Status

**Commits ahead of main**: {N}
**Commits behind main**: {N}
**Last rebased**: {date or "Never"}

{If conflicts exist:}

#### Conflicts Detected

| File | Type | Action Required |
|------|------|-----------------|
| {path} | {type} | {recommendation} |

---

### Contract Analysis

{If no contract changes:}
No contract files modified in this branch.

{If contract changes detected:}

#### Modified Contracts

| File | Change Type | Impact |
|------|-------------|--------|
| {path} | {Additive/Breaking} | {affected packages} |

#### Change Details

**{file-path}**:
- {description of change}
- Affected consumers: {list of importing packages}

---

### Test Results

**Contract Tests**: {pass}/{total}

{If failures:}
| Test | Status | Error |
|------|--------|-------|
| {test-name} | Failed | {brief error} |

---

### Architecture Compliance

{Summary of import boundary and layer violation checks}

| Check | Status | Details |
|-------|--------|---------|
| Import boundaries | {status} | {violations found or "Clean"} |
| Layer compliance | {status} | {violations found or "Clean"} |
| Plugin patterns | {status} | {issues found or "Correct"} |

---

### Recommendations

{Based on readiness level:}

**Ready**:
1. Create PR targeting main
2. Request review from {suggested reviewers based on files changed}
3. Merge when approved

**Caution**:
1. {Specific action for contract changes}
2. {Specific action for conflicts}
3. Coordinate with team on merge timing
4. Consider notifying other Epic owners of contract changes

**Blocked**:
1. {Specific blocker and resolution steps}
2. Re-run `/speckit.integration-check` after resolving
3. Do not create PR until status is Ready or Caution

---

### Next Steps

- [ ] {First action item}
- [ ] {Second action item}
- [ ] Re-run `/speckit.integration-check` to verify (if changes made)
```

## Key Rules

### Contract Change Classification

**Additive (Safe)**:
- New optional field with default value
- New method on ABC with default implementation
- New enum value (if consumers use exhaustive matching, flag as Caution)
- New class that doesn't modify existing interfaces

**Breaking**:
- Removed field or method
- Changed field type (even if compatible at runtime)
- New required field without default
- Renamed field or method
- Changed method signature (parameters, return type)

### Merge Conflict Guidance

When conflicts are detected, provide actionable guidance:
- For schema conflicts: Recommend reviewing both changes and merging semantically
- For test conflicts: Recommend keeping both test cases
- For implementation conflicts: Recommend rebasing and resolving manually

### Architecture Boundaries

Flag violations of these boundaries:
- floe-core should not import from plugin packages
- Plugin packages should only import from floe-core interfaces
- No package should import from another plugin package
- Test files should not be in production code paths

## When to Use

- **Before creating a PR** for any Epic branch
- **After significant changes** to contracts or interfaces
- **When main has advanced** significantly since last rebase
- **Before merging** to catch last-minute conflicts

## Related Commands

- `/speckit.test-review` - Detailed test quality analysis
- `/speckit.implement` - Task implementation workflow
- `/speckit.analyze` - Cross-artifact consistency check

## References

- **Architecture**: `docs/architecture/ARCHITECTURE-SUMMARY.md`
- **Contracts**: `.claude/rules/pydantic-contracts.md`
- **Testing**: `TESTING.md`
- **Linear Workflow**: `docs/guides/linear-workflow.md`
