# Research: Plugin Registry Foundation

**Date**: 2026-01-08
**Feature**: 001-plugin-registry

## Research Summary

This document consolidates research findings for implementing the plugin registry. All NEEDS CLARIFICATION items from initial planning have been resolved.

---

## 1. Entry Point Discovery Pattern

### Decision
Use `importlib.metadata.entry_points()` with type-specific group names.

### Rationale
- Python 3.10+ provides improved `entry_points()` API with `group` parameter
- Type-specific namespaces (`floe.computes`, `floe.orchestrators`, etc.) provide:
  - Type-safe discovery (no runtime type checking needed)
  - Clear plugin categorization in pyproject.toml
  - Namespace isolation (no conflicts between plugin types)
- Aligns with existing architecture in `docs/architecture/plugin-system/discovery.md`

### Alternatives Considered
| Alternative | Rejected Because |
|------------|------------------|
| Single `floe.plugins` namespace | Requires runtime type checking, less organized |
| `pkg_resources` (setuptools) | Deprecated in favor of `importlib.metadata` |
| Manual package scanning | Slower, less reliable, not standard |

### Implementation Pattern
```python
from importlib.metadata import entry_points

# Python 3.10+ API
eps = entry_points(group="floe.computes")
for ep in eps:
    plugin_class = ep.load()  # Lazy load on access
```

---

## 2. Lazy Loading Strategy

### Decision
Discover entry points at startup, load plugin classes on first access.

### Rationale
- Entry point discovery is fast (metadata only, no imports)
- Plugin loading (class import) can be slow (dependencies, initialization)
- Lazy loading improves startup time for platforms with many plugins
- Only plugins actually used are loaded

### Implementation Pattern
```python
class PluginRegistry:
    def __init__(self):
        self._discovered: dict[str, EntryPoint] = {}  # Fast discovery
        self._loaded: dict[str, type] = {}  # Lazy loading cache

    def discover_all(self):
        """Fast: Only reads metadata."""
        for group in PLUGIN_GROUPS:
            for ep in entry_points(group=group):
                key = f"{group}:{ep.name}"
                self._discovered[key] = ep

    def get(self, plugin_type: PluginType, name: str):
        """Loads on first access."""
        key = f"{plugin_type.entry_point_group}:{name}"
        if key not in self._loaded:
            ep = self._discovered[key]
            self._loaded[key] = ep.load()  # Import happens here
        return self._loaded[key]
```

---

## 3. Version Compatibility Rules

### Decision
Use semantic versioning with major version compatibility check.

### Rationale
- Industry standard (semver.org)
- Clear rules: same major version = compatible
- Minor/patch differences are backward compatible
- Aligns with Python ecosystem conventions

### Compatibility Logic
```python
def is_compatible(plugin_api_version: str, platform_api_version: str) -> bool:
    """Check if plugin is compatible with platform.

    Rules:
    - Same major version required
    - Plugin minor version <= platform minor version (plugin can't require newer features)
    - Patch versions ignored (bug fixes only)
    """
    plugin = parse_version(plugin_api_version)
    platform = parse_version(platform_api_version)

    if plugin.major != platform.major:
        return False  # Major mismatch = incompatible

    # Plugin can require older or equal minor version
    return plugin.minor <= platform.minor
```

### Alternatives Considered
| Alternative | Rejected Because |
|------------|------------------|
| Exact version matching | Too restrictive, breaks minor updates |
| Range expressions (>=1.0,<2.0) | Overcomplicated for internal API |
| No version checking | Risk of runtime errors from API mismatch |

---

## 4. Plugin Metadata Base ABC Design

### Decision
Use ABC with abstract properties for required metadata and concrete method for config schema.

### Rationale
- Abstract properties enforce implementation in subclasses
- Common base ensures all 11 plugin types have consistent metadata
- Pydantic model return for config schema enables validation

### Base Class Design
```python
from abc import ABC, abstractmethod
from typing import ClassVar
from pydantic import BaseModel

class PluginMetadata(ABC):
    """Base class for all floe plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (e.g., 'duckdb', 'dagster')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version (semver)."""
        ...

    @property
    @abstractmethod
    def floe_api_version(self) -> str:
        """Required floe API version (semver)."""
        ...

    @property
    def description(self) -> str:
        """Optional plugin description."""
        return ""

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return Pydantic model for configuration validation.

        Override to provide plugin-specific configuration schema.
        Returns None if plugin has no configuration.
        """
        return None
```

---

## 5. Error Handling Strategy

### Decision
Log errors during discovery but don't crash; raise exceptions during explicit operations.

### Rationale
- Platform should start even if some plugins are broken
- Explicit operations (get, register) should fail loudly
- Consistent with SC-005: "Platform startup succeeds even when 50% of installed plugins have discovery errors"

### Error Hierarchy
```python
class PluginError(Exception):
    """Base exception for plugin errors."""
    pass

class PluginNotFoundError(PluginError):
    """Plugin not found in registry."""
    pass

class PluginIncompatibleError(PluginError):
    """Plugin API version incompatible."""
    pass

class PluginConfigurationError(PluginError):
    """Plugin configuration validation failed."""
    pass

class DuplicatePluginError(PluginError):
    """Plugin with same type/name already registered."""
    pass

class CircularDependencyError(PluginError):
    """Circular dependency detected in plugin graph."""
    pass
```

---

## 6. Singleton Registry Pattern

### Decision
Use module-level singleton with `get_registry()` function.

### Rationale
- Single source of truth for plugin state
- Testable: can reset in tests with `_reset_registry()` for isolation
- Thread-safe initialization with `threading.Lock`

### Implementation Pattern
```python
import threading

_registry: PluginRegistry | None = None
_lock = threading.Lock()

def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton."""
    global _registry
    if _registry is None:
        with _lock:
            if _registry is None:
                _registry = PluginRegistry()
                _registry.discover_all()
    return _registry

def _reset_registry() -> None:
    """Reset registry (for testing only)."""
    global _registry
    with _lock:
        _registry = None
```

---

## 7. Health Check Pattern

### Decision
Default healthy response with optional override.

### Rationale
- Most plugins don't need custom health checks
- Plugins with external dependencies can override
- Returns structured HealthStatus for consistency

### Implementation Pattern
```python
from dataclasses import dataclass
from enum import Enum

class HealthState(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthStatus:
    state: HealthState
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

class PluginMetadata(ABC):
    # ... other methods ...

    def health_check(self) -> HealthStatus:
        """Check plugin health. Override for custom checks."""
        return HealthStatus(state=HealthState.HEALTHY)
```

---

## 8. Dependency Resolution Algorithm

### Decision
Topological sort with cycle detection using Kahn's algorithm.

### Rationale
- Well-known algorithm for dependency ordering
- O(V + E) complexity
- Detects cycles during sorting
- Simple to implement and test

### Implementation Pattern
```python
from collections import defaultdict, deque

def resolve_dependencies(plugins: list[PluginMetadata]) -> list[PluginMetadata]:
    """Sort plugins by dependencies (Kahn's algorithm).

    Raises:
        CircularDependencyError: If circular dependency detected
    """
    # Build graph
    graph = defaultdict(list)
    in_degree = {p.name: 0 for p in plugins}

    for plugin in plugins:
        for dep in plugin.dependencies:
            graph[dep].append(plugin.name)
            in_degree[plugin.name] += 1

    # Kahn's algorithm
    queue = deque([p for p in plugins if in_degree[p.name] == 0])
    result = []

    while queue:
        plugin = queue.popleft()
        result.append(plugin)
        for dependent in graph[plugin.name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(next(p for p in plugins if p.name == dependent))

    if len(result) != len(plugins):
        raise CircularDependencyError("Circular dependency detected")

    return result
```

---

## 9. Configuration Validation Pattern

### Decision
Use Pydantic v2 models with field-level validation.

### Rationale
- Pydantic is already a project dependency
- v2 syntax (`@field_validator`, `model_config`)
- Clear error messages with field paths
- Default values from schema

### Implementation Pattern
```python
from pydantic import BaseModel, Field, field_validator, ValidationError

class DuckDBConfig(BaseModel):
    """Configuration for DuckDB compute plugin."""
    model_config = ConfigDict(extra="forbid")

    database_path: str = Field(default=":memory:")
    threads: int = Field(default=4, ge=1, le=64)
    memory_limit: str = Field(default="4GB")

    @field_validator("memory_limit")
    @classmethod
    def validate_memory_limit(cls, v: str) -> str:
        if not v.endswith(("GB", "MB")):
            raise ValueError("must end with GB or MB")
        return v

# In registry
def validate_config(plugin: PluginMetadata, config: dict) -> BaseModel:
    schema = plugin.get_config_schema()
    if schema is None:
        return None  # No config required
    try:
        return schema.model_validate(config)
    except ValidationError as e:
        raise PluginConfigurationError(str(e)) from e
```

---

## 10. Testing Strategy

### Decision
Unit tests for core logic, contract tests for ABC stability.

### Rationale
- Unit tests: Fast, no external dependencies, mock entry points
- Contract tests: Verify ABC interfaces are stable (prevent breaking changes)
- No integration tests needed (no external services for registry itself)

### Test Structure
```
packages/floe-core/tests/
├── unit/
│   ├── test_plugin_registry.py      # Discovery, registration, lookup
│   ├── test_plugin_metadata.py      # Base ABC, metadata properties
│   ├── test_version_compat.py       # Semver compatibility logic
│   └── test_plugin_types.py         # PluginType enum
└── contract/
    └── test_plugin_abc_contract.py  # ABC stability across versions
```

### Mock Entry Points Pattern
```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_entry_points():
    """Mock entry_points for testing without installed plugins."""
    mock_ep = MagicMock()
    mock_ep.name = "test_plugin"
    mock_ep.load.return_value = TestPlugin

    with patch("importlib.metadata.entry_points") as mock:
        mock.return_value = [mock_ep]
        yield mock
```

---

## Summary

All research items resolved. Key decisions:

1. **Entry Points**: Type-specific namespaces (`floe.computes`, etc.)
2. **Loading**: Lazy loading on first access
3. **Versioning**: Semver with major version compatibility
4. **Base ABC**: `PluginMetadata` with abstract properties
5. **Errors**: Log on discovery, raise on explicit operations
6. **Singleton**: Module-level with thread-safe initialization
7. **Health**: Default healthy with optional override
8. **Dependencies**: Kahn's algorithm for topological sort
9. **Config**: Pydantic v2 with field validation
10. **Testing**: Unit + contract tests, mock entry points
