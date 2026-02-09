"""Unit tests for network policy integration in governance module.

These are TDD tests - they define the expected behavior before implementation.
T035 will implement the network policy check in GovernanceIntegrator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.enforcement.result import EnforcementResult, EnforcementSummary, Violation
from floe_core.governance.integrator import GovernanceIntegrator
from floe_core.schemas.governance import NetworkPoliciesConfig, RBACConfig
from floe_core.schemas.manifest import GovernanceConfig


@pytest.fixture
def mock_identity_plugin() -> MagicMock:
    """Mock identity plugin for tests."""
    plugin = MagicMock()
    plugin.verify_token.return_value = {"sub": "test-user", "role": "engineer"}
    return plugin


@pytest.fixture
def mock_network_security_plugin() -> MagicMock:
    """Mock network security plugin for tests."""
    plugin = MagicMock()
    plugin.generate_default_deny_policies.return_value = []
    plugin.generate_network_policy.return_value = []
    return plugin


def _create_mock_enforcement_result() -> EnforcementResult:
    """Create a mock enforcement result for tests."""
    return EnforcementResult(
        passed=True,
        violations=[],
        summary=EnforcementSummary(total_models=0, models_validated=0),
        enforcement_level="strict",
        manifest_version="1.0.0",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.requirement("003e-FR-020")
def test_network_policy_check_runs_when_enabled(
    mock_identity_plugin: MagicMock,
    mock_network_security_plugin: MagicMock,
) -> None:
    """Test that network policy check runs when enabled.

    Given: network_policies.enabled=True
    When: run_checks() is called
    Then: Network security plugin is discovered and used
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=NetworkPoliciesConfig(enabled=True, default_deny=True),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []
        mock_get_plugin.return_value = mock_network_security_plugin

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify network security plugin was discovered
        mock_get_plugin.assert_called_once()

        # Verify result is successful (no violations from network policies)
        assert result.passed is True
        assert len(result.violations) == 0


@pytest.mark.requirement("003e-FR-020")
def test_network_policy_disabled_skips_check(
    mock_identity_plugin: MagicMock,
) -> None:
    """Test that network policy check is skipped when disabled.

    Given: network_policies.enabled=False
    When: run_checks() is called
    Then: No network policy plugin calls, no network_policy violations
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=NetworkPoliciesConfig(enabled=False),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify network security plugin was NOT used
        mock_get_plugin.assert_not_called()

        # Verify no network policy violations
        network_violations = [
            v for v in result.violations if v.policy_type == "network_policy"
        ]
        assert len(network_violations) == 0


@pytest.mark.requirement("003e-FR-020")
def test_network_policy_none_config_skips_check(
    mock_identity_plugin: MagicMock,
) -> None:
    """Test that network policy check is skipped when not configured.

    Given: network_policies=None (not configured in manifest)
    When: run_checks() is called
    Then: No network policy violations
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=None,
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify network security plugin was NOT used
        mock_get_plugin.assert_not_called()

        # Verify no network policy violations
        network_violations = [
            v for v in result.violations if v.policy_type == "network_policy"
        ]
        assert len(network_violations) == 0


@pytest.mark.requirement("003e-FR-021")
def test_network_policy_default_deny_generated(
    mock_identity_plugin: MagicMock,
    mock_network_security_plugin: MagicMock,
) -> None:
    """Test that default-deny policy is generated when enabled.

    Given: network_policies.enabled=True, default_deny=True
    When: run_checks() is called
    Then: plugin.generate_default_deny_policies() is called
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=NetworkPoliciesConfig(enabled=True, default_deny=True),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []
        mock_get_plugin.return_value = mock_network_security_plugin

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify default-deny policy generation was called with namespace
        mock_network_security_plugin.generate_default_deny_policies.assert_called_once_with("floe")

        # Verify result is successful
        assert result.passed is True


@pytest.mark.requirement("003e-FR-021")
def test_network_policy_default_deny_false_skips_deny(
    mock_identity_plugin: MagicMock,
    mock_network_security_plugin: MagicMock,
) -> None:
    """Test that default-deny is not generated when disabled.

    Given: network_policies.enabled=True, default_deny=False
    When: run_checks() is called
    Then: plugin.generate_default_deny_policies() is NOT called
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=NetworkPoliciesConfig(enabled=True, default_deny=False),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []
        mock_get_plugin.return_value = mock_network_security_plugin

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify default-deny policy generation was NOT called
        mock_network_security_plugin.generate_default_deny_policies.assert_not_called()

        # Verify result is successful
        assert result.passed is True


@pytest.mark.requirement("003e-FR-022")
def test_network_policy_custom_egress_rules_passed_to_plugin(
    mock_identity_plugin: MagicMock,
    mock_network_security_plugin: MagicMock,
) -> None:
    """Test that custom egress rules are passed to the plugin.

    Given: network_policies with custom_egress_rules configured
    When: run_checks() is called
    Then: Custom rules are passed through to the plugin
    """
    custom_egress: list[dict[str, Any]] = [
        {
            "to": [{"podSelector": {"matchLabels": {"app": "external-api"}}}],
            "ports": [{"protocol": "TCP", "port": 443}],
        }
    ]

    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=NetworkPoliciesConfig(
            enabled=True,
            default_deny=True,
            custom_egress_rules=custom_egress,
        ),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []
        mock_get_plugin.return_value = mock_network_security_plugin

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify plugin was called with network config that includes custom egress
        mock_network_security_plugin.generate_network_policy.assert_called()
        call_args = mock_network_security_plugin.generate_network_policy.call_args
        assert call_args is not None

        # Verify result is successful
        assert result.passed is True


@pytest.mark.requirement("003e-FR-023")
def test_network_policy_violation_on_plugin_failure(
    mock_identity_plugin: MagicMock,
    mock_network_security_plugin: MagicMock,
) -> None:
    """Test that plugin failure produces network_policy violation.

    Given: network_policies.enabled=True, plugin raises Exception
    When: run_checks() is called
    Then: Violation with policy_type="network_policy" is produced
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        network_policies=NetworkPoliciesConfig(enabled=True, default_deny=True),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )
        mock_rbac_checker.return_value.check.return_value = []
        mock_secret_scanner.return_value.scan_directory.return_value = []

        # Plugin raises exception
        mock_network_security_plugin.generate_default_deny_policies.side_effect = (
            Exception("Network policy generation failed")
        )
        mock_get_plugin.return_value = mock_network_security_plugin

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify we have a network_policy violation
        network_violations = [
            v for v in result.violations if v.policy_type == "network_policy"
        ]
        assert len(network_violations) > 0
        assert result.passed is False

        # Verify violation details
        violation = network_violations[0]
        assert "network policy" in violation.message.lower()


@pytest.mark.requirement("003e-FR-020")
@pytest.mark.requirement("003e-FR-023")
def test_network_policy_violations_merged_with_other_checks(
    mock_identity_plugin: MagicMock,
    mock_network_security_plugin: MagicMock,
) -> None:
    """Test that network policy violations are merged with other checks.

    Given: RBAC violation + network policy violation
    When: run_checks() is called
    Then: Both violations appear in result
    """
    governance_config = GovernanceConfig(
        policy_enforcement_level="strict",
        pii_encryption="optional",
        audit_logging="enabled",
        data_retention_days=90,
        rbac=RBACConfig(enabled=True, required_role="admin"),
        network_policies=NetworkPoliciesConfig(enabled=True, default_deny=True),
    )

    with patch(
        "floe_core.governance.integrator.PolicyEnforcer"
    ) as mock_policy_enforcer, patch(
        "floe_core.governance.integrator.RBACChecker"
    ) as mock_rbac_checker, patch(
        "floe_core.governance.integrator.SecretScanner"
    ) as mock_secret_scanner, patch(
        "floe_core.governance.integrator.get_network_security_plugin",
        create=True,
    ) as mock_get_plugin:
        # Setup mocks
        mock_policy_enforcer.return_value.enforce.return_value = (
            _create_mock_enforcement_result()
        )

        # RBAC check produces a violation
        rbac_violation = Violation(
            error_code="RBAC-001",
            severity="error",
            policy_type="rbac",
            model_name="deployment",
            message="User lacks required permission",
            expected="deploy:prod permission",
            actual="None",
            suggestion="Request deployment permissions",
            documentation_url="https://floe.dev/docs/rbac",
        )
        mock_rbac_checker.return_value.check.return_value = [rbac_violation]
        mock_secret_scanner.return_value.scan_directory.return_value = []

        # Network policy check produces a violation
        mock_network_security_plugin.generate_default_deny_policies.side_effect = (
            Exception("Network policy failed")
        )
        mock_get_plugin.return_value = mock_network_security_plugin

        integrator = GovernanceIntegrator(
            governance_config=governance_config,
            identity_plugin=mock_identity_plugin,
        )

        result = integrator.run_checks(
            project_dir=Path("/tmp/test"),
            token="test-token",
            principal="test-user",
            dry_run=False,
            enforcement_level="strict",
        )

        # Verify we have both violations
        assert len(result.violations) >= 2
        assert result.passed is False

        # Verify both types of violations are present
        policy_types = {v.policy_type for v in result.violations}
        assert "rbac" in policy_types
        assert "network_policy" in policy_types
