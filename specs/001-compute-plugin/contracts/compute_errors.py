"""Compute Error Classes Contract Definition.

This file defines the exception hierarchy for compute plugin errors.
All compute-related exceptions inherit from ComputeError.

Location: packages/floe-core/src/floe_core/compute_errors.py
"""

from __future__ import annotations


class ComputeError(Exception):
    """Base exception for compute plugin errors.

    All compute-related exceptions inherit from this class. Supports
    optional correlation_id for debugging and tracing (FR-023).

    Attributes:
        message: Human-readable error message.
        correlation_id: Optional ID for correlating errors across logs.

    Example:
        >>> raise ComputeError("Connection failed", correlation_id="abc123")
    """

    def __init__(self, message: str, correlation_id: str | None = None) -> None:
        """Initialize ComputeError.

        Args:
            message: Human-readable error message.
            correlation_id: Optional ID for log correlation.
        """
        super().__init__(message)
        self.correlation_id = correlation_id

    def __str__(self) -> str:
        """Return string representation with correlation ID if present."""
        if self.correlation_id:
            return f"{super().__str__()} [correlation_id={self.correlation_id}]"
        return super().__str__()


class ComputeConnectionError(ComputeError):
    """Connection to compute target failed.

    Raised when validate_connection() cannot establish a connection
    to the compute target (database unreachable, auth failed, etc.).

    Attributes:
        plugin_name: Name of the compute plugin that failed.
        original_error: The underlying exception that caused the failure.

    Example:
        >>> raise ComputeConnectionError(
        ...     "Could not connect to DuckDB",
        ...     plugin_name="duckdb",
        ...     original_error=e
        ... )
    """

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        original_error: Exception | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Initialize ComputeConnectionError.

        Args:
            message: Human-readable error message.
            plugin_name: Name of the compute plugin.
            original_error: Underlying exception.
            correlation_id: Optional ID for log correlation.
        """
        super().__init__(message, correlation_id)
        self.plugin_name = plugin_name
        self.original_error = original_error


class ComputeTimeoutError(ComputeError):
    """Operation timed out.

    Raised when a compute operation (connection, query) exceeds
    the configured timeout.

    Attributes:
        plugin_name: Name of the compute plugin.
        timeout_seconds: The timeout that was exceeded.

    Example:
        >>> raise ComputeTimeoutError(
        ...     "Connection timed out after 5 seconds",
        ...     plugin_name="snowflake",
        ...     timeout_seconds=5
        ... )
    """

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        timeout_seconds: float | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Initialize ComputeTimeoutError.

        Args:
            message: Human-readable error message.
            plugin_name: Name of the compute plugin.
            timeout_seconds: The timeout that was exceeded.
            correlation_id: Optional ID for log correlation.
        """
        super().__init__(message, correlation_id)
        self.plugin_name = plugin_name
        self.timeout_seconds = timeout_seconds


class ComputeConfigurationError(ComputeError):
    """Invalid compute configuration.

    Raised when ComputeConfig validation fails or when the configuration
    is invalid for the specific compute plugin.

    Attributes:
        plugin_name: Name of the compute plugin.
        validation_errors: List of validation error messages.

    Example:
        >>> raise ComputeConfigurationError(
        ...     "Invalid DuckDB configuration",
        ...     plugin_name="duckdb",
        ...     validation_errors=["memory_limit must end with GB or MB"]
        ... )
    """

    def __init__(
        self,
        message: str,
        plugin_name: str | None = None,
        validation_errors: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Initialize ComputeConfigurationError.

        Args:
            message: Human-readable error message.
            plugin_name: Name of the compute plugin.
            validation_errors: List of validation error messages.
            correlation_id: Optional ID for log correlation.
        """
        super().__init__(message, correlation_id)
        self.plugin_name = plugin_name
        self.validation_errors = validation_errors or []
