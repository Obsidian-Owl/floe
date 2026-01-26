"""Contract tests for SecurityConfig extension with network_policies.

These tests validate the SecurityConfig schema extension for Epic 7C.
TDD: Written FIRST, expected to FAIL until T012, T013 are implemented.

Task: T005
Epic: 7C - Network and Pod Security
Contract: specs/7c-network-pod-security/contracts/security-config-extension.md
"""

from __future__ import annotations

import pytest


class TestSecurityConfigNetworkPoliciesExtension:
    """Contract tests for SecurityConfig.network_policies field."""

    @pytest.mark.requirement("FR-001")
    def test_security_config_has_network_policies_field(self) -> None:
        """Contract: SecurityConfig has network_policies field with defaults."""
        from floe_core.schemas.security import SecurityConfig

        config = SecurityConfig()

        assert hasattr(config, "network_policies")
        assert config.network_policies is not None

    @pytest.mark.requirement("FR-001")
    def test_network_policies_config_defaults(self) -> None:
        """Contract: NetworkPoliciesConfig has documented default values."""
        from floe_core.network import NetworkPoliciesConfig

        config = NetworkPoliciesConfig()

        assert config.enabled is True
        assert config.default_deny is True
        assert config.allow_external_https is True
        assert config.ingress_controller_namespace == "ingress-nginx"
        assert config.jobs_egress_allow == []
        assert config.platform_egress_allow == []

    @pytest.mark.requirement("FR-001")
    def test_security_config_network_policies_default_factory(self) -> None:
        """Contract: SecurityConfig uses default_factory for network_policies."""
        from floe_core.schemas.security import SecurityConfig

        config1 = SecurityConfig()
        config2 = SecurityConfig()

        assert config1.network_policies.enabled == config2.network_policies.enabled
        assert config1.network_policies is not config2.network_policies

    @pytest.mark.requirement("FR-001")
    def test_security_config_backward_compatibility(self) -> None:
        """Contract: Existing SecurityConfig without network_policies still works."""
        from floe_core.schemas.security import SecurityConfig

        config = SecurityConfig(
            namespace_isolation="strict",
        )

        assert config.namespace_isolation == "strict"
        assert config.network_policies.enabled is True

    @pytest.mark.requirement("FR-001")
    def test_security_config_frozen(self) -> None:
        """Contract: SecurityConfig is immutable (frozen=True)."""
        from floe_core.schemas.security import SecurityConfig

        config = SecurityConfig()

        with pytest.raises(Exception):
            config.namespace_isolation = "permissive"


class TestNetworkPoliciesConfigSchema:
    """Contract tests for NetworkPoliciesConfig schema structure."""

    @pytest.mark.requirement("FR-001")
    def test_network_policies_config_is_frozen(self) -> None:
        """Contract: NetworkPoliciesConfig is immutable."""
        from floe_core.network import NetworkPoliciesConfig

        config = NetworkPoliciesConfig()

        with pytest.raises(Exception):
            config.enabled = False

    @pytest.mark.requirement("FR-001")
    def test_network_policies_config_forbids_extra(self) -> None:
        """Contract: NetworkPoliciesConfig rejects unknown fields."""
        from pydantic import ValidationError

        from floe_core.network import NetworkPoliciesConfig

        with pytest.raises(ValidationError):
            NetworkPoliciesConfig(unknown_field="value")

    @pytest.mark.requirement("FR-033")
    def test_jobs_egress_allow_accepts_egress_rules(self) -> None:
        """Contract: jobs_egress_allow accepts list of EgressAllowRule."""
        from floe_core.network import EgressAllowRule, NetworkPoliciesConfig

        rule = EgressAllowRule(name="snowflake", to_cidr="0.0.0.0/0", port=443)
        config = NetworkPoliciesConfig(jobs_egress_allow=[rule])

        assert len(config.jobs_egress_allow) == 1
        assert config.jobs_egress_allow[0].name == "snowflake"

    @pytest.mark.requirement("FR-033")
    def test_platform_egress_allow_accepts_egress_rules(self) -> None:
        """Contract: platform_egress_allow accepts list of EgressAllowRule."""
        from floe_core.network import EgressAllowRule, NetworkPoliciesConfig

        rule = EgressAllowRule(name="vault", to_namespace="vault", port=8200)
        config = NetworkPoliciesConfig(platform_egress_allow=[rule])

        assert len(config.platform_egress_allow) == 1
        assert config.platform_egress_allow[0].to_namespace == "vault"


class TestEgressAllowRuleSchema:
    """Contract tests for EgressAllowRule schema."""

    @pytest.mark.requirement("FR-033")
    def test_egress_allow_rule_requires_name_and_port(self) -> None:
        """Contract: EgressAllowRule requires name and port."""
        from pydantic import ValidationError

        from floe_core.network import EgressAllowRule

        with pytest.raises(ValidationError):
            EgressAllowRule(to_cidr="0.0.0.0/0")

    @pytest.mark.requirement("FR-033")
    def test_egress_allow_rule_mutual_exclusion(self) -> None:
        """Contract: to_namespace and to_cidr are mutually exclusive."""
        from pydantic import ValidationError

        from floe_core.network import EgressAllowRule

        with pytest.raises(ValidationError):
            EgressAllowRule(name="invalid", to_namespace="vault", to_cidr="0.0.0.0/0", port=443)

        with pytest.raises(ValidationError):
            EgressAllowRule(name="invalid", port=443)

    @pytest.mark.requirement("FR-033")
    def test_egress_allow_rule_port_bounds(self) -> None:
        """Contract: Port must be 1-65535."""
        from pydantic import ValidationError

        from floe_core.network import EgressAllowRule

        with pytest.raises(ValidationError):
            EgressAllowRule(name="invalid", to_cidr="0.0.0.0/0", port=0)

        with pytest.raises(ValidationError):
            EgressAllowRule(name="invalid", to_cidr="0.0.0.0/0", port=65536)

    @pytest.mark.requirement("FR-033")
    def test_egress_allow_rule_cidr_pattern(self) -> None:
        """Contract: to_cidr must be valid CIDR notation."""
        from pydantic import ValidationError

        from floe_core.network import EgressAllowRule

        EgressAllowRule(name="valid", to_cidr="10.0.0.0/8", port=443)
        EgressAllowRule(name="valid", to_cidr="0.0.0.0/0", port=443)

        with pytest.raises(ValidationError):
            EgressAllowRule(name="invalid", to_cidr="not-a-cidr", port=443)

    @pytest.mark.requirement("FR-033")
    def test_egress_allow_rule_protocol_default(self) -> None:
        """Contract: Protocol defaults to TCP."""
        from floe_core.network import EgressAllowRule

        rule = EgressAllowRule(name="https", to_cidr="0.0.0.0/0", port=443)
        assert rule.protocol == "TCP"

    @pytest.mark.requirement("FR-033")
    def test_egress_allow_rule_udp_protocol(self) -> None:
        """Contract: Protocol can be UDP."""
        from floe_core.network import EgressAllowRule

        rule = EgressAllowRule(name="dns", to_namespace="kube-system", port=53, protocol="UDP")
        assert rule.protocol == "UDP"
