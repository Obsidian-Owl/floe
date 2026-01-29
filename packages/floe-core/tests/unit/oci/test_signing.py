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
import os
import threading
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

from floe_core.oci.errors import ConcurrentSigningError  # noqa: E402
from floe_core.oci.signing import (  # noqa: E402
    ANNOTATION_BUNDLE,
    ANNOTATION_CERT_FINGERPRINT,
    ANNOTATION_ISSUER,
    ANNOTATION_MODE,
    ANNOTATION_REKOR_INDEX,
    ANNOTATION_SIGNED_AT,
    ANNOTATION_SUBJECT,
    OIDC_MAX_RETRIES,
    OIDC_RETRY_BASE_DELAY,
    CosignNotAvailableError,
    KeyLoadError,
    OIDCTokenError,
    SigningClient,
    SigningError,
    check_cosign_available,
    sign_artifact,
    signing_lock,
)
from floe_core.schemas.signing import SignatureMetadata, SigningConfig  # noqa: E402

if TYPE_CHECKING:
    pass


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
            patch("sigstore.models.ClientTrustConfig"),
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
            patch("sigstore.models.ClientTrustConfig") as mock_trust_config,
        ):
            mock_token = MagicMock()
            mock_token.federated_issuer = "https://accounts.google.com"
            mock_token.identity = "user@example.com"

            mock_issuer = MagicMock()
            mock_issuer.identity_token.return_value = mock_token
            mock_issuer_cls.return_value = mock_issuer

            mock_signing_config = MagicMock()
            mock_signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev/auth"
            mock_trust_config.production.return_value.signing_config = mock_signing_config

            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token
            mock_issuer_cls.assert_called_once_with("https://oauth2.sigstore.dev/auth")

    def test_oidc_token_error_on_failure(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token raises OIDCTokenError on complete failure."""
        from sigstore.oidc import IdentityError

        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
            patch("sigstore.models.ClientTrustConfig") as mock_trust_config,
        ):
            mock_issuer = MagicMock()
            mock_issuer.identity_token.side_effect = IdentityError("Token expired")
            mock_issuer_cls.return_value = mock_issuer

            mock_signing_config = MagicMock()
            mock_signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev/auth"
            mock_trust_config.production.return_value.signing_config = mock_signing_config

            client = SigningClient(keyless_config)

            with pytest.raises(OIDCTokenError, match="Failed to acquire OIDC token"):
                client._get_identity_token()

    def test_browser_oauth_disabled_raises_error(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token raises OIDCTokenError when browser OAuth is disabled."""
        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
            patch("floe_core.oci.signing.DISABLE_BROWSER_OAUTH", True),
        ):
            client = SigningClient(keyless_config)

            with pytest.raises(OIDCTokenError, match="browser OAuth is disabled"):
                client._get_identity_token()

            mock_issuer_cls.assert_not_called()


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
            patch("sigstore.models.ClientTrustConfig"),
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


class TestOpenTelemetrySpans:
    """Tests for OpenTelemetry span emission (T088, SC-007).

    Verify that signing operations emit the documented OTel spans.

    Note: These tests patch the module-level tracer to capture spans.
    This is necessary because signing.py uses trace.get_tracer() at import time.
    """

    @pytest.fixture
    def captured_spans(self):
        """Capture spans by patching the signing module's tracer."""
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON

        import floe_core.oci.signing as signing_module

        exporter = InMemorySpanExporter()
        provider = TracerProvider(sampler=ALWAYS_ON)
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test.signing")

        # Patch the module-level tracer
        original_tracer = signing_module.tracer
        signing_module.tracer = test_tracer

        yield exporter

        # Restore original tracer
        signing_module.tracer = original_tracer
        exporter.clear()

    @requires_sigstore
    def test_keyless_sign_emits_span_hierarchy(
        self,
        captured_spans,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """Keyless signing emits floe.oci.sign span with child spans."""
        with (
            patch(
                "floe_core.oci.signing.SigningClient._get_identity_token",
                return_value=mock_identity_token,
            ),
            patch("sigstore.sign.SigningContext") as mock_context_cls,
            patch("sigstore.models.ClientTrustConfig"),
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.from_trust_config.return_value = mock_context

            client = SigningClient(keyless_config)
            client.sign(b"artifact content", "oci://registry/repo:v1.0.0")

        spans = captured_spans.get_finished_spans()
        span_names = [span.name for span in spans]

        # Verify root span exists
        assert "floe.oci.sign" in span_names

        # Verify child spans for keyless signing flow
        assert "floe.oci.sign.oidc_token" in span_names
        assert "floe.oci.sign.fulcio" in span_names
        assert "floe.oci.sign.rekor" in span_names

    @requires_sigstore
    def test_sign_span_has_required_attributes(
        self,
        captured_spans,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """floe.oci.sign span has documented attributes."""
        with (
            patch(
                "floe_core.oci.signing.SigningClient._get_identity_token",
                return_value=mock_identity_token,
            ),
            patch("sigstore.sign.SigningContext") as mock_context_cls,
            patch("sigstore.models.ClientTrustConfig"),
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.from_trust_config.return_value = mock_context

            client = SigningClient(keyless_config)
            client.sign(b"content", "oci://registry/repo:v1.0.0")

        spans = captured_spans.get_finished_spans()
        sign_span = next((s for s in spans if s.name == "floe.oci.sign"), None)

        assert sign_span is not None
        attrs = dict(sign_span.attributes)

        # Verify documented attributes per research.md
        assert "floe.artifact.ref" in attrs
        assert attrs["floe.artifact.ref"] == "oci://registry/repo:v1.0.0"
        assert "floe.signing.mode" in attrs
        assert attrs["floe.signing.mode"] == "keyless"

    def test_key_based_sign_emits_span(self, captured_spans) -> None:
        """Key-based signing emits floe.oci.sign.key_based span."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="test-key"),
        )
        mock_bundle = {"base64Signature": "dGVzdC1zaWc="}

        with (
            patch("floe_core.oci.signing.check_cosign_available", return_value=True),
            patch.object(SigningClient, "_cosign_sign_blob", return_value=mock_bundle),
            patch.object(SigningClient, "_resolve_key_reference", return_value="/path/to/key"),
        ):
            client = SigningClient(config)
            client.sign(b"content", "oci://registry/repo:v1.0.0")

        spans = captured_spans.get_finished_spans()
        span_names = [span.name for span in spans]

        assert "floe.oci.sign" in span_names
        assert "floe.oci.sign.key_based" in span_names

    def test_key_based_span_has_key_ref_attribute(self, captured_spans) -> None:
        """Key-based signing records floe.signing.key_ref attribute on inner span.

        Note: The key_ref attribute is set on the active span via
        trace.get_current_span() inside _key_bundle_to_metadata, which
        runs within the floe.oci.sign.key_based span context.
        """
        from floe_core.schemas.secrets import SecretReference, SecretSource

        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(source=SecretSource.ENV, name="test-key"),
        )
        mock_bundle = {"base64Signature": "dGVzdC1zaWc="}

        with (
            patch("floe_core.oci.signing.check_cosign_available", return_value=True),
            patch.object(SigningClient, "_cosign_sign_blob", return_value=mock_bundle),
            patch.object(SigningClient, "_resolve_key_reference", return_value="/path/to/key"),
        ):
            client = SigningClient(config)
            client.sign(b"content", "oci://registry/repo:v1.0.0")

        spans = captured_spans.get_finished_spans()

        # The key_ref attribute is set on the key_based span, not the root span
        # This is because _key_bundle_to_metadata uses trace.get_current_span()
        key_based_span = next((s for s in spans if s.name == "floe.oci.sign.key_based"), None)

        assert key_based_span is not None
        attrs = dict(key_based_span.attributes)
        assert "floe.signing.key_ref" in attrs
        assert attrs["floe.signing.key_ref"] == "/path/to/key"


class TestKeyBasedSigning:
    """Tests for key-based signing (T066, T067)."""

    @pytest.fixture
    def key_based_config(self, tmp_path) -> SigningConfig:
        """Create key-based signing config with temporary key file."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        key_file = tmp_path / "cosign.key"
        key_file.write_text("-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----")

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


class TestConcurrentSigning:
    """Tests for concurrent signing behavior (T091, FLO-1828).

    Validates file-based locking for serializing signing operations.
    """

    def test_signing_lock_acquires_and_releases(self, tmp_path: Any) -> None:
        """signing_lock context manager acquires and releases lock."""
        artifact_ref = "oci://registry/repo:v1.0.0"

        with patch("floe_core.oci.signing._get_lock_dir", return_value=tmp_path):
            with signing_lock(artifact_ref):
                lock_files = list(tmp_path.glob("signing-*.lock"))
                assert len(lock_files) == 1

    def test_signing_lock_serializes_concurrent_access(self, tmp_path: Any) -> None:
        """signing_lock serializes concurrent signing to same artifact."""
        artifact_ref = "oci://registry/repo:v1.0.0"
        execution_order: list[str] = []
        lock = threading.Lock()
        t1_acquired = threading.Event()
        t1_release = threading.Event()

        def worker(worker_id: str) -> None:
            with patch("floe_core.oci.signing._get_lock_dir", return_value=tmp_path):
                with signing_lock(artifact_ref, timeout_seconds=5.0):
                    with lock:
                        execution_order.append(f"{worker_id}_start")
                    if worker_id == "t1":
                        t1_acquired.set()  # Signal that t1 has lock
                        t1_release.wait(timeout=5.0)  # Wait for signal to release
                    with lock:
                        execution_order.append(f"{worker_id}_end")

        t1 = threading.Thread(target=worker, args=("t1",))
        t2 = threading.Thread(target=worker, args=("t2",))

        t1.start()
        t1_acquired.wait(timeout=5.0)  # Wait for t1 to acquire lock
        t2.start()
        t1_release.set()  # Allow t1 to complete

        t1.join(timeout=10)
        t2.join(timeout=10)

        # Verify serialization: one thread fully completes before the other starts
        assert len(execution_order) == 4
        # First thread starts and ends before second thread starts
        first_end_idx = execution_order.index("t1_end")
        second_start_idx = execution_order.index("t2_start")
        assert first_end_idx < second_start_idx

    def test_signing_lock_allows_different_artifacts(self, tmp_path: Any) -> None:
        """signing_lock allows concurrent access to different artifacts."""
        artifact1 = "oci://registry/repo:v1.0.0"
        artifact2 = "oci://registry/repo:v2.0.0"
        acquired: list[str] = []
        released = threading.Event()
        both_acquired = threading.Event()

        def worker(artifact_ref: str, worker_id: str) -> None:
            with patch("floe_core.oci.signing._get_lock_dir", return_value=tmp_path):
                with signing_lock(artifact_ref, timeout_seconds=5.0):
                    acquired.append(worker_id)
                    if len(acquired) == 2:
                        both_acquired.set()
                    released.wait(timeout=5.0)

        t1 = threading.Thread(target=worker, args=(artifact1, "t1"))
        t2 = threading.Thread(target=worker, args=(artifact2, "t2"))

        t1.start()
        t2.start()

        # Both should acquire locks for different artifacts
        both_acquired.wait(timeout=5.0)
        assert len(acquired) == 2, "Both threads should acquire locks simultaneously"

        released.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

    def test_signing_lock_timeout_raises_error(self, tmp_path: Any) -> None:
        """signing_lock raises ConcurrentSigningError on timeout."""
        artifact_ref = "oci://registry/repo:v1.0.0"
        lock_acquired = threading.Event()
        test_complete = threading.Event()
        error_raised: ConcurrentSigningError | None = None

        def holder() -> None:
            with patch("floe_core.oci.signing._get_lock_dir", return_value=tmp_path):
                with signing_lock(artifact_ref, timeout_seconds=10.0):
                    lock_acquired.set()
                    test_complete.wait(timeout=10.0)

        holder_thread = threading.Thread(target=holder)
        holder_thread.start()
        lock_acquired.wait(timeout=5.0)

        try:
            with patch("floe_core.oci.signing._get_lock_dir", return_value=tmp_path):
                try:
                    with signing_lock(artifact_ref, timeout_seconds=0.2):
                        pass
                except ConcurrentSigningError as e:
                    error_raised = e
        finally:
            test_complete.set()
            holder_thread.join(timeout=5)

        assert error_raised is not None, "ConcurrentSigningError should have been raised"
        assert "v1.0.0" in str(error_raised)
        assert error_raised.timeout_seconds == 0.2

    def test_signing_lock_releases_on_exception(self, tmp_path: Any) -> None:
        """signing_lock releases lock even when exception occurs."""
        artifact_ref = "oci://registry/repo:v1.0.0"

        with patch("floe_core.oci.signing._get_lock_dir", return_value=tmp_path):
            try:
                with signing_lock(artifact_ref):
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Lock should be released - can acquire again immediately
            with signing_lock(artifact_ref, timeout_seconds=0.5):
                pass

    def test_sign_method_uses_signing_lock(
        self,
        keyless_config: SigningConfig,
        mock_identity_token: MagicMock,
        mock_sigstore_bundle: MagicMock,
    ) -> None:
        """SigningClient.sign() uses signing_lock for serialization."""
        with (
            patch(
                "floe_core.oci.signing.SigningClient._get_identity_token",
                return_value=mock_identity_token,
            ),
            patch("sigstore.sign.SigningContext") as mock_context_cls,
            patch("sigstore.models.ClientTrustConfig"),
            patch("floe_core.oci.signing.signing_lock") as mock_lock,
        ):
            mock_context = MagicMock()
            mock_signer = MagicMock()
            mock_signer.sign_artifact.return_value = mock_sigstore_bundle
            mock_context.signer.return_value.__enter__ = MagicMock(return_value=mock_signer)
            mock_context.signer.return_value.__exit__ = MagicMock(return_value=False)
            mock_context_cls.from_trust_config.return_value = mock_context

            mock_lock.return_value.__enter__ = MagicMock()
            mock_lock.return_value.__exit__ = MagicMock(return_value=False)

            client = SigningClient(keyless_config)
            client.sign(b"content", "oci://registry/repo:v1.0.0")

            mock_lock.assert_called_once_with("oci://registry/repo:v1.0.0", None)


@requires_sigstore
class TestOIDCTokenRetry:
    """Tests for OIDC token retry with exponential backoff (T092, FLO-1829).

    Validates retry behavior for transient OIDC token acquisition failures.
    """

    def test_oidc_retry_on_transient_failure(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token retries on transient IdentityError."""
        from sigstore.oidc import IdentityError

        call_count = 0
        mock_token = MagicMock()
        mock_token.federated_issuer = "https://accounts.google.com"

        def failing_then_success() -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IdentityError("Transient failure")
            return mock_token

        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
            patch("sigstore.models.ClientTrustConfig") as mock_trust_config,
            patch("time.sleep") as mock_sleep,
        ):
            mock_issuer = MagicMock()
            mock_issuer.identity_token.side_effect = failing_then_success
            mock_issuer_cls.return_value = mock_issuer

            mock_signing_config = MagicMock()
            mock_signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev/auth"
            mock_trust_config.production.return_value.signing_config = mock_signing_config

            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token
            assert call_count == 3
            assert mock_sleep.call_count == 2

    def test_oidc_retry_respects_max_retries(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token raises after max retries exhausted."""
        from sigstore.oidc import IdentityError

        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
            patch("sigstore.models.ClientTrustConfig") as mock_trust_config,
            patch("time.sleep"),
        ):
            mock_issuer = MagicMock()
            mock_issuer.identity_token.side_effect = IdentityError("Persistent failure")
            mock_issuer_cls.return_value = mock_issuer

            mock_signing_config = MagicMock()
            mock_signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev/auth"
            mock_trust_config.production.return_value.signing_config = mock_signing_config

            client = SigningClient(keyless_config)

            with pytest.raises(OIDCTokenError) as exc_info:
                client._get_identity_token()

            assert f"Failed after {OIDC_MAX_RETRIES} attempts" in str(exc_info.value)

    def test_oidc_retry_uses_exponential_backoff(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token uses exponential backoff between retries."""
        from sigstore.oidc import IdentityError

        sleep_delays: list[float] = []

        def capture_sleep(delay: float) -> None:
            sleep_delays.append(delay)

        with (
            patch("sigstore.oidc.detect_credential", return_value=None),
            patch("sigstore.oidc.Issuer") as mock_issuer_cls,
            patch("sigstore.models.ClientTrustConfig") as mock_trust_config,
            patch("time.sleep", side_effect=capture_sleep),
            patch("random.uniform", return_value=0.05),
        ):
            mock_issuer = MagicMock()
            mock_issuer.identity_token.side_effect = IdentityError("Failure")
            mock_issuer_cls.return_value = mock_issuer

            mock_signing_config = MagicMock()
            mock_signing_config.get_oidc_url.return_value = "https://oauth2.sigstore.dev/auth"
            mock_trust_config.production.return_value.signing_config = mock_signing_config

            client = SigningClient(keyless_config)

            with pytest.raises(OIDCTokenError):
                client._get_identity_token()

            # Verify exponential backoff pattern: base_delay * 2^attempt + jitter
            assert len(sleep_delays) == OIDC_MAX_RETRIES - 1
            # First retry: 0.5 * 2^0 + 0.05 = 0.55
            assert abs(sleep_delays[0] - (OIDC_RETRY_BASE_DELAY * 1 + 0.05)) < 0.01
            # Second retry: 0.5 * 2^1 + 0.05 = 1.05
            assert abs(sleep_delays[1] - (OIDC_RETRY_BASE_DELAY * 2 + 0.05)) < 0.01

    def test_oidc_no_retry_on_immediate_success(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token does not retry on immediate success."""
        mock_token = MagicMock()

        with (
            patch("sigstore.oidc.detect_credential", return_value="ambient-cred"),
            patch("sigstore.oidc.IdentityToken", return_value=mock_token),
            patch("time.sleep") as mock_sleep,
        ):
            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token
            mock_sleep.assert_not_called()

    def test_oidc_ambient_credential_failure_retries(self, keyless_config: SigningConfig) -> None:
        """_get_identity_token retries when ambient credential detection fails."""
        from sigstore.oidc import IdentityError

        call_count = 0
        mock_token = MagicMock()

        def detect_with_retry() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise IdentityError("Service unavailable")
            return "ambient-token"

        with (
            patch("sigstore.oidc.detect_credential", side_effect=detect_with_retry),
            patch("sigstore.oidc.IdentityToken", return_value=mock_token),
            patch("time.sleep"),
        ):
            client = SigningClient(keyless_config)
            token = client._get_identity_token()

            assert token == mock_token
            assert call_count == 2
