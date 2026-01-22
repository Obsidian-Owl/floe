"""Base class for plugin health check tests.

This module provides reusable test cases for validating plugin health_check()
functionality. Plugin test files can inherit from this class to get standard
health check tests without duplicating code.

Task ID: T077
Phase: 10 - US8 (Reduce Test Duplication)
User Story: US8 - Test Duplication Reduction

Requirements tested:
    FR-028: System MUST provide a health check method that reports availability
    CR-002: Plugin health_check method
    SC-007: Health checks accurately report status within 1 second response time

Example:
    from testing.base_classes.base_health_check_tests import BaseHealthCheckTests

    class TestMyPluginHealthCheck(BaseHealthCheckTests):
        @pytest.fixture
        def unconnected_plugin(self):
            return MyPlugin(config=MyConfig())

        @pytest.fixture
        def connected_plugin(self, unconnected_plugin):
            unconnected_plugin.startup()
            yield unconnected_plugin
            unconnected_plugin.shutdown()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


class BaseHealthCheckTests(ABC):
    """Base class providing reusable health check test cases.

    Subclasses must define:
        - unconnected_plugin fixture: Returns an uninitialized plugin instance
        - connected_plugin fixture: Returns an initialized/connected plugin

    Provides standard tests for:
        - HealthStatus return type
        - Healthy/unhealthy state reporting
        - Response time capture
        - Timeout handling
        - Timestamp inclusion
        - Unconnected state handling

    Example:
        class TestPolarisHealthCheck(BaseHealthCheckTests):
            @pytest.fixture
            def unconnected_plugin(self) -> PolarisCatalogPlugin:
                return PolarisCatalogPlugin(config=config)

            @pytest.fixture
            def connected_plugin(self, unconnected_plugin) -> PolarisCatalogPlugin:
                unconnected_plugin.connect({})
                yield unconnected_plugin
                unconnected_plugin.shutdown()
    """

    @pytest.fixture
    @abstractmethod
    def unconnected_plugin(self) -> Any:
        """Return an uninitialized/unconnected plugin instance.

        Subclasses MUST implement this fixture to provide a configured
        but NOT connected plugin instance.

        Returns:
            An unconnected plugin object.
        """
        ...

    @pytest.fixture
    @abstractmethod
    def connected_plugin(self) -> Any:
        """Return an initialized/connected plugin instance.

        Subclasses MUST implement this fixture to provide a plugin
        that is ready to perform operations.

        Returns:
            A connected plugin object.
        """
        ...

    # =========================================================================
    # Basic Health Check Tests
    # =========================================================================

    @pytest.mark.requirement("CR-002")
    def test_health_check_exists(self, unconnected_plugin: Any) -> None:
        """Test plugin has health_check method."""
        assert hasattr(unconnected_plugin, "health_check")
        assert callable(unconnected_plugin.health_check)

    @pytest.mark.requirement("CR-002")
    def test_health_check_returns_health_status(self, connected_plugin: Any) -> None:
        """Test health_check returns a HealthStatus model."""
        from floe_core.plugin_metadata import HealthStatus

        result = connected_plugin.health_check()

        assert isinstance(result, HealthStatus)
        assert hasattr(result, "state")
        assert hasattr(result, "message")

    @pytest.mark.requirement("FR-028")
    def test_health_check_reports_healthy_when_connected(
        self, connected_plugin: Any
    ) -> None:
        """Test health_check returns HEALTHY when connected and operational."""
        from floe_core.plugin_metadata import HealthState

        result = connected_plugin.health_check()

        # Connected plugins should report healthy (unless backend is down)
        assert result.state == HealthState.HEALTHY

    @pytest.mark.requirement("FR-028")
    def test_health_check_reports_unhealthy_when_not_connected(
        self, unconnected_plugin: Any
    ) -> None:
        """Test health_check returns UNHEALTHY when not connected."""
        from floe_core.plugin_metadata import HealthState

        result = unconnected_plugin.health_check()

        # Unconnected plugins should report unhealthy
        assert result.state == HealthState.UNHEALTHY

    # =========================================================================
    # Response Time Tests
    # =========================================================================

    @pytest.mark.requirement("FR-028")
    def test_health_check_includes_response_time(self, connected_plugin: Any) -> None:
        """Test health_check includes response_time_ms in details."""
        result = connected_plugin.health_check()

        assert "response_time_ms" in result.details
        # Response time should be a non-negative number
        assert isinstance(result.details["response_time_ms"], int | float)
        assert result.details["response_time_ms"] >= 0

    @pytest.mark.requirement("SC-007")
    def test_health_check_completes_within_one_second(
        self, connected_plugin: Any
    ) -> None:
        """Test health_check completes within 1 second for healthy plugin."""
        import time

        from floe_core.plugin_metadata import HealthState

        start = time.perf_counter()
        result = connected_plugin.health_check()
        elapsed = time.perf_counter() - start

        if result.state == HealthState.HEALTHY:
            assert elapsed < 1.0, (
                f"Health check took {elapsed:.2f}s (should be < 1s)"
            )

    # =========================================================================
    # Timestamp Tests
    # =========================================================================

    @pytest.mark.requirement("FR-028")
    def test_health_check_includes_checked_at_timestamp(
        self, connected_plugin: Any
    ) -> None:
        """Test health_check includes checked_at timestamp in details."""
        before = datetime.now(timezone.utc)
        result = connected_plugin.health_check()
        after = datetime.now(timezone.utc)

        assert "checked_at" in result.details

        checked_at = result.details["checked_at"]
        # Handle both datetime objects and ISO format strings
        if isinstance(checked_at, str):
            checked_at = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))

        assert before <= checked_at <= after

    # =========================================================================
    # Timeout Tests
    # =========================================================================

    @pytest.mark.requirement("FR-028")
    def test_health_check_accepts_timeout_parameter(
        self, connected_plugin: Any
    ) -> None:
        """Test health_check accepts a timeout parameter."""
        from floe_core.plugin_metadata import HealthStatus

        # Should not raise with valid timeout
        result = connected_plugin.health_check(timeout=2.0)
        assert isinstance(result, HealthStatus)

    def test_health_check_rejects_invalid_timeout_low(
        self, unconnected_plugin: Any
    ) -> None:
        """Test health_check rejects timeout below 0.1 seconds."""
        with pytest.raises(ValueError, match=r"timeout"):
            unconnected_plugin.health_check(timeout=0.05)

    def test_health_check_rejects_invalid_timeout_high(
        self, unconnected_plugin: Any
    ) -> None:
        """Test health_check rejects timeout above 10.0 seconds."""
        with pytest.raises(ValueError, match=r"timeout"):
            unconnected_plugin.health_check(timeout=15.0)

    def test_health_check_accepts_boundary_timeout_min(
        self, connected_plugin: Any
    ) -> None:
        """Test health_check accepts minimum timeout of 0.1 seconds."""
        from floe_core.plugin_metadata import HealthStatus

        result = connected_plugin.health_check(timeout=0.1)
        assert isinstance(result, HealthStatus)

    def test_health_check_accepts_boundary_timeout_max(
        self, connected_plugin: Any
    ) -> None:
        """Test health_check accepts maximum timeout of 10.0 seconds."""
        from floe_core.plugin_metadata import HealthStatus

        result = connected_plugin.health_check(timeout=10.0)
        assert isinstance(result, HealthStatus)

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.requirement("FR-028")
    def test_health_check_does_not_raise_when_unhealthy(
        self, unconnected_plugin: Any
    ) -> None:
        """Test health_check returns status instead of raising exceptions."""
        from floe_core.plugin_metadata import HealthStatus

        # Should NOT raise, should return HealthStatus
        result = unconnected_plugin.health_check()

        assert isinstance(result, HealthStatus)

    @pytest.mark.requirement("FR-028")
    def test_health_check_includes_message(self, connected_plugin: Any) -> None:
        """Test health_check includes a non-empty message."""
        result = connected_plugin.health_check()

        assert result.message is not None
        assert isinstance(result.message, str)
        assert len(result.message) > 0


# Module exports
__all__ = ["BaseHealthCheckTests"]
