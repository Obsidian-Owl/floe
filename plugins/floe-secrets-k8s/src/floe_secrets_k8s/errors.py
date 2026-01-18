"""Custom exceptions for K8sSecretsPlugin.

This module provides custom exception classes for the K8s Secrets plugin.

Implements:
    - CR-004: Error handling requirements

Exception Hierarchy:
    SecretsPluginError (base)
    ├── SecretNotFoundError
    ├── SecretAccessDeniedError (wraps PermissionError)
    └── SecretBackendUnavailableError (wraps ConnectionError)

Example:
    >>> from floe_secrets_k8s.errors import SecretNotFoundError
    >>> raise SecretNotFoundError("db-password", namespace="production")
    SecretNotFoundError: Secret 'db-password' not found in namespace 'production'
"""

from __future__ import annotations


class SecretsPluginError(Exception):
    """Base exception for all secrets plugin errors.

    All exceptions raised by K8sSecretsPlugin inherit from this class,
    allowing callers to catch all plugin-specific errors with a single
    except clause.

    Attributes:
        message: Human-readable error message.

    Example:
        >>> try:
        ...     plugin.get_secret("missing")
        ... except SecretsPluginError as e:
        ...     print(f"Secrets error: {e}")
    """

    def __init__(self, message: str) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message.
        """
        self.message = message
        super().__init__(message)


class SecretNotFoundError(SecretsPluginError):
    """Raised when a requested secret does not exist.

    Note: Per CR-004, get_secret() should return None for missing secrets
    rather than raising this exception. This exception is available for
    cases where explicit error handling is preferred.

    Attributes:
        secret_name: The name of the secret that was not found.
        namespace: The K8s namespace searched.

    Example:
        >>> raise SecretNotFoundError("db-password", namespace="production")
        SecretNotFoundError: Secret 'db-password' not found in namespace 'production'
    """

    def __init__(self, secret_name: str, *, namespace: str = "default") -> None:
        """Initialize the exception.

        Args:
            secret_name: The name of the secret that was not found.
            namespace: The K8s namespace where the secret was expected.
        """
        self.secret_name = secret_name
        self.namespace = namespace
        message = f"Secret '{secret_name}' not found in namespace '{namespace}'"
        super().__init__(message)


class SecretAccessDeniedError(SecretsPluginError, PermissionError):
    """Raised when access to a secret is denied.

    This exception inherits from both SecretsPluginError and PermissionError,
    allowing it to be caught by either exception type per CR-004.

    Attributes:
        secret_name: The name of the secret access was denied to.
        namespace: The K8s namespace.
        reason: Additional context about why access was denied.

    Example:
        >>> raise SecretAccessDeniedError(
        ...     "db-password",
        ...     namespace="production",
        ...     reason="ServiceAccount lacks 'get' permission",
        ... )
    """

    def __init__(
        self,
        secret_name: str,
        *,
        namespace: str = "default",
        reason: str = "",
    ) -> None:
        """Initialize the exception.

        Args:
            secret_name: The name of the secret access was denied to.
            namespace: The K8s namespace.
            reason: Additional context about why access was denied.
        """
        self.secret_name = secret_name
        self.namespace = namespace
        self.reason = reason
        message = f"Access denied to secret '{secret_name}' in namespace '{namespace}'"
        if reason:
            message = f"{message}: {reason}"
        # Initialize both parent classes
        SecretsPluginError.__init__(self, message)


class SecretBackendUnavailableError(SecretsPluginError, ConnectionError):
    """Raised when the K8s API server is unavailable.

    This exception inherits from both SecretsPluginError and ConnectionError,
    allowing it to be caught by either exception type per CR-004.

    Attributes:
        endpoint: The K8s API endpoint that was unreachable.
        reason: Additional context about the connection failure.

    Example:
        >>> raise SecretBackendUnavailableError(
        ...     endpoint="https://kubernetes.default.svc",
        ...     reason="Connection timed out",
        ... )
    """

    def __init__(
        self,
        *,
        endpoint: str = "",
        reason: str = "",
    ) -> None:
        """Initialize the exception.

        Args:
            endpoint: The K8s API endpoint that was unreachable.
            reason: Additional context about the connection failure.
        """
        self.endpoint = endpoint
        self.reason = reason
        message = "Kubernetes API server unavailable"
        if endpoint:
            message = f"{message} at {endpoint}"
        if reason:
            message = f"{message}: {reason}"
        # Initialize both parent classes
        SecretsPluginError.__init__(self, message)


class SecretValidationError(SecretsPluginError, ValueError):
    """Raised when secret data fails validation.

    This exception is raised when attempting to store invalid secret data,
    such as non-string values or invalid secret names.

    Attributes:
        field: The field that failed validation.
        reason: Why validation failed.

    Example:
        >>> raise SecretValidationError(
        ...     field="secret_name",
        ...     reason="Name must be lowercase alphanumeric",
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
        SecretsPluginError.__init__(self, message)


__all__ = [
    "SecretsPluginError",
    "SecretNotFoundError",
    "SecretAccessDeniedError",
    "SecretBackendUnavailableError",
    "SecretValidationError",
]
