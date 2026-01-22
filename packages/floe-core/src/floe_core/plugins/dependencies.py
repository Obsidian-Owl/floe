"""Plugin dependency resolution using Kahn's algorithm.

This module handles resolving plugin dependencies to determine the correct
loading order. Plugins can declare dependencies on other plugins, and this
module ensures they are loaded in the correct order.

Extracted from plugin_registry.py as part of Epic 12B US4 (God Module Decomposition)
to reduce the file from 1230 lines to focused, single-responsibility modules.

Example:
    >>> from floe_core.plugins.dependencies import DependencyResolver
    >>> from floe_core.plugin_metadata import PluginMetadata
    >>>
    >>> resolver = DependencyResolver()
    >>> sorted_plugins = resolver.resolve([plugin_a, plugin_b, plugin_c])
    >>> # Returns plugins in dependency order (dependencies first)

Requirements Covered:
    - FR-003: Split plugin_registry.py into focused modules each ≤400 lines
    - 12B-ARCH-003: SRP decomposition of plugin registry
"""

from __future__ import annotations

import structlog

from floe_core.plugin_errors import (
    CircularDependencyError,
    MissingDependencyError,
)
from floe_core.plugin_metadata import PluginMetadata

logger = structlog.get_logger(__name__)


class DependencyResolver:
    """Resolves plugin dependencies using topological sorting (Kahn's algorithm).

    This class is responsible solely for:
    - Checking for missing dependencies
    - Detecting circular dependencies
    - Sorting plugins by dependency order

    The resolution process:
    1. Build dependency graph from plugin metadata
    2. Check for missing dependencies
    3. Use Kahn's algorithm for topological sort
    4. Detect cycles if sort fails
    5. Return plugins in correct load order

    Example:
        >>> resolver = DependencyResolver()
        >>> # Plugin A depends on B, B depends on C
        >>> sorted_plugins = resolver.resolve([A, B, C])
        >>> [p.name for p in sorted_plugins]
        ['C', 'B', 'A']
    """

    def resolve(
        self,
        plugins: list[PluginMetadata],
    ) -> list[PluginMetadata]:
        """Resolve plugin dependencies and return plugins in load order.

        Uses Kahn's algorithm for topological sorting to determine the
        correct order to load plugins based on their declared dependencies.
        Plugins with no dependencies are returned first, followed by plugins
        whose dependencies have already been resolved.

        Args:
            plugins: List of plugin instances to sort by dependencies.

        Returns:
            Plugins sorted in dependency order (load dependencies first).

        Raises:
            CircularDependencyError: If a circular dependency is detected.
            MissingDependencyError: If a plugin declares a dependency that is
                not in the provided plugin list.

        Example:
            >>> # Plugin A depends on B, B depends on C
            >>> sorted_plugins = resolver.resolve([A, B, C])
            >>> [p.name for p in sorted_plugins]
            ['C', 'B', 'A']
        """
        if not plugins:
            return []

        # Build name -> plugin mapping for fast lookup
        plugin_map: dict[str, PluginMetadata] = {p.name: p for p in plugins}
        plugin_names = set(plugin_map.keys())

        # Check for missing dependencies before proceeding
        self._check_missing_dependencies(plugins, plugin_names)

        # Build adjacency list and in-degree count
        # Graph: dependency -> dependents (edges point from dependency to dependent)
        # in_degree: count of dependencies for each plugin
        in_degree: dict[str, int] = dict.fromkeys(plugin_names, 0)
        dependents: dict[str, list[str]] = {name: [] for name in plugin_names}

        for plugin in plugins:
            for dep_name in plugin.dependencies:
                # Only count dependencies that are in our plugin set
                if dep_name in plugin_names:
                    in_degree[plugin.name] += 1
                    dependents[dep_name].append(plugin.name)

        # Kahn's algorithm: start with plugins that have no dependencies
        queue: list[str] = [
            name for name, degree in in_degree.items() if degree == 0
        ]
        sorted_names: list[str] = []

        logger.debug(
            "resolve.started",
            plugin_count=len(plugins),
            initial_queue_size=len(queue),
        )

        while queue:
            # Process next plugin with no unresolved dependencies
            current = queue.pop(0)
            sorted_names.append(current)

            # Reduce in-degree of dependents
            for dependent in dependents[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycle: if not all plugins processed, there's a cycle
        if len(sorted_names) != len(plugins):
            # Find the cycle for error reporting
            cycle = self._find_cycle(plugins, in_degree)
            logger.error(
                "resolve.circular_dependency",
                cycle=cycle,
                processed=len(sorted_names),
                total=len(plugins),
            )
            raise CircularDependencyError(cycle)

        logger.debug(
            "resolve.completed",
            order=list(sorted_names),
        )

        # Return plugins in sorted order
        return [plugin_map[name] for name in sorted_names]

    def _check_missing_dependencies(
        self,
        plugins: list[PluginMetadata],
        available_names: set[str],
    ) -> None:
        """Check if any plugin has dependencies not in the available set.

        Args:
            plugins: List of plugins to check.
            available_names: Set of plugin names that are available.

        Raises:
            MissingDependencyError: If any plugin has missing dependencies.
        """
        for plugin in plugins:
            missing = [
                dep for dep in plugin.dependencies if dep not in available_names
            ]
            if missing:
                logger.error(
                    "resolve.missing_dependency",
                    plugin=plugin.name,
                    missing=missing,
                )
                raise MissingDependencyError(plugin.name, missing)

    def _find_cycle(
        self,
        plugins: list[PluginMetadata],
        in_degree: dict[str, int],
    ) -> list[str]:
        """Find a cycle in the dependency graph for error reporting.

        Uses DFS to find a cycle starting from any node that wasn't
        processed (has remaining in-degree > 0).

        Args:
            plugins: List of plugins in the graph.
            in_degree: Remaining in-degree after Kahn's algorithm.

        Returns:
            List of plugin names forming the cycle (includes start twice).
        """
        # Build dependency map: plugin -> its dependencies
        plugin_map = {p.name: p for p in plugins}
        plugin_names = set(plugin_map.keys())

        # Find a node that's part of the cycle (in_degree > 0)
        cycle_nodes = [name for name, deg in in_degree.items() if deg > 0]
        if not cycle_nodes:
            return ["unknown"]

        start = cycle_nodes[0]

        # DFS to find the cycle
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            if node in visited:
                # Found cycle - extract it from path
                if node in path:
                    cycle_start = path.index(node)
                    return path[cycle_start:] + [node]
                return None

            visited.add(node)
            path.append(node)

            plugin = plugin_map.get(node)
            if plugin:
                for dep in plugin.dependencies:
                    if dep in plugin_names and in_degree.get(dep, 0) > 0:
                        result = dfs(dep)
                        if result:
                            return result

            path.pop()
            return None

        cycle = dfs(start)
        return cycle if cycle else [start, "...", start]

    def get_dependency_graph(
        self,
        plugins: list[PluginMetadata],
    ) -> dict[str, list[str]]:
        """Build and return the dependency graph.

        Useful for debugging and visualization.

        Args:
            plugins: List of plugins to analyze.

        Returns:
            Dict mapping plugin name to list of its dependencies.
        """
        return {p.name: list(p.dependencies) for p in plugins}

    def get_dependents(
        self,
        plugins: list[PluginMetadata],
    ) -> dict[str, list[str]]:
        """Build and return the reverse dependency graph.

        Shows which plugins depend on each plugin.

        Args:
            plugins: List of plugins to analyze.

        Returns:
            Dict mapping plugin name to list of plugins that depend on it.
        """
        plugin_names = {p.name for p in plugins}
        dependents: dict[str, list[str]] = {p.name: [] for p in plugins}

        for plugin in plugins:
            for dep_name in plugin.dependencies:
                if dep_name in plugin_names:
                    dependents[dep_name].append(plugin.name)

        return dependents


__all__ = [
    "DependencyResolver",
]
