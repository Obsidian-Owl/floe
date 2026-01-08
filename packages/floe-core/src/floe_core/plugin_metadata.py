"""Plugin metadata definitions for floe-core.

This module defines the base abstractions for all floe plugins:
- HealthState: Enum for plugin health states
- HealthStatus: Dataclass for health check results
- PluginMetadata: Abstract base class all plugins must inherit from

Example:
    >>> from floe_core.plugin_metadata import PluginMetadata, HealthState, HealthStatus
    >>> class MyPlugin(PluginMetadata):
    ...     @property
    ...     def name(self) -> str:
    ...         return "my-plugin"
    ...     @property
    ...     def version(self) -> str:
    ...         return "1.0.0"
    ...     @property
    ...     def floe_api_version(self) -> str:
    ...         return "1.0"
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel


class HealthState(Enum):
    """Health states for plugin health checks.

    Plugins report their health using one of these states:
    - HEALTHY: Plugin is fully operational
    - DEGRADED: Plugin is partially operational with reduced functionality
    - UNHEALTHY: Plugin is not operational

    Example:
        >>> health = HealthStatus(state=HealthState.HEALTHY)
        >>> health.state == HealthState.HEALTHY
        True
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthStatus:
    """Health check result from a plugin.

    Attributes:
        state: The health state (HEALTHY, DEGRADED, or UNHEALTHY).
        message: Optional human-readable message about the health status.
        details: Optional dictionary with additional diagnostic information.

    Example:
        >>> status = HealthStatus(
        ...     state=HealthState.DEGRADED,
        ...     message="Connection pool low",
        ...     details={"pool_size": 2, "max_size": 10}
        ... )
        >>> status.state
        <HealthState.DEGRADED: 'degraded'>
    """

    state: HealthState
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class PluginMetadata(ABC):
    """Abstract base class for all floe plugins.

    All plugins must inherit from this class and implement the required
    abstract properties: name, version, and floe_api_version.

    Abstract Properties:
        name: Plugin identifier (e.g., "duckdb", "dagster")
        version: Plugin version in semver format (X.Y.Z)
        floe_api_version: Required floe API version (X.Y format)

    Optional Properties:
        description: Human-readable description (default: empty)
        dependencies: List of plugin names this plugin depends on

    Lifecycle Methods:
        startup(): Called when plugin is activated
        shutdown(): Called when platform shuts down
        health_check(): Returns current health status

    Configuration:
        get_config_schema(): Returns Pydantic model for config validation

    Example:
        >>> class DuckDBPlugin(PluginMetadata):
        ...     @property
        ...     def name(self) -> str:
        ...         return "duckdb"
        ...
        ...     @property
        ...     def version(self) -> str:
        ...         return "1.0.0"
        ...
        ...     @property
        ...     def floe_api_version(self) -> str:
        ...         return "1.0"
        ...
        ...     @property
        ...     def description(self) -> str:
        ...         return "DuckDB compute plugin for floe"
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (e.g., 'duckdb', 'dagster').

        This is the unique identifier for the plugin within its type.
        Must be lowercase, alphanumeric with hyphens allowed.

        Returns:
            The plugin name as a string.
        """
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version in semver format (X.Y.Z).

        Follows semantic versioning: MAJOR.MINOR.PATCH
        - MAJOR: Breaking changes
        - MINOR: New features, backward compatible
        - PATCH: Bug fixes, backward compatible

        Returns:
            The plugin version as a string (e.g., "1.0.0").
        """
        ...

    @property
    @abstractmethod
    def floe_api_version(self) -> str:
        """Required floe API version (X.Y format).

        This is the minimum floe API version this plugin requires.
        The platform will check compatibility using is_compatible().

        Returns:
            The required API version as a string (e.g., "1.0").
        """
        ...

    @property
    def description(self) -> str:
        """Human-readable description of the plugin.

        Override this property to provide a description of what
        the plugin does and any important notes for users.

        Returns:
            Plugin description (default: empty string).
        """
        return ""

    @property
    def dependencies(self) -> list[str]:
        """List of plugin names this plugin depends on.

        Dependencies are specified by name only. The registry will
        ensure dependencies are loaded before this plugin.

        Returns:
            List of plugin names (default: empty list).

        Example:
            >>> class MyPlugin(PluginMetadata):
            ...     @property
            ...     def dependencies(self) -> list[str]:
            ...         return ["duckdb", "polaris"]
        """
        return []

    def get_config_schema(self) -> type[BaseModel] | None:
        """Return the Pydantic model for configuration validation.

        Override this method to provide a configuration schema.
        The schema must be a Pydantic v2 BaseModel subclass.

        Returns:
            A Pydantic BaseModel subclass, or None if no configuration.

        Example:
            >>> from pydantic import BaseModel
            >>> class MyConfig(BaseModel):
            ...     host: str
            ...     port: int = 5432
            >>>
            >>> class MyPlugin(PluginMetadata):
            ...     def get_config_schema(self) -> type[BaseModel]:
            ...         return MyConfig
        """
        return None

    def health_check(self) -> HealthStatus:
        """Check the health of this plugin.

        Override this method to implement custom health checks.
        Health checks should complete within 5 seconds (SC-007).

        Returns:
            HealthStatus indicating current health state.

        Example:
            >>> def health_check(self) -> HealthStatus:
            ...     if self._connection.is_alive():
            ...         return HealthStatus(state=HealthState.HEALTHY)
            ...     return HealthStatus(
            ...         state=HealthState.UNHEALTHY,
            ...         message="Connection lost"
            ...     )
        """
        return HealthStatus(state=HealthState.HEALTHY)

    def startup(self) -> None:  # noqa: B027
        """Lifecycle hook called when the plugin is activated.

        Override this method to perform initialization tasks such as:
        - Establishing connections
        - Loading resources
        - Validating environment

        Should complete within 30 seconds (SC-006).
        Exceptions raised here will prevent plugin activation.

        Note: Empty default implementation is intentional - subclasses override.
        """

    def shutdown(self) -> None:  # noqa: B027
        """Lifecycle hook called when the platform shuts down.

        Override this method to perform cleanup tasks such as:
        - Closing connections
        - Flushing buffers
        - Releasing resources

        Should complete within 30 seconds (SC-006).
        Exceptions are logged but don't prevent shutdown.

        Note: Empty default implementation is intentional - subclasses override.
        """
