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
from typing import TYPE_CHECKING
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

from floe_core.oci.errors import SignatureVerificationError
from floe_core.oci.verification import (
    PolicyViolationError,
    VerificationClient,
    VerificationError,
    verify_artifact,
)
from floe_core.schemas.signing import (
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

    def test_is_enabled_false_when_disabled(self, github_actions_issuer: TrustedIssuer) -> None:
        """is_enabled returns False when policy.enabled=False."""
        policy = VerificationPolicy(
            enabled=False,
            enforcement="enforce",
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)

        assert client.is_enabled is False

    def test_is_enabled_false_when_enforcement_off(self, off_policy: VerificationPolicy) -> None:
        """is_enabled returns False when enforcement=off."""
        client = VerificationClient(off_policy)

        assert client.is_enabled is False


class TestVerificationClientEnforcementLevels:
    """Tests for enforcement levels (T038)."""

    def test_enforce_raises_on_unsigned(self, enforce_policy: VerificationPolicy) -> None:
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

    def test_off_silently_accepts_unsigned(self, off_policy: VerificationPolicy) -> None:
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
            mock_bundle_cls.from_json.return_value = MagicMock()

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
        from sigstore.verify import VerificationError as SigstoreVerificationError

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

    def test_check_rekor_entry_with_entries(self, enforce_policy: VerificationPolicy) -> None:
        """_check_rekor_entry returns True when tlog entries exist."""
        client = VerificationClient(enforce_policy)
        bundle = MagicMock()
        bundle.to_json.return_value = json.dumps(
            {"verificationMaterial": {"tlogEntries": [{"logIndex": "12345"}]}}
        )

        assert client._check_rekor_entry(bundle) is True

    def test_check_rekor_entry_without_entries(self, enforce_policy: VerificationPolicy) -> None:
        """_check_rekor_entry returns False when no tlog entries."""
        client = VerificationClient(enforce_policy)
        bundle = MagicMock()
        bundle.to_json.return_value = json.dumps({"verificationMaterial": {"tlogEntries": []}})

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

        assert "Verification audit" in caplog.text or "verification" in caplog.text.lower()


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

    def test_environment_enforcement_override(self, github_actions_issuer: TrustedIssuer) -> None:
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

    def test_require_sbom_property_default(self, github_actions_issuer: TrustedIssuer) -> None:
        """Default require_sbom is False."""
        policy = VerificationPolicy(
            enabled=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)
        assert client.require_sbom is False

    def test_require_sbom_property_enabled(self, github_actions_issuer: TrustedIssuer) -> None:
        """require_sbom property returns policy value."""
        policy = VerificationPolicy(
            enabled=True,
            require_sbom=True,
            trusted_issuers=[github_actions_issuer],
        )
        client = VerificationClient(policy)
        assert client.require_sbom is True

    def test_require_sbom_environment_override(self, github_actions_issuer: TrustedIssuer) -> None:
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
