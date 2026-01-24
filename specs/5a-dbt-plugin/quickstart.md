# Quickstart: Epic 5A - dbt Plugin Abstraction

**Date**: 2026-01-24
**Epic**: 5A
**Branch**: `5a-dbt-plugin`

## Overview

This guide shows how to use the DBTPlugin abstraction layer to compile and run dbt models through floe. The abstraction supports multiple execution environments (dbt-core, dbt Fusion) while maintaining consistent interfaces.

## Prerequisites

- Python 3.10+
- floe-core installed
- One of: floe-dbt-core OR floe-dbt-fusion installed
- A valid dbt project with dbt_project.yml
- A valid profiles.yml with configured target

## Installation

```bash
# Install core plugin (dbt-core + SQLFluff)
pip install floe-dbt-core

# OR install Fusion plugin (requires dbt Fusion CLI binary)
pip install floe-dbt-fusion
```

## Basic Usage

### 1. Direct Plugin Usage

```python
from pathlib import Path
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

# Get the dbt plugin (configured in manifest.yaml)
registry = get_registry()
dbt_plugin = registry.get(PluginType.DBT, "core")  # or "fusion"

# Compile the project
manifest_path = dbt_plugin.compile_project(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev"
)
print(f"Compiled manifest: {manifest_path}")

# Run all models
result = dbt_plugin.run_models(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev"
)

if result.success:
    print(f"Ran {result.models_run} models in {result.execution_time_seconds}s")
else:
    print(f"Failed with {result.failures} failures")
```

### 2. With Model Selection

```python
# Run only staging models
result = dbt_plugin.run_models(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev",
    select="tag:staging",  # dbt selection syntax
    exclude="tag:wip"
)

# Run with full refresh (rebuild incremental models)
result = dbt_plugin.run_models(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev",
    select="fct_orders",
    full_refresh=True
)
```

### 3. Run Tests

```python
# Run all dbt tests
result = dbt_plugin.test_models(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev"
)

print(f"Tests run: {result.tests_run}")
print(f"Failures: {result.failures}")
```

### 4. SQL Linting

```python
# Lint SQL files
lint_result = dbt_plugin.lint_project(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev"
)

if not lint_result.success:
    for violation in lint_result.violations:
        print(f"{violation.file_path}:{violation.line}: {violation.message}")

# Auto-fix issues
lint_result = dbt_plugin.lint_project(
    project_dir=Path("./my_dbt_project"),
    profiles_dir=Path("~/.dbt"),
    target="dev",
    fix=True
)
print(f"Fixed {lint_result.files_fixed} files")
```

### 5. Retrieve Artifacts

```python
# Get the compiled manifest
manifest = dbt_plugin.get_manifest(Path("./my_dbt_project"))
print(f"Project has {len(manifest['nodes'])} nodes")

# Get run results (after a run)
run_results = dbt_plugin.get_run_results(Path("./my_dbt_project"))
print(f"Last run took {run_results['elapsed_time']}s")
```

## Dagster Integration

### Using DBTResource

```python
from dagster import asset, Definitions
from floe_orchestrator_dagster.resources.dbt_resource import DBTResource

# Define the resource
dbt_resource = DBTResource(
    plugin_type="core",  # or "fusion"
    project_dir="/path/to/dbt/project",
    profiles_dir="/path/to/profiles",
    target="dev"
)

# Use in an asset
@asset
def my_dbt_model(dbt: DBTResource) -> None:
    """Materialize dbt model."""
    result = dbt.run_models(select="my_model")
    if not result.success:
        raise Exception(f"dbt run failed: {result.failures} failures")

# Create definitions
defs = Definitions(
    assets=[my_dbt_model],
    resources={"dbt": dbt_resource}
)
```

### Multiple Models with Dependencies

```python
from dagster import asset, AssetExecutionContext

@asset
def stg_customers(dbt: DBTResource) -> None:
    """Stage customers from source."""
    dbt.run_models(select="stg_customers")

@asset(deps=[stg_customers])
def fct_customer_orders(dbt: DBTResource) -> None:
    """Customer orders fact table."""
    dbt.run_models(select="fct_customer_orders")

@asset(deps=[fct_customer_orders])
def dim_customers(dbt: DBTResource) -> None:
    """Customer dimension with order metrics."""
    dbt.run_models(select="dim_customers")
```

## Configuration

### Platform Manifest (manifest.yaml)

```yaml
# Platform Team configures the dbt runtime
version: "1.0"

plugins:
  # Choose: "core" (dbt-core) or "fusion" (dbt Fusion)
  dbt_runtime: core
```

### Checking Capabilities

```python
# Check if runtime supports parallel execution
if dbt_plugin.supports_parallel_execution():
    print("Runtime supports parallel compilation")
else:
    print("Runtime is single-threaded (use Fusion for parallel)")

# Check linting support
if dbt_plugin.supports_sql_linting():
    print("Runtime supports SQL linting")

# Get runtime metadata
metadata = dbt_plugin.get_runtime_metadata()
print(f"dbt version: {metadata.get('dbt_version')}")
print(f"Runtime: {metadata.get('runtime')}")
```

## Error Handling

```python
from floe_dbt_core import (
    DBTCompilationError,
    DBTExecutionError,
    DBTConfigurationError,
    DBTError,
)

try:
    result = dbt_plugin.run_models(
        project_dir=Path("./my_dbt_project"),
        profiles_dir=Path("~/.dbt"),
        target="dev"
    )
except DBTCompilationError as e:
    # Jinja/SQL compilation failed
    print(f"Compilation error in {e.file_path}:{e.line_number}")
    print(f"Message: {e.original_message}")
except DBTExecutionError as e:
    # Model execution failed
    print(f"Execution error in model {e.model_name}")
except DBTConfigurationError as e:
    # Invalid profiles.yml or dbt_project.yml
    print(f"Configuration error: {e.config_file}")
except DBTError as e:
    # Other dbt errors
    print(f"Error: {e}")
```

## Fusion-Specific Notes

### Checking Fusion Availability

```python
from floe_dbt_fusion import detect_fusion

info = detect_fusion()
if info.available:
    print(f"Fusion available: {info.binary_path} v{info.version}")
else:
    print("Fusion not installed")
```

### Automatic Fallback

When Fusion is configured but the Rust adapter is unavailable for your target:

```python
# Fusion is configured, but BigQuery has no Rust adapter
# Plugin automatically falls back to dbt-core with a warning
result = dbt_plugin.run_models(...)
# Warning logged: "Fusion adapter unavailable for bigquery, falling back to dbt-core"
```

### Supported Fusion Adapters

| Adapter | Rust Support |
|---------|--------------|
| DuckDB | Yes |
| Snowflake | Yes |
| BigQuery | No (fallback to core) |
| Databricks | No (fallback to core) |
| Redshift | No (fallback to core) |
| PostgreSQL | No (fallback to core) |

## Performance Tips

1. **Reuse Manifest**: For repeated runs, the plugin caches the parsed manifest
2. **Use Fusion for Large Projects**: Fusion provides 30x faster parsing
3. **Parallel Compilation**: Only Fusion supports parallel compilation (thread-safe)
4. **Selective Runs**: Use `select` parameter to run only needed models

## Observability

All plugin operations emit:
- **OpenTelemetry spans** with operation timing and attributes
- **OpenLineage events** for data transformations (via dbt native support)

```python
# Spans include attributes like:
# - dbt.project_dir
# - dbt.target
# - dbt.success
# - dbt.execution_time_seconds
# - dbt.models_run
```

## Next Steps

- See [spec.md](./spec.md) for full requirements
- See [research.md](./research.md) for technical details
- See [plan.md](./plan.md) for implementation phases
