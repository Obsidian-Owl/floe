# Claude Code Rules Quick Reference

**Purpose**: Single entry point for all project rules and standards

---

## Architecture & Ownership

| Rule | Focus | When to Reference |
|------|-------|-------------------|
| **component-ownership.md** | Technology boundaries (dbt owns SQL, Dagster owns orchestration, etc.) | Before implementing cross-component integration |
| **standalone-first.md** | Every feature works without SaaS Control Plane | Before adding any SaaS-dependent features |

**Core Principle**: Each technology owns its domain exclusively. Never cross boundaries (e.g., never parse SQL in Python - that's dbt's job).

---

## Python & Type Safety

| Rule | Focus | When to Reference |
|------|-------|-------------------|
| **python-standards.md** | Type hints, code quality, formatting, dependencies | Before writing any Python code |
| **pydantic-contracts.md** | Pydantic v2 syntax, contract design, secret management | Before creating schemas, configs, or API contracts |

**Core Principle**: Type hints on ALL functions. Pydantic for ALL data validation. SecretStr for ALL secrets.

---

## Testing & Quality

| Rule | Focus | When to Reference |
|------|-------|-------------------|
| **testing-standards.md** | Tests FAIL never skip, no hardcoded sleep, requirement traceability | Before writing any test |
| **test-organization.md** | Where to place tests (package vs root), tier selection (unit/contract/integration/E2E) | When creating new test files |
| **code-quality.md** | Code quality standards (credentials, duplicates, floats, etc.) | When writing Python code |
| **security.md** | Input validation, dangerous constructs, secret management, error handling | Before handling user input or secrets |

**Core Principle**: Tests are production code. No skips, no sleeps, full traceability. >80% coverage required.

**See Also**: [@TESTING.md](/Users/dmccarthy/Projects/floe-runtime/TESTING.md) for K8s-native testing patterns (900+ lines)

---

## Operations & Context Management

| Rule | Focus | When to Reference |
|------|-------|-------------------|
| **agent-delegation.md** | When to delegate to docker-log-analyser or helm-debugger subagents | Before analyzing logs or debugging K8s |
| **context-efficient-logging.md** | Never dump full logs, use `--tail=N`, delegate to subagents | Before running any log commands |
| **context-management.md** | Skill/subagent auto-invocation, trigger phrases, progressive disclosure | When creating new skills or subagents |
| **skill-invocation.md** | Skill trigger matrix (when to invoke pydantic-skill, dbt-skill, etc.) | When working on specific components |

**Core Principle**: Preserve main context. Delegate log analysis to subagents. Use progressive disclosure.

---

## Quick Decision Trees

### "Should I create a new rule?"
```
Is this enforcement-critical? (prevents bugs/security issues)
├─ YES → Is it < 300 lines?
│   ├─ YES → Create in .claude/rules/
│   └─ NO → Create in docs/ and link from rules
└─ NO → This is guidance, put in docs/ or CLAUDE.md
```

### "Where should my test go?"
```
See test-organization.md for complete decision tree.

Quick version:
- Imports from MULTIPLE packages? → tests/contract/ or tests/e2e/
- Single package, no external services? → packages/*/tests/unit/
- Single package, needs services? → packages/*/tests/integration/
```

### "Which skill should I invoke?"
```
See skill-invocation.md for trigger matrix.

Quick version (skills auto-invoke when you mention these):
- "Pydantic schema" → pydantic-skill
- "dbt model" → dbt-skill
- "Dagster asset" → dagster-skill
- "Iceberg table" → pyiceberg-skill
- "Polaris catalog" → polaris-skill
- "DuckDB lakehouse" → duckdb-lakehouse
- "Cube semantic layer" → cube-skill
- "Helm chart" / "K8s pod" → helm-k8s-skill
- "Writing tests" → testing-skill
```

---

## Progressive Disclosure Pattern

**Rules in .claude/rules/** are loaded at startup (concise, enforcement-only).

**For detailed guidance**, reference these docs:
- Architecture details → `docs/architecture/`
- Testing patterns → `TESTING.md`
- Development workflow → `CLAUDE.md`
- ADRs → `docs/architecture/adr/`

---

## Context Budget

**Baseline**: ~25-30k tokens per session
- CLAUDE.md: ~15-20k tokens
- .claude/rules/*.md: ~3-5k tokens
- Skill descriptions: ~2-3k tokens
- Settings + git status: ~1-2k tokens

**Target**: Keep rules under 5k tokens total (within optimal range).

---

## Maintenance Checklist

- [ ] Keep individual rules < 300 lines
- [ ] Link to detailed docs rather than duplicate content
- [ ] Update skill descriptions with current year (2026) in research queries
- [ ] Archive rules that haven't been referenced in 60 days
- [ ] Run `bd stats` monthly to verify rule effectiveness

---

**Last Updated**: 2026-01-06
