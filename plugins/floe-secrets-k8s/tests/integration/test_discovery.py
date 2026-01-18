"""Integration tests for K8s Secrets plugin entry point discovery.

Tests that the plugin can be discovered via the floe.secrets entry point.

Implements:
    - T021: Integration test for plugin entry point discovery
    - FR-004: All plugins MUST inherit from PluginMetadata
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from floe_core.plugins.secrets import SecretsPlugin


class TestK8sSecretsPluginDiscovery:
    """Test plugin discovery via entry points."""

    @pytest.mark.requirement("7A-FR-004")
    def test_plugin_discovered_via_entry_point(self) -> None:
        """Test K8sSecretsPlugin is discoverable via floe.secrets entry point."""
        eps = entry_points(group="floe.secrets")

        # Find the k8s entry point
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        assert len(k8s_eps) == 1, "Expected exactly one 'k8s' entry point"
        assert k8s_eps[0].name == "k8s"

    @pytest.mark.requirement("7A-FR-004")
    def test_plugin_loads_successfully(self) -> None:
        """Test K8sSecretsPlugin loads without errors."""
        eps = entry_points(group="floe.secrets")
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        assert len(k8s_eps) == 1

        # Load the plugin class
        plugin_class = k8s_eps[0].load()

        # Verify it can be instantiated
        plugin = plugin_class()
        assert plugin is not None

    @pytest.mark.requirement("7A-FR-004")
    def test_plugin_has_required_metadata(self) -> None:
        """Test K8sSecretsPlugin has all required PluginMetadata attributes."""
        eps = entry_points(group="floe.secrets")
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        plugin_class = k8s_eps[0].load()
        plugin: SecretsPlugin = plugin_class()

        # Required PluginMetadata attributes
        assert hasattr(plugin, "name")
        assert hasattr(plugin, "version")
        assert hasattr(plugin, "floe_api_version")
        assert hasattr(plugin, "description")
        assert hasattr(plugin, "get_config_schema")

        # Verify values
        assert plugin.name == "k8s"
        assert plugin.version is not None
        assert plugin.floe_api_version is not None
        assert plugin.description is not None
        assert plugin.get_config_schema() is not None

    @pytest.mark.requirement("7A-FR-010")
    def test_plugin_is_secrets_plugin(self) -> None:
        """Test K8sSecretsPlugin inherits from SecretsPlugin ABC."""
        from floe_core.plugins.secrets import SecretsPlugin

        eps = entry_points(group="floe.secrets")
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        plugin_class = k8s_eps[0].load()

        # Verify inheritance
        assert issubclass(plugin_class, SecretsPlugin)

    @pytest.mark.requirement("7A-FR-002")
    def test_plugin_has_secrets_methods(self) -> None:
        """Test K8sSecretsPlugin has required SecretsPlugin methods."""
        eps = entry_points(group="floe.secrets")
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        plugin_class = k8s_eps[0].load()
        plugin = plugin_class()

        # Required SecretsPlugin methods
        assert hasattr(plugin, "get_secret")
        assert hasattr(plugin, "set_secret")
        assert hasattr(plugin, "list_secrets")
        assert hasattr(plugin, "generate_pod_env_spec")
        assert hasattr(plugin, "get_multi_key_secret")

        # Lifecycle methods
        assert hasattr(plugin, "startup")
        assert hasattr(plugin, "shutdown")
        assert hasattr(plugin, "health_check")

        # All should be callable
        assert callable(plugin.get_secret)
        assert callable(plugin.set_secret)
        assert callable(plugin.list_secrets)
        assert callable(plugin.generate_pod_env_spec)
        assert callable(plugin.startup)
        assert callable(plugin.shutdown)
        assert callable(plugin.health_check)


class TestK8sSecretsPluginEntryPointMetadata:
    """Test entry point metadata."""

    @pytest.mark.requirement("7A-FR-004")
    def test_entry_point_group_name(self) -> None:
        """Test entry point is registered under correct group."""
        eps = entry_points(group="floe.secrets")

        # Should have at least the k8s plugin
        names = [ep.name for ep in eps]
        assert "k8s" in names

    @pytest.mark.requirement("7A-FR-004")
    def test_entry_point_module_path(self) -> None:
        """Test entry point points to correct module."""
        eps = entry_points(group="floe.secrets")
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        assert len(k8s_eps) == 1

        # Entry point should reference the plugin module
        ep = k8s_eps[0]
        assert "floe_secrets_k8s" in ep.value
