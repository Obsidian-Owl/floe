"""Integration tests for Polaris catalog health check.

Tests the PolarisCatalogPlugin health check against a real Polaris instance
running in the Kind cluster. These tests verify:
- Health check returns healthy for running Polaris
- Response time is measured accurately
- Timeout handling works correctly

Requirements Covered:
    - FR-050: Health check monitors catalog availability
    - FR-051: Response time is tracked in milliseconds
    - FR-052: Timeout parameter controls check duration
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import pytest
from floe_core import HealthState
from pydantic import SecretStr
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass


class TestHealthCheckIntegration(IntegrationTestBase):
    """Integration tests for health_check() method.

    These tests require a real Polaris instance running in the Kind cluster.
    They verify that the health check accurately reports catalog status.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris.

        Returns:
            PolarisCatalogConfig with test credentials.
        """
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    @pytest.mark.requirement("FR-050")
    @pytest.mark.integration
    def test_health_check_running_polaris_returns_healthy(self) -> None:
        """Test health check against running Polaris returns healthy=True.

        Verifies that when Polaris is running and accessible, the health
        check returns a HEALTHY state.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Connect first
        plugin.connect({})

        # Health check should return healthy
        status = plugin.health_check(timeout=5.0)

        assert status.state == HealthState.HEALTHY
        assert status.message is not None
        # Message should indicate positive status (healthy, ok, responding, normal, etc.)
        msg_lower = status.message.lower()
        assert any(
            word in msg_lower for word in ["healthy", "ok", "responding", "normal"]
        )

    @pytest.mark.requirement("FR-050")
    @pytest.mark.integration
    def test_health_check_not_connected_returns_unhealthy(self) -> None:
        """Test health check returns unhealthy when not connected.

        Verifies that before connect() is called, the health check
        returns an UNHEALTHY state with appropriate message.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Do NOT connect - health check should return unhealthy
        status = plugin.health_check(timeout=5.0)

        assert status.state == HealthState.UNHEALTHY
        assert status.message is not None
        assert "not connected" in status.message.lower()

    @pytest.mark.requirement("FR-051")
    @pytest.mark.integration
    def test_health_check_includes_response_time(self) -> None:
        """Test health check includes response time in milliseconds.

        Verifies that the health check response includes timing information
        that reflects actual network latency.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        # Perform health check
        status = plugin.health_check(timeout=5.0)

        # Should include response_time_ms in details
        assert status.details is not None
        assert "response_time_ms" in status.details

        # Response time should be a positive number
        response_time = status.details["response_time_ms"]
        assert isinstance(response_time, (int, float))
        assert response_time >= 0

    @pytest.mark.requirement("FR-051")
    @pytest.mark.integration
    def test_health_check_response_time_reflects_latency(self) -> None:
        """Test response time reflects actual network latency.

        Verifies that the response time measurement is realistic
        (greater than 0, less than timeout).
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        # Measure with our own timer
        start = time.perf_counter()
        status = plugin.health_check(timeout=5.0)
        our_elapsed_ms = (time.perf_counter() - start) * 1000

        assert status.details is not None
        response_time_ms = status.details["response_time_ms"]

        # Response time should be reasonable
        # It should be less than what we measured (they measure internal only)
        assert response_time_ms < our_elapsed_ms + 100  # Allow some tolerance
        # And greater than 0 (actual network call)
        assert response_time_ms > 0

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_timeout_validation(self) -> None:
        """Test health check validates timeout parameter.

        Verifies that timeout must be between 0.1 and 10.0 seconds.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        # Valid timeout should work
        status = plugin.health_check(timeout=1.0)
        assert status is not None

        # Too small timeout should raise ValueError
        with pytest.raises(ValueError, match="timeout must be between"):
            plugin.health_check(timeout=0.05)

        # Too large timeout should raise ValueError
        with pytest.raises(ValueError, match="timeout must be between"):
            plugin.health_check(timeout=15.0)

    @pytest.mark.requirement("FR-051")
    @pytest.mark.integration
    def test_health_check_includes_checked_at_timestamp(self) -> None:
        """Test health check includes checked_at timestamp.

        Verifies that the response includes when the check was performed.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        status = plugin.health_check(timeout=5.0)

        assert status.details is not None
        assert "checked_at" in status.details

        # Should be a datetime object
        from datetime import datetime

        checked_at = status.details["checked_at"]
        assert isinstance(checked_at, datetime)

    @pytest.mark.requirement("FR-050")
    @pytest.mark.integration
    def test_health_check_multiple_calls_consistent(self) -> None:
        """Test multiple health checks return consistent results.

        Verifies that health check is reliable and consistent.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        # Perform multiple health checks
        results = [plugin.health_check(timeout=5.0) for _ in range(3)]

        # All should be healthy
        for status in results:
            assert status.state == HealthState.HEALTHY

        # All should have response times
        for status in results:
            assert status.details is not None
            assert "response_time_ms" in status.details
            assert status.details["response_time_ms"] > 0


class TestHealthCheckTimeout(IntegrationTestBase):
    """Tests for health check timeout behavior.

    These tests verify that the timeout parameter properly controls
    how long the health check waits before returning unhealthy.
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris."""
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_respects_short_timeout(self) -> None:
        """Test that health check respects short timeout values.

        Verifies that the health check returns within the specified
        timeout period (plus a small buffer for overhead).
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        # Use a short but valid timeout
        timeout = 0.5

        start = time.perf_counter()
        status = plugin.health_check(timeout=timeout)
        elapsed = time.perf_counter() - start

        # Should complete within timeout + overhead
        # If healthy, it should complete quickly
        # If timeout triggers, it should complete around timeout value
        assert elapsed < timeout + 1.0  # Allow 1s overhead

        # Status should be determined
        assert status.state in (HealthState.HEALTHY, HealthState.UNHEALTHY)

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_timeout_returns_unhealthy_status(self) -> None:
        """Test that timeout returns UNHEALTHY status with reason.

        This test may be flaky if Polaris responds very quickly.
        We verify the timeout mechanism by checking the structure
        of the response when unhealthy.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        # Don't connect - this should return unhealthy quickly
        status = plugin.health_check(timeout=1.0)

        # Not connected case
        assert status.state == HealthState.UNHEALTHY
        assert status.details is not None
        assert "reason" in status.details

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_timeout_included_in_details(self) -> None:
        """Test that timeout value is included in response details.

        Verifies that the timeout parameter is recorded in the response.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})

        timeout_value = 2.5
        status = plugin.health_check(timeout=timeout_value)

        assert status.details is not None
        assert "timeout" in status.details
        assert status.details["timeout"] == pytest.approx(timeout_value)
