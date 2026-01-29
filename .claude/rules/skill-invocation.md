# Skill Invocation Rules

## File Pattern Triggers (Auto-Invoke)

| Pattern | Skill | When |
|---------|-------|------|
| `*.sql`, `dbt_project.yml`, `profiles.yml` | `dbt-skill` | SQL/dbt work |
| `**/schemas/*.py`, `**/models/*.py`, `**/config*.py` | `pydantic-skill` | Schema/model work |
| `charts/**`, `**/templates/**`, Helm YAML | `helm-k8s-skill` | K8s deployment |
| `**/assets.py`, `**/resources.py`, `**/io_managers.py` | `dagster-skill` | Orchestration |
| `**/test_*.py`, `**/conftest.py` | `testing-skill` | Test writing |

## Skill Chains (See `.claude/skill-chains.json`)

| Chain | Skills | Trigger |
|-------|--------|---------|
| `epic-planning` | specify→clarify→plan→tasks→taskstolinear | "plan epic" |
| `pre-pr` | test-review + wiring-check + merge-check (parallel) | "pre-pr check" |
| `dbt-work` | dbt-skill→pydantic-skill | `*.sql` files |
| `k8s-deploy` | helm-k8s-skill | `charts/**` |
| `plugin-dev` | pydantic-skill→dagster-skill→testing-skill | `plugins/**` |

## Core Skills (Active)

### pydantic-skill
**Trigger words**: schema, model, validation, config, BaseModel, Field, validator
**Trigger files**: `**/models.py`, `**/schemas.py`, `**/config.py`

### dagster-skill
**Trigger words**: asset, job, schedule, sensor, resource, IOManager
**Trigger files**: `**/assets.py`, `**/resources.py`

### dbt-skill
**Trigger words**: dbt, SQL model, macro, profiles.yml
**Trigger files**: `**/*.sql`, `**/dbt_project.yml`

### helm-k8s-skill
**Trigger words**: Helm, chart, Kubernetes, kubectl, pod
**Trigger files**: `charts/**`, `**/templates/**`

### testing-skill
**Trigger words**: test, pytest, fixture, coverage
**Trigger files**: `**/test_*.py`, `**/conftest.py`

## Reference Docs (Moved from Skills)

For less frequent technology work, reference docs are in `docs/reference/`:
- `docs/reference/polaris-skill.md` - Polaris catalog operations
- `docs/reference/pyiceberg-skill.md` - Iceberg table operations
- `docs/reference/cube-skill.md` - Cube semantic layer
- `docs/reference/duckdb-lakehouse.md` - DuckDB compute
- `docs/reference/arch-review.md` - Architecture review (use `tech-debt-review --arch`)

## OMC Agent Integration

For generic tasks, use OMC agents instead of custom:

| Task | OMC Agent |
|------|-----------|
| Code quality review | `oh-my-claudecode:code-reviewer` |
| Architecture analysis | `oh-my-claudecode:architect` |
| Build fixes | `oh-my-claudecode:build-fixer` |
| Security review | `oh-my-claudecode:security-reviewer` |
| Codebase search | `oh-my-claudecode:explore` |

## Custom Agents (floe-Specific)

Keep custom agents for project-specific concerns:
- `plugin-quality` - 11 floe plugin types testing
- `contract-stability` - CompiledArtifacts contract
- `test-debt-analyzer` - Consolidated test debt analysis
- `critic` - Final review gate
- `docker-log-analyser` - Context-efficient container logs
- `helm-debugger` - Context-efficient K8s debugging
