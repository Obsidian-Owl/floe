# dbt Architecture Clarification: Enforced vs Pluggable

**Date**: 2025-01-06
**Context**: ADR-0043 introduces DBTRuntimePlugin, creating dual nature of dbt in architecture
**Impact**: CRITICAL - Affects opinionation boundaries, plugin architecture, documentation
**Status**: Update Plan (Requires Systematic Changes)

---

## The Confusion

Current documentation states **"dbt is ENFORCED"** without distinguishing between:

1. **dbt as SQL transformation framework** (ENFORCED - non-negotiable)
2. **dbt execution runtime** (PLUGGABLE - local vs cloud vs fusion)

This creates ambiguity when we introduce `DBTRuntimePlugin` while maintaining "dbt is enforced" in opinionation boundaries.

---

## Clarified Architecture

### Two Distinct Layers

```
┌──────────────────────────────────────────────┐
│ LAYER 1: TRANSFORMATION FRAMEWORK (ENFORCED) │
│                                              │
│  - dbt-core library (SQL compilation)        │
│  - dbt models, tests, macros                 │
│  - dbt manifest.json contract                │
│  - ref(), source() macros                    │
│  - Jinja templating                          │
│                                              │
│  Decision: ADR-0009 "dbt Owns SQL"           │
│  Boundary: ENFORCED (non-negotiable)         │
└──────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────┐
│ LAYER 2: EXECUTION RUNTIME (PLUGGABLE)       │
│                                              │
│  - LocalDBTPlugin (dbt-core via dbtRunner)   │
│  - DBTCloudPlugin (dbt Cloud API)            │
│  - DBTFusionPlugin (Rust runtime, future)    │
│                                              │
│  Decision: ADR-0043 "dbt Runtime Abstraction"│
│  Boundary: PLUGGABLE (platform team choice)  │
└──────────────────────────────────────────────┘
```

### Key Distinctions

| Aspect | Transformation Framework | Execution Runtime |
|--------|-------------------------|-------------------|
| **What** | dbt-core library, SQL compilation | How dbt commands execute |
| **Status** | ENFORCED (ADR-0009) | PLUGGABLE (ADR-0043) |
| **Choice** | No choice - must use dbt | Platform team choice (local/cloud/fusion) |
| **Examples** | dbt models, tests, macros | dbtRunner vs dbt Cloud API |
| **Alternatives** | None (dbt required) | dbt-core, dbt Cloud, dbt Fusion |
| **Plugin Type** | N/A (not pluggable) | DBTRuntimePlugin |

### Architecture Statement (Canonical)

> **floe ENFORCES dbt as the SQL transformation framework** (ADR-0009). All SQL transformations MUST use dbt models, tests, and macros. This is non-negotiable.
>
> **However, dbt execution runtime is PLUGGABLE** (ADR-0043). Platform teams MAY choose:
> - **Local runtime**: dbt-core via `dbtRunner` (open-source, in-process)
> - **Cloud runtime**: dbt Cloud API (commercial, remote execution)
> - **Fusion runtime**: dbt Fusion (Rust-based, future)
>
> Data engineers write dbt models (enforced). Platform teams choose where dbt runs (pluggable).

---

## Files Requiring Updates

### Critical Updates (Architecture Clarity)

#### 1. `docs/architecture/opinionation-boundaries.md`

**Current State**:
```markdown
## ENFORCED (Non-negotiable)

- **Apache Iceberg**: Table format
- **OpenTelemetry**: Observability
- **OpenLineage**: Data lineage
- **dbt**: SQL transformations
- **Kubernetes**: Deployment
```

**Required Update**:
```markdown
## ENFORCED (Non-negotiable)

- **Apache Iceberg**: Table format (no alternatives)
- **OpenTelemetry**: Observability emission (no alternatives)
- **OpenLineage**: Data lineage events (no alternatives)
- **dbt (transformation framework)**: SQL transformations (no alternatives)
  - dbt-core library for SQL compilation (ref(), source(), tests)
  - dbt models define all transformations
  - dbt manifest.json is contract for downstream systems
  - **Note**: dbt execution runtime is PLUGGABLE (see DBTRuntimePlugin)
- **Kubernetes**: Deployment (no alternatives)

## PLUGGABLE (Platform Team Selects)

**Execution & Runtime Plugins**:

| Plugin Type | Purpose | Alternatives |
|-------------|---------|--------------|
| ComputePlugin | Where SQL executes | DuckDB, Snowflake, BigQuery, Databricks, Spark |
| OrchestratorPlugin | Job scheduling | Dagster, Airflow 3.x, Prefect, Argo |
| **DBTRuntimePlugin** | **How dbt executes** | **dbt-core (local), dbt Cloud (remote), dbt Fusion (future)** |
| CatalogPlugin | Iceberg catalog | Polaris, Unity Catalog, AWS Glue, Nessie |
| StoragePlugin | Object storage | S3, GCS, Azure Blob, MinIO |
```

**Rationale**: Clearly separate "what transforms" (dbt framework, enforced) from "where it runs" (dbt runtime, pluggable).

---

#### 2. `docs/architecture/adr/0009-dbt-owns-sql.md`

**Current State**: Does not mention execution runtime pluggability

**Required Update** (add new section):

```markdown
## Execution Runtime (Pluggable)

While dbt is ENFORCED for SQL transformation, the execution runtime is PLUGGABLE:

- **Local Execution**: dbt-core via `dbtRunner` (default, free, offline)
- **Remote Execution**: dbt Cloud API (commercial, managed, scalable)
- **Future**: dbt Fusion (Rust-based, performance)

See **ADR-0043: dbt Runtime Abstraction Layer** for details.

### Separation of Concerns

| Concern | Status | Decision |
|---------|--------|----------|
| **SQL transformation tool** | ENFORCED | ADR-0009 (this document) |
| **SQL dialect handling** | ENFORCED | dbt adapters (DuckDB, Snowflake, etc.) |
| **Execution runtime** | PLUGGABLE | ADR-0043 (DBTRuntimePlugin) |
| **Orchestration** | PLUGGABLE | OrchestratorPlugin (Dagster, Airflow) |

**Key Insight**: Platform teams cannot choose an alternative to dbt for SQL transformations (enforced), but they CAN choose how dbt executes (local vs cloud).
```

---

#### 3. `docs/architecture/ARCHITECTURE-SUMMARY.md`

**Required Update** (add clarification to opinionation section):

```markdown
### Opinionation Boundaries

**ENFORCED Components** (no alternatives):
- **Iceberg**: Storage format (ACID, time-travel, schema evolution)
- **OTel + OpenLineage**: Observability and lineage standards
- **dbt (framework)**: SQL transformation DSL (dbt-core library required)
- **Kubernetes**: Deployment target (no Docker Compose in production)

**PLUGGABLE Components** (platform team selects once):
- **Compute**: DuckDB, Snowflake, BigQuery, Databricks, Spark
- **Orchestrator**: Dagster (default), Airflow 3.x, Prefect
- **dbt Runtime**: dbt-core (local), dbt Cloud (remote), dbt Fusion (future) ← **NEW**
- **Catalog**: Polaris (default), Unity, Glue, Nessie
- **Storage**: S3, GCS, Azure, MinIO
- **Observability Backend**: Jaeger, Datadog, Grafana Cloud
- **Semantic Layer**: Cube (default), dbt Semantic Layer, custom
- **Ingestion**: dlt (default), Airbyte
- **Secrets**: K8s Secrets, ESO, Vault, Infisical
- **Identity**: Keycloak, Dex, Okta, Auth0

**Total Plugin Types**: 12 (was 11 before DBTRuntimePlugin)
```

---

#### 4. `CLAUDE.md` (Project Instructions)

**Section to Update**: "Technology Ownership"

**Current State**: Lists dbt without execution runtime distinction

**Required Update**:

```markdown
### dbt: Owns ALL SQL

**dbt owns SQL and SQL dialect translation:**

❌ **NEVER** parse SQL in Python
❌ **NEVER** validate SQL syntax in Python
❌ **NEVER** transform SQL dialects manually
❌ **NEVER** modify dbt-generated SQL
✅ **ALWAYS** let dbt handle all SQL compilation and execution
✅ **ALWAYS** trust dbt for dialect-specific features

**dbt Framework vs Runtime**:

| Component | Status | What | Examples |
|-----------|--------|------|----------|
| **dbt Framework** | ENFORCED | SQL transformation DSL | dbt models, tests, macros, ref(), source() |
| **dbt Runtime** | PLUGGABLE | Execution environment | dbt-core (local), dbt Cloud (remote), dbt Fusion (future) |

**Key Principle**: You MUST use dbt for SQL transformations (non-negotiable). You MAY choose where dbt executes (local vs cloud).

**Correct Usage**:
```python
# ✅ CORRECT - Via DBTRuntimePlugin
from floe_core.plugin_registry import PluginRegistry

registry = PluginRegistry()
dbt_runtime = registry.get_plugin("dbt_runtimes", "local")  # or "cloud"

result = dbt_runtime.run_models(
    project_dir=Path("/opt/dbt/project"),
    profiles_dir=Path("/opt/dbt/profiles"),
    target="dev",
    select="customers",
)
```

**Forbidden Pattern**:
```python
# ❌ FORBIDDEN - Direct dbtRunner usage (bypasses runtime abstraction)
from dbt.cli.main import dbtRunner

dbt = dbtRunner()
dbt.invoke(["run", "--select", "customers"])
```

**Migration**: Epic 3 extracts dbtRunner hardcoded logic → LocalDBTPlugin.
```

---

#### 5. `docs/architecture/four-layer-overview.md`

**Section to Update**: Layer 2 (Configuration)

**Required Update**:

```markdown
### Layer 2: CONFIGURATION (Immutable Artifacts)

**Components**:
- `platform-manifest.yaml`: Platform governance (plugins, policies, approved products)
- `floe.yaml`: Data product definition (transforms, schedules, dependencies)
- **CompiledArtifacts**: Immutable contract (manifest.json, profiles.yml, configs)

**Plugin Selection** (in platform-manifest.yaml):

```yaml
plugins:
  compute: duckdb                    # WHERE SQL executes
  orchestrator: dagster              # HOW jobs schedule
  dbt_runtime: local                 # WHERE dbt runs ← NEW
  catalog: polaris                   # WHERE metadata stores
  storage: s3                        # WHERE data stores
  observability: jaeger              # WHERE traces send
  semantic_layer: cube               # HOW data consumed
  ingestion: dlt                     # HOW data ingested
```

**Key Distinction**:
- `compute: duckdb` → ComputePlugin provides dbt profiles.yml target configuration
- `dbt_runtime: local` → DBTRuntimePlugin executes `dbt run` command (local vs cloud)
- Both are PLUGGABLE, both affect dbt execution, different purposes

**Separation**:
- **ComputePlugin**: "Here's the database connection for dbt to use"
- **DBTRuntimePlugin**: "Here's how to invoke dbt commands (local CLI vs cloud API)"
```

---

### Documentation Updates (Consistency)

#### 6. `docs/guides/03-solution-strategy.md`

**Add section**: "dbt Execution Strategy"

```markdown
### dbt Execution Strategy

**Transformation Framework (ENFORCED)**:
- All SQL transformations use dbt-core library
- dbt models define pipeline logic (ref(), source(), tests)
- dbt manifest.json is contract for downstream systems

**Execution Runtime (PLUGGABLE)**:
- **Local Runtime** (default): dbt-core via Python `dbtRunner` API
  - Free, open-source
  - Works offline
  - Serialized execution (not thread-safe)
- **Cloud Runtime** (commercial): dbt Cloud REST API
  - Remote execution in K8s pods
  - Parallel job execution
  - Metadata API for rich project insights
- **Fusion Runtime** (future): Rust-based dbt execution
  - Performance optimizations
  - Local execution (no cloud dependency)

**Platform Team Decision**: Select runtime in `platform-manifest.yaml`
**Data Team Input**: None (transparent to data engineers)
```

---

#### 7. `docs/architecture/plugin-architecture.md`

**Add new section**: "DBTRuntimePlugin"

```markdown
### DBTRuntimePlugin (Entry Point: `floe.dbt_runtimes`)

**Purpose**: Abstract dbt compilation and execution across local (dbt-core) and remote (dbt Cloud) runtimes.

**Implementations**:
- `LocalDBTPlugin`: Wraps dbt-core `dbtRunner` API (open-source)
- `DBTCloudPlugin`: Wraps dbt Cloud Admin API + Discovery API (commercial)
- `DBTFusionPlugin`: Placeholder for dbt Fusion (future)

**Key Methods**:
```python
class DBTRuntimePlugin(ABC):
    @abstractmethod
    def compile_project(
        self, project_dir: Path, profiles_dir: Path, target: str
    ) -> Path:
        """Compile dbt project, return manifest.json path."""

    @abstractmethod
    def run_models(
        self, project_dir: Path, profiles_dir: Path, target: str, select: str | None = None
    ) -> DBTRunResult:
        """Execute dbt run command."""

    @abstractmethod
    def supports_parallel_execution(self) -> bool:
        """Indicate if runtime supports concurrent execution."""
```

**Integration with OrchestratorPlugin**:
```python
@asset
def customers(context):
    dbt_runtime = context.resources.dbt_runtime  # Injected by Dagster
    result = dbt_runtime.run_models(
        project_dir=Path("/opt/dbt/project"),
        profiles_dir=Path("/opt/dbt/profiles"),
        target="dev",
        select="customers",
    )
    context.log_metadata({"models_run": result.models_run})
```

**Distinction from ComputePlugin**:
- **ComputePlugin**: Generates dbt `profiles.yml` (connection config)
- **DBTRuntimePlugin**: Executes dbt commands (local vs cloud)
- Both required for dbt execution

**See**: ADR-0043 for complete design
```

---

### Code Updates (Epic 3)

#### 8. `floe-dagster/src/floe_dagster/assets.py` (Example)

**Current State**: Likely has hardcoded `dbtRunner` usage

**Required Update**:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, Definitions, asset, resource

from floe_core.plugin_registry import PluginRegistry
from floe_core.plugin_interfaces import DBTRuntimePlugin


@resource
def dbt_runtime_resource() -> DBTRuntimePlugin:
    """Dagster resource for DBTRuntimePlugin.

    Resolves plugin from platform-manifest.yaml configuration.
    """
    registry = PluginRegistry()
    return registry.get_plugin("dbt_runtimes", "local")  # Read from config


@asset
def customers(context: AssetExecutionContext) -> None:
    """dbt model: customers.

    Uses DBTRuntimePlugin for execution (local or cloud).
    """
    dbt_runtime: DBTRuntimePlugin = context.resources.dbt_runtime

    result = dbt_runtime.run_models(
        project_dir=Path("/opt/dbt/project"),
        profiles_dir=Path("/opt/dbt/profiles"),
        target=context.run.tags.get("target", "dev"),
        select="customers",
    )

    context.log.info(f"dbt run completed: {result.models_run} models run")
    context.add_output_metadata(
        {
            "models_run": result.models_run,
            "execution_time_seconds": result.execution_time_seconds,
            "dbt_runtime_type": dbt_runtime.get_runtime_metadata()["type"],
        }
    )
```

**Migration Path**: Epic 3 refactoring task

---

## Communication Plan

### Internal Messaging (to Team)

**Subject**: Clarification: dbt Framework (ENFORCED) vs dbt Runtime (PLUGGABLE)

**Body**:
> Team,
>
> We've clarified an important architectural distinction:
>
> **dbt Framework: ENFORCED** (ADR-0009)
> - You MUST use dbt for all SQL transformations
> - dbt models, tests, macros are required
> - No alternatives (e.g., no raw SQL, no SQLMesh, no custom frameworks)
>
> **dbt Runtime: PLUGGABLE** (ADR-0043 - NEW)
> - Platform teams MAY choose WHERE dbt executes:
>   - Local: dbt-core via `dbtRunner` (default, free)
>   - Cloud: dbt Cloud API (commercial, remote)
>   - Fusion: dbt Fusion (future, Rust-based)
>
> **Impact**:
> - Data engineers: No change (still write dbt models)
> - Platform teams: New choice (local vs cloud dbt execution)
> - Epic 3: Extract dbtRunner hardcoded logic → LocalDBTPlugin
>
> **Documentation Updated**:
> - opinionation-boundaries.md (clarified ENFORCED vs PLUGGABLE)
> - ADR-0009 (added execution runtime section)
> - ADR-0043 (new - dbt Runtime Abstraction)
> - CLAUDE.md (updated dbt ownership section)
>
> Questions? See `docs/architecture/DBT-ARCHITECTURE-CLARIFICATION.md`

---

## Validation Checklist

Before marking this update complete, verify:

- [ ] `opinionation-boundaries.md` distinguishes dbt framework (enforced) from runtime (pluggable)
- [ ] `ADR-0009` references ADR-0043 for runtime abstraction
- [ ] `ARCHITECTURE-SUMMARY.md` lists DBTRuntimePlugin in pluggable components
- [ ] `CLAUDE.md` shows correct dbt usage pattern (via DBTRuntimePlugin)
- [ ] `four-layer-overview.md` explains `dbt_runtime` plugin selection
- [ ] `plugin-architecture.md` documents DBTRuntimePlugin ABC
- [ ] `03-solution-strategy.md` explains dbt execution strategy
- [ ] All references to "dbt is enforced" clarified with "(transformation framework)"
- [ ] No ambiguous statements like "dbt is hardcoded" without context

---

## Summary

**Problem**: Documentation states "dbt is enforced" without clarifying WHAT aspect of dbt is enforced.

**Solution**: Systematically distinguish:
- **dbt Framework** (ENFORCED): SQL transformation DSL, models, tests, macros
- **dbt Runtime** (PLUGGABLE): Execution environment (local, cloud, fusion)

**Impact**: 8 files require updates (7 documentation, 1 code example)

**Timeline**: Epic 3 (plugin extraction) is correct time to make these changes

**Risk**: LOW - No breaking changes (LocalDBTPlugin is drop-in replacement for current hardcoded dbtRunner)

---

**Next Actions**:
1. Review and approve this clarification strategy
2. Create Epic 3 task: "Update dbt architecture documentation (ADR-0043 alignment)"
3. Update files per checklist above
4. Communicate changes to team (use template messaging above)
