# floe-dbt-fusion

DBT plugin for floe using dbt Fusion CLI for high-performance parallel execution.

## Overview

This plugin provides `DBTFusionPlugin`, which wraps dbt Fusion's Rust-based CLI for:
- High-performance compilation (~30x faster than dbt-core for 100-model projects)
- Thread-safe parallel execution (Rust memory safety)
- Production workloads requiring concurrent compilation

## Prerequisites

dbt Fusion CLI must be installed separately:

```bash
# Install dbt Fusion CLI (Rust binary)
# See: https://github.com/dbt-labs/dbt-fusion
```

## Installation

```bash
pip install floe-dbt-fusion

# For automatic fallback to dbt-core when Rust adapters unavailable:
pip install floe-dbt-fusion[fallback]
```

## Usage

The plugin is automatically discovered via entry points:

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

registry = get_registry()
dbt_plugin = registry.get(PluginType.DBT, "fusion")

# Compile project (parallel-safe)
manifest_path = dbt_plugin.compile_project(
    project_dir=Path("my_project"),
    profiles_dir=Path("my_project"),
    target="dev"
)

# Check thread safety
assert dbt_plugin.supports_parallel_execution() is True
```

## Automatic Fallback

When Rust adapters are not available for the target database, the plugin
automatically falls back to `floe-dbt-core` (if installed) with a warning:

```
WARNING: Fusion adapter unavailable for BigQuery, falling back to dbt-core
```

## Supported Adapters

| Adapter | Rust Support | Status |
|---------|--------------|--------|
| DuckDB | duckdb-rs | Supported |
| Snowflake | snowflake-connector-rust | Supported |
| BigQuery | N/A | Fallback to dbt-core |
| Databricks | N/A | Fallback to dbt-core |

## License

Apache-2.0
