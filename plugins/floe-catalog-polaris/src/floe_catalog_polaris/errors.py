"""Error mapping from PyIceberg exceptions to floe errors.

This module provides exception mapping utilities for converting PyIceberg
catalog exceptions into floe's standardized error types.

Refactored to use Strategy Pattern (12B-CX-001) to reduce cyclomatic complexity
from CC 26 to CC ≤10. Each error type has a dedicated handler function registered
in ERROR_HANDLERS dispatch dictionary.

Example:
    >>> from floe_catalog_polaris.errors import map_pyiceberg_error
    >>> from pyiceberg.exceptions import NoSuchNamespaceError
    >>> try:
    ...     raise NoSuchNamespaceError("bronze")
    ... except Exception as e:
    ...     raise map_pyiceberg_error(e) from e

Requirements Covered:
    - FR-033: System MUST support error mapping for catalog operations
    - 12B-CX-001: Reduce map_pyiceberg_error CC from 26 to ≤10
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

import structlog
from floe_core.plugin_errors import (
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

# Type alias for error handler functions
ErrorHandler: TypeAlias = Callable[
    [Exception, str | None, str | None], CatalogError
]


# =============================================================================
# Helper Functions
# =============================================================================


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


# =============================================================================
# Error Handler Functions (Strategy Pattern - T030)
# =============================================================================


def _handle_service_unavailable(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle ServiceUnavailableError - catalog is unreachable."""
    logger.warning(
        "catalog_service_unavailable",
        catalog_uri=catalog_uri,
        error=str(error),
    )
    return CatalogUnavailableError(
        catalog_uri=catalog_uri or "unknown",
        cause=error,
    )


def _handle_unauthorized(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle UnauthorizedError - authentication failure."""
    logger.warning(
        "catalog_unauthorized",
        operation=operation,
        error=str(error),
    )
    return AuthenticationError(
        message=str(error),
        operation=operation,
    )


def _handle_authorization_expired(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle AuthorizationExpiredError - token needs refresh."""
    logger.warning(
        "catalog_authorization_expired",
        operation=operation,
        error=str(error),
    )
    return AuthenticationError(
        message="Authorization expired - token refresh required",
        operation=operation,
    )


def _handle_oauth_error(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle OAuthError - authentication configuration issues."""
    logger.error(
        "catalog_oauth_error",
        operation=operation,
        error=str(error),
    )
    return AuthenticationError(
        message=f"OAuth2 authentication failed: {error}",
        operation=operation,
    )


def _handle_forbidden(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle ForbiddenError - insufficient privileges."""
    logger.warning(
        "catalog_forbidden",
        operation=operation,
        error=str(error),
    )
    return AuthenticationError(
        message=f"Permission denied: {error}",
        operation=operation,
    )


def _handle_namespace_already_exists(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle NamespaceAlreadyExistsError - conflict error."""
    namespace = _extract_identifier(str(error), "Namespace")
    logger.info(
        "catalog_namespace_already_exists",
        namespace=namespace,
    )
    return ConflictError(
        resource_type="namespace",
        identifier=namespace,
    )


def _handle_table_already_exists(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle TableAlreadyExistsError - conflict error."""
    table = _extract_identifier(str(error), "Table")
    logger.info(
        "catalog_table_already_exists",
        table=table,
    )
    return ConflictError(
        resource_type="table",
        identifier=table,
    )


def _handle_no_such_namespace(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle NoSuchNamespaceError - namespace not found."""
    namespace = _extract_identifier(str(error), "Namespace")
    logger.debug(
        "catalog_namespace_not_found",
        namespace=namespace,
    )
    return NotFoundError(
        resource_type="namespace",
        identifier=namespace,
    )


def _handle_no_such_table(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle NoSuchTableError - table not found."""
    table = _extract_identifier(str(error), "Table")
    logger.debug(
        "catalog_table_not_found",
        table=table,
    )
    return NotFoundError(
        resource_type="table",
        identifier=table,
    )


def _handle_no_such_view(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle NoSuchViewError - view not found."""
    view = _extract_identifier(str(error), "View")
    logger.debug(
        "catalog_view_not_found",
        view=view,
    )
    return NotFoundError(
        resource_type="view",
        identifier=view,
    )


def _handle_no_such_identifier(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle NoSuchIdentifierError - generic identifier not found."""
    identifier = str(error)
    logger.debug(
        "catalog_identifier_not_found",
        identifier=identifier,
    )
    return NotFoundError(
        resource_type="identifier",
        identifier=identifier,
    )


def _handle_namespace_not_empty(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle NamespaceNotEmptyError - cannot delete non-empty namespace."""
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


def _handle_validation_error(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle ValidationError - bad request data."""
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


def _handle_bad_request(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle BadRequestError - invalid request parameters."""
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


def _handle_server_error(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle ServerError - internal catalog error."""
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


def _handle_rest_error(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle RESTError - generic REST catalog issues."""
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


def _handle_unknown_error(
    error: Exception,
    catalog_uri: str | None,
    operation: str | None,
) -> CatalogError:
    """Handle unknown error - wrap as generic CatalogError."""
    logger.error(
        "catalog_unknown_error",
        error_type=type(error).__name__,
        error=str(error),
        catalog_uri=catalog_uri,
        operation=operation,
    )
    return CatalogError(
        f"Unexpected catalog error during {operation or 'operation'}: {error}",
    )


# =============================================================================
# Error Handler Dispatch Dictionary (T031)
# =============================================================================

ERROR_HANDLERS: dict[type[Exception], ErrorHandler] = {
    ServiceUnavailableError: _handle_service_unavailable,
    UnauthorizedError: _handle_unauthorized,
    AuthorizationExpiredError: _handle_authorization_expired,
    OAuthError: _handle_oauth_error,
    ForbiddenError: _handle_forbidden,
    NamespaceAlreadyExistsError: _handle_namespace_already_exists,
    TableAlreadyExistsError: _handle_table_already_exists,
    NoSuchNamespaceError: _handle_no_such_namespace,
    NoSuchTableError: _handle_no_such_table,
    NoSuchViewError: _handle_no_such_view,
    NoSuchIdentifierError: _handle_no_such_identifier,
    NamespaceNotEmptyError: _handle_namespace_not_empty,
    ValidationError: _handle_validation_error,
    BadRequestError: _handle_bad_request,
    ServerError: _handle_server_error,
    RESTError: _handle_rest_error,
}
"""Dispatch dictionary mapping PyIceberg exception types to handler functions.

This pattern reduces cyclomatic complexity from O(n) if-else chains to O(1)
dictionary lookup, making the code easier to maintain and extend.

To add a new error mapping:
    1. Create a handler function: _handle_new_error(error, catalog_uri, operation)
    2. Add entry to ERROR_HANDLERS: NewErrorType: _handle_new_error
"""


# =============================================================================
# Main Entry Point (Refactored - T032)
# =============================================================================


def map_pyiceberg_error(
    error: Exception,
    catalog_uri: str | None = None,
    operation: str | None = None,
) -> CatalogError:
    """Map a PyIceberg exception to a floe CatalogError.

    Converts PyIceberg-specific exceptions into standardized floe catalog
    errors with appropriate context for logging and error handling.

    Uses Strategy Pattern with ERROR_HANDLERS dispatch dictionary to maintain
    low cyclomatic complexity (CC ≤10) while supporting 16+ error types.

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
    # Look up handler by exact exception type
    error_type = type(error)
    handler = ERROR_HANDLERS.get(error_type)

    if handler is not None:
        return handler(error, catalog_uri, operation)

    # Check for subclass matches (inheritance hierarchy)
    for exc_type, exc_handler in ERROR_HANDLERS.items():
        if isinstance(error, exc_type):
            return exc_handler(error, catalog_uri, operation)

    # Unknown error - use fallback handler
    return _handle_unknown_error(error, catalog_uri, operation)


# =============================================================================
# Exported Constants
# =============================================================================

# Type alias for exception mapping entries
PYICEBERG_EXCEPTION_TYPES: tuple[type[Exception], ...] = tuple(ERROR_HANDLERS.keys())
"""Tuple of all PyIceberg exception types that are mapped to floe errors."""
