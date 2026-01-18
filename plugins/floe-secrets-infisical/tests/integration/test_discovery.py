"""Integration tests for Infisical Secrets plugin entry point discovery.

Tests that the plugin can be discovered via the floe.secrets entry point.

Task: T043
Requirements: 7A-FR-004 (All plugins MUST inherit from PluginMetadata)
"""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest


class TestInfisicalSecretsPluginDiscovery:
    """Test plugin discovery via entry points."""

    @pytest.mark.requirement("7A-FR-004")
    def test_plugin_discovered_via_entry_point(self) -> None:
        """Test InfisicalSecretsPlugin is discoverable via floe.secrets entry point."""
        eps = entry_points(group="floe.secrets")

        # Find the infisical entry point
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        assert len(infisical_eps) == 1, "Expected exactly one 'infisical' entry point"
        assert infisical_eps[0].name == "infisical"

    @pytest.mark.requirement("7A-FR-004")
    def test_plugin_loads_successfully(self) -> None:
        """Test InfisicalSecretsPlugin loads without errors."""
        eps = entry_points(group="floe.secrets")
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        assert len(infisical_eps) == 1

        # Load the plugin class
        plugin_class = infisical_eps[0].load()

        # Verify it's a class (not instantiated yet - needs config)
        assert plugin_class is not None
        assert isinstance(plugin_class, type)

    @pytest.mark.requirement("7A-FR-004")
    def test_plugin_has_required_metadata_attributes(self) -> None:
        """Test InfisicalSecretsPlugin has all required PluginMetadata attributes."""
        eps = entry_points(group="floe.secrets")
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        plugin_class = infisical_eps[0].load()

        # Required PluginMetadata class attributes
        assert hasattr(plugin_class, "name")
        assert hasattr(plugin_class, "version")
        assert hasattr(plugin_class, "floe_api_version")
        assert hasattr(plugin_class, "description")
        assert hasattr(plugin_class, "get_config_schema")

        # Verify class-level values
        assert plugin_class.name == "infisical"
        assert plugin_class.version is not None
        assert plugin_class.floe_api_version is not None

    @pytest.mark.requirement("7A-FR-020")
    def test_plugin_is_secrets_plugin(self) -> None:
        """Test InfisicalSecretsPlugin inherits from SecretsPlugin ABC."""
        from floe_core.plugins.secrets import SecretsPlugin

        eps = entry_points(group="floe.secrets")
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        plugin_class = infisical_eps[0].load()

        # Verify inheritance
        assert issubclass(plugin_class, SecretsPlugin)

    @pytest.mark.requirement("7A-FR-002")
    def test_plugin_has_secrets_methods(self) -> None:
        """Test InfisicalSecretsPlugin has required SecretsPlugin methods."""
        eps = entry_points(group="floe.secrets")
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        plugin_class = infisical_eps[0].load()

        # Required SecretsPlugin methods (on class)
        assert hasattr(plugin_class, "get_secret")
        assert hasattr(plugin_class, "set_secret")
        assert hasattr(plugin_class, "list_secrets")
        assert hasattr(plugin_class, "health_check")

        # Lifecycle methods
        assert hasattr(plugin_class, "startup")
        assert hasattr(plugin_class, "shutdown")

        # All should be callable (methods)
        assert callable(getattr(plugin_class, "get_secret"))
        assert callable(getattr(plugin_class, "set_secret"))
        assert callable(getattr(plugin_class, "list_secrets"))
        assert callable(getattr(plugin_class, "health_check"))

    @pytest.mark.requirement("7A-FR-021")
    def test_plugin_supports_universal_auth(self) -> None:
        """Test InfisicalSecretsPlugin requires config with Universal Auth."""
        eps = entry_points(group="floe.secrets")
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        plugin_class = infisical_eps[0].load()

        # Get the config schema
        config_schema = plugin_class.get_config_schema()

        # Config should require client_id and client_secret for Universal Auth
        assert config_schema is not None
        schema_json = config_schema.model_json_schema()
        required_fields = schema_json.get("required", [])

        assert "client_id" in required_fields
        assert "client_secret" in required_fields


class TestInfisicalSecretsPluginEntryPointMetadata:
    """Test entry point metadata."""

    @pytest.mark.requirement("7A-FR-004")
    def test_entry_point_group_name(self) -> None:
        """Test entry point is registered under correct group."""
        eps = entry_points(group="floe.secrets")

        # Should have the infisical plugin
        names = [ep.name for ep in eps]
        assert "infisical" in names

    @pytest.mark.requirement("7A-FR-004")
    def test_entry_point_module_path(self) -> None:
        """Test entry point points to correct module."""
        eps = entry_points(group="floe.secrets")
        infisical_eps = [ep for ep in eps if ep.name == "infisical"]

        assert len(infisical_eps) == 1

        # Entry point should reference the plugin module
        ep = infisical_eps[0]
        assert "floe_secrets_infisical" in ep.value

    @pytest.mark.requirement("7A-FR-020")
    def test_multiple_secrets_plugins_coexist(self) -> None:
        """Test multiple secrets plugins can be discovered together."""
        eps = entry_points(group="floe.secrets")
        names = [ep.name for ep in eps]

        # Both k8s and infisical should be available
        assert "k8s" in names
        assert "infisical" in names

        # Each should be distinct
        assert len(names) == len(set(names)), "Duplicate entry point names found"
