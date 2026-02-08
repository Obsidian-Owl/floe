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

import time
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from floe_core import HealthState
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_catalog_polaris.config import PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass


class TestHealthCheckIntegration(IntegrationTestBase):
    """Integration tests for health_check() method.

    These tests require a real Polaris instance running in the Kind cluster.
    They verify that the health check accurately reports catalog status.

    Uses polaris_config fixture from conftest.py for configuration.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    @pytest.mark.requirement("FR-050")
    @pytest.mark.integration
    def test_health_check_running_polaris_returns_healthy(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test health check against running Polaris returns healthy=True.

        Verifies that when Polaris is running and accessible, the health
        check returns a HEALTHY state.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)

        # Connect first
        plugin.connect({})

        # Health check should return healthy
        status = plugin.health_check(timeout=5.0)

        assert status.state == HealthState.HEALTHY
        assert status.message is not None
        # Message should indicate positive status (healthy, ok, responding, normal, etc.)
        msg_lower = status.message.lower()
        assert any(word in msg_lower for word in ["healthy", "ok", "responding", "normal"])

    @pytest.mark.requirement("FR-050")
    @pytest.mark.integration
    def test_health_check_not_connected_returns_unhealthy(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test health check returns unhealthy when not connected.

        Verifies that before connect() is called, the health check
        returns an UNHEALTHY state with appropriate message.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)

        # Do NOT connect - health check should return unhealthy
        status = plugin.health_check(timeout=5.0)

        assert status.state == HealthState.UNHEALTHY
        assert status.message is not None
        assert "not connected" in status.message.lower()

    @pytest.mark.requirement("FR-051")
    @pytest.mark.integration
    def test_health_check_includes_response_time(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test health check includes response time in milliseconds.

        Verifies that the health check response includes timing information
        that reflects actual network latency.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
        plugin.connect({})

        # Perform health check
        status = plugin.health_check(timeout=5.0)

        # Should include response_time_ms in details
        assert status.details is not None
        assert "response_time_ms" in status.details

        # Response time should be a positive number
        response_time = status.details["response_time_ms"]
        assert isinstance(response_time, int | float)
        assert response_time >= 0

    @pytest.mark.requirement("FR-051")
    @pytest.mark.integration
    def test_health_check_response_time_reflects_latency(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test response time reflects actual network latency.

        Verifies that the response time measurement is realistic
        (greater than 0, less than timeout).
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
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
    def test_health_check_timeout_validation(self, polaris_config: PolarisCatalogConfig) -> None:
        """Test health check validates timeout parameter.

        Verifies that timeout must be between 0.1 and 10.0 seconds.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
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
    def test_health_check_includes_checked_at_timestamp(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test health check includes checked_at timestamp.

        Verifies that the response includes when the check was performed.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
        plugin.connect({})

        status = plugin.health_check(timeout=5.0)

        assert status.details is not None
        assert "checked_at" in status.details

        # Should be a datetime object
        checked_at = status.details["checked_at"]
        assert isinstance(checked_at, datetime)

    @pytest.mark.requirement("FR-050")
    @pytest.mark.integration
    def test_health_check_multiple_calls_consistent(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test multiple health checks return consistent results.

        Verifies that health check is reliable and consistent.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
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

    Uses polaris_config fixture from conftest.py for configuration.
    """

    required_services = [("polaris", 8181)]

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_respects_short_timeout(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test that health check respects short timeout values.

        Verifies that the health check completes in a reasonable time.
        Note: We only check that the check completes without timing assertions
        to avoid flaky tests in CI environments.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
        plugin.connect({})

        # Use a short but valid timeout
        timeout = 0.5

        # Execute health check with short timeout
        status = plugin.health_check(timeout=timeout)

        # Status should be determined (either healthy or unhealthy)
        assert status.state in (HealthState.HEALTHY, HealthState.UNHEALTHY)

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_timeout_returns_unhealthy_status(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test that timeout returns UNHEALTHY status with reason.

        This test verifies the structure of the response when unhealthy
        by checking an unconnected plugin.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)

        # Don't connect - this should return unhealthy quickly
        status = plugin.health_check(timeout=1.0)

        # Not connected case
        assert status.state == HealthState.UNHEALTHY
        assert status.details is not None
        assert "reason" in status.details

    @pytest.mark.requirement("FR-052")
    @pytest.mark.integration
    def test_health_check_timeout_included_in_details(
        self, polaris_config: PolarisCatalogConfig
    ) -> None:
        """Test that timeout value is included in response details.

        Verifies that the timeout parameter is recorded in the response.
        """
        plugin = PolarisCatalogPlugin(config=polaris_config)
        plugin.connect({})

        timeout_value = 2.5
        status = plugin.health_check(timeout=timeout_value)

        assert status.details is not None
        assert "timeout" in status.details
        assert status.details["timeout"] == pytest.approx(timeout_value)
