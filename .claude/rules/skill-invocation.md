# Skill Invocation Rules

## Automatic Skill Activation

When working on specific components, you SHOULD invoke the appropriate skill to ensure best practices are followed.

## Skill Trigger Matrix

### pydantic-skill
**Trigger words**: schema, model, validation, config, BaseModel, Field, validator
**Trigger files**: Any `**/models.py`, `**/schemas.py`, `**/config.py`
**Invoke when**: Creating or modifying Pydantic models, data validation, API contracts

### dagster-skill
**Trigger words**: asset, job, schedule, sensor, resource, IOManager, materialize
**Trigger files**: Any `plugins/floe-orchestrator-dagster/**`, `**/assets.py`, `**/resources.py`
**Invoke when**: Working with Dagster orchestration, assets, or scheduling

### dbt-skill
**Trigger words**: dbt, SQL model, macro, source, test, profiles.yml, dbt_project.yml
**Trigger files**: Any `floe-dbt/**`, `**/*.sql`, `**/dbt_project.yml`
**Invoke when**: Creating dbt models, tests, or macros

### pyiceberg-skill
**Trigger words**: Iceberg, table, partition, schema evolution, time travel, scan
**Trigger files**: Any `floe-iceberg/**`
**Invoke when**: Working with Iceberg table operations

### polaris-skill
**Trigger words**: Polaris, catalog, namespace, principal, REST catalog
**Trigger files**: Any `plugins/floe-catalog-polaris/**`
**Invoke when**: Working with Polaris catalog management

### cube-skill
**Trigger words**: Cube, semantic layer, measure, dimension, pre-aggregation
**Trigger files**: Any `plugins/floe-semantic-cube/**`, `**/cube/**`
**Invoke when**: Working with Cube semantic layer

### helm-k8s-skill
**Trigger words**: Helm, chart, Kubernetes, kubectl, pod, deployment, values.yaml
**Trigger files**: Any `charts/**`, `**/templates/**`
**Invoke when**: Working with Helm charts or K8s deployments

## How to Invoke

Skills can be invoked explicitly:

```markdown
# Explicit invocation
Use the pydantic-skill to help design the CompiledArtifacts schema.

# Or reference the skill file
Read .claude/skills/pydantic-skill/SKILL.md for Pydantic best practices.
```

## Skill Chaining

For complex tasks, multiple skills may be needed:

| Task | Primary | Secondary |
|------|---------|-----------|
| Create Dagster asset for dbt | dagster-skill | dbt-skill |
| Configure Polaris in K8s | polaris-skill | helm-k8s-skill |
| Design CompiledArtifacts | pydantic-skill | All (integration) |

## Context Efficiency

Skills inject research protocols and validation steps, NOT full implementations.
This keeps context lean while ensuring correct patterns.
