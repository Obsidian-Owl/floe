# floe Development Guide

**For**: Claude Code and AI developers | **Philosophy**: Build the future, not maintain the past

---

## Recovery (CRITICAL - Check First)

**If `.agent/epic-auto-mode` exists** → See `.claude/rules/epic-recovery.md` and continue automatically.

---

## Quick Start

```bash
bd linear sync --pull        # Sync from Linear
/speckit.implement           # Auto-implement next task
/speckit.test-review         # Pre-PR quality check
/speckit.pr                  # Create PR
```

| Command | Purpose |
|---------|---------|
| `make test` | All tests (K8s Kind cluster) |
| `make test-unit` | Fast unit tests |
| `make check` | Full CI (lint, type, security, test) |

---

## 8 Core Principles

1. **Technology Ownership**: dbt=SQL, Dagster=orchestration, Iceberg=storage, Polaris=catalog, Cube=semantic
2. **Plugin-First**: 11 types via entry points, ABCs required, >80% coverage
3. **Boundaries**: ENFORCE Iceberg/OTel/dbt/K8s; PLUG compute/catalog/orchestrator
4. **Contracts**: `CompiledArtifacts` is SOLE cross-package contract
5. **K8s-Native Testing**: Kind cluster, tests FAIL (no skip), 100% traceability
6. **Security First**: Pydantic validation, SecretStr, no eval/exec/shell=True
7. **Four Layers**: Foundation→Config→Services→Data (config flows DOWN only)
8. **Observability**: OTel traces, OpenLineage lineage, structured logging

---

## Development Phases

| Phase | Key Context | Skills |
|-------|-------------|--------|
| **Planning** | Constitution, architecture | specify, clarify, plan, tasks |
| **Coding** | Type hints, Pydantic v2, atomic commits | implement, dbt-skill, pydantic-skill |
| **Testing** | K8s-native, 100% markers, >80% coverage | test-review, testing-skill |
| **Pre-PR** | Quality gates MUST pass | wiring-check, merge-check, arch-review |

---

## Architecture

### Four-Layer Model

```
Layer 1: FOUNDATION     → PyPI packages, plugin interfaces
Layer 2: CONFIGURATION  → OCI registry artifacts (manifest.yaml)
Layer 3: SERVICES       → K8s Deployments (Dagster, Polaris, Cube)
Layer 4: DATA           → K8s Jobs (dbt run, dlt ingestion)
```

### Two-File Configuration

| File | Owner | Changes |
|------|-------|---------|
| `manifest.yaml` | Platform Team | Rarely |
| `floe.yaml` | Data Engineers | Frequently |

### Plugin Types (11)

**ENFORCED**: Iceberg, dbt, OpenTelemetry, OpenLineage, Kubernetes
**PLUGGABLE**: Compute, Orchestrator, Catalog, Semantic, Ingestion, Storage

---

## Workflow: SpecKit + Beads + Linear

**Source of Truth**: Linear → **Local Cache**: Beads → **Planning**: SpecKit

```
Planning:   specify → clarify → plan → tasks → taskstolinear
Implement:  bd linear sync --pull → /speckit.implement → commit → loop
Pre-PR:     test-review → wiring-check → merge-check → /speckit.pr
```

---

## Context Management

### Agent Delegation (MANDATORY)

| Task | Delegate To |
|------|-------------|
| Docker/K8s logs | `docker-log-analyser` or `helm-debugger` |
| dbt work | `dbt-skill` |
| Pydantic models | `pydantic-skill` |
| Complex exploration | `Task(Explore)` agent |

### Progressive Disclosure

- Point to detailed docs, don't paste them
- Rules in `.claude/rules/` - read when working on specific domain
- Architecture in `docs/architecture/` - reference, don't copy

---

## Code Standards

**Pre-commit**:
- Type hints on ALL functions (`mypy --strict`)
- Pydantic v2 syntax (`@field_validator`, `model_config`)
- Ruff linting, >80% coverage
- No `eval`, `exec`, `shell=True`, hardcoded secrets

**See**: `.claude/rules/python-standards.md`, `.claude/rules/sonarqube-quality.md`

---

## Testing

**K8s-Native ONLY** - All tests run in Kind cluster

| Tier | Location | Needs Services? |
|------|----------|----------------|
| Unit | `tests/unit/` | No (mocks) |
| Contract | `tests/contract/` (ROOT) | No (schema) |
| Integration | `tests/integration/` | Yes (K8s) |
| E2E | `tests/e2e/` | Yes (full stack) |

**Rules**: Tests FAIL never skip, `@pytest.mark.requirement()` on all, no `time.sleep()`

**See**: `TESTING.md`, `.claude/rules/testing-standards.md`

---

## Memory Workflow

```bash
./scripts/memory-search "query"              # Search prior context
./scripts/memory-save --decisions "..." --issues "FLO-123"  # Save decisions
```

Session start hook auto-queries for prior context.

---

## Key References

| Topic | Location |
|-------|----------|
| Architecture | `docs/architecture/ARCHITECTURE-SUMMARY.md` |
| Testing | `TESTING.md` |
| Linear Workflow | `docs/guides/linear-workflow.md` |
| Constitution | `.specify/memory/constitution.md` |
| Epic Recovery | `.claude/rules/epic-recovery.md` |
| Cognee API | `.claude/rules/cognee-api.md` |

---

## Rules (Progressive Disclosure)

Read when working on specific domain:
- `.claude/rules/python-standards.md` - Type hints, Pydantic v2
- `.claude/rules/testing-standards.md` - Test organization, markers
- `.claude/rules/component-ownership.md` - Technology boundaries
- `.claude/rules/pydantic-contracts.md` - Contract versioning
- `.claude/rules/security.md` - Input validation, secrets
- `.claude/rules/agent-delegation.md` - Context preservation
- `.claude/rules/skill-invocation.md` - Skill triggers
