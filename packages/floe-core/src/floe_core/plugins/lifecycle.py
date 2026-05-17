"""Plugin lifecycle management with timeout protection."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import TYPE_CHECKING

import structlog

from floe_core.plugin_errors import PluginStartupError
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugin_types import PluginType
from floe_core.telemetry.lifecycle import observe_plugin_lifecycle

if TYPE_CHECKING:
    from floe_core.plugins.loader import PluginLoader

logger = structlog.get_logger(__name__)

DEFAULT_LIFECYCLE_TIMEOUT: float = 30.0
DEFAULT_HEALTH_CHECK_TIMEOUT: float = 5.0
_PHASE_STARTUP = "startup"
_PHASE_SHUTDOWN = "shutdown"
_PHASE_HEALTH_CHECK = "health_check"
_STATUS_SUCCESS = "success"
_STATUS_FAILURE = "failure"


class PluginLifecycle:
    """Manages plugin activation, shutdown, and health checks."""

    def __init__(self, loader: PluginLoader) -> None:
        """Initialize lifecycle manager."""
        self._loader = loader

        self._activated: set[tuple[PluginType, str]] = set()

    def activate_plugin(
        self,
        plugin_type: PluginType,
        name: str,
        timeout: float | None = None,
    ) -> None:
        """Call startup() for one plugin and mark it activated on success."""
        key = (plugin_type, name)

        if key in self._activated:
            logger.debug(
                "activate_plugin.already_activated",
                plugin_type=plugin_type.name,
                name=name,
            )
            return

        plugin = self._loader.get(plugin_type, name)

        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        logger.debug(
            "activate_plugin.starting",
            plugin_type=plugin_type.name,
            name=name,
            timeout=timeout,
        )

        with observe_plugin_lifecycle(
            plugin_type=plugin_type.name,
            plugin_name=plugin.name,
            plugin_version=plugin.version,
            floe_api_version=plugin.floe_api_version,
            phase=_PHASE_STARTUP,
            extra={"timeout": timeout},
        ) as observation:
            try:
                self._run_with_timeout(plugin.startup, timeout)
            except FutureTimeoutError:
                observation.finish(
                    status=_STATUS_FAILURE,
                    error_type=TimeoutError.__name__,
                    extra={"timeout": timeout},
                )
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
                observation.finish(
                    status=_STATUS_FAILURE,
                    error_type=type(e).__name__,
                )
                logger.error(
                    "activate_plugin.failed",
                    plugin_type=plugin_type.name,
                    name=name,
                    error=str(e),
                )
                raise PluginStartupError(plugin_type, name, e) from e

            observation.finish(status=_STATUS_SUCCESS)

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
        """Activate multiple plugins in order, preserving graceful degradation."""
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        results: dict[str, Exception | None] = {}

        if plugins is not None:
            plugins_to_activate = plugins
        elif plugin_types is not None:
            plugins_to_activate = []
            loaded = self._loader.get_loaded()
            for (pt, _pname), plugin in loaded.items():
                if pt in plugin_types:
                    plugins_to_activate.append(plugin)
        else:
            plugins_to_activate = list(self._loader.get_loaded().values())

        if not plugins_to_activate:
            logger.debug("activate_all.no_plugins")
            return results

        if plugin_type_lookup is None:
            plugin_type_lookup = {}
            for (pt, pname), _ in self._loader.get_loaded().items():
                plugin_type_lookup[pname] = pt

        logger.info(
            "activate_all.starting",
            plugin_count=len(plugins_to_activate),
            timeout_per_plugin=timeout,
        )

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
        failed_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            "activate_all.completed",
            total=len(results),
            succeeded=len(results) - failed_count,
            failed=failed_count,
        )

        return results

    def shutdown_all(self, timeout: float | None = None) -> dict[str, Exception | None]:
        """Call shutdown() for activated plugins in reverse activation order."""
        if timeout is None:
            timeout = DEFAULT_LIFECYCLE_TIMEOUT

        results: dict[str, Exception | None] = {}

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

            plugin = loaded.get((plugin_type, name))
            if plugin is None:
                logger.warning(
                    "shutdown_all.plugin_not_loaded",
                    plugin_type=plugin_type.name,
                    name=name,
                )
                continue

            with observe_plugin_lifecycle(
                plugin_type=plugin_type.name,
                plugin_name=plugin.name,
                plugin_version=plugin.version,
                floe_api_version=plugin.floe_api_version,
                phase=_PHASE_SHUTDOWN,
                extra={"timeout": timeout},
            ) as observation:
                try:
                    self._run_with_timeout(plugin.shutdown, timeout)
                    observation.finish(status=_STATUS_SUCCESS)
                    results[key_str] = None
                    logger.debug(
                        "shutdown_all.plugin_success",
                        plugin_type=plugin_type.name,
                        name=name,
                    )
                except FutureTimeoutError:
                    error = TimeoutError(f"shutdown() timed out after {timeout}s")
                    observation.finish(
                        status=_STATUS_FAILURE,
                        error_type=TimeoutError.__name__,
                        extra={"timeout": timeout},
                    )
                    results[key_str] = error
                    logger.error(
                        "shutdown_all.plugin_timeout",
                        plugin_type=plugin_type.name,
                        name=name,
                        timeout=timeout,
                    )
                except Exception as e:
                    observation.finish(
                        status=_STATUS_FAILURE,
                        error_type=type(e).__name__,
                    )
                    results[key_str] = e
                    logger.error(
                        "shutdown_all.plugin_failed",
                        plugin_type=plugin_type.name,
                        name=name,
                        error=str(e),
                    )

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
        """Run health_check() for all loaded plugins."""
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

            with observe_plugin_lifecycle(
                plugin_type=plugin_type.name,
                plugin_name=plugin.name,
                plugin_version=plugin.version,
                floe_api_version=plugin.floe_api_version,
                phase=_PHASE_HEALTH_CHECK,
                extra={"timeout": timeout},
            ) as observation:
                try:
                    status = self._run_health_check_with_timeout(
                        plugin.health_check,
                        timeout,
                    )
                    observation.finish(status=status.state.value)
                except FutureTimeoutError:
                    status = HealthStatus(
                        state=HealthState.UNHEALTHY,
                        message=f"health_check() timed out after {timeout}s",
                    )
                    observation.finish(
                        status=status.state.value,
                        error_type=TimeoutError.__name__,
                        extra={"timeout": timeout},
                    )
                    logger.warning(
                        "health_check_all.plugin_timeout",
                        plugin_type=plugin_type.name,
                        name=name,
                        timeout=timeout,
                    )
                except Exception as e:
                    status = HealthStatus(
                        state=HealthState.UNHEALTHY,
                        message=f"health_check() raised exception: {e}",
                        details={"exception_type": type(e).__name__},
                    )
                    observation.finish(
                        status=status.state.value,
                        error_type=type(e).__name__,
                    )
                    logger.error(
                        "health_check_all.plugin_error",
                        plugin_type=plugin_type.name,
                        name=name,
                        error=str(e),
                    )

                results[key_str] = status

                logger.debug(
                    "health_check_all.plugin_checked",
                    plugin_type=plugin_type.name,
                    name=name,
                    state=status.state.value,
                )

        healthy_count = sum(1 for s in results.values() if s.state == HealthState.HEALTHY)
        logger.info(
            "health_check_all.completed",
            total=len(results),
            healthy=healthy_count,
            unhealthy=len(results) - healthy_count,
        )

        return results

    def is_activated(self, plugin_type: PluginType, name: str) -> bool:
        """Return whether a plugin has been activated."""
        return (plugin_type, name) in self._activated

    def get_activated(self) -> set[tuple[PluginType, str]]:
        """Return all activated plugin keys."""
        return self._activated.copy()

    def _run_with_timeout(
        self,
        func: Callable[[], None],
        timeout: float,
    ) -> None:
        """Run a no-arg lifecycle hook with timeout protection."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            future.result(timeout=timeout)

    def _run_health_check_with_timeout(
        self,
        func: Callable[[], HealthStatus],
        timeout: float,
    ) -> HealthStatus:
        """Run a no-arg health_check function with timeout protection."""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            return future.result(timeout=timeout)

    def clear(self) -> None:
        """Clear activation tracking without calling shutdown hooks."""
        self._activated.clear()
        logger.debug("lifecycle.cleared")


__all__ = [
    "PluginLifecycle",
    "DEFAULT_LIFECYCLE_TIMEOUT",
    "DEFAULT_HEALTH_CHECK_TIMEOUT",
]
