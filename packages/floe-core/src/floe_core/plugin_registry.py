"""Plugin registry for discovering and managing floe plugins.

This module provides the central registry for all floe plugins. It serves as a
facade over the focused plugin modules:
- discovery.py: Entry point scanning
- loader.py: Plugin loading and caching
- lifecycle.py: Activation, shutdown, health checks
- dependencies.py: Dependency resolution

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

Architecture Note:
    This module was refactored in Epic 12B US4 (God Module Decomposition) from
    1230 lines to a ~350 line facade. The implementation details are now in
    focused, single-responsibility modules under floe_core.plugins/.
"""

from __future__ import annotations

import builtins
import threading
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.plugin_errors import PluginConfigurationError
from floe_core.plugin_metadata import HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.plugins.dependencies import DependencyResolver
from floe_core.plugins.discovery import PluginDiscovery
from floe_core.plugins.lifecycle import (
    DEFAULT_HEALTH_CHECK_TIMEOUT,
    DEFAULT_LIFECYCLE_TIMEOUT,
    PluginLifecycle,
)
from floe_core.plugins.loader import PluginLoader

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# Module-level singleton instance and lock
_registry: PluginRegistry | None = None
_registry_lock = threading.Lock()


class _DiscoveredProxy:
    """Proxy class for backward-compatible access to discovered plugins.

    This class provides dict-like access to discovered entry points,
    allowing both reading and writing while delegating to the underlying
    PluginDiscovery instance.

    This is primarily for backward compatibility with existing tests that
    directly assign to registry._discovered[(key)] = value.
    """

    def __init__(self, discovery: PluginDiscovery) -> None:
        self._discovery: PluginDiscovery = discovery

    def __getitem__(self, key: tuple[PluginType, str]) -> Any:
        """Get an entry point by key."""
        ep: Any = self._discovery.get_entry_point(key[0], key[1])
        if ep is None:
            raise KeyError(key)
        return ep

    def __setitem__(self, key: tuple[PluginType, str], value: Any) -> None:
        """Set an entry point by key (for testing)."""
        self._discovery.register_entry_point(key[0], key[1], value)

    def __contains__(self, key: object) -> bool:
        """Check if key exists."""
        if not isinstance(key, tuple) or len(key) != 2:
            return False
        plugin_type, name = key
        if not isinstance(plugin_type, PluginType) or not isinstance(name, str):
            return False
        return self._discovery.is_discovered(plugin_type, name)

    def __iter__(self) -> Any:
        """Iterate over keys."""
        return iter(self._discovery.get_discovered().keys())

    def __len__(self) -> int:
        """Return number of discovered plugins."""
        return len(self._discovery.get_discovered())

    def get(
        self, key: tuple[PluginType, str], default: Any = None
    ) -> Any:
        """Get with default."""
        return self._discovery.get_entry_point(key[0], key[1]) or default

    def keys(self) -> Any:
        """Return keys."""
        return self._discovery.get_discovered().keys()

    def values(self) -> Any:
        """Return values."""
        return self._discovery.get_discovered().values()

    def items(self) -> Any:
        """Return items."""
        return self._discovery.get_discovered().items()


class PluginRegistry:
    """Central registry for discovering and managing floe plugins.

    This class serves as a facade over the focused plugin modules,
    maintaining backward compatibility while delegating to:
    - PluginDiscovery: Entry point scanning
    - PluginLoader: Plugin loading and caching
    - PluginLifecycle: Activation, shutdown, health checks
    - DependencyResolver: Dependency resolution

    Attributes:
        _discovery: PluginDiscovery instance for entry point scanning.
        _loader: PluginLoader instance for loading plugins.
        _lifecycle: PluginLifecycle instance for lifecycle management.
        _resolver: DependencyResolver instance for dependency resolution.
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
        # Initialize focused modules
        self._discovery = PluginDiscovery()
        self._loader = PluginLoader(self._discovery)
        self._lifecycle = PluginLifecycle(self._loader)
        self._resolver = DependencyResolver()

        # Validated configurations for plugins (kept here for API compatibility)
        # Key: (PluginType, plugin_name), Value: BaseModel config instance
        self._configs: dict[tuple[PluginType, str], BaseModel] = {}

    # -------------------------------------------------------------------------
    # Discovery (delegates to PluginDiscovery)
    # -------------------------------------------------------------------------

    def discover_all(self) -> None:
        """Discover all plugins from entry points.

        Scans all plugin type entry point groups defined in PluginType.
        Does NOT load/import plugin classes - only discovers entry points.

        This method is idempotent - calling it multiple times has no effect
        after the first successful discovery.
        """
        self._discovery.discover_all()

    # -------------------------------------------------------------------------
    # Loading (delegates to PluginLoader)
    # -------------------------------------------------------------------------

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
        """
        self._loader.register(plugin_type, plugin)

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
        """
        return self._loader.get(plugin_type, name)

    def list(
        self,
        plugin_type: PluginType,
        *,
        limit: int | None = None,
    ) -> builtins.list[PluginMetadata]:
        """List all plugins of a specific type.

        Loads and returns all plugins for the given type. Each plugin
        is lazy-loaded on first access if not already loaded.

        Args:
            plugin_type: The plugin category to list.
            limit: Optional maximum number of plugins to return.

        Returns:
            List of plugin instances for that type (may be empty).
        """
        plugins: builtins.list[PluginMetadata] = []

        # Get discovered plugin names for this type
        discovered_names = self._discovery.list_discovered_names(plugin_type)

        for name in discovered_names:
            # Early exit if limit reached
            if limit is not None and len(plugins) >= limit:
                break

            try:
                plugin = self.get(plugin_type, name)
                plugins.append(plugin)
            except Exception as e:
                logger.warning(
                    "list.plugin_load_failed",
                    plugin_type=plugin_type.name,
                    name=name,
                    error=str(e),
                )

        logger.debug(
            "list.completed",
            plugin_type=plugin_type.name,
            count=len(plugins),
            limit=limit,
        )

        return plugins

    def list_all(self) -> dict[PluginType, builtins.list[str]]:
        """List all available plugins by type.

        Returns plugin names grouped by type. Does NOT load plugins -
        returns only discovered plugin names.

        Returns:
            Dict mapping PluginType to list of plugin names.
        """
        return self._discovery.list_all_by_type()

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------

    def configure(
        self,
        plugin_type: PluginType,
        name: str,
        config: dict[str, Any],
    ) -> BaseModel | None:
        """Configure a plugin with validated settings.

        Loads the plugin if not already loaded, retrieves its configuration
        schema, and validates the provided config.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            config: Configuration dictionary to validate.

        Returns:
            Validated Pydantic model instance, or None if plugin has no schema.

        Raises:
            PluginNotFoundError: If plugin not found.
            PluginConfigurationError: If validation fails.
        """
        from pydantic import ValidationError as PydanticValidationError

        key = (plugin_type, name)

        # Load plugin if not already loaded
        plugin = self.get(plugin_type, name)

        # Get the plugin's configuration schema
        schema_class = plugin.get_config_schema()

        if schema_class is None:
            logger.debug(
                "configure.no_schema",
                plugin_type=plugin_type.name,
                name=name,
            )
            self._configs[key] = None  # type: ignore[assignment]
            return None

        # Validate config using Pydantic
        try:
            validated_config = schema_class(**config)
        except PydanticValidationError as e:
            errors = self._convert_pydantic_errors(e)
            logger.warning(
                "configure.validation_failed",
                plugin_type=plugin_type.name,
                name=name,
                error_count=len(errors),
            )
            raise PluginConfigurationError(name, errors) from e

        self._configs[key] = validated_config

        logger.debug(
            "configure.success",
            plugin_type=plugin_type.name,
            name=name,
        )

        return validated_config

    def _convert_pydantic_errors(
        self,
        error: Any,
    ) -> builtins.list[dict[str, Any]]:
        """Convert Pydantic ValidationError to field-level error details."""
        errors: list[dict[str, Any]] = []

        for err in error.errors():
            loc = err.get("loc", ())
            field_path = ".".join(str(part) for part in loc)

            errors.append(
                {
                    "field": field_path,
                    "message": err.get("msg", "Unknown error"),
                    "type": err.get("type", "unknown"),
                }
            )

        return errors

    def get_config(
        self,
        plugin_type: PluginType,
        name: str,
    ) -> BaseModel | None:
        """Get the validated configuration for a plugin."""
        key = (plugin_type, name)
        return self._configs.get(key)

    # -------------------------------------------------------------------------
    # Lifecycle (delegates to PluginLifecycle)
    # -------------------------------------------------------------------------

    def activate_plugin(
        self,
        plugin_type: PluginType,
        name: str,
        timeout: float | None = None,
    ) -> None:
        """Activate a plugin by calling its startup() hook.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            timeout: Timeout in seconds (default: 30s per SC-006).

        Raises:
            PluginNotFoundError: If plugin not found.
            PluginStartupError: If startup() fails or times out.
        """
        self._lifecycle.activate_plugin(plugin_type, name, timeout)

    def activate_all(
        self,
        plugins: builtins.list[PluginMetadata] | None = None,
        plugin_types: builtins.list[PluginType] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Exception | None]:
        """Activate multiple plugins in dependency order.

        Args:
            plugins: Explicit list of plugins to activate.
            plugin_types: If plugins not provided, activate all of these types.
            timeout: Per-plugin timeout in seconds (default: 30s).

        Returns:
            Dict mapping "type:name" to exception (or None if success).

        Raises:
            CircularDependencyError: If circular dependencies detected.
            MissingDependencyError: If plugin has missing dependencies.
        """
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        # Determine which plugins to activate
        if plugins is not None:
            plugins_to_activate = plugins
        elif plugin_types is not None:
            plugins_to_activate = []
            for pt in plugin_types:
                plugins_to_activate.extend(self.list(pt))
        else:
            plugins_to_activate = list(self._loader.get_loaded().values())

        if not plugins_to_activate:
            return {}

        # Resolve dependencies to get correct activation order
        sorted_plugins = self._resolver.resolve(plugins_to_activate)

        # Build plugin_type_lookup
        plugin_type_lookup: dict[str, PluginType] = {}
        for (pt, pname), _ in self._loader.get_loaded().items():
            plugin_type_lookup[pname] = pt

        return self._lifecycle.activate_all(
            sorted_plugins,
            timeout=timeout,
            plugin_type_lookup=plugin_type_lookup,
        )

    def shutdown_all(
        self, timeout: float | None = None
    ) -> dict[str, Exception | None]:
        """Shutdown all activated plugins.

        Args:
            timeout: Per-plugin timeout in seconds (default: 30s).

        Returns:
            Dict mapping "type:name" to exception (or None if success).
        """
        return self._lifecycle.shutdown_all(timeout)

    def health_check_all(
        self,
        timeout: float | None = None,
    ) -> dict[str, HealthStatus]:
        """Check health of all loaded plugins.

        Args:
            timeout: Per-plugin timeout in seconds (default: 5s).

        Returns:
            Dict mapping "type:name" to HealthStatus.
        """
        return self._lifecycle.health_check_all(timeout)

    # -------------------------------------------------------------------------
    # Dependencies (delegates to DependencyResolver)
    # -------------------------------------------------------------------------

    def resolve_dependencies(
        self,
        plugins: builtins.list[PluginMetadata],
    ) -> builtins.list[PluginMetadata]:
        """Resolve plugin dependencies and return plugins in load order.

        Args:
            plugins: List of plugin instances to sort by dependencies.

        Returns:
            Plugins sorted in dependency order (load dependencies first).

        Raises:
            CircularDependencyError: If a circular dependency is detected.
            MissingDependencyError: If a plugin has missing dependencies.
        """
        return self._resolver.resolve(plugins)

    # -------------------------------------------------------------------------
    # Internal accessors (for backward compatibility and testing)
    # -------------------------------------------------------------------------

    @property
    def _discovered(self) -> _DiscoveredProxy:
        """Access discovered entry points (backward compatibility).

        Returns a proxy object that allows dict-like access while delegating
        to the underlying PluginDiscovery instance. This supports both reading
        and writing for backward compatibility with existing tests.
        """
        return _DiscoveredProxy(self._discovery)

    @property
    def _loaded(self) -> dict[tuple[PluginType, str], PluginMetadata]:
        """Access loaded plugins (backward compatibility)."""
        return self._loader.get_loaded()

    @property
    def _activated(self) -> set[tuple[PluginType, str]]:
        """Access activated plugins (backward compatibility)."""
        return self._lifecycle.get_activated()

    @property
    def _discovered_all(self) -> bool:
        """Check if discovery has been run (backward compatibility)."""
        return self._discovery.has_discovered


def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton.

    Thread-safe initialization. Automatically calls discover_all()
    on first access.

    Returns:
        The singleton PluginRegistry instance.
    """
    global _registry

    # Fast path: registry already initialized
    if _registry is not None:
        return _registry

    # Slow path: thread-safe initialization
    with _registry_lock:
        if _registry is not None:
            return _registry

        logger.debug("get_registry.initializing")
        _registry = PluginRegistry()
        _registry.discover_all()
        logger.info("get_registry.initialized")
        return _registry


def _reset_registry() -> None:  # pyright: ignore[reportUnusedFunction]
    """Reset the global registry singleton (for testing only)."""
    global _registry

    with _registry_lock:
        if _registry is not None:
            logger.debug("_reset_registry.clearing")
        _registry = None


# Re-export for backward compatibility
__all__ = [
    "PluginRegistry",
    "get_registry",
    "_reset_registry",
    "DEFAULT_LIFECYCLE_TIMEOUT",
    "DEFAULT_HEALTH_CHECK_TIMEOUT",
]
