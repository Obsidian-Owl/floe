"""Unit tests for OCI error message quality (T094, FLO-1831).

Validates that error messages are actionable with remediation steps.
"""

from __future__ import annotations

import pytest

from floe_core.oci.errors import ConcurrentSigningError, SignatureVerificationError
from floe_core.oci.signing import (
    CosignNotAvailableError,
    KeyLoadError,
    OIDCTokenError,
)


class TestErrorMessageQuality:
    """Tests validating error messages include remediation steps."""

    def test_oidc_token_error_includes_remediation(self) -> None:
        """OIDCTokenError message includes actionable remediation steps."""
        error = OIDCTokenError("Token expired", issuer="https://example.com")
        msg = str(error)

        assert "Remediation" in msg
        assert "CI/CD" in msg or "GitHub" in msg
        assert "floe sign" in msg or "OAuth" in msg

    def test_key_load_error_includes_remediation(self) -> None:
        """KeyLoadError message includes actionable remediation steps."""
        error = KeyLoadError("File not found", key_ref="/path/to/key")
        msg = str(error)

        assert "Remediation" in msg
        assert "file" in msg.lower() or "readable" in msg.lower()
        assert "KMS" in msg or "IAM" in msg

    def test_cosign_not_available_includes_installation(self) -> None:
        """CosignNotAvailableError message includes installation instructions."""
        error = CosignNotAvailableError()
        msg = str(error)

        assert "cosign" in msg.lower()
        assert "install" in msg.lower()
        assert "brew" in msg or "github" in msg.lower()

    def test_signature_verification_error_includes_remediation(self) -> None:
        """SignatureVerificationError message includes context-aware remediation."""
        error = SignatureVerificationError(
            artifact_ref="oci://registry/repo:v1.0.0",
            reason="No signature found",
        )
        msg = str(error)

        assert "Remediation" in msg
        assert "floe artifact sign" in msg

    def test_signature_verification_error_signer_mismatch(self) -> None:
        """SignatureVerificationError provides signer-specific remediation."""
        error = SignatureVerificationError(
            artifact_ref="oci://registry/repo:v1.0.0",
            reason="Signer not in trusted issuers",
            expected_signer="repo:acme/floe:ref:refs/heads/main",
            actual_signer="repo:other/repo:ref:refs/heads/main",
        )
        msg = str(error)

        assert "trusted_issuers" in msg
        assert "floe artifact sign" in msg

    def test_signature_verification_error_expired(self) -> None:
        """SignatureVerificationError provides expiry-specific remediation."""
        error = SignatureVerificationError(
            artifact_ref="oci://registry/repo:v1.0.0",
            reason="Certificate expired",
        )
        msg = str(error)

        assert "floe artifact sign" in msg

    def test_concurrent_signing_error_includes_remediation(self) -> None:
        """ConcurrentSigningError message includes remediation steps."""
        error = ConcurrentSigningError(
            artifact_ref="oci://registry/repo:v1.0.0",
            timeout_seconds=30.0,
        )
        msg = str(error)

        assert "FLOE_SIGNING_LOCK_TIMEOUT" in msg
        assert "Retry" in msg or "later" in msg.lower()


class TestErrorMessageFormat:
    """Tests for error message format consistency."""

    def test_all_errors_have_nonempty_messages(self) -> None:
        """All signing/verification errors produce non-empty messages."""
        errors = [
            OIDCTokenError("Test reason"),
            KeyLoadError("Test reason"),
            CosignNotAvailableError(),
            SignatureVerificationError("oci://test", "Test reason"),
            ConcurrentSigningError("oci://test", 30.0),
        ]

        for error in errors:
            msg = str(error)
            assert msg, f"{type(error).__name__} produced empty message"
            assert len(msg) > 20, f"{type(error).__name__} message too short"

    def test_error_messages_are_user_friendly(self) -> None:
        """Error messages don't contain internal implementation details."""
        errors = [
            OIDCTokenError("Token expired"),
            KeyLoadError("Permission denied"),
            SignatureVerificationError("oci://test", "Verification failed"),
        ]

        forbidden_patterns = [
            "Traceback",
            "raise ",
            "self.",
            "__",
            "0x",
        ]

        for error in errors:
            msg = str(error)
            for pattern in forbidden_patterns:
                assert pattern not in msg, (
                    f"{type(error).__name__} contains '{pattern}' "
                    f"which looks like implementation detail"
                )

    def test_error_messages_include_artifact_ref(self) -> None:
        """Errors that relate to artifacts include the artifact reference."""
        error = SignatureVerificationError(
            artifact_ref="oci://registry/repo:v1.0.0",
            reason="Verification failed",
        )
        assert "oci://registry/repo:v1.0.0" in str(error)

        error = ConcurrentSigningError(
            artifact_ref="oci://registry/repo:v2.0.0",
            timeout_seconds=30.0,
        )
        assert "oci://registry/repo:v2.0.0" in str(error)
