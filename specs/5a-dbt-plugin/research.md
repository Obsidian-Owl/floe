# Research: Epic 5A - dbt Plugin Abstraction

**Date**: 2026-01-24
**Epic**: 5A
**Branch**: `5a-dbt-plugin`

## Executive Summary

This research documents findings from investigating dbt-core, dbt Fusion, and the existing floe implementation to inform the Epic 5A implementation plan.

**Key Findings**:
1. DBTPlugin ABC already exists in floe-core with 10 abstract methods - ready for implementation
2. dbt-core dbtRunner is NOT thread-safe - confirmed by official documentation
3. dbt Fusion is Rust-based CLI requiring subprocess invocation
4. Dagster integration should use ConfigurableResource pattern for type-safe injection
5. Existing dbt_profiles.py is complete and tested - no changes needed

---

## 1. dbt-core dbtRunner API

### 1.1 Programmatic Invocation

The `dbtRunner` class provides Python API for dbt commands:

```python
from dbt.cli.main import dbtRunner, dbtRunnerResult

# Initialize runner
dbt = dbtRunner()

# Run a command
result: dbtRunnerResult = dbt.invoke(["run", "--select", "my_model"])

# Check success
if result.success:
    print(f"Result: {result.result}")
else:
    if result.exception:
        print(f"Exception: {result.exception}")
```

### 1.2 Callback System

dbtRunner supports callbacks for event handling:

```python
from dbt_common.events.base_types import EventMsg

def event_callback(event: EventMsg):
    if event.info.name == "MainReportVersion":
        print(f"dbt version: {event.data.version}")

dbt = dbtRunner(callbacks=[event_callback])
dbt.invoke(["run"])
```

**Callback event types** (relevant for FR-016):
- `MainReportVersion` - dbt version info
- `LogStartLine` / `LogLine` - stdout/stderr capture
- `NodeStart` / `NodeFinished` - model execution events
- `TestResult` - test pass/fail events

### 1.3 Manifest Reuse

Pre-parsed manifest can be passed for performance:

```python
# Parse once
result = dbt.invoke(["parse"])
manifest = result.result

# Reuse manifest
dbt_with_manifest = dbtRunner(manifest=manifest)
result2 = dbt_with_manifest.invoke(["run"])
result3 = dbt_with_manifest.invoke(["test"])
```

### 1.4 Thread Safety (CRITICAL)

**From official documentation**:
> dbt-core does not support safe parallel execution for multiple invocations in the same process. It's not safe to run multiple dbt commands concurrently, as they can unexpectedly interact with global Python variables.

**Implication**: `DBTCorePlugin.supports_parallel_execution()` MUST return `False`.

**Workaround for parallel execution**: Use separate processes or dbt Cloud/Fusion.

---

## 2. dbt Fusion CLI

### 2.1 Overview

dbt Fusion is a Rust-based ground-up rewrite of the dbt execution engine:
- **30x faster parsing** for large projects
- **Thread-safe** by design (Rust memory safety)
- **Native SQL understanding** across warehouse dialects
- **Standalone binary** - no Python interpreter needed

### 2.2 CLI Interface

The CLI binary is `dbt-sa-cli` (Static Analysis CLI):

```bash
# Install dependencies
dbt-sa-cli deps

# Add a package
dbt-sa-cli deps --add-package "dbt-labs/dbt_utils@1.0.0"

# Compile project
dbt-sa-cli compile --project-dir /path/to/project

# Run models
dbt-sa-cli run --select "tag:daily"
```

### 2.3 Adapter Availability

dbt Fusion requires Rust-based adapters:

| Adapter | Rust Support | Status |
|---------|--------------|--------|
| DuckDB | duckdb-rs | Supported |
| Snowflake | snowflake-connector-rust | Supported |
| BigQuery | N/A | Python-only |
| Databricks | N/A | Python-only |
| Redshift | N/A | Python-only |
| PostgreSQL | N/A | Python-only |

**Implication**: Automatic fallback to dbt-core needed when Rust adapter unavailable (FR-039, FR-040).

### 2.4 Detection Strategy

```python
import shutil
import subprocess

def detect_fusion():
    """Detect if dbt Fusion is available."""
    binary = shutil.which("dbt-sa-cli")
    if not binary:
        return None, None

    result = subprocess.run(
        [binary, "--version"],
        capture_output=True,
        text=True
    )
    version = parse_version(result.stdout)
    return binary, version
```

---

## 3. Existing floe Implementation

### 3.1 DBTPlugin ABC (floe-core)

**Location**: `packages/floe-core/src/floe_core/plugins/dbt.py`

The ABC is **already defined** with 10 abstract methods:

| Method | Purpose | Return Type |
|--------|---------|-------------|
| `compile_project()` | Compile Jinja to SQL | `Path` |
| `run_models()` | Execute models | `DBTRunResult` |
| `test_models()` | Execute tests | `DBTRunResult` |
| `lint_project()` | SQL linting | `LintResult` |
| `get_manifest()` | Retrieve manifest.json | `dict[str, Any]` |
| `get_run_results()` | Retrieve run_results.json | `dict[str, Any]` |
| `supports_parallel_execution()` | Thread safety indicator | `bool` |
| `supports_sql_linting()` | Linting capability | `bool` |
| `get_runtime_metadata()` | Observability metadata | `dict[str, Any]` |

**Result Dataclasses**:
- `DBTRunResult`: success, manifest_path, run_results_path, execution_time_seconds, models_run, tests_run, failures, metadata
- `LintResult`: success, issues, files_checked, files_fixed

### 3.2 dbt_profiles.py (floe-core)

**Location**: `packages/floe-core/src/floe_core/compilation/dbt_profiles.py`

**Status**: Complete and tested. Generates profiles.yml from ResolvedPlugins.

**Key Functions**:
- `generate_dbt_profiles(plugins, product_name, environments)` - Main entry point
- `format_env_var_placeholder(var_name, default)` - Creates `{{ env_var('X') }}` syntax
- `get_compute_plugin(plugin_type)` - Loads compute plugin from registry

**Integration Point**: DBTPlugin implementations will use the profiles.yml generated by this module.

### 3.3 CompiledArtifacts Schema (floe-core)

**Location**: `packages/floe-core/src/floe_core/schemas/compiled_artifacts.py`

**Version**: 0.3.0

**Relevant Fields**:
- `transforms: ResolvedTransforms | None` - dbt model information
- `dbt_profiles: dict[str, Any] | None` - Generated profiles.yml

### 3.4 Dagster Plugin (floe-orchestrator-dagster)

**Location**: `plugins/floe-orchestrator-dagster/src/floe_orchestrator_dagster/plugin.py`

**Current State**: Creates **placeholder assets** (line 349-354):
```python
def _asset_fn() -> None:
    """Placeholder asset for dbt model.

    Actual materialization happens via dbt resource integration.
    """
    return None
```

**Epic 5A Integration**: Replace placeholder with DBTPlugin.run_models() call via ConfigurableResource.

---

## 4. Plugin Architecture Patterns

### 4.1 Entry Point Registration

Plugins register via `pyproject.toml`:

```toml
[project.entry-points."floe.dbt"]
core = "floe_dbt_core:DBTCorePlugin"
fusion = "floe_dbt_fusion:DBTFusionPlugin"
```

### 4.2 Package Structure

Following existing plugin patterns:

```
plugins/floe-dbt-core/
├── pyproject.toml
├── src/
│   └── floe_dbt_core/
│       ├── __init__.py
│       ├── plugin.py      # DBTCorePlugin implementation
│       └── linting.py     # SQLFluff integration
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/

plugins/floe-dbt-fusion/
├── pyproject.toml
├── src/
│   └── floe_dbt_fusion/
│       ├── __init__.py
│       ├── plugin.py      # DBTFusionPlugin implementation
│       └── detection.py   # Binary/version detection
└── tests/
    ├── conftest.py
    ├── unit/
    └── integration/
```

### 4.3 Dagster ConfigurableResource Pattern

For FR-037/FR-038, use Dagster's ConfigurableResource:

```python
from dagster import ConfigurableResource
from floe_core.plugins.dbt import DBTPlugin

class DBTResource(ConfigurableResource):
    """DBTPlugin wrapped as Dagster resource."""

    plugin_type: str = "core"  # or "fusion"
    project_dir: str
    profiles_dir: str
    target: str = "dev"

    def get_plugin(self) -> DBTPlugin:
        """Load and return DBTPlugin instance."""
        from floe_core.plugin_registry import get_registry
        return get_registry().get(PluginType.DBT, self.plugin_type)

    def run_models(self, select: str | None = None) -> DBTRunResult:
        """Execute dbt models."""
        plugin = self.get_plugin()
        return plugin.run_models(
            project_dir=Path(self.project_dir),
            profiles_dir=Path(self.profiles_dir),
            target=self.target,
            select=select
        )
```

---

## 5. SQLFluff Dialect Mapping

For FR-013, map dbt adapter to SQLFluff dialect:

| dbt Adapter | SQLFluff Dialect |
|-------------|------------------|
| duckdb | duckdb |
| snowflake | snowflake |
| bigquery | bigquery |
| postgres | postgres |
| redshift | redshift |
| databricks | sparksql |

**Detection Strategy**:
1. Read profiles.yml target configuration
2. Extract adapter type from `type:` field
3. Map to SQLFluff dialect

---

## 6. Error Handling Design

### 6.1 Exception Hierarchy

```python
class DBTError(FloeError):
    """Base exception for all dbt plugin errors."""
    pass

class DBTCompilationError(DBTError):
    """Compilation failed (Jinja parsing, SQL generation)."""
    file_path: str | None = None
    line_number: int | None = None
    original_message: str

class DBTExecutionError(DBTError):
    """Runtime execution failed (model materialization, test failure)."""
    model_name: str | None = None
    adapter: str | None = None

class DBTConfigurationError(DBTError):
    """Configuration invalid (profiles.yml, dbt_project.yml)."""
    config_file: str | None = None
```

### 6.2 Error Preservation

For FR-036, preserve dbt's file/line information:

```python
try:
    result = dbt.invoke(["compile"])
except Exception as e:
    # Parse dbt error message for file/line info
    match = re.search(r"in file '([^']+)' at line (\d+)", str(e))
    if match:
        raise DBTCompilationError(
            message=str(e),
            file_path=match.group(1),
            line_number=int(match.group(2)),
            original_message=str(e)
        )
```

---

## 7. Observability Integration

### 7.1 OpenTelemetry Spans (NFR-006)

```python
from opentelemetry import trace

tracer = trace.get_tracer("floe.dbt")

def compile_project(self, project_dir, profiles_dir, target):
    with tracer.start_as_current_span("dbt.compile") as span:
        span.set_attribute("dbt.project_dir", str(project_dir))
        span.set_attribute("dbt.target", target)

        result = self._invoke_compile(...)

        span.set_attribute("dbt.success", result.success)
        span.set_attribute("dbt.execution_time_seconds", result.execution_time_seconds)
        return result
```

### 7.2 OpenLineage Events (NFR-007)

dbt natively emits OpenLineage events when configured:

```yaml
# dbt_project.yml
config:
  send_anonymous_usage_stats: False

# Enable OpenLineage
# Set OPENLINEAGE_URL environment variable
```

---

## 8. Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Plugin packages | `plugins/floe-dbt-core/`, `plugins/floe-dbt-fusion/` | Follows existing pattern |
| Entry point group | `floe.dbt` | Consistent with other plugin types |
| dbt-core version | `>=1.6,<2.0` | LTS support, dbtRunner API stability |
| Dagster integration | ConfigurableResource | Type-safe, testable, Dagster best practice |
| Fusion fallback | Automatic with warning | User experience, graceful degradation |
| Linting | SQLFluff (core), built-in (Fusion) | Best tool for each runtime |

---

## 9. References

- [dbt Programmatic Invocations](https://docs.getdbt.com/reference/programmatic-invocations)
- [dbt Fusion Documentation](https://github.com/dbt-labs/dbt-fusion)
- [Dagster ConfigurableResource](https://docs.dagster.io/concepts/resources)
- [SQLFluff Documentation](https://docs.sqlfluff.com/)
- [ADR-0043: dbt Runtime Abstraction](docs/architecture/adr/)
