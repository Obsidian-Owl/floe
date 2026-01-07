# ADR-0009: dbt Owns SQL Transformation

## Status

Accepted

## Context

Floe needs to handle SQL transformations across multiple compute targets (DuckDB, Snowflake, BigQuery, etc.). Key challenges:

- SQL dialect differences between targets
- Dependency resolution between models
- Incremental processing logic
- Data testing

Options considered:
- **Build custom SQL handling** - Parse, transpile, manage dependencies ourselves
- **Use dbt** - Leverage existing, proven tooling
- **Hybrid** - Light wrapper around dbt
- **Target-specific code** - Different implementations per target

## Decision

**dbt owns SQL transformation**. Floe does not parse, transpile, or manage SQL dependencies.

## Consequences

### Positive

- **Proven tooling** - dbt handles dialect translation via adapters
- **Dependency resolution** - `ref()` and `source()` macros work out of the box
- **Incremental processing** - `is_incremental()` macro handles complexity
- **Data testing** - dbt tests validate data quality
- **Large ecosystem** - dbt packages, community, documentation
- **Simpler Floe** - Less code to maintain

### Negative

- **dbt dependency** - Users must structure transforms as dbt projects
- **Learning curve** - Users need dbt knowledge
- **Less flexibility** - Can't support non-dbt SQL patterns
- **Version coupling** - Must support dbt version changes

### Neutral

- CompiledArtifacts just point to dbt project (don't rewrite SQL)
- Floe adds value in orchestration, data isolation, observability
- Future non-dbt transforms (Python, Flink) handled separately

## Responsibility Split

| Concern | Owner |
|---------|-------|
| SQL dialect translation | **dbt** (via adapters) |
| Dependency resolution | **dbt** (`ref()`, `source()`) |
| Incremental processing | **dbt** (`is_incremental()`) |
| Data tests | **dbt** |
| Orchestration | **Dagster** |
| Data isolation | **Floe** |
| Pipeline lifecycle | **Floe** |
| Observability | **Floe** |

## Execution Runtime (Pluggable)

While dbt framework is enforced for SQL transformation DSL, the **execution environment** WHERE dbt compiles and runs is pluggable via DBTPlugin (ADR-0043):

| Implementation | Description | Entry Point |
|----------------|-------------|-------------|
| **LocalDBTPlugin** | dbt-core via CLI subprocess | `floe.dbt` |
| **FusionDBTPlugin** | dbt Fusion (Rust-based) via CLI subprocess | `floe.dbt` |
| **CloudDBTPlugin** | dbt Cloud API (deferred to Epic 8+) | `floe.dbt` |

**Key Distinction:**
- **dbt Framework** (ENFORCED): SQL transformation DSL, models, tests, macros, Jinja templating
- **dbt Execution Environment** (PLUGGABLE): WHERE dbt compiles (local dbt-core, dbt Fusion, dbt Cloud)

Platform teams select the execution environment in `manifest.yaml`:

```yaml
plugins:
  dbt_compiler:
    provider: fusion  # or local, or cloud
```

Data engineers use dbt framework features (models, tests, macros) regardless of execution environment.

## CompiledArtifacts Pattern

```go
// Floe points to dbt project, doesn't rewrite SQL
type DBTConfig struct {
    ProjectDir string            // Path to dbt project
    Target     string            // dbt target (profiles.yml)
    EnvVars    map[string]string // Environment variables
    Commands   []string          // ["dbt run", "dbt test"]
    Select     string            // Model selection
    Exclude    string            // Model exclusion
}
```

## What Floe Does NOT Do

- ❌ Parse SQL to understand structure
- ❌ Transpile SQL between dialects
- ❌ Manage model dependencies
- ❌ Handle incremental logic
- ❌ Run data tests directly

## What Floe DOES Do

- ✅ Orchestrate dbt runs via Dagster
- ✅ Provide environment variables (connections, etc.)
- ✅ Collect observability from dbt runs
- ✅ Manage data isolation (namespace-based)
- ✅ Provision compute targets

## References

- [dbt](https://www.getdbt.com/)
- [dbt adapters](https://docs.getdbt.com/docs/available-adapters)
