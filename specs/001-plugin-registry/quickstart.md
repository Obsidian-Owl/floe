# Quickstart: Plugin Registry Foundation

**Date**: 2026-01-08
**Feature**: 001-plugin-registry

## Prerequisites

- Python 3.10+
- uv (package manager)
- floe-core package installed

## Installation

```bash
# Clone the repository (if not already)
git clone https://github.com/obsidian-owl/floe.git
cd floe

# Install floe-core in development mode
cd packages/floe-core
uv pip install -e ".[dev]"
```

## Quick Examples

### 1. Access the Plugin Registry

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

# Get the singleton registry (auto-discovers plugins on first access)
registry = get_registry()

# List all available plugins
all_plugins = registry.list_all()
for plugin_type, names in all_plugins.items():
    print(f"{plugin_type.name}: {names}")
```

### 2. Get a Specific Plugin

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.plugin_errors import PluginNotFoundError

registry = get_registry()

try:
    # Get compute plugin by name
    duckdb = registry.get(PluginType.COMPUTE, "duckdb")
    print(f"Plugin: {duckdb.name} v{duckdb.version}")
    print(f"API Version: {duckdb.floe_api_version}")
except PluginNotFoundError as e:
    print(f"Plugin not found: {e}")
```

### 3. Configure a Plugin

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType
from floe_core.plugin_errors import PluginConfigurationError

registry = get_registry()

try:
    # Configure with validation
    config = registry.configure(
        PluginType.COMPUTE,
        "duckdb",
        {
            "database_path": "/data/floe.duckdb",
            "threads": 8,
            "memory_limit": "8GB"
        }
    )
    print(f"Configured: {config}")
except PluginConfigurationError as e:
    print(f"Configuration error: {e.errors}")
```

### 4. Check Plugin Health

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_metadata import HealthState

registry = get_registry()

# Check health of all loaded plugins
statuses = registry.health_check_all()
for key, status in statuses.items():
    if status.state != HealthState.HEALTHY:
        print(f"WARNING: {key} is {status.state.value}: {status.message}")
```

### 5. Create a Custom Plugin

```python
# my_plugin/plugin.py
from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugins.compute import ComputePlugin
from pydantic import BaseModel, Field

class MyComputeConfig(BaseModel):
    """Configuration for my custom compute plugin."""
    connection_string: str = Field(..., description="Database connection")
    max_workers: int = Field(default=4, ge=1, le=32)

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

    @property
    def description(self) -> str:
        return "My custom compute engine"

    def get_config_schema(self) -> type[BaseModel]:
        return MyComputeConfig

    def generate_dbt_profile(self, config: MyComputeConfig) -> dict:
        return {
            "type": "my_adapter",
            "connection_string": config.connection_string,
            "threads": config.max_workers,
        }

    # ... implement other abstract methods
```

Register in `pyproject.toml`:
```toml
[project.entry-points."floe.computes"]
my-compute = "my_plugin.plugin:MyComputePlugin"
```

## Running Tests

```bash
# Unit tests (fast, no external deps)
cd packages/floe-core
uv run pytest tests/unit/ -v

# All tests including contract tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=floe_core --cov-report=term-missing
```

## Common Tasks

### List All 11 Plugin Types

```python
from floe_core.plugin_types import PluginType

for pt in PluginType:
    print(f"{pt.name}: {pt.entry_point_group}")
```

Output:
```
COMPUTE: floe.computes
ORCHESTRATOR: floe.orchestrators
CATALOG: floe.catalogs
STORAGE: floe.storage
TELEMETRY_BACKEND: floe.telemetry_backends
LINEAGE_BACKEND: floe.lineage_backends
DBT: floe.dbt
SEMANTIC_LAYER: floe.semantic_layers
INGESTION: floe.ingestion
SECRETS: floe.secrets
IDENTITY: floe.identity
```

### Check Version Compatibility

```python
from floe_core.version_compat import is_compatible, FLOE_PLUGIN_API_VERSION

# Check if plugin version is compatible
plugin_version = "1.0"
if is_compatible(plugin_version, FLOE_PLUGIN_API_VERSION):
    print("Compatible!")
else:
    print(f"Incompatible: requires {plugin_version}, have {FLOE_PLUGIN_API_VERSION}")
```

### Manual Plugin Registration (Testing)

```python
from floe_core.plugin_registry import get_registry
from my_plugin.plugin import MyComputePlugin

registry = get_registry()

# Register programmatically (useful for testing)
plugin = MyComputePlugin()
registry.register(plugin)
```

## Troubleshooting

### Plugin Not Found

```python
# Debug: List what's actually discovered
registry = get_registry()
print("Discovered entry points:")
for key, ep in registry._discovered.items():
    print(f"  {key}: {ep}")
```

### Configuration Validation Errors

```python
from floe_core.plugin_errors import PluginConfigurationError

try:
    config = registry.configure(PluginType.COMPUTE, "duckdb", {"threads": -1})
except PluginConfigurationError as e:
    for error in e.errors:
        print(f"Field: {error['loc']}")
        print(f"Error: {error['msg']}")
```

### Entry Point Not Loading

```bash
# Check if entry points are registered correctly
uv run python -c "from importlib.metadata import entry_points; print(entry_points(group='floe.computes'))"
```

## Next Steps

- See [data-model.md](data-model.md) for entity details
- See [contracts/plugin-registry-api.md](contracts/plugin-registry-api.md) for full API contract
- See [research.md](research.md) for design decisions
