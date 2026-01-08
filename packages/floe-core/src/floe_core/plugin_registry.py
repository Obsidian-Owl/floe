"""Plugin registry for discovering and managing floe plugins.

This module provides the central registry for all floe plugins. Plugins are
discovered via entry points and can be registered manually for testing.

The registry follows a lazy loading pattern:
- discover_all() scans entry points but does NOT import plugins
- get() imports and instantiates plugins on first access
- Loaded plugins are cached for subsequent access

Example:
    >>> from floe_core.plugin_registry import get_registry
    >>> from floe_core.plugin_types import PluginType
    >>>
    >>> registry = get_registry()
    >>> compute_plugins = registry.list(PluginType.COMPUTE)
    >>> duckdb = registry.get(PluginType.COMPUTE, "duckdb")
"""

from __future__ import annotations

import builtins
import threading
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.plugin_metadata import HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType

if TYPE_CHECKING:
    from importlib.metadata import EntryPoint

    from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# Module-level singleton instance and lock
_registry: PluginRegistry | None = None
_registry_lock = threading.Lock()


class PluginRegistry:
    """Central registry for discovering and managing floe plugins.

    The registry maintains two internal dictionaries:
    - _discovered: Entry points found via discover_all() (not yet loaded)
    - _loaded: Plugin instances that have been imported and instantiated

    Plugins are discovered by scanning entry point groups defined in PluginType.
    Loading is lazy - plugins are only imported when accessed via get().

    Attributes:
        _discovered: Dict mapping (PluginType, name) to EntryPoint.
        _loaded: Dict mapping (PluginType, name) to PluginMetadata instance.
        _configs: Dict mapping (PluginType, name) to validated config.

    Example:
        >>> registry = PluginRegistry()
        >>> registry.discover_all()
        >>> plugins = registry.list(PluginType.COMPUTE)
    """

    def __init__(self) -> None:
        """Initialize an empty plugin registry.

        The registry starts empty. Call discover_all() to scan entry points,
        or use register() to manually add plugins.
        """
        # Entry points discovered but not yet loaded
        # Key: (PluginType, plugin_name), Value: EntryPoint
        self._discovered: dict[tuple[PluginType, str], EntryPoint] = {}

        # Plugin instances that have been loaded
        # Key: (PluginType, plugin_name), Value: PluginMetadata instance
        self._loaded: dict[tuple[PluginType, str], PluginMetadata] = {}

        # Validated configurations for plugins
        # Key: (PluginType, plugin_name), Value: BaseModel config instance
        self._configs: dict[tuple[PluginType, str], BaseModel] = {}

        # Flag to track if discovery has been run
        self._discovered_all: bool = False

    def discover_all(self) -> None:
        """Discover all plugins from entry points.

        Scans all 11 plugin type entry point groups defined in PluginType.
        Does NOT load/import plugin classes - only discovers entry points.

        This method is idempotent - calling it multiple times has no effect
        after the first successful discovery.

        Entry points with errors are logged but do not prevent discovery
        of other plugins (graceful degradation).

        Note:
            This is implemented in T012. This skeleton just sets the flag.
        """
        # Implementation in T012
        self._discovered_all = True

    def register(self, plugin: PluginMetadata) -> None:
        """Manually register a plugin instance.

        Use this for testing or for plugins that aren't installed via
        entry points.

        Args:
            plugin: Plugin instance to register.

        Raises:
            DuplicatePluginError: If plugin with same type+name exists.
            PluginIncompatibleError: If version check fails.

        Note:
            Implementation details in T018-T022.
        """
        # Implementation in T018
        raise NotImplementedError("register() not yet implemented (T018)")

    def get(self, plugin_type: PluginType, name: str) -> PluginMetadata:
        """Get a plugin by type and name.

        Loads the plugin if not already loaded (lazy loading).

        Args:
            plugin_type: The plugin category (e.g., PluginType.COMPUTE).
            name: The plugin name (e.g., "duckdb").

        Returns:
            The plugin instance.

        Raises:
            PluginNotFoundError: If plugin not found.
            PluginIncompatibleError: If version check fails during load.

        Note:
            Implementation details in T019.
        """
        # Implementation in T019
        raise NotImplementedError("get() not yet implemented (T019)")

    def list(self, plugin_type: PluginType) -> builtins.list[PluginMetadata]:
        """List all plugins of a specific type.

        Returns discovered plugins for the given type. Does NOT load
        plugins - returns metadata only.

        Args:
            plugin_type: The plugin category to list.

        Returns:
            List of plugin instances for that type (may be empty).

        Note:
            Implementation details in T020.
        """
        # Implementation in T020
        raise NotImplementedError("list() not yet implemented (T020)")

    def list_all(self) -> dict[PluginType, builtins.list[PluginMetadata]]:
        """List all plugins grouped by type.

        Returns:
            Dict mapping PluginType to list of plugins.

        Note:
            Implementation details in T021.
        """
        # Implementation in T021
        raise NotImplementedError("list_all() not yet implemented (T021)")

    def configure(
        self,
        plugin_type: PluginType,
        name: str,
        config: dict[str, Any],
    ) -> None:
        """Configure a plugin with validated settings.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            config: Configuration dictionary to validate.

        Raises:
            PluginNotFoundError: If plugin not found.
            PluginConfigurationError: If validation fails.

        Note:
            Implementation details in T032-T036.
        """
        # Implementation in T032
        raise NotImplementedError("configure() not yet implemented (T032)")

    def get_config(
        self,
        plugin_type: PluginType,
        name: str,
    ) -> BaseModel | None:
        """Get the validated configuration for a plugin.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.

        Returns:
            The validated config, or None if not configured.

        Note:
            Implementation details in T036.
        """
        # Implementation in T036
        key = (plugin_type, name)
        return self._configs.get(key)

    def health_check_all(self) -> dict[str, HealthStatus]:
        """Check health of all loaded plugins.

        Returns:
            Dict mapping "type:name" to HealthStatus.

        Note:
            Only checks LOADED plugins (not discovered-only).
            Implementation details in T046-T049.
        """
        # Implementation in T046
        raise NotImplementedError("health_check_all() not yet implemented (T046)")


def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton.

    Thread-safe initialization. Automatically calls discover_all()
    on first access.

    Returns:
        The singleton PluginRegistry instance.

    Note:
        Implementation details in T014.
    """
    # Implementation in T014
    raise NotImplementedError("get_registry() not yet implemented (T014)")


def _reset_registry() -> None:
    """Reset the global registry singleton (for testing only).

    This clears the singleton instance, allowing a fresh registry
    to be created on next get_registry() call.

    Warning:
        Only use in tests. Not for production use.

    Note:
        Implementation details in T015.
    """
    # Implementation in T015
    global _registry
    _registry = None
