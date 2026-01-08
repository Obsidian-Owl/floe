"""floe-core: Core plugin registry and interfaces for the floe data platform.

This package provides:
- PluginRegistry: Singleton for discovering and managing plugins
- PluginMetadata: Base ABC for all plugin types
- PluginType: Enum defining the 11 plugin categories
- Plugin ABCs: Type-specific interfaces (ComputePlugin, etc.)
- Errors: Custom exceptions for plugin operations

Example:
    >>> from floe_core import get_registry, PluginType
    >>> registry = get_registry()
    >>> registry.discover_all()
    >>> compute_plugins = registry.list(PluginType.COMPUTE)

    >>> from floe_core import ComputePlugin, CatalogPlugin
    >>> class MyCompute(ComputePlugin):
    ...     # Implement abstract methods
    ...     pass

See Also:
    - floe_core.plugins: All plugin ABCs with supporting dataclasses
    - docs/architecture/plugin-system/: Full architecture documentation
"""

from __future__ import annotations

__version__ = "0.1.0"

# Error hierarchy
from floe_core.plugin_errors import (
    CircularDependencyError,
    DuplicatePluginError,
    PluginConfigurationError,
    PluginError,
    PluginIncompatibleError,
    PluginNotFoundError,
)

# Health types and PluginMetadata ABC
from floe_core.plugin_metadata import (
    HealthState,
    HealthStatus,
    PluginMetadata,
)

# Plugin registry singleton
from floe_core.plugin_registry import (
    PluginRegistry,
    get_registry,
)

# Plugin type categories
from floe_core.plugin_types import PluginType

# Plugin ABCs (11 types)
from floe_core.plugins import (
    CatalogPlugin,
    ComputePlugin,
    DBTPlugin,
    IdentityPlugin,
    IngestionPlugin,
    LineageBackendPlugin,
    OrchestratorPlugin,
    SecretsPlugin,
    SemanticLayerPlugin,
    StoragePlugin,
    TelemetryBackendPlugin,
)

# Version compatibility
from floe_core.version_compat import (
    FLOE_PLUGIN_API_MIN_VERSION,
    FLOE_PLUGIN_API_VERSION,
    is_compatible,
)

__all__: list[str] = [
    # Package version
    "__version__",
    # Plugin type categories
    "PluginType",
    # Error hierarchy
    "PluginError",
    "PluginNotFoundError",
    "PluginIncompatibleError",
    "PluginConfigurationError",
    "DuplicatePluginError",
    "CircularDependencyError",
    # Version compatibility
    "FLOE_PLUGIN_API_VERSION",
    "FLOE_PLUGIN_API_MIN_VERSION",
    "is_compatible",
    # Health types and base ABC
    "HealthState",
    "HealthStatus",
    "PluginMetadata",
    # Plugin registry
    "PluginRegistry",
    "get_registry",
    # Plugin ABCs (11 types)
    "CatalogPlugin",
    "ComputePlugin",
    "DBTPlugin",
    "IdentityPlugin",
    "IngestionPlugin",
    "LineageBackendPlugin",
    "OrchestratorPlugin",
    "SecretsPlugin",
    "SemanticLayerPlugin",
    "StoragePlugin",
    "TelemetryBackendPlugin",
]
