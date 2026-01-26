"""Unit tests for domain namespace NetworkPolicy generation.

Task: T056, T057, T058
Phase: 8 - Domain Namespace Policies (US6)
User Story: US6 - Domain Namespace Isolation
Requirement: FR-060, FR-061, FR-062, FR-063
"""

from __future__ import annotations

import pytest


class TestDomainDefaultDenyPolicies:
    """Tests for domain namespace default-deny policies (FR-060).

    Domain namespaces use the same default-deny pattern as job namespaces,
    blocking all ingress and egress by default. Explicit allowlists are
    required for any communication.
    """

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_generated(self) -> None:
        """Test default-deny policy generated for domain namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-sales-domain")

        assert len(policies) >= 1
        assert policies[0]["metadata"]["namespace"] == "floe-sales-domain"

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_has_correct_api_version(self) -> None:
        """Test that domain default-deny policy has correct K8s API version."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-marketing-domain")

        for policy in policies:
            assert policy["apiVersion"] == "networking.k8s.io/v1"

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_has_correct_kind(self) -> None:
        """Test that domain default-deny policy has correct K8s kind."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-finance-domain")

        for policy in policies:
            assert policy["kind"] == "NetworkPolicy"

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_targets_correct_namespace(self) -> None:
        """Test that domain default-deny policy targets the specified namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        namespace = "floe-operations-domain"
        policies = plugin.generate_default_deny_policies(namespace)

        for policy in policies:
            assert policy["metadata"]["namespace"] == namespace

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_has_empty_pod_selector(self) -> None:
        """Test that domain default-deny applies to all pods (empty podSelector)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-sales-domain")

        for policy in policies:
            assert policy["spec"]["podSelector"] == {}

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_includes_ingress_policy_type(self) -> None:
        """Test that domain default-deny includes Ingress in policyTypes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-marketing-domain")

        policy_types = []
        for policy in policies:
            policy_types.extend(policy["spec"]["policyTypes"])

        assert "Ingress" in policy_types

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_includes_egress_policy_type(self) -> None:
        """Test that domain default-deny includes Egress in policyTypes."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-finance-domain")

        policy_types = []
        for policy in policies:
            policy_types.extend(policy["spec"]["policyTypes"])

        assert "Egress" in policy_types

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_has_empty_ingress_rules(self) -> None:
        """Test that domain default-deny has empty ingress rules (blocks all)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-operations-domain")

        for policy in policies:
            if "Ingress" in policy["spec"]["policyTypes"]:
                assert policy["spec"]["ingress"] == []

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_has_empty_egress_rules(self) -> None:
        """Test that domain default-deny has empty egress rules (blocks all)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-sales-domain")

        for policy in policies:
            if "Egress" in policy["spec"]["policyTypes"]:
                assert policy["spec"]["egress"] == []

    @pytest.mark.requirement("FR-060")
    def test_domain_default_deny_has_managed_by_label(self) -> None:
        """Test that domain default-deny policy has managed-by label."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-marketing-domain")

        for policy in policies:
            assert "labels" in policy["metadata"]
            assert policy["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "floe"


class TestDomainToPlatformEgress:
    """Tests for domain namespace egress to floe-platform services (FR-061).

    Domain namespaces need to communicate with platform services:
    - Polaris catalog (TCP 8181) for metadata
    - OTel Collector (TCP 4317/4318) for telemetry
    - MinIO storage (TCP 9000) for data access
    """

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_rules_generated(self) -> None:
        """Test that platform egress rules are generated."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        assert isinstance(rules, list)
        assert len(rules) >= 1

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_targets_floe_platform_namespace(self) -> None:
        """Test that platform egress rules target floe-platform namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        for rule in rules:
            assert "to" in rule
            assert len(rule["to"]) >= 1

            # Should target floe-platform namespace
            namespace_selector = rule["to"][0].get("namespaceSelector", {})
            match_labels = namespace_selector.get("matchLabels", {})
            assert match_labels.get("kubernetes.io/metadata.name") == "floe-platform"

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_includes_polaris_port(self) -> None:
        """Test that platform egress includes Polaris catalog port (8181)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        # Find rule with port 8181
        polaris_found = any(
            any(p.get("port") == 8181 and p.get("protocol") == "TCP" for p in rule.get("ports", []))
            for rule in rules
        )
        assert polaris_found, "Platform egress must include Polaris port 8181"

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_includes_otel_grpc_port(self) -> None:
        """Test that platform egress includes OTel gRPC port (4317)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        # Find rule with port 4317
        otel_grpc_found = any(
            any(p.get("port") == 4317 and p.get("protocol") == "TCP" for p in rule.get("ports", []))
            for rule in rules
        )
        assert otel_grpc_found, "Platform egress must include OTel gRPC port 4317"

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_includes_otel_http_port(self) -> None:
        """Test that platform egress includes OTel HTTP port (4318)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        # Find rule with port 4318
        otel_http_found = any(
            any(p.get("port") == 4318 and p.get("protocol") == "TCP" for p in rule.get("ports", []))
            for rule in rules
        )
        assert otel_http_found, "Platform egress must include OTel HTTP port 4318"

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_includes_minio_port(self) -> None:
        """Test that platform egress includes MinIO storage port (9000)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        # Find rule with port 9000
        minio_found = any(
            any(p.get("port") == 9000 and p.get("protocol") == "TCP" for p in rule.get("ports", []))
            for rule in rules
        )
        assert minio_found, "Platform egress must include MinIO port 9000"

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_rules_use_tcp_protocol(self) -> None:
        """Test that platform egress rules use TCP protocol."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        for rule in rules:
            if "ports" in rule:
                for port in rule["ports"]:
                    assert port.get("protocol") == "TCP"

    @pytest.mark.requirement("FR-061")
    def test_platform_egress_rules_have_valid_structure(self) -> None:
        """Test that platform egress rules have valid K8s NetworkPolicy structure."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rules = plugin.generate_platform_egress_rules()

        for rule in rules:
            # Valid egress rule must have 'to' and/or 'ports'
            assert "to" in rule or "ports" in rule
            # If 'to' is present, it should be a list
            if "to" in rule:
                assert isinstance(rule["to"], list)
            # If 'ports' is present, it should be a list
            if "ports" in rule:
                assert isinstance(rule["ports"], list)


class TestCrossDomainIsolation:
    """Tests for cross-domain isolation (FR-062).

    Domains cannot communicate with each other by default. Each domain
    namespace is isolated from other domain namespaces. Only explicit
    allowlists (via NetworkPolicy) permit cross-domain communication.
    """

    @pytest.mark.requirement("FR-062")
    def test_no_cross_domain_egress_by_default(self) -> None:
        """Test domains cannot communicate with each other by default."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-marketing-domain")

        # Default-deny blocks all egress except explicitly allowed
        for policy in policies:
            if "Egress" in policy["spec"].get("policyTypes", []):
                # Egress array should be empty (deny all)
                assert policy["spec"]["egress"] == []

    @pytest.mark.requirement("FR-062")
    def test_no_cross_domain_ingress_by_default(self) -> None:
        """Test domains cannot receive traffic from other domains by default."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-finance-domain")

        # Default-deny blocks all ingress except explicitly allowed
        for policy in policies:
            if "Ingress" in policy["spec"].get("policyTypes", []):
                # Ingress array should be empty (deny all)
                assert policy["spec"]["ingress"] == []

    @pytest.mark.requirement("FR-062")
    def test_domain_isolation_applies_to_all_pods(self) -> None:
        """Test that domain isolation applies to all pods in the namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-sales-domain")

        # Empty podSelector means all pods in namespace
        for policy in policies:
            assert policy["spec"]["podSelector"] == {}

    @pytest.mark.requirement("FR-062")
    def test_domain_isolation_independent_per_domain(self) -> None:
        """Test that isolation policies are independent per domain namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # Generate policies for two different domains
        sales_policies = plugin.generate_default_deny_policies("floe-sales-domain")
        marketing_policies = plugin.generate_default_deny_policies("floe-marketing-domain")

        # Each should target its own namespace
        assert sales_policies[0]["metadata"]["namespace"] == "floe-sales-domain"
        assert marketing_policies[0]["metadata"]["namespace"] == "floe-marketing-domain"

    @pytest.mark.requirement("FR-062")
    def test_domain_isolation_blocks_pod_to_pod_cross_domain(self) -> None:
        """Test that pod-to-pod communication across domains is blocked."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        policies = plugin.generate_default_deny_policies("floe-operations-domain")

        # Default-deny with empty ingress blocks all pod-to-pod traffic
        for policy in policies:
            if "Ingress" in policy["spec"].get("policyTypes", []):
                # No ingress rules means no cross-domain pods can connect
                assert policy["spec"]["ingress"] == []


class TestDomainIngressRules:
    """Tests for domain namespace ingress rules (FR-063).

    Domain namespaces may need to receive traffic from:
    - Ingress controller (for external API access)
    - Other services within the same domain (intra-domain communication)
    - Platform services (for metadata/telemetry responses)
    """

    @pytest.mark.requirement("FR-063")
    def test_ingress_controller_rule_generated(self) -> None:
        """Test that ingress controller rule can be generated."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_ingress_controller_rule()

        assert isinstance(rule, dict)
        assert "from" in rule

    @pytest.mark.requirement("FR-063")
    def test_ingress_controller_rule_targets_ingress_nginx(self) -> None:
        """Test that ingress controller rule targets ingress-nginx namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_ingress_controller_rule()

        # Should have 'from' with namespaceSelector
        assert "from" in rule
        assert len(rule["from"]) >= 1

        # Should target ingress-nginx namespace
        namespace_selector = rule["from"][0].get("namespaceSelector", {})
        match_labels = namespace_selector.get("matchLabels", {})
        assert match_labels.get("kubernetes.io/metadata.name") == "ingress-nginx"

    @pytest.mark.requirement("FR-063")
    def test_ingress_controller_rule_allows_http(self) -> None:
        """Test that ingress controller rule allows HTTP (port 80)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_ingress_controller_rule()

        # Should have ports defined
        assert "ports" in rule

        # Find HTTP port rule
        http_found = any(p.get("port") == 80 and p.get("protocol") == "TCP" for p in rule["ports"])
        assert http_found, "Ingress controller rule must allow HTTP port 80"

    @pytest.mark.requirement("FR-063")
    def test_ingress_controller_rule_allows_https(self) -> None:
        """Test that ingress controller rule allows HTTPS (port 443)."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_ingress_controller_rule()

        # Should have ports defined
        assert "ports" in rule

        # Find HTTPS port rule
        https_found = any(
            p.get("port") == 443 and p.get("protocol") == "TCP" for p in rule["ports"]
        )
        assert https_found, "Ingress controller rule must allow HTTPS port 443"

    @pytest.mark.requirement("FR-063")
    def test_intra_namespace_rule_generated(self) -> None:
        """Test that intra-namespace communication rule can be generated."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_intra_namespace_rule("floe-sales-domain")

        assert isinstance(rule, dict)
        assert "from" in rule

    @pytest.mark.requirement("FR-063")
    def test_intra_namespace_rule_allows_all_pods_in_namespace(self) -> None:
        """Test that intra-namespace rule allows all pods in the same namespace."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_intra_namespace_rule("floe-marketing-domain")

        # Should have 'from' with empty podSelector (matches all pods in namespace)
        assert "from" in rule
        assert len(rule["from"]) >= 1

        # Empty podSelector matches all pods in the same namespace
        pod_selector = rule["from"][0].get("podSelector", {})
        assert pod_selector == {}

    @pytest.mark.requirement("FR-063")
    def test_intra_namespace_rule_uses_pod_selector(self) -> None:
        """Test that intra-namespace rule uses podSelector (not namespaceSelector).

        Using podSelector with empty value matches all pods in the same namespace,
        which is the correct behavior for intra-namespace communication.
        """
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()
        rule = plugin.generate_intra_namespace_rule("floe-finance-domain")

        # Should use podSelector, not namespaceSelector
        assert "from" in rule
        first_from = rule["from"][0]
        assert "podSelector" in first_from

    @pytest.mark.requirement("FR-063")
    def test_ingress_rules_have_valid_structure(self) -> None:
        """Test that ingress rules have valid K8s NetworkPolicy ingress structure."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # Test ingress controller rule
        controller_rule = plugin.generate_ingress_controller_rule()
        assert "from" in controller_rule
        assert isinstance(controller_rule["from"], list)

        # Test intra-namespace rule
        intra_rule = plugin.generate_intra_namespace_rule("floe-sales-domain")
        assert "from" in intra_rule
        assert isinstance(intra_rule["from"], list)

    @pytest.mark.requirement("FR-063")
    def test_domain_ingress_rules_independent_per_domain(self) -> None:
        """Test that ingress rules can be applied independently per domain."""
        from floe_network_security_k8s import K8sNetworkSecurityPlugin

        plugin = K8sNetworkSecurityPlugin()

        # Generate intra-namespace rules for different domains
        sales_rule = plugin.generate_intra_namespace_rule("floe-sales-domain")
        marketing_rule = plugin.generate_intra_namespace_rule("floe-marketing-domain")

        # Both should have valid structure
        assert "from" in sales_rule
        assert "from" in marketing_rule

        # Both should allow intra-namespace communication
        assert sales_rule["from"][0].get("podSelector") == {}
        assert marketing_rule["from"][0].get("podSelector") == {}
