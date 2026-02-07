"""Unit tests for retry logic (T051, T052).

Tests error categorization, retry decision logic, and retry decorator.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from floe_ingestion_dlt.config import RetryConfig
from floe_ingestion_dlt.errors import ErrorCategory, IngestionError
from floe_ingestion_dlt.retry import (
    categorize_error,
    is_retryable,
    create_retry_decorator,
)


class TestCategorizeError:
    """Test error categorization logic (T052)."""

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_timeout_error_is_transient(self) -> None:
        """Test TimeoutError categorized as TRANSIENT."""
        error = TimeoutError("timeout")
        assert categorize_error(error) == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_connection_error_is_transient(self) -> None:
        """Test ConnectionError categorized as TRANSIENT."""
        error = ConnectionError("connection failed")
        assert categorize_error(error) == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_os_error_is_transient(self) -> None:
        """Test OSError categorized as TRANSIENT."""
        error = OSError("os error")
        assert categorize_error(error) == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_permission_error_is_permanent(self) -> None:
        """Test PermissionError categorized as PERMANENT.

        PermissionError is a subclass of OSError but should be PERMANENT.
        """
        error = PermissionError("permission denied")
        assert categorize_error(error) == ErrorCategory.PERMANENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_key_error_is_permanent(self) -> None:
        """Test KeyError categorized as PERMANENT."""
        error = KeyError("missing key")
        assert categorize_error(error) == ErrorCategory.PERMANENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_value_error_is_configuration(self) -> None:
        """Test ValueError categorized as CONFIGURATION."""
        error = ValueError("invalid value")
        assert categorize_error(error) == ErrorCategory.CONFIGURATION

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_import_error_is_configuration(self) -> None:
        """Test ImportError categorized as CONFIGURATION."""
        error = ImportError("module not found")
        assert categorize_error(error) == ErrorCategory.CONFIGURATION

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_ingestion_error_uses_its_category(self) -> None:
        """Test IngestionError uses its own category field."""
        error = IngestionError(
            message="test error",
            source_type="test",
            destination_table="test",
            pipeline_name="test",
            category=ErrorCategory.PARTIAL,
        )
        assert categorize_error(error) == ErrorCategory.PARTIAL

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_unknown_error_is_permanent(self) -> None:
        """Test unknown error categorized as PERMANENT (fail-fast default)."""
        error = RuntimeError("unknown error")
        assert categorize_error(error) == ErrorCategory.PERMANENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_http_429_is_transient(self) -> None:
        """Test HTTP 429 (rate limit) categorized as TRANSIENT."""
        mock_error = Mock()
        mock_error.status_code = 429
        assert categorize_error(mock_error) == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4F-FR-053")
    def test_categorize_http_401_is_permanent(self) -> None:
        """Test HTTP 401 (unauthorized) categorized as PERMANENT."""
        mock_error = Mock()
        mock_error.status_code = 401
        assert categorize_error(mock_error) == ErrorCategory.PERMANENT


class TestIsRetryable:
    """Test retry decision logic (T051)."""

    @pytest.mark.requirement("4F-FR-052")
    def test_transient_error_is_retryable(self) -> None:
        """Test TRANSIENT errors are retryable."""
        error = TimeoutError("timeout")
        assert is_retryable(error) is True

    @pytest.mark.requirement("4F-FR-052")
    def test_permanent_error_is_not_retryable(self) -> None:
        """Test PERMANENT errors are not retryable."""
        error = PermissionError("permission denied")
        assert is_retryable(error) is False

    @pytest.mark.requirement("4F-FR-052")
    def test_configuration_error_is_not_retryable(self) -> None:
        """Test CONFIGURATION errors are not retryable."""
        error = ValueError("invalid value")
        assert is_retryable(error) is False


class TestCreateRetryDecorator:
    """Test retry decorator creation (T051)."""

    @pytest.mark.requirement("4F-FR-051")
    def test_retry_decorator_retries_transient_error(self) -> None:
        """Test retry decorator retries TRANSIENT errors.

        Given a function that raises TimeoutError N times then succeeds,
        when decorated with retry, then it is called max_retries+1 times.
        """
        call_count = 0
        max_retries = 2

        def flaky_function() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= max_retries:
                raise TimeoutError("temporary failure")
            return "success"

        retry_config = RetryConfig(max_retries=max_retries, initial_delay_seconds=0.01)
        retry_decorator = create_retry_decorator(retry_config)
        wrapped = retry_decorator(flaky_function)

        result = wrapped()
        assert result == "success"
        assert call_count == max_retries + 1  # 1 initial + 2 retries

    @pytest.mark.requirement("4F-FR-054")
    def test_retry_decorator_no_retry_on_permanent_error(self) -> None:
        """Test retry decorator does not retry PERMANENT errors.

        Given a function that raises PermissionError, when decorated with retry,
        then it is called exactly once (no retries).
        """
        call_count = 0

        def failing_function() -> None:
            nonlocal call_count
            call_count += 1
            raise PermissionError("permission denied")

        retry_config = RetryConfig(max_retries=2, initial_delay_seconds=0.01)
        retry_decorator = create_retry_decorator(retry_config)
        wrapped = retry_decorator(failing_function)

        with pytest.raises(PermissionError, match="permission denied"):
            wrapped()

        assert call_count == 1  # Called exactly once, no retries

    @pytest.mark.requirement("4F-FR-051")
    def test_retry_decorator_respects_max_retries(self) -> None:
        """Test retry decorator respects max_retries configuration.

        Given a function that always raises TimeoutError, when decorated with
        max_retries=2, then it is called exactly 3 times (1 initial + 2 retries).
        """
        call_count = 0

        def always_failing_function() -> None:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("always fails")

        retry_config = RetryConfig(max_retries=2, initial_delay_seconds=0.01)
        retry_decorator = create_retry_decorator(retry_config)
        wrapped = retry_decorator(always_failing_function)

        with pytest.raises(TimeoutError, match="always fails"):
            wrapped()

        assert call_count == 3  # 1 initial + 2 retries
