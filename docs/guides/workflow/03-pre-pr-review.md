# Phase C: Pre-PR Review

Collaborative human-AI session for thorough quality validation before PR creation.

## Overview

Phase C returns to human-AI collaboration. Claude presents analysis, human makes decisions. No surprises in production.

## Workflow

```
/ralph.integrate [epic]
        |
        v
Rebase all feature branches on main
        |
        v
/speckit.test-review
        |
        +---> Present: Test quality analysis
        +---> AskUserQuestion: Accept findings or request changes?
        |
        v
/speckit.integration-check
        |
        +---> Present: Contract stability report
        +---> AskUserQuestion: Accept or investigate?
        |
        v
/security-review
        |
        +---> Present: Security findings
        +---> AskUserQuestion: Accept or remediate?
        |
        v
/arch-review
        |
        +---> Present: Constitution compliance report
        +---> AskUserQuestion: Accept or refactor?
        |
        v
Human confirms: "Ready for PR"
        |
        v
gh pr create --base main
        |
        v
/ralph.cleanup
```

## Commands

### /ralph.integrate [epic]

Prepares all completed tasks for review.

**Process**:
1. Identify all completed worktrees for the epic
2. Fetch latest main branch
3. Rebase each feature branch on main
4. Detect and report conflicts
5. Run full test suite on rebased code

**Output**:
```
INTEGRATION STATUS - EP001

Worktrees to integrate: 5
Rebased successfully: 4
Conflicts detected: 1 (T003)

Conflict in T003:
  - packages/floe-core/schemas.py
  - Cause: CompiledArtifacts schema changed on main

Action required: Resolve T003 conflict before proceeding
```

### /speckit.test-review

Semantic analysis of test quality.

**Checks**:
- Purpose clarity: Is intent obvious?
- Correctness: Could test pass while code broken?
- Isolation: Tests independent and deterministic?
- Maintainability: Brittle to implementation changes?
- Type appropriateness: Right test level?

**floe-Specific Checks** (parallel agents):
- `plugin-quality`: Plugin testing completeness
- `contract-stability`: Contract regression detection
- `architecture-compliance`: Framework patterns validated

**Output**:
```
TEST QUALITY REPORT

| Aspect | Status | Key Finding |
|--------|--------|-------------|
| Test Design | PASS | Clear intent, good isolation |
| Plugin Coverage | WARN | Missing lifecycle tests for CatalogPlugin |
| Contract Stability | PASS | No breaking changes |
| Architecture | PASS | Technology ownership respected |

Priority Actions:
- P1: Add lifecycle tests for CatalogPlugin (test_startup, test_shutdown)
```

### /security-review

Claude Code built-in security vulnerability scan.

**Categories Checked**:
- Injection attacks (SQL, command, XSS)
- Authentication/authorization issues
- Data exposure (hardcoded secrets, PII logging)
- Cryptographic weaknesses
- Input validation gaps
- Code execution vulnerabilities

**Output**:
```
SECURITY REVIEW

Files scanned: 23
Findings: 2

HIGH: packages/floe-core/auth.py:45
  - Hardcoded API key in source
  - Remediation: Use SecretStr and environment variable

LOW: plugins/floe-compute-duckdb/client.py:112
  - SQL string concatenation
  - Note: Input is internal, but consider parameterization
```

### /arch-review

Architecture alignment with constitution principles.

**Checks All 8 Principles**:
1. Technology Ownership (dbt owns SQL)
2. Plugin-First Architecture
3. Enforced vs Pluggable
4. Contract-Driven Integration
5. K8s-Native Testing
6. Security First
7. Four-Layer Architecture
8. Observability By Default

**Output**:
```
ARCHITECTURE COMPLIANCE

Principle                  | Status | Notes
--------------------------|--------|-------
I. Technology Ownership   | PASS   | No SQL in Python
II. Plugin-First          | PASS   | Entry points used
III. Enforced/Pluggable   | PASS   | Standards respected
IV. Contract-Driven       | PASS   | Pydantic v2 syntax
V. K8s-Native Testing     | WARN   | 1 test using time.sleep()
VI. Security First        | PASS   | SecretStr used
VII. Four-Layer           | PASS   | No layer violations
VIII. Observability       | PASS   | OTel traces present
```

### /ralph.cleanup

Removes worktrees after successful PR merge.

**Process**:
1. Verify PR merged to main
2. Delete worktree directories
3. Prune git worktree metadata
4. Update manifest.json
5. Archive activity logs

## Human Decision Points

| Review | Decision Options |
|--------|-----------------|
| Test quality | Accept / Request changes / Defer to follow-up |
| Contract stability | Accept / Investigate breaking change / Revert |
| Security findings | Accept risk / Remediate / Block PR |
| Architecture | Accept / Refactor / Document exception |

## PR Creation

After all reviews pass:

```bash
gh pr create --base main --title "EP001: Feature implementation" --body "$(cat <<'EOF'
## Summary
- Implemented authentication middleware
- Added catalog integration
- Full test coverage

## Test Plan
- [x] Unit tests pass (23/23)
- [x] Integration tests pass (8/8)
- [x] Contract tests pass (5/5)
- [x] Security review: 0 high findings
- [x] Architecture review: Compliant

## Linear Issues
- FLO-33: T001 Authentication
- FLO-34: T002 Catalog
- FLO-35: T003 Integration

Generated with Claude Code
EOF
)"
```

## CI Validation

After PR creation, CI runs:
1. `make lint` - Ruff formatting check
2. `make typecheck` - mypy strict
3. `make test-unit` - Unit tests
4. `make test-contract` - Contract tests
5. Security scan via GitHub Action
6. SonarCloud analysis

## Merge Workflow

```
PR created
    |
    v
CI validates
    |
    v
Human reviews
    |
    v
Merge to main
    |
    v
/ralph.cleanup
    |
    v
Done
```

## Best Practices

1. **Address P0 issues before PR** - High-priority findings block merge
2. **Document accepted risks** - If accepting LOW findings, add comment
3. **Verify CI passes locally** - Run `make check` before PR
4. **Review activity logs** - Check `.agent/activity.md` for decisions made
5. **Clean up worktrees** - Don't leave stale worktrees

## Troubleshooting

### Conflict During Rebase

```bash
# In worktree with conflict
cd floe-agent-ep001-t003
git status  # See conflicting files
# Resolve conflicts manually
git add -A
git rebase --continue
```

### Security Finding False Positive

```markdown
<!-- In PR description -->
## Security Notes
- LOW finding in client.py:112 - Accepted: Input is internal constant
```

### Architecture Exception

If constitution violation is intentional:
1. Document justification in PR
2. Add to plan.md Complexity Tracking section
3. Get explicit approval from reviewer

## Next Steps

After merge:
1. `/ralph.cleanup` removes worktrees
2. Update Linear issues with PR link
3. Start next epic or continue with remaining tasks
