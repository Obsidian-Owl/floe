"""Unit tests for PromotionController.promote(dry_run=True) method (T039-T040).

Tests for dry-run promotion behavior:
- T039: Unit tests for promote(dry_run=True) behavior
- T040: Unit tests for dry-run output formatting

Requirements tested:
    FR-007: Dry-run validation without changes

See Also:
    - specs/8c-promotion-lifecycle/spec.md: Feature specification
    - User Story 2: Dry-Run Promotion
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate


class TestDryRunPromotion:
    """Unit tests for PromotionController.promote(dry_run=True) (T039)."""

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

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_does_not_create_env_tag(self, controller: MagicMock) -> None:
        """Test dry_run=True does NOT call _create_env_tag().

        Dry-run should validate without making registry changes.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ) as mock_create_tag, patch.object(
            controller, "_update_latest_tag"
        ) as mock_update_latest, patch.object(
            controller, "_store_promotion_record"
        ) as mock_store:
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                )
            ]
            mock_verify.return_value = Mock(status="valid")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Mutation methods should NOT be called in dry_run mode
            mock_create_tag.assert_not_called()
            mock_update_latest.assert_not_called()
            mock_store.assert_not_called()

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_does_not_update_latest_tag(self, controller: MagicMock) -> None:
        """Test dry_run=True does NOT call _update_latest_tag().

        Dry-run should validate without making registry changes.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ) as mock_update_latest, patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            mock_update_latest.assert_not_called()

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_does_not_store_promotion_record(self, controller: MagicMock) -> None:
        """Test dry_run=True does NOT call _store_promotion_record().

        Dry-run should not create audit records.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ) as mock_store:
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            mock_store.assert_not_called()

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_still_runs_gates(self, controller: MagicMock) -> None:
        """Test dry_run=True still executes validation gates.

        Gates should be validated even in dry-run mode to show what would happen.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                )
            ]
            mock_verify.return_value = Mock(status="valid")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Gates should still be called in dry_run mode
            mock_gates.assert_called_once()
            # Verify dry_run flag is passed to gates
            call_kwargs = mock_gates.call_args[1]
            assert call_kwargs.get("dry_run") is True

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_still_verifies_signature(self, controller: MagicMock) -> None:
        """Test dry_run=True still executes signature verification.

        Signatures should be verified even in dry-run mode to show what would happen.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Signature verification should still be called
            mock_verify.assert_called_once()

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_returns_record_with_dry_run_true(
        self, controller: MagicMock
    ) -> None:
        """Test dry_run=True returns PromotionRecord with dry_run=True.

        The returned record should indicate this was a dry-run.
        """
        from floe_core.schemas.promotion import PromotionRecord

        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            assert isinstance(result, PromotionRecord)
            assert result.dry_run is True

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_does_not_raise_on_gate_failure(
        self, controller: MagicMock
    ) -> None:
        """Test dry_run=True does NOT raise GateValidationError on gate failure.

        In dry-run mode, gate failures should be reported in the record,
        not raised as exceptions.
        """
        from floe_core.schemas.promotion import PromotionRecord

        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            # Return a FAILED gate result
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.FAILED,
                    duration_ms=100,
                    error="Policy compliance failed",
                )
            ]
            mock_verify.return_value = Mock(status="valid")

            # Should NOT raise GateValidationError in dry_run mode
            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Should return a record showing the failure
            assert isinstance(result, PromotionRecord)
            assert result.dry_run is True
            assert len(result.gate_results) == 1
            assert result.gate_results[0].status == GateStatus.FAILED

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_runs_all_gates_even_after_failure(
        self, controller: MagicMock
    ) -> None:
        """Test dry_run=True runs all gates even after one fails.

        In dry-run mode, all gates should run to show complete validation status.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            # Return multiple gate results - first fails, second passes
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.FAILED,
                    duration_ms=100,
                    error="Policy failed",
                ),
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.PASSED,
                    duration_ms=200,
                ),
            ]
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Should have all gate results, not just the first failure
            assert len(result.gate_results) == 2


class TestDryRunConvenienceMethod:
    """Unit tests for PromotionController.dry_run() convenience method."""

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

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_method_calls_promote_with_dry_run_true(
        self, controller: MagicMock
    ) -> None:
        """Test dry_run() convenience method calls promote(dry_run=True)."""
        with patch.object(controller, "promote") as mock_promote:
            mock_promote.return_value = Mock()

            controller.dry_run(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_promote.assert_called_once_with(
                "v1.0.0", "dev", "staging", "ci@github.com", dry_run=True
            )

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_method_returns_promotion_record(
        self, controller: MagicMock
    ) -> None:
        """Test dry_run() convenience method returns PromotionRecord."""
        from floe_core.schemas.promotion import PromotionRecord

        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            result = controller.dry_run(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert isinstance(result, PromotionRecord)
            assert result.dry_run is True


class TestDryRunValidation:
    """Unit tests for dry-run validation behavior."""

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

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_still_validates_transition(self, controller: MagicMock) -> None:
        """Test dry_run=True still validates environment transition.

        Invalid transitions should still raise InvalidTransitionError.
        """
        from floe_core.oci.errors import InvalidTransitionError

        # Don't mock _validate_transition - let it run
        with pytest.raises(InvalidTransitionError):
            controller.promote(
                tag="v1.0.0",
                from_env="staging",
                to_env="dev",  # Invalid: backward transition
                operator="ci@github.com",
                dry_run=True,
            )

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_record_contains_gate_results(self, controller: MagicMock) -> None:
        """Test dry-run PromotionRecord contains all gate results.

        The record should show what gates would run and their results.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.PASSED,
                    duration_ms=500,
                ),
            ]
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Record should contain all gate results
            assert len(result.gate_results) == 2
            gate_types = {g.gate for g in result.gate_results}
            assert PromotionGate.POLICY_COMPLIANCE in gate_types
            assert PromotionGate.TESTS in gate_types

    @pytest.mark.requirement("8C-FR-007")
    def test_dry_run_record_contains_signature_status(
        self, controller: MagicMock
    ) -> None:
        """Test dry-run PromotionRecord contains signature verification status."""
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_get_artifact_digest"
        ) as mock_get_digest, patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ), patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_get_digest.return_value = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # Record should indicate signature was verified
            assert result.signature_verified is True
