"""Unit tests for egress rule generation.

Task: T023, T025
Phase: 3 - Default Deny Policies (US1)
User Story: US1 - Default Deny Network Isolation for Jobs
Requirement: FR-030, FR-031, FR-032, FR-033
"""

from __future__ import annotations

import pytest


class TestDNSEgressRule:
    """Unit tests for DNS egress rule generation (T023).

    DNS egress is ALWAYS required and cannot be disabled.
    Allows pods to resolve DNS via kube-system CoreDNS.
    """

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_rule_targets_kube_system(self) -> None:
        """Test that DNS egress rule targets kube-system namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Rule should have 'to' field with namespaceSelector
        assert "to" in rule
        assert len(rule["to"]) >= 1

        # Should target kube-system namespace
        namespace_selector = rule["to"][0].get("namespaceSelector", {})
        match_labels = namespace_selector.get("matchLabels", {})
        assert match_labels.get("kubernetes.io/metadata.name") == "kube-system"

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_rule_allows_udp_53(self) -> None:
        """Test that DNS egress rule allows UDP port 53."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Rule should have ports defined
        assert "ports" in rule

        # Find UDP 53 port rule
        udp_53_found = any(
            p.get("port") == 53 and p.get("protocol") == "UDP" for p in rule["ports"]
        )
        assert udp_53_found, "DNS egress must allow UDP port 53"

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_rule_allows_tcp_53_fallback(self) -> None:
        """Test that DNS egress rule allows TCP port 53 for fallback.

        TCP DNS is required when UDP responses are truncated (large responses).
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Rule should have ports defined
        assert "ports" in rule

        # Find TCP 53 port rule
        tcp_53_found = any(
            p.get("port") == 53 and p.get("protocol") == "TCP" for p in rule["ports"]
        )
        assert tcp_53_found, "DNS egress must allow TCP port 53 for fallback"

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_rule_uses_namespace_selector(self) -> None:
        """Test that DNS egress uses namespaceSelector (not podSelector).

        Using namespaceSelector matches all pods in kube-system,
        which is correct for CoreDNS/kube-dns.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Should use namespaceSelector, not podSelector
        assert "to" in rule
        first_to = rule["to"][0]
        assert "namespaceSelector" in first_to

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_rule_structure_valid_for_k8s(self) -> None:
        """Test that DNS egress rule has valid K8s NetworkPolicy egress structure."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        # Valid egress rule structure for K8s NetworkPolicy
        assert isinstance(rule, dict)
        assert "to" in rule
        assert "ports" in rule
        assert isinstance(rule["to"], list)
        assert isinstance(rule["ports"], list)

        # Each port entry should have port and protocol
        for port_entry in rule["ports"]:
            assert "port" in port_entry
            assert "protocol" in port_entry

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_rule_returns_dict(self) -> None:
        """Test that generate_dns_egress_rule returns a dict."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_dns_egress_rule()

        assert isinstance(rule, dict)

    @pytest.mark.requirement("FR-030")
    def test_dns_egress_is_method_on_plugin(self) -> None:
        """Test that generate_dns_egress_rule exists on plugin interface."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # Method should exist and be callable
        assert hasattr(plugin, "generate_dns_egress_rule")
        assert callable(plugin.generate_dns_egress_rule)


class TestPlatformServiceEgressRules:
    """Unit tests for platform service egress rules (T025).

    Jobs need to communicate with:
    - Polaris catalog (port 8181)
    - OTel Collector (ports 4317 gRPC, 4318 HTTP)
    - MinIO storage (port 9000)
    """

    @pytest.mark.requirement("FR-031")
    def test_generate_polaris_egress_rule(self) -> None:
        """Test generation of Polaris catalog egress rule (port 8181)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # Check if method exists - implementation will be in T026
        if hasattr(plugin, "generate_platform_egress_rules"):
            rules = plugin.generate_platform_egress_rules()

            # Find Polaris rule (port 8181)
            polaris_found = any(
                any(p.get("port") == 8181 for p in r.get("ports", [])) for r in rules
            )
            assert polaris_found, "Platform egress must include Polaris (8181)"
        else:
            pytest.skip("generate_platform_egress_rules not yet implemented (T026)")

    @pytest.mark.requirement("FR-031")
    def test_generate_otel_grpc_egress_rule(self) -> None:
        """Test generation of OTel Collector gRPC egress rule (port 4317)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_platform_egress_rules"):
            rules = plugin.generate_platform_egress_rules()

            # Find OTel gRPC rule (port 4317)
            otel_grpc_found = any(
                any(p.get("port") == 4317 for p in r.get("ports", [])) for r in rules
            )
            assert otel_grpc_found, "Platform egress must include OTel gRPC (4317)"
        else:
            pytest.skip("generate_platform_egress_rules not yet implemented (T026)")

    @pytest.mark.requirement("FR-031")
    def test_generate_otel_http_egress_rule(self) -> None:
        """Test generation of OTel Collector HTTP egress rule (port 4318)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_platform_egress_rules"):
            rules = plugin.generate_platform_egress_rules()

            # Find OTel HTTP rule (port 4318)
            otel_http_found = any(
                any(p.get("port") == 4318 for p in r.get("ports", [])) for r in rules
            )
            assert otel_http_found, "Platform egress must include OTel HTTP (4318)"
        else:
            pytest.skip("generate_platform_egress_rules not yet implemented (T026)")

    @pytest.mark.requirement("FR-032")
    def test_generate_minio_egress_rule(self) -> None:
        """Test generation of MinIO storage egress rule (port 9000)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_platform_egress_rules"):
            rules = plugin.generate_platform_egress_rules()

            # Find MinIO rule (port 9000)
            minio_found = any(any(p.get("port") == 9000 for p in r.get("ports", [])) for r in rules)
            assert minio_found, "Platform egress must include MinIO (9000)"
        else:
            pytest.skip("generate_platform_egress_rules not yet implemented (T026)")

    @pytest.mark.requirement("FR-033")
    def test_platform_egress_targets_floe_platform_namespace(self) -> None:
        """Test that platform egress rules target floe-platform namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_platform_egress_rules"):
            rules = plugin.generate_platform_egress_rules()

            # All rules should target floe-platform namespace
            for rule in rules:
                if "to" in rule:
                    for to_entry in rule["to"]:
                        if "namespaceSelector" in to_entry:
                            match_labels = to_entry["namespaceSelector"].get("matchLabels", {})
                            namespace = match_labels.get("kubernetes.io/metadata.name")
                            assert namespace == "floe-platform", (
                                f"Platform egress should target floe-platform, got {namespace}"
                            )
        else:
            pytest.skip("generate_platform_egress_rules not yet implemented (T026)")

    @pytest.mark.requirement("FR-031")
    def test_platform_egress_uses_tcp_protocol(self) -> None:
        """Test that platform egress rules use TCP protocol."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_platform_egress_rules"):
            rules = plugin.generate_platform_egress_rules()

            for rule in rules:
                for port_entry in rule.get("ports", []):
                    # Platform services use TCP
                    assert port_entry.get("protocol") == "TCP", (
                        f"Platform egress should use TCP, got {port_entry.get('protocol')}"
                    )
        else:
            pytest.skip("generate_platform_egress_rules not yet implemented (T026)")
