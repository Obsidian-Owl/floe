"""Contract tests for TelemetryBackendPlugin ABC.

These tests validate that the TelemetryBackendPlugin ABC contract is stable
and that implementations correctly inherit and implement the required methods.

Contract tests focus on:
- ABC inheritance requirements (must implement abstract methods)
- Method signatures (return types, parameter types)
- Subclass compliance (concrete implementations satisfy the contract)

Requirements Covered:
- FR-001: Plugin registry public API stability
- FR-023: Telemetry plugin interface contract
"""

from __future__ import annotations

from abc import ABC
from inspect import signature
from typing import Any

import pytest
from floe_core.plugin_metadata import HealthState, HealthStatus, PluginMetadata
from floe_core.plugins.telemetry import TelemetryBackendPlugin


class TestTelemetryBackendPluginContract:
    """Contract tests for TelemetryBackendPlugin ABC.

    Validates the ABC interface that telemetry backend plugin
    implementations must conform to.
    """

    @pytest.mark.requirement("FR-023")
    def test_is_abstract_base_class(self) -> None:
        """Verify TelemetryBackendPlugin is an ABC."""
        assert issubclass(TelemetryBackendPlugin, ABC)

    @pytest.mark.requirement("FR-023")
    def test_inherits_from_plugin_metadata(self) -> None:
        """Verify TelemetryBackendPlugin extends PluginMetadata."""
        assert issubclass(TelemetryBackendPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-023")
    def test_cannot_instantiate_directly(self) -> None:
        """Verify TelemetryBackendPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError, match="abstract"):
            TelemetryBackendPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-023")
    def test_has_get_otlp_exporter_config_method(self) -> None:
        """Verify get_otlp_exporter_config() is defined."""
        assert hasattr(TelemetryBackendPlugin, "get_otlp_exporter_config")
        assert callable(TelemetryBackendPlugin.get_otlp_exporter_config)

    @pytest.mark.requirement("FR-023")
    def test_has_get_helm_values_method(self) -> None:
        """Verify get_helm_values() is defined."""
        assert hasattr(TelemetryBackendPlugin, "get_helm_values")
        assert callable(TelemetryBackendPlugin.get_helm_values)

    @pytest.mark.requirement("FR-023")
    def test_has_validate_connection_method(self) -> None:
        """Verify validate_connection() is defined."""
        assert hasattr(TelemetryBackendPlugin, "validate_connection")
        assert callable(TelemetryBackendPlugin.validate_connection)

    @pytest.mark.requirement("FR-023")
    def test_get_otlp_exporter_config_signature(self) -> None:
        """Verify get_otlp_exporter_config() returns dict[str, Any]."""
        sig = signature(TelemetryBackendPlugin.get_otlp_exporter_config)
        # Should take only self parameter
        params = list(sig.parameters.keys())
        assert params == ["self"]
        # Return annotation (string due to __future__.annotations)
        assert "dict" in str(sig.return_annotation)

    @pytest.mark.requirement("FR-023")
    def test_get_helm_values_signature(self) -> None:
        """Verify get_helm_values() returns dict[str, Any]."""
        sig = signature(TelemetryBackendPlugin.get_helm_values)
        params = list(sig.parameters.keys())
        assert params == ["self"]
        assert "dict" in str(sig.return_annotation)

    @pytest.mark.requirement("FR-023")
    def test_validate_connection_signature(self) -> None:
        """Verify validate_connection() returns bool."""
        sig = signature(TelemetryBackendPlugin.validate_connection)
        params = list(sig.parameters.keys())
        assert params == ["self"]
        assert "bool" in str(sig.return_annotation)


class TestTelemetryBackendPluginImplementation:
    """Contract tests for concrete TelemetryBackendPlugin implementations.

    Uses a minimal test implementation to verify that the ABC contract
    can be properly satisfied by concrete classes.
    """

    def _create_test_plugin(self) -> type[TelemetryBackendPlugin]:
        """Create a minimal test implementation of TelemetryBackendPlugin."""

        class TestTelemetryPlugin(TelemetryBackendPlugin):
            """Minimal test implementation."""

            @property
            def name(self) -> str:
                return "test-telemetry"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            @property
            def description(self) -> str:
                return "Test telemetry backend plugin"

            def get_otlp_exporter_config(self) -> dict[str, Any]:
                return {
                    "exporters": {"test": {"endpoint": "test:4317"}},
                    "service": {"pipelines": {"traces": {"exporters": ["test"]}}},
                }

            def get_helm_values(self) -> dict[str, Any]:
                return {"enabled": True}

            def validate_connection(self) -> bool:
                return True

        return TestTelemetryPlugin

    @pytest.mark.requirement("FR-023")
    def test_can_implement_all_abstract_methods(self) -> None:
        """Verify a concrete class can implement all abstract methods."""
        plugin_class = self._create_test_plugin()
        # Should not raise - all abstract methods implemented
        plugin = plugin_class()
        assert plugin is not None

    @pytest.mark.requirement("FR-023")
    def test_implementation_inherits_plugin_metadata_properties(self) -> None:
        """Verify implementation has PluginMetadata properties."""
        plugin = self._create_test_plugin()()

        assert plugin.name == "test-telemetry"
        assert plugin.version == "1.0.0"
        assert plugin.floe_api_version == "1.0"
        assert plugin.description == "Test telemetry backend plugin"
        assert plugin.dependencies == []  # Default from PluginMetadata

    @pytest.mark.requirement("FR-023")
    def test_get_otlp_exporter_config_returns_dict(self) -> None:
        """Verify get_otlp_exporter_config() returns proper structure."""
        plugin = self._create_test_plugin()()
        config = plugin.get_otlp_exporter_config()

        assert isinstance(config, dict)
        assert "exporters" in config
        assert "service" in config
        assert "pipelines" in config["service"]

    @pytest.mark.requirement("FR-023")
    def test_get_helm_values_returns_dict(self) -> None:
        """Verify get_helm_values() returns a dict."""
        plugin = self._create_test_plugin()()
        values = plugin.get_helm_values()

        assert isinstance(values, dict)

    @pytest.mark.requirement("FR-023")
    def test_validate_connection_returns_bool(self) -> None:
        """Verify validate_connection() returns a bool."""
        plugin = self._create_test_plugin()()
        result = plugin.validate_connection()

        assert isinstance(result, bool)

    @pytest.mark.requirement("FR-001")
    def test_implementation_has_health_check(self) -> None:
        """Verify implementation inherits health_check() from PluginMetadata."""
        plugin = self._create_test_plugin()()
        status = plugin.health_check()

        assert isinstance(status, HealthStatus)
        assert status.state == HealthState.HEALTHY

    @pytest.mark.requirement("FR-001")
    def test_implementation_has_lifecycle_methods(self) -> None:
        """Verify implementation inherits startup/shutdown from PluginMetadata."""
        plugin = self._create_test_plugin()()

        # Should not raise - inherited from PluginMetadata
        plugin.startup()
        plugin.shutdown()

    @pytest.mark.requirement("FR-001")
    def test_implementation_has_config_schema_method(self) -> None:
        """Verify implementation inherits get_config_schema from PluginMetadata."""
        plugin = self._create_test_plugin()()
        schema = plugin.get_config_schema()

        # Default is None
        assert schema is None


class TestTelemetryBackendPluginPartialImplementation:
    """Contract tests for incomplete implementations.

    Verifies that partial implementations correctly fail with TypeError.
    """

    @pytest.mark.requirement("FR-023")
    def test_missing_name_raises_type_error(self) -> None:
        """Verify missing name property raises TypeError."""

        class IncompletePlugin(TelemetryBackendPlugin):
            """Missing name property."""

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_otlp_exporter_config(self) -> dict[str, Any]:
                return {}

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return True

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-023")
    def test_missing_get_otlp_exporter_config_raises_type_error(self) -> None:
        """Verify missing get_otlp_exporter_config() raises TypeError."""

        class IncompletePlugin(TelemetryBackendPlugin):
            """Missing get_otlp_exporter_config method."""

            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_helm_values(self) -> dict[str, Any]:
                return {}

            def validate_connection(self) -> bool:
                return True

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-023")
    def test_missing_validate_connection_raises_type_error(self) -> None:
        """Verify missing validate_connection() raises TypeError."""

        class IncompletePlugin(TelemetryBackendPlugin):
            """Missing validate_connection method."""

            @property
            def name(self) -> str:
                return "incomplete"

            @property
            def version(self) -> str:
                return "1.0.0"

            @property
            def floe_api_version(self) -> str:
                return "1.0"

            def get_otlp_exporter_config(self) -> dict[str, Any]:
                return {}

            def get_helm_values(self) -> dict[str, Any]:
                return {}

        with pytest.raises(TypeError, match="abstract"):
            IncompletePlugin()  # type: ignore[abstract]


class TestTelemetryBackendPluginDiscovery:
    """Contract tests for plugin discovery via entry points.

    Validates that telemetry backend plugins can be discovered and loaded
    via Python entry points (importlib.metadata).
    """

    @pytest.mark.requirement("FR-025")
    def test_can_discover_plugins_via_entry_points(self) -> None:
        """Verify plugins are discoverable via entry points."""
        from importlib.metadata import entry_points

        # Get all telemetry backend plugins
        eps = entry_points(group="floe.telemetry_backends")

        # Should have at least console and jaeger plugins
        plugin_names = [ep.name for ep in eps]
        assert "console" in plugin_names
        assert "jaeger" in plugin_names

    @pytest.mark.requirement("FR-025")
    def test_console_plugin_loadable_via_entry_point(self) -> None:
        """Verify console plugin can be loaded via entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.telemetry_backends")
        console_ep = next(ep for ep in eps if ep.name == "console")

        # Load the plugin class
        plugin_class = console_ep.load()
        assert plugin_class is not None
        assert issubclass(plugin_class, TelemetryBackendPlugin)

        # Instantiate and verify
        plugin = plugin_class()
        assert plugin.name == "console"

    @pytest.mark.requirement("FR-025")
    def test_jaeger_plugin_loadable_via_entry_point(self) -> None:
        """Verify Jaeger plugin can be loaded via entry point."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.telemetry_backends")
        jaeger_ep = next(ep for ep in eps if ep.name == "jaeger")

        # Load the plugin class
        plugin_class = jaeger_ep.load()
        assert plugin_class is not None
        assert issubclass(plugin_class, TelemetryBackendPlugin)

        # Instantiate and verify
        plugin = plugin_class()
        assert plugin.name == "jaeger"


class TestConcretePluginCompliance:
    """Contract tests for concrete plugin implementations.

    Validates that real plugin implementations (console, jaeger) satisfy
    the TelemetryBackendPlugin contract.
    """

    @pytest.mark.requirement("FR-027")
    def test_console_plugin_implements_abc(self) -> None:
        """Verify console plugin properly implements the ABC."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()

        # Verify all abstract properties
        assert isinstance(plugin.name, str)
        assert isinstance(plugin.version, str)
        assert isinstance(plugin.floe_api_version, str)

        # Verify all abstract methods
        config = plugin.get_otlp_exporter_config()
        assert isinstance(config, dict)

        values = plugin.get_helm_values()
        assert isinstance(values, dict)

        valid = plugin.validate_connection()
        assert isinstance(valid, bool)

    @pytest.mark.requirement("FR-027")
    def test_console_plugin_returns_console_exporter_type(self) -> None:
        """Verify console plugin indicates console exporter type."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        config = plugin.get_otlp_exporter_config()

        assert config.get("exporter_type") == "console"

    @pytest.mark.requirement("FR-027")
    def test_console_plugin_returns_empty_helm_values(self) -> None:
        """Verify console plugin returns empty Helm values (no deployment)."""
        from floe_telemetry_console import ConsoleTelemetryPlugin

        plugin = ConsoleTelemetryPlugin()
        values = plugin.get_helm_values()

        assert values == {}

    @pytest.mark.requirement("FR-029")
    def test_jaeger_plugin_implements_abc(self) -> None:
        """Verify Jaeger plugin properly implements the ABC."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()

        # Verify all abstract properties
        assert isinstance(plugin.name, str)
        assert isinstance(plugin.version, str)
        assert isinstance(plugin.floe_api_version, str)

        # Verify all abstract methods
        config = plugin.get_otlp_exporter_config()
        assert isinstance(config, dict)

        values = plugin.get_helm_values()
        assert isinstance(values, dict)

        valid = plugin.validate_connection()
        assert isinstance(valid, bool)

    @pytest.mark.requirement("FR-029")
    def test_jaeger_plugin_returns_otlp_exporter_type(self) -> None:
        """Verify Jaeger plugin indicates OTLP exporter type."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        config = plugin.get_otlp_exporter_config()

        assert config.get("exporter_type") == "otlp"
        assert "endpoint" in config

    @pytest.mark.requirement("FR-029")
    def test_jaeger_plugin_returns_helm_values(self) -> None:
        """Verify Jaeger plugin returns Helm values for deployment."""
        from floe_telemetry_jaeger import JaegerTelemetryPlugin

        plugin = JaegerTelemetryPlugin()
        values = plugin.get_helm_values()

        assert isinstance(values, dict)
        assert len(values) > 0  # Jaeger needs deployment config
        assert "collector" in values or "query" in values
