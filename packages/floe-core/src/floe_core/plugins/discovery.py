"""Plugin discovery via entry points.

This module handles discovering plugins from installed packages via entry points.
It follows a lazy loading pattern - discover() scans entry points but does NOT
import plugin classes.

Extracted from plugin_registry.py as part of Epic 12B US4 (God Module Decomposition)
to reduce the file from 1230 lines to focused, single-responsibility modules.

Example:
    >>> from floe_core.plugins.discovery import PluginDiscovery
    >>> from floe_core.plugin_types import PluginType
    >>>
    >>> discovery = PluginDiscovery()
    >>> discovery.discover_all()
    >>> entry_points = discovery.list_discovered()

Requirements Covered:
    - FR-003: Split plugin_registry.py into focused modules each ≤400 lines
    - 12B-ARCH-003: SRP decomposition of plugin registry
"""

from __future__ import annotations

from importlib.metadata import EntryPoint, entry_points
from typing import TYPE_CHECKING

import structlog

from floe_core.plugin_types import PluginType

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class PluginDiscovery:
    """Discovers plugins from entry points without loading them.

    This class is responsible solely for scanning entry point groups
    and tracking which plugins are available. It does NOT import or
    instantiate plugins - that responsibility belongs to PluginLoader.

    The discovery process:
    1. Scans all plugin type entry point groups (floe.computes, floe.catalogs, etc.)
    2. Stores EntryPoint references for later lazy loading
    3. Logs any errors but continues (graceful degradation)

    Attributes:
        _discovered: Dict mapping (PluginType, name) to EntryPoint.
        _discovered_all: Flag indicating if discovery has been run.

    Example:
        >>> discovery = PluginDiscovery()
        >>> discovery.discover_all()
        >>> eps = discovery.get_discovered()
        >>> print(len(eps))
        15
    """

    def __init__(self) -> None:
        """Initialize an empty plugin discovery instance."""
        # Entry points discovered but not yet loaded
        # Key: (PluginType, plugin_name), Value: EntryPoint
        self._discovered: dict[tuple[PluginType, str], EntryPoint] = {}

        # Flag to track if discovery has been run
        self._discovered_all: bool = False

    def discover_all(self) -> int:
        """Discover all plugins from entry points.

        Scans all plugin type entry point groups defined in PluginType.
        Does NOT load/import plugin classes - only discovers entry points.

        This method is idempotent - calling it multiple times has no effect
        after the first successful discovery.

        Entry points with errors are logged but do not prevent discovery
        of other plugins (graceful degradation).

        Returns:
            Total number of plugins discovered across all types.

        Example:
            >>> discovery = PluginDiscovery()
            >>> count = discovery.discover_all()
            >>> print(f"Discovered {count} plugins")
        """
        if self._discovered_all:
            logger.debug("discover_all.skipped", reason="already_discovered")
            return len(self._discovered)

        logger.info("discover_all.started")
        total_discovered = 0

        # Scan all plugin type entry point groups
        for plugin_type in PluginType:
            group = plugin_type.entry_point_group
            discovered_count = self._discover_group(plugin_type, group)
            total_discovered += discovered_count

        self._discovered_all = True
        logger.info(
            "discover_all.completed",
            total_discovered=total_discovered,
            plugin_types_scanned=len(PluginType),
        )

        return total_discovered

    def _discover_group(self, plugin_type: PluginType, group: str) -> int:
        """Discover plugins from a single entry point group.

        Args:
            plugin_type: The PluginType for this group.
            group: The entry point group name (e.g., "floe.computes").

        Returns:
            Number of plugins discovered in this group.
        """
        discovered_count = 0

        try:
            eps = entry_points(group=group)
        except Exception as e:
            # Graceful degradation - log error but continue with other groups
            logger.error(
                "discover_group.failed",
                plugin_type=plugin_type.name,
                group=group,
                error=str(e),
            )
            return 0

        for ep in eps:
            try:
                key = (plugin_type, ep.name)

                if key in self._discovered:
                    logger.warning(
                        "discover_group.duplicate",
                        plugin_type=plugin_type.name,
                        name=ep.name,
                        group=group,
                    )
                    continue

                self._discovered[key] = ep
                discovered_count += 1

                logger.debug(
                    "discover_group.found",
                    plugin_type=plugin_type.name,
                    name=ep.name,
                    value=ep.value,
                )
            except Exception as e:
                # Graceful degradation - log error but continue with other entry points
                logger.error(
                    "discover_group.entry_point_error",
                    plugin_type=plugin_type.name,
                    name=getattr(ep, "name", "unknown"),
                    error=str(e),
                )

        if discovered_count > 0:
            logger.debug(
                "discover_group.completed",
                plugin_type=plugin_type.name,
                group=group,
                count=discovered_count,
            )

        return discovered_count

    def is_discovered(self, plugin_type: PluginType, name: str) -> bool:
        """Check if a plugin has been discovered.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.

        Returns:
            True if plugin entry point has been discovered.
        """
        return (plugin_type, name) in self._discovered

    def get_entry_point(
        self, plugin_type: PluginType, name: str
    ) -> EntryPoint | None:
        """Get the entry point for a discovered plugin.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.

        Returns:
            The EntryPoint if found, None otherwise.
        """
        return self._discovered.get((plugin_type, name))

    def get_discovered(self) -> dict[tuple[PluginType, str], EntryPoint]:
        """Get all discovered entry points.

        Returns:
            Dict mapping (PluginType, name) to EntryPoint.
        """
        return self._discovered.copy()

    def list_discovered_names(
        self, plugin_type: PluginType | None = None
    ) -> list[str]:
        """List names of all discovered plugins.

        Args:
            plugin_type: Optional filter by plugin type. If None, returns all.

        Returns:
            List of plugin names.
        """
        if plugin_type is None:
            return [name for (_, name) in self._discovered.keys()]

        return [
            name
            for (pt, name) in self._discovered.keys()
            if pt == plugin_type
        ]

    def list_all_by_type(self) -> dict[PluginType, list[str]]:
        """List all available plugins by type.

        Returns plugin names grouped by type. Does NOT load plugins -
        returns only discovered plugin names.

        Returns:
            Dict mapping PluginType to list of plugin names.

        Example:
            >>> discovery = PluginDiscovery()
            >>> discovery.discover_all()
            >>> all_plugins = discovery.list_all_by_type()
            >>> all_plugins[PluginType.COMPUTE]
            ['duckdb', 'snowflake']
        """
        result: dict[PluginType, list[str]] = {}

        # Initialize all plugin types with empty lists
        for plugin_type in PluginType:
            result[plugin_type] = []

        # Populate with discovered plugin names
        for plugin_type, name in self._discovered.keys():
            result[plugin_type].append(name)

        # Sort names for consistent output
        for plugin_type in result:
            result[plugin_type].sort()

        logger.debug(
            "list_all_by_type.completed",
            total_plugins=sum(len(names) for names in result.values()),
        )

        return result

    @property
    def has_discovered(self) -> bool:
        """Check if discovery has been run.

        Returns:
            True if discover_all() has been called.
        """
        return self._discovered_all

    def clear(self) -> None:
        """Clear all discovered plugins (for testing).

        Resets the discovery state, allowing discover_all() to run again.
        """
        self._discovered.clear()
        self._discovered_all = False
        logger.debug("discovery.cleared")

    def register_entry_point(
        self,
        plugin_type: PluginType,
        name: str,
        entry_point: EntryPoint,
    ) -> None:
        """Register an entry point directly (for testing).

        This bypasses the normal entry point scanning and allows tests
        to inject mock entry points directly.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            entry_point: The EntryPoint to register.

        Note:
            This is primarily for testing. In production, plugins should
            be discovered via discover_all().
        """
        key = (plugin_type, name)
        self._discovered[key] = entry_point
        logger.debug(
            "register_entry_point.registered",
            plugin_type=plugin_type.name,
            name=name,
        )


__all__ = [
    "PluginDiscovery",
]
