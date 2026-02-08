"""Unit tests for JaegerTelemetryPlugin.

Contract Version: 1.0.0

Requirements Covered:
- FR-029: Jaeger backend for production tracing

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture

TDD Note:
    These tests are written BEFORE the implementation (T073).
    All tests MUST FAIL until JaegerTelemetryPlugin is implemented.
"""

from __future__ import annotations

from typing import Any

import pytest


class TestJaegerTelemetryPluginInitialization:
    """Test JaegerTelemetryPlugin initialization."""

    @pytest.mark.requirement("FR-029")
    def test_plugin_can_be_imported(self) -> None:
        """Test that JaegerTelemetryPlugin can be imported from package."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        assert JaegerTelemetryPlugin is not None

    @pytest.mark.requirement("FR-029")
    def test_plugin_can_be_instantiated(self) -> None:
        """Test that JaegerTelemetryPlugin can be instantiated."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert plugin is not None


class TestJaegerTelemetryPluginMetadata:
    """Test JaegerTelemetryPlugin metadata properties."""

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_name(self) -> None:
        """Test that plugin has a name property."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "name")
        assert isinstance(plugin.name, str)
        assert plugin.name == "jaeger"

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_version(self) -> None:
        """Test that plugin has a version property."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "version")
        assert isinstance(plugin.version, str)
        # Version should follow semver pattern
        assert len(plugin.version.split(".")) >= 2

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_floe_api_version(self) -> None:
        """Test that plugin has a floe_api_version property."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "floe_api_version")
        assert isinstance(plugin.floe_api_version, str)
        # API version should follow semver pattern
        assert len(plugin.floe_api_version.split(".")) >= 2

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_description(self) -> None:
        """Test that plugin has an optional description property."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        # description is optional, but if present should be a string
        if hasattr(plugin, "description") and plugin.description is not None:
            assert isinstance(plugin.description, str)


class TestJaegerTelemetryPluginInterface:
    """Test JaegerTelemetryPlugin implements TelemetryBackendPlugin interface."""

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_get_otlp_exporter_config(self) -> None:
        """Test that plugin has get_otlp_exporter_config method."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "get_otlp_exporter_config")
        assert callable(plugin.get_otlp_exporter_config)

    @pytest.mark.requirement("FR-029")
    def test_get_otlp_exporter_config_returns_dict(self) -> None:
        """Test that get_otlp_exporter_config returns a dictionary."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        config: dict[str, Any] = plugin.get_otlp_exporter_config()
        assert isinstance(config, dict)

    @pytest.mark.requirement("FR-029")
    def test_get_otlp_exporter_config_for_jaeger(self) -> None:
        """Test that Jaeger plugin returns OTLP exporter config.

        Jaeger backend should indicate OTLP exporter with Jaeger endpoint.
        """
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        config = plugin.get_otlp_exporter_config()
        # Jaeger plugin should indicate OTLP exporter type
        assert config.get("exporter_type") == "otlp"
        # Should have endpoint configuration
        assert "endpoint" in config

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_get_helm_values(self) -> None:
        """Test that plugin has get_helm_values method."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "get_helm_values")
        assert callable(plugin.get_helm_values)

    @pytest.mark.requirement("FR-029")
    def test_get_helm_values_returns_dict(self) -> None:
        """Test that get_helm_values returns a dictionary."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        values: dict[str, Any] = plugin.get_helm_values()
        assert isinstance(values, dict)

    @pytest.mark.requirement("FR-029")
    def test_get_helm_values_for_jaeger(self) -> None:
        """Test that Jaeger plugin returns Helm values for deployment.

        Jaeger is self-hosted, so should return Helm chart configuration.
        """
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        values = plugin.get_helm_values()
        # Jaeger plugin should return non-empty Helm values
        assert isinstance(values, dict)
        # Should include Jaeger-specific configuration
        assert "collector" in values or "query" in values or len(values) > 0

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_validate_connection(self) -> None:
        """Test that plugin has validate_connection method."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "validate_connection")
        assert callable(plugin.validate_connection)

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_returns_bool(self) -> None:
        """Test that validate_connection returns a boolean."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        result: bool = plugin.validate_connection()
        assert isinstance(result, bool)


class TestJaegerTelemetryPluginLifecycle:
    """Test JaegerTelemetryPlugin lifecycle methods from PluginMetadata."""

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_startup_method(self) -> None:
        """Test that plugin has startup method."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "startup")
        assert callable(plugin.startup)

    @pytest.mark.requirement("FR-029")
    def test_startup_does_not_raise(self) -> None:
        """Test that startup completes without error."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        # Should not raise any exception
        plugin.startup()

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_shutdown_method(self) -> None:
        """Test that plugin has shutdown method."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "shutdown")
        assert callable(plugin.shutdown)

    @pytest.mark.requirement("FR-029")
    def test_shutdown_does_not_raise(self) -> None:
        """Test that shutdown completes without error."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        plugin.startup()
        # Should not raise any exception
        plugin.shutdown()

    @pytest.mark.requirement("FR-029")
    def test_plugin_has_health_check_method(self) -> None:
        """Test that plugin has health_check method."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        assert hasattr(plugin, "health_check")
        assert callable(plugin.health_check)

    @pytest.mark.requirement("FR-029")
    def test_health_check_returns_health_status(self) -> None:
        """Test that health_check returns a HealthStatus."""
        from floe_core.plugin_metadata import HealthStatus

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        result = plugin.health_check()
        assert isinstance(result, HealthStatus)

    @pytest.mark.requirement("FR-029")
    def test_health_check_healthy_after_startup(self) -> None:
        """Test that health_check returns HEALTHY state after startup."""
        from floe_core.plugin_metadata import HealthState

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        plugin.startup()
        result = plugin.health_check()
        assert result.state == HealthState.HEALTHY
        plugin.shutdown()


class TestJaegerValidateConnection:
    """Test JaegerTelemetryPlugin.validate_connection() method."""

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_returns_false_when_unreachable(self) -> None:
        """Test validate_connection returns False when endpoint is unreachable."""
        import os

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        # Set an unreachable endpoint
        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "nonexistent-host:4317"
        try:
            result = plugin.validate_connection()
            assert result is False
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_returns_true_when_reachable(self) -> None:
        """Test validate_connection returns True when endpoint is reachable."""
        from unittest.mock import MagicMock, patch

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        # Mock socket.create_connection to simulate successful connection
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock(return_value=None)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = plugin.validate_connection()
            assert result is True

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_parses_http_prefix(self) -> None:
        """Test validate_connection correctly parses http:// prefixed endpoints."""
        import os
        from unittest.mock import MagicMock, patch

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://jaeger-collector:4317"
        try:
            with patch("socket.create_connection") as mock_conn:
                mock_conn.return_value.__enter__ = MagicMock(return_value=None)
                mock_conn.return_value.__exit__ = MagicMock(return_value=False)
                plugin.validate_connection()
                # Verify the host was parsed correctly (without http://)
                mock_conn.assert_called_once_with(
                    ("jaeger-collector", 4317), timeout=5.0
                )
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_parses_https_prefix(self) -> None:
        """Test validate_connection correctly parses https:// prefixed endpoints."""
        import os
        from unittest.mock import MagicMock, patch

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "https://secure-jaeger:4317"
        try:
            with patch("socket.create_connection") as mock_conn:
                mock_conn.return_value.__enter__ = MagicMock(return_value=None)
                mock_conn.return_value.__exit__ = MagicMock(return_value=False)
                plugin.validate_connection()
                mock_conn.assert_called_once_with(("secure-jaeger", 4317), timeout=5.0)
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_uses_default_port_when_not_specified(self) -> None:
        """Test validate_connection uses port 4317 when not specified."""
        import os
        from unittest.mock import MagicMock, patch

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "jaeger-collector"
        try:
            with patch("socket.create_connection") as mock_conn:
                mock_conn.return_value.__enter__ = MagicMock(return_value=None)
                mock_conn.return_value.__exit__ = MagicMock(return_value=False)
                plugin.validate_connection()
                mock_conn.assert_called_once_with(
                    ("jaeger-collector", 4317), timeout=5.0
                )
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original

    @pytest.mark.requirement("FR-029")
    def test_validate_connection_returns_false_for_invalid_port(self) -> None:
        """Test validate_connection returns False for invalid port format."""
        import os

        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        original = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "jaeger-collector:invalid"
        try:
            result = plugin.validate_connection()
            assert result is False
        finally:
            if original is None:
                os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            else:
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original
