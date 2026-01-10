"""Unit tests for retry utilities.

This module tests the retry decorator and utilities for handling
transient failures with exponential backoff.

Requirements Covered:
    - FR-033: System MUST support retry logic with configurable backoff
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from floe_catalog_polaris.retry import (
    RETRYABLE_EXCEPTIONS,
    create_retry_decorator,
    with_retry,
)


class TestCreateRetryDecorator:
    """Tests for create_retry_decorator function."""

    @pytest.mark.requirement("FR-033")
    def test_creates_callable_decorator(self) -> None:
        """Test decorator creation returns a callable."""
        decorator = create_retry_decorator(max_retries=3)
        assert callable(decorator)

    @pytest.mark.requirement("FR-033")
    def test_decorator_with_zero_retries_returns_identity(self) -> None:
        """Test zero retries returns identity decorator (no retry)."""
        decorator = create_retry_decorator(max_retries=0)

        call_count = 0

        @decorator
        def failing_func() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Test error")

        with pytest.raises(ConnectionError):
            failing_func()

        # Should only be called once (no retries)
        assert call_count == 1

    @pytest.mark.requirement("FR-033")
    def test_decorator_retries_on_connection_error(self) -> None:
        """Test decorator retries on ConnectionError."""
        decorator = create_retry_decorator(
            max_retries=3,
            min_wait_seconds=0.01,  # Fast for tests
            max_wait_seconds=0.1,
        )

        call_count = 0

        @decorator
        def sometimes_fails() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return "success"

        result = sometimes_fails()

        assert result == "success"
        assert call_count == 3  # 2 failures + 1 success

    @pytest.mark.requirement("FR-033")
    def test_decorator_retries_on_timeout_error(self) -> None:
        """Test decorator retries on TimeoutError."""
        decorator = create_retry_decorator(
            max_retries=2,
            min_wait_seconds=0.01,
            max_wait_seconds=0.1,
        )

        call_count = 0

        @decorator
        def timeout_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Connection timed out")
            return "ok"

        result = timeout_then_success()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.requirement("FR-033")
    def test_decorator_does_not_retry_on_value_error(self) -> None:
        """Test decorator does NOT retry on non-retryable exceptions."""
        decorator = create_retry_decorator(
            max_retries=5,
            min_wait_seconds=0.01,
        )

        call_count = 0

        @decorator
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Programming error - should not retry")

        with pytest.raises(ValueError, match="Programming error"):
            always_fails()

        # Should only be called once (ValueError is not retryable)
        assert call_count == 1

    @pytest.mark.requirement("FR-033")
    def test_decorator_exhausts_retries_and_raises(self) -> None:
        """Test decorator raises after exhausting all retries."""
        decorator = create_retry_decorator(
            max_retries=2,
            min_wait_seconds=0.01,
            max_wait_seconds=0.1,
        )

        call_count = 0

        @decorator
        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        with pytest.raises(ConnectionError, match="Persistent failure"):
            always_fails()

        # Initial + 2 retries = 3 total attempts
        assert call_count == 3

    @pytest.mark.requirement("FR-033")
    def test_decorator_logs_retry_attempts(self) -> None:
        """Test decorator logs retry attempts."""
        decorator = create_retry_decorator(
            max_retries=2,
            min_wait_seconds=0.01,
            max_wait_seconds=0.1,
        )

        call_count = 0

        @decorator
        def fails_then_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First attempt fails")
            return "success"

        with patch("floe_catalog_polaris.retry.logger") as mock_logger:
            result = fails_then_succeeds()

            assert result == "success"
            # Should have logged at least one retry warning
            mock_logger.warning.assert_called()


class TestWithRetry:
    """Tests for with_retry function."""

    @pytest.mark.requirement("FR-033")
    def test_wraps_function_with_retry(self) -> None:
        """Test with_retry wraps function correctly."""
        call_count = 0

        def sometimes_fails() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Transient")
            return "done"

        wrapped = with_retry(
            sometimes_fails,
            max_retries=3,
            min_wait_seconds=0.01,
        )

        result = wrapped()
        assert result == "done"
        assert call_count == 2

    @pytest.mark.requirement("FR-033")
    def test_with_retry_respects_max_retries(self) -> None:
        """Test with_retry respects max_retries parameter."""
        call_count = 0

        def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise OSError("Network error")

        wrapped = with_retry(
            always_fails,
            max_retries=1,  # Only 1 retry
            min_wait_seconds=0.01,
        )

        with pytest.raises(OSError):
            wrapped()

        # Initial + 1 retry = 2 calls
        assert call_count == 2


class TestRetryableExceptions:
    """Tests for retryable exception configuration."""

    @pytest.mark.requirement("FR-033")
    def test_connection_error_is_retryable(self) -> None:
        """Test ConnectionError is in retryable exceptions."""
        assert ConnectionError in RETRYABLE_EXCEPTIONS

    @pytest.mark.requirement("FR-033")
    def test_timeout_error_is_retryable(self) -> None:
        """Test TimeoutError is in retryable exceptions."""
        assert TimeoutError in RETRYABLE_EXCEPTIONS

    @pytest.mark.requirement("FR-033")
    def test_os_error_is_retryable(self) -> None:
        """Test OSError is in retryable exceptions."""
        assert OSError in RETRYABLE_EXCEPTIONS


class TestConnectWithRetry:
    """Integration tests for connect() with retry logic."""

    @pytest.mark.requirement("FR-033")
    def test_connect_retries_on_transient_failure(self) -> None:
        """Test connect() retries on transient connection failures."""
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
            max_retries=2,
        )
        plugin = PolarisCatalogPlugin(config=config)

        call_count = 0
        mock_catalog = MagicMock()

        def load_with_failures(*args: str, **kwargs: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Server temporarily unavailable")
            return mock_catalog

        with patch(
            "floe_catalog_polaris.plugin.load_catalog",
            side_effect=load_with_failures,
        ):
            result = plugin.connect({})

            assert result == mock_catalog
            assert call_count == 2  # 1 failure + 1 success

    @pytest.mark.requirement("FR-033")
    def test_connect_uses_config_max_retries(self) -> None:
        """Test connect() uses max_retries from config."""
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
            max_retries=1,  # Only 1 retry
        )
        plugin = PolarisCatalogPlugin(config=config)

        call_count = 0

        def always_fails(*args: str, **kwargs: str) -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        with patch(
            "floe_catalog_polaris.plugin.load_catalog",
            side_effect=always_fails,
        ):
            with pytest.raises(ConnectionError):
                plugin.connect({})

            # Initial + 1 retry = 2 calls
            assert call_count == 2
