"""Plugin loading from entry points.

This module handles loading plugin classes from entry points and instantiating them.
It follows the lazy loading pattern - plugins are only imported when accessed.

Extracted from plugin_registry.py as part of Epic 12B US4 (God Module Decomposition)
to reduce the file from 1230 lines to focused, single-responsibility modules.

Example:
    >>> from floe_core.plugins.loader import PluginLoader
    >>> from floe_core.plugins.discovery import PluginDiscovery
    >>> from floe_core.plugin_types import PluginType
    >>>
    >>> discovery = PluginDiscovery()
    >>> discovery.discover_all()
    >>> loader = PluginLoader(discovery)
    >>> plugin = loader.get(PluginType.COMPUTE, "duckdb")

Requirements Covered:
    - FR-003: Split plugin_registry.py into focused modules each ≤400 lines
    - 12B-ARCH-003: SRP decomposition of plugin registry
"""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import TYPE_CHECKING

import structlog

from floe_core.plugin_errors import (
    DuplicatePluginError,
    PluginIncompatibleError,
    PluginNotFoundError,
)
from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.version_compat import FLOE_PLUGIN_API_VERSION, is_compatible

if TYPE_CHECKING:
    from floe_core.plugins.discovery import PluginDiscovery

logger = structlog.get_logger(__name__)


class PluginLoader:
    """Loads plugin classes from entry points and manages loaded instances.

    This class is responsible solely for:
    - Loading plugin classes from entry points (lazy loading)
    - Instantiating plugin classes
    - Caching loaded plugin instances
    - Version compatibility checking
    - Manual plugin registration (for testing)

    The loading process:
    1. Check if plugin already loaded (cache hit)
    2. Get entry point from discovery
    3. Load plugin class via entry point
    4. Instantiate plugin and check version
    5. Cache for subsequent access

    Attributes:
        _discovery: PluginDiscovery instance for entry point lookup.
        _loaded: Dict mapping (PluginType, name) to loaded plugin instance.

    Example:
        >>> loader = PluginLoader(discovery)
        >>> plugin = loader.get(PluginType.COMPUTE, "duckdb")
        >>> plugin.name
        'duckdb'
    """

    def __init__(self, discovery: PluginDiscovery) -> None:
        """Initialize plugin loader with discovery instance.

        Args:
            discovery: PluginDiscovery instance to use for entry point lookup.
        """
        self._discovery = discovery

        # Plugin instances that have been loaded
        # Key: (PluginType, plugin_name), Value: PluginMetadata instance
        self._loaded: dict[tuple[PluginType, str], PluginMetadata] = {}

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

        Example:
            >>> loader = PluginLoader(discovery)
            >>> duckdb = loader.get(PluginType.COMPUTE, "duckdb")
            >>> duckdb.name
            'duckdb'
        """
        key = (plugin_type, name)

        # Fast path: already loaded
        if key in self._loaded:
            return self._loaded[key]

        # Check if discovered (entry point exists)
        entry_point = self._discovery.get_entry_point(plugin_type, name)
        if entry_point is None:
            logger.debug(
                "get.not_found",
                plugin_type=plugin_type.name,
                name=name,
            )
            raise PluginNotFoundError(plugin_type, name)

        # Lazy load: import and instantiate the plugin
        plugin = self._load_plugin(plugin_type, name, entry_point)

        return plugin

    def _load_plugin(
        self,
        plugin_type: PluginType,
        name: str,
        entry_point: EntryPoint,
    ) -> PluginMetadata:
        """Load a plugin from an entry point.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            entry_point: The entry point to load.

        Returns:
            The loaded plugin instance.

        Raises:
            PluginIncompatibleError: If version check fails.
        """
        key = (plugin_type, name)

        logger.debug(
            "load_plugin.started",
            plugin_type=plugin_type.name,
            name=name,
            entry_point=entry_point.value,
        )

        # Load the plugin class from entry point
        plugin_class = entry_point.load()

        # Instantiate the plugin
        plugin: PluginMetadata = plugin_class()

        # Check version compatibility
        if not is_compatible(plugin.floe_api_version, FLOE_PLUGIN_API_VERSION):
            logger.warning(
                "load_plugin.incompatible",
                plugin_type=plugin_type.name,
                name=name,
                plugin_version=plugin.floe_api_version,
                platform_version=FLOE_PLUGIN_API_VERSION,
            )
            raise PluginIncompatibleError(
                name,
                plugin.floe_api_version,
                FLOE_PLUGIN_API_VERSION,
            )

        # Cache the loaded plugin
        self._loaded[key] = plugin

        logger.debug(
            "load_plugin.success",
            plugin_type=plugin_type.name,
            name=name,
            version=plugin.version,
        )

        return plugin

    def register(self, plugin_type: PluginType, plugin: PluginMetadata) -> None:
        """Manually register a plugin instance.

        Use this for testing or for plugins that aren't installed via
        entry points.

        Args:
            plugin_type: The plugin category (e.g., PluginType.COMPUTE).
            plugin: Plugin instance to register.

        Raises:
            DuplicatePluginError: If plugin with same type+name exists.
            PluginIncompatibleError: If version check fails.

        Example:
            >>> class MyPlugin(PluginMetadata):
            ...     name = "my-plugin"
            ...     version = "1.0.0"
            ...     floe_api_version = "1.0"
            >>> loader.register(PluginType.COMPUTE, MyPlugin())
        """
        key = (plugin_type, plugin.name)

        # Check for duplicate registration
        if key in self._loaded:
            logger.warning(
                "register.duplicate",
                plugin_type=plugin_type.name,
                name=plugin.name,
            )
            raise DuplicatePluginError(plugin_type, plugin.name)

        # Check version compatibility
        if not is_compatible(plugin.floe_api_version, FLOE_PLUGIN_API_VERSION):
            logger.warning(
                "register.incompatible",
                plugin_type=plugin_type.name,
                name=plugin.name,
                plugin_version=plugin.floe_api_version,
                platform_version=FLOE_PLUGIN_API_VERSION,
            )
            raise PluginIncompatibleError(
                plugin.name,
                plugin.floe_api_version,
                FLOE_PLUGIN_API_VERSION,
            )

        # Store in loaded dict
        self._loaded[key] = plugin

        logger.debug(
            "register.success",
            plugin_type=plugin_type.name,
            name=plugin.name,
            version=plugin.version,
        )

    def is_loaded(self, plugin_type: PluginType, name: str) -> bool:
        """Check if a plugin is already loaded.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.

        Returns:
            True if plugin is loaded and cached.
        """
        return (plugin_type, name) in self._loaded

    def get_loaded(self) -> dict[tuple[PluginType, str], PluginMetadata]:
        """Get all loaded plugin instances.

        Returns:
            Dict mapping (PluginType, name) to plugin instance.
        """
        return self._loaded.copy()

    def list_loaded_names(self, plugin_type: PluginType | None = None) -> list[str]:
        """List names of all loaded plugins.

        Args:
            plugin_type: Optional filter by plugin type. If None, returns all.

        Returns:
            List of plugin names.
        """
        if plugin_type is None:
            return [name for (_, name) in self._loaded.keys()]

        return [name for (pt, name) in self._loaded.keys() if pt == plugin_type]

    def unload(self, plugin_type: PluginType, name: str) -> bool:
        """Unload a plugin from the cache.

        This removes the plugin from the loaded cache, but does NOT
        call any lifecycle hooks. Use PluginLifecycle.shutdown_plugin()
        for proper shutdown.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.

        Returns:
            True if plugin was unloaded, False if not found.
        """
        key = (plugin_type, name)

        if key in self._loaded:
            del self._loaded[key]
            logger.debug(
                "unload.success",
                plugin_type=plugin_type.name,
                name=name,
            )
            return True

        logger.debug(
            "unload.not_found",
            plugin_type=plugin_type.name,
            name=name,
        )
        return False

    def clear(self) -> None:
        """Clear all loaded plugins (for testing).

        This removes all plugins from the loaded cache, but does NOT
        call any lifecycle hooks.
        """
        self._loaded.clear()
        logger.debug("loader.cleared")


__all__ = [
    "PluginLoader",
]
