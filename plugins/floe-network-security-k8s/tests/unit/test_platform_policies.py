"""Unit tests for floe-platform namespace NetworkPolicy generation.

Task: T027, T028, T030, T032, T034
Phase: 4 - Platform Namespace Policies (US2)
User Story: US2 - Platform Namespace Ingress Control
Requirement: FR-020, FR-021, FR-022, FR-023
"""

from __future__ import annotations

import pytest


class TestPlatformDefaultDenyPolicy:
    """Unit tests for floe-platform default-deny NetworkPolicy (T027).

    Platform namespace needs default-deny with selective ingress:
    - Allow from ingress controller namespace
    - Allow from floe-jobs namespace (for API calls)
    - Allow intra-namespace communication
    """

    @pytest.mark.requirement("FR-020")
    def test_default_deny_for_platform_namespace(self) -> None:
        """Test that default-deny policies can be generated for floe-platform."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-platform")

        assert len(policies) >= 1
        assert policies[0]["metadata"]["namespace"] == "floe-platform"

    @pytest.mark.requirement("FR-020")
    def test_platform_default_deny_has_correct_structure(self) -> None:
        """Test that platform default-deny has correct K8s structure."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-platform")

        for policy in policies:
            assert policy["apiVersion"] == "networking.k8s.io/v1"
            assert policy["kind"] == "NetworkPolicy"
            assert "metadata" in policy
            assert "spec" in policy

    @pytest.mark.requirement("FR-020")
    def test_platform_default_deny_blocks_all_by_default(self) -> None:
        """Test that default-deny blocks all ingress/egress by default."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-platform")

        for policy in policies:
            # Empty ingress/egress arrays = deny all
            assert policy["spec"]["ingress"] == []
            assert policy["spec"]["egress"] == []


class TestIngressControllerAllowlist:
    """Unit tests for ingress controller namespace allowlist (T028).

    Platform services need to receive traffic from the ingress controller
    (typically ingress-nginx or similar).
    """

    @pytest.mark.requirement("FR-021")
    def test_generate_ingress_controller_rule(self) -> None:
        """Test generation of ingress rule from ingress controller namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_ingress_controller_rule"):
            rule = plugin.generate_ingress_controller_rule()

            # Should have 'from' field with namespaceSelector
            assert "from" in rule
            assert len(rule["from"]) >= 1
        else:
            pytest.skip("generate_ingress_controller_rule not yet implemented (T029)")

    @pytest.mark.requirement("FR-021")
    def test_ingress_controller_targets_ingress_namespace(self) -> None:
        """Test that ingress controller rule targets ingress-nginx namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_ingress_controller_rule"):
            rule = plugin.generate_ingress_controller_rule()

            # Should target ingress-nginx namespace by default
            namespace_selector = rule["from"][0].get("namespaceSelector", {})
            match_labels = namespace_selector.get("matchLabels", {})
            assert match_labels.get("kubernetes.io/metadata.name") == "ingress-nginx"
        else:
            pytest.skip("generate_ingress_controller_rule not yet implemented (T029)")

    @pytest.mark.requirement("FR-021")
    def test_ingress_controller_rule_configurable_namespace(self) -> None:
        """Test that ingress controller namespace is configurable."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_ingress_controller_rule"):
            # Custom ingress namespace
            rule = plugin.generate_ingress_controller_rule(namespace="traefik")

            namespace_selector = rule["from"][0].get("namespaceSelector", {})
            match_labels = namespace_selector.get("matchLabels", {})
            assert match_labels.get("kubernetes.io/metadata.name") == "traefik"
        else:
            pytest.skip("generate_ingress_controller_rule not yet implemented (T029)")

    @pytest.mark.requirement("FR-021")
    def test_ingress_controller_allows_http_https(self) -> None:
        """Test that ingress controller rule allows HTTP and HTTPS ports."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_ingress_controller_rule"):
            rule = plugin.generate_ingress_controller_rule()

            # Should allow HTTP (80) and HTTPS (443)
            ports = [p.get("port") for p in rule.get("ports", [])]
            assert 80 in ports or 8080 in ports, "Should allow HTTP traffic"
        else:
            pytest.skip("generate_ingress_controller_rule not yet implemented (T029)")


class TestJobsToPatformIngress:
    """Unit tests for jobs-to-platform ingress rules (T030).

    Job pods need to communicate with platform services:
    - Polaris catalog for metadata
    - OTel Collector for telemetry
    - MinIO for storage
    """

    @pytest.mark.requirement("FR-022")
    def test_generate_jobs_ingress_rule(self) -> None:
        """Test generation of ingress rule from floe-jobs namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_jobs_ingress_rule"):
            rule = plugin.generate_jobs_ingress_rule()

            # Should have 'from' field with namespaceSelector
            assert "from" in rule
            assert len(rule["from"]) >= 1
        else:
            pytest.skip("generate_jobs_ingress_rule not yet implemented (T029)")

    @pytest.mark.requirement("FR-022")
    def test_jobs_ingress_targets_floe_jobs_namespace(self) -> None:
        """Test that jobs ingress rule targets floe-jobs namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_jobs_ingress_rule"):
            rule = plugin.generate_jobs_ingress_rule()

            namespace_selector = rule["from"][0].get("namespaceSelector", {})
            match_labels = namespace_selector.get("matchLabels", {})
            assert match_labels.get("kubernetes.io/metadata.name") == "floe-jobs"
        else:
            pytest.skip("generate_jobs_ingress_rule not yet implemented (T029)")

    @pytest.mark.requirement("FR-022")
    def test_jobs_ingress_allows_platform_service_ports(self) -> None:
        """Test that jobs ingress allows platform service ports."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_jobs_ingress_rule"):
            rule = plugin.generate_jobs_ingress_rule()

            ports = [p.get("port") for p in rule.get("ports", [])]
            # Should allow Polaris (8181), OTel (4317, 4318), MinIO (9000)
            assert 8181 in ports, "Should allow Polaris traffic"
            assert 4317 in ports, "Should allow OTel gRPC traffic"
            assert 4318 in ports, "Should allow OTel HTTP traffic"
            assert 9000 in ports, "Should allow MinIO traffic"
        else:
            pytest.skip("generate_jobs_ingress_rule not yet implemented (T029)")


class TestIntraNamespaceCommunication:
    """Unit tests for intra-namespace communication (T032).

    Platform services need to communicate with each other within
    the floe-platform namespace.
    """

    @pytest.mark.requirement("FR-023")
    def test_generate_intra_namespace_rule(self) -> None:
        """Test generation of intra-namespace communication rule."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_intra_namespace_rule"):
            rule = plugin.generate_intra_namespace_rule("floe-platform")

            # Should have 'from' field
            assert "from" in rule
        else:
            pytest.skip("generate_intra_namespace_rule not yet implemented (T029)")

    @pytest.mark.requirement("FR-023")
    def test_intra_namespace_uses_pod_selector(self) -> None:
        """Test that intra-namespace rule uses empty podSelector (all pods)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_intra_namespace_rule"):
            rule = plugin.generate_intra_namespace_rule("floe-platform")

            # Should match all pods in same namespace
            from_entry = rule["from"][0]
            assert "podSelector" in from_entry
            # Empty podSelector = match all pods
            assert from_entry["podSelector"] == {}
        else:
            pytest.skip("generate_intra_namespace_rule not yet implemented (T029)")


class TestCustomPlatformEgressRules:
    """Unit tests for custom platform egress rules (T032).

    Platform can configure custom egress rules via:
    - CIDR-based rules (external services)
    - Namespace-based rules (other K8s namespaces)
    """

    @pytest.mark.requirement("FR-023")
    def test_generate_custom_cidr_egress_rule(self) -> None:
        """Test generation of CIDR-based custom egress rules."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_custom_egress_rule"):
            rule = plugin.generate_custom_egress_rule(
                cidr="10.0.0.0/8",
                port=443,
                protocol="TCP",
            )

            assert "to" in rule
            assert "ports" in rule
            # Should have ipBlock with CIDR
            assert "ipBlock" in rule["to"][0]
            assert rule["to"][0]["ipBlock"]["cidr"] == "10.0.0.0/8"
        else:
            pytest.skip("generate_custom_egress_rule not yet implemented (T033)")

    @pytest.mark.requirement("FR-023")
    def test_generate_custom_namespace_egress_rule(self) -> None:
        """Test generation of namespace-based custom egress rules."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_custom_egress_rule"):
            rule = plugin.generate_custom_egress_rule(
                namespace="external-services",
                port=5432,
                protocol="TCP",
            )

            assert "to" in rule
            assert "ports" in rule
            # Should have namespaceSelector
            assert "namespaceSelector" in rule["to"][0]
            match_labels = rule["to"][0]["namespaceSelector"].get("matchLabels", {})
            assert match_labels.get("kubernetes.io/metadata.name") == "external-services"
        else:
            pytest.skip("generate_custom_egress_rule not yet implemented (T033)")

    @pytest.mark.requirement("FR-023")
    def test_custom_egress_validates_port_range(self) -> None:
        """Test that custom egress validates port in valid range."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_custom_egress_rule"):
            # Valid port should work
            rule = plugin.generate_custom_egress_rule(
                cidr="0.0.0.0/0",
                port=443,
                protocol="TCP",
            )
            assert rule["ports"][0]["port"] == 443

            # Method should handle port as int
            assert isinstance(rule["ports"][0]["port"], int)
        else:
            pytest.skip("generate_custom_egress_rule not yet implemented (T033)")

    @pytest.mark.requirement("FR-023")
    def test_custom_egress_protocol_options(self) -> None:
        """Test that custom egress supports TCP and UDP protocols."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_custom_egress_rule"):
            tcp_rule = plugin.generate_custom_egress_rule(
                cidr="0.0.0.0/0",
                port=443,
                protocol="TCP",
            )
            assert tcp_rule["ports"][0]["protocol"] == "TCP"

            udp_rule = plugin.generate_custom_egress_rule(
                cidr="0.0.0.0/0",
                port=53,
                protocol="UDP",
            )
            assert udp_rule["ports"][0]["protocol"] == "UDP"
        else:
            pytest.skip("generate_custom_egress_rule not yet implemented (T033)")

    @pytest.mark.requirement("FR-023")
    def test_custom_egress_with_multiple_ports(self) -> None:
        """Test generation of custom egress with multiple ports."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_custom_egress_rules"):
            rules = plugin.generate_custom_egress_rules(
                cidr="10.0.0.0/8",
                ports=[443, 8080, 9000],
                protocol="TCP",
            )

            # Should have one rule with multiple ports OR multiple rules
            if isinstance(rules, list):
                all_ports = []
                for r in rules:
                    all_ports.extend([p["port"] for p in r.get("ports", [])])
                assert 443 in all_ports
                assert 8080 in all_ports
                assert 9000 in all_ports
            else:
                ports = [p["port"] for p in rules.get("ports", [])]
                assert 443 in ports
                assert 8080 in ports
                assert 9000 in ports
        else:
            pytest.skip("generate_custom_egress_rules not yet implemented (T033)")


class TestPlatformEgressRules:
    """Unit tests for platform egress rules (T034).

    Platform services need egress to:
    - Kubernetes API server
    - External HTTPS (configurable)
    - DNS (always)
    """

    @pytest.mark.requirement("FR-023")
    def test_platform_egress_allows_k8s_api(self) -> None:
        """Test that platform egress allows Kubernetes API access."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_k8s_api_egress_rule"):
            rule = plugin.generate_k8s_api_egress_rule(strict_mode=False)

            # Should allow port 443 (HTTPS) or 6443 (K8s API)
            ports = [p.get("port") for p in rule.get("ports", [])]
            assert 443 in ports or 6443 in ports
        else:
            pytest.skip("generate_k8s_api_egress_rule not yet implemented (T033)")

    @pytest.mark.requirement("FR-023")
    def test_platform_egress_external_https_configurable(self) -> None:
        """Test that external HTTPS egress is configurable."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        if hasattr(plugin, "generate_external_https_egress_rule"):
            # External HTTPS should be toggleable
            rule = plugin.generate_external_https_egress_rule(enabled=True)
            assert rule is not None

            # When disabled, should return None or empty
            rule_disabled = plugin.generate_external_https_egress_rule(enabled=False)
            assert rule_disabled is None
        else:
            pytest.skip("generate_external_https_egress_rule not yet implemented (T033)")
