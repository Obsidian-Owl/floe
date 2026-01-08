# Plugin Registry API Contract

**Date**: 2026-01-08
**Feature**: 001-plugin-registry
**Type**: Internal Python API (not REST/GraphQL)

## Overview

The Plugin Registry is an internal Python API, not a network service. This contract defines the public interface that other floe components depend on.

---

## Module: `floe_core.plugin_registry`

### Function: `get_registry()`

**Purpose**: Get the global plugin registry singleton.

```python
def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton.

    Returns:
        PluginRegistry: The singleton registry instance.

    Notes:
        - Thread-safe initialization
        - Automatically calls discover_all() on first access
        - Returns same instance on subsequent calls
    """
```

**Contract Guarantees**:
- Always returns the same `PluginRegistry` instance
- Instance is fully discovered (all entry points scanned)
- Thread-safe

---

## Class: `PluginRegistry`

### Method: `discover_all()`

```python
def discover_all(self) -> None:
    """Discover all plugins from entry points.

    Scans all 11 plugin type namespaces:
    - floe.computes
    - floe.orchestrators
    - floe.catalogs
    - floe.storage
    - floe.telemetry_backends
    - floe.lineage_backends
    - floe.dbt
    - floe.semantic_layers
    - floe.ingestion
    - floe.secrets
    - floe.identity

    Notes:
        - Does NOT load plugin classes (lazy loading)
        - Logs errors for malformed entry points but does not raise
        - Idempotent: safe to call multiple times
    """
```

**Contract Guarantees**:
- Scans all 11 entry point groups
- Does not crash on malformed entry points
- Populates `_discovered` dict with found entry points

---

### Method: `register()`

```python
def register(self, plugin: PluginMetadata) -> None:
    """Manually register a plugin instance.

    Args:
        plugin: Plugin instance to register.

    Raises:
        DuplicatePluginError: If plugin with same type+name exists.
        PluginIncompatibleError: If API version incompatible.

    Notes:
        - Validates API version compatibility before registration
        - Used for testing or programmatic plugin registration
    """
```

**Contract Guarantees**:
- Raises `DuplicatePluginError` if `(type, name)` already exists
- Raises `PluginIncompatibleError` if version check fails
- Plugin is immediately available via `get()` after successful registration

---

### Method: `get()`

```python
def get(self, plugin_type: PluginType, name: str) -> PluginMetadata:
    """Get a plugin by type and name.

    Args:
        plugin_type: The plugin category (e.g., PluginType.COMPUTE).
        name: The plugin name (e.g., "duckdb").

    Returns:
        PluginMetadata: The plugin instance.

    Raises:
        PluginNotFoundError: If plugin not found.
        PluginIncompatibleError: If version check fails during load.

    Notes:
        - Lazy loads plugin class on first access
        - Caches loaded instance for subsequent calls
    """
```

**Contract Guarantees**:
- Returns `PluginMetadata` subclass instance
- Lazy loads on first access (import happens here)
- Caches instance (same object returned on subsequent calls)
- Raises `PluginNotFoundError` with plugin_type and name in message

---

### Method: `list()`

```python
def list(self, plugin_type: PluginType) -> list[PluginMetadata]:
    """List all plugins of a specific type.

    Args:
        plugin_type: The plugin category to list.

    Returns:
        list[PluginMetadata]: All plugins of that type (may be empty).

    Notes:
        - Does NOT load plugins (returns metadata only)
        - Returns empty list if no plugins of that type
    """
```

**Contract Guarantees**:
- Returns list (never None)
- Does not raise exceptions
- Order is consistent but not guaranteed

---

### Method: `list_all()`

```python
def list_all(self) -> dict[PluginType, list[str]]:
    """List all available plugins by type.

    Returns:
        dict[PluginType, list[str]]: Plugin names grouped by type.

    Example:
        {
            PluginType.COMPUTE: ["duckdb", "snowflake"],
            PluginType.ORCHESTRATOR: ["dagster", "airflow"],
            ...
        }
    """
```

**Contract Guarantees**:
- Returns all 11 plugin types as keys
- Values are lists of plugin names (may be empty)

---

### Method: `configure()`

```python
def configure(
    self,
    plugin_type: PluginType,
    name: str,
    config: dict[str, Any]
) -> BaseModel:
    """Validate and store plugin configuration.

    Args:
        plugin_type: The plugin category.
        name: The plugin name.
        config: Configuration dictionary.

    Returns:
        BaseModel: Validated configuration instance.

    Raises:
        PluginNotFoundError: If plugin not found.
        PluginConfigurationError: If validation fails.

    Notes:
        - Loads plugin if not already loaded
        - Applies defaults from schema
        - Stores validated config for later retrieval
    """
```

**Contract Guarantees**:
- Returns Pydantic model instance with validated config
- Raises `PluginConfigurationError` with field-level error details
- Configuration is stored and retrievable

---

### Method: `health_check_all()`

```python
def health_check_all(self) -> dict[str, HealthStatus]:
    """Check health of all loaded plugins.

    Returns:
        dict[str, HealthStatus]: Health status keyed by "type:name".

    Notes:
        - Only checks LOADED plugins (not discovered-only)
        - Catches exceptions and returns UNHEALTHY status
        - Timeout: 5 seconds per plugin (SC-007)
    """
```

**Contract Guarantees**:
- Returns status for all loaded plugins
- Never raises exceptions (catches and reports)
- Respects 5-second timeout per plugin

---

## Class: `PluginMetadata` (ABC)

### Abstract Properties

```python
@property
@abstractmethod
def name(self) -> str:
    """Plugin name (e.g., 'duckdb', 'dagster')."""
    ...

@property
@abstractmethod
def version(self) -> str:
    """Plugin version (semver format: X.Y.Z)."""
    ...

@property
@abstractmethod
def floe_api_version(self) -> str:
    """Required floe API version (semver format: X.Y)."""
    ...
```

### Optional Properties

```python
@property
def description(self) -> str:
    """Plugin description. Default: empty string."""
    return ""

@property
def dependencies(self) -> list[str]:
    """Plugin dependencies by name. Default: empty list."""
    return []
```

### Methods

```python
def get_config_schema(self) -> type[BaseModel] | None:
    """Return Pydantic model for config validation.

    Returns:
        type[BaseModel] | None: Config schema class or None.

    Notes:
        - Return None if plugin has no configuration
        - Must return a Pydantic v2 BaseModel subclass
    """
    return None

def health_check(self) -> HealthStatus:
    """Check plugin health.

    Returns:
        HealthStatus: Current health status.

    Notes:
        - Default implementation returns HEALTHY
        - Override for custom health checks
        - Should complete within 5 seconds
    """
    return HealthStatus(state=HealthState.HEALTHY)

def startup(self) -> None:
    """Lifecycle hook: called when plugin is activated.

    Notes:
        - Default implementation does nothing
        - Override for initialization tasks
        - Should complete within 30 seconds (SC-006)
    """
    pass

def shutdown(self) -> None:
    """Lifecycle hook: called when platform shuts down.

    Notes:
        - Default implementation does nothing
        - Override for cleanup tasks
        - Should complete within 30 seconds (SC-006)
    """
    pass
```

---

## Enum: `PluginType`

```python
class PluginType(Enum):
    """Plugin type enumeration with entry point mapping."""

    COMPUTE = "floe.computes"
    ORCHESTRATOR = "floe.orchestrators"
    CATALOG = "floe.catalogs"
    STORAGE = "floe.storage"
    TELEMETRY_BACKEND = "floe.telemetry_backends"
    LINEAGE_BACKEND = "floe.lineage_backends"
    DBT = "floe.dbt"
    SEMANTIC_LAYER = "floe.semantic_layers"
    INGESTION = "floe.ingestion"
    SECRETS = "floe.secrets"
    IDENTITY = "floe.identity"

    @property
    def entry_point_group(self) -> str:
        """Get the entry point group name."""
        return self.value
```

---

## Exceptions

```python
class PluginError(Exception):
    """Base exception for plugin errors."""
    pass

class PluginNotFoundError(PluginError):
    """Plugin not found in registry."""
    def __init__(self, plugin_type: PluginType, name: str):
        self.plugin_type = plugin_type
        self.name = name
        super().__init__(f"Plugin not found: {plugin_type.name}:{name}")

class PluginIncompatibleError(PluginError):
    """Plugin API version incompatible."""
    def __init__(self, name: str, required: str, platform: str):
        self.name = name
        self.required_version = required
        self.platform_version = platform
        super().__init__(
            f"Plugin '{name}' requires API v{required}, "
            f"but platform provides v{platform}"
        )

class PluginConfigurationError(PluginError):
    """Plugin configuration validation failed."""
    def __init__(self, name: str, errors: list[dict]):
        self.name = name
        self.errors = errors
        super().__init__(f"Configuration error for plugin '{name}': {errors}")

class DuplicatePluginError(PluginError):
    """Plugin with same type+name already registered."""
    def __init__(self, plugin_type: PluginType, name: str):
        self.plugin_type = plugin_type
        self.name = name
        super().__init__(f"Duplicate plugin: {plugin_type.name}:{name}")

class CircularDependencyError(PluginError):
    """Circular dependency detected in plugin graph."""
    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        super().__init__(f"Circular dependency: {' -> '.join(cycle)}")
```

---

## DataClasses

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class HealthState(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthStatus:
    """Health check result."""
    state: HealthState
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
```

---

## Version Compatibility

```python
# Module: floe_core.version_compat

FLOE_PLUGIN_API_VERSION: str = "1.0"
FLOE_PLUGIN_API_MIN_VERSION: str = "1.0"

def is_compatible(plugin_api_version: str, platform_api_version: str) -> bool:
    """Check if plugin API version is compatible with platform.

    Args:
        plugin_api_version: Plugin's required API version (X.Y format).
        platform_api_version: Platform's provided API version (X.Y format).

    Returns:
        bool: True if compatible.

    Compatibility Rules:
        - Major version must match exactly
        - Plugin minor version <= platform minor version
    """
```

---

## Usage Example

```python
from floe_core.plugin_registry import get_registry
from floe_core.plugin_types import PluginType

# Get registry (auto-discovers on first access)
registry = get_registry()

# List available compute plugins
compute_plugins = registry.list(PluginType.COMPUTE)
print([p.name for p in compute_plugins])  # ['duckdb', 'snowflake', ...]

# Get specific plugin
duckdb = registry.get(PluginType.COMPUTE, "duckdb")
print(duckdb.version)  # '1.0.0'

# Configure plugin
config = registry.configure(
    PluginType.COMPUTE,
    "duckdb",
    {"database_path": "/data/floe.duckdb", "threads": 8}
)

# Health check
statuses = registry.health_check_all()
for key, status in statuses.items():
    print(f"{key}: {status.state.value}")
```
