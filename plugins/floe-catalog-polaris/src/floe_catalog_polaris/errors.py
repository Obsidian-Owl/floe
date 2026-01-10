"""Error mapping from PyIceberg exceptions to floe errors.

This module provides exception mapping utilities for converting PyIceberg
catalog exceptions into floe's standardized error types.

Example:
    >>> from floe_catalog_polaris.errors import map_pyiceberg_error
    >>> from pyiceberg.exceptions import NoSuchNamespaceError
    >>> try:
    ...     raise NoSuchNamespaceError("bronze")
    ... except Exception as e:
    ...     raise map_pyiceberg_error(e) from e

Requirements Covered:
    - FR-033: System MUST support error mapping for catalog operations
"""

from __future__ import annotations

import structlog
from floe_core import (
    AuthenticationError,
    CatalogError,
    CatalogUnavailableError,
    ConflictError,
    NotFoundError,
    NotSupportedError,
)
from pyiceberg.exceptions import (
    AuthorizationExpiredError,
    BadRequestError,
    ForbiddenError,
    NamespaceAlreadyExistsError,
    NamespaceNotEmptyError,
    NoSuchIdentifierError,
    NoSuchNamespaceError,
    NoSuchTableError,
    NoSuchViewError,
    OAuthError,
    RESTError,
    ServerError,
    ServiceUnavailableError,
    TableAlreadyExistsError,
    UnauthorizedError,
    ValidationError,
)

logger = structlog.get_logger(__name__)


def map_pyiceberg_error(
    error: Exception,
    catalog_uri: str | None = None,
    operation: str | None = None,
) -> CatalogError:
    """Map a PyIceberg exception to a floe CatalogError.

    Converts PyIceberg-specific exceptions into standardized floe catalog
    errors with appropriate context for logging and error handling.

    Args:
        error: The PyIceberg exception to map.
        catalog_uri: Optional catalog URI for context in error messages.
        operation: Optional operation name for context in error messages.

    Returns:
        A CatalogError subclass appropriate for the error type.

    Examples:
        >>> from pyiceberg.exceptions import NoSuchNamespaceError
        >>> error = NoSuchNamespaceError("bronze")
        >>> mapped = map_pyiceberg_error(error, operation="list_tables")
        >>> isinstance(mapped, NotFoundError)
        True

        >>> from pyiceberg.exceptions import ServiceUnavailableError
        >>> error = ServiceUnavailableError("Service down")
        >>> mapped = map_pyiceberg_error(error, catalog_uri="http://polaris:8181")
        >>> isinstance(mapped, CatalogUnavailableError)
        True
    """
    # Service unavailability - catalog is unreachable
    if isinstance(error, ServiceUnavailableError):
        logger.warning(
            "catalog_service_unavailable",
            catalog_uri=catalog_uri,
            error=str(error),
        )
        return CatalogUnavailableError(
            catalog_uri=catalog_uri or "unknown",
            cause=error,
        )

    # Authentication failures - unauthorized access
    if isinstance(error, UnauthorizedError):
        logger.warning(
            "catalog_unauthorized",
            operation=operation,
            error=str(error),
        )
        return AuthenticationError(
            message=str(error),
            operation=operation,
        )

    # Authorization expiration - token needs refresh
    if isinstance(error, AuthorizationExpiredError):
        logger.warning(
            "catalog_authorization_expired",
            operation=operation,
            error=str(error),
        )
        return AuthenticationError(
            message="Authorization expired - token refresh required",
            operation=operation,
        )

    # OAuth errors - authentication configuration issues
    if isinstance(error, OAuthError):
        logger.error(
            "catalog_oauth_error",
            operation=operation,
            error=str(error),
        )
        return AuthenticationError(
            message=f"OAuth2 authentication failed: {error}",
            operation=operation,
        )

    # Permission denied - insufficient privileges
    if isinstance(error, ForbiddenError):
        logger.warning(
            "catalog_forbidden",
            operation=operation,
            error=str(error),
        )
        return AuthenticationError(
            message=f"Permission denied: {error}",
            operation=operation,
        )

    # Namespace already exists - conflict error
    if isinstance(error, NamespaceAlreadyExistsError):
        # Extract namespace name from error message
        namespace = _extract_identifier(str(error), "Namespace")
        logger.info(
            "catalog_namespace_already_exists",
            namespace=namespace,
        )
        return ConflictError(
            resource_type="namespace",
            identifier=namespace,
        )

    # Table already exists - conflict error
    if isinstance(error, TableAlreadyExistsError):
        table = _extract_identifier(str(error), "Table")
        logger.info(
            "catalog_table_already_exists",
            table=table,
        )
        return ConflictError(
            resource_type="table",
            identifier=table,
        )

    # Namespace not found
    if isinstance(error, NoSuchNamespaceError):
        namespace = _extract_identifier(str(error), "Namespace")
        logger.debug(
            "catalog_namespace_not_found",
            namespace=namespace,
        )
        return NotFoundError(
            resource_type="namespace",
            identifier=namespace,
        )

    # Table not found
    if isinstance(error, NoSuchTableError):
        table = _extract_identifier(str(error), "Table")
        logger.debug(
            "catalog_table_not_found",
            table=table,
        )
        return NotFoundError(
            resource_type="table",
            identifier=table,
        )

    # View not found
    if isinstance(error, NoSuchViewError):
        view = _extract_identifier(str(error), "View")
        logger.debug(
            "catalog_view_not_found",
            view=view,
        )
        return NotFoundError(
            resource_type="view",
            identifier=view,
        )

    # Identifier not found (generic)
    if isinstance(error, NoSuchIdentifierError):
        identifier = str(error)
        logger.debug(
            "catalog_identifier_not_found",
            identifier=identifier,
        )
        return NotFoundError(
            resource_type="identifier",
            identifier=identifier,
        )

    # Namespace not empty (cannot delete)
    if isinstance(error, NamespaceNotEmptyError):
        namespace = _extract_identifier(str(error), "Namespace")
        logger.warning(
            "catalog_namespace_not_empty",
            namespace=namespace,
        )
        return NotSupportedError(
            operation="delete_namespace",
            catalog_name=catalog_uri or "polaris",
            reason=f"Namespace '{namespace}' is not empty - delete tables first",
        )

    # Validation error - bad request data
    if isinstance(error, ValidationError):
        logger.warning(
            "catalog_validation_error",
            operation=operation,
            error=str(error),
        )
        return NotSupportedError(
            operation=operation or "unknown",
            catalog_name=catalog_uri or "polaris",
            reason=f"Validation failed: {error}",
        )

    # Bad request - invalid request parameters
    if isinstance(error, BadRequestError):
        logger.warning(
            "catalog_bad_request",
            operation=operation,
            error=str(error),
        )
        return NotSupportedError(
            operation=operation or "unknown",
            catalog_name=catalog_uri or "polaris",
            reason=f"Invalid request: {error}",
        )

    # Server error - internal catalog error
    if isinstance(error, ServerError):
        logger.error(
            "catalog_server_error",
            catalog_uri=catalog_uri,
            operation=operation,
            error=str(error),
        )
        return CatalogUnavailableError(
            catalog_uri=catalog_uri or "unknown",
            cause=error,
        )

    # Generic REST error - catch-all for REST catalog issues
    if isinstance(error, RESTError):
        logger.error(
            "catalog_rest_error",
            catalog_uri=catalog_uri,
            operation=operation,
            error=str(error),
        )
        return CatalogUnavailableError(
            catalog_uri=catalog_uri or "unknown",
            cause=error,
        )

    # Unknown error - wrap as CatalogUnavailableError
    logger.error(
        "catalog_unknown_error",
        error_type=type(error).__name__,
        error=str(error),
        catalog_uri=catalog_uri,
        operation=operation,
    )
    return CatalogUnavailableError(
        catalog_uri=catalog_uri or "unknown",
        cause=error,
    )


def _extract_identifier(message: str, resource_type: str) -> str:
    """Extract identifier from PyIceberg error message.

    PyIceberg error messages often contain the resource identifier.
    This helper attempts to extract it for better error context.

    Args:
        message: The error message string.
        resource_type: The type of resource (Namespace, Table, etc.).

    Returns:
        The extracted identifier or the original message if extraction fails.
    """
    # PyIceberg messages are often just the identifier itself
    # or in formats like "Namespace 'bronze' already exists"
    message = message.strip()

    # If message is empty, return unknown
    if not message:
        return "unknown"

    # If message looks like a quoted identifier, extract it
    if "'" in message:
        parts = message.split("'")
        if len(parts) >= 2:
            return parts[1]

    # If message looks like just the identifier, return it
    if " " not in message:
        return message

    # Otherwise return the message as the identifier
    return message


# Type alias for exception mapping entries
PYICEBERG_EXCEPTION_TYPES: tuple[type[Exception], ...] = (
    ServiceUnavailableError,
    UnauthorizedError,
    AuthorizationExpiredError,
    OAuthError,
    ForbiddenError,
    NamespaceAlreadyExistsError,
    TableAlreadyExistsError,
    NoSuchNamespaceError,
    NoSuchTableError,
    NoSuchViewError,
    NoSuchIdentifierError,
    NamespaceNotEmptyError,
    ValidationError,
    BadRequestError,
    ServerError,
    RESTError,
)
"""Tuple of all PyIceberg exception types that are mapped to floe errors."""
