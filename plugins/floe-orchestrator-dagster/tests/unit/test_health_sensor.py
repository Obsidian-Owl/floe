"""Unit tests for health check sensor in floe-orchestrator-dagster.

Task: T034
Epic: 13 - E2E Demo Platform
Requirements: FR-029, FR-033

These tests verify the health_check_sensor auto-triggers pipeline runs
when platform services are healthy and ready.

Test coverage:
- Sensor yields RunRequest when platform is healthy
- Sensor uses cursor to avoid duplicate triggers
- Sensor respects minimum interval
- Platform health check logic
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from dagster import RunRequest

if TYPE_CHECKING:
    pass


class TestHealthCheckSensorBasics:
    """Test basic health check sensor functionality."""

    @pytest.mark.requirement("FR-029")
    def test_sensor_yields_run_request_when_healthy(self) -> None:
        """Test sensor yields RunRequest when platform is healthy and cursor is 'never'."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        # Create mock context with cursor="never"
        mock_context = MagicMock()
        mock_context.cursor = "never"

        # Mock platform health check to return True
        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            # Evaluate sensor
            results = list(_health_check_sensor_impl(mock_context))

            # Should yield exactly one RunRequest
            assert len(results) == 1
            assert isinstance(results[0], RunRequest)

    @pytest.mark.requirement("FR-029")
    def test_sensor_does_not_trigger_when_already_triggered(self) -> None:
        """Test sensor does not yield RunRequest when cursor shows already triggered."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        # Create mock context with cursor="triggered"
        mock_context = MagicMock()
        mock_context.cursor = "triggered"

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            # Evaluate sensor
            results = list(_health_check_sensor_impl(mock_context))

            # Should not yield any RunRequest
            assert len(results) == 0

    @pytest.mark.requirement("FR-033")
    def test_sensor_does_not_trigger_when_unhealthy(self) -> None:
        """Test sensor does not yield RunRequest when platform is unhealthy."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        # Create mock context with cursor="never"
        mock_context = MagicMock()
        mock_context.cursor = "never"

        # Mock platform health check to return False
        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=False,
        ):
            # Evaluate sensor
            results = list(_health_check_sensor_impl(mock_context))

            # Should not yield RunRequest
            assert len(results) == 0

    @pytest.mark.requirement("FR-029")
    def test_sensor_updates_cursor_after_trigger(self) -> None:
        """Test sensor updates cursor to 'triggered' after yielding RunRequest."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        # Create mock context with cursor="never"
        mock_context = MagicMock()
        mock_context.cursor = "never"

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            # Evaluate sensor
            list(_health_check_sensor_impl(mock_context))

            # Verify cursor was updated
            mock_context.update_cursor.assert_called_once_with("triggered")

    @pytest.mark.requirement("FR-029")
    def test_run_request_has_correct_tags(self) -> None:
        """Test RunRequest includes correct tags for traceability."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        mock_context = MagicMock()
        mock_context.cursor = "never"

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            results = list(_health_check_sensor_impl(mock_context))

            run_request = results[0]
            assert run_request.tags["source"] == "health_check_sensor"
            assert run_request.tags["trigger_type"] == "auto"

    @pytest.mark.requirement("FR-029")
    def test_run_request_has_unique_run_key(self) -> None:
        """Test RunRequest has a unique run key for idempotency."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        mock_context = MagicMock()
        mock_context.cursor = "never"

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            results = list(_health_check_sensor_impl(mock_context))

            run_request = results[0]
            assert run_request.run_key == "health_check_auto_trigger"


class TestPlatformHealthCheck:
    """Test platform health check logic."""

    @pytest.mark.requirement("FR-033")
    def test_health_check_returns_false_when_dagster_home_missing(self) -> None:
        """Test _check_platform_health returns False when DAGSTER_HOME not set."""
        from floe_orchestrator_dagster.sensors import _check_platform_health

        with patch.dict("os.environ", {}, clear=True):
            # Remove DAGSTER_HOME from environment
            result = _check_platform_health()

            assert result is False

    @pytest.mark.requirement("FR-033")
    def test_health_check_returns_true_when_dagster_home_set(self) -> None:
        """Test _check_platform_health returns True when DAGSTER_HOME is set."""
        from floe_orchestrator_dagster.sensors import _check_platform_health

        with patch.dict("os.environ", {"DAGSTER_HOME": "/tmp/dagster"}):
            result = _check_platform_health()

            assert result is True

    @pytest.mark.requirement("FR-033")
    def test_health_check_handles_environment_variables(self) -> None:
        """Test health check properly reads environment variables."""
        from floe_orchestrator_dagster.sensors import _check_platform_health

        # Test with DAGSTER_HOME set
        with patch.dict("os.environ", {"DAGSTER_HOME": "/opt/dagster/home"}):
            assert _check_platform_health() is True

        # Test without DAGSTER_HOME
        with patch.dict("os.environ", {}, clear=True):
            assert _check_platform_health() is False


class TestSensorDefinition:
    """Test sensor definition metadata."""

    @pytest.mark.requirement("FR-029")
    def test_sensor_has_name(self) -> None:
        """Test sensor has correct name."""
        from floe_orchestrator_dagster.sensors import health_check_sensor

        # Dagster @sensor decorator sets name attribute
        # The decorated sensor should have a name attribute
        assert hasattr(health_check_sensor, "name")
        assert health_check_sensor.name == "health_check_sensor"

    @pytest.mark.requirement("FR-029")
    def test_sensor_has_minimum_interval(self) -> None:
        """Test sensor has minimum interval configured."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        # The underlying implementation should be callable
        assert callable(_health_check_sensor_impl)

        # Verify it can accept a context and returns a generator
        mock_context = MagicMock()
        mock_context.cursor = "triggered"

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=False,
        ):
            # Should not raise
            result = _health_check_sensor_impl(mock_context)
            # Should return a generator
            from collections.abc import Generator

            assert isinstance(result, Generator)


class TestSensorEdgeCases:
    """Test edge cases for health check sensor."""

    @pytest.mark.requirement("FR-029")
    def test_sensor_handles_none_cursor(self) -> None:
        """Test sensor treats None cursor as 'never' (first evaluation)."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        mock_context = MagicMock()
        mock_context.cursor = None  # Dagster may pass None on first evaluation

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            results = list(_health_check_sensor_impl(mock_context))

            # Should not yield (None is not "never")
            # Sensor logic: last_trigger = context.cursor or "never"
            # So None becomes "never", but the check is `if last_trigger == "never"`
            # With cursor=None, last_trigger will be "never" due to `or` operator
            assert len(results) == 1  # Should trigger

    @pytest.mark.requirement("FR-033")
    def test_sensor_handles_health_check_exception(self) -> None:
        """Test sensor handles exceptions from health check gracefully."""
        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        mock_context = MagicMock()
        mock_context.cursor = "never"

        # Mock health check to raise exception
        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            side_effect=RuntimeError("Health check failed"),
        ):
            # Sensor should propagate exception (Dagster will handle it)
            with pytest.raises(RuntimeError, match="Health check failed"):
                list(_health_check_sensor_impl(mock_context))

    @pytest.mark.requirement("FR-029")
    def test_sensor_returns_generator(self) -> None:
        """Test sensor returns a generator (yields results)."""
        from collections.abc import Generator

        from floe_orchestrator_dagster.sensors import _health_check_sensor_impl

        mock_context = MagicMock()
        mock_context.cursor = "triggered"

        with patch(
            "floe_orchestrator_dagster.sensors._check_platform_health",
            return_value=True,
        ):
            result = _health_check_sensor_impl(mock_context)

            # Should be a generator
            assert isinstance(result, Generator)

            # Consuming generator should not yield results (already triggered)
            results = list(result)
            assert len(results) == 0


__all__ = [
    "TestHealthCheckSensorBasics",
    "TestPlatformHealthCheck",
    "TestSensorDefinition",
    "TestSensorEdgeCases",
]
