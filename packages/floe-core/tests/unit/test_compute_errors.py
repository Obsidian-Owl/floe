"""Unit tests for compute error classes.

Tests the exception hierarchy in compute_errors.py for proper
initialization, string representation, and attribute handling.
"""

from __future__ import annotations

import pytest

from floe_core.compute_errors import (
    ComputeConfigurationError,
    ComputeConnectionError,
    ComputeError,
    ComputeTimeoutError,
)


class TestComputeError:
    """Test ComputeError base exception."""

    @pytest.mark.requirement("001-FR-023")
    def test_compute_error_basic(self) -> None:
        """Test ComputeError with message only."""
        error = ComputeError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.correlation_id is None

    @pytest.mark.requirement("001-FR-023")
    def test_compute_error_with_correlation_id(self) -> None:
        """Test ComputeError includes correlation_id in string."""
        error = ComputeError("Connection failed", correlation_id="req-12345")
        assert "Connection failed" in str(error)
        assert "[correlation_id=req-12345]" in str(error)
        assert error.correlation_id == "req-12345"

    @pytest.mark.requirement("001-FR-023")
    def test_compute_error_is_exception(self) -> None:
        """Test ComputeError can be raised and caught."""
        with pytest.raises(ComputeError, match="Test error"):
            raise ComputeError("Test error")

    @pytest.mark.requirement("001-FR-023")
    def test_compute_error_hierarchy(self) -> None:
        """Test ComputeError inherits from Exception."""
        error = ComputeError("Test")
        assert isinstance(error, Exception)


class TestComputeConnectionError:
    """Test ComputeConnectionError exception."""

    @pytest.mark.requirement("001-FR-023")
    def test_connection_error_basic(self) -> None:
        """Test ComputeConnectionError with message only."""
        error = ComputeConnectionError("Connection refused")
        assert str(error) == "Connection refused"
        assert error.plugin_name is None
        assert error.original_error is None

    @pytest.mark.requirement("001-FR-023")
    def test_connection_error_with_plugin_name(self) -> None:
        """Test ComputeConnectionError captures plugin name."""
        error = ComputeConnectionError(
            "Could not connect",
            plugin_name="duckdb",
        )
        assert error.plugin_name == "duckdb"

    @pytest.mark.requirement("001-FR-023")
    def test_connection_error_with_original_error(self) -> None:
        """Test ComputeConnectionError wraps original exception."""
        original = RuntimeError("Socket timeout")
        error = ComputeConnectionError(
            "Connection failed",
            plugin_name="snowflake",
            original_error=original,
        )
        assert error.original_error is original
        assert isinstance(error.original_error, RuntimeError)

    @pytest.mark.requirement("001-FR-023")
    def test_connection_error_full(self) -> None:
        """Test ComputeConnectionError with all attributes."""
        original = ValueError("Invalid credentials")
        error = ComputeConnectionError(
            "Authentication failed",
            plugin_name="bigquery",
            original_error=original,
            correlation_id="trace-abc",
        )
        assert "Authentication failed" in str(error)
        assert "[correlation_id=trace-abc]" in str(error)
        assert error.plugin_name == "bigquery"
        assert error.original_error is original

    @pytest.mark.requirement("001-FR-023")
    def test_connection_error_hierarchy(self) -> None:
        """Test ComputeConnectionError inherits from ComputeError."""
        error = ComputeConnectionError("Test")
        assert isinstance(error, ComputeError)
        assert isinstance(error, Exception)


class TestComputeTimeoutError:
    """Test ComputeTimeoutError exception."""

    @pytest.mark.requirement("001-FR-023")
    def test_timeout_error_basic(self) -> None:
        """Test ComputeTimeoutError with message only."""
        error = ComputeTimeoutError("Operation timed out")
        assert str(error) == "Operation timed out"
        assert error.plugin_name is None
        assert error.timeout_seconds is None

    @pytest.mark.requirement("001-FR-023")
    def test_timeout_error_with_timeout(self) -> None:
        """Test ComputeTimeoutError captures timeout value."""
        error = ComputeTimeoutError(
            "Query timed out after 30 seconds",
            plugin_name="snowflake",
            timeout_seconds=30.0,
        )
        assert error.plugin_name == "snowflake"
        assert error.timeout_seconds == pytest.approx(30.0)

    @pytest.mark.requirement("001-FR-023")
    def test_timeout_error_with_correlation_id(self) -> None:
        """Test ComputeTimeoutError includes correlation_id."""
        error = ComputeTimeoutError(
            "Connection timeout",
            timeout_seconds=5.0,
            correlation_id="req-timeout-123",
        )
        assert "[correlation_id=req-timeout-123]" in str(error)

    @pytest.mark.requirement("001-FR-023")
    def test_timeout_error_hierarchy(self) -> None:
        """Test ComputeTimeoutError inherits from ComputeError."""
        error = ComputeTimeoutError("Test")
        assert isinstance(error, ComputeError)
        assert isinstance(error, Exception)


class TestComputeConfigurationError:
    """Test ComputeConfigurationError exception."""

    @pytest.mark.requirement("001-FR-023")
    def test_configuration_error_basic(self) -> None:
        """Test ComputeConfigurationError with message only."""
        error = ComputeConfigurationError("Invalid configuration")
        assert str(error) == "Invalid configuration"
        assert error.plugin_name is None
        assert error.validation_errors == []

    @pytest.mark.requirement("001-FR-023")
    def test_configuration_error_with_validation_errors(self) -> None:
        """Test ComputeConfigurationError captures validation errors."""
        error = ComputeConfigurationError(
            "Configuration validation failed",
            plugin_name="duckdb",
            validation_errors=[
                "memory_limit must end with GB or MB",
                "threads must be between 1 and 64",
            ],
        )
        assert error.plugin_name == "duckdb"
        assert len(error.validation_errors) == 2
        assert "memory_limit" in error.validation_errors[0]

    @pytest.mark.requirement("001-FR-023")
    def test_configuration_error_none_validation_errors(self) -> None:
        """Test ComputeConfigurationError defaults validation_errors to empty list."""
        error = ComputeConfigurationError(
            "Invalid config",
            validation_errors=None,
        )
        assert error.validation_errors == []

    @pytest.mark.requirement("001-FR-023")
    def test_configuration_error_full(self) -> None:
        """Test ComputeConfigurationError with all attributes."""
        error = ComputeConfigurationError(
            "DuckDB configuration invalid",
            plugin_name="duckdb",
            validation_errors=["path cannot be empty"],
            correlation_id="config-err-456",
        )
        assert "DuckDB configuration invalid" in str(error)
        assert "[correlation_id=config-err-456]" in str(error)
        assert error.plugin_name == "duckdb"
        assert "path cannot be empty" in error.validation_errors

    @pytest.mark.requirement("001-FR-023")
    def test_configuration_error_hierarchy(self) -> None:
        """Test ComputeConfigurationError inherits from ComputeError."""
        error = ComputeConfigurationError("Test")
        assert isinstance(error, ComputeError)
        assert isinstance(error, Exception)


class TestExceptionCatching:
    """Test exception hierarchy for catch patterns."""

    @pytest.mark.requirement("001-FR-023")
    def test_catch_all_compute_errors(self) -> None:
        """Test catching all compute errors with base class."""
        errors = [
            ComputeError("base error"),
            ComputeConnectionError("connection error"),
            ComputeTimeoutError("timeout error"),
            ComputeConfigurationError("config error"),
        ]

        for error in errors:
            with pytest.raises(ComputeError):
                raise error

    @pytest.mark.requirement("001-FR-023")
    def test_catch_specific_error(self) -> None:
        """Test catching specific error types."""
        # ComputeConnectionError should not be caught by ComputeTimeoutError
        with pytest.raises(ComputeConnectionError):
            try:
                raise ComputeConnectionError("Connection failed")
            except ComputeTimeoutError:
                pytest.fail("Should not catch ComputeConnectionError as ComputeTimeoutError")
