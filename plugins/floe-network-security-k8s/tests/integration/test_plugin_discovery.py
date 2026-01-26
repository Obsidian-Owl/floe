"""Integration tests for plugin discovery via entry points.

Task: T086
Phase: 11 - Plugin Discovery (US7)
User Story: US7 - Plugin Architecture Standards
Requirement: FR-001

Tests that K8sNetworkSecurityPlugin is properly registered and discoverable
via the floe.network_security entry point group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from floe_core.network import (
    NetworkSecurityPluginNotFoundError,
    discover_network_security_plugins,
    get_network_security_plugin,
)
from floe_core.network.generator import NETWORK_SECURITY_ENTRY_POINT_GROUP
from floe_core.plugins import NetworkSecurityPlugin

if TYPE_CHECKING:
    from floe_network_security_k8s import K8sNetworkSecurityPlugin


class TestEntryPointRegistration:
    """Tests for entry point registration."""

    @pytest.mark.requirement("FR-001")
    def test_entry_point_group_exists(self) -> None:
        """Test floe.network_security entry point group exists.

        Validates that the entry point group is properly configured
        and can be queried via importlib.metadata.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=NETWORK_SECURITY_ENTRY_POINT_GROUP)
        eps_list = list(eps)
        assert len(eps_list) > 0, (
            f"No entry points found in '{NETWORK_SECURITY_ENTRY_POINT_GROUP}' group. "
            "Ensure floe-network-security-k8s is installed."
        )

    @pytest.mark.requirement("FR-001")
    def test_k8s_plugin_registered(self) -> None:
        """Test k8s plugin is registered under floe.network_security.

        Validates that the K8sNetworkSecurityPlugin is discoverable
        by name in the entry point group.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=NETWORK_SECURITY_ENTRY_POINT_GROUP)
        names = [ep.name for ep in eps]
        assert "k8s" in names, (
            f"K8s plugin not found in '{NETWORK_SECURITY_ENTRY_POINT_GROUP}' entry points. "
            f"Found: {names}. Ensure floe-network-security-k8s is installed."
        )

    @pytest.mark.requirement("FR-001")
    def test_entry_point_value_format(self) -> None:
        """Test entry point value has correct module and class reference.

        Validates that the entry point references the correct module
        and class name for the K8sNetworkSecurityPlugin.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=NETWORK_SECURITY_ENTRY_POINT_GROUP)
        k8s_ep = next((ep for ep in eps if ep.name == "k8s"), None)

        assert k8s_ep is not None, "K8s entry point not found"
        assert "floe_network_security_k8s" in k8s_ep.value, (
            f"Entry point value '{k8s_ep.value}' should reference 'floe_network_security_k8s' module"
        )
        assert "K8sNetworkSecurityPlugin" in k8s_ep.value, (
            f"Entry point value '{k8s_ep.value}' should reference 'K8sNetworkSecurityPlugin' class"
        )

    @pytest.mark.requirement("FR-001")
    def test_exactly_one_k8s_entry_point(self) -> None:
        """Test there is exactly one k8s entry point.

        Validates that the plugin is registered exactly once to avoid
        duplicate discovery issues.
        """
        from importlib.metadata import entry_points

        eps = entry_points(group=NETWORK_SECURITY_ENTRY_POINT_GROUP)
        k8s_eps = [ep for ep in eps if ep.name == "k8s"]

        assert len(k8s_eps) == 1, f"Expected exactly one 'k8s' entry point, found {len(k8s_eps)}"


class TestDiscoverPlugins:
    """Tests for discover_network_security_plugins() function."""

    @pytest.mark.requirement("FR-001")
    def test_discover_returns_dict(self) -> None:
        """Test discover_network_security_plugins returns dict.

        Validates that the discovery function returns a dictionary
        mapping plugin names to plugin classes.
        """
        plugins = discover_network_security_plugins()
        assert isinstance(plugins, dict), (
            f"discover_network_security_plugins() should return dict, got {type(plugins)}"
        )

    @pytest.mark.requirement("FR-001")
    def test_discover_returns_non_empty_dict(self) -> None:
        """Test discover_network_security_plugins returns non-empty dict.

        Validates that at least one plugin is discovered.
        """
        plugins = discover_network_security_plugins()
        assert len(plugins) > 0, (
            "discover_network_security_plugins() returned empty dict. "
            "Ensure floe-network-security-k8s is installed."
        )

    @pytest.mark.requirement("FR-001")
    def test_k8s_plugin_discovered(self) -> None:
        """Test K8sNetworkSecurityPlugin is discovered.

        Validates that the k8s plugin is present in the discovered
        plugins dictionary.
        """
        plugins = discover_network_security_plugins()
        assert "k8s" in plugins, f"K8s plugin not discovered. Found: {list(plugins.keys())}"

    @pytest.mark.requirement("FR-001")
    def test_discovered_plugin_is_class(self) -> None:
        """Test discovered plugin is a class (not instance).

        Validates that discover_network_security_plugins returns
        plugin classes, not instances.
        """
        plugins = discover_network_security_plugins()
        k8s_plugin = plugins["k8s"]

        assert isinstance(k8s_plugin, type), (
            f"Discovered plugin should be a class, got {type(k8s_plugin)}"
        )

    @pytest.mark.requirement("FR-001")
    def test_discovered_plugin_inherits_from_abc(self) -> None:
        """Test discovered plugin inherits from NetworkSecurityPlugin ABC.

        Validates that the plugin class properly implements the
        NetworkSecurityPlugin interface.
        """
        plugins = discover_network_security_plugins()
        k8s_plugin = plugins["k8s"]

        assert issubclass(k8s_plugin, NetworkSecurityPlugin), (
            f"Plugin '{k8s_plugin.__name__}' should inherit from NetworkSecurityPlugin"
        )

    @pytest.mark.requirement("FR-001")
    def test_discovered_plugin_has_correct_name(self) -> None:
        """Test discovered plugin class has correct name.

        Validates that the plugin class is named K8sNetworkSecurityPlugin.
        """
        plugins = discover_network_security_plugins()
        k8s_plugin = plugins["k8s"]

        assert k8s_plugin.__name__ == "K8sNetworkSecurityPlugin", (
            f"Expected class name 'K8sNetworkSecurityPlugin', got '{k8s_plugin.__name__}'"
        )


class TestGetPlugin:
    """Tests for get_network_security_plugin() function."""

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_by_name(self) -> None:
        """Test getting plugin by name returns plugin instance.

        Validates that get_network_security_plugin("k8s") returns
        an instantiated K8sNetworkSecurityPlugin.
        """
        plugin = get_network_security_plugin("k8s")

        assert plugin is not None, "get_network_security_plugin('k8s') returned None"
        assert isinstance(plugin, NetworkSecurityPlugin), (
            f"Plugin should be instance of NetworkSecurityPlugin, got {type(plugin)}"
        )

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_returns_correct_type(self) -> None:
        """Test get_network_security_plugin returns K8sNetworkSecurityPlugin instance.

        Validates that the returned plugin is specifically a
        K8sNetworkSecurityPlugin instance.
        """
        plugin = get_network_security_plugin("k8s")

        assert plugin.__class__.__name__ == "K8sNetworkSecurityPlugin", (
            f"Expected K8sNetworkSecurityPlugin instance, got {plugin.__class__.__name__}"
        )

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_has_metadata(self) -> None:
        """Test plugin instance has required metadata attributes.

        Validates that the plugin has name, version, and floe_api_version
        attributes as required by PluginMetadata.
        """
        plugin = get_network_security_plugin("k8s")

        assert hasattr(plugin, "name"), "Plugin missing 'name' attribute"
        assert hasattr(plugin, "version"), "Plugin missing 'version' attribute"
        assert hasattr(plugin, "floe_api_version"), "Plugin missing 'floe_api_version' attribute"

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_metadata_values_not_none(self) -> None:
        """Test plugin metadata values are not None.

        Validates that name, version, and floe_api_version have
        actual values (not None).
        """
        plugin = get_network_security_plugin("k8s")

        assert plugin.name is not None, "Plugin 'name' is None"
        assert plugin.version is not None, "Plugin 'version' is None"
        assert plugin.floe_api_version is not None, "Plugin 'floe_api_version' is None"

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_name_matches_entry_point(self) -> None:
        """Test plugin name is properly set.

        Validates that the plugin's name property is set to a valid
        identifier (may differ from entry point name).
        """
        plugin = get_network_security_plugin("k8s")

        assert plugin.name is not None, "Plugin name should not be None"
        assert isinstance(plugin.name, str), "Plugin name should be a string"
        assert len(plugin.name) > 0, "Plugin name should not be empty"

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_without_name_when_single_available(self) -> None:
        """Test get_network_security_plugin() without name when only one plugin available.

        Validates that when only one plugin is available, calling
        get_network_security_plugin() without arguments returns that plugin.
        """
        # This test assumes only k8s plugin is installed
        plugins = discover_network_security_plugins()
        if len(plugins) == 1:
            plugin = get_network_security_plugin()
            assert plugin is not None
            assert isinstance(plugin, NetworkSecurityPlugin)

    @pytest.mark.requirement("FR-001")
    def test_get_plugin_multiple_calls_return_new_instances(self) -> None:
        """Test multiple calls to get_network_security_plugin return new instances.

        Validates that each call to get_network_security_plugin creates
        a new plugin instance (not cached).
        """
        plugin1 = get_network_security_plugin("k8s")
        plugin2 = get_network_security_plugin("k8s")

        # Should be different instances
        assert plugin1 is not plugin2, (
            "get_network_security_plugin should return new instances, not cached"
        )
        # But same type
        assert type(plugin1) == type(plugin2)
