# floe-compute-duckdb

DuckDB compute plugin for the floe data platform.

## Overview

This plugin enables DuckDB as a compute target for dbt transforms in the floe platform. DuckDB is a self-hosted, in-process analytical database that runs within K8s job pods alongside dbt.

## Features

- **In-process**: Runs alongside dbt in the same pod
- **Self-hosted**: Managed by floe K8s infrastructure
- **Iceberg support**: Direct catalog attachment via iceberg extension
- **Low overhead**: No separate database server required

## Installation

```bash
pip install floe-compute-duckdb
```

Or with dbt adapter:

```bash
pip install floe-compute-duckdb[dbt]
```

## Usage

The plugin is automatically discovered by the floe registry via entry points:

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

registry = get_registry()
duckdb_plugin = registry.get(PluginType.COMPUTE, "duckdb")

print(f"Plugin: {duckdb_plugin.name} v{duckdb_plugin.version}")
```

### Generate dbt Profile

```python
from floe_core.plugins.compute import ComputeConfig

config = ComputeConfig(
    extra={
        "path": ":memory:",
        "threads": 4,
        "extensions": ["iceberg", "httpfs"],
        "settings": {"memory_limit": "4GB"}
    }
)

profile = duckdb_plugin.generate_dbt_profile(config)
# {'type': 'duckdb', 'path': ':memory:', 'threads': 4, ...}
```

### Validate Connection

```python
result = duckdb_plugin.validate_connection(config)
if result.success:
    print(f"Connected in {result.latency_ms:.1f}ms")
else:
    print(f"Failed: {result.message}")
```

### Query Timeout Configuration

The plugin supports query timeout enforcement via the `timeout_seconds` configuration:

```python
from floe_core import ComputeConfig

config = ComputeConfig(
    plugin="duckdb",
    threads=4,
    timeout_seconds=300,  # 5 minute timeout
    connection={"path": ":memory:"}
)

profile = duckdb_plugin.generate_dbt_profile(config)
# profile["timeout_seconds"] == 300
```

**How timeout enforcement works:**

1. The plugin includes `timeout_seconds` in the generated dbt profile
2. The dbt-duckdb adapter is responsible for actual timeout enforcement
3. Platform operators can set timeouts in `manifest.yaml` to enforce governance
4. Data engineers inherit the platform default unless explicitly overridden

**Default value:** 3600 seconds (1 hour)

**Valid range:** 1 to 86400 seconds (1 second to 24 hours)

### Get K8s Resource Requirements

```python
spec = duckdb_plugin.get_resource_requirements("medium")
print(f"CPU: {spec.cpu_request} - {spec.cpu_limit}")
print(f"Memory: {spec.memory_request} - {spec.memory_limit}")
```

## Development

```bash
# Install in development mode
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/unit/ -v

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```

## License

Apache 2.0
