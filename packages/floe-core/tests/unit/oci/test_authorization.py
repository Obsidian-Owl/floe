"""Unit tests for AuthorizationChecker (T124).

Task ID: T124
Phase: 12 - Authorization (US10)
User Story: US10 - Authorization and Access Control
Requirements: FR-045, FR-046, FR-047, FR-048

TDD: These tests are written FIRST and should FAIL until implementation.

Tests the AuthorizationChecker class that enforces:
- FR-045: Operator identity verification
- FR-046: Environment-specific authorization rules
- FR-047: Group-based access control
- FR-048: Authorization decision recording
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestAuthorizationCheckerInit:
    """Tests for AuthorizationChecker initialization."""

    @pytest.mark.requirement("FR-046")
    def test_authorization_checker_init_with_config(self) -> None:
        """Test AuthorizationChecker initialization with AuthorizationConfig."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins"],
            separation_of_duties=False,
        )
        checker = AuthorizationChecker(config=config)
        assert checker.config == config

    @pytest.mark.requirement("FR-046")
    def test_authorization_checker_init_without_config(self) -> None:
        """Test AuthorizationChecker initialization without config allows all."""
        from floe_core.oci.authorization import AuthorizationChecker

        checker = AuthorizationChecker(config=None)
        assert checker.config is None


class TestAuthorizationCheckerCheckAuthorization:
    """Tests for AuthorizationChecker.check_authorization() method."""

    @pytest.mark.requirement("FR-047")
    def test_check_authorization_allowed_by_group(self) -> None:
        """Test authorization passes when operator is in allowed group."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins", "release-managers"],
        )
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="alice@example.com",
            groups=["platform-admins", "developers"],
        )
        assert result.authorized is True
        assert result.authorized_via == "group:platform-admins"

    @pytest.mark.requirement("FR-046")
    def test_check_authorization_allowed_by_operator(self) -> None:
        """Test authorization passes when operator is in allowed_operators."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_operators=["alice@example.com", "bob@example.com"],
        )
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="alice@example.com",
            groups=[],
        )
        assert result.authorized is True
        assert result.authorized_via == "operator:alice@example.com"

    @pytest.mark.requirement("FR-047")
    def test_check_authorization_denied_not_in_group(self) -> None:
        """Test authorization denied when operator not in any allowed group."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins"],
        )
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="alice@example.com",
            groups=["developers"],  # Not in platform-admins
        )
        assert result.authorized is False
        assert "platform-admins" in result.reason

    @pytest.mark.requirement("FR-046")
    def test_check_authorization_denied_not_allowed_operator(self) -> None:
        """Test authorization denied when operator not in allowed_operators."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_operators=["admin@example.com"],
        )
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="alice@example.com",
            groups=[],
        )
        assert result.authorized is False
        assert (
            "alice@example.com" in result.reason
            or "not authorized" in result.reason.lower()
        )

    @pytest.mark.requirement("FR-046")
    def test_check_authorization_no_restrictions_allows_all(self) -> None:
        """Test authorization passes when no groups/operators configured."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()  # No restrictions
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="anyone@example.com",
            groups=[],
        )
        assert result.authorized is True
        assert result.authorized_via == "no_restrictions"

    @pytest.mark.requirement("FR-046")
    def test_check_authorization_no_config_allows_all(self) -> None:
        """Test authorization passes when checker has no config."""
        from floe_core.oci.authorization import AuthorizationChecker

        checker = AuthorizationChecker(config=None)

        result = checker.check_authorization(
            operator="anyone@example.com",
            groups=[],
        )
        assert result.authorized is True
        assert result.authorized_via == "no_config"

    @pytest.mark.requirement("FR-047")
    def test_check_authorization_combined_groups_and_operators(self) -> None:
        """Test authorization with both groups and operators (OR semantics)."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins"],
            allowed_operators=["special@example.com"],
        )
        checker = AuthorizationChecker(config=config)

        # Allowed by operator (not in group)
        result = checker.check_authorization(
            operator="special@example.com",
            groups=["developers"],
        )
        assert result.authorized is True
        assert "operator" in result.authorized_via

        # Allowed by group (not in operators)
        result2 = checker.check_authorization(
            operator="admin@example.com",
            groups=["platform-admins"],
        )
        assert result2.authorized is True
        assert "group" in result2.authorized_via

    @pytest.mark.requirement("FR-047")
    def test_check_authorization_multiple_groups_match(self) -> None:
        """Test authorization picks first matching group."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["admins", "operators", "developers"],
        )
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="alice@example.com",
            groups=["developers", "admins"],  # Both match
        )
        assert result.authorized is True
        # Should match one of the allowed groups
        assert "group:" in result.authorized_via


class TestAuthorizationResult:
    """Tests for AuthorizationResult schema."""

    @pytest.mark.requirement("FR-048")
    def test_authorization_result_authorized(self) -> None:
        """Test AuthorizationResult for authorized access."""
        from floe_core.oci.authorization import AuthorizationResult

        result = AuthorizationResult(
            authorized=True,
            operator="alice@example.com",
            authorized_via="group:platform-admins",
        )
        assert result.authorized is True
        assert result.operator == "alice@example.com"
        assert result.authorized_via == "group:platform-admins"
        assert result.reason is None

    @pytest.mark.requirement("FR-048")
    def test_authorization_result_denied(self) -> None:
        """Test AuthorizationResult for denied access."""
        from floe_core.oci.authorization import AuthorizationResult

        result = AuthorizationResult(
            authorized=False,
            operator="alice@example.com",
            reason="Operator not in allowed groups: ['platform-admins']",
        )
        assert result.authorized is False
        assert result.reason is not None
        assert "platform-admins" in result.reason

    @pytest.mark.requirement("FR-048")
    def test_authorization_result_frozen(self) -> None:
        """Test AuthorizationResult is immutable."""
        from floe_core.oci.authorization import AuthorizationResult

        result = AuthorizationResult(
            authorized=True,
            operator="alice@example.com",
            authorized_via="group:admins",
        )
        with pytest.raises(ValidationError):  # Frozen model raises ValidationError
            result.authorized = False  # type: ignore[misc]


class TestAuthorizationDecisionAudit:
    """Tests for authorization decision audit recording (FR-048)."""

    @pytest.mark.requirement("FR-048")
    def test_authorization_result_includes_timestamp(self) -> None:
        """Test AuthorizationResult includes check timestamp."""
        from floe_core.oci.authorization import AuthorizationResult

        result = AuthorizationResult(
            authorized=True,
            operator="alice@example.com",
            authorized_via="group:admins",
        )
        # checked_at should be set automatically
        assert result.checked_at is not None

    @pytest.mark.requirement("FR-048")
    def test_authorization_result_includes_groups_checked(self) -> None:
        """Test AuthorizationResult includes groups that were checked."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(
            allowed_groups=["platform-admins"],
        )
        checker = AuthorizationChecker(config=config)

        result = checker.check_authorization(
            operator="alice@example.com",
            groups=["developers", "testers"],
        )
        # Result should record what groups were checked
        assert result.groups_checked == ["developers", "testers"]

    @pytest.mark.requirement("FR-048")
    def test_authorization_result_to_dict_for_audit(self) -> None:
        """Test AuthorizationResult can be serialized for audit trail."""
        from floe_core.oci.authorization import AuthorizationResult

        result = AuthorizationResult(
            authorized=True,
            operator="alice@example.com",
            authorized_via="group:admins",
            groups_checked=["admins", "developers"],
        )
        audit_data = result.model_dump()
        assert "authorized" in audit_data
        assert "operator" in audit_data
        assert "authorized_via" in audit_data
        assert "checked_at" in audit_data
        assert "groups_checked" in audit_data


class TestOperatorIdentityVerification:
    """Tests for operator identity verification (FR-045)."""

    @pytest.mark.requirement("FR-045")
    def test_get_operator_identity_from_registry_auth(self) -> None:
        """Test getting operator identity from registry authentication."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()
        checker = AuthorizationChecker(config=config)

        # Mock registry credentials that contain identity
        mock_credentials = {
            "username": "alice@example.com",
            "token": "xxxxxx",
        }
        identity = checker.get_operator_identity(credentials=mock_credentials)
        assert identity == "alice@example.com"

    @pytest.mark.requirement("FR-045")
    def test_get_operator_identity_fallback_to_env(self) -> None:
        """Test operator identity falls back to environment variable."""
        import os

        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()
        checker = AuthorizationChecker(config=config)

        # Set environment variable
        os.environ["FLOE_OPERATOR"] = "env-user@example.com"
        try:
            identity = checker.get_operator_identity(credentials=None)
            assert identity == "env-user@example.com"
        finally:
            del os.environ["FLOE_OPERATOR"]

    @pytest.mark.requirement("FR-045")
    def test_get_operator_groups_from_registry(self) -> None:
        """Test getting operator groups from registry metadata."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()
        checker = AuthorizationChecker(config=config)

        # Mock registry metadata with groups
        mock_metadata = {
            "groups": ["platform-admins", "developers"],
        }
        groups = checker.get_operator_groups(metadata=mock_metadata)
        assert groups == ["platform-admins", "developers"]

    @pytest.mark.requirement("FR-045")
    def test_get_operator_groups_empty_if_no_metadata(self) -> None:
        """Test operator groups returns empty list if no metadata."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()
        checker = AuthorizationChecker(config=config)

        groups = checker.get_operator_groups(metadata=None)
        assert groups == []


class TestSeparationOfDuties:
    """Tests for separation of duties enforcement (T134).

    Task ID: T134
    Phase: 13 - Separation of Duties (US11)
    User Story: US11 - Separation of Duties
    Requirements: FR-049, FR-050, FR-051, FR-052

    TDD: These tests are written FIRST and should FAIL until implementation.

    Tests the separation of duties logic that prevents the same operator
    from promoting an artifact through consecutive environments.
    """

    @pytest.mark.requirement("FR-049")
    def test_check_separation_of_duties_passes_different_operator(self) -> None:
        """Test separation of duties passes when different operators promote."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=True)
        checker = AuthorizationChecker(config=config)

        # Alice promoted to dev, Bob promoting to staging - should pass
        result = checker.check_separation_of_duties(
            operator="bob@example.com",
            previous_operator="alice@example.com",
        )
        assert result.allowed is True
        assert result.reason is None

    @pytest.mark.requirement("FR-049")
    def test_check_separation_of_duties_fails_same_operator(self) -> None:
        """Test separation of duties fails when same operator promotes consecutive envs."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=True)
        checker = AuthorizationChecker(config=config)

        # Alice promoted to dev, Alice trying to promote to staging - should fail
        result = checker.check_separation_of_duties(
            operator="alice@example.com",
            previous_operator="alice@example.com",
        )
        assert result.allowed is False
        assert "alice@example.com" in result.reason
        assert "separation" in result.reason.lower()

    @pytest.mark.requirement("FR-050")
    def test_check_separation_of_duties_disabled_allows_same_operator(self) -> None:
        """Test same operator allowed when separation_of_duties is disabled."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=False)
        checker = AuthorizationChecker(config=config)

        # Same operator, but separation_of_duties is disabled
        result = checker.check_separation_of_duties(
            operator="alice@example.com",
            previous_operator="alice@example.com",
        )
        assert result.allowed is True

    @pytest.mark.requirement("FR-050")
    def test_check_separation_of_duties_no_previous_operator(self) -> None:
        """Test separation of duties passes when no previous promotion exists."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=True)
        checker = AuthorizationChecker(config=config)

        # First promotion in chain (no previous operator)
        result = checker.check_separation_of_duties(
            operator="alice@example.com",
            previous_operator=None,
        )
        assert result.allowed is True

    @pytest.mark.requirement("FR-051")
    def test_check_separation_of_duties_result_includes_operators(self) -> None:
        """Test separation of duties result includes operator identities."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=True)
        checker = AuthorizationChecker(config=config)

        result = checker.check_separation_of_duties(
            operator="alice@example.com",
            previous_operator="bob@example.com",
        )
        assert result.operator == "alice@example.com"
        assert result.previous_operator == "bob@example.com"

    @pytest.mark.requirement("FR-052")
    def test_check_separation_of_duties_case_insensitive(self) -> None:
        """Test separation of duties comparison is case-insensitive for emails."""
        from floe_core.oci.authorization import AuthorizationChecker
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig(separation_of_duties=True)
        checker = AuthorizationChecker(config=config)

        # Same operator with different case
        result = checker.check_separation_of_duties(
            operator="Alice@Example.com",
            previous_operator="alice@example.com",
        )
        assert result.allowed is False  # Should detect same person

    @pytest.mark.requirement("FR-049")
    def test_separation_of_duties_config_defaults_to_false(self) -> None:
        """Test separation_of_duties defaults to False in AuthorizationConfig."""
        from floe_core.schemas.promotion import AuthorizationConfig

        config = AuthorizationConfig()
        assert config.separation_of_duties is False


class TestSeparationOfDutiesResult:
    """Tests for SeparationOfDutiesResult schema (T134)."""

    @pytest.mark.requirement("FR-051")
    def test_separation_of_duties_result_allowed(self) -> None:
        """Test SeparationOfDutiesResult for allowed promotion."""
        from floe_core.oci.authorization import SeparationOfDutiesResult

        result = SeparationOfDutiesResult(
            allowed=True,
            operator="bob@example.com",
            previous_operator="alice@example.com",
        )
        assert result.allowed is True
        assert result.operator == "bob@example.com"
        assert result.previous_operator == "alice@example.com"
        assert result.reason is None

    @pytest.mark.requirement("FR-051")
    def test_separation_of_duties_result_denied(self) -> None:
        """Test SeparationOfDutiesResult for denied promotion."""
        from floe_core.oci.authorization import SeparationOfDutiesResult

        result = SeparationOfDutiesResult(
            allowed=False,
            operator="alice@example.com",
            previous_operator="alice@example.com",
            reason="Separation of duties violation: same operator",
        )
        assert result.allowed is False
        assert result.reason is not None
        assert "separation" in result.reason.lower()

    @pytest.mark.requirement("FR-052")
    def test_separation_of_duties_result_frozen(self) -> None:
        """Test SeparationOfDutiesResult is immutable."""
        from floe_core.oci.authorization import SeparationOfDutiesResult

        result = SeparationOfDutiesResult(
            allowed=True,
            operator="alice@example.com",
            previous_operator=None,
        )
        with pytest.raises(ValidationError):  # Frozen model raises ValidationError
            result.allowed = False  # type: ignore[misc]
