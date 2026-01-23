"""Plugin lifecycle management (activation, shutdown, health checks).

This module handles plugin lifecycle hooks with timeout protection:
- Activation: calling startup() hooks
- Shutdown: calling shutdown() hooks in reverse order
- Health checks: calling health_check() with timeout protection

Extracted from plugin_registry.py as part of Epic 12B US4 (God Module Decomposition)
to reduce the file from 1230 lines to focused, single-responsibility modules.

Example:
    >>> from floe_core.plugins.lifecycle import PluginLifecycle
    >>> from floe_core.plugins.loader import PluginLoader
    >>> from floe_core.plugin_types import PluginType
    >>>
    >>> lifecycle = PluginLifecycle(loader)
    >>> lifecycle.activate_plugin(PluginType.COMPUTE, "duckdb")
    >>> results = lifecycle.health_check_all()
    >>> lifecycle.shutdown_all()

Requirements Covered:
    - FR-003: Split plugin_registry.py into focused modules each ≤400 lines
    - 12B-ARCH-003: SRP decomposition of plugin registry
    - SC-006: 30-second timeout for lifecycle hooks
    - SC-007: 5-second timeout for health checks
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TYPE_CHECKING

import structlog

from floe_core.plugin_errors import PluginStartupError
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType

if TYPE_CHECKING:
    from floe_core.plugins.loader import PluginLoader

logger = structlog.get_logger(__name__)

# Default timeout for lifecycle hooks (SC-006: 30 seconds)
DEFAULT_LIFECYCLE_TIMEOUT: float = 30.0

# Default timeout for health checks (SC-007: 5 seconds)
DEFAULT_HEALTH_CHECK_TIMEOUT: float = 5.0


class PluginLifecycle:
    """Manages plugin lifecycle: activation, shutdown, and health checks.

    This class is responsible solely for:
    - Calling startup() hooks on plugins (activation)
    - Calling shutdown() hooks in reverse order
    - Running health_check() with timeout protection
    - Tracking which plugins are activated

    All lifecycle hooks are run with timeout protection to prevent
    hung plugins from blocking the entire system.

    Attributes:
        _loader: PluginLoader instance for accessing loaded plugins.
        _activated: Set of (PluginType, name) tuples for activated plugins.

    Example:
        >>> lifecycle = PluginLifecycle(loader)
        >>> lifecycle.activate_plugin(PluginType.COMPUTE, "duckdb")
        >>> health = lifecycle.health_check_all()
        >>> lifecycle.shutdown_all()
    """

    def __init__(self, loader: PluginLoader) -> None:
        """Initialize lifecycle manager with loader instance.

        Args:
            loader: PluginLoader instance to use for accessing plugins.
        """
        self._loader = loader

        # Plugins that have been activated (startup() called)
        # Key: (PluginType, plugin_name)
        self._activated: set[tuple[PluginType, str]] = set()

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
            >>> lifecycle.activate_plugin(PluginType.COMPUTE, "duckdb")
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
        plugin = self._loader.get(plugin_type, name)

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
        plugins: list[PluginMetadata] | None = None,
        plugin_types: list[PluginType] | None = None,
        timeout: float | None = None,
        plugin_type_lookup: dict[str, PluginType] | None = None,
    ) -> dict[str, Exception | None]:
        """Activate multiple plugins.

        Activates plugins in the provided order. For dependency-aware
        activation, use resolve_dependencies() first to get the correct order.

        Args:
            plugins: List of plugins to activate. If not provided,
                activates all loaded plugins or those matching plugin_types.
            plugin_types: If plugins not provided, activate all plugins of
                these types. If None, activates all loaded plugins.
            timeout: Per-plugin timeout in seconds (default: 30s per SC-006).
            plugin_type_lookup: Dict mapping plugin name to PluginType.
                Required when activating from a list of PluginMetadata.

        Returns:
            Dict mapping "type:name" to exception (or None if success).

        Example:
            >>> results = lifecycle.activate_all()
            >>> failed = {k: v for k, v in results.items() if v is not None}
        """
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        results: dict[str, Exception | None] = {}

        # Determine which plugins to activate
        if plugins is not None:
            plugins_to_activate = plugins
        elif plugin_types is not None:
            # Get all loaded plugins of specified types
            plugins_to_activate = []
            loaded = self._loader.get_loaded()
            for (pt, _pname), plugin in loaded.items():
                if pt in plugin_types:
                    plugins_to_activate.append(plugin)
        else:
            # Activate all loaded plugins
            plugins_to_activate = list(self._loader.get_loaded().values())

        if not plugins_to_activate:
            logger.debug("activate_all.no_plugins")
            return results

        # Build plugin_type_lookup if not provided
        if plugin_type_lookup is None:
            plugin_type_lookup = {}
            for (pt, pname), _ in self._loader.get_loaded().items():
                plugin_type_lookup[pname] = pt

        logger.info(
            "activate_all.starting",
            plugin_count=len(plugins_to_activate),
            timeout_per_plugin=timeout,
        )

        # Activate each plugin
        for plugin in plugins_to_activate:
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
            >>> results = lifecycle.shutdown_all()
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

        loaded = self._loader.get_loaded()

        for plugin_type, name in activated_list:
            key_str = f"{plugin_type.name}:{name}"

            # Get the loaded plugin
            plugin = loaded.get((plugin_type, name))
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
            >>> results = lifecycle.health_check_all()
            >>> unhealthy = {k: v for k, v in results.items()
            ...              if v.state != HealthState.HEALTHY}
        """
        if timeout is None:
            timeout = DEFAULT_HEALTH_CHECK_TIMEOUT

        results: dict[str, HealthStatus] = {}
        loaded = self._loader.get_loaded()

        logger.debug(
            "health_check_all.starting",
            plugin_count=len(loaded),
            timeout_per_plugin=timeout,
        )

        for (plugin_type, name), plugin in loaded.items():
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

    def is_activated(self, plugin_type: PluginType, name: str) -> bool:
        """Check if a plugin has been activated.

        Args:
            plugin_type: The plugin category.
            name: The plugin name.

        Returns:
            True if plugin is activated (startup() called successfully).
        """
        return (plugin_type, name) in self._activated

    def get_activated(self) -> set[tuple[PluginType, str]]:
        """Get all activated plugin keys.

        Returns:
            Set of (PluginType, name) tuples for activated plugins.
        """
        return self._activated.copy()

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

    def clear(self) -> None:
        """Clear activated set (for testing).

        This clears the activation tracking without calling shutdown hooks.
        """
        self._activated.clear()
        logger.debug("lifecycle.cleared")


__all__ = [
    "PluginLifecycle",
    "DEFAULT_LIFECYCLE_TIMEOUT",
    "DEFAULT_HEALTH_CHECK_TIMEOUT",
]
