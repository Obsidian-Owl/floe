"""Unit tests for PromotionController.promote() method (T028-T030).

Tests for the promote() method covering:
- T028: Success path (all gates pass, signatures valid)
- T029: Gate failure path
- T030: Signature verification failure path

Requirements tested:
    FR-001: Promote artifact from one environment to next
    FR-002: Gate validation before promotion
    FR-006: Signature verification integration
    FR-008: Audit trail via PromotionRecord
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate


class TestPromoteSuccessPath:
    """Unit tests for PromotionController.promote() success path (T028)."""

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

    @pytest.mark.requirement("8C-FR-001")
    def test_promote_returns_promotion_record(self, controller: MagicMock) -> None:
        """Test promote() returns a valid PromotionRecord on success.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Mock all internal methods to simulate successful promotion
        with patch.object(
            controller, "_validate_transition"
        ) as mock_validate, patch.object(
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
            # Configure mocks for success path
            mock_validate.return_value = None  # No exception = valid
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                )
            ]
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = "sha256:abc123"
            mock_update_latest.return_value = None
            mock_store.return_value = None

            # Also mock client methods
            controller.client._get_artifact_digest = Mock(
                return_value="sha256:abc123def456"
            )

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert isinstance(result, PromotionRecord)
            assert result.source_environment == "dev"
            assert result.target_environment == "staging"
            assert result.operator == "ci@github.com"
            assert result.dry_run is False

    @pytest.mark.requirement("8C-FR-001")
    def test_promote_validates_transition_first(self, controller: MagicMock) -> None:
        """Test promote() validates environment transition before other operations.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import InvalidTransitionError

        # Valid transitions should not raise
        with patch.object(controller, "_validate_transition") as mock_validate:
            mock_validate.return_value = None

            # The full promote will still fail (NotImplementedError) but
            # validate_transition should be called first
            try:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )
            except NotImplementedError:
                pass  # Expected until T032

            mock_validate.assert_called_once_with("dev", "staging")

    @pytest.mark.requirement("8C-FR-008")
    def test_promote_returns_promotion_id(self, controller: MagicMock) -> None:
        """Test promote() returns PromotionRecord with valid UUID promotion_id.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from uuid import UUID

        from floe_core.schemas.promotion import PromotionRecord

        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert isinstance(result.promotion_id, UUID)

    @pytest.mark.requirement("8C-FR-008")
    def test_promote_records_artifact_digest(self, controller: MagicMock) -> None:
        """Test promote() records the artifact digest in PromotionRecord.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        expected_digest = "sha256:abc123def456789"

        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value=expected_digest)

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert result.artifact_digest == expected_digest

    @pytest.mark.requirement("8C-FR-002")
    def test_promote_runs_all_gates(self, controller: MagicMock) -> None:
        """Test promote() runs all configured gates before creating tags.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        gate_results = [
            GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=50,
            ),
            GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.PASSED,
                duration_ms=1000,
            ),
        ]

        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = gate_results
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_gates.assert_called_once()
            assert len(result.gate_results) == 2

    @pytest.mark.requirement("8C-FR-006")
    def test_promote_verifies_signature(self, controller: MagicMock) -> None:
        """Test promote() verifies artifact signature before promotion.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_verify.assert_called_once()
            assert result.signature_verified is True

    @pytest.mark.requirement("8C-FR-001")
    def test_promote_creates_environment_tag(self, controller: MagicMock) -> None:
        """Test promote() creates immutable environment-specific tag.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
            controller, "_run_all_gates"
        ) as mock_gates, patch.object(
            controller, "_verify_signature"
        ) as mock_verify, patch.object(
            controller, "_create_env_tag"
        ) as mock_create_tag, patch.object(
            controller, "_update_latest_tag"
        ), patch.object(
            controller, "_store_promotion_record"
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = "sha256:abc123"
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Should create tag like v1.0.0-staging
            mock_create_tag.assert_called_once()
            call_args = mock_create_tag.call_args
            assert "staging" in str(call_args) or "v1.0.0" in str(call_args)

    @pytest.mark.requirement("8C-FR-001")
    def test_promote_dry_run_does_not_modify(self, controller: MagicMock) -> None:
        """Test promote() with dry_run=True validates but doesn't create tags.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            # In dry-run mode, should NOT create tags or store records
            mock_create_tag.assert_not_called()
            mock_update_latest.assert_not_called()
            mock_store.assert_not_called()
            assert result.dry_run is True

    @pytest.mark.requirement("8C-FR-008")
    def test_promote_stores_promotion_record(self, controller: MagicMock) -> None:
        """Test promote() stores PromotionRecord in OCI annotations.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_store.assert_called_once()

    @pytest.mark.requirement("8C-FR-001")
    def test_promote_returns_trace_id(self, controller: MagicMock) -> None:
        """Test promote() returns PromotionRecord with trace_id for observability.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with patch.object(controller, "_validate_transition"), patch.object(
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
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            controller.client._get_artifact_digest = Mock(return_value="sha256:abc123")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # trace_id should be present (may be empty string if no tracer configured)
            assert hasattr(result, "trace_id")
            assert isinstance(result.trace_id, str)
