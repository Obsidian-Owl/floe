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

from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

# Test constants
TEST_DIGEST = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


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

        # Test constants

        # Mock all internal methods to simulate successful promotion
        with (
            patch.object(controller, "_validate_transition") as mock_validate,
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            # Configure mocks for success path
            mock_validate.return_value = None  # No exception = valid
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                )
            ]
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_update_latest.return_value = None
            mock_store.return_value = None

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

        # Valid transitions should not raise
        with (
            patch.object(controller, "_validate_transition") as mock_validate,
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_validate.return_value = None
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_validate.assert_called_once_with("dev", "staging")

    @pytest.mark.requirement("8C-FR-008")
    def test_promote_returns_promotion_id(self, controller: MagicMock) -> None:
        """Test promote() returns PromotionRecord with valid UUID promotion_id.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from uuid import UUID

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

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
        expected_digest = (
            "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d0"
        )

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_get_digest.return_value = expected_digest
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert result.artifact_digest == expected_digest

    @pytest.mark.requirement("8C-FR-006")
    @pytest.mark.requirement("8C-FR-011")
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

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = gate_results
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_gates.assert_called_once()
            assert len(result.gate_results) == 2

    @pytest.mark.requirement("8C-FR-004")
    def test_promote_verifies_signature(self, controller: MagicMock) -> None:
        """Test promote() verifies artifact signature before promotion.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            mock_verify.assert_called_once()
            assert result.signature_verified is True

    @pytest.mark.requirement("8C-FR-001")
    @pytest.mark.requirement("8C-FR-002")
    @pytest.mark.requirement("8C-FR-003")
    def test_promote_creates_environment_tag(self, controller: MagicMock) -> None:
        """Test promote() creates immutable environment-specific tag.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST

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
    @pytest.mark.requirement("8C-FR-007")
    def test_promote_dry_run_does_not_modify(self, controller: MagicMock) -> None:
        """Test promote() with dry_run=True validates but doesn't create tags.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

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
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

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
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_get_digest.return_value = TEST_DIGEST
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # trace_id should be present (may be empty string if no tracer configured)
            assert hasattr(result, "trace_id")
            assert isinstance(result.trace_id, str)


class TestPromoteGateFailurePath:
    """Unit tests for PromotionController.promote() gate failure path (T029)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        # Test constants

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-006")
    @pytest.mark.requirement("8C-FR-011")
    def test_promote_raises_gate_validation_error_on_gate_failure(
        self, controller: MagicMock
    ) -> None:
        """Test promote() raises GateValidationError when a gate fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
        ):
            # Gate returns failure
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.FAILED,
                    duration_ms=500,
                    error="Test suite failed with 3 failures",
                )
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert exc_info.value.gate == "tests"
            assert "failed" in exc_info.value.details.lower()

    @pytest.mark.requirement("8C-FR-006")
    @pytest.mark.requirement("8C-FR-011")
    def test_promote_includes_failed_gate_in_error(self, controller: MagicMock) -> None:
        """Test GateValidationError includes which gate failed.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
        ):
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.SECURITY_SCAN,
                    status=GateStatus.FAILED,
                    duration_ms=2000,
                    error="Critical CVE found: CVE-2026-12345",
                )
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Error should identify which gate failed
            assert exc_info.value.gate == "security_scan"
            assert "CVE" in exc_info.value.details

    @pytest.mark.requirement("8C-FR-006")
    def test_promote_stops_at_first_gate_failure(self, controller: MagicMock) -> None:
        """Test promote() stops processing when first gate fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
        ):
            # First gate passes, second fails
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.FAILED,
                    duration_ms=500,
                    error="Test suite failed",
                ),
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Signature verification and tag creation should NOT be called
            mock_verify.assert_not_called()
            mock_create_tag.assert_not_called()

    @pytest.mark.requirement("8C-FR-006")
    def test_promote_gate_failure_does_not_create_tags(
        self, controller: MagicMock
    ) -> None:
        """Test promote() does not create tags when a gate fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag") as mock_update_latest,
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.FAILED,
                    duration_ms=500,
                    error="Test failed",
                )
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # No modifications should have been made
            mock_create_tag.assert_not_called()
            mock_update_latest.assert_not_called()
            mock_store.assert_not_called()

    @pytest.mark.requirement("8C-FR-006")
    def test_promote_gate_failure_exit_code(self, controller: MagicMock) -> None:
        """Test GateValidationError has correct exit code (8).

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
        ):
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.FAILED,
                    duration_ms=500,
                    error="Test failed",
                )
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Exit code 8 for gate validation failure
            assert exc_info.value.exit_code == 8

    @pytest.mark.requirement("8C-FR-006")
    @pytest.mark.requirement("8C-FR-007")
    def test_promote_dry_run_reports_gate_failure_without_raising(
        self, controller: MagicMock
    ) -> None:
        """Test promote() in dry_run mode returns record with failed gates (no exception).

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        In dry-run mode, gate failures should be recorded but not raise an exception,
        allowing users to see what WOULD happen without actually blocking.
        """
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            failed_gate = GateResult(
                gate=PromotionGate.TESTS,
                status=GateStatus.FAILED,
                duration_ms=500,
                error="Test failed",
            )
            mock_gates.return_value = [failed_gate]
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            # In dry-run mode, should NOT raise but return record with failures
            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
                dry_run=True,
            )

            assert result.dry_run is True
            assert len(result.gate_results) == 1
            assert result.gate_results[0].status == GateStatus.FAILED

    @pytest.mark.requirement("8C-FR-002")
    def test_promote_gate_timeout_is_failure(self, controller: MagicMock) -> None:
        """Test gate timeout is treated as gate failure.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
        ):
            # Gate timed out (status=FAILED due to timeout)
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.FAILED,
                    duration_ms=60000,  # Hit timeout
                    error="Gate timed out after 60 seconds",
                )
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert "timed out" in exc_info.value.details.lower()

    @pytest.mark.requirement("8C-FR-006")
    def test_promote_multiple_gate_failures_reports_first(
        self, controller: MagicMock
    ) -> None:
        """Test when multiple gates fail, error reports the first failure.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import GateValidationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
        ):
            # Multiple gates fail
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.FAILED,
                    duration_ms=50,
                    error="Policy violation: naming convention",
                ),
                GateResult(
                    gate=PromotionGate.TESTS,
                    status=GateStatus.FAILED,
                    duration_ms=500,
                    error="Test suite failed",
                ),
            ]
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(GateValidationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Should report the first failed gate
            assert exc_info.value.gate == "policy_compliance"


class TestPromoteSignatureFailurePath:
    """Unit tests for PromotionController.promote() signature failure path (T030)."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a PromotionController with mocked dependencies."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        # Test constants

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_raises_signature_verification_error_on_invalid_signature(
        self, controller: MagicMock
    ) -> None:
        """Test promote() raises SignatureVerificationError when signature is invalid.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            mock_gates.return_value = []  # All gates pass
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="Invalid signature",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert "Invalid signature" in exc_info.value.reason

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_raises_signature_verification_error_on_unsigned_artifact(
        self, controller: MagicMock
    ) -> None:
        """Test promote() raises SignatureVerificationError for unsigned artifacts.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            mock_gates.return_value = []
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="No signature found",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert "no signature" in exc_info.value.reason.lower()

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_raises_signature_verification_error_on_untrusted_signer(
        self, controller: MagicMock
    ) -> None:
        """Test promote() raises SignatureVerificationError for untrusted signer.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            mock_gates.return_value = []
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="Signer not in trusted issuers",
                expected_signer="repo:acme/floe:ref:refs/heads/main",
                actual_signer="repo:unknown/repo:ref:refs/heads/main",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert (
                exc_info.value.expected_signer == "repo:acme/floe:ref:refs/heads/main"
            )
            assert (
                exc_info.value.actual_signer == "repo:unknown/repo:ref:refs/heads/main"
            )

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_signature_failure_does_not_create_tags(
        self, controller: MagicMock
    ) -> None:
        """Test promote() does not create tags when signature verification fails.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

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
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="Invalid signature",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # No modifications should have been made
            mock_create_tag.assert_not_called()
            mock_update_latest.assert_not_called()
            mock_store.assert_not_called()

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_signature_failure_exit_code(self, controller: MagicMock) -> None:
        """Test SignatureVerificationError has correct exit code (6).

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            mock_gates.return_value = []
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="Invalid signature",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Exit code 6 for signature verification failure
            assert exc_info.value.exit_code == 6

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_signature_failure_after_gates_pass(
        self, controller: MagicMock
    ) -> None:
        """Test signature verification happens after gates pass.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            # Gates pass
            mock_gates.return_value = [
                GateResult(
                    gate=PromotionGate.POLICY_COMPLIANCE,
                    status=GateStatus.PASSED,
                    duration_ms=100,
                ),
            ]
            # But signature fails
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="Signature expired",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            # Both gates and verify should be called (gates pass, verify fails)
            mock_gates.assert_called_once()
            mock_verify.assert_called_once()

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-011")
    def test_promote_signature_verification_records_result_on_success(
        self, controller: MagicMock
    ) -> None:
        """Test promote() records signature_verified=True when verification passes.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag"),
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
        ):
            mock_gates.return_value = []
            mock_verify.return_value = Mock(status="valid")
            mock_get_digest.return_value = TEST_DIGEST

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            assert result.signature_verified is True

    @pytest.mark.requirement("8C-FR-004")
    @pytest.mark.requirement("8C-FR-005")
    def test_promote_includes_artifact_ref_in_signature_error(
        self, controller: MagicMock
    ) -> None:
        """Test SignatureVerificationError includes the artifact reference.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.
        """
        from floe_core.oci.errors import SignatureVerificationError

        artifact_ref = "harbor.example.com/floe:v1.0.0"

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
        ):
            mock_gates.return_value = []
            mock_verify.side_effect = SignatureVerificationError(
                artifact_ref=artifact_ref,
                reason="Invalid signature",
            )
            mock_get_digest.return_value = TEST_DIGEST

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="ci@github.com",
                )

            assert exc_info.value.artifact_ref == artifact_ref
            assert artifact_ref in str(exc_info.value)
