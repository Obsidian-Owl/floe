"""Unit tests for default-deny NetworkPolicy generation.

Task: T020
Phase: 3 - Default Deny Policies (US1)
User Story: US1 - Default Deny Network Isolation for Jobs
Requirement: FR-010, FR-011, FR-030
"""

from __future__ import annotations

import pytest


class TestDefaultDenyPolicyGeneration:
    """Unit tests for default-deny NetworkPolicy generation."""

    @pytest.mark.requirement("FR-010")
    def test_generate_default_deny_returns_list(self) -> None:
        """Test that generate_default_deny_policies returns a list."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        assert isinstance(policies, list)
        assert len(policies) >= 1

    @pytest.mark.requirement("FR-010")
    def test_default_deny_has_correct_api_version(self) -> None:
        """Test that default-deny policy has correct K8s API version."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            assert policy["apiVersion"] == "networking.k8s.io/v1"

    @pytest.mark.requirement("FR-010")
    def test_default_deny_has_correct_kind(self) -> None:
        """Test that default-deny policy has correct K8s kind."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            assert policy["kind"] == "NetworkPolicy"

    @pytest.mark.requirement("FR-010")
    def test_default_deny_targets_correct_namespace(self) -> None:
        """Test that default-deny policy targets the specified namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        namespace = "floe-jobs"
        policies = plugin.generate_default_deny_policies(namespace)

        for policy in policies:
            assert policy["metadata"]["namespace"] == namespace

    @pytest.mark.requirement("FR-010")
    def test_default_deny_has_empty_pod_selector(self) -> None:
        """Test that default-deny applies to all pods (empty podSelector)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            assert policy["spec"]["podSelector"] == {}

    @pytest.mark.requirement("FR-010")
    def test_default_deny_includes_ingress_policy_type(self) -> None:
        """Test that default-deny includes Ingress in policyTypes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        # At least one policy should include Ingress
        policy_types = []
        for policy in policies:
            policy_types.extend(policy["spec"]["policyTypes"])

        assert "Ingress" in policy_types

    @pytest.mark.requirement("FR-011")
    def test_default_deny_includes_egress_policy_type(self) -> None:
        """Test that default-deny includes Egress in policyTypes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        # At least one policy should include Egress
        policy_types = []
        for policy in policies:
            policy_types.extend(policy["spec"]["policyTypes"])

        assert "Egress" in policy_types

    @pytest.mark.requirement("FR-010")
    def test_default_deny_has_empty_ingress_rules(self) -> None:
        """Test that default-deny has empty ingress rules (blocks all)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            if "Ingress" in policy["spec"]["policyTypes"]:
                # Empty ingress list means deny all ingress
                assert policy["spec"]["ingress"] == []

    @pytest.mark.requirement("FR-011")
    def test_default_deny_has_empty_egress_rules(self) -> None:
        """Test that default-deny has empty egress rules (blocks all)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            if "Egress" in policy["spec"]["policyTypes"]:
                # Empty egress list means deny all egress
                assert policy["spec"]["egress"] == []

    @pytest.mark.requirement("FR-090")
    def test_default_deny_has_managed_by_label(self) -> None:
        """Test that default-deny policy has managed-by label."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            assert "labels" in policy["metadata"]
            assert policy["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-030")
    def test_default_deny_works_for_jobs_namespace(self) -> None:
        """Test that default-deny works specifically for floe-jobs namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        assert len(policies) >= 1
        assert policies[0]["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-010")
    def test_default_deny_works_for_platform_namespace(self) -> None:
        """Test that default-deny works for floe-platform namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-platform")

        assert len(policies) >= 1
        assert policies[0]["metadata"]["namespace"] == "floe-platform"

    @pytest.mark.requirement("FR-010")
    def test_default_deny_policy_name_format(self) -> None:
        """Test that default-deny policy has a descriptive name."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-jobs")

        for policy in policies:
            name = policy["metadata"]["name"]
            # Name should be descriptive
            assert "deny" in name.lower() or "default" in name.lower()
