---
name: speckit-merge-check
description: Validate Epic branch merge readiness - contract stability, merge conflicts, and architecture compliance. Use before PR.
user_invocable: true
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

This skill answers: **Is this Epic safe to merge?**

## Operating Constraints

**READ-ONLY ANALYSIS**: Do not modify any files or create commits. Output analysis and recommendations only.

**CURRENT BRANCH FOCUS**: This skill validates the current worktree's branch against main. It does not attempt to merge multiple Epic branches together (the user manages cross-Epic coordination via Linear).

**REBASE SIMULATION**: The validation simulates a rebase on main without actually modifying the branch. If conflicts are detected, report them without resolution.

## Memory Integration

### After Completion
Save pre-PR decisions:
```bash
./scripts/memory-save --decisions "Merge check for {epic}: {findings}" --issues "{LinearIDs}"
```

## Constitution Alignment

This skill validates adherence to project principles:
- **Contract-Driven**: CompiledArtifacts changes are flagged
- **Technology Ownership**: Import boundaries checked
- **K8s-Native**: Architecture compliance verified

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

---

### Contract Analysis

{Contract change details}

---

### Test Results

**Contract Tests**: {pass}/{total}

---

### Architecture Compliance

{Import boundary and layer violation checks}

---

### Recommendations

{Based on readiness level}

---

### Next Steps

- [ ] {First action item}
- [ ] {Second action item}
- [ ] Re-run `/speckit.merge-check` to verify (if changes made)
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

## Handoff

After completing this skill:
- **Review tests**: Run `/speckit.test-review` if needed
- **Create PR**: Run `/speckit.pr` when Ready
- **Fix issues**: Address Blocked/Caution items first

## References

- **Architecture**: `docs/architecture/ARCHITECTURE-SUMMARY.md`
- **Contracts**: `.claude/rules/pydantic-contracts.md`
- **Testing**: `TESTING.md`
