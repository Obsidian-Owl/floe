"""floe-core: Core plugin registry and interfaces for the floe data platform.

This package provides:
- PluginRegistry: Singleton for discovering and managing plugins
- PluginMetadata: Base ABC for all plugin types
- PluginType: Enum defining the 11 plugin categories
- Plugin ABCs: Type-specific interfaces (ComputePlugin, etc.)
- Errors: Custom exceptions for plugin operations
"""

from __future__ import annotations

__version__ = "0.1.0"

# Public API - exports will be added as modules are implemented
# See tasks.md for implementation order
__all__: list[str] = [
    "__version__",
    # T006: PluginType enum
    # T007: Errors (PluginError, PluginNotFoundError, etc.)
    # T008: FLOE_PLUGIN_API_VERSION, is_compatible
    # T009-T010: HealthState, HealthStatus, PluginMetadata
    # T011-T015: PluginRegistry, get_registry
    # T058-T068: Plugin ABCs (ComputePlugin, etc.)
]
