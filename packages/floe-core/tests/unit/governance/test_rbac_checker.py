"""TDD unit tests for RBACChecker class.

These tests are written BEFORE the implementation exists (TDD pattern).
They will FAIL with ModuleNotFoundError until T025 implements RBACChecker.

Task: T022
Requirements: 3E-FR-002 (RBAC identity validation), 3E-FR-003 (principal fallback)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from floe_core.governance.rbac_checker import RBACChecker

# This import will FAIL until RBACChecker is implemented in T025
from floe_core.plugins.identity import IdentityPlugin, TokenValidationResult, UserInfo
from floe_core.schemas.governance import RBACConfig

# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def mock_identity_plugin() -> MagicMock:
    """Create a mock IdentityPlugin for testing.

    Returns:
        Mock IdentityPlugin with validate_token method.
    """
    plugin = MagicMock(spec=IdentityPlugin)
    return plugin


@pytest.fixture
def rbac_config_enabled() -> RBACConfig:
    """Create RBACConfig with RBAC enabled and required role.

    Returns:
        RBACConfig with enabled=True, required_role="platform-engineer".
    """
    return RBACConfig(
        enabled=True,
        required_role="platform-engineer",
        allow_principal_fallback=True,
    )


@pytest.fixture
def rbac_config_disabled() -> RBACConfig:
    """Create RBACConfig with RBAC disabled.

    Returns:
        RBACConfig with enabled=False.
    """
    return RBACConfig(enabled=False)


@pytest.fixture
def rbac_config_no_required_role() -> RBACConfig:
    """Create RBACConfig with enabled=True but no required_role.

    Returns:
        RBACConfig with enabled=True, required_role=None.
    """
    return RBACConfig(enabled=True, required_role=None, allow_principal_fallback=True)


@pytest.fixture
def rbac_config_no_principal_fallback() -> RBACConfig:
    """Create RBACConfig with principal fallback disabled.

    Returns:
        RBACConfig with allow_principal_fallback=False.
    """
    return RBACConfig(
        enabled=True,
        required_role="platform-engineer",
        allow_principal_fallback=False,
    )


# ==============================================================================
# Test Scenarios
# ==============================================================================


@pytest.mark.requirement("3E-FR-002")
def test_valid_token_with_required_role(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that valid token with required role returns no violations.

    Given a valid token where user has the required role,
    When RBACChecker.check() is called,
    Then it should return an empty violations list.
    """
    # Arrange
    user_info = UserInfo(
        subject="user123",
        email="engineer@example.com",
        name="Platform Engineer",
        roles=["platform-engineer", "viewer"],
    )
    mock_identity_plugin.validate_token.return_value = TokenValidationResult(
        valid=True,
        user_info=user_info,
        expires_at="2026-12-31T23:59:59Z",
    )

    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token="valid-token", principal=None)

    # Assert
    assert violations == []
    mock_identity_plugin.validate_token.assert_called_once_with("valid-token")


@pytest.mark.requirement("3E-FR-002")
def test_expired_token(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that expired token returns FLOE-E502 violation.

    Given an expired token,
    When RBACChecker.check() is called,
    Then it should return a Violation with error_code="FLOE-E502".
    """
    # Arrange
    mock_identity_plugin.validate_token.return_value = TokenValidationResult(
        valid=False,
        error="Token expired",
    )

    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token="expired-token", principal=None)

    # Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.error_code == "FLOE-E502"
    assert violation.severity == "error"
    assert violation.policy_type == "rbac"
    assert violation.model_name == "__rbac__"
    assert "expired" in violation.message.lower()
    assert violation.expected == "Valid OIDC token"
    assert violation.actual == "Token expired"
    assert "Obtain a fresh token" in violation.suggestion
    assert violation.documentation_url == "https://floe.dev/docs/governance/rbac#token-expired"

    mock_identity_plugin.validate_token.assert_called_once_with("expired-token")


@pytest.mark.requirement("3E-FR-002")
def test_missing_token_no_principal(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that missing token with no principal fallback returns FLOE-E501.

    Given no FLOE_TOKEN and no --principal fallback,
    When RBACChecker.check() is called,
    Then it should return a Violation with error_code="FLOE-E501".
    """
    # Arrange
    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token=None, principal=None)

    # Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.error_code == "FLOE-E501"
    assert violation.severity == "error"
    assert violation.policy_type == "rbac"
    assert violation.model_name == "__rbac__"
    assert "missing" in violation.message.lower() or "required" in violation.message.lower()
    assert violation.expected == "OIDC token or principal fallback"
    assert violation.actual == "No token or principal provided"
    assert "Set FLOE_TOKEN" in violation.suggestion or "--principal" in violation.suggestion
    assert violation.documentation_url == "https://floe.dev/docs/governance/rbac#missing-token"

    # validate_token should NOT be called when token is None
    mock_identity_plugin.validate_token.assert_not_called()


@pytest.mark.requirement("3E-FR-002")
def test_insufficient_role(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that valid token without required role returns FLOE-E503.

    Given a valid token where user does NOT have the required role,
    When RBACChecker.check() is called,
    Then it should return a Violation with error_code="FLOE-E503".
    """
    # Arrange
    user_info = UserInfo(
        subject="user123",
        email="viewer@example.com",
        name="Read Only User",
        roles=["viewer"],  # Missing "platform-engineer"
    )
    mock_identity_plugin.validate_token.return_value = TokenValidationResult(
        valid=True,
        user_info=user_info,
        expires_at="2026-12-31T23:59:59Z",
    )

    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token="valid-token", principal=None)

    # Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.error_code == "FLOE-E503"
    assert violation.severity == "error"
    assert violation.policy_type == "rbac"
    assert violation.model_name == "__rbac__"
    assert "insufficient" in violation.message.lower() or "missing" in violation.message.lower()
    assert violation.expected == "Role: platform-engineer"
    assert violation.actual == "User roles: ['viewer']"
    assert "Request role assignment" in violation.suggestion
    assert violation.documentation_url == "https://floe.dev/docs/governance/rbac#insufficient-role"

    mock_identity_plugin.validate_token.assert_called_once_with("valid-token")


@pytest.mark.requirement("3E-FR-003")
def test_principal_fallback_when_no_token(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test principal fallback passes when no token but principal provided.

    Given no token but --principal provided and allow_principal_fallback=True,
    When RBACChecker.check() is called,
    Then it should return no violations (bypasses OIDC check).
    """
    # Arrange
    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token=None, principal="service-account-xyz")

    # Assert
    assert violations == []
    # validate_token should NOT be called when using principal fallback
    mock_identity_plugin.validate_token.assert_not_called()


@pytest.mark.requirement("3E-FR-003")
def test_principal_fallback_disabled(
    mock_identity_plugin: MagicMock,
    rbac_config_no_principal_fallback: RBACConfig,
) -> None:
    """Test that principal fallback fails when allow_principal_fallback=False.

    Given no token, principal provided, but allow_principal_fallback=False,
    When RBACChecker.check() is called,
    Then it should return FLOE-E501 violation.
    """
    # Arrange
    checker = RBACChecker(
        rbac_config=rbac_config_no_principal_fallback,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token=None, principal="service-account-xyz")

    # Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.error_code == "FLOE-E501"
    assert violation.severity == "error"
    assert violation.policy_type == "rbac"
    assert "principal fallback disabled" in violation.message.lower()
    assert violation.expected == "OIDC token (principal fallback disabled)"
    assert violation.actual == "Principal provided but fallback disabled"

    mock_identity_plugin.validate_token.assert_not_called()


@pytest.mark.requirement("3E-FR-002")
def test_rbac_disabled_skips_check(
    mock_identity_plugin: MagicMock,
    rbac_config_disabled: RBACConfig,
) -> None:
    """Test that RBAC checks are skipped when enabled=False.

    Given RBACConfig(enabled=False),
    When RBACChecker.check() is called,
    Then it should return no violations without calling identity plugin.
    """
    # Arrange
    checker = RBACChecker(
        rbac_config=rbac_config_disabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token=None, principal=None)

    # Assert
    assert violations == []
    # Should not even attempt to validate token when RBAC is disabled
    mock_identity_plugin.validate_token.assert_not_called()


@pytest.mark.requirement("3E-FR-002")
def test_no_required_role_means_any_valid_token_passes(
    mock_identity_plugin: MagicMock,
    rbac_config_no_required_role: RBACConfig,
) -> None:
    """Test that any valid token passes when required_role=None.

    Given enabled=True but required_role=None,
    When RBACChecker.check() is called with a valid token,
    Then it should pass (only validates token existence, not roles).
    """
    # Arrange
    user_info = UserInfo(
        subject="user123",
        email="anyuser@example.com",
        name="Any User",
        roles=["viewer"],  # Any role is acceptable
    )
    mock_identity_plugin.validate_token.return_value = TokenValidationResult(
        valid=True,
        user_info=user_info,
        expires_at="2026-12-31T23:59:59Z",
    )

    checker = RBACChecker(
        rbac_config=rbac_config_no_required_role,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token="valid-token", principal=None)

    # Assert
    assert violations == []
    mock_identity_plugin.validate_token.assert_called_once_with("valid-token")


@pytest.mark.requirement("3E-FR-002")
def test_violations_have_correct_structure(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that Violation objects have all required fields populated correctly.

    Given any RBAC violation,
    When the violation is created,
    Then it should have correct model_name, suggestion, documentation_url, etc.
    """
    # Arrange
    mock_identity_plugin.validate_token.return_value = TokenValidationResult(
        valid=False,
        error="Invalid signature",
    )

    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token="invalid-token", principal=None)

    # Assert
    assert len(violations) == 1
    violation = violations[0]

    # Verify all required Violation fields are present
    assert violation.error_code.startswith("FLOE-E")
    assert violation.severity in ["error", "warning"]
    assert violation.policy_type == "rbac"
    assert violation.model_name == "__rbac__"
    assert len(violation.message) > 0
    assert len(violation.expected) > 0
    assert len(violation.actual) > 0
    assert len(violation.suggestion) > 0
    assert violation.documentation_url.startswith("https://floe.dev/docs/governance/rbac")

    # column_name should be None for RBAC violations (model-level)
    assert violation.column_name is None


@pytest.mark.requirement("3E-FR-002")
def test_token_validation_error_message_propagated(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that token validation error messages are propagated to violations.

    Given a token validation failure with a specific error message,
    When RBACChecker.check() is called,
    Then the error message should appear in violation.actual.
    """
    # Arrange
    mock_identity_plugin.validate_token.return_value = TokenValidationResult(
        valid=False,
        error="Invalid issuer: expected https://auth.example.com",
    )

    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    # Act
    violations = checker.check(token="bad-issuer-token", principal=None)

    # Assert
    assert len(violations) == 1
    violation = violations[0]
    assert violation.actual == "Invalid issuer: expected https://auth.example.com"


@pytest.mark.requirement("3E-FR-002")
def test_rbac_checker_handles_identity_plugin_exception(
    mock_identity_plugin: MagicMock,
    rbac_config_enabled: RBACConfig,
) -> None:
    """Test that identity plugin exception produces FLOE-E503 violation.

    Given the identity plugin raises RuntimeError during validate_token,
    When RBACChecker.check() is called,
    Then it should return a Violation with error_code="FLOE-E503".
    """
    mock_identity_plugin.validate_token.side_effect = RuntimeError(
        "Identity provider connection failed"
    )

    checker = RBACChecker(
        rbac_config=rbac_config_enabled,
        identity_plugin=mock_identity_plugin,
    )

    violations = checker.check(token="some-token", principal=None)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.error_code == "FLOE-E503"
    assert violation.severity == "error"
    assert violation.policy_type == "rbac"
    assert "Identity provider connection failed" in violation.message
