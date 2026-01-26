"""Contract tests for NetworkSecurityPlugin ABC.

These tests validate the NetworkSecurityPlugin abstract base class interface.
TDD: Written FIRST, expected to FAIL until T014-T016 are implemented.

Task: T006
Epic: 7C - Network and Pod Security
Contract: specs/7c-network-pod-security/contracts/network-security-plugin-interface.md
"""

from __future__ import annotations

from abc import ABC
from typing import Any

import pytest


class TestNetworkSecurityPluginABCStructure:
    """Contract tests for NetworkSecurityPlugin ABC structure."""

    @pytest.mark.requirement("FR-001")
    def test_network_security_plugin_is_abstract(self) -> None:
        """Contract: NetworkSecurityPlugin is an abstract base class."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert issubclass(NetworkSecurityPlugin, ABC)

    @pytest.mark.requirement("FR-001")
    def test_network_security_plugin_cannot_instantiate(self) -> None:
        """Contract: NetworkSecurityPlugin cannot be instantiated directly."""
        from floe_core.plugins import NetworkSecurityPlugin

        with pytest.raises(TypeError):
            NetworkSecurityPlugin()  # type: ignore[abstract]

    @pytest.mark.requirement("FR-001")
    def test_network_security_plugin_has_metadata_properties(self) -> None:
        """Contract: NetworkSecurityPlugin has name, version, floe_api_version."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "name")
        assert hasattr(NetworkSecurityPlugin, "version")
        assert hasattr(NetworkSecurityPlugin, "floe_api_version")


class TestNetworkSecurityPluginNetworkPolicyMethods:
    """Contract tests for NetworkPolicy generation methods."""

    @pytest.mark.requirement("FR-001")
    def test_generate_network_policy_method_exists(self) -> None:
        """Contract: NetworkSecurityPlugin has generate_network_policy method."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "generate_network_policy")

    @pytest.mark.requirement("FR-010")
    def test_generate_default_deny_policies_method_exists(self) -> None:
        """Contract: NetworkSecurityPlugin has generate_default_deny_policies method."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "generate_default_deny_policies")

    @pytest.mark.requirement("FR-012")
    def test_generate_dns_egress_rule_method_exists(self) -> None:
        """Contract: NetworkSecurityPlugin has generate_dns_egress_rule method."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "generate_dns_egress_rule")


class TestNetworkSecurityPluginSecurityContextMethods:
    """Contract tests for SecurityContext generation methods."""

    @pytest.mark.requirement("FR-060")
    def test_generate_pod_security_context_method_exists(self) -> None:
        """Contract: NetworkSecurityPlugin has generate_pod_security_context method."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "generate_pod_security_context")

    @pytest.mark.requirement("FR-061")
    def test_generate_container_security_context_method_exists(self) -> None:
        """Contract: NetworkSecurityPlugin has generate_container_security_context method."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "generate_container_security_context")

    @pytest.mark.requirement("FR-063")
    def test_generate_writable_volumes_method_exists(self) -> None:
        """Contract: NetworkSecurityPlugin has generate_writable_volumes method."""
        from floe_core.plugins import NetworkSecurityPlugin

        assert hasattr(NetworkSecurityPlugin, "generate_writable_volumes")


class TestK8sNetworkSecurityPluginCompliance:
    """Contract tests for K8sNetworkSecurityPlugin implementation."""

    @pytest.mark.requirement("FR-001")
    def test_k8s_plugin_implements_abc(self) -> None:
        """Contract: K8sNetworkSecurityPlugin implements NetworkSecurityPlugin."""
        from floe_core.plugins import NetworkSecurityPlugin
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        assert isinstance(plugin, NetworkSecurityPlugin)

    @pytest.mark.requirement("FR-001")
    def test_k8s_plugin_has_metadata(self) -> None:
        """Contract: K8sNetworkSecurityPlugin has valid metadata."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        assert plugin.name == "k8s-network-security"
        assert plugin.version == "0.1.0"
        assert plugin.floe_api_version == "1.0"

    @pytest.mark.requirement("FR-012")
    def test_dns_egress_rule_output_structure(self) -> None:
        """Contract: generate_dns_egress_rule returns K8s egress rule structure."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        assert "to" in rule
        assert "ports" in rule

        assert any(p.get("port") == 53 for p in rule["ports"])
        assert any(p.get("protocol") == "UDP" for p in rule["ports"])

    @pytest.mark.requirement("FR-010")
    def test_default_deny_policies_output_structure(self) -> None:
        """Contract: generate_default_deny_policies returns list of K8s NetworkPolicy."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        assert isinstance(policies, list)
        assert len(policies) >= 1

        for policy in policies:
            assert policy["apiVersion"] == "networking.k8s.io/v1"
            assert policy["kind"] == "NetworkPolicy"
            assert "metadata" in policy
            assert policy["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-060")
    def test_pod_security_context_output(self) -> None:
        """Contract: generate_pod_security_context returns valid K8s securityContext."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        context = plugin.generate_pod_security_context(None)

        assert context["runAsNonRoot"] is True
        assert context["runAsUser"] == 1000
        assert context["runAsGroup"] == 1000
        assert context["fsGroup"] == 1000
        assert context["seccompProfile"]["type"] == "RuntimeDefault"

    @pytest.mark.requirement("FR-061")
    def test_container_security_context_output(self) -> None:
        """Contract: generate_container_security_context returns hardened settings."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        context = plugin.generate_container_security_context(None)

        assert context["allowPrivilegeEscalation"] is False
        assert context["readOnlyRootFilesystem"] is True
        assert "ALL" in context["capabilities"]["drop"]

    @pytest.mark.requirement("FR-063")
    def test_writable_volumes_output(self) -> None:
        """Contract: generate_writable_volumes returns volumes and volumeMounts."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        volumes, mounts = plugin.generate_writable_volumes(["/tmp", "/home/floe"])

        assert len(volumes) == 2
        assert len(mounts) == 2

        for vol in volumes:
            assert "name" in vol
            assert "emptyDir" in vol

        mount_paths = [m["mountPath"] for m in mounts]
        assert "/tmp" in mount_paths
        assert "/home/floe" in mount_paths


class TestNetworkSecurityPluginEntryPoint:
    """Contract tests for plugin entry point discovery."""

    @pytest.mark.requirement("FR-001")
    def test_entry_point_discoverable(self) -> None:
        """Contract: K8sNetworkSecurityPlugin is discoverable via entry points."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.network_security")
        ep_names = [ep.name for ep in eps]

        assert "k8s" in ep_names

    @pytest.mark.requirement("FR-001")
    def test_entry_point_loads_plugin(self) -> None:
        """Contract: Entry point loads K8sNetworkSecurityPlugin class."""
        from importlib.metadata import entry_points

        eps = entry_points(group="floe.network_security")
        k8s_ep = next(ep for ep in eps if ep.name == "k8s")

        plugin_class = k8s_ep.load()
        assert plugin_class.__name__ == "K8sNetworkSecurityPlugin"
