"""Error types for the Cube semantic layer plugin.

This module defines the exception hierarchy for the Cube semantic layer plugin.
All errors inherit from CubeSemanticError, which is the base exception for
any operation within the Cube plugin.

Example:
    >>> from floe_semantic_cube.errors import SchemaGenerationError
    >>> raise SchemaGenerationError("Failed to parse dbt manifest")

Requirements Covered:
    - FR-008: Plugin error handling with meaningful error messages
"""

from __future__ import annotations


class CubeSemanticError(Exception):
    """Base exception for all Cube semantic layer plugin errors.

    All plugin-specific exceptions inherit from this class, enabling
    callers to catch any Cube-related error with a single except clause.

    Args:
        message: Human-readable error description.

    Example:
        >>> try:
        ...     raise CubeSemanticError("Something went wrong")
        ... except CubeSemanticError as e:
        ...     print(f"Cube error: {e}")
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class SchemaGenerationError(CubeSemanticError):
    """Error during Cube schema generation from dbt manifest.

    Raised when the schema generator encounters issues parsing the dbt
    manifest, inferring column types, or writing YAML output files.

    Args:
        message: Human-readable error description.
        model_name: Name of the dbt model that caused the error, if known.

    Example:
        >>> raise SchemaGenerationError(
        ...     "Invalid column type for measure",
        ...     model_name="orders",
        ... )
    """

    def __init__(self, message: str, *, model_name: str | None = None) -> None:
        self.model_name = model_name
        detail = f" (model: {model_name})" if model_name else ""
        super().__init__(f"{message}{detail}")


class CubeHealthCheckError(CubeSemanticError):
    """Error during Cube health check.

    Raised when the health check to the Cube API server fails
    due to connectivity issues, timeouts, or unexpected responses.

    Args:
        message: Human-readable error description.
        server_url: URL of the Cube server that was checked.

    Example:
        >>> raise CubeHealthCheckError(
        ...     "Connection refused",
        ...     server_url="http://cube:4000",
        ... )
    """

    def __init__(self, message: str, *, server_url: str | None = None) -> None:
        self.server_url = server_url
        detail = f" (server: {server_url})" if server_url else ""
        super().__init__(f"{message}{detail}")


class CubeDatasourceError(CubeSemanticError):
    """Error during Cube datasource configuration.

    Raised when the plugin cannot generate valid datasource configuration
    from the active compute plugin.

    Args:
        message: Human-readable error description.
        compute_type: Type of compute plugin that was being configured.

    Example:
        >>> raise CubeDatasourceError(
        ...     "Unsupported compute type",
        ...     compute_type="bigquery",
        ... )
    """

    def __init__(self, message: str, *, compute_type: str | None = None) -> None:
        self.compute_type = compute_type
        detail = f" (compute: {compute_type})" if compute_type else ""
        super().__init__(f"{message}{detail}")
