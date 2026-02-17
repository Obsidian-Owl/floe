# Workflow Quick Reference

Quick reference for the floe development workflow with Specwright quality gates and automation.

## Specwright Workflow

```
Design:    /sw-design -> approve design
Plan:      /sw-plan -> work units with acceptance criteria
Build:     /sw-build -> TDD implementation, commit per task
Verify:    /sw-verify -> fix findings -> re-verify
Ship:      /sw-ship -> PR with evidence
```

### Commands

| Command | Purpose |
|---------|---------|
| `/sw-design` | Research codebase, design solution |
| `/sw-plan` | Break design into work units with specs |
| `/sw-build` | TDD implementation of next work unit |
| `/sw-verify` | Run quality gates (tests, security, wiring, spec) |
| `/sw-ship` | Create PR with gate evidence |
| `/sw-status` | Check current work state and gate results |
| `/sw-audit` | Periodic codebase health check |

## Quality Agents

### Test Quality Agents

| Agent | Model | Purpose | Invocation |
|-------|-------|---------|------------|
| `test-requirement-mapper` | Sonnet | @requirement coverage, gap analysis | Pre-PR |
| `test-design-reviewer` | Opus | Test architecture, patterns, maintainability | Manual/Full review |
| `test-debt-analyzer` | Sonnet | Consolidated test debt analysis | Pre-PR |

### Code Quality Agents

| Agent | Model | Purpose | Invocation |
|-------|-------|---------|------------|
| `code-pattern-reviewer` | Sonnet | Module anti-patterns, refactoring | Pre-PR |
| `security-scanner` | Sonnet | OWASP, secrets, injection | Pre-PR |
| `dead-code-detector` | Sonnet | Unused code, orphaned files | Pre-PR |
| `performance-debt-detector` | Sonnet | N+1, O(n²), sync in async | Pre-PR |

### Platform-Specific Agents

| Agent | Model | Purpose | Invocation |
|-------|-------|---------|------------|
| `plugin-quality` | Opus | 11 floe plugin types testing | Pre-PR |
| `contract-stability` | Opus | CompiledArtifacts contract | Pre-PR |
| `critic` | Opus | Ruthless plan/implementation reviewer | Pre-PR (blocking) |
| `docker-log-analyser` | Sonnet | Context-efficient container logs | On demand |
| `helm-debugger` | Sonnet | Context-efficient K8s debugging | On demand |

## Quality Gates (Specwright)

Gate results are tracked in `.specwright/state/workflow.json`:

| Gate | What It Checks |
|------|---------------|
| `gate-build` | Build and test commands pass |
| `gate-tests` | Test quality, assertion strength, mock discipline |
| `gate-security` | Secrets, injection, sensitive data |
| `gate-wiring` | Unused exports, orphaned files, layer violations |
| `gate-spec` | Every acceptance criterion has evidence |

### Running Gates

```bash
# Run all gates
/sw-verify

# Check gate status
/sw-status
```

## Quality Scripts

```bash
# Architecture drift detection (runs automatically via hook)
./scripts/check-architecture-drift [file]

# Pre-PR quality gate (runs automatically before gh pr create)
./scripts/pre-pr-gate

# Invoke specific agent
./scripts/invoke-agent test-requirement-mapper tests/unit/test_compiler.py

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
- Must have passing Specwright gates (`/sw-verify`)
- Must have critic OKAY verdict

## Model Tier Routing

| Tier | Model | When Used |
|------|-------|-----------|
| LOW | Haiku | Fast, focused analysis (single file) |
| MEDIUM | Sonnet | Module analysis, cross-file patterns |
| HIGH | Opus | Architecture review, critic decisions |

## Quick Fixes

### "Pre-PR gate failed"

Run the quality gates:
```bash
/sw-verify
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
|------|---------:|
| `.claude/settings.json` | Hook configuration |
| `.claude/agents/*.md` | Agent definitions |
| `.claude/skills/*/SKILL.md` | Skill definitions |
| `.specwright/state/workflow.json` | Work unit state and gate results |
| `.specwright/work/{id}/` | Design, spec, plan, evidence per work unit |
| `tests/fixtures/golden/` | Contract baselines |

## References

- Testing standards: `TESTING.md`
- Architecture: `docs/architecture/`
- Constitution: `.specify/memory/constitution.md`
