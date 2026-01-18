"""Custom exceptions for InfisicalSecretsPlugin.

This module provides custom exception classes for the Infisical Secrets plugin.

Implements:
    - CR-004: Error handling requirements

Exception Hierarchy:
    InfisicalPluginError (base)
    ├── InfisicalAuthError (authentication failure)
    ├── InfisicalSecretNotFoundError (secret not found)
    ├── InfisicalAccessDeniedError (wraps PermissionError)
    └── InfisicalBackendUnavailableError (wraps ConnectionError)

Example:
    >>> from floe_secrets_infisical.errors import InfisicalAuthError
    >>> raise InfisicalAuthError("Invalid credentials")
    InfisicalAuthError: Infisical authentication failed: Invalid credentials
"""

from __future__ import annotations


class InfisicalPluginError(Exception):
    """Base exception for all Infisical plugin errors.

    All exceptions raised by InfisicalSecretsPlugin inherit from this class,
    allowing callers to catch all plugin-specific errors with a single
    except clause.

    Attributes:
        message: Human-readable error message.

    Example:
        >>> try:
        ...     plugin.get_secret("missing")
        ... except InfisicalPluginError as e:
        ...     print(f"Infisical error: {e}")
    """

    def __init__(self, message: str) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message.
        """
        self.message = message
        super().__init__(message)


class InfisicalAuthError(InfisicalPluginError):
    """Raised when Infisical authentication fails.

    This exception is raised when Universal Auth credentials are invalid
    or the authentication flow fails.

    Attributes:
        reason: Additional context about the authentication failure.

    Example:
        >>> raise InfisicalAuthError("Invalid client credentials")
        InfisicalAuthError: Infisical authentication failed: Invalid client credentials
    """

    def __init__(self, reason: str = "") -> None:
        """Initialize the exception.

        Args:
            reason: Additional context about the authentication failure.
        """
        self.reason = reason
        message = "Infisical authentication failed"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


class InfisicalSecretNotFoundError(InfisicalPluginError):
    """Raised when a requested secret does not exist.

    Note: Per CR-004, get_secret() should return None for missing secrets
    rather than raising this exception. This exception is available for
    cases where explicit error handling is preferred.

    Attributes:
        secret_key: The key of the secret that was not found.
        path: The path where the secret was expected.
        environment: The environment searched.

    Example:
        >>> raise InfisicalSecretNotFoundError(
        ...     "db-password",
        ...     path="/floe",
        ...     environment="dev",
        ... )  # doctest: +ELLIPSIS
        InfisicalSecretNotFoundError: Secret 'db-password' not found...
    """

    def __init__(
        self,
        secret_key: str,
        *,
        path: str = "/",
        environment: str = "dev",
    ) -> None:
        """Initialize the exception.

        Args:
            secret_key: The key of the secret that was not found.
            path: The path where the secret was expected.
            environment: The environment searched.
        """
        self.secret_key = secret_key
        self.path = path
        self.environment = environment
        message = f"Secret '{secret_key}' not found at path '{path}' in environment '{environment}'"
        super().__init__(message)


class InfisicalAccessDeniedError(InfisicalPluginError, PermissionError):
    """Raised when access to a secret or project is denied.

    This exception inherits from both InfisicalPluginError and PermissionError,
    allowing it to be caught by either exception type per CR-004.

    Attributes:
        secret_key: The key of the secret access was denied to (if applicable).
        project_id: The project ID (if applicable).
        reason: Additional context about why access was denied.

    Example:
        >>> raise InfisicalAccessDeniedError(
        ...     secret_key="db-password",
        ...     reason="Insufficient permissions for this environment",
        ... )
    """

    def __init__(
        self,
        *,
        secret_key: str = "",
        project_id: str = "",
        reason: str = "",
    ) -> None:
        """Initialize the exception.

        Args:
            secret_key: The key of the secret access was denied to.
            project_id: The project ID.
            reason: Additional context about why access was denied.
        """
        self.secret_key = secret_key
        self.project_id = project_id
        self.reason = reason

        message = "Infisical access denied"
        if secret_key:
            message = f"{message} to secret '{secret_key}'"
        if project_id:
            message = f"{message} in project '{project_id}'"
        if reason:
            message = f"{message}: {reason}"

        # Initialize both parent classes
        InfisicalPluginError.__init__(self, message)


class InfisicalBackendUnavailableError(InfisicalPluginError, ConnectionError):
    """Raised when the Infisical API is unavailable.

    This exception inherits from both InfisicalPluginError and ConnectionError,
    allowing it to be caught by either exception type per CR-004.

    Attributes:
        site_url: The Infisical site URL that was unreachable.
        reason: Additional context about the connection failure.

    Example:
        >>> raise InfisicalBackendUnavailableError(
        ...     site_url="https://app.infisical.com",
        ...     reason="Connection timed out",
        ... )
    """

    def __init__(
        self,
        *,
        site_url: str = "",
        reason: str = "",
    ) -> None:
        """Initialize the exception.

        Args:
            site_url: The Infisical site URL that was unreachable.
            reason: Additional context about the connection failure.
        """
        self.site_url = site_url
        self.reason = reason

        message = "Infisical API unavailable"
        if site_url:
            message = f"{message} at {site_url}"
        if reason:
            message = f"{message}: {reason}"

        # Initialize both parent classes
        InfisicalPluginError.__init__(self, message)


class InfisicalValidationError(InfisicalPluginError, ValueError):
    """Raised when secret data fails validation.

    This exception is raised when attempting to store invalid secret data,
    such as invalid secret keys or malformed values.

    Attributes:
        field: The field that failed validation.
        reason: Why validation failed.

    Example:
        >>> raise InfisicalValidationError(
        ...     field="secret_key",
        ...     reason="Key must not contain special characters",
        ... )
    """

    def __init__(self, *, field: str, reason: str) -> None:
        """Initialize the exception.

        Args:
            field: The field that failed validation.
            reason: Why validation failed.
        """
        self.field = field
        self.reason = reason
        message = f"Validation failed for '{field}': {reason}"
        InfisicalPluginError.__init__(self, message)


__all__ = [
    "InfisicalPluginError",
    "InfisicalAuthError",
    "InfisicalSecretNotFoundError",
    "InfisicalAccessDeniedError",
    "InfisicalBackendUnavailableError",
    "InfisicalValidationError",
]
