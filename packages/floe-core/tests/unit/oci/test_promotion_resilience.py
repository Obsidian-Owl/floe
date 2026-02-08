"""Unit tests for promotion resilience - registry unavailable mid-promotion (T031b).

Tests for scenarios where registry becomes unavailable during promotion:
- Registry fails after gates pass but before tag creation
- Registry fails during latest tag update
- No partial state should be left behind

Requirements tested:
    NFR-003: Graceful degradation
    FR-001: Atomicity of promotion operations

⚠️ TDD: Tests WILL FAIL until T032 implements full promote() logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

# Test constants
TEST_DIGEST = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


class TestRegistryUnavailableMidPromotion:
    """Unit tests for registry unavailable mid-promotion (T031b)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-NFR-003")
    def test_promote_raises_registry_unavailable_when_tag_creation_fails(
        self, controller: MagicMock
    ) -> None:
        """Test promote() raises RegistryUnavailableError when tag creation fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Scenario: Registry becomes unavailable after gates pass but before
        the env tag can be created.
        """
        from floe_core.oci.errors import RegistryUnavailableError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            # Gates pass successfully
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                )
            ]
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            # Registry becomes unavailable during tag creation
            mock_create_tag.side_effect = RegistryUnavailableError(
                registry="harbor.example.com",
                reason="Connection refused",
            )

            with pytest.raises(RegistryUnavailableError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert "harbor.example.com" in str(exc_info.value)
            assert exc_info.value.exit_code == 5

    @pytest.mark.requirement("8C-NFR-003")
    def test_promote_no_partial_state_on_registry_failure(
        self, controller: MagicMock
    ) -> None:
        """Test promote() leaves no partial state when registry fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When registry becomes unavailable mid-promotion, no partial state
        (like env tag without record, or record without tag) should exist.
        """
        from floe_core.oci.errors import RegistryUnavailableError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            # Registry fails on tag creation
            mock_create_tag.side_effect = RegistryUnavailableError(
                registry="harbor.example.com",
                reason="Connection refused",
            )

            with pytest.raises(RegistryUnavailableError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # No further operations should have been attempted
            mock_update_latest.assert_not_called()
            mock_store.assert_not_called()

    @pytest.mark.requirement("8C-NFR-003")
    def test_promote_registry_unavailable_error_is_actionable(
        self, controller: MagicMock
    ) -> None:
        """Test RegistryUnavailableError message is actionable.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Error messages should include:
        - Which registry was unavailable
        - What operation failed
        - Suggested remediation steps
        """
        from floe_core.oci.errors import RegistryUnavailableError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            mock_create_tag.side_effect = RegistryUnavailableError(
                registry="harbor.example.com",
                reason="Connection timed out after 30s",
            )

            with pytest.raises(RegistryUnavailableError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            error_message = str(exc_info.value)
            # Should contain registry identifier
            assert "harbor.example.com" in error_message
            # Should contain reason
            assert (
                "timed out" in error_message.lower()
                or "connection" in error_message.lower()
            )

    @pytest.mark.requirement("8C-NFR-003")
    def test_promote_registry_fails_during_latest_tag_update(
        self, controller: MagicMock
    ) -> None:
        """Test promote() handles registry failure during latest tag update.

        Scenario: Env tag created successfully, but registry fails during
        latest tag update. This is a recoverable state - the env tag exists.
        The promote() should succeed (with warning) since env tag is the critical
        part and latest tag is non-critical.
        """
        from floe_core.oci.errors import RegistryUnavailableError
        from floe_core.schemas.promotion import PromotionRecord

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            # Tag created successfully
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            # Registry fails during latest tag update
            mock_update_latest.side_effect = RegistryUnavailableError(
                registry="harbor.example.com",
                reason="Connection refused",
            )

            # Promotion should succeed (with warning) since env tag was created
            # Latest tag update is non-critical - failure is logged but doesn't block
            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Env tag creation should have been called
            mock_create_tag.assert_called_once()
            # Promotion should return a valid record (partial success)
            assert isinstance(result, PromotionRecord)


class TestCircuitBreakerBehavior:
    """Unit tests for circuit breaker behavior during promotion (T031b)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-NFR-003")
    def test_promote_respects_circuit_breaker_open_state(
        self, controller: MagicMock
    ) -> None:
        """Test promote() fails fast when circuit breaker is open.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        If the registry circuit breaker is open (too many recent failures),
        promotion should fail immediately without attempting registry operations.
        """
        from floe_core.oci.errors import CircuitBreakerOpenError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            # Circuit breaker is open
            mock_create_tag.side_effect = CircuitBreakerOpenError(
                registry="harbor.example.com",
                failure_count=5,
            )

            with pytest.raises(CircuitBreakerOpenError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Exit code 5 for registry unavailable / circuit breaker
            assert exc_info.value.exit_code == 5

    @pytest.mark.requirement("8C-NFR-003")
    def test_promote_circuit_breaker_error_includes_retry_info(
        self, controller: MagicMock
    ) -> None:
        """Test CircuitBreakerOpenError includes retry information.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When circuit breaker is open, error should indicate when to retry.
        """
        from floe_core.oci.errors import CircuitBreakerOpenError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            mock_create_tag.side_effect = CircuitBreakerOpenError(
                registry="harbor.example.com",
                failure_count=5,
                recovery_at="2026-01-30T15:00:00Z",
            )

            with pytest.raises(CircuitBreakerOpenError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Error should include failure count and recovery timestamp
            assert exc_info.value.failure_count == 5
            assert exc_info.value.recovery_at == "2026-01-30T15:00:00Z"
