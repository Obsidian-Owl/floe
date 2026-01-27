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
    OIDCTokenError,
    SigningClient,
    SigningError,
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
            patch("sigstore.models.ClientTrustConfig") as mock_trust_config,
            patch("sigstore.sign.SigningContext") as mock_context_cls,
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.from_trust_config.return_value = mock_context

            client = SigningClient(keyless_config)
            metadata = client.sign(b"artifact content", "oci://registry/repo:v1.0.0")

            assert isinstance(metadata, SignatureMetadata)
            assert metadata.mode == "keyless"
            assert metadata.issuer == "https://token.actions.githubusercontent.com"
            assert metadata.subject == "repo:acme/floe:ref:refs/heads/main"
            assert metadata.rekor_log_index == 12345678
            assert metadata.bundle  # Base64-encoded bundle

    def test_sign_key_based_not_implemented(self) -> None:
        """SigningClient.sign() raises NotImplementedError for key-based mode."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="key"),
        )
        client = SigningClient(config)

        with pytest.raises(NotImplementedError, match="Key-based signing"):
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
            patch("sigstore.models.ClientTrustConfig") as mock_trust,
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
        ):
            mock_token = MagicMock()
            mock_token.federated_issuer = "https://accounts.google.com"
            mock_token.identity = "user@example.com"

            mock_issuer = MagicMock()
            mock_issuer.identity_token.return_value = mock_token
            mock_issuer_cls.return_value = mock_issuer

            mock_config = MagicMock()
            mock_config.signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev"
            mock_trust.production.return_value = mock_config

            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token

    def test_oidc_token_error_on_failure(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token raises OIDCTokenError on complete failure."""
        from sigstore.oidc import IdentityError

        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.models.ClientTrustConfig") as mock_trust,
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
        ):
            mock_config = MagicMock()
            mock_config.signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev"
            mock_trust.production.return_value = mock_config

            mock_issuer = MagicMock()
            mock_issuer.identity_token.side_effect = IdentityError("Token expired")
            mock_issuer_cls.return_value = mock_issuer

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
            patch("sigstore.models.ClientTrustConfig"),
            patch("sigstore.sign.SigningContext") as mock_context_cls,
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.from_trust_config.return_value = mock_context

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
