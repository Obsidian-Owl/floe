"""Integration tests for authorization flow (T129).

Task ID: T129
Phase: 12 - Authorization (US10)
User Story: US10 - Authorization and Access Control
Requirements: FR-045, FR-046, FR-047, FR-048

Tests the authorization flow integration with PromotionController:
- FR-045: Operator identity verification
- FR-046: Environment-specific authorization rules
- FR-047: Group-based access control
- FR-048: Authorization decision recording in audit trail
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from floe_core.schemas.promotion import PromotionConfig

# Test constants
TEST_DIGEST = "sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1"


class TestAuthorizationIntegration:
    """Integration tests for authorization flow with PromotionController."""

    @pytest.fixture
    def mock_oci_client(self) -> MagicMock:
        """Create a mock OCI client for testing."""
        client = MagicMock()
        client.registry_uri = "oci://test.registry.io/repo"
        client._build_target_ref.return_value = "test.registry.io/repo:v1.0.0"
        client._credentials = None  # No credentials by default
        return client

    @pytest.fixture
    def promotion_config_with_auth(self) -> PromotionConfig:
        """Create promotion config with authorization rules."""
        from floe_core.schemas.promotion import (
            AuthorizationConfig,
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        return PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                    authorization=None,  # No auth required for dev
                ),
                EnvironmentConfig(
                    name="staging",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                    authorization=AuthorizationConfig(
                        allowed_groups=["release-managers", "platform-admins"],
                    ),
                ),
                EnvironmentConfig(
                    name="prod",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                    authorization=AuthorizationConfig(
                        allowed_groups=["platform-admins"],
                        allowed_operators=["emergency-release@example.com"],
                        separation_of_duties=True,
                    ),
                ),
            ],
        )

    @pytest.mark.requirement("FR-046")
    def test_promote_without_auth_config_allows_all(
        self,
        mock_oci_client: MagicMock,
    ) -> None:
        """Test promotion succeeds when no authorization config exists."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import (
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        # Config without authorization rules
        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="staging",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
            ],
        )

        controller = PromotionController(
            client=mock_oci_client,
            promotion=config,
        )

        # Mock internal methods to avoid actual registry operations
        with patch.object(controller, "_get_artifact_digest", return_value=TEST_DIGEST):
            with patch.object(controller, "_run_all_gates", return_value=[]):
                with patch.object(controller, "_verify_signature") as mock_verify:
                    mock_verify.return_value = MagicMock(status="valid")
                    with patch.object(controller, "_create_env_tag"):
                        with patch.object(controller, "_update_latest_tag"):
                            with patch.object(controller, "_store_promotion_record"):
                                # Any operator should be allowed
                                record = controller.promote(
                                    tag="v1.0.0",
                                    from_env="dev",
                                    to_env="staging",
                                    operator="random@example.com",
                                )
                                assert record.authorization_passed is True
                                assert record.authorized_via == "no_config"

    @pytest.mark.requirement("FR-047")
    def test_promote_with_authorized_group(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_auth: PromotionConfig,
    ) -> None:
        """Test promotion succeeds when operator is in allowed group."""
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_auth,
        )

        # Mock client credentials with group membership
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {
            "groups": ["release-managers", "developers"],
        }

        with patch.object(controller, "_get_artifact_digest", return_value=TEST_DIGEST):
            with patch.object(controller, "_run_all_gates", return_value=[]):
                with patch.object(controller, "_verify_signature") as mock_verify:
                    mock_verify.return_value = MagicMock(status="valid")
                    with patch.object(controller, "_create_env_tag"):
                        with patch.object(controller, "_update_latest_tag"):
                            with patch.object(controller, "_store_promotion_record"):
                                record = controller.promote(
                                    tag="v1.0.0",
                                    from_env="dev",
                                    to_env="staging",
                                    operator="alice@example.com",
                                )
                                assert record.authorization_passed is True
                                assert "group:release-managers" in record.authorized_via
                                # T130: Verify operator_groups audit field
                                assert record.operator_groups == [
                                    "release-managers",
                                    "developers",
                                ]

    @pytest.mark.requirement("FR-046")
    def test_promote_with_authorized_operator(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_auth: PromotionConfig,
    ) -> None:
        """Test promotion succeeds when operator is explicitly allowed."""
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_auth,
        )

        # No group membership, but operator is explicitly allowed for prod
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": []}

        with patch.object(controller, "_get_artifact_digest", return_value=TEST_DIGEST):
            with patch.object(controller, "_run_all_gates", return_value=[]):
                with patch.object(controller, "_verify_signature") as mock_verify:
                    mock_verify.return_value = MagicMock(status="valid")
                    with patch.object(controller, "_create_env_tag"):
                        with patch.object(controller, "_update_latest_tag"):
                            with patch.object(controller, "_store_promotion_record"):
                                record = controller.promote(
                                    tag="v1.0.0",
                                    from_env="staging",
                                    to_env="prod",
                                    operator="emergency-release@example.com",
                                )
                                assert record.authorization_passed is True
                                assert "operator:" in record.authorized_via

    @pytest.mark.requirement("FR-047")
    def test_promote_denied_not_in_group(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_auth: PromotionConfig,
    ) -> None:
        """Test promotion denied when operator not in allowed groups."""
        from floe_core.oci.errors import AuthorizationError
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_auth,
        )

        # Operator in wrong group
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {
            "groups": ["developers"],  # Not release-managers or platform-admins
        }

        with pytest.raises(AuthorizationError) as exc_info:
            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="alice@example.com",
            )

        assert exc_info.value.exit_code == 12
        assert "alice@example.com" in str(exc_info.value)
        assert "release-managers" in str(exc_info.value) or "platform-admins" in str(exc_info.value)

    @pytest.mark.requirement("FR-046")
    def test_promote_denied_not_allowed_operator(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_auth: PromotionConfig,
    ) -> None:
        """Test promotion denied when operator not in allowed list for prod."""
        from floe_core.oci.errors import AuthorizationError
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_auth,
        )

        # No group membership and not an allowed operator
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": []}

        with pytest.raises(AuthorizationError) as exc_info:
            controller.promote(
                tag="v1.0.0",
                from_env="staging",
                to_env="prod",
                operator="random@example.com",
            )

        assert exc_info.value.exit_code == 12
        assert "random@example.com" in str(exc_info.value)

    @pytest.mark.requirement("FR-048")
    def test_authorization_decision_recorded_in_audit(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_auth: PromotionConfig,
    ) -> None:
        """Test authorization decision is recorded in PromotionRecord."""
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_auth,
        )

        # Authorized via group
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {
            "groups": ["platform-admins"],
        }

        with patch.object(controller, "_get_artifact_digest", return_value=TEST_DIGEST):
            with patch.object(controller, "_run_all_gates", return_value=[]):
                with patch.object(controller, "_verify_signature") as mock_verify:
                    mock_verify.return_value = MagicMock(status="valid")
                    with patch.object(controller, "_create_env_tag"):
                        with patch.object(controller, "_update_latest_tag"):
                            with patch.object(controller, "_store_promotion_record"):
                                record = controller.promote(
                                    tag="v1.0.0",
                                    from_env="dev",
                                    to_env="staging",
                                    operator="admin@example.com",
                                )

        # Verify audit fields are populated
        assert record.authorization_passed is True
        assert record.authorized_via is not None
        assert "group:" in record.authorized_via
        # T130: Verify operator_groups audit field (FR-048)
        assert record.operator_groups == ["platform-admins"]


class TestAuthorizationErrorMessages:
    """Tests for authorization error message quality (FR-048)."""

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_includes_operator(self) -> None:
        """Test AuthorizationError includes operator identity."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=["platform-admins"],
            reason="Not a member of required groups",
        )
        assert "alice@example.com" in str(error)

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_includes_required_groups(self) -> None:
        """Test AuthorizationError includes required groups."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=["platform-admins", "release-managers"],
            reason="Not a member of required groups",
        )
        assert "platform-admins" in str(error)
        assert "release-managers" in str(error)

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_exit_code(self) -> None:
        """Test AuthorizationError has correct exit code (12)."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=["admins"],
            reason="Not authorized",
        )
        assert error.exit_code == 12

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_includes_environment(self) -> None:
        """Test AuthorizationError includes environment in message (T132)."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=["platform-admins"],
            reason="Not a member of required groups",
            environment="prod",
        )
        assert "prod" in str(error)
        assert error.environment == "prod"

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_includes_actionable_guidance(self) -> None:
        """Test AuthorizationError includes actionable guidance (T132)."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=["platform-admins"],
            reason="Not a member of required groups",
            environment="prod",
        )
        error_str = str(error)
        # Should include guidance about getting access
        assert "Request membership" in error_str or "get access" in error_str.lower()
        # Should include info command
        assert "floe promote info" in error_str

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_get_actionable_guidance_method(self) -> None:
        """Test AuthorizationError.get_actionable_guidance() method (T132)."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=["platform-admins", "release-managers"],
            reason="Not authorized",
            environment="staging",
        )
        guidance = error.get_actionable_guidance()

        # Should include steps
        assert "1." in guidance
        assert "platform-admins" in guidance
        assert "floe promote info" in guidance
        assert "floe whoami" in guidance

    @pytest.mark.requirement("FR-048")
    def test_authorization_error_with_allowed_operators(self) -> None:
        """Test AuthorizationError shows allowed operators when no groups (T132)."""
        from floe_core.oci.errors import AuthorizationError

        error = AuthorizationError(
            operator="alice@example.com",
            required_groups=[],
            reason="Not in allowed operators list",
            environment="prod",
            allowed_operators=["admin@example.com", "ops@example.com"],
        )
        error_str = str(error)
        # Should include allowed operators info
        assert "admin@example.com" in error_str or "Allowed operators" in error_str


class TestSeparationOfDutiesIntegration:
    """Integration tests for separation of duties enforcement (T137, T138).

    Tests FR-049, FR-050, FR-051, FR-052:
    - FR-049: Same operator cannot promote to consecutive environments
    - FR-050: Enable/disable per environment
    - FR-051: Result schema for audit trail
    - FR-052: Case-insensitive operator comparison
    """

    @pytest.fixture
    def mock_oci_client(self) -> MagicMock:
        """Create a mock OCI client for testing."""
        client = MagicMock()
        client.registry_uri = "oci://test.registry.io/repo"
        client._build_target_ref.return_value = "test.registry.io/repo:v1.0.0"
        client._credentials = None
        return client

    @pytest.fixture
    def promotion_config_with_sod(self) -> PromotionConfig:
        """Create promotion config with separation of duties enabled for prod."""
        from floe_core.schemas.promotion import (
            AuthorizationConfig,
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        return PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="dev",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="staging",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                    authorization=AuthorizationConfig(
                        allowed_groups=["release-managers", "platform-admins"],
                    ),
                ),
                EnvironmentConfig(
                    name="prod",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                    authorization=AuthorizationConfig(
                        allowed_groups=["platform-admins"],
                        separation_of_duties=True,
                    ),
                ),
            ],
        )

    @pytest.mark.requirement("FR-049")
    def test_promote_fails_same_operator_consecutive_environments(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_sod: PromotionConfig,
    ) -> None:
        """Test promotion fails when same operator promotes consecutively (FR-049).

        Separation of duties check happens BEFORE gates and signature verification,
        so this test should fail immediately at the separation check.
        """
        from floe_core.oci.errors import SeparationOfDutiesError
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_sod,
        )

        # Operator is in platform-admins (authorized)
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": ["platform-admins"]}

        # Mock _get_previous_operator to return same operator
        # The check should fail BEFORE gates/signature verification
        with patch.object(controller, "_get_previous_operator", return_value="alice@example.com"):
            with pytest.raises(SeparationOfDutiesError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="staging",
                    to_env="prod",
                    operator="alice@example.com",
                )

        assert exc_info.value.exit_code == 14
        assert "alice@example.com" in str(exc_info.value)
        assert "separation of duties" in str(exc_info.value).lower()
        assert exc_info.value.from_env == "staging"
        assert exc_info.value.to_env == "prod"

    @pytest.mark.requirement("FR-049")
    def test_promote_succeeds_different_operator(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_sod: PromotionConfig,
    ) -> None:
        """Test promotion succeeds when different operator promotes (FR-049)."""
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_sod,
        )

        # Operator is in platform-admins (authorized)
        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": ["platform-admins"]}

        # Mock _get_previous_operator to return different operator
        with patch.object(controller, "_get_previous_operator", return_value="alice@example.com"):
            with patch.object(
                controller,
                "_get_artifact_digest",
                return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
            ):
                with patch.object(controller, "_run_all_gates", return_value=[]):
                    with patch.object(controller, "_verify_signature") as mock_verify:
                        mock_verify.return_value = MagicMock(status="valid")
                        with patch.object(controller, "_create_env_tag"):
                            with patch.object(controller, "_update_latest_tag"):
                                with patch.object(controller, "_store_promotion_record"):
                                    # Bob promotes, Alice previously promoted - should succeed
                                    record = controller.promote(
                                        tag="v1.0.0",
                                        from_env="staging",
                                        to_env="prod",
                                        operator="bob@example.com",
                                    )
                                    assert record.authorization_passed is True

    @pytest.mark.requirement("FR-050")
    def test_promote_succeeds_when_sod_disabled(
        self,
        mock_oci_client: MagicMock,
    ) -> None:
        """Test same operator can promote when separation_of_duties=False (FR-050)."""
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.promotion import (
            AuthorizationConfig,
            EnvironmentConfig,
            PromotionConfig,
            PromotionGate,
        )

        # Config with separation_of_duties=False
        config = PromotionConfig(
            environments=[
                EnvironmentConfig(
                    name="staging",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                ),
                EnvironmentConfig(
                    name="prod",
                    gates={PromotionGate.POLICY_COMPLIANCE: True},
                    authorization=AuthorizationConfig(
                        allowed_groups=["platform-admins"],
                        separation_of_duties=False,  # Explicitly disabled
                    ),
                ),
            ],
        )

        controller = PromotionController(
            client=mock_oci_client,
            promotion=config,
        )

        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": ["platform-admins"]}

        # Mock _get_previous_operator to return same operator
        with patch.object(controller, "_get_previous_operator", return_value="alice@example.com"):
            with patch.object(
                controller,
                "_get_artifact_digest",
                return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
            ):
                with patch.object(controller, "_run_all_gates", return_value=[]):
                    with patch.object(controller, "_verify_signature") as mock_verify:
                        mock_verify.return_value = MagicMock(status="valid")
                        with patch.object(controller, "_create_env_tag"):
                            with patch.object(controller, "_update_latest_tag"):
                                with patch.object(controller, "_store_promotion_record"):
                                    # Same operator should succeed when SOD disabled
                                    record = controller.promote(
                                        tag="v1.0.0",
                                        from_env="staging",
                                        to_env="prod",
                                        operator="alice@example.com",
                                    )
                                    assert record.authorization_passed is True

    @pytest.mark.requirement("FR-049")
    def test_promote_succeeds_first_promotion_no_previous_operator(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_sod: PromotionConfig,
    ) -> None:
        """Test first promotion succeeds when no previous operator exists (FR-049)."""
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_sod,
        )

        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": ["platform-admins"]}

        # Mock _get_previous_operator to return None (no previous promotion)
        with patch.object(controller, "_get_previous_operator", return_value=None):
            with patch.object(
                controller,
                "_get_artifact_digest",
                return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
            ):
                with patch.object(controller, "_run_all_gates", return_value=[]):
                    with patch.object(controller, "_verify_signature") as mock_verify:
                        mock_verify.return_value = MagicMock(status="valid")
                        with patch.object(controller, "_create_env_tag"):
                            with patch.object(controller, "_update_latest_tag"):
                                with patch.object(controller, "_store_promotion_record"):
                                    record = controller.promote(
                                        tag="v1.0.0",
                                        from_env="staging",
                                        to_env="prod",
                                        operator="alice@example.com",
                                    )
                                    assert record.authorization_passed is True

    @pytest.mark.requirement("FR-052")
    def test_promote_fails_case_insensitive_operator_comparison(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_sod: PromotionConfig,
    ) -> None:
        """Test separation of duties is case-insensitive (FR-052).

        Separation of duties check happens BEFORE gates and signature verification.
        """
        from floe_core.oci.errors import SeparationOfDutiesError
        from floe_core.oci.promotion import PromotionController

        controller = PromotionController(
            client=mock_oci_client,
            promotion=promotion_config_with_sod,
        )

        mock_oci_client._credentials = MagicMock()
        mock_oci_client._credentials.metadata = {"groups": ["platform-admins"]}

        # Previous operator was lowercase, current is uppercase - should still fail
        # The check should fail BEFORE gates/signature verification
        with patch.object(controller, "_get_previous_operator", return_value="alice@example.com"):
            with pytest.raises(SeparationOfDutiesError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="staging",
                    to_env="prod",
                    operator="ALICE@EXAMPLE.COM",  # Different case
                )


class TestSeparationOfDutiesErrorMessages:
    """Tests for separation of duties error message quality (T140)."""

    @pytest.mark.requirement("FR-052")
    def test_separation_of_duties_error_includes_operators(self) -> None:
        """Test SeparationOfDutiesError includes both operators."""
        from floe_core.oci.errors import SeparationOfDutiesError

        error = SeparationOfDutiesError(
            operator="alice@example.com",
            previous_operator="alice@example.com",
            from_env="staging",
            to_env="prod",
        )
        error_str = str(error)
        assert "alice@example.com" in error_str
        assert "staging" in error_str
        assert "prod" in error_str

    @pytest.mark.requirement("FR-052")
    def test_separation_of_duties_error_exit_code(self) -> None:
        """Test SeparationOfDutiesError has correct exit code (14)."""
        from floe_core.oci.errors import SeparationOfDutiesError

        error = SeparationOfDutiesError(
            operator="alice@example.com",
            previous_operator="alice@example.com",
            from_env="staging",
            to_env="prod",
        )
        assert error.exit_code == 14

    @pytest.mark.requirement("FR-052")
    def test_separation_of_duties_error_includes_remediation(self) -> None:
        """Test SeparationOfDutiesError includes remediation steps."""
        from floe_core.oci.errors import SeparationOfDutiesError

        error = SeparationOfDutiesError(
            operator="alice@example.com",
            previous_operator="alice@example.com",
            from_env="staging",
            to_env="prod",
        )
        error_str = str(error)
        assert "Remediation" in error_str
        error_str_lower = error_str.lower()
        assert "different team member" in error_str_lower or "different operator" in error_str_lower
