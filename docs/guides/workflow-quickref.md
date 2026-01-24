# Workflow Quick Reference

Quick reference for the floe development workflow with quality gates and automation.

## Quality Agent Overview

### Test Quality Agents

| Agent | Model | Purpose | Invocation |
|-------|-------|---------|------------|
| `test-edge-case-analyzer` | Haiku | Empty, null, bounds, error paths | PostToolUse on test files |
| `test-isolation-checker` | Haiku | Shared state, fixtures, determinism | PostToolUse on test files |
| `test-flakiness-predictor` | Sonnet | Random seeds, time.sleep, external deps | Pre-PR |
| `test-requirement-mapper` | Sonnet | @requirement coverage, gap analysis | Pre-PR |
| `test-duplication-detector` | Sonnet | Overlapping assertions, redundant tests | Pre-PR |
| `test-design-reviewer` | Opus | Test architecture, patterns, maintainability | Manual/Full review |

### Code Quality Agents

| Agent | Model | Purpose | Invocation |
|-------|-------|---------|------------|
| `code-pattern-reviewer-low` | Haiku | Single file anti-patterns | PostToolUse on source files |
| `code-pattern-reviewer` | Sonnet | Module anti-patterns, refactoring | Pre-PR |
| `security-scanner` | Sonnet | OWASP, secrets, injection | Pre-PR |
| `docstring-validator` | Haiku | Google-style, type hints | PostToolUse on source files |

### Quality Gate

| Agent | Model | Purpose | Invocation |
|-------|-------|---------|------------|
| `critic` | Opus | Ruthless plan/implementation reviewer | Pre-PR (blocking) |

## Workflow Commands

### Daily Development

```bash
# Start session - sync from Linear
bd linear sync --pull
bd ready                        # Show ready work

# Implement with auto-quality checks
/speckit.implement              # Single task (with confirmation)
/speckit.implement-epic         # All tasks (no confirmation)
```

### Pre-PR Checklist

```bash
# 1. Test quality review
/speckit.test-review

# 2. Wiring check (is new code connected?)
/speckit.wiring-check

# 3. Merge check (contracts, conflicts)
/speckit.merge-check

# 4. Critic approval (automatic via pre-pr-gate)
# Agent invoked automatically when running gh pr create

# 5. Create PR
/speckit.pr
```

### Quality Scripts

```bash
# Architecture drift detection (runs automatically via hook)
./scripts/check-architecture-drift [file]

# Pre-PR quality gate (runs automatically before gh pr create)
./scripts/pre-pr-gate

# Invoke specific agent
./scripts/invoke-agent test-edge-case-analyzer tests/unit/test_compiler.py

# Generate contract golden files
./scripts/generate-contract-golden [--force]
```

## Automatic Quality Checks

### PostToolUse Hooks (Non-blocking)

When you edit/write Python files, these run automatically:
- Black formatting (100 char line length)
- isort import sorting
- Architecture drift detection

### PreToolUse Hooks (Blocking)

When you run `gh pr create`:
- Pre-PR quality gate runs
- Must have passed /speckit.test-review
- Must have passed /speckit.wiring-check
- Must have passed /speckit.merge-check
- Must have critic OKAY verdict

## Quality State

Quality check results are tracked in `.agent/quality-state.json`:

```json
{
  "test_review_passed": true,
  "integration_check_passed": true,
  "critic_passed": true,
  "last_updated": "2026-01-21T08:00:00Z"
}
```

## Epic Auto-Mode Recovery

If context compacts during `/speckit.implement-epic`:

1. State is saved in `.agent/epic-auto-mode`
2. SessionStart hook detects the file
3. Claude automatically continues implementation
4. NO user confirmation needed

## Model Tier Routing

| Tier | Model | When Used |
|------|-------|-----------|
| LOW | Haiku | Fast, focused analysis (single file) |
| MEDIUM | Sonnet | Module analysis, cross-file patterns |
| HIGH | Opus | Architecture review, critic decisions |

## Quick Fixes

### "Pre-PR gate failed"

Run the required checks:
```bash
/speckit.test-review
/speckit.wiring-check
/speckit.merge-check
```

### "Architecture drift detected"

Check the violation, fix the code:
```bash
./scripts/check-architecture-drift path/to/file.py
```

Common violations:
- SQL parsing outside dbt package
- Layer 4 modifying Layer 2 configuration
- Direct FloeSpec usage outside floe-core

### "Critic rejected"

Review the critic's findings:
1. Address all CRITICAL issues
2. Verify claims in the plan
3. Add missing edge cases
4. Re-run critic

## Key Files

| File | Purpose |
|------|---------|
| `.claude/settings.json` | Hook configuration |
| `.claude/agents/*.md` | Agent definitions |
| `.claude/skills/*/SKILL.md` | Skill definitions |
| `.agent/epic-auto-mode` | Epic recovery state |
| `.agent/quality-state.json` | Quality check results |
| `tests/fixtures/golden/` | Contract baselines |

## References

- Full workflow guide: `docs/guides/linear-workflow.md`
- Testing standards: `TESTING.md`
- Architecture: `docs/architecture/`
- Constitution: `.specify/memory/constitution.md`
