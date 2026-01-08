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

# T006: PluginType enum
# T007: Exception hierarchy
from floe_core.plugin_errors import (
    CircularDependencyError,
    DuplicatePluginError,
    PluginConfigurationError,
    PluginError,
    PluginIncompatibleError,
    PluginNotFoundError,
)

# T009-T010: Health types and PluginMetadata
from floe_core.plugin_metadata import (
    HealthState,
    HealthStatus,
    PluginMetadata,
)
from floe_core.plugin_types import PluginType

# T008: Version compatibility
from floe_core.version_compat import (
    FLOE_PLUGIN_API_MIN_VERSION,
    FLOE_PLUGIN_API_VERSION,
    is_compatible,
)

__all__: list[str] = [
    "__version__",
    # T006: PluginType enum
    "PluginType",
    # T007: Errors
    "PluginError",
    "PluginNotFoundError",
    "PluginIncompatibleError",
    "PluginConfigurationError",
    "DuplicatePluginError",
    "CircularDependencyError",
    # T008: Version compatibility
    "FLOE_PLUGIN_API_VERSION",
    "FLOE_PLUGIN_API_MIN_VERSION",
    "is_compatible",
    # T009-T010: HealthState, HealthStatus, PluginMetadata
    "HealthState",
    "HealthStatus",
    "PluginMetadata",
    # T011-T015: PluginRegistry, get_registry
    # T058-T068: Plugin ABCs (ComputePlugin, etc.)
]
