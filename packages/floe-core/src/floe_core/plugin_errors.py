"""Plugin exception hierarchy for floe-core.

This module defines all custom exceptions used in the plugin system.
All exceptions inherit from PluginError, the base exception class.

Exception Hierarchy:
    PluginError (base)
    ├── PluginNotFoundError     # Plugin not in registry
    ├── PluginIncompatibleError # API version mismatch
    ├── PluginConfigurationError # Config validation failed
    ├── DuplicatePluginError    # Same type+name already registered
    └── CircularDependencyError # Dependency cycle detected

Example:
    >>> from floe_core.plugin_errors import PluginNotFoundError
    >>> from floe_core.plugin_types import PluginType
    >>> raise PluginNotFoundError(PluginType.COMPUTE, "missing-plugin")
    Traceback (most recent call last):
        ...
    PluginNotFoundError: Plugin not found: COMPUTE:missing-plugin
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from floe_core.plugin_types import PluginType


class PluginError(Exception):
    """Base exception for all plugin-related errors.

    All plugin exceptions inherit from this class, allowing callers
    to catch all plugin errors with a single except clause.

    Example:
        >>> try:
        ...     registry.get(PluginType.COMPUTE, "nonexistent")
        ... except PluginError as e:
        ...     print(f"Plugin operation failed: {e}")
    """

    pass


class PluginNotFoundError(PluginError):
    """Raised when a requested plugin is not found in the registry.

    Attributes:
        plugin_type: The type of plugin that was requested.
        name: The name of the plugin that was not found.

    Example:
        >>> raise PluginNotFoundError(PluginType.COMPUTE, "duckdb")
        Traceback (most recent call last):
            ...
        PluginNotFoundError: Plugin not found: COMPUTE:duckdb
    """

    def __init__(self, plugin_type: PluginType, name: str) -> None:
        """Initialize PluginNotFoundError.

        Args:
            plugin_type: The type of plugin that was requested.
            name: The name of the plugin that was not found.
        """
        self.plugin_type = plugin_type
        self.name = name
        super().__init__(f"Plugin not found: {plugin_type.name}:{name}")


class PluginIncompatibleError(PluginError):
    """Raised when a plugin's API version is incompatible with the platform.

    This error indicates that the plugin requires a different API version
    than what the platform provides.

    Attributes:
        name: The name of the incompatible plugin.
        required_version: The API version required by the plugin.
        platform_version: The API version provided by the platform.

    Example:
        >>> raise PluginIncompatibleError("old-plugin", "2.0", "1.0")
        Traceback (most recent call last):
            ...
        PluginIncompatibleError: Plugin 'old-plugin' requires API v2.0, but platform provides v1.0
    """

    def __init__(self, name: str, required: str, platform: str) -> None:
        """Initialize PluginIncompatibleError.

        Args:
            name: The name of the incompatible plugin.
            required: The API version required by the plugin.
            platform: The API version provided by the platform.
        """
        self.name = name
        self.required_version = required
        self.platform_version = platform
        super().__init__(
            f"Plugin '{name}' requires API v{required}, "
            f"but platform provides v{platform}"
        )


class PluginConfigurationError(PluginError):
    """Raised when plugin configuration validation fails.

    This error indicates that the provided configuration for a plugin
    does not meet the plugin's schema requirements.

    Attributes:
        name: The name of the plugin with invalid configuration.
        errors: List of validation error details.

    Example:
        >>> errors = [{"field": "host", "message": "required field"}]
        >>> raise PluginConfigurationError("my-plugin", errors)
        Traceback (most recent call last):
            ...
        PluginConfigurationError: Configuration error for plugin 'my-plugin': ...
    """

    def __init__(self, name: str, errors: list[dict[str, Any]]) -> None:
        """Initialize PluginConfigurationError.

        Args:
            name: The name of the plugin with invalid configuration.
            errors: List of validation error dictionaries with details.
        """
        self.name = name
        self.errors = errors
        super().__init__(f"Configuration error for plugin '{name}': {errors}")


class DuplicatePluginError(PluginError):
    """Raised when attempting to register a plugin that already exists.

    The registry enforces unique (type, name) pairs. Attempting to
    register a plugin with an existing type+name combination raises
    this error.

    Attributes:
        plugin_type: The type of the duplicate plugin.
        name: The name of the duplicate plugin.

    Example:
        >>> raise DuplicatePluginError(PluginType.COMPUTE, "duckdb")
        Traceback (most recent call last):
            ...
        DuplicatePluginError: Duplicate plugin: COMPUTE:duckdb
    """

    def __init__(self, plugin_type: PluginType, name: str) -> None:
        """Initialize DuplicatePluginError.

        Args:
            plugin_type: The type of the duplicate plugin.
            name: The name of the duplicate plugin.
        """
        self.plugin_type = plugin_type
        self.name = name
        super().__init__(f"Duplicate plugin: {plugin_type.name}:{name}")


class CircularDependencyError(PluginError):
    """Raised when a circular dependency is detected in the plugin graph.

    Plugins can declare dependencies on other plugins. If these
    dependencies form a cycle, this error is raised.

    Attributes:
        cycle: List of plugin names forming the cycle.

    Example:
        >>> raise CircularDependencyError(["A", "B", "C", "A"])
        Traceback (most recent call last):
            ...
        CircularDependencyError: Circular dependency: A -> B -> C -> A
    """

    def __init__(self, cycle: list[str]) -> None:
        """Initialize CircularDependencyError.

        Args:
            cycle: List of plugin names forming the dependency cycle.
                   The cycle should include the starting plugin at the end
                   to show the complete loop.
        """
        self.cycle = cycle
        super().__init__(f"Circular dependency: {' -> '.join(cycle)}")
