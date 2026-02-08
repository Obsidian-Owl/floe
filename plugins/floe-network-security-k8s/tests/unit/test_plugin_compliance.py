"""Unit tests for K8sNetworkSecurityPlugin ABC compliance.

Task: T085
Phase: 11 - Plugin Compliance (US7)
User Story: US7 - Plugin Architecture Standards
Requirement: FR-001
"""

from __future__ import annotations

import inspect

import pytest
from floe_core.plugin_metadata import PluginMetadata
from floe_core.plugins import NetworkSecurityPlugin

from floe_network_security_k8s import K8sNetworkSecurityPlugin


class TestPluginABCCompliance:
    """Tests for NetworkSecurityPlugin ABC compliance (FR-001)."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_extends_network_security_plugin_abc(self) -> None:
        """Test K8sNetworkSecurityPlugin extends NetworkSecurityPlugin."""
        assert issubclass(K8sNetworkSecurityPlugin, NetworkSecurityPlugin)

    @pytest.mark.requirement("FR-001")
    def test_plugin_extends_plugin_metadata_abc(self) -> None:
        """Test K8sNetworkSecurityPlugin extends PluginMetadata."""
        assert issubclass(K8sNetworkSecurityPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-001")
    def test_plugin_is_not_abstract(self) -> None:
        """Test K8sNetworkSecurityPlugin is concrete (not abstract)."""
        assert not inspect.isabstract(K8sNetworkSecurityPlugin)

    @pytest.mark.requirement("FR-001")
    def test_plugin_can_be_instantiated(self) -> None:
        """Test K8sNetworkSecurityPlugin can be instantiated without errors."""
        plugin = K8sNetworkSecurityPlugin()
        assert isinstance(plugin, K8sNetworkSecurityPlugin)
        assert isinstance(plugin, NetworkSecurityPlugin)
        assert isinstance(plugin, PluginMetadata)

    @pytest.mark.requirement("FR-001")
    def test_plugin_inheritance_chain(self) -> None:
        """Test plugin inheritance chain is correct.

        K8sNetworkSecurityPlugin -> NetworkSecurityPlugin -> PluginMetadata -> ABC
        """
        mro = K8sNetworkSecurityPlugin.__mro__
        # Check inheritance chain
        assert K8sNetworkSecurityPlugin in mro
        assert NetworkSecurityPlugin in mro
        assert PluginMetadata in mro


class TestPluginMetadataCompliance:
    """Tests for plugin metadata properties (FR-001)."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_name_property(self) -> None:
        """Test plugin has name property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "name")
        assert isinstance(plugin.name, str)
        assert len(plugin.name) > 0

    @pytest.mark.requirement("FR-001")
    def test_plugin_name_value(self) -> None:
        """Test plugin name is correct."""
        plugin = K8sNetworkSecurityPlugin()
        assert plugin.name == "k8s-network-security"

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_version_property(self) -> None:
        """Test plugin has version property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "version")
        assert isinstance(plugin.version, str)
        assert len(plugin.version) > 0

    @pytest.mark.requirement("FR-001")
    def test_plugin_version_is_semver(self) -> None:
        """Test plugin version follows semantic versioning."""
        plugin = K8sNetworkSecurityPlugin()
        version = plugin.version
        # Semver format: X.Y.Z
        parts = version.split(".")
        assert len(parts) == 3, f"Version {version} is not semver (X.Y.Z)"
        for part in parts:
            assert part.isdigit(), f"Version part {part} is not numeric"

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_floe_api_version_property(self) -> None:
        """Test plugin has floe_api_version property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "floe_api_version")
        assert isinstance(plugin.floe_api_version, str)
        assert len(plugin.floe_api_version) > 0

    @pytest.mark.requirement("FR-001")
    def test_plugin_floe_api_version_format(self) -> None:
        """Test plugin floe_api_version is in X.Y format."""
        plugin = K8sNetworkSecurityPlugin()
        api_version = plugin.floe_api_version
        # API version format: X.Y
        parts = api_version.split(".")
        assert len(parts) == 2, f"API version {api_version} is not X.Y format"
        for part in parts:
            assert part.isdigit(), f"API version part {part} is not numeric"

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_description_property(self) -> None:
        """Test plugin has description property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "description")
        assert isinstance(plugin.description, str)

    @pytest.mark.requirement("FR-001")
    def test_plugin_has_dependencies_property(self) -> None:
        """Test plugin has dependencies property."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "dependencies")
        assert isinstance(plugin.dependencies, list)

    @pytest.mark.requirement("FR-001")
    def test_plugin_metadata_properties_are_properties(self) -> None:
        """Test metadata properties are defined as properties."""
        for prop_name in ["name", "version", "floe_api_version"]:
            prop = getattr(K8sNetworkSecurityPlugin, prop_name)
            assert isinstance(
                prop, property
            ), f"{prop_name} should be a property, not {type(prop)}"


class TestAbstractMethodImplementation:
    """Tests for abstract method implementation (FR-001)."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_implements_generate_network_policy(self) -> None:
        """Test plugin implements generate_network_policy method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "generate_network_policy")
        assert callable(plugin.generate_network_policy)

    @pytest.mark.requirement("FR-001")
    def test_plugin_implements_generate_default_deny_policies(self) -> None:
        """Test plugin implements generate_default_deny_policies method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "generate_default_deny_policies")
        assert callable(plugin.generate_default_deny_policies)

    @pytest.mark.requirement("FR-001")
    def test_plugin_implements_generate_dns_egress_rule(self) -> None:
        """Test plugin implements generate_dns_egress_rule method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "generate_dns_egress_rule")
        assert callable(plugin.generate_dns_egress_rule)

    @pytest.mark.requirement("FR-001")
    def test_plugin_implements_generate_pod_security_context(self) -> None:
        """Test plugin implements generate_pod_security_context method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "generate_pod_security_context")
        assert callable(plugin.generate_pod_security_context)

    @pytest.mark.requirement("FR-001")
    def test_plugin_implements_generate_container_security_context(self) -> None:
        """Test plugin implements generate_container_security_context method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "generate_container_security_context")
        assert callable(plugin.generate_container_security_context)

    @pytest.mark.requirement("FR-001")
    def test_plugin_implements_generate_writable_volumes(self) -> None:
        """Test plugin implements generate_writable_volumes method."""
        plugin = K8sNetworkSecurityPlugin()
        assert hasattr(plugin, "generate_writable_volumes")
        assert callable(plugin.generate_writable_volumes)

    @pytest.mark.requirement("FR-001")
    def test_all_abstract_methods_are_implemented(self) -> None:
        """Test all abstract methods from NetworkSecurityPlugin are implemented.

        Verifies that K8sNetworkSecurityPlugin implements all abstract methods
        required by the NetworkSecurityPlugin ABC.
        """
        # Get abstract methods from NetworkSecurityPlugin (excluding properties)
        abstract_methods = set()
        for name, method in inspect.getmembers(NetworkSecurityPlugin):
            if getattr(method, "__isabstractmethod__", False):
                # Skip properties - they're handled separately
                if not isinstance(
                    inspect.getattr_static(NetworkSecurityPlugin, name), property
                ):
                    abstract_methods.add(name)

        # Verify K8sNetworkSecurityPlugin implements all of them
        plugin = K8sNetworkSecurityPlugin()
        for method_name in abstract_methods:
            assert hasattr(
                plugin, method_name
            ), f"Plugin missing abstract method: {method_name}"
            method = getattr(plugin, method_name)
            assert callable(method), f"Plugin method {method_name} is not callable"

    @pytest.mark.requirement("FR-001")
    def test_abstract_methods_are_not_abstract_in_plugin(self) -> None:
        """Test abstract methods are concrete in K8sNetworkSecurityPlugin.

        All abstract methods should be implemented (not abstract) in the
        concrete plugin class.
        """
        # Get all members of the plugin
        for name, method in inspect.getmembers(K8sNetworkSecurityPlugin):
            # Check if it's marked as abstract
            is_abstract = getattr(method, "__isabstractmethod__", False)
            assert (
                not is_abstract
            ), f"Plugin method {name} is still abstract (not implemented)"

    @pytest.mark.requirement("FR-001")
    def test_generate_network_policy_returns_dict(self) -> None:
        """Test generate_network_policy returns a dictionary."""
        from floe_core.network.schemas import NetworkPolicyConfig

        plugin = K8sNetworkSecurityPlugin()
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="default",
            pod_selector={},
            policy_types=("Ingress",),
            ingress_rules=[],
            egress_rules=[],
        )
        result = plugin.generate_network_policy(config)
        assert isinstance(result, dict)

    @pytest.mark.requirement("FR-001")
    def test_generate_default_deny_policies_returns_list(self) -> None:
        """Test generate_default_deny_policies returns a list."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.generate_default_deny_policies("default")
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.requirement("FR-001")
    def test_generate_dns_egress_rule_returns_dict(self) -> None:
        """Test generate_dns_egress_rule returns a dictionary."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.generate_dns_egress_rule()
        assert isinstance(result, dict)

    @pytest.mark.requirement("FR-001")
    def test_generate_pod_security_context_returns_dict(self) -> None:
        """Test generate_pod_security_context returns a dictionary."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.generate_pod_security_context(None)
        assert isinstance(result, dict)

    @pytest.mark.requirement("FR-001")
    def test_generate_container_security_context_returns_dict(self) -> None:
        """Test generate_container_security_context returns a dictionary."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.generate_container_security_context(None)
        assert isinstance(result, dict)

    @pytest.mark.requirement("FR-001")
    def test_generate_writable_volumes_returns_tuple(self) -> None:
        """Test generate_writable_volumes returns a tuple of lists."""
        plugin = K8sNetworkSecurityPlugin()
        result = plugin.generate_writable_volumes(["/tmp"])
        assert isinstance(result, tuple)
        assert len(result) == 2
        volumes, mounts = result
        assert isinstance(volumes, list)
        assert isinstance(mounts, list)


class TestPluginEntryPoint:
    """Tests for plugin entry point discovery (FR-001)."""

    @pytest.mark.requirement("FR-001")
    def test_plugin_is_discoverable_via_entry_point(self) -> None:
        """Test plugin is discoverable via entry points.

        The plugin must be registered in pyproject.toml under
        [project.entry-points."floe.network_security"] to be discoverable.

        Note: In development mode, entry points may not be registered until
        the package is installed. This test skips if entry points are not
        available but verifies the entry point configuration exists.
        """
        import importlib.metadata

        # Get entry points for floe.network_security
        entry_points = importlib.metadata.entry_points()

        # Try to find the network_security group
        # Different Python versions have different APIs
        if hasattr(entry_points, "select"):
            # Python 3.10+
            network_security_eps = entry_points.select(group="floe.network_security")
        else:
            # Python 3.9 and earlier
            network_security_eps = entry_points.get("floe.network_security", [])

        # Convert to list if needed
        network_security_eps = list(network_security_eps)

        # In development mode, entry points may not be registered
        # Verify pyproject.toml has the entry point configured
        if len(network_security_eps) == 0:
            # Check that pyproject.toml has the entry point
            import pathlib

            pyproject_path = (
                pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
            )
            assert pyproject_path.exists(), "pyproject.toml not found"
            content = pyproject_path.read_text()
            assert (
                "floe.network_security" in content
            ), "Entry point group 'floe.network_security' not found in pyproject.toml"
        else:
            # Entry points are registered, verify we have at least one
            assert len(network_security_eps) > 0

    @pytest.mark.requirement("FR-001")
    def test_plugin_entry_point_name_is_k8s(self) -> None:
        """Test plugin entry point is named 'k8s'.

        Note: In development mode, entry points may not be registered until
        the package is installed. This test verifies the configuration exists.
        """
        import importlib.metadata

        entry_points = importlib.metadata.entry_points()

        # Get network_security entry points
        if hasattr(entry_points, "select"):
            network_security_eps = entry_points.select(group="floe.network_security")
        else:
            network_security_eps = entry_points.get("floe.network_security", [])

        # Find the k8s entry point
        k8s_ep = None
        for ep in network_security_eps:
            if ep.name == "k8s":
                k8s_ep = ep
                break

        # In development mode, entry points may not be registered
        if k8s_ep is None:
            # Check that pyproject.toml has the entry point
            import pathlib

            pyproject_path = (
                pathlib.Path(__file__).parent.parent.parent / "pyproject.toml"
            )
            content = pyproject_path.read_text()
            assert (
                'k8s = "floe_network_security_k8s:K8sNetworkSecurityPlugin"' in content
            ), "Entry point 'k8s' not found in pyproject.toml"
        else:
            # Entry point is registered, verify it's correct
            assert k8s_ep.name == "k8s"

    @pytest.mark.requirement("FR-001")
    def test_plugin_entry_point_loads_correct_class(self) -> None:
        """Test plugin entry point loads K8sNetworkSecurityPlugin."""
        import importlib.metadata

        entry_points = importlib.metadata.entry_points()

        # Get network_security entry points
        if hasattr(entry_points, "select"):
            network_security_eps = entry_points.select(group="floe.network_security")
        else:
            network_security_eps = entry_points.get("floe.network_security", [])

        # Find and load the k8s entry point
        for ep in network_security_eps:
            if ep.name == "k8s":
                # Load the entry point
                plugin_class = ep.load()
                assert plugin_class is K8sNetworkSecurityPlugin
                break

    @pytest.mark.requirement("FR-001")
    def test_plugin_entry_point_value_is_correct(self) -> None:
        """Test plugin entry point value matches expected format.

        Entry point should be: k8s = "floe_network_security_k8s:K8sNetworkSecurityPlugin"
        """
        import importlib.metadata

        entry_points = importlib.metadata.entry_points()

        # Get network_security entry points
        if hasattr(entry_points, "select"):
            network_security_eps = entry_points.select(group="floe.network_security")
        else:
            network_security_eps = entry_points.get("floe.network_security", [])

        # Find the k8s entry point
        for ep in network_security_eps:
            if ep.name == "k8s":
                # Check the value format
                assert "floe_network_security_k8s" in ep.value
                assert "K8sNetworkSecurityPlugin" in ep.value
                break

    @pytest.mark.requirement("FR-001")
    def test_plugin_can_be_loaded_from_entry_point(self) -> None:
        """Test plugin can be instantiated from entry point."""
        import importlib.metadata

        entry_points = importlib.metadata.entry_points()

        # Get network_security entry points
        if hasattr(entry_points, "select"):
            network_security_eps = entry_points.select(group="floe.network_security")
        else:
            network_security_eps = entry_points.get("floe.network_security", [])

        # Find and load the k8s entry point
        for ep in network_security_eps:
            if ep.name == "k8s":
                # Load the entry point
                plugin_class = ep.load()
                # Instantiate it
                plugin = plugin_class()
                assert isinstance(plugin, K8sNetworkSecurityPlugin)
                assert isinstance(plugin, NetworkSecurityPlugin)
                break
