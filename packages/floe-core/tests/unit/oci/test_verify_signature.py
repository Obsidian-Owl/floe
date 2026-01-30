"""Unit tests for signature verification in promotion (T020).

Tests PromotionController._verify_signature() behavior.

Requirements tested:
    FR-005: Signature verification during promotion
    FR-018: Verification with enforcement modes
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestVerifySignature:
    """Tests for signature verification in promotion."""

    @pytest.fixture
    def controller_with_policy(self) -> MagicMock:
        """Create a PromotionController with verification policy configured."""
        from floe_core.oci.client import OCIClient
        from floe_core.oci.promotion import PromotionController
        from floe_core.schemas.oci import AuthType, RegistryAuth, RegistryConfig
        from floe_core.schemas.promotion import PromotionConfig

        auth = RegistryAuth(type=AuthType.ANONYMOUS)
        registry_config = RegistryConfig(uri="oci://harbor.example.com/floe", auth=auth)
        oci_client = OCIClient.from_registry_config(registry_config)
        promotion = PromotionConfig()

        return PromotionController(client=oci_client, promotion=promotion)

    @pytest.mark.requirement("8C-FR-005")
    def test_verify_signature_returns_verification_result(
        self, controller_with_policy: MagicMock
    ) -> None:
        """Test _verify_signature returns a VerificationResult."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="valid",
            signer_identity="ci@github.com",
            issuer="https://token.actions.githubusercontent.com",
            verified_at=datetime.now(timezone.utc),
            rekor_verified=True,
        )

        # Mock both VerificationPolicy (to bypass validation) and VerificationClient
        with patch(
            "floe_core.schemas.signing.VerificationPolicy"
        ) as mock_policy_class, patch(
            "floe_core.oci.verification.VerificationClient"
        ) as mock_client_class:
            mock_policy = Mock()
            mock_policy.enforcement = "enforce"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.return_value = mock_result
            mock_client_class.return_value = mock_client

            result = controller_with_policy._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123def456",
                content=b"artifact content",
                enforcement="enforce",
            )

            assert isinstance(result, VerificationResult)
            assert result.status == "valid"
            assert result.is_valid

    @pytest.mark.requirement("8C-FR-005")
    def test_verify_signature_passes_enforcement_mode(
        self, controller_with_policy: MagicMock
    ) -> None:
        """Test that enforcement mode is passed to VerificationClient."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
        )

        # Mock both VerificationPolicy and VerificationClient
        with patch(
            "floe_core.schemas.signing.VerificationPolicy"
        ) as mock_policy_class, patch(
            "floe_core.oci.verification.VerificationClient"
        ) as mock_client_class:
            mock_policy = Mock()
            mock_policy.enforcement = "warn"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.return_value = mock_result
            mock_client_class.return_value = mock_client

            controller_with_policy._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content",
                enforcement="warn",
            )

            # Check VerificationPolicy was created with correct enforcement
            mock_policy_class.assert_called_once()
            call_kwargs = mock_policy_class.call_args.kwargs
            assert call_kwargs.get("enforcement") == "warn"

    @pytest.mark.requirement("8C-FR-018")
    def test_verify_signature_returns_unsigned_when_no_metadata(
        self, controller_with_policy: MagicMock
    ) -> None:
        """Test that unsigned artifacts return 'unsigned' status."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="unsigned",
            verified_at=datetime.now(timezone.utc),
            failure_reason="Artifact is unsigned",
        )

        # Mock both VerificationPolicy and VerificationClient
        with patch(
            "floe_core.schemas.signing.VerificationPolicy"
        ) as mock_policy_class, patch(
            "floe_core.oci.verification.VerificationClient"
        ) as mock_client_class:
            mock_policy = Mock()
            mock_policy.enforcement = "enforce"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.return_value = mock_result
            mock_client_class.return_value = mock_client

            result = controller_with_policy._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content",
                enforcement="enforce",
            )

            assert result.status == "unsigned"

    @pytest.mark.requirement("8C-FR-018")
    def test_verify_signature_returns_invalid_on_failure(
        self, controller_with_policy: MagicMock
    ) -> None:
        """Test that verification failures return 'invalid' status."""
        from floe_core.schemas.signing import VerificationResult

        mock_result = VerificationResult(
            status="invalid",
            verified_at=datetime.now(timezone.utc),
            failure_reason="Signature mismatch",
        )

        # Mock both VerificationPolicy and VerificationClient
        with patch(
            "floe_core.schemas.signing.VerificationPolicy"
        ) as mock_policy_class, patch(
            "floe_core.oci.verification.VerificationClient"
        ) as mock_client_class:
            mock_policy = Mock()
            mock_policy.enforcement = "enforce"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.return_value = mock_result
            mock_client_class.return_value = mock_client

            result = controller_with_policy._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content",
                enforcement="enforce",
            )

            assert result.status == "invalid"
            assert not result.is_valid

    @pytest.mark.requirement("8C-FR-018")
    def test_verify_signature_with_off_enforcement_skips(
        self, controller_with_policy: MagicMock
    ) -> None:
        """Test that enforcement='off' skips verification."""
        result = controller_with_policy._verify_signature(
            artifact_ref="harbor.example.com/floe:v1.0.0",
            artifact_digest="sha256:abc123",
            content=b"content",
            enforcement="off",
        )

        # Should return a skipped/unsigned result without calling client
        assert result.status in ("unsigned", "unknown")

    @pytest.mark.requirement("8C-FR-005")
    def test_verify_signature_handles_verification_error(
        self, controller_with_policy: MagicMock
    ) -> None:
        """Test that verification errors are handled gracefully."""
        from floe_core.oci.errors import SignatureVerificationError

        # Mock both VerificationPolicy and VerificationClient
        with patch(
            "floe_core.schemas.signing.VerificationPolicy"
        ) as mock_policy_class, patch(
            "floe_core.oci.verification.VerificationClient"
        ) as mock_client_class:
            mock_policy = Mock()
            mock_policy.enforcement = "warn"
            mock_policy_class.return_value = mock_policy

            mock_client = Mock()
            mock_client.verify.side_effect = SignatureVerificationError(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                reason="Verification failed",
            )
            mock_client_class.return_value = mock_client

            result = controller_with_policy._verify_signature(
                artifact_ref="harbor.example.com/floe:v1.0.0",
                artifact_digest="sha256:abc123",
                content=b"content",
                enforcement="warn",
            )

            # Should return invalid result, not raise exception (warn mode)
            assert result.status == "invalid"
            assert result.failure_reason is not None
