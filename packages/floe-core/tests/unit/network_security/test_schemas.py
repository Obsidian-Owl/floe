"""Unit tests for network policy schemas.

Task: Extend test coverage for network/schemas.py
Epic: 7C - Network and Pod Security
Requirements: FR-070
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from floe_core.network.schemas import (
    EgressAllowRule,
    EgressRule,
    IngressRule,
    NetworkPolicyConfig,
    PortRule,
    _validate_cidr_format,
    _validate_label_key,
    _validate_label_value,
    _validate_namespace,
)


class TestValidateNamespace:
    """Test _validate_namespace function for RFC 1123 DNS label validation."""

    @pytest.mark.requirement("FR-070")
    def test_valid_namespace_floe_jobs_passes(self) -> None:
        """Test that 'floe-jobs' is a valid namespace."""
        result = _validate_namespace("floe-jobs")
        assert result == "floe-jobs"

    @pytest.mark.requirement("FR-070")
    def test_valid_namespace_default_passes(self) -> None:
        """Test that 'default' is a valid namespace."""
        result = _validate_namespace("default")
        assert result == "default"

    @pytest.mark.requirement("FR-070")
    def test_valid_namespace_kube_system_passes(self) -> None:
        """Test that 'kube-system' is a valid namespace."""
        result = _validate_namespace("kube-system")
        assert result == "kube-system"

    @pytest.mark.requirement("FR-070")
    def test_uppercase_fails(self) -> None:
        """Test that uppercase characters are rejected."""
        with pytest.raises(ValueError, match="Invalid namespace"):
            _validate_namespace("Floe-Jobs")

    @pytest.mark.requirement("FR-070")
    def test_underscore_fails(self) -> None:
        """Test that underscores are rejected."""
        with pytest.raises(ValueError, match="Invalid namespace"):
            _validate_namespace("floe_jobs")

    @pytest.mark.requirement("FR-070")
    def test_double_dash_ok(self) -> None:
        """Test that double dashes are allowed in the middle."""
        result = _validate_namespace("floe--jobs")
        assert result == "floe--jobs"

    @pytest.mark.requirement("FR-070")
    def test_max_length_63_passes(self) -> None:
        """Test that a 63-character namespace passes."""
        namespace = "a" * 63
        result = _validate_namespace(namespace)
        assert result == namespace

    @pytest.mark.requirement("FR-070")
    def test_over_63_chars_fails(self) -> None:
        """Test that a namespace over 63 characters fails."""
        namespace = "a" * 64
        with pytest.raises(ValueError, match="Namespace too long"):
            _validate_namespace(namespace)

    @pytest.mark.requirement("FR-070")
    def test_single_char_passes(self) -> None:
        """Test that a single character namespace passes."""
        result = _validate_namespace("a")
        assert result == "a"

    @pytest.mark.requirement("FR-070")
    def test_starts_with_dash_fails(self) -> None:
        """Test that namespace starting with dash fails."""
        with pytest.raises(ValueError, match="Invalid namespace"):
            _validate_namespace("-floe")

    @pytest.mark.requirement("FR-070")
    def test_ends_with_dash_fails(self) -> None:
        """Test that namespace ending with dash fails."""
        with pytest.raises(ValueError, match="Invalid namespace"):
            _validate_namespace("floe-")

    @pytest.mark.requirement("FR-070")
    def test_numeric_only_passes(self) -> None:
        """Test that numeric-only namespace passes."""
        result = _validate_namespace("123")
        assert result == "123"

    @pytest.mark.requirement("FR-070")
    def test_alphanumeric_with_dashes_passes(self) -> None:
        """Test that alphanumeric with dashes passes."""
        result = _validate_namespace("floe-123-jobs")
        assert result == "floe-123-jobs"


class TestValidateLabelKey:
    """Test _validate_label_key function for K8s label key validation."""

    @pytest.mark.requirement("FR-070")
    def test_simple_key_passes(self) -> None:
        """Test that a simple key passes."""
        result = _validate_label_key("app")
        assert result == "app"

    @pytest.mark.requirement("FR-070")
    def test_qualified_key_passes(self) -> None:
        """Test that a qualified key with domain prefix passes."""
        result = _validate_label_key("app.kubernetes.io/name")
        assert result == "app.kubernetes.io/name"

    @pytest.mark.requirement("FR-070")
    def test_empty_key_fails(self) -> None:
        """Test that an empty key fails."""
        with pytest.raises(ValueError, match="Label key cannot be empty"):
            _validate_label_key("")

    @pytest.mark.requirement("FR-070")
    def test_key_too_long_fails(self) -> None:
        """Test that a key over 253 characters fails."""
        key = "a" * 254
        with pytest.raises(ValueError, match="Label key too long"):
            _validate_label_key(key)

    @pytest.mark.requirement("FR-070")
    def test_key_exactly_253_passes(self) -> None:
        """Test that a key exactly 253 characters passes."""
        key = "a" * 253
        result = _validate_label_key(key)
        assert result == key

    @pytest.mark.requirement("FR-070")
    def test_starts_with_dash_fails(self) -> None:
        """Test that key starting with dash fails."""
        with pytest.raises(ValueError, match="Invalid label key"):
            _validate_label_key("-app")

    @pytest.mark.requirement("FR-070")
    def test_ends_with_dash_fails(self) -> None:
        """Test that key ending with dash fails."""
        with pytest.raises(ValueError, match="Invalid label key"):
            _validate_label_key("app-")

    @pytest.mark.requirement("FR-070")
    def test_with_underscores_passes(self) -> None:
        """Test that key with underscores passes."""
        result = _validate_label_key("app_name")
        assert result == "app_name"

    @pytest.mark.requirement("FR-070")
    def test_with_dots_passes(self) -> None:
        """Test that key with dots passes."""
        result = _validate_label_key("floe.dev/component")
        assert result == "floe.dev/component"


class TestValidateLabelValue:
    """Test _validate_label_value function for K8s label value validation."""

    @pytest.mark.requirement("FR-070")
    def test_alphanumeric_passes(self) -> None:
        """Test that alphanumeric value passes."""
        result = _validate_label_value("value123")
        assert result == "value123"

    @pytest.mark.requirement("FR-070")
    def test_with_dashes_passes(self) -> None:
        """Test that value with dashes passes."""
        result = _validate_label_value("my-value")
        assert result == "my-value"

    @pytest.mark.requirement("FR-070")
    def test_with_underscores_passes(self) -> None:
        """Test that value with underscores passes."""
        result = _validate_label_value("my_value")
        assert result == "my_value"

    @pytest.mark.requirement("FR-070")
    def test_with_dots_passes(self) -> None:
        """Test that value with dots passes."""
        result = _validate_label_value("my.value")
        assert result == "my.value"

    @pytest.mark.requirement("FR-070")
    def test_empty_string_passes(self) -> None:
        """Test that empty string passes (allowed for label values)."""
        result = _validate_label_value("")
        assert result == ""

    @pytest.mark.requirement("FR-070")
    def test_too_long_fails(self) -> None:
        """Test that value over 63 characters fails."""
        value = "a" * 64
        with pytest.raises(ValueError, match="Label value too long"):
            _validate_label_value(value)

    @pytest.mark.requirement("FR-070")
    def test_exactly_63_passes(self) -> None:
        """Test that value exactly 63 characters passes."""
        value = "a" * 63
        result = _validate_label_value(value)
        assert result == value

    @pytest.mark.requirement("FR-070")
    def test_starts_with_dash_fails(self) -> None:
        """Test that value starting with dash fails."""
        with pytest.raises(ValueError, match="Invalid label value"):
            _validate_label_value("-value")

    @pytest.mark.requirement("FR-070")
    def test_ends_with_dash_fails(self) -> None:
        """Test that value ending with dash fails."""
        with pytest.raises(ValueError, match="Invalid label value"):
            _validate_label_value("value-")

    @pytest.mark.requirement("FR-070")
    def test_special_chars_fail(self) -> None:
        """Test that special characters are rejected."""
        with pytest.raises(ValueError, match="Invalid label value"):
            _validate_label_value("value@123")

    @pytest.mark.requirement("FR-070")
    def test_starts_with_underscore_fails(self) -> None:
        """Test that value starting with underscore fails."""
        with pytest.raises(ValueError, match="Invalid label value"):
            _validate_label_value("_value")

    @pytest.mark.requirement("FR-070")
    def test_ends_with_underscore_fails(self) -> None:
        """Test that value ending with underscore fails."""
        with pytest.raises(ValueError, match="Invalid label value"):
            _validate_label_value("value_")


class TestValidateCidrFormat:
    """Test _validate_cidr_format function for CIDR notation validation."""

    @pytest.mark.requirement("FR-070")
    def test_ipv4_cidr_passes(self) -> None:
        """Test that valid IPv4 CIDR passes."""
        result = _validate_cidr_format("10.0.0.0/8")
        assert result == "10.0.0.0/8"

    @pytest.mark.requirement("FR-070")
    def test_ipv4_cidr_24_passes(self) -> None:
        """Test that IPv4 /24 CIDR passes."""
        result = _validate_cidr_format("192.168.1.0/24")
        assert result == "192.168.1.0/24"

    @pytest.mark.requirement("FR-070")
    def test_ipv6_cidr_passes(self) -> None:
        """Test that valid IPv6 CIDR passes."""
        result = _validate_cidr_format("2001:db8::/32")
        assert result == "2001:db8::/32"

    @pytest.mark.requirement("FR-070")
    def test_all_zeros_passes(self) -> None:
        """Test that 0.0.0.0/0 (all traffic) passes."""
        result = _validate_cidr_format("0.0.0.0/0")
        assert result == "0.0.0.0/0"

    @pytest.mark.requirement("FR-070")
    def test_host_route_passes(self) -> None:
        """Test that /32 host route passes."""
        result = _validate_cidr_format("192.168.1.1/32")
        assert result == "192.168.1.1/32"

    @pytest.mark.requirement("FR-070")
    def test_invalid_ip_fails(self) -> None:
        """Test that invalid IP address fails."""
        with pytest.raises(ValueError, match="Invalid CIDR"):
            _validate_cidr_format("999.999.999.999/24")

    @pytest.mark.requirement("FR-070")
    def test_invalid_prefix_fails(self) -> None:
        """Test that invalid prefix length fails."""
        with pytest.raises(ValueError, match="Invalid CIDR"):
            _validate_cidr_format("192.168.1.0/33")

    @pytest.mark.requirement("FR-070")
    def test_not_cidr_string_fails(self) -> None:
        """Test that non-CIDR string fails."""
        with pytest.raises(ValueError, match="Invalid CIDR"):
            _validate_cidr_format("not-a-cidr")

    @pytest.mark.requirement("FR-070")
    def test_missing_prefix_passes(self) -> None:
        """Test that IP without prefix passes (treated as host address)."""
        result = _validate_cidr_format("192.168.1.0")
        assert result == "192.168.1.0"

    @pytest.mark.requirement("FR-070")
    def test_ipv6_full_address_passes(self) -> None:
        """Test that full IPv6 CIDR passes."""
        result = _validate_cidr_format("2001:0db8:85a3:0000:0000:8a2e:0370:7334/128")
        assert result == "2001:0db8:85a3:0000:0000:8a2e:0370:7334/128"


class TestEgressRuleMutualExclusion:
    """Test EgressRule mutual exclusion validator."""

    @pytest.mark.requirement("FR-070")
    def test_only_namespace_passes(self) -> None:
        """Test that egress rule with only to_namespace passes."""
        rule = EgressRule(
            to_namespace="floe-platform",
            ports=(PortRule(port=443, protocol="TCP"),),
        )
        assert rule.to_namespace == "floe-platform"
        assert rule.to_cidr is None

    @pytest.mark.requirement("FR-070")
    def test_only_cidr_passes(self) -> None:
        """Test that egress rule with only to_cidr passes."""
        rule = EgressRule(
            to_cidr="10.0.0.0/8",
            ports=(PortRule(port=443, protocol="TCP"),),
        )
        assert rule.to_cidr == "10.0.0.0/8"
        assert rule.to_namespace is None

    @pytest.mark.requirement("FR-070")
    def test_both_set_fails(self) -> None:
        """Test that egress rule with both to_namespace and to_cidr fails."""
        with pytest.raises(
            ValidationError, match="Exactly one of to_namespace or to_cidr"
        ):
            EgressRule(
                to_namespace="floe-platform",
                to_cidr="10.0.0.0/8",
                ports=(PortRule(port=443, protocol="TCP"),),
            )

    @pytest.mark.requirement("FR-070")
    def test_neither_set_fails(self) -> None:
        """Test that egress rule with neither to_namespace nor to_cidr fails."""
        with pytest.raises(
            ValidationError, match="Exactly one of to_namespace or to_cidr"
        ):
            EgressRule(
                ports=(PortRule(port=443, protocol="TCP"),),
            )

    @pytest.mark.requirement("FR-070")
    def test_invalid_namespace_fails(self) -> None:
        """Test that egress rule with invalid namespace fails."""
        with pytest.raises(ValidationError, match="Invalid namespace"):
            EgressRule(
                to_namespace="Invalid_Namespace",
                ports=(PortRule(port=443, protocol="TCP"),),
            )

    @pytest.mark.requirement("FR-070")
    def test_invalid_cidr_fails(self) -> None:
        """Test that egress rule with invalid CIDR fails."""
        with pytest.raises(ValidationError, match="Invalid CIDR"):
            EgressRule(
                to_cidr="not-a-cidr",
                ports=(PortRule(port=443, protocol="TCP"),),
            )


class TestEgressAllowRuleMutualExclusion:
    """Test EgressAllowRule mutual exclusion validator."""

    @pytest.mark.requirement("FR-070")
    def test_only_namespace_passes(self) -> None:
        """Test that egress allow rule with only to_namespace passes."""
        rule = EgressAllowRule(
            name="allow-platform",
            to_namespace="floe-platform",
            port=443,
            protocol="TCP",
        )
        assert rule.to_namespace == "floe-platform"
        assert rule.to_cidr is None

    @pytest.mark.requirement("FR-070")
    def test_only_cidr_passes(self) -> None:
        """Test that egress allow rule with only to_cidr passes."""
        rule = EgressAllowRule(
            name="allow-external",
            to_cidr="0.0.0.0/0",
            port=443,
            protocol="TCP",
        )
        assert rule.to_cidr == "0.0.0.0/0"
        assert rule.to_namespace is None

    @pytest.mark.requirement("FR-070")
    def test_both_set_fails(self) -> None:
        """Test that egress allow rule with both to_namespace and to_cidr fails."""
        with pytest.raises(
            ValidationError, match="Exactly one of to_namespace or to_cidr"
        ):
            EgressAllowRule(
                name="invalid-rule",
                to_namespace="floe-platform",
                to_cidr="10.0.0.0/8",
                port=443,
                protocol="TCP",
            )

    @pytest.mark.requirement("FR-070")
    def test_neither_set_fails(self) -> None:
        """Test that egress allow rule with neither to_namespace nor to_cidr fails."""
        with pytest.raises(
            ValidationError, match="Exactly one of to_namespace or to_cidr"
        ):
            EgressAllowRule(
                name="invalid-rule",
                port=443,
                protocol="TCP",
            )

    @pytest.mark.requirement("FR-070")
    def test_invalid_namespace_fails(self) -> None:
        """Test that egress allow rule with invalid namespace fails."""
        with pytest.raises(ValidationError, match="Invalid namespace"):
            EgressAllowRule(
                name="invalid-rule",
                to_namespace="Invalid_Namespace",
                port=443,
                protocol="TCP",
            )

    @pytest.mark.requirement("FR-070")
    def test_invalid_cidr_fails(self) -> None:
        """Test that egress allow rule with invalid CIDR fails."""
        with pytest.raises(ValidationError, match="Invalid CIDR"):
            EgressAllowRule(
                name="invalid-rule",
                to_cidr="999.999.999.999/24",
                port=443,
                protocol="TCP",
            )


class TestNetworkPolicyConfigToK8sManifest:
    """Test NetworkPolicyConfig.to_k8s_manifest() method."""

    @pytest.mark.requirement("FR-070")
    def test_basic_manifest_structure(self) -> None:
        """Test that basic manifest has correct structure."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress", "Egress"),
        )
        manifest = config.to_k8s_manifest()

        assert manifest["apiVersion"] == "networking.k8s.io/v1"
        assert manifest["kind"] == "NetworkPolicy"
        assert manifest["metadata"]["name"] == "floe-test-policy"
        assert manifest["metadata"]["namespace"] == "floe-jobs"

    @pytest.mark.requirement("FR-070")
    def test_empty_pod_selector(self) -> None:
        """Test that empty pod selector generates empty matchLabels."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
        )
        manifest = config.to_k8s_manifest()

        assert manifest["spec"]["podSelector"] == {}

    @pytest.mark.requirement("FR-070")
    def test_non_empty_pod_selector(self) -> None:
        """Test that non-empty pod selector generates matchLabels."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            pod_selector={"app": "floe", "component": "jobs"},
            policy_types=("Ingress",),
        )
        manifest = config.to_k8s_manifest()

        assert manifest["spec"]["podSelector"] == {
            "matchLabels": {"app": "floe", "component": "jobs"}
        }

    @pytest.mark.requirement("FR-070")
    def test_ingress_rules_included(self) -> None:
        """Test that ingress rules are included in manifest."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
            ingress_rules=(
                IngressRule(
                    from_namespace="floe-platform",
                    ports=(PortRule(port=8080, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        assert "ingress" in manifest["spec"]
        assert len(manifest["spec"]["ingress"]) == 1
        ingress_rule = manifest["spec"]["ingress"][0]
        assert "from" in ingress_rule
        assert "ports" in ingress_rule
        assert ingress_rule["ports"][0]["port"] == 8080

    @pytest.mark.requirement("FR-070")
    def test_egress_rules_included(self) -> None:
        """Test that egress rules are included in manifest."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Egress",),
            egress_rules=(
                EgressRule(
                    to_namespace="floe-platform",
                    ports=(PortRule(port=443, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        assert "egress" in manifest["spec"]
        assert len(manifest["spec"]["egress"]) == 1
        egress_rule = manifest["spec"]["egress"][0]
        assert "to" in egress_rule
        assert "ports" in egress_rule
        assert egress_rule["ports"][0]["port"] == 443

    @pytest.mark.requirement("FR-070")
    def test_managed_by_label_present(self) -> None:
        """Test that managed-by label is present in metadata."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert "app.kubernetes.io/managed-by" in labels
        assert labels["app.kubernetes.io/managed-by"] == "floe"

    @pytest.mark.requirement("FR-070")
    def test_component_label_present(self) -> None:
        """Test that component label is present in metadata."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
        )
        manifest = config.to_k8s_manifest()

        labels = manifest["metadata"]["labels"]
        assert "floe.dev/component" in labels
        assert labels["floe.dev/component"] == "network-security"

    @pytest.mark.requirement("FR-070")
    def test_policy_types_in_spec(self) -> None:
        """Test that policy types are included in spec."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress", "Egress"),
        )
        manifest = config.to_k8s_manifest()

        assert "policyTypes" in manifest["spec"]
        assert "Ingress" in manifest["spec"]["policyTypes"]
        assert "Egress" in manifest["spec"]["policyTypes"]

    @pytest.mark.requirement("FR-070")
    def test_egress_rule_with_cidr(self) -> None:
        """Test that egress rule with CIDR generates ipBlock."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Egress",),
            egress_rules=(
                EgressRule(
                    to_cidr="0.0.0.0/0",
                    ports=(PortRule(port=443, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        egress_rule = manifest["spec"]["egress"][0]
        assert "to" in egress_rule
        assert len(egress_rule["to"]) == 1
        assert "ipBlock" in egress_rule["to"][0]
        assert egress_rule["to"][0]["ipBlock"]["cidr"] == "0.0.0.0/0"

    @pytest.mark.requirement("FR-070")
    def test_egress_rule_with_namespace(self) -> None:
        """Test that egress rule with namespace generates namespaceSelector."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Egress",),
            egress_rules=(
                EgressRule(
                    to_namespace="floe-platform",
                    ports=(PortRule(port=443, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        egress_rule = manifest["spec"]["egress"][0]
        assert "to" in egress_rule
        assert len(egress_rule["to"]) == 1
        assert "namespaceSelector" in egress_rule["to"][0]
        assert egress_rule["to"][0]["namespaceSelector"]["matchLabels"] == {
            "kubernetes.io/metadata.name": "floe-platform"
        }

    @pytest.mark.requirement("FR-070")
    def test_ingress_rule_with_namespace(self) -> None:
        """Test that ingress rule with namespace generates namespaceSelector."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
            ingress_rules=(
                IngressRule(
                    from_namespace="floe-platform",
                    ports=(PortRule(port=8080, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        ingress_rule = manifest["spec"]["ingress"][0]
        assert "from" in ingress_rule
        assert len(ingress_rule["from"]) == 1
        assert "namespaceSelector" in ingress_rule["from"][0]
        assert ingress_rule["from"][0]["namespaceSelector"]["matchLabels"] == {
            "kubernetes.io/metadata.name": "floe-platform"
        }

    @pytest.mark.requirement("FR-070")
    def test_ingress_rule_with_pod_labels(self) -> None:
        """Test that ingress rule with pod labels generates podSelector."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
            ingress_rules=(
                IngressRule(
                    from_pod_labels={"app": "floe", "component": "api"},
                    ports=(PortRule(port=8080, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        ingress_rule = manifest["spec"]["ingress"][0]
        assert "from" in ingress_rule
        assert len(ingress_rule["from"]) == 1
        assert "podSelector" in ingress_rule["from"][0]
        assert ingress_rule["from"][0]["podSelector"]["matchLabels"] == {
            "app": "floe",
            "component": "api",
        }

    @pytest.mark.requirement("FR-070")
    def test_ingress_rule_without_ports(self) -> None:
        """Test that ingress rule without ports omits ports field."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
            ingress_rules=(IngressRule(from_namespace="floe-platform"),),
        )
        manifest = config.to_k8s_manifest()

        ingress_rule = manifest["spec"]["ingress"][0]
        assert "ports" not in ingress_rule

    @pytest.mark.requirement("FR-070")
    def test_multiple_ingress_rules(self) -> None:
        """Test that multiple ingress rules are all included."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Ingress",),
            ingress_rules=(
                IngressRule(
                    from_namespace="floe-platform",
                    ports=(PortRule(port=8080, protocol="TCP"),),
                ),
                IngressRule(
                    from_pod_labels={"app": "monitoring"},
                    ports=(PortRule(port=9090, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        assert len(manifest["spec"]["ingress"]) == 2

    @pytest.mark.requirement("FR-070")
    def test_multiple_egress_rules(self) -> None:
        """Test that multiple egress rules are all included."""
        config = NetworkPolicyConfig(
            name="floe-test-policy",
            namespace="floe-jobs",
            policy_types=("Egress",),
            egress_rules=(
                EgressRule(
                    to_namespace="floe-platform",
                    ports=(PortRule(port=443, protocol="TCP"),),
                ),
                EgressRule(
                    to_cidr="0.0.0.0/0",
                    ports=(PortRule(port=443, protocol="TCP"),),
                ),
            ),
        )
        manifest = config.to_k8s_manifest()

        assert len(manifest["spec"]["egress"]) == 2
