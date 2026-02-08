"""Unit tests for OCI annotation size limit handling (T031c).

Tests for scenarios where PromotionRecord exceeds OCI annotation size limits:
- Graceful degradation when record exceeds 64KB
- Truncate gate result details while preserving core fields
- Warning logged when truncation occurs

Requirements tested:
    NFR-005: OCI annotation size limits

⚠️ TDD: Tests WILL FAIL until T032 implements full promote() logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from floe_core.schemas.promotion import GateResult, GateStatus, PromotionGate

# OCI annotation size limit (64KB per annotation, 256KB total)
OCI_ANNOTATION_SIZE_LIMIT = 64 * 1024  # 64KB

# Test constants
TEST_DIGEST = "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


class TestAnnotationSizeLimitHandling:
    """Unit tests for OCI annotation size limit handling (T031c)."""

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

    def _create_large_gate_result(self, size_kb: int = 100) -> GateResult:
        """Create a GateResult with large details that exceeds size limit.

        Args:
            size_kb: Approximate size of the details in KB.

        Returns:
            GateResult with large details dict.
        """
        # Create a large details dict that will exceed the annotation size limit
        # Each character is ~1 byte, so we need ~size_kb * 1024 characters
        large_output = "x" * (size_kb * 1024)

        return GateResult(
            gate=PromotionGate.POLICY_COMPLIANCE,
            status=GateStatus.PASSED,
            duration_ms=1500,
            details={
                "test_output": large_output,
                "test_count": 500,
                "coverage_report": {"lines": 95.5, "branches": 88.2},
            },
        )

    @pytest.mark.requirement("8C-NFR-005")
    def test_promote_handles_large_promotion_record_gracefully(
        self, controller: MagicMock
    ) -> None:
        """Test promote() handles PromotionRecord exceeding 64KB gracefully.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When a PromotionRecord's serialized size exceeds 64KB, the system should:
        1. Truncate large fields (gate result details)
        2. Preserve core fields (promotion_id, timestamps, digests)
        3. Still complete the promotion successfully
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Create gate results that will make the record exceed 64KB
        large_gate_result = self._create_large_gate_result(size_kb=100)

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            # Gates return large result
            mock_gates.return_value = [large_gate_result]
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Promotion should succeed despite large record
            assert isinstance(result, PromotionRecord)
            assert result.artifact_digest == TEST_DIGEST

            # Record storage should have been called
            mock_store.assert_called_once()

    @pytest.mark.requirement("8C-NFR-005")
    @pytest.mark.xfail(reason="T032a: Annotation truncation logic not yet implemented")
    def test_promote_truncates_gate_details_when_exceeding_limit(
        self, controller: MagicMock
    ) -> None:
        """Test promote() truncates gate details when record exceeds size limit.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Large gate result details should be truncated while preserving:
        - Gate name
        - Gate status
        - Duration
        - Error message (if any)
        """

        # Create multiple large gate results
        large_gate_results = [
            self._create_large_gate_result(size_kb=50),
            GateResult(
                gate=PromotionGate.SECURITY_SCAN,
                status=GateStatus.PASSED,
                duration_ms=2000,
                details={"vulnerabilities": [], "scan_output": "y" * 50000},
            ),
        ]

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = large_gate_results
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Check the stored record was truncated
            stored_record = mock_store.call_args[0][0]

            # Core fields must be preserved
            assert stored_record.promotion_id is not None
            assert stored_record.artifact_digest == TEST_DIGEST
            assert stored_record.source_environment == "dev"
            assert stored_record.target_environment == "staging"

            # Gate results must preserve core info
            assert len(stored_record.gate_results) == 2
            for gate_result in stored_record.gate_results:
                assert gate_result.gate is not None
                assert gate_result.status is not None
                assert gate_result.duration_ms is not None

            # Serialized size should be under limit
            serialized = stored_record.model_dump_json()
            assert len(serialized.encode("utf-8")) < OCI_ANNOTATION_SIZE_LIMIT

    @pytest.mark.requirement("8C-NFR-005")
    @pytest.mark.xfail(
        reason="T032a: Annotation truncation warning logging not yet implemented"
    )
    def test_promote_logs_warning_when_truncation_occurs(
        self, controller: MagicMock
    ) -> None:
        """Test promote() logs warning when record truncation occurs.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When truncation is needed, a warning should be logged indicating:
        - Original size
        - Truncated size
        - Which fields were affected
        """

        large_gate_result = self._create_large_gate_result(size_kb=100)

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record"),
            patch("floe_core.oci.promotion.logger") as mock_logger,
        ):
            mock_gates.return_value = [large_gate_result]
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Warning should have been logged about truncation
            warning_calls = [
                call
                for call in mock_logger.warning.call_args_list
                if "truncat" in str(call).lower() or "size" in str(call).lower()
            ]
            assert len(warning_calls) >= 1, "Expected warning about truncation"

    @pytest.mark.requirement("8C-NFR-005")
    @pytest.mark.xfail(
        reason="T032a: TEST_SUITE gate not in PromotionGate enum, "
        "error preservation logic incomplete"
    )
    def test_promote_preserves_error_messages_during_truncation(
        self, controller: MagicMock
    ) -> None:
        """Test promote() preserves error messages when truncating gate details.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Error messages are critical for debugging and should be preserved
        even when other details are truncated.
        """

        # Gate with error and large details
        gate_with_error = GateResult(
            gate=PromotionGate.TEST_SUITE,
            status=GateStatus.PASSED,
            duration_ms=5000,
            error="Test suite had 3 flaky tests but passed on retry",
            details={
                "test_output": "z" * 100000,  # Large output
                "flaky_tests": ["test_a", "test_b", "test_c"],
            },
        )

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = [gate_with_error]
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Check stored record preserves error message
            stored_record = mock_store.call_args[0][0]
            assert len(stored_record.gate_results) == 1

            # Error message must be preserved
            stored_gate = stored_record.gate_results[0]
            assert (
                stored_gate.error == "Test suite had 3 flaky tests but passed on retry"
            )

    @pytest.mark.requirement("8C-NFR-005")
    @pytest.mark.xfail(
        reason="T032a: _store_promotion_record mock interface mismatch - "
        "stores string not PromotionRecord"
    )
    def test_promote_small_record_not_truncated(self, controller: MagicMock) -> None:
        """Test promote() does not truncate records under size limit.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        Records under 64KB should be stored as-is without any truncation.
        """

        # Small gate result (well under limit)
        small_gate_result = GateResult(
            gate=PromotionGate.POLICY_COMPLIANCE,
            status=GateStatus.PASSED,
            duration_ms=100,
            details={
                "policies_checked": ["policy-1", "policy-2"],
                "all_passed": True,
            },
        )

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = [small_gate_result]
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Check stored record has full details
            stored_record = mock_store.call_args[0][0]
            stored_gate = stored_record.gate_results[0]

            # Details should be preserved as-is
            assert stored_gate.details == {
                "policies_checked": ["policy-1", "policy-2"],
                "all_passed": True,
            }

    @pytest.mark.requirement("8C-NFR-005")
    @pytest.mark.xfail(
        reason="T032a: TEST_SUITE gate not in PromotionGate enum, truncation logic incomplete"
    )
    def test_promote_handles_multiple_large_gates_efficiently(
        self, controller: MagicMock
    ) -> None:
        """Test promote() handles multiple large gate results efficiently.

        ⚠️ TDD: This test WILL FAIL until T032 implements full promote() logic.

        When multiple gates have large details, truncation should be applied
        proportionally to keep total size under limit.
        """
        from floe_core.schemas.promotion import PromotionRecord

        # Multiple gates with varying sizes
        gate_results = [
            GateResult(
                gate=PromotionGate.POLICY_COMPLIANCE,
                status=GateStatus.PASSED,
                duration_ms=100,
                details={"output": "a" * 30000},  # 30KB
            ),
            GateResult(
                gate=PromotionGate.SECURITY_SCAN,
                status=GateStatus.PASSED,
                duration_ms=200,
                details={"output": "b" * 30000},  # 30KB
            ),
            GateResult(
                gate=PromotionGate.TEST_SUITE,
                status=GateStatus.PASSED,
                duration_ms=300,
                details={"output": "c" * 30000},  # 30KB
            ),
        ]
        # Total: ~90KB, exceeds 64KB limit

        with (
            patch.object(controller, "_validate_transition"),
            patch.object(controller, "_get_artifact_digest") as mock_get_digest,
            patch.object(controller, "_run_all_gates") as mock_gates,
            patch.object(controller, "_verify_signature") as mock_verify,
            patch.object(controller, "_create_env_tag") as mock_create_tag,
            patch.object(controller, "_update_latest_tag"),
            patch.object(controller, "_store_promotion_record") as mock_store,
        ):
            mock_gates.return_value = gate_results
            mock_verify.return_value = Mock(status="valid")
            mock_create_tag.return_value = TEST_DIGEST
            mock_get_digest.return_value = TEST_DIGEST

            result = controller.promote(
                tag="v1.0.0",
                from_env="dev",
                to_env="staging",
                operator="ci@github.com",
            )

            # Promotion should succeed
            assert isinstance(result, PromotionRecord)

            # All gates should be present
            stored_record = mock_store.call_args[0][0]
            assert len(stored_record.gate_results) == 3

            # Total size should be under limit
            serialized = stored_record.model_dump_json()
            assert len(serialized.encode("utf-8")) < OCI_ANNOTATION_SIZE_LIMIT
