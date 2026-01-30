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

from unittest.mock import MagicMock, patch

import pytest


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
    def promotion_config_with_auth(self) -> "PromotionConfig":
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
        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1"):
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
        promotion_config_with_auth: "PromotionConfig",
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

        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1"):
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
                                assert record.operator_groups == ["release-managers", "developers"]

    @pytest.mark.requirement("FR-046")
    def test_promote_with_authorized_operator(
        self,
        mock_oci_client: MagicMock,
        promotion_config_with_auth: "PromotionConfig",
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

        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1"):
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
        promotion_config_with_auth: "PromotionConfig",
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
        promotion_config_with_auth: "PromotionConfig",
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
        promotion_config_with_auth: "PromotionConfig",
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

        with patch.object(controller, "_get_artifact_digest", return_value="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1"):
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
