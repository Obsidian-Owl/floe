"""Unit tests for polling utilities.

Tests for testing.fixtures.polling module including PollingConfig,
wait_for_condition(), and wait_for_service().
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from testing.fixtures.polling import (
    PollingConfig,
    PollingTimeoutError,
    wait_for_condition,
    wait_for_service,
)


class TestPollingConfig:
    """Tests for PollingConfig Pydantic model."""

    @pytest.mark.requirement("9c-FR-015")
    def test_default_values(self) -> None:
        """Test PollingConfig has sensible defaults."""
        config = PollingConfig()
        assert config.timeout == pytest.approx(30.0)
        assert config.interval == pytest.approx(0.5)
        assert config.description == "condition"

    @pytest.mark.requirement("9c-FR-015")
    def test_custom_values(self) -> None:
        """Test PollingConfig accepts custom values."""
        config = PollingConfig(timeout=60.0, interval=1.0, description="service ready")
        assert config.timeout == pytest.approx(60.0)
        assert config.interval == pytest.approx(1.0)
        assert config.description == "service ready"

    @pytest.mark.requirement("9c-FR-015")
    def test_frozen_model(self) -> None:
        """Test PollingConfig is immutable."""
        config = PollingConfig()
        with pytest.raises(ValidationError):
            config.timeout = 100.0

    @pytest.mark.requirement("9c-FR-015")
    def test_validation_timeout_non_negative(self) -> None:
        """Test timeout must be non-negative."""
        with pytest.raises(ValueError):
            PollingConfig(timeout=-1.0)

    @pytest.mark.requirement("9c-FR-015")
    def test_validation_interval_minimum(self) -> None:
        """Test interval has minimum value."""
        with pytest.raises(ValueError):
            PollingConfig(interval=0.05)  # Below 0.1 minimum


class TestWaitForCondition:
    """Tests for wait_for_condition() function."""

    @pytest.mark.requirement("9c-FR-015")
    def test_returns_immediately_when_condition_true(self) -> None:
        """Test wait_for_condition returns immediately when condition is True."""
        call_count = 0

        def condition() -> bool:
            nonlocal call_count
            call_count += 1
            return True

        result = wait_for_condition(condition, timeout=5.0)
        assert result is True
        assert call_count == 1

    @pytest.mark.requirement("9c-FR-015")
    def test_polls_until_condition_true(self) -> None:
        """Test wait_for_condition polls until condition becomes True."""
        call_count = 0

        def condition() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count >= 3

        result = wait_for_condition(condition, timeout=5.0, interval=0.1)
        assert result is True
        assert call_count == 3

    @pytest.mark.requirement("9c-FR-015")
    def test_raises_timeout_error(self) -> None:
        """Test wait_for_condition raises PollingTimeoutError on timeout."""
        with pytest.raises(PollingTimeoutError) as exc_info:
            wait_for_condition(
                lambda: False,
                timeout=0.3,
                interval=0.1,
                description="never true",
            )

        assert "never true" in str(exc_info.value)
        assert exc_info.value.timeout == pytest.approx(0.3)

    @pytest.mark.requirement("9c-FR-015")
    def test_no_raise_on_timeout_returns_false(self) -> None:
        """Test wait_for_condition returns False when raise_on_timeout=False."""
        result = wait_for_condition(
            lambda: False,
            timeout=0.2,
            interval=0.1,
            raise_on_timeout=False,
        )
        assert result is False

    @pytest.mark.requirement("9c-FR-015")
    def test_captures_last_error(self) -> None:
        """Test timeout error includes last exception from condition."""

        def failing_condition() -> bool:
            raise ValueError("Test error")

        with pytest.raises(PollingTimeoutError) as exc_info:
            wait_for_condition(
                failing_condition,
                timeout=0.2,
                interval=0.1,
            )

        assert exc_info.value.last_error is not None
        assert "Test error" in str(exc_info.value.last_error)


class TestWaitForService:
    """Tests for wait_for_service() function."""

    @pytest.mark.requirement("9c-FR-016")
    def test_returns_true_when_service_ready(self) -> None:
        """Test wait_for_service returns True when service accepts connections."""
        with patch("testing.fixtures.polling._tcp_check", return_value=True):
            result = wait_for_service("polaris", 8181, timeout=5.0)
            assert result is True

    @pytest.mark.requirement("9c-FR-016")
    def test_raises_timeout_when_service_unavailable(self) -> None:
        """Test wait_for_service raises PollingTimeoutError when service unavailable."""
        with patch("testing.fixtures.polling._tcp_check", return_value=False):
            with pytest.raises(PollingTimeoutError) as exc_info:
                wait_for_service("polaris", 8181, timeout=0.3)

            assert "polaris:8181" in str(exc_info.value)
            assert "floe-test" in str(exc_info.value)

    @pytest.mark.requirement("9c-FR-016")
    def test_uses_custom_namespace(self) -> None:
        """Test wait_for_service uses custom namespace in service discovery."""
        with patch("testing.fixtures.polling._tcp_check") as mock_check:
            mock_check.return_value = True
            wait_for_service("postgres", 5432, namespace="custom-ns")

            # Verify it was called with the correct host
            call_args = mock_check.call_args
            assert "custom-ns" in call_args[0][0]

    @pytest.mark.requirement("9c-FR-016")
    def test_uses_polling_config(self) -> None:
        """Test wait_for_service respects PollingConfig."""
        config = PollingConfig(timeout=10.0, interval=2.0)

        with patch("testing.fixtures.polling._tcp_check", return_value=True):
            result = wait_for_service("minio", 9000, config=config)
            assert result is True

    @pytest.mark.requirement("9c-FR-016")
    def test_no_raise_returns_false(self) -> None:
        """Test wait_for_service returns False when raise_on_timeout=False."""
        with patch("testing.fixtures.polling._tcp_check", return_value=False):
            result = wait_for_service("unavailable", 9999, timeout=0.2, raise_on_timeout=False)
            assert result is False


class TestTcpCheck:
    """Tests for _tcp_check internal function."""

    @pytest.mark.requirement("9c-FR-016")
    def test_successful_connection(self) -> None:
        """Test _tcp_check returns True for successful connection."""
        from testing.fixtures.polling import _tcp_check

        mock_socket = MagicMock()
        with patch("socket.create_connection", return_value=mock_socket):
            result = _tcp_check("localhost", 8080, timeout=5.0)
            assert result is True

    @pytest.mark.requirement("9c-FR-016")
    def test_failed_connection(self) -> None:
        """Test _tcp_check returns False for failed connection."""
        from testing.fixtures.polling import _tcp_check

        with patch("socket.create_connection", side_effect=OSError("Connection refused")):
            result = _tcp_check("localhost", 8080, timeout=5.0)
            assert result is False
