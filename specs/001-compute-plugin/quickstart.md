# Quickstart: Compute Plugin ABC with Multi-Compute Pipeline Support

**Date**: 2026-01-09
**Feature**: 001-compute-plugin

## Prerequisites

- Python 3.10+
- uv (package manager)
- floe-core package installed
- duckdb>=0.9.0 (for DuckDB reference implementation)

## Installation

```bash
# Clone the repository (if not already)
git clone https://github.com/obsidian-owl/floe.git
cd floe

# Install floe-core in development mode
cd packages/floe-core
uv pip install -e ".[dev]"

# Install DuckDB compute plugin
cd ../../plugins/floe-compute-duckdb
uv pip install -e ".[dev]"
```

## Quick Examples

### 1. Get a Compute Plugin

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

# Get the registry and load the DuckDB compute plugin
registry = get_registry()
duckdb_plugin = registry.get(PluginType.COMPUTE, "duckdb")

print(f"Plugin: {duckdb_plugin.name} v{duckdb_plugin.version}")
print(f"Required packages: {duckdb_plugin.get_required_dbt_packages()}")
```

### 2. Generate dbt Profile

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.compute_config import DuckDBConfig

# Get DuckDB plugin
registry = get_registry()
plugin = registry.get(PluginType.COMPUTE, "duckdb")

# Configure for local development
config = DuckDBConfig(
    path=":memory:",
    memory_limit="4GB",
    threads=4,
    extensions=["iceberg", "httpfs"]
)

# Generate profiles.yml structure
profile = plugin.generate_dbt_profile(config)
print(profile)
# Output:
# {
#     "type": "duckdb",
#     "path": ":memory:",
#     "threads": 4,
#     "extensions": ["iceberg", "httpfs"],
#     "settings": {"memory_limit": "4GB"}
# }
```

### 3. Validate Connection

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.compute_config import DuckDBConfig, ConnectionStatus

registry = get_registry()
plugin = registry.get(PluginType.COMPUTE, "duckdb")

config = DuckDBConfig(path=":memory:")

# Test connection using native driver (fast health check)
result = plugin.validate_connection(config)

if result.status == ConnectionStatus.HEALTHY:
    print(f"Connected successfully in {result.latency_ms:.1f}ms")
else:
    print(f"Connection failed: {result.message}")
    for warning in result.warnings:
        print(f"  Warning: {warning}")
```

### 4. Get K8s Resource Requirements

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

registry = get_registry()
plugin = registry.get(PluginType.COMPUTE, "duckdb")

# Get resource requirements for different workload sizes
for size in ["small", "medium", "large"]:
    spec = plugin.get_resource_requirements(size)
    print(f"{size}: CPU={spec.cpu_limit}, Memory={spec.memory_limit}")

# Output:
# small: CPU=500m, Memory=512Mi
# medium: CPU=2000m, Memory=4Gi
# large: CPU=8000m, Memory=16Gi
```

### 5. Get Iceberg Catalog Attachment SQL

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.compute_config import CatalogConfig
from pydantic import SecretStr

registry = get_registry()
plugin = registry.get(PluginType.COMPUTE, "duckdb")

# Configure Polaris catalog connection
catalog_config = CatalogConfig(
    catalog_type="rest",
    catalog_uri="http://polaris:8181/api/catalog",
    catalog_name="floe",
    credentials={
        "client_id": SecretStr("my_client_id"),
        "client_secret": SecretStr("my_client_secret"),
    }
)

# Get SQL statements to attach catalog
sql_statements = plugin.get_catalog_attachment_sql(catalog_config)
if sql_statements:
    for sql in sql_statements:
        print(sql)
# Output:
# INSTALL iceberg;
# LOAD iceberg;
# ATTACH 'iceberg:floe' AS iceberg_catalog (
#     TYPE ICEBERG,
#     CATALOG_URI 'http://polaris:8181/api/catalog',
#     ...
# );
```

### 6. Create a Custom Compute Plugin

```python
# my_compute/plugin.py
from __future__ import annotations

from typing import Any

from floe_core.compute_plugin import ComputePlugin
from floe_core.compute_config import (
    CatalogConfig,
    ComputeConfig,
    ConnectionResult,
    ConnectionStatus,
    ResourceSpec,
)
from pydantic import BaseModel, Field


class MyComputeConfig(ComputeConfig):
    """Configuration for my custom compute plugin."""
    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(..., description="Database name")


class MyComputePlugin(ComputePlugin):
    """Custom compute plugin implementation."""

    @property
    def name(self) -> str:
        return "my-compute"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        return "1.0"

    def get_config_schema(self) -> type[BaseModel]:
        return MyComputeConfig

    def generate_dbt_profile(self, config: ComputeConfig) -> dict[str, Any]:
        """Generate dbt profiles.yml for my adapter."""
        return {
            "type": "my_adapter",
            "host": config.connection.get("host"),
            "port": config.connection.get("port", 5432),
            "database": config.connection.get("database"),
            "threads": config.threads,
        }

    def get_required_dbt_packages(self) -> list[str]:
        return ["dbt-my-adapter>=1.0.0"]

    def validate_connection(self, config: ComputeConfig) -> ConnectionResult:
        """Test connection using native driver."""
        import time
        start = time.perf_counter()
        try:
            # Your connection logic here
            latency = (time.perf_counter() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.HEALTHY,
                latency_ms=latency,
                message="Connected successfully"
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return ConnectionResult(
                status=ConnectionStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )

    def get_resource_requirements(self, workload_size: str) -> ResourceSpec:
        """Return K8s resource requirements."""
        presets = {
            "small": ResourceSpec(cpu_limit="500m", memory_limit="512Mi"),
            "medium": ResourceSpec(cpu_limit="2000m", memory_limit="4Gi"),
            "large": ResourceSpec(cpu_limit="8000m", memory_limit="16Gi"),
        }
        if workload_size not in presets:
            raise ValueError(f"Unknown workload size: {workload_size}")
        return presets[workload_size]

    def get_catalog_attachment_sql(
        self, catalog_config: CatalogConfig
    ) -> list[str] | None:
        """Return None - this compute doesn't support direct catalog attachment."""
        return None
```

Register in `pyproject.toml`:
```toml
[project.entry-points."floe.computes"]
my-compute = "my_compute.plugin:MyComputePlugin"
```

## Configuration Reference

### DuckDB Configuration Options

```yaml
# In manifest.yaml
compute:
  approved:
    - duckdb
  default: duckdb

  duckdb:
    path: ":memory:"           # Database path (or file path)
    memory_limit: "4GB"        # Max memory for DuckDB
    threads: 4                 # Parallel query threads
    extensions:                # Extensions to load
      - iceberg
      - httpfs
    attach:                    # Iceberg catalogs to attach
      - path: "iceberg:floe"
        alias: iceberg_catalog
        options:
          catalog_uri: "http://polaris:8181/api/catalog"
```

### Workload Size Presets

| Size | CPU Request | CPU Limit | Memory Request | Memory Limit | Use Case |
|------|-------------|-----------|----------------|--------------|----------|
| `small` | 100m | 500m | 256Mi | 512Mi | Dev, simple transforms |
| `medium` | 500m | 2000m | 1Gi | 4Gi | Standard production |
| `large` | 2000m | 8000m | 4Gi | 16Gi | Heavy aggregations |

## Running Tests

```bash
# Unit tests for DuckDB plugin
cd plugins/floe-compute-duckdb
uv run pytest tests/unit/ -v

# Integration tests (requires DuckDB)
uv run pytest tests/integration/ -v

# Contract tests (ABC compliance)
cd ../../tests/contract
uv run pytest test_compute_plugin_contract.py -v

# All tests with coverage
uv run pytest tests/ --cov=floe_compute_duckdb --cov-report=term-missing
```

## Troubleshooting

### Plugin Not Found

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

registry = get_registry()

# List all available compute plugins
compute_plugins = registry.list(PluginType.COMPUTE)
print("Available compute plugins:")
for plugin in compute_plugins:
    print(f"  - {plugin.name} v{plugin.version}")
```

### Connection Validation Failed

```python
from floe_core.compute_config import ConnectionStatus

result = plugin.validate_connection(config)
if result.status == ConnectionStatus.UNHEALTHY:
    print(f"Error: {result.message}")
    print(f"Latency: {result.latency_ms}ms")

if result.status == ConnectionStatus.DEGRADED:
    print("Connection works but with warnings:")
    for warning in result.warnings:
        print(f"  - {warning}")
```

### Invalid Configuration

```python
from pydantic import ValidationError
from floe_core.compute_config import DuckDBConfig

try:
    config = DuckDBConfig(memory_limit="invalid")  # Must end with GB or MB
except ValidationError as e:
    for error in e.errors():
        print(f"Field: {error['loc']}")
        print(f"Error: {error['msg']}")
```

### DuckDB Iceberg Extension Issues

```python
# Check if extension is available
result = plugin.validate_connection(config)
if result.status == ConnectionStatus.DEGRADED:
    if "iceberg" in str(result.warnings):
        print("Iceberg extension not loaded - install with: INSTALL iceberg;")
```

## Next Steps

- See [data-model.md](data-model.md) for entity details
- See [contracts/](contracts/) for API contracts
- See [research.md](research.md) for design decisions
- See [spec.md](spec.md) for full requirements
