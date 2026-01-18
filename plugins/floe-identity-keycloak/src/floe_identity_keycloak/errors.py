"""Custom exceptions for KeycloakIdentityPlugin.

This module provides custom exception classes for the Keycloak Identity plugin.

Implements:
    - CR-004: Error handling requirements

Exception Hierarchy:
    KeycloakPluginError (base)
    ├── KeycloakConfigError (configuration issues)
    ├── KeycloakAuthError (authentication failures)
    ├── KeycloakTokenError (token validation failures)
    └── KeycloakUnavailableError (connectivity issues)
"""

from __future__ import annotations


class KeycloakPluginError(Exception):
    """Base exception for all Keycloak plugin errors.

    All plugin-specific exceptions inherit from this base class,
    allowing callers to catch all Keycloak-related errors with a
    single except clause if needed.

    Attributes:
        message: Human-readable error description.
        details: Optional additional error details.

    Examples:
        >>> try:
        ...     plugin.authenticate(credentials)
        ... except KeycloakPluginError as e:
        ...     logger.error(f"Keycloak error: {e}")
    """

    def __init__(self, message: str, details: str | None = None) -> None:
        """Initialize KeycloakPluginError.

        Args:
            message: Human-readable error description.
            details: Optional additional error details for debugging.
        """
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class KeycloakConfigError(KeycloakPluginError):
    """Exception raised for configuration errors.

    Raised when the plugin configuration is invalid, such as
    missing required fields, invalid URLs, or incompatible settings.

    Examples:
        >>> raise KeycloakConfigError(
        ...     "Invalid server URL",
        ...     details="URL must start with https://"
        ... )
    """

    pass


class KeycloakAuthError(KeycloakPluginError):
    """Exception raised for authentication failures.

    Raised when authentication fails due to invalid credentials,
    disabled accounts, or other authentication-related issues.

    Attributes:
        error_code: Optional OAuth2 error code (e.g., "invalid_grant").

    Examples:
        >>> raise KeycloakAuthError(
        ...     "Authentication failed",
        ...     error_code="invalid_grant",
        ...     details="Invalid username or password"
        ... )
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: str | None = None,
    ) -> None:
        """Initialize KeycloakAuthError.

        Args:
            message: Human-readable error description.
            error_code: Optional OAuth2 error code.
            details: Optional additional error details.
        """
        super().__init__(message, details)
        self.error_code = error_code

    def __str__(self) -> str:
        """Return string representation including error code."""
        base = super().__str__()
        if self.error_code:
            return f"{base} (code: {self.error_code})"
        return base


class KeycloakTokenError(KeycloakPluginError):
    """Exception raised for token validation failures.

    Raised when token validation fails due to expired tokens,
    invalid signatures, missing claims, or other JWT-related issues.

    Attributes:
        reason: Specific reason for token failure.

    Examples:
        >>> raise KeycloakTokenError(
        ...     "Token validation failed",
        ...     reason="expired",
        ...     details="Token expired at 2026-01-18T00:00:00Z"
        ... )
    """

    def __init__(
        self,
        message: str,
        reason: str | None = None,
        details: str | None = None,
    ) -> None:
        """Initialize KeycloakTokenError.

        Args:
            message: Human-readable error description.
            reason: Specific reason for failure (e.g., "expired", "invalid_signature").
            details: Optional additional error details.
        """
        super().__init__(message, details)
        self.reason = reason

    def __str__(self) -> str:
        """Return string representation including reason."""
        base = super().__str__()
        if self.reason:
            return f"{base} (reason: {self.reason})"
        return base


class KeycloakUnavailableError(KeycloakPluginError):
    """Exception raised when Keycloak server is unavailable.

    Raised when the plugin cannot connect to the Keycloak server
    due to network issues, server downtime, or DNS failures.
    Wraps underlying connection errors for consistent handling.

    Attributes:
        original_error: The underlying exception that caused this error.

    Examples:
        >>> try:
        ...     response = httpx.get(keycloak_url)
        ... except httpx.ConnectError as e:
        ...     raise KeycloakUnavailableError(
        ...         "Cannot connect to Keycloak server",
        ...         original_error=e
        ...     )
    """

    def __init__(
        self,
        message: str,
        original_error: Exception | None = None,
        details: str | None = None,
    ) -> None:
        """Initialize KeycloakUnavailableError.

        Args:
            message: Human-readable error description.
            original_error: The underlying exception that caused this error.
            details: Optional additional error details.
        """
        super().__init__(message, details)
        self.original_error = original_error

    def __str__(self) -> str:
        """Return string representation including original error."""
        base = super().__str__()
        if self.original_error:
            return f"{base} (caused by: {type(self.original_error).__name__})"
        return base
