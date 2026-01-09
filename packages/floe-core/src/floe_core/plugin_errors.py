"""Plugin exception hierarchy for floe-core.

This module defines all custom exceptions used in the plugin system.
All exceptions inherit from PluginError, the base exception class.

Exception Hierarchy:
    PluginError (base)
    ├── PluginNotFoundError     # Plugin not in registry
    ├── PluginIncompatibleError # API version mismatch
    ├── PluginConfigurationError # Config validation failed
    ├── PluginStartupError      # Startup hook failed
    ├── DuplicatePluginError    # Same type+name already registered
    ├── CircularDependencyError # Dependency cycle detected
    └── MissingDependencyError  # Required dependency not available

    CatalogError (base for catalog operations)
    ├── CatalogUnavailableError # Catalog service unreachable
    ├── AuthenticationError     # Authentication/authorization failed
    ├── NotSupportedError       # Operation not supported by catalog
    ├── ConflictError           # Resource already exists
    └── NotFoundError           # Resource not found

Example:
    >>> from floe_core.plugin_errors import PluginNotFoundError
    >>> from floe_core.plugin_types import PluginType
    >>> raise PluginNotFoundError(PluginType.COMPUTE, "missing-plugin")
    Traceback (most recent call last):
        ...
    PluginNotFoundError: Plugin not found: COMPUTE:missing-plugin

    >>> from floe_core.plugin_errors import NotFoundError
    >>> raise NotFoundError("namespace", "bronze")
    Traceback (most recent call last):
        ...
    NotFoundError: namespace not found: bronze
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
            f"Plugin '{name}' requires API v{required}, but platform provides v{platform}"
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


class PluginStartupError(PluginError):
    """Raised when a plugin's startup hook fails.

    This error indicates that the plugin's startup() method raised
    an exception or timed out during activation.

    Attributes:
        plugin_type: The type of the plugin that failed.
        name: The name of the plugin that failed.
        cause: The original exception that caused the failure.

    Example:
        >>> raise PluginStartupError(PluginType.COMPUTE, "duckdb", ValueError("bad"))
        Traceback (most recent call last):
            ...
        PluginStartupError: Plugin startup failed: COMPUTE:duckdb - bad
    """

    def __init__(
        self,
        plugin_type: PluginType,
        name: str,
        cause: Exception | None = None,
    ) -> None:
        """Initialize PluginStartupError.

        Args:
            plugin_type: The type of the plugin that failed.
            name: The name of the plugin that failed.
            cause: The original exception, if any.
        """
        self.plugin_type = plugin_type
        self.name = name
        self.cause = cause
        cause_msg = f" - {cause}" if cause else ""
        super().__init__(f"Plugin startup failed: {plugin_type.name}:{name}{cause_msg}")


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


class MissingDependencyError(PluginError):
    """Raised when a plugin declares a dependency that is not available.

    This error indicates that a plugin requires another plugin that
    is not installed or not in the current plugin set.

    Attributes:
        plugin_name: The name of the plugin with missing dependencies.
        missing_dependencies: List of dependency names that are missing.

    Example:
        >>> raise MissingDependencyError("my-plugin", ["duckdb", "polaris"])
        Traceback (most recent call last):
            ...
        MissingDependencyError: Plugin 'my-plugin' has missing dependencies: duckdb, polaris
    """

    def __init__(self, plugin_name: str, missing_dependencies: list[str]) -> None:
        """Initialize MissingDependencyError.

        Args:
            plugin_name: The name of the plugin with missing dependencies.
            missing_dependencies: List of dependency names that are not available.
        """
        self.plugin_name = plugin_name
        self.missing_dependencies = missing_dependencies
        deps_str = ", ".join(missing_dependencies)
        super().__init__(f"Plugin '{plugin_name}' has missing dependencies: {deps_str}")


# =============================================================================
# Catalog Error Hierarchy
# =============================================================================
# These exceptions are used by CatalogPlugin implementations (Polaris, Glue, etc.)
# to report catalog-specific errors. They inherit from a separate base class
# to distinguish catalog operations from plugin registry operations.


class CatalogError(Exception):
    """Base exception for all catalog operations.

    All catalog-related exceptions inherit from this class, allowing callers
    to catch all catalog errors with a single except clause.

    This is separate from PluginError because catalog errors are operational
    (e.g., namespace not found, authentication failed) while PluginError
    covers plugin lifecycle issues (e.g., plugin not registered, incompatible).

    Example:
        >>> try:
        ...     catalog.create_namespace("bronze")
        ... except CatalogError as e:
        ...     print(f"Catalog operation failed: {e}")
    """

    pass


class CatalogUnavailableError(CatalogError):
    """Raised when the catalog service is unreachable.

    This error indicates network connectivity issues, service downtime,
    or timeout waiting for catalog response.

    Attributes:
        catalog_uri: The URI of the unavailable catalog.
        cause: The underlying exception (e.g., connection timeout).

    Example:
        >>> raise CatalogUnavailableError(
        ...     "http://polaris:8181/api/catalog",
        ...     cause=ConnectionError("Connection refused")
        ... )
        Traceback (most recent call last):
            ...
        CatalogUnavailableError: Catalog unavailable: http://polaris:8181/api/catalog
    """

    def __init__(self, catalog_uri: str, cause: Exception | None = None) -> None:
        """Initialize CatalogUnavailableError.

        Args:
            catalog_uri: The URI of the unavailable catalog.
            cause: The underlying exception that caused the unavailability.
        """
        self.catalog_uri = catalog_uri
        self.cause = cause
        cause_msg = f" - {cause}" if cause else ""
        super().__init__(f"Catalog unavailable: {catalog_uri}{cause_msg}")


class AuthenticationError(CatalogError):
    """Raised when authentication or authorization fails.

    This error indicates invalid credentials, expired tokens, or
    insufficient permissions for the requested operation.

    Attributes:
        message: Description of the authentication failure.
        operation: The operation that was attempted (optional).

    Example:
        >>> raise AuthenticationError("Invalid OAuth2 token")
        Traceback (most recent call last):
            ...
        AuthenticationError: Authentication failed: Invalid OAuth2 token

        >>> raise AuthenticationError(
        ...     "Insufficient permissions",
        ...     operation="create_namespace"
        ... )
        Traceback (most recent call last):
            ...
        AuthenticationError: Authentication failed for 'create_namespace': Insufficient permissions
    """

    def __init__(self, message: str, operation: str | None = None) -> None:
        """Initialize AuthenticationError.

        Args:
            message: Description of the authentication failure.
            operation: The operation that was attempted (optional).
        """
        self.message = message
        self.operation = operation
        if operation:
            super().__init__(f"Authentication failed for '{operation}': {message}")
        else:
            super().__init__(f"Authentication failed: {message}")


class NotSupportedError(CatalogError):
    """Raised when an operation is not supported by the catalog implementation.

    Different catalog backends support different features. This error
    indicates that the requested operation is not available.

    Attributes:
        operation: The unsupported operation name.
        catalog_name: The name of the catalog that doesn't support it.
        reason: Optional explanation of why it's not supported.

    Example:
        >>> raise NotSupportedError(
        ...     "vend_credentials",
        ...     "hive",
        ...     reason="Hive Metastore does not support credential vending"
        ... )
        Traceback (most recent call last):
            ...
        NotSupportedError: Operation 'vend_credentials' not supported by catalog 'hive': ...
    """

    def __init__(
        self,
        operation: str,
        catalog_name: str,
        reason: str | None = None,
    ) -> None:
        """Initialize NotSupportedError.

        Args:
            operation: The unsupported operation name.
            catalog_name: The name of the catalog that doesn't support it.
            reason: Optional explanation of why it's not supported.
        """
        self.operation = operation
        self.catalog_name = catalog_name
        self.reason = reason
        msg = f"Operation '{operation}' not supported by catalog '{catalog_name}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class ConflictError(CatalogError):
    """Raised when a resource already exists.

    This error indicates that a create operation failed because
    the namespace or table already exists in the catalog.

    Attributes:
        resource_type: The type of resource (e.g., "namespace", "table").
        identifier: The identifier of the conflicting resource.

    Example:
        >>> raise ConflictError("namespace", "bronze")
        Traceback (most recent call last):
            ...
        ConflictError: namespace already exists: bronze

        >>> raise ConflictError("table", "bronze.raw_customers")
        Traceback (most recent call last):
            ...
        ConflictError: table already exists: bronze.raw_customers
    """

    def __init__(self, resource_type: str, identifier: str) -> None:
        """Initialize ConflictError.

        Args:
            resource_type: The type of resource (e.g., "namespace", "table").
            identifier: The identifier of the conflicting resource.
        """
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} already exists: {identifier}")


class NotFoundError(CatalogError):
    """Raised when a resource is not found.

    This error indicates that an operation failed because the
    namespace or table does not exist in the catalog.

    Attributes:
        resource_type: The type of resource (e.g., "namespace", "table").
        identifier: The identifier of the missing resource.

    Example:
        >>> raise NotFoundError("namespace", "bronze")
        Traceback (most recent call last):
            ...
        NotFoundError: namespace not found: bronze

        >>> raise NotFoundError("table", "bronze.raw_customers")
        Traceback (most recent call last):
            ...
        NotFoundError: table not found: bronze.raw_customers
    """

    def __init__(self, resource_type: str, identifier: str) -> None:
        """Initialize NotFoundError.

        Args:
            resource_type: The type of resource (e.g., "namespace", "table").
            identifier: The identifier of the missing resource.
        """
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} not found: {identifier}")
