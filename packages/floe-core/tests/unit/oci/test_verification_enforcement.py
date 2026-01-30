"""Unit tests for verification enforcement levels in PromotionController.

Task ID: T068, T069, T070
Phase: 7 - User Story 5 (Verification)
User Story: US5 - Verification Before Artifact Use
Requirements: FR-018, FR-019, FR-020, FR-021, FR-022

These tests validate enforcement policy handling in PromotionController._verify_signature():
- enforcement=enforce: Raises on invalid/unsigned artifacts (T068)
- enforcement=warn: Logs warning but doesn't raise (T069)
- enforcement=off: Skips verification entirely (T070)

The tests exercise the integration between PromotionController and VerificationClient,
ensuring that promotion operations respect verification.enforcement policy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from floe_core.oci.errors import SignatureVerificationError
from floe_core.oci.promotion import PromotionController
from floe_core.schemas.promotion import (
    EnvironmentConfig,
    PromotionConfig,
    PromotionGate,
)
from floe_core.schemas.signing import VerificationResult

if TYPE_CHECKING:
    pass


@pytest.fixture
def mock_oci_client() -> MagicMock:
    """Create mock OCI client for testing."""
    client = MagicMock()
    client.registry = MagicMock()
    client.registry.uri = "oci://registry.example.com/repo"
    return client


@pytest.fixture
def promotion_config() -> PromotionConfig:
    """Create promotion config with default environments."""
    return PromotionConfig(
        environments=[
            EnvironmentConfig(
                name="dev",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="staging",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
            EnvironmentConfig(
                name="prod",
                gates={PromotionGate.POLICY_COMPLIANCE: True},
            ),
        ]
    )


@pytest.fixture
def controller(mock_oci_client: MagicMock, promotion_config: PromotionConfig) -> PromotionController:
    """Create PromotionController with mocked dependencies."""
    return PromotionController(
        client=mock_oci_client,
        promotion=promotion_config,
    )


class TestVerificationEnforcementEnforce:
    """Tests for enforcement=enforce mode (T068).

    When enforcement=enforce:
    - Valid signature allows promotion to proceed
    - Invalid signature raises SignatureVerificationError
    - Unsigned artifact raises SignatureVerificationError
    - Missing signature metadata raises SignatureVerificationError

    Requirements: FR-018, FR-019, FR-020, FR-021
    """

    @pytest.mark.requirement("FR-021")
    def test_enforce_mode_valid_signature_returns_valid_result(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce with valid signature returns valid result."""
        mock_verification_result = VerificationResult(
            status="valid",
            signer_identity="repo:acme/floe:ref:refs/heads/main",
            issuer="https://token.actions.githubusercontent.com",
            verified_at=datetime.now(timezone.utc),
            rekor_verified=True,
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            result = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"artifact content",
                enforcement="enforce",
            )

            assert result.status == "valid"
            assert result.signer_identity == "repo:acme/floe:ref:refs/heads/main"
            assert result.rekor_verified is True

    @pytest.mark.requirement("FR-021")
    def test_enforce_mode_invalid_signature_raises_error(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce with invalid signature raises SignatureVerificationError."""
        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.side_effect = SignatureVerificationError(
                artifact_ref="oci://registry/repo:v1.0.0",
                reason="Signature verification failed: signature mismatch",
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller._verify_signature(
                    artifact_ref="oci://registry/repo:v1.0.0",
                    artifact_digest="sha256:abc123def456",
                    content=b"tampered content",
                    enforcement="enforce",
                )

            assert "signature" in str(exc_info.value).lower()

    @pytest.mark.requirement("FR-021")
    def test_enforce_mode_unsigned_artifact_raises_error(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce with unsigned artifact raises SignatureVerificationError."""
        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.side_effect = SignatureVerificationError(
                artifact_ref="oci://registry/repo:v1.0.0",
                reason="Artifact is not signed",
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(SignatureVerificationError) as exc_info:
                controller._verify_signature(
                    artifact_ref="oci://registry/repo:v1.0.0",
                    artifact_digest="sha256:abc123def456",
                    content=b"unsigned content",
                    enforcement="enforce",
                )

            assert "not signed" in str(exc_info.value).lower()

    @pytest.mark.requirement("FR-018")
    def test_enforce_mode_creates_verification_policy_with_enforce(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce creates VerificationPolicy with enforcement='enforce'."""
        mock_verification_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        # Patch at the import location inside _verify_signature method
        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch(
                "floe_core.schemas.signing.VerificationPolicy"
            ) as mock_policy_cls,
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Verify VerificationPolicy was created with enforcement='enforce'
            mock_policy_cls.assert_called_once()
            call_kwargs = mock_policy_cls.call_args.kwargs
            assert call_kwargs.get("enforcement") == "enforce"

    @pytest.mark.requirement("FR-019")
    def test_enforce_mode_rekor_verification_captured(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce captures Rekor transparency log verification status."""
        mock_verification_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
            rekor_verified=True,
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            result = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Rekor verification status should be captured
            assert result.rekor_verified is True

    @pytest.mark.requirement("FR-020")
    def test_enforce_mode_with_key_based_verification(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce works with key-based (non-keyless) verification."""
        mock_verification_result = VerificationResult(
            status="valid",
            signer_identity="/path/to/key.pub",
            verified_at=datetime.now(timezone.utc),
            rekor_verified=False,  # Key-based doesn't use Rekor
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            result = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            assert result.status == "valid"
            assert result.rekor_verified is False

    @pytest.mark.requirement("FR-021")
    def test_enforce_mode_propagates_verification_error_to_promote(
        self, controller: PromotionController
    ) -> None:
        """When enforce fails, promote() should also fail."""
        # Mock the necessary components for promote()
        controller.client.get_manifest_digest.return_value = "sha256:abc123"
        controller.client.tag_artifact.return_value = None

        with (
            patch.object(controller, "_run_gate", return_value=MagicMock(passed=True)),
            patch.object(
                controller,
                "_verify_signature",
                side_effect=SignatureVerificationError(
                    artifact_ref="oci://registry/repo:v1.0.0",
                    reason="Verification failed",
                ),
            ),
        ):
            with pytest.raises(SignatureVerificationError):
                controller.promote(
                    tag="v1.0.0",
                    from_env="dev",
                    to_env="staging",
                    operator="test@example.com",
                )

    @pytest.mark.requirement("FR-021")
    def test_enforce_mode_emits_otel_span_attributes(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=enforce emits OTel span with enforcement_mode attribute."""
        mock_verification_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        captured_spans: list[dict] = []

        def mock_create_span(name: str, attributes: dict | None = None):
            span = MagicMock()
            span_info = {"name": name, "attributes": attributes or {}}
            captured_spans.append(span_info)

            def set_attribute(key: str, value: str) -> None:
                span_info["attributes"][key] = value

            span.set_attribute = set_attribute
            span.__enter__ = MagicMock(return_value=span)
            span.__exit__ = MagicMock(return_value=None)
            return span

        with (
            patch("floe_core.oci.promotion.create_span", side_effect=mock_create_span),
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Verify OTel span was created with enforcement_mode
            assert len(captured_spans) > 0
            verify_span = next(
                (s for s in captured_spans if "verify" in s["name"].lower()),
                None,
            )
            assert verify_span is not None
            assert verify_span["attributes"].get("enforcement_mode") == "enforce"


class TestVerificationEnforcementWarn:
    """Tests for enforcement=warn mode (T069).

    When enforcement=warn:
    - Valid signature returns valid result
    - Invalid signature logs warning but returns invalid result (no raise)
    - Unsigned artifact logs warning but returns unsigned result (no raise)

    Requirements: FR-021
    """

    @pytest.mark.requirement("FR-021")
    def test_warn_mode_valid_signature_returns_valid_result(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=warn with valid signature returns valid result."""
        mock_verification_result = VerificationResult(
            status="valid",
            signer_identity="repo:acme/floe:ref:refs/heads/main",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            result = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="warn",
            )

            assert result.status == "valid"

    @pytest.mark.requirement("FR-021")
    def test_warn_mode_invalid_signature_does_not_raise(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=warn with invalid signature returns result without raising."""
        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.side_effect = SignatureVerificationError(
                artifact_ref="oci://registry/repo:v1.0.0",
                reason="Signature mismatch",
            )
            mock_client_cls.return_value = mock_client

            # Should NOT raise - warn mode catches errors
            result = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"tampered content",
                enforcement="warn",
            )

            assert result.status == "invalid"
            assert result.failure_reason is not None

    @pytest.mark.requirement("FR-021")
    def test_warn_mode_logs_error_on_failure(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=warn logs error message when verification fails."""
        import structlog

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
            structlog.testing.capture_logs() as captured_logs,
        ):
            mock_client = MagicMock()
            mock_client.verify.side_effect = SignatureVerificationError(
                artifact_ref="oci://registry/repo:v1.0.0",
                reason="Verification failed",
            )
            mock_client_cls.return_value = mock_client

            controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="warn",
            )

            # Check for error log entry using structlog's testing facility
            assert any(
                log.get("event") == "verify_signature_error"
                for log in captured_logs
            )


class TestVerificationEnforcementOff:
    """Tests for enforcement=off mode (T070).

    When enforcement=off:
    - Verification is completely skipped
    - Returns unsigned result immediately
    - Does not call VerificationClient

    Requirements: FR-021
    """

    @pytest.mark.requirement("FR-021")
    def test_off_mode_skips_verification(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=off returns unsigned result without verification."""
        with patch("floe_core.oci.verification.VerificationClient") as mock_client_cls:
            result = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="off",
            )

            # Verification should be skipped, returns unsigned status
            assert result.status == "unsigned"
            # VerificationClient should NOT be instantiated
            mock_client_cls.assert_not_called()

    @pytest.mark.requirement("FR-021")
    def test_off_mode_includes_skip_reason(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=off result includes reason for skip."""
        result = controller._verify_signature(
            artifact_ref="oci://registry/repo:v1.0.0",
            artifact_digest="sha256:abc123def456",
            content=b"content",
            enforcement="off",
        )

        assert result.failure_reason is not None
        assert "off" in result.failure_reason.lower() or "skip" in result.failure_reason.lower()

    @pytest.mark.requirement("FR-021")
    def test_off_mode_emits_skipped_log(
        self, controller: PromotionController
    ) -> None:
        """Enforcement=off logs that verification was skipped."""
        import structlog

        with structlog.testing.capture_logs() as captured_logs:
            controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="off",
            )

        # Check for skipped log entry using structlog's testing facility
        assert any(
            log.get("event") == "verify_signature_skipped"
            for log in captured_logs
        )


class TestVerificationResultCaching:
    """Tests for verification result caching (T071).

    When an artifact is verified, the result should be cached to avoid
    re-verification of immutable artifacts. Cache is keyed by artifact digest.

    Requirements: FR-022
    """

    @pytest.mark.requirement("FR-022")
    def test_same_artifact_verified_once(
        self, controller: PromotionController
    ) -> None:
        """Verifying same artifact twice only calls VerificationClient once."""
        mock_verification_result = VerificationResult(
            status="valid",
            signer_identity="repo:acme/floe:ref:refs/heads/main",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            # First verification call
            result1 = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Second verification call with same digest
            result2 = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Both should return valid result
            assert result1.status == "valid"
            assert result2.status == "valid"

            # VerificationClient.verify should only be called once (cached)
            assert mock_client.verify.call_count == 1

    @pytest.mark.requirement("FR-022")
    def test_different_digests_verified_separately(
        self, controller: PromotionController
    ) -> None:
        """Different artifact digests are verified separately (not cached)."""
        mock_verification_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            # First digest
            controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content1",
                enforcement="enforce",
            )

            # Different digest
            controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.1",
                artifact_digest="sha256:def456",
                content=b"content2",
                enforcement="enforce",
            )

            # Both should be verified (2 calls, not cached)
            assert mock_client.verify.call_count == 2

    @pytest.mark.requirement("FR-022")
    def test_cached_result_returned_for_same_digest(
        self, controller: PromotionController
    ) -> None:
        """Cached verification result is returned for same artifact digest."""
        first_result = VerificationResult(
            status="valid",
            signer_identity="original-signer",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = first_result
            mock_client_cls.return_value = mock_client

            # First call
            result1 = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Change mock return value
            mock_client.verify.return_value = VerificationResult(
                status="invalid",
                verified_at=datetime.now(timezone.utc),
            )

            # Second call should return cached result (still valid)
            result2 = controller._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"content",
                enforcement="enforce",
            )

            # Should return original cached result
            assert result2.status == "valid"
            assert result2.signer_identity == "original-signer"

    @pytest.mark.requirement("FR-022")
    def test_cache_is_per_controller_instance(
        self, mock_oci_client: MagicMock, promotion_config: PromotionConfig
    ) -> None:
        """Cache is scoped to controller instance, not global."""
        mock_verification_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        with (
            patch("floe_core.oci.verification.VerificationClient") as mock_client_cls,
            patch("floe_core.schemas.signing.VerificationPolicy"),
        ):
            mock_client = MagicMock()
            mock_client.verify.return_value = mock_verification_result
            mock_client_cls.return_value = mock_client

            # Two separate controller instances
            controller1 = PromotionController(
                client=mock_oci_client,
                promotion=promotion_config,
            )
            controller2 = PromotionController(
                client=mock_oci_client,
                promotion=promotion_config,
            )

            # Same artifact verified by both controllers
            controller1._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content",
                enforcement="enforce",
            )
            controller2._verify_signature(
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content",
                enforcement="enforce",
            )

            # Each controller should verify independently (2 calls)
            assert mock_client.verify.call_count == 2


__all__: list[str] = [
    "TestVerificationEnforcementEnforce",
    "TestVerificationEnforcementWarn",
    "TestVerificationEnforcementOff",
    "TestVerificationResultCaching",
]
