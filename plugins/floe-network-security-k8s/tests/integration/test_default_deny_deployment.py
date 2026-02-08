"""Integration tests for default-deny policy deployment.

Task: T022
Phase: 3 - Default Deny Policies (US1)
User Story: US1 - Default Deny Network Isolation for Jobs
Requirements: FR-010 (egress), FR-011 (ingress), FR-012 (DNS allowed)

Prerequisites:
    - Kind cluster running
    - kubectl configured
    - CNI with NetworkPolicy support
"""

from __future__ import annotations

import json
import subprocess
import uuid
from typing import Any

import pytest
import yaml
from testing.base_classes.integration_test_base import IntegrationTestBase


class TestDefaultDenyDeployment(IntegrationTestBase):
    """Tests for deploying default-deny policies to Kind cluster.

    Verifies that NetworkPolicy manifests can be generated and applied
    to a real Kubernetes cluster without errors.
    """

    # No external services required - just K8s API access
    required_services: list[tuple[str, int]] = []

    def _kubectl_available(self) -> bool:
        """Check if kubectl is available and configured."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _create_namespace(self, name: str) -> None:
        """Create a K8s namespace for testing."""
        subprocess.run(
            ["kubectl", "create", "namespace", name],
            capture_output=True,
            check=False,
        )

    def _delete_namespace(self, name: str) -> None:
        """Delete a K8s namespace."""
        subprocess.run(
            ["kubectl", "delete", "namespace", name, "--ignore-not-found"],
            capture_output=True,
            check=False,
        )

    def _apply_policy(self, namespace: str, policy_yaml: str) -> bool:
        """Apply a NetworkPolicy to the cluster.

        Args:
            namespace: Target namespace.
            policy_yaml: YAML string containing policy manifest.

        Returns:
            True if policy was applied successfully, False otherwise.
        """
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=policy_yaml,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def _get_policies(self, namespace: str) -> list[dict[str, Any]]:
        """Get all NetworkPolicies in a namespace.

        Args:
            namespace: Target namespace.

        Returns:
            List of NetworkPolicy manifests.
        """
        result = subprocess.run(
            ["kubectl", "get", "networkpolicy", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        return data.get("items", [])

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_kubectl_available(self) -> None:
        """Test that kubectl is available and configured."""
        assert (
            self._kubectl_available()
        ), "kubectl not available or cluster not accessible"

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_default_deny_policy_applies(self) -> None:
        """Test default-deny policy can be applied to cluster.

        Verifies that the plugin can generate a default-deny policy
        and apply it to a real K8s cluster without errors.
        """
        if not self._kubectl_available():
            pytest.skip("kubectl not available")

        test_namespace = f"test-{uuid.uuid4().hex[:8]}"
        self._create_namespace(test_namespace)

        try:
            # Generate policy using plugin
            from floe_network_security_k8s import K8sNetworkSecurityPlugin

            plugin = K8sNetworkSecurityPlugin()
            policies = plugin.generate_default_deny_policies(test_namespace)

            # Verify policy was generated
            assert len(policies) >= 1, "No policies generated"
            assert policies[0]["kind"] == "NetworkPolicy"
            assert policies[0]["metadata"]["namespace"] == test_namespace

            # Apply policy to cluster
            policy_yaml = yaml.dump_all(policies)
            assert self._apply_policy(
                test_namespace, policy_yaml
            ), "Failed to apply policy"

            # Verify policy exists in cluster
            policies_in_cluster = self._get_policies(test_namespace)
            assert len(policies_in_cluster) >= 1, "Policy not found in cluster"
            assert policies_in_cluster[0]["kind"] == "NetworkPolicy"
        finally:
            self._delete_namespace(test_namespace)

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_default_deny_policy_structure(self) -> None:
        """Test default-deny policy has correct structure.

        Verifies that the generated policy has:
        - Correct apiVersion and kind
        - Empty ingress rules (deny all)
        - Empty egress rules (deny all)
        - Correct labels
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        test_namespace = "test-namespace"
        policies = plugin.generate_default_deny_policies(test_namespace)

        assert len(policies) == 1
        policy = policies[0]

        # Verify structure
        assert policy["apiVersion"] == "networking.k8s.io/v1"
        assert policy["kind"] == "NetworkPolicy"
        assert policy["metadata"]["name"] == "default-deny-all"
        assert policy["metadata"]["namespace"] == test_namespace

        # Verify labels
        assert "app.kubernetes.io/managed-by" in policy["metadata"]["labels"]
        assert policy["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"

        # Verify spec
        spec = policy["spec"]
        assert "Ingress" in spec["policyTypes"]
        assert "Egress" in spec["policyTypes"]
        assert spec["ingress"] == []
        assert spec["egress"] == []
        assert spec["podSelector"] == {}

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_multiple_policies_apply(self) -> None:
        """Test multiple policies can be applied together.

        Verifies that multiple NetworkPolicy manifests can be
        generated and applied in a single operation.
        """
        if not self._kubectl_available():
            pytest.skip("kubectl not available")

        test_namespace = f"test-{uuid.uuid4().hex[:8]}"
        self._create_namespace(test_namespace)

        try:
            from floe_network_security_k8s import K8sNetworkSecurityPlugin

            plugin = K8sNetworkSecurityPlugin()

            # Generate default-deny policy
            policies = plugin.generate_default_deny_policies(test_namespace)

            # Apply all policies
            policy_yaml = yaml.dump_all(policies)
            assert self._apply_policy(
                test_namespace, policy_yaml
            ), "Failed to apply policies"

            # Verify all policies exist
            policies_in_cluster = self._get_policies(test_namespace)
            assert len(policies_in_cluster) >= len(policies)
        finally:
            self._delete_namespace(test_namespace)


class TestDefaultDenyEgress(IntegrationTestBase):
    """Tests for egress blocking in default-deny policies.

    Verifies that the default-deny policy blocks all egress traffic
    except for explicitly allowed rules.
    """

    required_services: list[tuple[str, int]] = []

    def _kubectl_available(self) -> bool:
        """Check if kubectl is available and configured."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _create_namespace(self, name: str) -> None:
        """Create a K8s namespace for testing."""
        subprocess.run(
            ["kubectl", "create", "namespace", name],
            capture_output=True,
            check=False,
        )

    def _delete_namespace(self, name: str) -> None:
        """Delete a K8s namespace."""
        subprocess.run(
            ["kubectl", "delete", "namespace", name, "--ignore-not-found"],
            capture_output=True,
            check=False,
        )

    def _apply_policy(self, namespace: str, policy_yaml: str) -> bool:
        """Apply a NetworkPolicy to the cluster."""
        result = subprocess.run(
            ["kubectl", "apply", "-f", "-"],
            input=policy_yaml,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_egress_blocked_by_default(self) -> None:
        """Test that egress is blocked by default-deny policy.

        Verifies that the default-deny policy has empty egress rules,
        which blocks all outbound traffic.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("test-namespace")

        policy = policies[0]
        spec = policy["spec"]

        # Verify egress is blocked (empty rules)
        assert "Egress" in spec["policyTypes"]
        assert spec["egress"] == [], "Egress should be empty (deny all)"

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_platform_egress_rules_structure(self) -> None:
        """Test platform egress rules have correct structure.

        Verifies that platform egress rules allow communication to:
        - Polaris catalog (TCP 8181)
        - OTel Collector (TCP 4317, 4318)
        - MinIO storage (TCP 9000)
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        assert len(rules) >= 4, "Should have at least 4 platform egress rules"

        # Verify each rule has correct structure
        for rule in rules:
            assert "to" in rule
            assert "ports" in rule
            assert len(rule["to"]) >= 1
            assert len(rule["ports"]) >= 1

            # Verify port structure
            for port_spec in rule["ports"]:
                assert "port" in port_spec
                assert "protocol" in port_spec
                assert port_spec["protocol"] in ["TCP", "UDP"]

        # Verify specific ports are present
        all_ports = []
        for rule in rules:
            for port_spec in rule["ports"]:
                all_ports.append(port_spec["port"])

        assert 8181 in all_ports, "Polaris port (8181) not found"
        assert 4317 in all_ports, "OTel gRPC port (4317) not found"
        assert 4318 in all_ports, "OTel HTTP port (4318) not found"
        assert 9000 in all_ports, "MinIO port (9000) not found"

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_custom_egress_rule_cidr(self) -> None:
        """Test custom egress rule with CIDR block.

        Verifies that custom egress rules can be generated for
        external services via CIDR blocks.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_custom_egress_rule(
            cidr="10.0.0.0/8",
            port=443,
            protocol="TCP",
        )

        assert "to" in rule
        assert "ports" in rule
        assert len(rule["to"]) == 1
        assert "ipBlock" in rule["to"][0]
        assert rule["to"][0]["ipBlock"]["cidr"] == "10.0.0.0/8"
        assert rule["ports"][0]["port"] == 443
        assert rule["ports"][0]["protocol"] == "TCP"

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-010")
    def test_custom_egress_rule_namespace(self) -> None:
        """Test custom egress rule with namespace selector.

        Verifies that custom egress rules can be generated for
        other Kubernetes namespaces.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_custom_egress_rule(
            namespace="external-service",
            port=5432,
            protocol="TCP",
        )

        assert "to" in rule
        assert "ports" in rule
        assert len(rule["to"]) == 1
        assert "namespaceSelector" in rule["to"][0]
        assert (
            rule["to"][0]["namespaceSelector"]["matchLabels"][
                "kubernetes.io/metadata.name"
            ]
            == "external-service"
        )
        assert rule["ports"][0]["port"] == 5432


class TestDefaultDenyIngress(IntegrationTestBase):
    """Tests for ingress blocking in default-deny policies.

    Verifies that the default-deny policy blocks all ingress traffic
    except for explicitly allowed rules.
    """

    required_services: list[tuple[str, int]] = []

    def _kubectl_available(self) -> bool:
        """Check if kubectl is available and configured."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-011")
    def test_ingress_blocked_by_default(self) -> None:
        """Test that ingress is blocked by default-deny policy.

        Verifies that the default-deny policy has empty ingress rules,
        which blocks all inbound traffic.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("test-namespace")

        policy = policies[0]
        spec = policy["spec"]

        # Verify ingress is blocked (empty rules)
        assert "Ingress" in spec["policyTypes"]
        assert spec["ingress"] == [], "Ingress should be empty (deny all)"

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-011")
    def test_ingress_controller_rule_structure(self) -> None:
        """Test ingress controller rule has correct structure.

        Verifies that ingress controller rules allow traffic from
        the ingress-nginx namespace on ports 80, 443, 8080.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_ingress_controller_rule()

        assert "from" in rule
        assert "ports" in rule
        assert len(rule["from"]) >= 1
        assert len(rule["ports"]) >= 3

        # Verify namespace selector
        assert "namespaceSelector" in rule["from"][0]
        assert (
            rule["from"][0]["namespaceSelector"]["matchLabels"][
                "kubernetes.io/metadata.name"
            ]
            == "ingress-nginx"
        )

        # Verify ports
        ports = [p["port"] for p in rule["ports"]]
        assert 80 in ports
        assert 443 in ports
        assert 8080 in ports

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-011")
    def test_jobs_ingress_rule_structure(self) -> None:
        """Test jobs namespace ingress rule has correct structure.

        Verifies that ingress rules allow traffic from floe-jobs
        namespace on platform service ports.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_jobs_ingress_rule()

        assert "from" in rule
        assert "ports" in rule
        assert len(rule["from"]) >= 1

        # Verify namespace selector
        assert "namespaceSelector" in rule["from"][0]
        assert (
            rule["from"][0]["namespaceSelector"]["matchLabels"][
                "kubernetes.io/metadata.name"
            ]
            == "floe-jobs"
        )

        # Verify ports for platform services
        ports = [p["port"] for p in rule["ports"]]
        assert 8181 in ports  # Polaris
        assert 4317 in ports  # OTel gRPC
        assert 4318 in ports  # OTel HTTP
        assert 9000 in ports  # MinIO

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-011")
    def test_intra_namespace_rule_structure(self) -> None:
        """Test intra-namespace communication rule.

        Verifies that intra-namespace rules allow pods within the same
        namespace to communicate with each other.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_intra_namespace_rule("test-namespace")

        assert "from" in rule
        assert len(rule["from"]) >= 1
        # Empty podSelector matches all pods in the namespace
        assert rule["from"][0]["podSelector"] == {}


class TestDnsEgressAllowed(IntegrationTestBase):
    """Tests for DNS egress allowance in default-deny policies.

    Verifies that DNS traffic is always allowed, even with default-deny
    policies, as it's required for service discovery.
    """

    required_services: list[tuple[str, int]] = []

    def _kubectl_available(self) -> bool:
        """Check if kubectl is available and configured."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-012")
    def test_dns_egress_rule_structure(self) -> None:
        """Test DNS egress rule has correct structure.

        Verifies that DNS egress rules allow UDP and TCP on port 53
        to the kube-system namespace.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        assert "to" in rule
        assert "ports" in rule
        assert len(rule["to"]) >= 1
        assert len(rule["ports"]) >= 2

        # Verify namespace selector points to kube-system
        assert "namespaceSelector" in rule["to"][0]
        assert (
            rule["to"][0]["namespaceSelector"]["matchLabels"][
                "kubernetes.io/metadata.name"
            ]
            == "kube-system"
        )

        # Verify both UDP and TCP on port 53
        protocols = {(p["port"], p["protocol"]) for p in rule["ports"]}
        assert (53, "UDP") in protocols
        assert (53, "TCP") in protocols

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-012")
    def test_dns_always_allowed(self) -> None:
        """Test that DNS is always allowed in default-deny policies.

        Verifies that even with default-deny policies, DNS traffic
        is explicitly allowed for service discovery.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # DNS rule should be independent of default-deny policy
        dns_rule = plugin.generate_dns_egress_rule()
        default_deny = plugin.generate_default_deny_policies("test-namespace")

        # DNS rule should exist and be valid
        assert dns_rule is not None
        assert "to" in dns_rule
        assert "ports" in dns_rule

        # Default-deny should have empty egress (deny all)
        assert default_deny[0]["spec"]["egress"] == []

        # DNS rule should be added separately to allow DNS
        assert dns_rule["ports"][0]["port"] == 53

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-012")
    def test_dns_rule_targets_kube_system(self) -> None:
        """Test DNS rule targets kube-system namespace.

        Verifies that DNS egress rules target the kube-system namespace
        where CoreDNS is typically deployed.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Verify it targets kube-system
        assert "to" in rule
        assert len(rule["to"]) >= 1
        assert "namespaceSelector" in rule["to"][0]

        namespace_selector = rule["to"][0]["namespaceSelector"]
        assert "matchLabels" in namespace_selector
        assert (
            namespace_selector["matchLabels"]["kubernetes.io/metadata.name"]
            == "kube-system"
        )

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-012")
    def test_dns_rule_both_protocols(self) -> None:
        """Test DNS rule allows both UDP and TCP.

        Verifies that DNS egress rules allow both UDP (primary) and TCP
        (fallback for large responses) on port 53.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Extract protocols
        protocols = {(p["port"], p["protocol"]) for p in rule["ports"]}

        # Both UDP and TCP should be present
        assert (53, "UDP") in protocols, "UDP port 53 not found"
        assert (53, "TCP") in protocols, "TCP port 53 not found"

    @pytest.mark.k8s
    @pytest.mark.integration
    @pytest.mark.requirement("FR-012")
    def test_dns_rule_port_53(self) -> None:
        """Test DNS rule uses port 53.

        Verifies that DNS egress rules use the standard DNS port (53).
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # All ports should be 53
        for port_spec in rule["ports"]:
            assert port_spec["port"] == 53, f"Expected port 53, got {port_spec['port']}"
