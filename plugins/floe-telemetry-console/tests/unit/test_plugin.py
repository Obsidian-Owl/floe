"""Unit tests for ConsoleTelemetryPlugin.

Contract Version: 1.0.0

Requirements Covered:
- FR-027: Console backend for local development

See Also:
    - specs/001-opentelemetry/: Feature specification
    - ADR-0006: Telemetry architecture

TDD Note:
    These tests are written BEFORE the implementation (T070).
    All tests MUST FAIL until ConsoleTelemetryPlugin is implemented.
"""

from __future__ import annotations

from typing import Any

import pytest


class TestConsoleTelemetryPluginInitialization:
    """Test ConsoleTelemetryPlugin initialization."""

    @pytest.mark.requirement("FR-027")
    def test_plugin_can_be_imported(self) -> None:
        """Test that ConsoleTelemetryPlugin can be imported from package."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        assert ConsoleTelemetryPlugin is not None

    @pytest.mark.requirement("FR-027")
    def test_plugin_can_be_instantiated(self) -> None:
        """Test that ConsoleTelemetryPlugin can be instantiated."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert plugin is not None


class TestConsoleTelemetryPluginMetadata:
    """Test ConsoleTelemetryPlugin metadata properties."""

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_name(self) -> None:
        """Test that plugin has a name property."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "name")
        assert isinstance(plugin.name, str)
        assert plugin.name == "console"

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_version(self) -> None:
        """Test that plugin has a version property."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "version")
        assert isinstance(plugin.version, str)
        # Version should follow semver pattern
        assert len(plugin.version.split(".")) >= 2

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_floe_api_version(self) -> None:
        """Test that plugin has a floe_api_version property."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "floe_api_version")
        assert isinstance(plugin.floe_api_version, str)
        # API version should follow semver pattern
        assert len(plugin.floe_api_version.split(".")) >= 2

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_description(self) -> None:
        """Test that plugin has an optional description property."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        # description is optional, but if present should be a string
        if hasattr(plugin, "description") and plugin.description is not None:
            assert isinstance(plugin.description, str)


class TestConsoleTelemetryPluginInterface:
    """Test ConsoleTelemetryPlugin implements TelemetryBackendPlugin interface."""

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_get_otlp_exporter_config(self) -> None:
        """Test that plugin has get_otlp_exporter_config method."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "get_otlp_exporter_config")
        assert callable(plugin.get_otlp_exporter_config)

    @pytest.mark.requirement("FR-027")
    def test_get_otlp_exporter_config_returns_dict(self) -> None:
        """Test that get_otlp_exporter_config returns a dictionary."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        config: dict[str, Any] = plugin.get_otlp_exporter_config()
        assert isinstance(config, dict)

    @pytest.mark.requirement("FR-027")
    def test_get_otlp_exporter_config_for_console(self) -> None:
        """Test that console plugin returns console-specific config.

        Console backend should indicate it uses console exporter,
        not OTLP exporter (since there's no collector).
        """
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        config = plugin.get_otlp_exporter_config()
        # Console plugin should indicate it's a console exporter
        assert config.get("exporter_type") == "console"

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_get_helm_values(self) -> None:
        """Test that plugin has get_helm_values method."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "get_helm_values")
        assert callable(plugin.get_helm_values)

    @pytest.mark.requirement("FR-027")
    def test_get_helm_values_returns_dict(self) -> None:
        """Test that get_helm_values returns a dictionary."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        values: dict[str, Any] = plugin.get_helm_values()
        assert isinstance(values, dict)

    @pytest.mark.requirement("FR-027")
    def test_get_helm_values_for_console(self) -> None:
        """Test that console plugin returns empty or minimal Helm values.

        Console backend doesn't require Helm deployment since it just
        outputs to stdout locally.
        """
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        values = plugin.get_helm_values()
        # Console plugin should return empty dict (no K8s resources needed)
        assert values == {}

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_validate_connection(self) -> None:
        """Test that plugin has validate_connection method."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "validate_connection")
        assert callable(plugin.validate_connection)

    @pytest.mark.requirement("FR-027")
    def test_validate_connection_returns_bool(self) -> None:
        """Test that validate_connection returns a boolean."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        result: bool = plugin.validate_connection()
        assert isinstance(result, bool)

    @pytest.mark.requirement("FR-027")
    def test_validate_connection_always_true_for_console(self) -> None:
        """Test that console plugin always validates successfully.

        Console backend always works (stdout is always available),
        so validate_connection should always return True.
        """
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert plugin.validate_connection() is True


class TestConsoleTelemetryPluginLifecycle:
    """Test ConsoleTelemetryPlugin lifecycle methods from PluginMetadata."""

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_startup_method(self) -> None:
        """Test that plugin has startup method."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "startup")
        assert callable(plugin.startup)

    @pytest.mark.requirement("FR-027")
    def test_startup_does_not_raise(self) -> None:
        """Test that startup completes without error."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        # Should not raise any exception
        plugin.startup()

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_shutdown_method(self) -> None:
        """Test that plugin has shutdown method."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "shutdown")
        assert callable(plugin.shutdown)

    @pytest.mark.requirement("FR-027")
    def test_shutdown_does_not_raise(self) -> None:
        """Test that shutdown completes without error."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        plugin.startup()
        # Should not raise any exception
        plugin.shutdown()

    @pytest.mark.requirement("FR-027")
    def test_plugin_has_health_check_method(self) -> None:
        """Test that plugin has health_check method."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        assert hasattr(plugin, "health_check")
        assert callable(plugin.health_check)

    @pytest.mark.requirement("FR-027")
    def test_health_check_returns_health_status(self) -> None:
        """Test that health_check returns a HealthStatus."""
        from floe_core.plugin_metadata import HealthStatus
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        result = plugin.health_check()
        assert isinstance(result, HealthStatus)

    @pytest.mark.requirement("FR-027")
    def test_health_check_healthy_after_startup(self) -> None:
        """Test that health_check returns HEALTHY state after startup."""
        from floe_core.plugin_metadata import HealthState
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        plugin.startup()
        result = plugin.health_check()
        assert result.state == HealthState.HEALTHY
        plugin.shutdown()
