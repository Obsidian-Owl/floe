"""Contract tests for NetworkPolicy schema stability.

These tests validate the NetworkPolicy-related Pydantic schemas.
TDD: Written FIRST, expected to FAIL until T008-T011 are implemented.

Task: T007
Epic: 7C - Network and Pod Security
Contract: specs/7c-network-pod-security/data-model.md
"""

from __future__ import annotations

import pytest


class TestPortRuleSchema:
    """Contract tests for PortRule schema."""

    @pytest.mark.requirement("FR-001")
    def test_port_rule_basic_construction(self) -> None:
        """Contract: PortRule accepts port and protocol."""
        from floe_core.network import PortRule

        rule = PortRule(port=443)
        assert rule.port == 443
        assert rule.protocol == "TCP"

    @pytest.mark.requirement("FR-001")
    def test_port_rule_udp_protocol(self) -> None:
        """Contract: PortRule accepts UDP protocol."""
        from floe_core.network import PortRule

        rule = PortRule(port=53, protocol="UDP")
        assert rule.protocol == "UDP"

    @pytest.mark.requirement("FR-001")
    def test_port_rule_port_bounds(self) -> None:
        """Contract: Port must be in valid range."""
        from floe_core.network import PortRule
        from pydantic import ValidationError

        PortRule(port=1)
        PortRule(port=65535)

        with pytest.raises(ValidationError):
            PortRule(port=0)

        with pytest.raises(ValidationError):
            PortRule(port=65536)


class TestEgressRuleSchema:
    """Contract tests for EgressRule schema."""

    @pytest.mark.requirement("FR-001")
    def test_egress_rule_with_namespace(self) -> None:
        """Contract: EgressRule accepts to_namespace."""
        from floe_core.network import EgressRule, PortRule

        rule = EgressRule(
            to_namespace="kube-system", ports=[PortRule(port=53, protocol="UDP")]
        )
        assert rule.to_namespace == "kube-system"
        assert rule.to_cidr is None

    @pytest.mark.requirement("FR-001")
    def test_egress_rule_with_cidr(self) -> None:
        """Contract: EgressRule accepts to_cidr."""
        from floe_core.network import EgressRule, PortRule

        rule = EgressRule(to_cidr="0.0.0.0/0", ports=[PortRule(port=443)])
        assert rule.to_cidr == "0.0.0.0/0"
        assert rule.to_namespace is None

    @pytest.mark.requirement("FR-001")
    def test_egress_rule_requires_ports(self) -> None:
        """Contract: EgressRule requires ports."""
        from floe_core.network import EgressRule
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EgressRule(to_namespace="kube-system")

    @pytest.mark.requirement("FR-001")
    def test_egress_rule_mutual_exclusion(self) -> None:
        """Contract: to_namespace and to_cidr are mutually exclusive."""
        from floe_core.network import EgressRule, PortRule
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EgressRule(
                to_namespace="kube-system",
                to_cidr="0.0.0.0/0",
                ports=[PortRule(port=53)],
            )


class TestIngressRuleSchema:
    """Contract tests for IngressRule schema."""

    @pytest.mark.requirement("FR-001")
    def test_ingress_rule_with_namespace(self) -> None:
        """Contract: IngressRule accepts from_namespace."""
        from floe_core.network import IngressRule

        rule = IngressRule(from_namespace="ingress-nginx")
        assert rule.from_namespace == "ingress-nginx"

    @pytest.mark.requirement("FR-001")
    def test_ingress_rule_with_pod_labels(self) -> None:
        """Contract: IngressRule accepts from_pod_labels."""
        from floe_core.network import IngressRule

        rule = IngressRule(from_pod_labels={"app": "frontend"})
        assert rule.from_pod_labels == {"app": "frontend"}

    @pytest.mark.requirement("FR-001")
    def test_ingress_rule_with_ports(self) -> None:
        """Contract: IngressRule accepts optional ports."""
        from floe_core.network import IngressRule, PortRule

        rule = IngressRule(from_namespace="ingress-nginx", ports=[PortRule(port=8080)])
        assert len(rule.ports) == 1


class TestNetworkPolicyConfigSchema:
    """Contract tests for NetworkPolicyConfig schema."""

    @pytest.mark.requirement("FR-001")
    def test_network_policy_config_basic(self) -> None:
        """Contract: NetworkPolicyConfig accepts required fields."""
        from floe_core.network import NetworkPolicyConfig

        config = NetworkPolicyConfig(
            name="floe-jobs-default-deny",
            namespace="floe-jobs",
            policy_types=["Egress"],
        )
        assert config.name == "floe-jobs-default-deny"
        assert config.namespace == "floe-jobs"
        assert "Egress" in config.policy_types

    @pytest.mark.requirement("FR-001")
    def test_network_policy_config_name_pattern(self) -> None:
        """Contract: Name must match floe-* pattern."""
        from floe_core.network import NetworkPolicyConfig
        from pydantic import ValidationError

        NetworkPolicyConfig(
            name="floe-jobs-deny", namespace="floe-jobs", policy_types=["Egress"]
        )

        with pytest.raises(ValidationError):
            NetworkPolicyConfig(
                name="invalid-name", namespace="floe-jobs", policy_types=["Egress"]
            )

    @pytest.mark.requirement("FR-001")
    def test_network_policy_config_pod_selector_default(self) -> None:
        """Contract: pod_selector defaults to empty dict (all pods)."""
        from floe_core.network import NetworkPolicyConfig

        config = NetworkPolicyConfig(
            name="floe-jobs-deny", namespace="floe-jobs", policy_types=["Egress"]
        )
        assert config.pod_selector == {}

    @pytest.mark.requirement("FR-001")
    def test_network_policy_config_to_k8s_manifest(self) -> None:
        """Contract: to_k8s_manifest returns valid K8s NetworkPolicy."""
        from floe_core.network import EgressRule, NetworkPolicyConfig, PortRule

        config = NetworkPolicyConfig(
            name="floe-jobs-allow-dns",
            namespace="floe-jobs",
            policy_types=["Egress"],
            egress_rules=[
                EgressRule(
                    to_namespace="kube-system",
                    ports=[PortRule(port=53, protocol="UDP")],
                )
            ],
        )

        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "networking.k8s.io/v1"
        assert manifest["kind"] == "NetworkPolicy"
        assert manifest["metadata"]["name"] == "floe-jobs-allow-dns"
        assert manifest["metadata"]["namespace"] == "floe-jobs"
        assert "spec" in manifest
        assert "policyTypes" in manifest["spec"]
        assert "Egress" in manifest["spec"]["policyTypes"]

    @pytest.mark.requirement("FR-090")
    def test_network_policy_manifest_has_managed_by_label(self) -> None:
        """Contract: Generated manifest includes managed-by label."""
        from floe_core.network import NetworkPolicyConfig

        config = NetworkPolicyConfig(
            name="floe-jobs-deny", namespace="floe-jobs", policy_types=["Egress"]
        )

        manifest = config.to_k8s_manifest()

        assert manifest["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"


class TestNetworkPolicyConfigDefaultDeny:
    """Contract tests for default-deny policy generation."""

    @pytest.mark.requirement("FR-010")
    def test_default_deny_egress_has_empty_rules(self) -> None:
        """Contract: Default-deny egress has empty egress_rules."""
        from floe_core.network import NetworkPolicyConfig

        config = NetworkPolicyConfig(
            name="floe-jobs-default-deny-egress",
            namespace="floe-jobs",
            policy_types=["Egress"],
            egress_rules=[],
        )

        manifest = config.to_k8s_manifest()

        assert manifest["spec"]["egress"] == []

    @pytest.mark.requirement("FR-011")
    def test_default_deny_ingress_has_empty_rules(self) -> None:
        """Contract: Default-deny ingress has empty ingress_rules."""
        from floe_core.network import NetworkPolicyConfig

        config = NetworkPolicyConfig(
            name="floe-jobs-default-deny-ingress",
            namespace="floe-jobs",
            policy_types=["Ingress"],
            ingress_rules=[],
        )

        manifest = config.to_k8s_manifest()

        assert manifest["spec"]["ingress"] == []


class TestNetworkPolicySchemaJsonExport:
    """Contract tests for JSON Schema export."""

    @pytest.mark.requirement("FR-001")
    def test_network_policies_config_json_schema(self) -> None:
        """Contract: NetworkPoliciesConfig exports valid JSON Schema."""
        from floe_core.network import NetworkPoliciesConfig

        schema = NetworkPoliciesConfig.model_json_schema()

        assert schema["title"] == "NetworkPoliciesConfig"
        assert "properties" in schema
        assert "enabled" in schema["properties"]
        assert "default_deny" in schema["properties"]

    @pytest.mark.requirement("FR-001")
    def test_network_policy_config_json_schema(self) -> None:
        """Contract: NetworkPolicyConfig exports valid JSON Schema."""
        from floe_core.network import NetworkPolicyConfig

        schema = NetworkPolicyConfig.model_json_schema()

        assert schema["title"] == "NetworkPolicyConfig"
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "namespace" in schema["properties"]
        assert "policy_types" in schema["properties"]
