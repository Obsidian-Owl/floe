# Skill Invocation Rules

## File Pattern Triggers (Auto-Invoke)

| Pattern | Skill | When |
|---------|-------|------|
| `*.sql`, `dbt_project.yml`, `profiles.yml` | `dbt-skill` | SQL/dbt work |
| `**/schemas/*.py`, `**/models/*.py`, `**/config*.py` | `pydantic-skill` | Schema/model work |
| `charts/**`, `**/templates/**`, Helm YAML | `helm-k8s-skill` | K8s deployment |
| `**/assets.py`, `**/resources.py`, `**/io_managers.py` | `dagster-skill` | Orchestration |
| `**/test_*.py`, `**/conftest.py` | `testing-skill` | Test writing |

## Specwright Workflow

| Command | Purpose | When |
|---------|---------|------|
| `/sw-design` | Research codebase, design solution | New feature or significant change |
| `/sw-plan` | Break design into work units with specs | After design approval |
| `/sw-build` | TDD implementation of work unit | Implementation phase |
| `/sw-verify` | Quality gates (tests, security, wiring, spec) | Pre-PR validation |
| `/sw-ship` | Create PR with evidence | After all gates pass |

## Skill Chains

| Chain | Skills | Trigger |
|-------|--------|---------|
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

## Custom Agents (floe-Specific)

Keep custom agents for project-specific concerns:
- `plugin-quality` - 11 floe plugin types testing
- `contract-stability` - CompiledArtifacts contract
- `test-debt-analyzer` - Consolidated test debt analysis
- `critic` - Final review gate
- `docker-log-analyser` - Context-efficient container logs
- `helm-debugger` - Context-efficient K8s debugging
