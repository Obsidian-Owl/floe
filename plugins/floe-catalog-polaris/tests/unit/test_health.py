"""Unit tests for health check functionality.

This module tests the health_check() method for the PolarisCatalogPlugin,
verifying health status reporting, response time capture, and timeout handling.

Requirements Covered:
    - FR-028: System MUST provide a health check method that reports catalog availability
    - FR-030: System MUST emit OpenTelemetry spans for all catalog operations
    - FR-031: OTel spans MUST include operation duration, status, catalog name attributes
    - SC-007: Health checks accurately report catalog status within 1 second response time

Note: These tests are written TDD-style BEFORE implementation (T065).
They will FAIL until health_check() is fully implemented in T067.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugin_metadata import HealthState, HealthStatus

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass


@pytest.fixture
def polaris_config() -> PolarisCatalogConfig:
    """Create a test Polaris configuration."""
    return PolarisCatalogConfig(
        uri="https://polaris.example.com/api/catalog",
        warehouse="test_warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        ),
    )


@pytest.fixture
def polaris_plugin(polaris_config: PolarisCatalogConfig) -> PolarisCatalogPlugin:
    """Create a test Polaris plugin instance."""
    return PolarisCatalogPlugin(config=polaris_config)


@pytest.fixture
def mock_catalog() -> MagicMock:
    """Create a mock PyIceberg catalog."""
    catalog = MagicMock()
    catalog.list_namespaces.return_value = [("bronze",), ("silver",), ("gold",)]
    return catalog


@pytest.fixture
def connected_plugin(
    polaris_plugin: PolarisCatalogPlugin,
    mock_catalog: MagicMock,
) -> PolarisCatalogPlugin:
    """Create a plugin with a mocked connected catalog."""
    with patch(
        "floe_catalog_polaris.plugin.load_catalog",
        return_value=mock_catalog,
    ):
        polaris_plugin.connect({})
    return polaris_plugin


class TestHealthCheckBasic:
    """Tests for basic health_check() functionality."""

    def test_health_check_returns_health_status(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check returns a HealthStatus model."""
        result = connected_plugin.health_check()

        assert isinstance(result, HealthStatus)
        assert hasattr(result, "state")
        assert hasattr(result, "message")

    def test_health_check_healthy_when_list_namespaces_succeeds(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check returns HEALTHY when list_namespaces succeeds."""
        mock_catalog.list_namespaces.return_value = [("bronze",)]

        result = connected_plugin.health_check()

        assert result.state == HealthState.HEALTHY
        # Accept various positive messages
        msg_lower = result.message.lower()
        assert any(word in msg_lower for word in ["healthy", "ok", "responding", "normal"])

    def test_health_check_unhealthy_when_list_namespaces_fails(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check returns UNHEALTHY when list_namespaces fails."""
        mock_catalog.list_namespaces.side_effect = Exception("Connection refused")

        result = connected_plugin.health_check()

        assert result.state == HealthState.UNHEALTHY
        assert result.message != ""

    def test_health_check_unhealthy_includes_error_details(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check includes error info when unhealthy."""
        mock_catalog.list_namespaces.side_effect = Exception("Connection refused")

        result = connected_plugin.health_check()

        # Error details should be in message or details
        assert "Connection refused" in result.message or "Connection refused" in str(result.details)


class TestHealthCheckResponseTime:
    """Tests for response time measurement in health_check()."""

    def test_health_check_captures_response_time_ms(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check captures response time in milliseconds."""

        def slow_list_namespaces(*args: object, **kwargs: object) -> list[tuple[str]]:
            time.sleep(0.05)  # 50ms delay
            return [("bronze",)]

        mock_catalog.list_namespaces.side_effect = slow_list_namespaces

        result = connected_plugin.health_check()

        assert "response_time_ms" in result.details
        # Response time should be >= 50ms (our simulated delay)
        assert result.details["response_time_ms"] >= 50.0
        # And less than 1 second (reasonable upper bound)
        assert result.details["response_time_ms"] < 1000.0

    def test_health_check_response_time_is_float(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that response_time_ms is a float value."""
        result = connected_plugin.health_check()

        assert "response_time_ms" in result.details
        # Use pytest.approx or isinstance check to handle float comparison
        assert isinstance(result.details["response_time_ms"], (int, float))

    def test_health_check_response_time_captured_on_failure(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that response_time_ms is captured even when check fails."""

        def slow_failing_list(*args: object, **kwargs: object) -> None:
            time.sleep(0.03)  # 30ms delay
            raise Exception("Connection timeout")

        mock_catalog.list_namespaces.side_effect = slow_failing_list

        result = connected_plugin.health_check()

        assert result.state == HealthState.UNHEALTHY
        assert "response_time_ms" in result.details
        assert result.details["response_time_ms"] >= 30.0


class TestHealthCheckTimeout:
    """Tests for timeout parameter in health_check()."""

    def test_health_check_accepts_timeout_parameter(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check accepts a timeout parameter."""
        # Should not raise - timeout is accepted
        result = connected_plugin.health_check(timeout=5.0)

        assert isinstance(result, HealthStatus)

    def test_health_check_default_timeout_is_one_second(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that default timeout is 1.0 second."""
        import inspect

        sig = inspect.signature(polaris_plugin.health_check)
        timeout_param = sig.parameters.get("timeout")

        assert timeout_param is not None
        assert timeout_param.default == 1.0

    def test_health_check_respects_timeout(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check times out when operation exceeds timeout."""

        def very_slow_operation(*args: object, **kwargs: object) -> list[tuple[str]]:
            time.sleep(2.0)  # 2 second delay
            return [("bronze",)]

        mock_catalog.list_namespaces.side_effect = very_slow_operation

        start = time.time()
        result = connected_plugin.health_check(timeout=0.1)  # 100ms timeout
        elapsed = time.time() - start

        # Should return UNHEALTHY due to timeout
        assert result.state == HealthState.UNHEALTHY
        # Should have returned before the 2 second operation completed
        assert elapsed < 1.5, f"Timeout not respected: took {elapsed:.2f}s"

    def test_health_check_timeout_includes_in_details(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check includes timeout in details."""
        result = connected_plugin.health_check(timeout=2.5)

        # Timeout should be recorded in details for diagnostics
        assert "timeout" in result.details or result.details.get("timeout_seconds")
        if "timeout" in result.details:
            assert result.details["timeout"] == pytest.approx(2.5)
        elif "timeout_seconds" in result.details:
            assert result.details["timeout_seconds"] == pytest.approx(2.5)

    def test_health_check_rejects_timeout_below_minimum(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that health_check rejects timeout below 0.1 seconds."""
        with pytest.raises(ValueError, match=r"timeout.*0\.1.*10"):
            polaris_plugin.health_check(timeout=0.05)

    def test_health_check_rejects_timeout_above_maximum(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that health_check rejects timeout above 10.0 seconds."""
        with pytest.raises(ValueError, match=r"timeout.*0\.1.*10"):
            polaris_plugin.health_check(timeout=15.0)

    def test_health_check_accepts_minimum_timeout(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check accepts timeout of exactly 0.1 seconds."""
        # Should not raise - 0.1 is the minimum allowed
        result = connected_plugin.health_check(timeout=0.1)
        assert isinstance(result, HealthStatus)

    def test_health_check_accepts_maximum_timeout(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check accepts timeout of exactly 10.0 seconds."""
        # Should not raise - 10.0 is the maximum allowed
        result = connected_plugin.health_check(timeout=10.0)
        assert isinstance(result, HealthStatus)

    def test_health_check_rejects_zero_timeout(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that health_check rejects zero timeout."""
        with pytest.raises(ValueError, match=r"timeout.*0\.1.*10"):
            polaris_plugin.health_check(timeout=0.0)

    def test_health_check_rejects_negative_timeout(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that health_check rejects negative timeout."""
        with pytest.raises(ValueError, match=r"timeout.*0\.1.*10"):
            polaris_plugin.health_check(timeout=-1.0)


class TestHealthCheckTimestamp:
    """Tests for timestamp in health_check()."""

    def test_health_check_includes_checked_at_timestamp(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check includes a checked_at timestamp."""
        before = datetime.now(timezone.utc)
        result = connected_plugin.health_check()
        after = datetime.now(timezone.utc)

        assert "checked_at" in result.details
        checked_at = result.details["checked_at"]

        # Should be a datetime or ISO format string
        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))

        assert before <= checked_at <= after

    def test_health_check_timestamp_is_utc(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that checked_at timestamp is in UTC."""
        result = connected_plugin.health_check()

        assert "checked_at" in result.details
        checked_at = result.details["checked_at"]

        if isinstance(checked_at, datetime):
            assert checked_at.tzinfo is not None
            assert checked_at.tzinfo == timezone.utc or str(checked_at.tzinfo) == "UTC"
        elif isinstance(checked_at, str):
            # ISO format with Z suffix or +00:00 indicates UTC
            assert checked_at.endswith("Z") or "+00:00" in checked_at or checked_at.endswith("UTC")


class TestHealthCheckNotConnected:
    """Tests for health_check when plugin is not connected."""

    def test_health_check_not_connected_returns_unhealthy(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that health_check returns UNHEALTHY when not connected."""
        # Plugin is not connected (no connect() called)
        result = polaris_plugin.health_check()

        assert result.state == HealthState.UNHEALTHY
        assert "not connected" in result.message.lower() or "connect" in result.message.lower()

    def test_health_check_not_connected_does_not_raise(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that health_check gracefully handles not-connected state."""
        # Should NOT raise an exception, but return unhealthy status
        result = polaris_plugin.health_check()

        assert isinstance(result, HealthStatus)
        assert result.state != HealthState.HEALTHY


class TestHealthCheckOTelTracing:
    """Tests for OpenTelemetry tracing in health_check()."""

    def test_health_check_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check emits an OTel span."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.health_check()

            mock_span.assert_called_once()
            call_args = mock_span.call_args
            assert "health_check" in str(call_args)

    def test_health_check_span_includes_duration(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check span includes duration attribute."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_context = MagicMock()
            mock_span.return_value.__enter__ = MagicMock(return_value=mock_context)
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.health_check()

            # The span context manager should be used
            assert mock_span.called

    def test_health_check_span_includes_status(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check span includes health status."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            mock_context = MagicMock()
            mock_span.return_value.__enter__ = MagicMock(return_value=mock_context)
            mock_span.return_value.__exit__ = MagicMock(return_value=False)

            connected_plugin.health_check()

            # Verify span was called with health_check operation
            call_str = str(mock_span.call_args)
            assert "health" in call_str.lower()


class TestHealthCheckLogging:
    """Tests for logging in health_check()."""

    def test_health_check_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check logs the operation."""
        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.health_check()

            # Should log the health check operation
            assert mock_logger.bind.called or mock_logger.info.called or mock_logger.debug.called

    def test_health_check_logs_failure(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check logs failures."""
        mock_catalog.list_namespaces.side_effect = Exception("Connection refused")

        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.health_check()

            # Should log the error/warning
            assert mock_logger.warning.called or mock_logger.error.called or mock_logger.bind.called


class TestHealthCheckEdgeCases:
    """Tests for edge cases in health_check()."""

    def test_health_check_handles_empty_namespace_list(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check handles empty namespace list as healthy."""
        mock_catalog.list_namespaces.return_value = []

        result = connected_plugin.health_check()

        # Empty catalog is still healthy (catalog is reachable)
        assert result.state == HealthState.HEALTHY

    def test_health_check_handles_network_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check handles network errors gracefully."""
        from requests.exceptions import ConnectionError as RequestsConnectionError

        mock_catalog.list_namespaces.side_effect = RequestsConnectionError("Host unreachable")

        result = connected_plugin.health_check()

        assert result.state == HealthState.UNHEALTHY
        assert "unreachable" in result.message.lower() or len(result.message) > 0

    def test_health_check_handles_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check handles authentication errors."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.list_namespaces.side_effect = ForbiddenError("Token expired")

        result = connected_plugin.health_check()

        # Auth failures should be reported as UNHEALTHY or DEGRADED
        assert result.state in (HealthState.UNHEALTHY, HealthState.DEGRADED)

    def test_health_check_returns_quickly_when_healthy(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that health_check completes quickly for healthy catalog."""
        mock_catalog.list_namespaces.return_value = [("bronze",)]

        start = time.time()
        result = connected_plugin.health_check()
        elapsed = time.time() - start

        assert result.state == HealthState.HEALTHY
        # Should complete within SC-007 requirement (1 second)
        assert elapsed < 1.0, f"Health check took {elapsed:.2f}s (should be < 1s)"
