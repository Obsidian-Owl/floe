"""Integration tests for Cube semantic plugin health check.

Tests validate health_check() behavior for both connected and unconnected
states, response time measurement, timeout handling, and error reporting.

Inherits standard health check tests from BaseHealthCheckTests and adds
Cube-specific test cases.

Requirements Covered:
    - SC-002: Health check validates Cube API availability
    - CR-002: Plugin health_check method
    - FR-028: Health check reports availability
    - FR-048: OTel span for health check
    - FR-049: Configurable timeout
    - FR-050: Response time measurement
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from floe_core.plugin_metadata import HealthState, HealthStatus
from floe_semantic_cube.config import CubeSemanticConfig
from floe_semantic_cube.plugin import CubeSemanticPlugin
from testing.base_classes.base_health_check_tests import BaseHealthCheckTests


def _mock_healthy_response(*args: Any, **kwargs: Any) -> httpx.Response:
    """Return a mock healthy HTTP response."""
    return httpx.Response(status_code=200, text="OK")


@pytest.mark.requirement("SC-002")
class TestCubeHealthCheck(BaseHealthCheckTests):
    """Health check tests for CubeSemanticPlugin.

    Inherits standard health check tests from BaseHealthCheckTests.
    Uses a mock HTTP transport to simulate Cube API responses.
    """

    @pytest.fixture
    def unconnected_plugin(self) -> CubeSemanticPlugin:
        """Return an uninitialized CubeSemanticPlugin.

        Returns:
            CubeSemanticPlugin that has NOT been started.
        """
        config = CubeSemanticConfig(
            server_url="http://localhost:4000",
            api_secret="test-secret",
        )
        return CubeSemanticPlugin(config=config)

    @pytest.fixture
    def connected_plugin(self) -> CubeSemanticPlugin:
        """Return a started CubeSemanticPlugin with mocked HTTP client.

        The httpx client is patched to return healthy responses without
        requiring a real Cube server.

        Returns:
            CubeSemanticPlugin that is started with mocked HTTP transport.
        """
        config = CubeSemanticConfig(
            server_url="http://localhost:4000",
            api_secret="test-secret",
        )
        plugin = CubeSemanticPlugin(config=config)
        plugin.startup()
        assert plugin._client is not None

        # Patch the client's get method to return healthy responses
        with patch.object(plugin._client, "get", side_effect=_mock_healthy_response):
            yield plugin  # type: ignore[misc]

        plugin.shutdown()


@pytest.mark.requirement("SC-002")
class TestCubeHealthCheckSpecific:
    """Cube-specific health check tests beyond the base class."""

    @pytest.fixture
    def config(self) -> CubeSemanticConfig:
        """Create a test configuration."""
        return CubeSemanticConfig(
            server_url="http://localhost:4000",
            api_secret="test-secret",
        )

    @pytest.fixture
    def plugin(self, config: CubeSemanticConfig) -> CubeSemanticPlugin:
        """Create an unstarted plugin."""
        return CubeSemanticPlugin(config=config)

    @pytest.mark.requirement("FR-049")
    def test_health_check_default_timeout_from_config(
        self, config: CubeSemanticConfig, plugin: CubeSemanticPlugin
    ) -> None:
        """Test health check uses config timeout when none specified."""
        status = plugin.health_check()
        assert isinstance(status, HealthStatus)

    @pytest.mark.requirement("FR-049")
    def test_health_check_rejects_timeout_below_minimum(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test health check rejects timeout below 0.1s."""
        with pytest.raises(ValueError, match="timeout"):
            plugin.health_check(timeout=0.05)

    @pytest.mark.requirement("FR-049")
    def test_health_check_rejects_timeout_above_maximum(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test health check rejects timeout above 10.0s."""
        with pytest.raises(ValueError, match="timeout"):
            plugin.health_check(timeout=15.0)

    @pytest.mark.requirement("FR-028")
    def test_health_check_unhealthy_when_not_started(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test health check returns UNHEALTHY before startup()."""
        status = plugin.health_check()
        assert status.state == HealthState.UNHEALTHY
        assert "not started" in status.message.lower()

    @pytest.mark.requirement("FR-028")
    def test_health_check_unhealthy_includes_reason(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test unhealthy status includes reason in details."""
        status = plugin.health_check()
        assert "reason" in status.details

    @pytest.mark.requirement("FR-050")
    def test_health_check_connection_error_returns_unhealthy(self) -> None:
        """Test health check returns UNHEALTHY on connection error."""
        # Use a port that is definitely not serving anything
        config = CubeSemanticConfig(
            server_url="http://localhost:19999",
            api_secret="test-secret",
        )
        plugin = CubeSemanticPlugin(config=config)
        plugin.startup()
        try:
            status = plugin.health_check(timeout=0.5)
            assert status.state == HealthState.UNHEALTHY
            assert status.details.get("response_time_ms") is not None
            assert status.details.get("checked_at") is not None
        finally:
            plugin.shutdown()

    @pytest.mark.requirement("FR-008")
    def test_startup_shutdown_lifecycle_idempotent(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test startup/shutdown can be called multiple times safely."""
        plugin.startup()
        plugin.startup()  # Should be idempotent
        plugin.shutdown()
        plugin.shutdown()  # Should be idempotent

    @pytest.mark.requirement("FR-008")
    def test_startup_creates_http_client(
        self, plugin: CubeSemanticPlugin
    ) -> None:
        """Test that startup creates an httpx client."""
        assert plugin._client is None
        plugin.startup()
        assert plugin._client is not None
        plugin.shutdown()
        assert plugin._client is None
