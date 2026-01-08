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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from importlib.metadata import EntryPoint, entry_points
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.plugin_errors import (
    CircularDependencyError,
    DuplicatePluginError,
    MissingDependencyError,
    PluginConfigurationError,
    PluginIncompatibleError,
    PluginNotFoundError,
    PluginStartupError,
)
from floe_core.plugin_metadata import HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.version_compat import FLOE_PLUGIN_API_VERSION, is_compatible

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# Default timeout for lifecycle hooks (SC-006: 30 seconds)
DEFAULT_LIFECYCLE_TIMEOUT: float = 30.0

# Default timeout for health checks (SC-007: 5 seconds)
DEFAULT_HEALTH_CHECK_TIMEOUT: float = 5.0

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

        # Plugins that have been activated (startup() called)
        # Key: (PluginType, plugin_name)
        self._activated: set[tuple[PluginType, str]] = set()

        # Flag to track if discovery has been run
        self._discovered_all: bool = False

    def discover_all(self) -> None:
        """Discover all plugins from entry points.

        Scans all plugin type entry point groups defined in PluginType.
        Does NOT load/import plugin classes - only discovers entry points.

        This method is idempotent - calling it multiple times has no effect
        after the first successful discovery.

        Entry points with errors are logged but do not prevent discovery
        of other plugins (graceful degradation).
        """
        if self._discovered_all:
            logger.debug("discover_all.skipped", reason="already_discovered")
            return

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
                # Error handling details in T013
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
            >>> registry.register(PluginType.COMPUTE, MyPlugin())
        """
        key = (plugin_type, plugin.name)

        # Check for duplicate registration (T022)
        if key in self._loaded:
            logger.warning(
                "register.duplicate",
                plugin_type=plugin_type.name,
                name=plugin.name,
            )
            raise DuplicatePluginError(plugin_type, plugin.name)

        # Check version compatibility (T018)
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
            >>> registry = get_registry()
            >>> duckdb = registry.get(PluginType.COMPUTE, "duckdb")
            >>> duckdb.name
            'duckdb'
        """
        key = (plugin_type, name)

        # Fast path: already loaded
        if key in self._loaded:
            return self._loaded[key]

        # Check if discovered (entry point exists)
        if key not in self._discovered:
            logger.debug(
                "get.not_found",
                plugin_type=plugin_type.name,
                name=name,
            )
            raise PluginNotFoundError(plugin_type, name)

        # Lazy load: import and instantiate the plugin
        entry_point = self._discovered[key]
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

    def list(self, plugin_type: PluginType) -> builtins.list[PluginMetadata]:
        """List all plugins of a specific type.

        Loads and returns all plugins for the given type. Each plugin
        is lazy-loaded on first access if not already loaded.

        Args:
            plugin_type: The plugin category to list.

        Returns:
            List of plugin instances for that type (may be empty).

        Example:
            >>> registry = get_registry()
            >>> compute_plugins = registry.list(PluginType.COMPUTE)
            >>> [p.name for p in compute_plugins]
            ['duckdb', 'snowflake']
        """
        plugins: builtins.list[PluginMetadata] = []

        # Collect all discovered plugins of this type
        for pt, name in self._discovered.keys():
            if pt != plugin_type:
                continue

            try:
                # Use get() to leverage lazy loading and caching
                plugin = self.get(plugin_type, name)
                plugins.append(plugin)
            except Exception as e:
                # Log but continue with other plugins (graceful degradation)
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
        )

        return plugins

    def list_all(self) -> dict[PluginType, builtins.list[str]]:
        """List all available plugins by type.

        Returns plugin names grouped by type. Does NOT load plugins -
        returns only discovered plugin names.

        Returns:
            Dict mapping PluginType to list of plugin names.

        Example:
            >>> registry = get_registry()
            >>> all_plugins = registry.list_all()
            >>> all_plugins[PluginType.COMPUTE]
            ['duckdb', 'snowflake']
        """
        result: dict[PluginType, builtins.list[str]] = {}

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
            "list_all.completed",
            total_plugins=sum(len(names) for names in result.values()),
        )

        return result

    def configure(
        self,
        plugin_type: PluginType,
        name: str,
        config: dict[str, Any],
    ) -> BaseModel | None:
        """Configure a plugin with validated settings.

        Loads the plugin if not already loaded, retrieves its configuration
        schema, and validates the provided config. The validated configuration
        is stored for later retrieval via get_config().

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            config: Configuration dictionary to validate.

        Returns:
            Validated Pydantic model instance, or None if plugin has no schema.

        Raises:
            PluginNotFoundError: If plugin not found.
            PluginConfigurationError: If validation fails with field-level errors.

        Example:
            >>> registry = get_registry()
            >>> config = registry.configure(
            ...     PluginType.COMPUTE,
            ...     "duckdb",
            ...     {"threads": 4}
            ... )
            >>> config.threads
            4
        """
        from pydantic import ValidationError as PydanticValidationError

        key = (plugin_type, name)

        # Load plugin if not already loaded (may raise PluginNotFoundError)
        plugin = self.get(plugin_type, name)

        # Get the plugin's configuration schema
        schema_class = plugin.get_config_schema()

        if schema_class is None:
            # Plugin has no configuration schema - store None
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
            # Convert Pydantic errors to field-level error details
            errors = self._convert_pydantic_errors(e)
            logger.warning(
                "configure.validation_failed",
                plugin_type=plugin_type.name,
                name=name,
                error_count=len(errors),
            )
            raise PluginConfigurationError(name, errors) from e

        # Store validated config
        self._configs[key] = validated_config

        logger.debug(
            "configure.success",
            plugin_type=plugin_type.name,
            name=name,
        )

        return validated_config

    def _convert_pydantic_errors(
        self,
        error: Any,  # PydanticValidationError
    ) -> builtins.list[dict[str, Any]]:
        """Convert Pydantic ValidationError to field-level error details.

        Args:
            error: Pydantic ValidationError instance.

        Returns:
            List of error dicts with 'field', 'message', and 'type' keys.
        """
        errors: list[dict[str, Any]] = []

        for err in error.errors():
            # Build field path from location tuple
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

    def activate_plugin(
        self,
        plugin_type: PluginType,
        name: str,
        timeout: float | None = None,
    ) -> None:
        """Activate a plugin by calling its startup() hook.

        Loads the plugin if not already loaded, then calls startup() with
        timeout protection. The plugin is marked as activated on success.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.
            timeout: Timeout in seconds (default: 30s per SC-006).

        Raises:
            PluginNotFoundError: If plugin not found.
            PluginStartupError: If startup() fails or times out.

        Example:
            >>> registry = get_registry()
            >>> registry.activate_plugin(PluginType.COMPUTE, "duckdb")
        """
        key = (plugin_type, name)

        # Check if already activated
        if key in self._activated:
            logger.debug(
                "activate_plugin.already_activated",
                plugin_type=plugin_type.name,
                name=name,
            )
            return

        # Load plugin (may raise PluginNotFoundError)
        plugin = self.get(plugin_type, name)

        # Use default timeout if not specified
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        logger.debug(
            "activate_plugin.starting",
            plugin_type=plugin_type.name,
            name=name,
            timeout=timeout,
        )

        # Run startup() with timeout protection
        try:
            self._run_with_timeout(plugin.startup, timeout)
        except FutureTimeoutError:
            logger.error(
                "activate_plugin.timeout",
                plugin_type=plugin_type.name,
                name=name,
                timeout=timeout,
            )
            raise PluginStartupError(
                plugin_type,
                name,
                TimeoutError(f"startup() timed out after {timeout}s"),
            ) from None
        except Exception as e:
            logger.error(
                "activate_plugin.failed",
                plugin_type=plugin_type.name,
                name=name,
                error=str(e),
            )
            raise PluginStartupError(plugin_type, name, e) from e

        # Mark as activated on success
        self._activated.add(key)

        logger.info(
            "activate_plugin.success",
            plugin_type=plugin_type.name,
            name=name,
        )

    def activate_all(
        self,
        plugins: builtins.list[PluginMetadata] | None = None,
        plugin_types: builtins.list[PluginType] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Exception | None]:
        """Activate multiple plugins in dependency order.

        Resolves dependencies between plugins and activates them in the
        correct order (dependencies before dependents). This ensures plugins
        can rely on their dependencies being available during startup.

        Args:
            plugins: Explicit list of plugins to activate. If not provided,
                activates all loaded plugins or those matching plugin_types.
            plugin_types: If plugins not provided, activate all plugins of
                these types. If None, activates all loaded plugins.
            timeout: Per-plugin timeout in seconds (default: 30s per SC-006).

        Returns:
            Dict mapping "type:name" to exception (or None if success).

        Raises:
            CircularDependencyError: If circular dependencies detected.
            MissingDependencyError: If plugin has missing dependencies.

        Example:
            >>> registry = get_registry()
            >>> # Activate all loaded plugins in dependency order
            >>> results = registry.activate_all()
            >>> # Activate specific plugin types
            >>> results = registry.activate_all(
            ...     plugin_types=[PluginType.COMPUTE, PluginType.CATALOG]
            ... )
        """
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        results: dict[str, Exception | None] = {}

        # Determine which plugins to activate
        if plugins is not None:
            plugins_to_activate = plugins
        elif plugin_types is not None:
            # Load all plugins of specified types
            plugins_to_activate = []
            for pt in plugin_types:
                plugins_to_activate.extend(self.list(pt))
        else:
            # Activate all loaded plugins
            plugins_to_activate = list(self._loaded.values())

        if not plugins_to_activate:
            logger.debug("activate_all.no_plugins")
            return results

        logger.info(
            "activate_all.starting",
            plugin_count=len(plugins_to_activate),
            timeout_per_plugin=timeout,
        )

        # Resolve dependencies to get correct activation order
        # This may raise CircularDependencyError or MissingDependencyError
        sorted_plugins = self.resolve_dependencies(plugins_to_activate)

        # Build reverse lookup: plugin name -> plugin type
        # This is needed because PluginMetadata doesn't store its type
        plugin_type_lookup: dict[str, PluginType] = {}
        for (pt, pname), _plugin in self._loaded.items():
            plugin_type_lookup[pname] = pt

        # Activate in dependency order
        for plugin in sorted_plugins:
            plugin_type = plugin_type_lookup.get(plugin.name)
            if plugin_type is None:
                logger.warning(
                    "activate_all.plugin_type_unknown",
                    name=plugin.name,
                )
                continue

            key_str = f"{plugin_type.name}:{plugin.name}"

            try:
                self.activate_plugin(plugin_type, plugin.name, timeout)
                results[key_str] = None
            except Exception as e:
                results[key_str] = e
                logger.error(
                    "activate_all.plugin_failed",
                    plugin_type=plugin_type.name,
                    name=plugin.name,
                    error=str(e),
                )
                # Continue with other plugins (graceful degradation)

        # Log summary
        failed_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            "activate_all.completed",
            total=len(results),
            succeeded=len(results) - failed_count,
            failed=failed_count,
        )

        return results

    def shutdown_all(self, timeout: float | None = None) -> dict[str, Exception | None]:
        """Shutdown all activated plugins.

        Calls shutdown() on all plugins that have been activated, in reverse
        activation order. Errors are logged but don't prevent other plugins
        from shutting down (graceful degradation).

        Args:
            timeout: Per-plugin timeout in seconds (default: 30s per SC-006).

        Returns:
            Dict mapping "type:name" to exception (or None if success).

        Example:
            >>> registry = get_registry()
            >>> results = registry.shutdown_all()
            >>> failed = {k: v for k, v in results.items() if v is not None}
        """
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        results: dict[str, Exception | None] = {}

        # Shutdown in reverse activation order
        activated_list = list(self._activated)
        activated_list.reverse()

        logger.info(
            "shutdown_all.starting",
            plugin_count=len(activated_list),
            timeout_per_plugin=timeout,
        )

        for plugin_type, name in activated_list:
            key_str = f"{plugin_type.name}:{name}"

            # Get the loaded plugin
            plugin = self._loaded.get((plugin_type, name))
            if plugin is None:
                logger.warning(
                    "shutdown_all.plugin_not_loaded",
                    plugin_type=plugin_type.name,
                    name=name,
                )
                continue

            try:
                self._run_with_timeout(plugin.shutdown, timeout)
                results[key_str] = None
                logger.debug(
                    "shutdown_all.plugin_success",
                    plugin_type=plugin_type.name,
                    name=name,
                )
            except FutureTimeoutError:
                error = TimeoutError(f"shutdown() timed out after {timeout}s")
                results[key_str] = error
                logger.error(
                    "shutdown_all.plugin_timeout",
                    plugin_type=plugin_type.name,
                    name=name,
                    timeout=timeout,
                )
            except Exception as e:
                results[key_str] = e
                logger.error(
                    "shutdown_all.plugin_failed",
                    plugin_type=plugin_type.name,
                    name=name,
                    error=str(e),
                )

        # Clear activated set
        self._activated.clear()

        logger.info(
            "shutdown_all.completed",
            total=len(results),
            failed=sum(1 for v in results.values() if v is not None),
        )

        return results

    def _run_with_timeout(
        self,
        func: Callable[[], None],
        timeout: float,
    ) -> None:
        """Run a function with timeout protection.

        Uses ThreadPoolExecutor to run the function in a separate thread
        with a timeout. This allows lifecycle hooks to be interrupted if
        they take too long.

        Args:
            func: Function to run (no arguments, no return value).
            timeout: Maximum time in seconds to wait.

        Raises:
            FutureTimeoutError: If function exceeds timeout.
            Exception: Any exception raised by the function.
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            future.result(timeout=timeout)

    def health_check_all(
        self,
        timeout: float | None = None,
    ) -> dict[str, HealthStatus]:
        """Check health of all loaded plugins.

        Calls health_check() on each loaded plugin with timeout protection.
        Plugins that fail or timeout are reported as UNHEALTHY.

        Args:
            timeout: Per-plugin timeout in seconds (default: 5s per SC-007).

        Returns:
            Dict mapping "type:name" to HealthStatus.

        Note:
            Only checks LOADED plugins (not discovered-only).

        Example:
            >>> registry = get_registry()
            >>> results = registry.health_check_all()
            >>> unhealthy = {k: v for k, v in results.items()
            ...              if v.state != HealthState.HEALTHY}
        """
        from floe_core.plugin_metadata import HealthState

        if timeout is None:
            timeout = DEFAULT_HEALTH_CHECK_TIMEOUT

        results: dict[str, HealthStatus] = {}

        logger.debug(
            "health_check_all.starting",
            plugin_count=len(self._loaded),
            timeout_per_plugin=timeout,
        )

        for (plugin_type, name), plugin in self._loaded.items():
            key_str = f"{plugin_type.name}:{name}"

            try:
                # Run health_check with timeout protection
                status = self._run_health_check_with_timeout(
                    plugin.health_check,
                    timeout,
                )
                results[key_str] = status

                logger.debug(
                    "health_check_all.plugin_checked",
                    plugin_type=plugin_type.name,
                    name=name,
                    state=status.state.value,
                )

            except FutureTimeoutError:
                # Timeout - return UNHEALTHY
                results[key_str] = HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"health_check() timed out after {timeout}s",
                )
                logger.warning(
                    "health_check_all.plugin_timeout",
                    plugin_type=plugin_type.name,
                    name=name,
                    timeout=timeout,
                )

            except Exception as e:
                # Exception - return UNHEALTHY with error details
                results[key_str] = HealthStatus(
                    state=HealthState.UNHEALTHY,
                    message=f"health_check() raised exception: {e}",
                    details={"exception_type": type(e).__name__},
                )
                logger.error(
                    "health_check_all.plugin_error",
                    plugin_type=plugin_type.name,
                    name=name,
                    error=str(e),
                )

        # Log summary
        healthy_count = sum(1 for s in results.values() if s.state == HealthState.HEALTHY)
        logger.info(
            "health_check_all.completed",
            total=len(results),
            healthy=healthy_count,
            unhealthy=len(results) - healthy_count,
        )

        return results

    def _run_health_check_with_timeout(
        self,
        func: Callable[[], HealthStatus],
        timeout: float,
    ) -> HealthStatus:
        """Run a health_check function with timeout protection.

        Args:
            func: Health check function to run.
            timeout: Maximum time in seconds to wait.

        Returns:
            HealthStatus from the function.

        Raises:
            FutureTimeoutError: If function exceeds timeout.
            Exception: Any exception raised by the function.
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            return future.result(timeout=timeout)

    def resolve_dependencies(
        self,
        plugins: builtins.list[PluginMetadata],
    ) -> builtins.list[PluginMetadata]:
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
            >>> sorted_plugins = registry.resolve_dependencies([A, B, C])
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
        dependents: dict[str, builtins.list[str]] = {name: [] for name in plugin_names}

        for plugin in plugins:
            for dep_name in plugin.dependencies:
                # Only count dependencies that are in our plugin set
                if dep_name in plugin_names:
                    in_degree[plugin.name] += 1
                    dependents[dep_name].append(plugin.name)

        # Kahn's algorithm: start with plugins that have no dependencies
        queue: builtins.list[str] = [name for name, degree in in_degree.items() if degree == 0]
        sorted_names: builtins.list[str] = []

        logger.debug(
            "resolve_dependencies.started",
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
            cycle = self._find_dependency_cycle(plugins, in_degree)
            logger.error(
                "resolve_dependencies.circular_dependency",
                cycle=cycle,
                processed=len(sorted_names),
                total=len(plugins),
            )
            raise CircularDependencyError(cycle)

        logger.debug(
            "resolve_dependencies.completed",
            order=list(sorted_names),
        )

        # Return plugins in sorted order
        return [plugin_map[name] for name in sorted_names]

    def _check_missing_dependencies(
        self,
        plugins: builtins.list[PluginMetadata],
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
            missing = [dep for dep in plugin.dependencies if dep not in available_names]
            if missing:
                logger.error(
                    "resolve_dependencies.missing_dependency",
                    plugin=plugin.name,
                    missing=missing,
                )
                raise MissingDependencyError(plugin.name, missing)

    def _find_dependency_cycle(
        self,
        plugins: builtins.list[PluginMetadata],
        in_degree: dict[str, int],
    ) -> builtins.list[str]:
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
        path: builtins.list[str] = []

        def dfs(node: str) -> builtins.list[str] | None:
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


def get_registry() -> PluginRegistry:
    """Get the global plugin registry singleton.

    Thread-safe initialization. Automatically calls discover_all()
    on first access.

    Returns:
        The singleton PluginRegistry instance.

    Example:
        >>> registry = get_registry()
        >>> plugins = registry.list(PluginType.COMPUTE)
    """
    global _registry

    # Fast path: registry already initialized
    if _registry is not None:
        return _registry

    # Slow path: thread-safe initialization
    with _registry_lock:
        # Double-check after acquiring lock (another thread may have initialized)
        if _registry is not None:
            return _registry

        logger.debug("get_registry.initializing")
        _registry = PluginRegistry()
        _registry.discover_all()
        logger.info("get_registry.initialized")
        return _registry


def _reset_registry() -> None:  # pyright: ignore[reportUnusedFunction]
    """Reset the global registry singleton (for testing only).

    This clears the singleton instance, allowing a fresh registry
    to be created on next get_registry() call.

    Thread-safe reset that acquires the registry lock.

    Warning:
        Only use in tests. Not for production use.

    Example:
        >>> # In test teardown
        >>> _reset_registry()
        >>> # Next get_registry() call creates fresh instance
    """
    global _registry

    with _registry_lock:
        if _registry is not None:
            logger.debug("_reset_registry.clearing")
        _registry = None
