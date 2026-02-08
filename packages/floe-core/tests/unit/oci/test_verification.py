"""Unit tests for OCI verification module.

Task ID: T036, T037, T038, T039, T040
Phase: 4 - User Story 2 (Signature Verification)
Requirements: FR-009, FR-010, FR-011, FR-013, SC-007

These tests validate:
- VerificationClient with valid signatures
- VerificationClient with invalid signatures
- Enforcement levels (enforce/warn/off)
- Identity policy matching
- Audit logging and tracing
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl

try:
    import sigstore  # noqa: F401

    SIGSTORE_AVAILABLE = True
except ImportError:
    SIGSTORE_AVAILABLE = False

requires_sigstore = pytest.mark.skipif(
    not SIGSTORE_AVAILABLE, reason="sigstore library not installed"
)

from floe_core.oci.errors import SignatureVerificationError  # noqa: E402
from floe_core.oci.verification import (  # noqa: E402
    CosignNotAvailableError,
    KeyVerificationError,
    VerificationClient,
    check_cosign_available,
    verify_artifact,
)
from floe_core.schemas.signing import (  # noqa: E402
    SignatureMetadata,
    TrustedIssuer,
    VerificationPolicy,
    VerificationResult,
)


@pytest.fixture
def github_actions_issuer() -> TrustedIssuer:
    """Create GitHub Actions trusted issuer."""
    return TrustedIssuer(
        issuer=HttpUrl("https://token.actions.githubusercontent.com"),
        subject="repo:acme/floe:ref:refs/heads/main",
    )


@pytest.fixture
def github_actions_issuer_regex() -> TrustedIssuer:
    """Create GitHub Actions trusted issuer with regex."""
    return TrustedIssuer(
        issuer=HttpUrl("https://token.actions.githubusercontent.com"),
        subject_regex=r"repo:acme/.*:ref:refs/heads/main",
    )


@pytest.fixture
def enforce_policy(github_actions_issuer: TrustedIssuer) -> VerificationPolicy:
    """Create verification policy with enforcement=enforce."""
    return VerificationPolicy(
        enabled=True,
        enforcement="enforce",
        trusted_issuers=[github_actions_issuer],
        require_rekor=True,
    )


@pytest.fixture
def warn_policy(github_actions_issuer: TrustedIssuer) -> VerificationPolicy:
    """Create verification policy with enforcement=warn."""
    return VerificationPolicy(
        enabled=True,
        enforcement="warn",
        trusted_issuers=[github_actions_issuer],
        require_rekor=True,
    )


@pytest.fixture
def off_policy(github_actions_issuer: TrustedIssuer) -> VerificationPolicy:
    """Create verification policy with enforcement=off."""
    return VerificationPolicy(
        enabled=True,
        enforcement="off",
        trusted_issuers=[github_actions_issuer],
        require_rekor=False,
    )


@pytest.fixture
def valid_signature_metadata() -> SignatureMetadata:
    """Create valid signature metadata matching GitHub Actions issuer."""
    bundle_data = {
        "verificationMaterial": {
            "certificate": {"rawBytes": base64.b64encode(b"cert").decode()},
            "tlogEntries": [{"logIndex": "12345"}],
        },
        "messageSignature": {"signature": "sig"},
    }
    return SignatureMetadata(
        bundle=base64.b64encode(json.dumps(bundle_data).encode()).decode(),
        mode="keyless",
        issuer="https://token.actions.githubusercontent.com",
        subject="repo:acme/floe:ref:refs/heads/main",
        signed_at=datetime.now(timezone.utc),
        rekor_log_index=12345,
        certificate_fingerprint="a" * 64,
    )


@pytest.fixture
def untrusted_signature_metadata() -> SignatureMetadata:
    """Create signature metadata from untrusted issuer."""
    bundle_data = {
        "verificationMaterial": {
            "certificate": {"rawBytes": base64.b64encode(b"cert").decode()},
            "tlogEntries": [{"logIndex": "99999"}],
        },
        "messageSignature": {"signature": "sig"},
    }
    return SignatureMetadata(
        bundle=base64.b64encode(json.dumps(bundle_data).encode()).decode(),
        mode="keyless",
        issuer="https://untrusted-issuer.example.com",
        subject="repo:evil/repo:ref:refs/heads/main",
        signed_at=datetime.now(timezone.utc),
        rekor_log_index=99999,
        certificate_fingerprint="b" * 64,
    )


class TestVerificationClientInit:
    """Tests for VerificationClient initialization."""

    def test_init_with_policy(self, enforce_policy: VerificationPolicy) -> None:
        """VerificationClient initializes with policy."""
        client = VerificationClient(enforce_policy)

        assert client.policy == enforce_policy
        assert client.environment is None
        assert client.enforcement == "enforce"
        assert client.is_enabled is True

    def test_init_with_environment(self, enforce_policy: VerificationPolicy) -> None:
        """VerificationClient accepts environment parameter."""
        client = VerificationClient(enforce_policy, environment="production")

        assert client.environment == "production"

    def test_is_enabled_false_when_disabled(
        self, github_actions_issuer: TrustedIssuer
    ) -> None:
        """is_enabled returns False when policy.enabled=False."""
        policy = VerificationPolicy(
            enabled=False,
            enforcement="enforce",
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)

        assert client.is_enabled is False

    def test_is_enabled_false_when_enforcement_off(
        self, off_policy: VerificationPolicy
    ) -> None:
        """is_enabled returns False when enforcement=off."""
        client = VerificationClient(off_policy)

        assert client.is_enabled is False


class TestVerificationClientEnforcementLevels:
    """Tests for enforcement levels (T038)."""

    def test_enforce_raises_on_unsigned(
        self, enforce_policy: VerificationPolicy
    ) -> None:
        """enforce mode raises SignatureVerificationError for unsigned artifacts."""
        client = VerificationClient(enforce_policy)

        with pytest.raises(SignatureVerificationError) as exc_info:
            client.verify(
                content=b"artifact",
                metadata=None,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

        assert "not signed" in str(exc_info.value)

    def test_warn_logs_on_unsigned(
        self, warn_policy: VerificationPolicy, caplog: pytest.LogCaptureFixture
    ) -> None:
        """warn mode logs warning for unsigned artifacts but doesn't raise."""
        client = VerificationClient(warn_policy)

        result = client.verify(
            content=b"artifact",
            metadata=None,
            artifact_ref="oci://registry/repo:v1.0.0",
        )

        assert result.status == "unsigned"
        assert "enforcement=warn" in caplog.text or result.failure_reason is not None

    def test_off_silently_accepts_unsigned(
        self, off_policy: VerificationPolicy
    ) -> None:
        """off mode silently accepts unsigned artifacts."""
        client = VerificationClient(off_policy)

        result = client.verify(
            content=b"artifact",
            metadata=None,
            artifact_ref="oci://registry/repo:v1.0.0",
        )

        assert result.status == "unsigned"


class TestIdentityPolicyMatching:
    """Tests for identity policy matching (T039)."""

    def test_exact_subject_match(
        self,
        enforce_policy: VerificationPolicy,
        valid_signature_metadata: SignatureMetadata,
    ) -> None:
        """_match_trusted_issuer matches exact subject."""
        client = VerificationClient(enforce_policy)
        matched = client._match_trusted_issuer(valid_signature_metadata)

        assert matched is not None
        assert matched.subject == "repo:acme/floe:ref:refs/heads/main"

    def test_regex_subject_match(
        self,
        github_actions_issuer_regex: TrustedIssuer,
        valid_signature_metadata: SignatureMetadata,
    ) -> None:
        """_match_trusted_issuer matches regex subject."""
        policy = VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[github_actions_issuer_regex],
        )
        client = VerificationClient(policy)
        matched = client._match_trusted_issuer(valid_signature_metadata)

        assert matched is not None
        assert matched.subject_regex == r"repo:acme/.*:ref:refs/heads/main"

    def test_no_match_returns_none(
        self,
        enforce_policy: VerificationPolicy,
        untrusted_signature_metadata: SignatureMetadata,
    ) -> None:
        """_match_trusted_issuer returns None for untrusted issuer."""
        client = VerificationClient(enforce_policy)
        matched = client._match_trusted_issuer(untrusted_signature_metadata)

        assert matched is None

    def test_issuer_mismatch_not_matched(
        self,
        enforce_policy: VerificationPolicy,
    ) -> None:
        """Signature with wrong issuer but matching subject is not matched."""
        metadata = SignatureMetadata(
            bundle=base64.b64encode(b"{}").decode(),
            mode="keyless",
            issuer="https://wrong-issuer.example.com",
            subject="repo:acme/floe:ref:refs/heads/main",
            signed_at=datetime.now(timezone.utc),
            rekor_log_index=1,
            certificate_fingerprint="c" * 64,
        )
        client = VerificationClient(enforce_policy)
        matched = client._match_trusted_issuer(metadata)

        assert matched is None


@requires_sigstore
class TestVerificationWithSigstore:
    """Tests requiring sigstore library (T036, T037)."""

    def test_verify_valid_signature(
        self,
        enforce_policy: VerificationPolicy,
        valid_signature_metadata: SignatureMetadata,
    ) -> None:
        """verify() returns valid result for correctly signed artifact."""
        with (
            patch("sigstore.verify.Verifier") as mock_verifier_cls,
            patch("sigstore.models.Bundle") as mock_bundle_cls,
            patch("sigstore.verify.policy.Identity"),
        ):
            mock_verifier = MagicMock()
            mock_verifier_cls.production.return_value = mock_verifier

            mock_bundle = MagicMock()
            mock_bundle.to_json.return_value = json.dumps(
                {"verificationMaterial": {"tlogEntries": [{"logIndex": "12345"}]}}
            )
            mock_bundle_cls.from_json.return_value = mock_bundle

            client = VerificationClient(enforce_policy)
            result = client.verify(
                content=b"artifact content",
                metadata=valid_signature_metadata,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

            assert result.status == "valid"
            assert result.signer_identity == "repo:acme/floe:ref:refs/heads/main"
            assert result.issuer == "https://token.actions.githubusercontent.com"

    def test_verify_invalid_signature_raises_when_enforce(
        self,
        enforce_policy: VerificationPolicy,
        valid_signature_metadata: SignatureMetadata,
    ) -> None:
        """verify() raises SignatureVerificationError when signature is invalid and enforce."""
        from sigstore.errors import VerificationError as SigstoreVerificationError

        with (
            patch("sigstore.verify.Verifier") as mock_verifier_cls,
            patch("sigstore.models.Bundle") as mock_bundle_cls,
            patch("sigstore.verify.policy.Identity"),
        ):
            mock_verifier = MagicMock()
            mock_verifier.verify_artifact.side_effect = SigstoreVerificationError(
                "signature invalid"
            )
            mock_verifier_cls.production.return_value = mock_verifier
            mock_bundle_cls.from_json.return_value = MagicMock()

            client = VerificationClient(enforce_policy)

            with pytest.raises(SignatureVerificationError):
                client.verify(
                    content=b"artifact content",
                    metadata=valid_signature_metadata,
                    artifact_ref="oci://registry/repo:v1.0.0",
                )

    def test_verify_untrusted_signer_raises_when_enforce(
        self,
        enforce_policy: VerificationPolicy,
        untrusted_signature_metadata: SignatureMetadata,
    ) -> None:
        """verify() raises SignatureVerificationError for untrusted signer."""
        with (
            patch("sigstore.verify.Verifier") as mock_verifier_cls,
            patch("sigstore.models.Bundle") as mock_bundle_cls,
            patch("sigstore.verify.policy.Identity"),
        ):
            mock_verifier = MagicMock()
            mock_verifier_cls.production.return_value = mock_verifier

            mock_bundle = MagicMock()
            mock_bundle.to_json.return_value = json.dumps(
                {"verificationMaterial": {"tlogEntries": [{"logIndex": "99999"}]}}
            )
            mock_bundle_cls.from_json.return_value = mock_bundle

            client = VerificationClient(enforce_policy)

            with pytest.raises(SignatureVerificationError) as exc_info:
                client.verify(
                    content=b"artifact",
                    metadata=untrusted_signature_metadata,
                    artifact_ref="oci://registry/repo:v1.0.0",
                )

            assert "not in trusted issuers" in str(exc_info.value)


class TestRekorVerification:
    """Tests for Rekor transparency log verification."""

    def test_check_rekor_entry_with_entries(
        self, enforce_policy: VerificationPolicy
    ) -> None:
        """_check_rekor_entry returns True when tlog entries exist."""
        client = VerificationClient(enforce_policy)
        bundle = MagicMock()
        bundle.to_json.return_value = json.dumps(
            {"verificationMaterial": {"tlogEntries": [{"logIndex": "12345"}]}}
        )

        assert client._check_rekor_entry(bundle) is True

    def test_check_rekor_entry_without_entries(
        self, enforce_policy: VerificationPolicy
    ) -> None:
        """_check_rekor_entry returns False when no tlog entries."""
        client = VerificationClient(enforce_policy)
        bundle = MagicMock()
        bundle.to_json.return_value = json.dumps(
            {"verificationMaterial": {"tlogEntries": []}}
        )

        assert client._check_rekor_entry(bundle) is False


class TestAuditLogging:
    """Tests for audit logging (T035)."""

    def test_audit_event_logged_on_verify(
        self,
        warn_policy: VerificationPolicy,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verification audit event is logged."""
        client = VerificationClient(warn_policy)

        with caplog.at_level("INFO"):
            client.verify(
                content=b"artifact",
                metadata=None,
                artifact_ref="oci://registry/repo:v1.0.0",
                artifact_digest="sha256:abc123",
            )

        assert (
            "Verification audit" in caplog.text or "verification" in caplog.text.lower()
        )


class TestVerifyArtifactConvenienceFunction:
    """Tests for verify_artifact() convenience function."""

    def test_verify_artifact_creates_client(
        self,
        enforce_policy: VerificationPolicy,
    ) -> None:
        """verify_artifact() creates VerificationClient and verifies."""
        with pytest.raises(SignatureVerificationError):
            verify_artifact(
                content=b"artifact",
                metadata=None,
                artifact_ref="oci://registry/repo:v1.0.0",
                policy=enforce_policy,
            )


class TestEnvironmentPolicyOverride:
    """Tests for per-environment policy overrides."""

    def test_environment_enforcement_override(
        self, github_actions_issuer: TrustedIssuer
    ) -> None:
        """Environment-specific enforcement overrides default."""
        from floe_core.schemas.signing import EnvironmentPolicy

        policy = VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[github_actions_issuer],
            environments={
                "dev": EnvironmentPolicy(enforcement="off"),
                "prod": EnvironmentPolicy(enforcement="enforce"),
            },
        )

        dev_client = VerificationClient(policy, environment="dev")
        prod_client = VerificationClient(policy, environment="prod")

        assert dev_client.enforcement == "off"
        assert prod_client.enforcement == "enforce"


class TestRequireSBOMEnforcement:
    """Tests for require_sbom enforcement during verification (T058)."""

    def test_require_sbom_property_default(
        self, github_actions_issuer: TrustedIssuer
    ) -> None:
        """Default require_sbom is False."""
        policy = VerificationPolicy(
            enabled=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)
        assert client.require_sbom is False

    def test_require_sbom_property_enabled(
        self, github_actions_issuer: TrustedIssuer
    ) -> None:
        """require_sbom property returns policy value."""
        policy = VerificationPolicy(
            enabled=True,
            require_sbom=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)
        assert client.require_sbom is True

    def test_require_sbom_environment_override(
        self, github_actions_issuer: TrustedIssuer
    ) -> None:
        """Environment-specific require_sbom overrides default."""
        from floe_core.schemas.signing import EnvironmentPolicy

        policy = VerificationPolicy(
            enabled=True,
            require_sbom=False,
            trusted_issuers=[github_actions_issuer],
            environments={
                "prod": EnvironmentPolicy(enforcement="enforce", require_sbom=True),
                "dev": EnvironmentPolicy(enforcement="warn", require_sbom=False),
            },
        )

        prod_client = VerificationClient(policy, environment="prod")
        dev_client = VerificationClient(policy, environment="dev")
        staging_client = VerificationClient(policy, environment="staging")

        assert prod_client.require_sbom is True
        assert dev_client.require_sbom is False
        assert staging_client.require_sbom is False

    @patch("floe_core.oci.verification.VerificationClient._verify_sbom_present")
    def test_sbom_verification_called_when_required(
        self,
        mock_verify_sbom: MagicMock,
        github_actions_issuer: TrustedIssuer,
    ) -> None:
        """_verify_sbom_present is called when require_sbom=True and signature valid."""
        mock_verify_sbom.return_value = None

        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            require_sbom=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)

        with patch.object(client, "_verify_signature") as mock_sig:
            mock_sig.return_value = VerificationResult(
                status="valid",
                signer_identity="test@example.com",
                verified_at=datetime.now(timezone.utc),
            )
            client.verify(
                content=b"test",
                metadata=MagicMock(),
                artifact_ref="oci://registry/repo:v1.0.0",
            )

        mock_verify_sbom.assert_called_once()

    @patch("floe_core.oci.verification.VerificationClient._verify_sbom_present")
    def test_sbom_verification_skipped_when_not_required(
        self,
        mock_verify_sbom: MagicMock,
        github_actions_issuer: TrustedIssuer,
    ) -> None:
        """_verify_sbom_present is NOT called when require_sbom=False."""
        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            require_sbom=False,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)

        with patch.object(client, "_verify_signature") as mock_sig:
            mock_sig.return_value = VerificationResult(
                status="valid",
                signer_identity="test@example.com",
                verified_at=datetime.now(timezone.utc),
            )
            client.verify(
                content=b"test",
                metadata=MagicMock(),
                artifact_ref="oci://registry/repo:v1.0.0",
            )

        mock_verify_sbom.assert_not_called()

    @patch("floe_core.oci.attestation.retrieve_sbom")
    def test_sbom_missing_returns_invalid_result(
        self, mock_retrieve: MagicMock, github_actions_issuer: TrustedIssuer
    ) -> None:
        """Missing SBOM returns invalid result when required."""
        mock_retrieve.return_value = None

        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            require_sbom=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)

        mock_span = MagicMock()
        result = client._verify_sbom_present("oci://registry/repo:v1.0.0", mock_span)

        assert result is not None
        assert result.status == "invalid"
        assert "SBOM" in (result.failure_reason or "")

    @patch("floe_core.oci.attestation.retrieve_sbom")
    def test_sbom_present_returns_none(
        self, mock_retrieve: MagicMock, github_actions_issuer: TrustedIssuer
    ) -> None:
        """Present SBOM returns None (no failure)."""
        mock_retrieve.return_value = {"spdxVersion": "SPDX-2.3"}

        policy = VerificationPolicy(
            enabled=True,
            require_sbom=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)

        mock_span = MagicMock()
        result = client._verify_sbom_present("oci://registry/repo:v1.0.0", mock_span)

        assert result is None


class TestKeyBasedVerification:
    """Tests for key-based verification (T067, T068)."""

    @pytest.fixture
    def key_based_signature_metadata(self, tmp_path) -> SignatureMetadata:
        """Create key-based signature metadata."""
        bundle_data = {"base64Signature": base64.b64encode(b"test-signature").decode()}
        return SignatureMetadata(
            bundle=base64.b64encode(json.dumps(bundle_data).encode()).decode(),
            mode="key-based",
            issuer=None,
            subject="/path/to/key",
            signed_at=datetime.now(timezone.utc),
            rekor_log_index=None,
            certificate_fingerprint="a" * 16,
        )

    @pytest.fixture
    def key_based_policy(self, tmp_path) -> VerificationPolicy:
        """Create verification policy for key-based verification."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        key_file = tmp_path / "cosign.pub"
        key_file.write_text(
            "-----BEGIN PUBLIC KEY-----\ntest\n-----END PUBLIC KEY-----"
        )

        import os

        os.environ["FLOE_TEST_PUB_KEY"] = str(key_file)

        return VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[],
            require_rekor=False,
            public_key_ref=SecretReference(
                source=SecretSource.ENV, name="test-pub-key"
            ),
        )

    def test_check_cosign_available_returns_bool(self) -> None:
        """check_cosign_available() returns boolean."""
        result = check_cosign_available()
        assert isinstance(result, bool)

    def test_cosign_not_available_error_message(self) -> None:
        """CosignNotAvailableError has helpful message."""
        error = CosignNotAvailableError()
        assert "cosign CLI not found" in str(error)

    def test_key_verification_error_message(self) -> None:
        """KeyVerificationError includes reason and key reference."""
        error = KeyVerificationError("Signature mismatch", key_ref="/path/to/key.pub")
        assert "Signature mismatch" in str(error)
        assert "/path/to/key.pub" in str(error)

    def test_verify_routes_to_key_based(
        self,
        key_based_policy: VerificationPolicy,
        key_based_signature_metadata: SignatureMetadata,
    ) -> None:
        """verify() routes to _verify_key_based for key-based signatures."""
        with (
            patch(
                "floe_core.oci.verification.check_cosign_available", return_value=True
            ),
            patch.object(
                VerificationClient, "_cosign_verify_blob", return_value=True
            ) as mock_verify,
        ):
            client = VerificationClient(key_based_policy)
            result = client.verify(
                content=b"artifact content",
                metadata=key_based_signature_metadata,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

            mock_verify.assert_called_once()
            assert result.status == "valid"
            assert result.rekor_verified is False

    def test_verify_key_based_without_cosign(
        self,
        key_based_policy: VerificationPolicy,
        key_based_signature_metadata: SignatureMetadata,
    ) -> None:
        """Key-based verification returns invalid when cosign not available."""
        with patch(
            "floe_core.oci.verification.check_cosign_available", return_value=False
        ):
            client = VerificationClient(key_based_policy)
            result = client._verify_key_based(
                content=b"content",
                metadata=key_based_signature_metadata,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

            assert result.status == "invalid"
            assert "cosign CLI not available" in (result.failure_reason or "")

    def test_verify_policy_requires_issuers_or_key(self) -> None:
        """VerificationPolicy requires trusted_issuers or public_key_ref when enabled."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="trusted_issuers or public_key_ref"):
            VerificationPolicy(
                enabled=True,
                enforcement="enforce",
                trusted_issuers=[],
                public_key_ref=None,
            )

    def test_resolve_public_key_ref_env(
        self, key_based_policy: VerificationPolicy
    ) -> None:
        """_resolve_public_key_ref resolves environment variable."""
        client = VerificationClient(key_based_policy)
        key_ref = client._resolve_public_key_ref()

        assert key_ref is not None
        assert "cosign.pub" in key_ref

    def test_resolve_public_key_ref_missing_env(self) -> None:
        """_resolve_public_key_ref returns None for missing env var."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        policy = VerificationPolicy(
            enabled=True,
            trusted_issuers=[],
            public_key_ref=SecretReference(
                source=SecretSource.ENV, name="nonexistent-var"
            ),
        )
        client = VerificationClient(policy)

        assert client._resolve_public_key_ref() is None

    def test_cosign_verify_blob_success(
        self, key_based_policy: VerificationPolicy, tmp_path
    ) -> None:
        """_cosign_verify_blob returns True on success."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            client = VerificationClient(key_based_policy)
            result = client._cosign_verify_blob(
                content=b"test content",
                bundle_data={"base64Signature": "dGVzdC1zaWc="},
                public_key_ref=str(tmp_path / "key.pub"),
            )

            assert result is True
            mock_run.assert_called_once()

    def test_cosign_verify_blob_failure(
        self, key_based_policy: VerificationPolicy, tmp_path
    ) -> None:
        """_cosign_verify_blob returns False on verification failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="verification failed"
            )

            client = VerificationClient(key_based_policy)
            result = client._cosign_verify_blob(
                content=b"test content",
                bundle_data={"base64Signature": "dGVzdC1zaWc="},
                public_key_ref=str(tmp_path / "key.pub"),
            )

            assert result is False

    def test_cosign_verify_blob_timeout(
        self, key_based_policy: VerificationPolicy, tmp_path
    ) -> None:
        """_cosign_verify_blob handles timeout."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="cosign", timeout=60)

            client = VerificationClient(key_based_policy)
            result = client._cosign_verify_blob(
                content=b"test content",
                bundle_data={"base64Signature": "dGVzdC1zaWc="},
                public_key_ref=str(tmp_path / "key.pub"),
            )

            assert result is False


@requires_sigstore
class TestOfflineVerification:
    """Tests for offline verification without Rekor (T063, T068)."""

    def test_offline_verifier_when_rekor_not_required(
        self, github_actions_issuer: TrustedIssuer
    ) -> None:
        """Verifier uses offline mode when require_rekor=False."""
        policy = VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[github_actions_issuer],
            require_rekor=False,
        )

        with patch("sigstore.verify.Verifier") as mock_verifier_cls:
            client = VerificationClient(policy)
            client._verifier = None

            with (
                patch("sigstore.models.Bundle"),
                patch("sigstore.verify.policy.Identity"),
            ):
                mock_verifier_cls.production.return_value = MagicMock()
                bundle_data = {"verificationMaterial": {"tlogEntries": []}}
                metadata = SignatureMetadata(
                    bundle=base64.b64encode(json.dumps(bundle_data).encode()).decode(),
                    mode="keyless",
                    issuer="https://token.actions.githubusercontent.com",
                    subject="repo:acme/floe:ref:refs/heads/main",
                    signed_at=datetime.now(timezone.utc),
                    rekor_log_index=None,
                    certificate_fingerprint="a" * 64,
                )

                try:
                    client._verify_keyless(
                        b"content", metadata, "oci://registry/repo:v1.0.0"
                    )
                except Exception:
                    pass

                mock_verifier_cls.production.assert_called_with(offline=True)

    def test_online_verifier_when_rekor_required(
        self, enforce_policy: VerificationPolicy
    ) -> None:
        """Verifier uses online mode when require_rekor=True."""
        with patch("sigstore.verify.Verifier") as mock_verifier_cls:
            client = VerificationClient(enforce_policy)
            client._verifier = None

            with (
                patch("sigstore.models.Bundle"),
                patch("sigstore.verify.policy.Identity"),
            ):
                mock_verifier_cls.production.return_value = MagicMock()
                bundle_data = {
                    "verificationMaterial": {"tlogEntries": [{"logIndex": "123"}]}
                }
                metadata = SignatureMetadata(
                    bundle=base64.b64encode(json.dumps(bundle_data).encode()).decode(),
                    mode="keyless",
                    issuer="https://token.actions.githubusercontent.com",
                    subject="repo:acme/floe:ref:refs/heads/main",
                    signed_at=datetime.now(timezone.utc),
                    rekor_log_index=123,
                    certificate_fingerprint="a" * 64,
                )

                try:
                    client._verify_keyless(
                        b"content", metadata, "oci://registry/repo:v1.0.0"
                    )
                except Exception:
                    pass

                mock_verifier_cls.production.assert_called_with(offline=False)


class TestKeyBasedOfflineVerification:
    """Tests for key-based verification (always offline)."""

    @pytest.fixture
    def key_based_signature_metadata(self) -> SignatureMetadata:
        """Create key-based signature metadata."""
        bundle_data = {"base64Signature": base64.b64encode(b"test-signature").decode()}
        return SignatureMetadata(
            bundle=base64.b64encode(json.dumps(bundle_data).encode()).decode(),
            mode="key-based",
            issuer=None,
            subject="/path/to/key",
            signed_at=datetime.now(timezone.utc),
            rekor_log_index=None,
            certificate_fingerprint="a" * 16,
        )

    def test_key_based_verification_always_offline(
        self, key_based_signature_metadata: SignatureMetadata
    ) -> None:
        """Key-based verification doesn't require Rekor."""
        from floe_core.schemas.secrets import SecretReference, SecretSource

        policy = VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[],
            require_rekor=True,
            public_key_ref=SecretReference(source=SecretSource.ENV, name="test-key"),
        )

        import os

        os.environ["FLOE_TEST_KEY"] = "/path/to/key.pub"

        with (
            patch(
                "floe_core.oci.verification.check_cosign_available", return_value=True
            ),
            patch.object(VerificationClient, "_cosign_verify_blob", return_value=True),
        ):
            client = VerificationClient(policy)
            result = client._verify_key_based(
                content=b"content",
                metadata=key_based_signature_metadata,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

            assert result.status == "valid"
            assert result.rekor_verified is False


class TestCertificateGracePeriod:
    """Tests for certificate rotation grace period (FR-012).

    Task: T080
    Requirements: FR-012, 8B-FR-009
    """

    @pytest.fixture
    def policy_with_grace_period(
        self, github_actions_issuer: TrustedIssuer
    ) -> VerificationPolicy:
        """Create policy with 7-day grace period."""
        return VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[github_actions_issuer],
            grace_period_days=7,
        )

    @pytest.mark.requirement("8B-FR-012")
    def test_is_certificate_expired_error_detects_expiration(
        self, policy_with_grace_period: VerificationPolicy
    ) -> None:
        """Test _is_certificate_expired_error detects expiration-related errors."""
        client = VerificationClient(policy_with_grace_period)

        expired_errors = [
            Exception("certificate expired at 2026-01-15"),
            Exception("invalid signing cert: expired at time of signing"),
            Exception("Certificate not valid after 2026-01-15"),
            Exception("cert validity period exceeded"),
        ]
        for error in expired_errors:
            assert client._is_certificate_expired_error(error) is True

    @pytest.mark.requirement("8B-FR-012")
    def test_is_certificate_expired_error_ignores_other_errors(
        self, policy_with_grace_period: VerificationPolicy
    ) -> None:
        """Test _is_certificate_expired_error ignores non-expiration errors."""
        client = VerificationClient(policy_with_grace_period)

        other_errors = [
            Exception("signature mismatch"),
            Exception("untrusted issuer"),
            Exception("bundle parse error"),
            Exception("network timeout"),
        ]
        for error in other_errors:
            assert client._is_certificate_expired_error(error) is False

    @pytest.mark.requirement("8B-FR-012")
    def test_get_certificate_expiration_extracts_from_bundle(
        self, policy_with_grace_period: VerificationPolicy
    ) -> None:
        """Test _get_certificate_expiration extracts expiry from bundle."""
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        client = VerificationClient(policy_with_grace_period)

        mock_bundle = MagicMock()
        mock_cert = MagicMock()
        mock_cert.not_valid_after_utc = datetime(
            2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc
        )
        mock_bundle.signing_certificate = mock_cert

        expiry = client._get_certificate_expiration(mock_bundle)
        assert expiry == datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.requirement("8B-FR-012")
    def test_get_certificate_expiration_returns_none_on_error(
        self, policy_with_grace_period: VerificationPolicy
    ) -> None:
        """Test _get_certificate_expiration returns None if extraction fails."""
        from unittest.mock import MagicMock

        client = VerificationClient(policy_with_grace_period)

        mock_bundle = MagicMock()
        mock_bundle.signing_certificate = None

        expiry = client._get_certificate_expiration(mock_bundle)
        assert expiry is None

    @requires_sigstore
    @pytest.mark.requirement("8B-FR-012")
    def test_verify_accepts_expired_cert_within_grace_period(
        self,
        policy_with_grace_period: VerificationPolicy,
        valid_signature_metadata: SignatureMetadata,
    ) -> None:
        """Test that expired certificate is accepted if within grace period."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        client = VerificationClient(policy_with_grace_period)

        expired_at = datetime.now(timezone.utc) - timedelta(days=3)

        mock_bundle = MagicMock()
        mock_cert = MagicMock()
        mock_cert.not_valid_after_utc = expired_at
        mock_bundle.signing_certificate = mock_cert
        mock_bundle.to_json.return_value = (
            '{"verificationMaterial": {"tlogEntries": [{}]}}'
        )

        with (
            patch("sigstore.models.Bundle.from_json", return_value=mock_bundle),
            patch("sigstore.verify.Verifier.production") as mock_verifier_cls,
        ):
            mock_verifier = MagicMock()
            mock_verifier.verify_artifact.side_effect = Exception(
                "invalid signing cert: expired at time of signing"
            )
            mock_verifier_cls.return_value = mock_verifier

            result = client._verify_keyless(
                content=b"test-content",
                metadata=valid_signature_metadata,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

        assert result.status == "valid"
        assert result.within_grace_period is True
        assert result.certificate_expired_at == expired_at

    @requires_sigstore
    @pytest.mark.requirement("8B-FR-012")
    def test_verify_rejects_expired_cert_outside_grace_period(
        self,
        policy_with_grace_period: VerificationPolicy,
        valid_signature_metadata: SignatureMetadata,
    ) -> None:
        """Test that expired certificate is rejected if outside grace period."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        client = VerificationClient(policy_with_grace_period)

        expired_at = datetime.now(timezone.utc) - timedelta(days=30)

        mock_bundle = MagicMock()
        mock_cert = MagicMock()
        mock_cert.not_valid_after_utc = expired_at
        mock_bundle.signing_certificate = mock_cert

        with (
            patch("sigstore.models.Bundle.from_json", return_value=mock_bundle),
            patch("sigstore.verify.Verifier.production") as mock_verifier_cls,
        ):
            mock_verifier = MagicMock()
            mock_verifier.verify_artifact.side_effect = Exception(
                "invalid signing cert: expired at time of signing"
            )
            mock_verifier_cls.return_value = mock_verifier

            result = client._verify_keyless(
                content=b"test-content",
                metadata=valid_signature_metadata,
                artifact_ref="oci://registry/repo:v1.0.0",
            )

        assert result.status == "invalid"
        assert result.within_grace_period is False
        assert result.failure_reason is not None
        assert "expired" in result.failure_reason.lower()

    @pytest.mark.requirement("8B-FR-012")
    def test_verification_result_includes_grace_period_fields(self) -> None:
        """Test VerificationResult has certificate_expired_at and within_grace_period."""
        from datetime import datetime, timezone

        result = VerificationResult(
            status="valid",
            verified_at=datetime.now(timezone.utc),
            certificate_expired_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            within_grace_period=True,
        )

        assert result.certificate_expired_at is not None
        assert result.within_grace_period is True
        assert result.is_valid is True


class TestAuditLogFormat:
    """Tests for audit log format validation (FR-013).

    Task: T083
    Requirements: FR-013, 8B-FR-013
    """

    @pytest.mark.requirement("8B-FR-013")
    def test_verification_audit_event_has_required_fields(self) -> None:
        """VerificationAuditEvent has all required fields for audit trail."""
        from datetime import datetime, timezone

        from floe_core.schemas.signing import VerificationAuditEvent

        event = VerificationAuditEvent(
            artifact_ref="oci://registry/repo:v1.0.0",
            artifact_digest="sha256:abc123def456",
            policy_enforcement="enforce",
            expected_issuers=["https://token.actions.githubusercontent.com"],
            actual_issuer="https://token.actions.githubusercontent.com",
            actual_subject="repo:acme/floe:ref:refs/heads/main",
            signature_status="valid",
            rekor_verified=True,
            timestamp=datetime.now(timezone.utc),
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            success=True,
        )

        assert event.event_type == "verification"
        assert event.artifact_ref == "oci://registry/repo:v1.0.0"
        assert event.trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert event.span_id == "b7ad6b7169203331"

    @pytest.mark.requirement("8B-FR-013")
    def test_signing_audit_event_has_required_fields(self) -> None:
        """SigningAuditEvent has all required fields for audit trail."""
        from datetime import datetime, timezone

        from floe_core.schemas.signing import SigningAuditEvent

        event = SigningAuditEvent(
            artifact_ref="oci://registry/repo:v1.0.0",
            artifact_digest="sha256:abc123def456",
            signing_mode="keyless",
            signer_identity="repo:acme/floe:ref:refs/heads/main",
            issuer="https://token.actions.githubusercontent.com",
            rekor_log_index=12345678,
            timestamp=datetime.now(timezone.utc),
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            success=True,
        )

        assert event.event_type == "signing"
        assert event.signing_mode == "keyless"
        assert event.rekor_log_index == 12345678
        assert event.trace_id == "0af7651916cd43dd8448eb211c80319c"

    @pytest.mark.requirement("8B-FR-013")
    def test_audit_event_serializes_to_json(self) -> None:
        """Audit events serialize to valid JSON for log aggregation."""
        from datetime import datetime, timezone

        from floe_core.schemas.signing import VerificationAuditEvent

        event = VerificationAuditEvent(
            artifact_ref="oci://registry/repo:v1.0.0",
            artifact_digest="sha256:abc123def456",
            policy_enforcement="enforce",
            expected_issuers=["https://github.com"],
            signature_status="valid",
            rekor_verified=True,
            timestamp=datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc),
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            success=True,
        )

        import json

        json_str = event.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "verification"
        assert parsed["artifact_ref"] == "oci://registry/repo:v1.0.0"
        assert parsed["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        assert "2026-01-27" in parsed["timestamp"]

    @pytest.mark.requirement("8B-FR-013")
    def test_audit_event_includes_failure_reason(self) -> None:
        """Failed verification audit includes failure reason."""
        from datetime import datetime, timezone

        from floe_core.schemas.signing import VerificationAuditEvent

        event = VerificationAuditEvent(
            artifact_ref="oci://registry/repo:v1.0.0",
            artifact_digest="sha256:abc123def456",
            policy_enforcement="enforce",
            expected_issuers=["https://trusted.issuer.com"],
            actual_issuer="https://untrusted.issuer.com",
            signature_status="invalid",
            rekor_verified=False,
            timestamp=datetime.now(timezone.utc),
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            success=False,
            failure_reason="Signer not in trusted issuers list",
        )

        assert event.success is False
        assert event.failure_reason == "Signer not in trusted issuers list"

    @pytest.mark.requirement("8B-FR-013")
    def test_audit_events_are_immutable(self) -> None:
        """Audit events should be frozen (immutable) for integrity."""
        from datetime import datetime, timezone

        import pydantic

        from floe_core.schemas.signing import VerificationAuditEvent

        event = VerificationAuditEvent(
            artifact_ref="oci://registry/repo:v1.0.0",
            artifact_digest="sha256:abc123def456",
            policy_enforcement="enforce",
            expected_issuers=[],
            signature_status="valid",
            rekor_verified=True,
            timestamp=datetime.now(timezone.utc),
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            success=True,
        )

        with pytest.raises(pydantic.ValidationError):
            event.success = False  # type: ignore[misc]


class TestVerificationBundleExport:
    """Tests for offline verification bundle creation (FR-015).

    Task: T086
    Requirements: FR-015, 8B-FR-015
    """

    @pytest.fixture
    def sample_signature_metadata(self) -> SignatureMetadata:
        """Create sample SignatureMetadata with realistic Sigstore bundle."""
        import base64
        import json

        bundle_dict = {
            "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json",
            "verificationMaterial": {
                "certificate": {"rawBytes": "LS0tLS1CRUdJTi..."},
                "tlogEntries": [
                    {
                        "logIndex": "12345678",
                        "logId": {"keyId": "abc123"},
                        "kindVersion": {"kind": "hashedrekord", "version": "0.0.1"},
                        "integratedTime": "1706345678",
                        "inclusionPromise": {"signedEntryTimestamp": "abc..."},
                    }
                ],
            },
            "messageSignature": {
                "messageDigest": {"algorithm": "SHA2_256", "digest": "abc123..."},
                "signature": "MEUCIQDx...",
            },
        }
        bundle_json = json.dumps(bundle_dict)
        bundle_b64 = base64.b64encode(bundle_json.encode()).decode()

        return SignatureMetadata(
            bundle=bundle_b64,
            mode="keyless",
            issuer="https://token.actions.githubusercontent.com",
            subject="repo:acme/floe:ref:refs/heads/main",
            signed_at=datetime.now(timezone.utc),
            certificate_fingerprint="abcd1234" * 8,
            rekor_log_index=12345678,
        )

    @pytest.mark.requirement("8B-FR-015")
    def test_export_bundle_creates_valid_bundle(
        self, sample_signature_metadata: SignatureMetadata
    ) -> None:
        """export_verification_bundle creates valid VerificationBundle."""
        from floe_core.oci.verification import export_verification_bundle
        from floe_core.schemas.signing import VerificationBundle

        bundle = export_verification_bundle(
            artifact_digest="sha256:abc123def456",
            metadata=sample_signature_metadata,
        )

        assert isinstance(bundle, VerificationBundle)
        assert bundle.version == "1.0"
        assert bundle.artifact_digest == "sha256:abc123def456"
        assert bundle.sigstore_bundle is not None
        assert "verificationMaterial" in bundle.sigstore_bundle

    @pytest.mark.requirement("8B-FR-015")
    def test_export_bundle_extracts_certificate_chain(
        self, sample_signature_metadata: SignatureMetadata
    ) -> None:
        """export_verification_bundle extracts certificate from bundle."""
        from floe_core.oci.verification import export_verification_bundle

        bundle = export_verification_bundle(
            artifact_digest="sha256:abc123def456",
            metadata=sample_signature_metadata,
        )

        assert len(bundle.certificate_chain) == 1
        assert bundle.certificate_chain[0] == "LS0tLS1CRUdJTi..."

    @pytest.mark.requirement("8B-FR-015")
    def test_export_bundle_extracts_rekor_entry(
        self, sample_signature_metadata: SignatureMetadata
    ) -> None:
        """export_verification_bundle extracts Rekor entry from bundle."""
        from floe_core.oci.verification import export_verification_bundle

        bundle = export_verification_bundle(
            artifact_digest="sha256:abc123def456",
            metadata=sample_signature_metadata,
        )

        assert bundle.rekor_entry is not None
        assert bundle.rekor_entry.get("logIndex") == "12345678"

    @pytest.mark.requirement("8B-FR-015")
    def test_export_bundle_sets_created_at(
        self, sample_signature_metadata: SignatureMetadata
    ) -> None:
        """export_verification_bundle sets creation timestamp."""
        from floe_core.oci.verification import export_verification_bundle

        before = datetime.now(timezone.utc)
        bundle = export_verification_bundle(
            artifact_digest="sha256:abc123def456",
            metadata=sample_signature_metadata,
        )
        after = datetime.now(timezone.utc)

        assert before <= bundle.created_at <= after

    @pytest.mark.requirement("8B-FR-015")
    def test_verification_bundle_serializes_to_json(
        self, sample_signature_metadata: SignatureMetadata
    ) -> None:
        """VerificationBundle can be serialized to JSON for export."""
        import json

        from floe_core.oci.verification import export_verification_bundle

        bundle = export_verification_bundle(
            artifact_digest="sha256:abc123def456",
            metadata=sample_signature_metadata,
        )

        json_str = bundle.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["version"] == "1.0"
        assert parsed["artifact_digest"] == "sha256:abc123def456"
        assert "sigstore_bundle" in parsed
        assert "certificate_chain" in parsed

    @pytest.mark.requirement("8B-FR-015")
    def test_verification_bundle_is_immutable(
        self, sample_signature_metadata: SignatureMetadata
    ) -> None:
        """VerificationBundle should be frozen for integrity."""
        import pydantic

        from floe_core.oci.verification import export_verification_bundle

        bundle = export_verification_bundle(
            artifact_digest="sha256:abc123def456",
            metadata=sample_signature_metadata,
        )

        with pytest.raises(pydantic.ValidationError):
            bundle.artifact_digest = "sha256:tampered"  # type: ignore[misc]


class TestVerificationOpenTelemetrySpans:
    """Tests for verification OpenTelemetry span emission (T088, SC-007).

    Verify that verification operations emit the documented OTel spans.
    """

    @pytest.fixture
    def captured_spans(self):
        """Capture spans by patching the verification module's tracer."""
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )
        from opentelemetry.sdk.trace.sampling import ALWAYS_ON

        import floe_core.oci.verification as verification_module

        exporter = InMemorySpanExporter()
        provider = TracerProvider(sampler=ALWAYS_ON)
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test.verification")

        # Patch the module-level tracer
        original_tracer = verification_module.tracer
        verification_module.tracer = test_tracer

        yield exporter

        # Restore original tracer
        verification_module.tracer = original_tracer
        exporter.clear()

    @pytest.fixture
    def sample_policy(self) -> VerificationPolicy:
        """Create a sample verification policy."""
        return VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[
                TrustedIssuer(
                    issuer=HttpUrl("https://token.actions.githubusercontent.com"),
                    subject="repo:acme/floe:ref:refs/heads/main",
                )
            ],
        )

    @pytest.fixture
    def sample_metadata(self) -> SignatureMetadata:
        """Create sample signature metadata."""
        return SignatureMetadata(
            bundle="dGVzdC1idW5kbGU=",
            mode="keyless",
            issuer="https://token.actions.githubusercontent.com",
            subject="repo:acme/floe:ref:refs/heads/main",
            signed_at=datetime(2026, 1, 27, 10, 0, 0, tzinfo=timezone.utc),
            rekor_log_index=12345678,
            certificate_fingerprint="a" * 64,
        )

    @pytest.fixture
    def mock_verification_result(self) -> VerificationResult:
        """Create a mock successful verification result."""
        return VerificationResult(
            status="valid",
            signer_identity="repo:acme/floe:ref:refs/heads/main",
            issuer="https://token.actions.githubusercontent.com",
            verified_at=datetime.now(timezone.utc),
            rekor_verified=True,
            certificate_chain=[],
            failure_reason=None,
        )

    @requires_sigstore
    @pytest.mark.requirement("SC-007")
    def test_verify_emits_root_span(
        self,
        captured_spans,
        sample_policy: VerificationPolicy,
        sample_metadata: SignatureMetadata,
        mock_verification_result: VerificationResult,
    ) -> None:
        """Verification emits floe.oci.verify root span."""
        with patch.object(
            VerificationClient, "_verify_keyless", return_value=mock_verification_result
        ):
            client = VerificationClient(sample_policy)
            client.verify(
                content=b"test content",
                artifact_ref="oci://registry/repo:v1.0.0",
                metadata=sample_metadata,
            )

        spans = captured_spans.get_finished_spans()
        span_names = [span.name for span in spans]

        assert "floe.oci.verify" in span_names

    @requires_sigstore
    @pytest.mark.requirement("SC-007")
    def test_verify_span_has_required_attributes(
        self,
        captured_spans,
        sample_policy: VerificationPolicy,
        sample_metadata: SignatureMetadata,
        mock_verification_result: VerificationResult,
    ) -> None:
        """floe.oci.verify span has documented attributes."""
        with patch.object(
            VerificationClient, "_verify_keyless", return_value=mock_verification_result
        ):
            client = VerificationClient(sample_policy)
            client.verify(
                content=b"test content",
                artifact_ref="oci://registry/repo:v1.0.0",
                metadata=sample_metadata,
            )

        spans = captured_spans.get_finished_spans()
        verify_span = next((s for s in spans if s.name == "floe.oci.verify"), None)

        assert verify_span is not None
        attrs = dict(verify_span.attributes)

        # Verify documented attributes per research.md
        assert "floe.artifact.ref" in attrs
        assert attrs["floe.artifact.ref"] == "oci://registry/repo:v1.0.0"
        assert "floe.verification.enforcement" in attrs
        assert attrs["floe.verification.enforcement"] == "enforce"
        assert "floe.verification.status" in attrs

    @requires_sigstore
    @pytest.mark.requirement("SC-007")
    def test_verify_sets_status_attribute(
        self,
        captured_spans,
        sample_policy: VerificationPolicy,
        sample_metadata: SignatureMetadata,
        mock_verification_result: VerificationResult,
    ) -> None:
        """Verification sets status attribute on completion."""
        with patch.object(
            VerificationClient, "_verify_keyless", return_value=mock_verification_result
        ):
            client = VerificationClient(sample_policy)
            client.verify(
                content=b"test content",
                artifact_ref="oci://registry/repo:v1.0.0",
                metadata=sample_metadata,
            )

        spans = captured_spans.get_finished_spans()
        verify_span = next((s for s in spans if s.name == "floe.oci.verify"), None)

        assert verify_span is not None
        attrs = dict(verify_span.attributes)

        # Verify status is recorded
        assert "floe.verification.status" in attrs
        assert attrs["floe.verification.status"] == "valid"

    @pytest.mark.requirement("SC-007")
    def test_verify_with_environment_sets_attribute(
        self,
        captured_spans,
        sample_metadata: SignatureMetadata,
        mock_verification_result: VerificationResult,
    ) -> None:
        """Verification with environment sets floe.verification.environment attribute."""
        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            trusted_issuers=[
                TrustedIssuer(
                    issuer=HttpUrl("https://token.actions.githubusercontent.com"),
                    subject="repo:acme/floe:ref:refs/heads/main",
                )
            ],
        )

        with patch.object(
            VerificationClient, "_verify_keyless", return_value=mock_verification_result
        ):
            client = VerificationClient(policy, environment="staging")
            client.verify(
                content=b"test content",
                artifact_ref="oci://registry/repo:v1.0.0",
                metadata=sample_metadata,
            )

        spans = captured_spans.get_finished_spans()
        verify_span = next((s for s in spans if s.name == "floe.oci.verify"), None)

        assert verify_span is not None
        attrs = dict(verify_span.attributes)
        assert "floe.verification.environment" in attrs
        assert attrs["floe.verification.environment"] == "staging"
