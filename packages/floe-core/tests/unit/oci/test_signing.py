"""Unit tests for OCI signing module.

Task ID: T023, T024, T025, T026
Phase: 3 - User Story 1 (Keyless Signing)
Requirements: FR-001, FR-011, SC-007

These tests validate:
- SigningClient keyless signing mode
- OIDC token acquisition with mocks
- Sigstore bundle creation and serialization
- OpenTelemetry tracing integration
"""

from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

# Check if sigstore is available
try:
    import sigstore  # noqa: F401

    SIGSTORE_AVAILABLE = True
except ImportError:
    SIGSTORE_AVAILABLE = False

requires_sigstore = pytest.mark.skipif(
    not SIGSTORE_AVAILABLE, reason="sigstore library not installed"
)

from floe_core.oci.signing import (
    ANNOTATION_BUNDLE,
    ANNOTATION_CERT_FINGERPRINT,
    ANNOTATION_ISSUER,
    ANNOTATION_MODE,
    ANNOTATION_REKOR_INDEX,
    ANNOTATION_SIGNED_AT,
    ANNOTATION_SUBJECT,
    CosignNotAvailableError,
    KeyLoadError,
    OIDCTokenError,
    SigningClient,
    SigningError,
    check_cosign_available,
    sign_artifact,
)
from floe_core.schemas.signing import SignatureMetadata, SigningConfig

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def keyless_config() -> SigningConfig:
    """Create keyless signing config for testing."""
    from pydantic import HttpUrl

    return SigningConfig(
        mode="keyless",
        oidc_issuer=HttpUrl("https://token.actions.githubusercontent.com"),
    )


@pytest.fixture
def mock_identity_token() -> MagicMock:
    """Create a mock IdentityToken."""
    token = MagicMock()
    token.federated_issuer = "https://token.actions.githubusercontent.com"
    token.identity = "repo:acme/floe:ref:refs/heads/main"
    return token


@pytest.fixture
def mock_sigstore_bundle() -> MagicMock:
    """Create a mock Sigstore bundle with realistic structure."""
    bundle = MagicMock()
    bundle_data = {
        "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
        "verificationMaterial": {
            "certificate": {"rawBytes": base64.b64encode(b"mock-certificate-der").decode()},
            "tlogEntries": [
                {
                    "logIndex": "12345678",
                    "logId": {"keyId": "test-key-id"},
                    "inclusionProof": {},
                }
            ],
        },
        "messageSignature": {
            "messageDigest": {"algorithm": "SHA2_256", "digest": "abc123"},
            "signature": base64.b64encode(b"mock-signature").decode(),
        },
    }
    bundle.to_json.return_value = json.dumps(bundle_data)
    return bundle


class TestSigningClient:
    """Tests for SigningClient class."""

    def test_init_keyless_config(self, keyless_config: SigningConfig) -> None:
        """SigningClient initializes with keyless config."""
        client = SigningClient(keyless_config)

        assert client.config == keyless_config
        assert client.config.mode == "keyless"

    @requires_sigstore
    def test_sign_keyless_success(
        self,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """SigningClient.sign() returns SignatureMetadata on success."""
        with (
            patch(
                "floe_core.oci.signing.SigningClient._get_identity_token",
                return_value=mock_identity_token,
            ),
            patch("sigstore.sign.SigningContext") as mock_context_cls,
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.production.return_value = mock_context

            client = SigningClient(keyless_config)
            metadata = client.sign(b"artifact content", "oci://registry/repo:v1.0.0")

            assert isinstance(metadata, SignatureMetadata)
            assert metadata.mode == "keyless"
            assert metadata.issuer == "https://token.actions.githubusercontent.com"
            assert metadata.subject == "repo:acme/floe:ref:refs/heads/main"
            assert metadata.rekor_log_index == 12345678
            assert metadata.bundle  # Base64-encoded bundle

    def test_sign_key_based_requires_cosign(self) -> None:
        """SigningClient.sign() raises CosignNotAvailableError when cosign not installed."""
        from floe_core.oci.signing import CosignNotAvailableError
        from floe_core.schemas.secrets import SecretReference, SecretSource

        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="test-key"),
        )
        client = SigningClient(config)

        with patch("floe_core.oci.signing.check_cosign_available", return_value=False):
            with pytest.raises(CosignNotAvailableError):
                client.sign(b"content", "oci://registry/repo:v1.0.0")


@requires_sigstore
class TestOIDCTokenAcquisition:
    """Tests for OIDC token acquisition (T015)."""

    def test_ambient_credential_detection(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token uses ambient credentials when available."""
        with (
            patch("sigstore.oidc.detect_credential", return_value="mock-token"),
            patch("sigstore.oidc.IdentityToken") as mock_token_cls,
        ):
            mock_token = MagicMock()
            mock_token.federated_issuer = "https://token.actions.githubusercontent.com"
            mock_token.identity = "repo:test/repo:ref:refs/heads/main"
            mock_token_cls.return_value = mock_token

            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token
            mock_token_cls.assert_called_once_with("mock-token")

    def test_fallback_to_interactive_oauth(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token falls back to interactive OAuth when no ambient creds."""
        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
        ):
            mock_token = MagicMock()
            mock_token.federated_issuer = "https://accounts.google.com"
            mock_token.identity = "user@example.com"

            mock_issuer = MagicMock()
            mock_issuer.identity_token.return_value = mock_token
            mock_issuer_cls.production.return_value = mock_issuer

            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token

    def test_oidc_token_error_on_failure(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token raises OIDCTokenError on complete failure."""
        from sigstore.oidc import IdentityError

        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
        ):
            mock_issuer = MagicMock()
            mock_issuer.identity_token.side_effect = IdentityError("Token expired")
            mock_issuer_cls.production.return_value = mock_issuer

            client = SigningClient(keyless_config)

            with pytest.raises(OIDCTokenError, match="Failed to acquire OIDC token"):
                client._get_identity_token()


@requires_sigstore
class TestSigstoreBundleSerialization:
    """Tests for Sigstore bundle creation and serialization (T016)."""

    def test_bundle_to_metadata_extracts_rekor_index(
        self,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """_bundle_to_metadata extracts Rekor log index from bundle."""
        client = SigningClient(keyless_config)
        metadata = client._bundle_to_metadata(mock_sigstore_bundle, mock_identity_token)

        assert metadata.rekor_log_index == 12345678

    def test_bundle_to_metadata_computes_cert_fingerprint(
        self,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """_bundle_to_metadata computes certificate SHA256 fingerprint."""
        client = SigningClient(keyless_config)
        metadata = client._bundle_to_metadata(mock_sigstore_bundle, mock_identity_token)

        assert metadata.certificate_fingerprint
        assert len(metadata.certificate_fingerprint) == 64  # SHA256 hex

    def test_bundle_base64_encoded(
        self,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """Bundle is base64-encoded in SignatureMetadata."""
        client = SigningClient(keyless_config)
        metadata = client._bundle_to_metadata(mock_sigstore_bundle, mock_identity_token)

        decoded = base64.b64decode(metadata.bundle)
        bundle_data = json.loads(decoded)

        assert "verificationMaterial" in bundle_data
        assert "messageSignature" in bundle_data


class TestSignatureMetadataAnnotations:
    """Tests for SignatureMetadata.to_annotations() integration."""

    def test_to_annotations_includes_all_fields(self) -> None:
        """SignatureMetadata.to_annotations() includes all signature fields."""
        metadata = SignatureMetadata(
            bundle="dGVzdC1idW5kbGU=",
            mode="keyless",
            issuer="https://token.actions.githubusercontent.com",
            subject="repo:acme/floe:ref:refs/heads/main",
            signed_at=datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc),
            rekor_log_index=12345678,
            certificate_fingerprint="abcd1234" * 8,
        )

        annotations = metadata.to_annotations()

        assert annotations[ANNOTATION_BUNDLE] == "dGVzdC1idW5kbGU="
        assert annotations[ANNOTATION_MODE] == "keyless"
        assert annotations[ANNOTATION_ISSUER] == "https://token.actions.githubusercontent.com"
        assert annotations[ANNOTATION_SUBJECT] == "repo:acme/floe:ref:refs/heads/main"
        assert annotations[ANNOTATION_REKOR_INDEX] == "12345678"
        assert ANNOTATION_SIGNED_AT in annotations
        assert ANNOTATION_CERT_FINGERPRINT in annotations

    def test_from_annotations_roundtrip(self) -> None:
        """SignatureMetadata survives to_annotations/from_annotations roundtrip."""
        original = SignatureMetadata(
            bundle="dGVzdC1idW5kbGU=",
            mode="keyless",
            issuer="https://token.actions.githubusercontent.com",
            subject="repo:acme/floe:ref:refs/heads/main",
            signed_at=datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc),
            rekor_log_index=12345678,
            certificate_fingerprint="abcd1234" * 8,
        )

        annotations = original.to_annotations()
        restored = SignatureMetadata.from_annotations(annotations)

        assert restored is not None
        assert restored.bundle == original.bundle
        assert restored.mode == original.mode
        assert restored.issuer == original.issuer
        assert restored.subject == original.subject
        assert restored.rekor_log_index == original.rekor_log_index


@requires_sigstore
class TestSignArtifactConvenienceFunction:
    """Tests for sign_artifact() convenience function."""

    def test_sign_artifact_creates_client(
        self,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """sign_artifact() creates SigningClient and signs."""
        with (
            patch(
                "floe_core.oci.signing.SigningClient._get_identity_token",
                return_value=mock_identity_token,
            ),
            patch("sigstore.sign.SigningContext") as mock_context_cls,
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.production.return_value = mock_context

            metadata = sign_artifact(b"content", "oci://registry/repo:v1.0.0", keyless_config)

            assert isinstance(metadata, SignatureMetadata)


class TestAnnotationConstants:
    """Tests for annotation key constants."""

    def test_annotation_keys_follow_convention(self) -> None:
        """All annotation keys use dev.floe.signature.* prefix."""
        assert ANNOTATION_BUNDLE.startswith("dev.floe.signature.")
        assert ANNOTATION_MODE.startswith("dev.floe.signature.")
        assert ANNOTATION_ISSUER.startswith("dev.floe.signature.")
        assert ANNOTATION_SUBJECT.startswith("dev.floe.signature.")
        assert ANNOTATION_SIGNED_AT.startswith("dev.floe.signature.")
        assert ANNOTATION_REKOR_INDEX.startswith("dev.floe.signature.")
        assert ANNOTATION_CERT_FINGERPRINT.startswith("dev.floe.signature.")


class TestKeyBasedSigning:
    """Tests for key-based signing (T066, T067)."""

    @pytest.fixture
    def key_based_config(self, tmp_path) -> SigningConfig:
        """Create key-based signing config with temporary key file."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        key_file = tmp_path / "cosign.key"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----")

        import os

        os.environ["FLOE_TEST_KEY"] = str(key_file)

        return SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="test-key"),
        )

    def test_check_cosign_available_returns_bool(self) -> None:
        """check_cosign_available() returns boolean."""
        result = check_cosign_available()
        assert isinstance(result, bool)

    def test_cosign_not_available_error_message(self) -> None:
        """CosignNotAvailableError has helpful message."""
        error = CosignNotAvailableError()
        assert "cosign CLI not found" in str(error)
        assert "brew install" in str(error) or "installation" in str(error).lower()

    def test_key_load_error_with_reason(self) -> None:
        """KeyLoadError includes reason and key reference."""
        error = KeyLoadError("File not found", key_ref="/path/to/key")
        assert "File not found" in str(error)
        assert "/path/to/key" in str(error)

    def test_resolve_key_reference_env_var(self, key_based_config: SigningConfig) -> None:
        """_resolve_key_reference resolves environment variable."""
        client = SigningClient(key_based_config)
        key_ref = client._resolve_key_reference()

        assert key_ref is not None
        assert "cosign.key" in key_ref

    def test_resolve_key_reference_missing_env_var(self) -> None:
        """_resolve_key_reference raises for missing env var."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="nonexistent-var"),
        )
        client = SigningClient(config)

        with pytest.raises(KeyLoadError, match="Environment variable not set"):
            client._resolve_key_reference()

    def test_signing_config_requires_key_ref_for_key_based(self) -> None:
        """SigningConfig validation requires private_key_ref for key-based mode."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="private_key_ref required"):
            SigningConfig(mode="key-based", private_key_ref=None)

    def test_sign_key_based_with_cosign_mock(self, key_based_config: SigningConfig) -> None:
        """Key-based signing calls cosign CLI and returns metadata."""
        mock_bundle = {"base64Signature": "dGVzdC1zaWc=", "keyRef": "/path/to/key"}

        with (
            patch("floe_core.oci.signing.check_cosign_available", return_value=True),
            patch.object(
                SigningClient, "_cosign_sign_blob", return_value=mock_bundle
            ) as mock_cosign,
        ):
            client = SigningClient(key_based_config)
            metadata = client.sign(b"artifact content", "oci://registry/repo:v1.0.0")

            mock_cosign.assert_called_once()
            assert metadata.mode == "key-based"
            assert metadata.rekor_log_index is None
            assert metadata.bundle is not None

    def test_key_signature_metadata_has_fingerprint(self, key_based_config: SigningConfig) -> None:
        """Key-based signature metadata includes key fingerprint."""
        mock_bundle = {"base64Signature": "dGVzdC1zaWc="}

        with (
            patch("floe_core.oci.signing.check_cosign_available", return_value=True),
            patch.object(SigningClient, "_cosign_sign_blob", return_value=mock_bundle),
        ):
            client = SigningClient(key_based_config)
            metadata = client.sign(b"content", "oci://registry/repo:v1.0.0")

            assert metadata.certificate_fingerprint is not None

    def test_compute_key_fingerprint_for_kms(self) -> None:
        """_compute_key_fingerprint hashes KMS URIs."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="test"),
        )
        client = SigningClient(config)

        fingerprint = client._compute_key_fingerprint("awskms://alias/my-key")
        assert len(fingerprint) == 16
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_cosign_sign_blob_timeout(self, key_based_config: SigningConfig, tmp_path) -> None:
        """_cosign_sign_blob handles timeout."""
        import subprocess

        with (
            patch("subprocess.run") as mock_run,
            patch("floe_core.oci.signing.check_cosign_available", return_value=True),
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="cosign", timeout=60)

            client = SigningClient(key_based_config)

            with pytest.raises(SigningError, match="timed out"):
                client._cosign_sign_blob(b"content", str(tmp_path / "key"))

    def test_cosign_sign_blob_failure(self, key_based_config: SigningConfig, tmp_path) -> None:
        """_cosign_sign_blob handles cosign failure."""
        with (
            patch("subprocess.run") as mock_run,
            patch("floe_core.oci.signing.check_cosign_available", return_value=True),
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="error: key not found")

            client = SigningClient(key_based_config)

            with pytest.raises(SigningError, match="cosign sign-blob failed"):
                client._cosign_sign_blob(b"content", str(tmp_path / "key"))
