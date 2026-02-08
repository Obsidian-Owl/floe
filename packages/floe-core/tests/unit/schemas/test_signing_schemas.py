"""Unit tests for artifact signing schemas.

Tests validation of signing configuration, verification policy,
trusted issuers, and signature metadata.

Task: T011, T012, T013
Requirements: FR-001, FR-009, FR-011, FR-012
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import HttpUrl, ValidationError

from floe_core.schemas.secrets import SecretReference, SecretSource
from floe_core.schemas.signing import (
    AttestationManifest,
    EnvironmentPolicy,
    SignatureMetadata,
    SigningConfig,
    Subject,
    TrustedIssuer,
    VerificationBundle,
    VerificationPolicy,
    VerificationResult,
)


class TestSigningConfigValidation:
    """Tests for SigningConfig validation rules (T011)."""

    @pytest.mark.requirement("8B-FR-001")
    def test_keyless_mode_valid(self) -> None:
        """Test that keyless mode with OIDC issuer is valid."""
        config = SigningConfig(
            mode="keyless",
            oidc_issuer=HttpUrl("https://token.actions.githubusercontent.com"),
        )
        assert config.mode == "keyless"
        assert str(config.oidc_issuer) == "https://token.actions.githubusercontent.com/"

    @pytest.mark.requirement("8B-FR-001")
    def test_key_based_mode_valid(self) -> None:
        """Test that key-based mode with private key ref is valid."""
        config = SigningConfig(
            mode="key-based",
            private_key_ref=SecretReference(
                source=SecretSource.KUBERNETES,
                name="cosign-key",
            ),
        )
        assert config.mode == "key-based"
        assert config.private_key_ref is not None
        assert config.private_key_ref.name == "cosign-key"

    @pytest.mark.requirement("8B-FR-001")
    def test_keyless_mode_requires_oidc_issuer(self) -> None:
        """Test that keyless mode requires oidc_issuer."""
        with pytest.raises(ValidationError) as exc_info:
            SigningConfig(mode="keyless")
        assert "oidc_issuer required for keyless mode" in str(exc_info.value)

    @pytest.mark.requirement("8B-FR-001")
    def test_key_based_mode_requires_private_key_ref(self) -> None:
        """Test that key-based mode requires private_key_ref."""
        with pytest.raises(ValidationError) as exc_info:
            SigningConfig(mode="key-based")
        assert "private_key_ref required for key-based mode" in str(exc_info.value)

    @pytest.mark.requirement("8B-FR-001")
    def test_keyless_mode_rejects_private_key_ref(self) -> None:
        """Test that keyless mode rejects private_key_ref."""
        with pytest.raises(ValidationError) as exc_info:
            SigningConfig(
                mode="keyless",
                oidc_issuer=HttpUrl("https://example.com"),
                private_key_ref=SecretReference(name="key"),
            )
        assert "private_key_ref not allowed for keyless mode" in str(exc_info.value)

    @pytest.mark.requirement("8B-FR-001")
    def test_default_urls(self) -> None:
        """Test that Sigstore production URLs are defaults."""
        config = SigningConfig(
            mode="keyless",
            oidc_issuer=HttpUrl("https://example.com"),
        )
        assert "rekor.sigstore.io" in str(config.rekor_url)
        assert "fulcio.sigstore.dev" in str(config.fulcio_url)

    @pytest.mark.requirement("8B-FR-001")
    def test_custom_sigstore_urls(self) -> None:
        """Test that custom Sigstore URLs can be configured."""
        config = SigningConfig(
            mode="keyless",
            oidc_issuer=HttpUrl("https://example.com"),
            rekor_url=HttpUrl("https://rekor.internal.example.com"),
            fulcio_url=HttpUrl("https://fulcio.internal.example.com"),
        )
        assert "rekor.internal.example.com" in str(config.rekor_url)
        assert "fulcio.internal.example.com" in str(config.fulcio_url)

    @pytest.mark.requirement("8B-FR-001")
    def test_config_is_frozen(self) -> None:
        """Test that SigningConfig is immutable."""
        config = SigningConfig(
            mode="keyless",
            oidc_issuer=HttpUrl("https://example.com"),
        )
        with pytest.raises(ValidationError):
            config.mode = "key-based"  # type: ignore[misc]


class TestTrustedIssuerValidation:
    """Tests for TrustedIssuer validation rules."""

    @pytest.mark.requirement("8B-FR-009")
    def test_valid_with_subject(self) -> None:
        """Test that issuer with subject is valid."""
        issuer = TrustedIssuer(
            issuer=HttpUrl("https://token.actions.githubusercontent.com"),
            subject="repo:acme/floe:ref:refs/heads/main",
        )
        assert issuer.subject == "repo:acme/floe:ref:refs/heads/main"
        assert issuer.subject_regex is None

    @pytest.mark.requirement("8B-FR-009")
    def test_valid_with_subject_regex(self) -> None:
        """Test that issuer with subject_regex is valid."""
        issuer = TrustedIssuer(
            issuer=HttpUrl("https://token.actions.githubusercontent.com"),
            subject_regex=r"repo:acme/.*:ref:refs/heads/main",
        )
        assert issuer.subject is None
        assert issuer.subject_regex == r"repo:acme/.*:ref:refs/heads/main"

    @pytest.mark.requirement("8B-FR-009")
    def test_requires_subject_or_regex(self) -> None:
        """Test that either subject or subject_regex is required."""
        with pytest.raises(ValidationError) as exc_info:
            TrustedIssuer(
                issuer=HttpUrl("https://example.com"),
            )
        assert "Either subject or subject_regex required" in str(exc_info.value)

    @pytest.mark.requirement("8B-FR-009")
    def test_subject_and_regex_mutually_exclusive(self) -> None:
        """Test that subject and subject_regex are mutually exclusive."""
        with pytest.raises(ValidationError) as exc_info:
            TrustedIssuer(
                issuer=HttpUrl("https://example.com"),
                subject="exact-match",
                subject_regex="pattern.*",
            )
        assert "mutually exclusive" in str(exc_info.value)


class TestVerificationPolicyValidation:
    """Tests for VerificationPolicy validation rules (T012)."""

    @pytest.mark.requirement("8B-FR-009")
    def test_valid_with_trusted_issuers(self) -> None:
        """Test that policy with trusted issuers is valid."""
        policy = VerificationPolicy(
            enabled=True,
            enforcement="enforce",
            trusted_issuers=[
                TrustedIssuer(
                    issuer=HttpUrl("https://token.actions.githubusercontent.com"),
                    subject="repo:acme/floe:ref:refs/heads/main",
                )
            ],
        )
        assert policy.enabled
        assert policy.enforcement == "enforce"
        assert len(policy.trusted_issuers) == 1

    @pytest.mark.requirement("8B-FR-009")
    def test_valid_with_public_key(self) -> None:
        """Test that policy with public key is valid."""
        policy = VerificationPolicy(
            enabled=True,
            public_key_ref=SecretReference(name="cosign-pub"),
        )
        assert policy.public_key_ref is not None

    @pytest.mark.requirement("8B-FR-009")
    def test_enabled_requires_issuers_or_key(self) -> None:
        """Test that enabled policy requires trusted_issuers or public_key_ref."""
        with pytest.raises(ValidationError) as exc_info:
            VerificationPolicy(enabled=True)
        assert "At least one of trusted_issuers or public_key_ref required" in str(
            exc_info.value
        )

    @pytest.mark.requirement("8B-FR-009")
    def test_disabled_policy_valid_without_issuers(self) -> None:
        """Test that disabled policy doesn't require issuers."""
        policy = VerificationPolicy(enabled=False)
        assert not policy.enabled

    @pytest.mark.requirement("8B-FR-009")
    def test_enforcement_levels(self) -> None:
        """Test all enforcement levels are valid."""
        for level in ["enforce", "warn", "off"]:
            policy = VerificationPolicy(
                enabled=True,
                enforcement=level,  # type: ignore[arg-type]
                trusted_issuers=[
                    TrustedIssuer(
                        issuer=HttpUrl("https://example.com"),
                        subject="test",
                    )
                ],
            )
            assert policy.enforcement == level

    @pytest.mark.requirement("8B-FR-009")
    def test_per_environment_enforcement(self) -> None:
        """Test per-environment policy overrides."""
        policy = VerificationPolicy(
            enabled=True,
            enforcement="warn",
            trusted_issuers=[
                TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
            ],
            environments={
                "prod": EnvironmentPolicy(enforcement="enforce", require_sbom=True),
                "dev": EnvironmentPolicy(enforcement="off"),
            },
        )
        assert policy.get_enforcement_for_env("prod") == "enforce"
        assert policy.get_enforcement_for_env("dev") == "off"
        assert policy.get_enforcement_for_env("staging") == "warn"  # default

    @pytest.mark.requirement("8B-FR-009")
    def test_per_environment_sbom_requirement(self) -> None:
        """Test per-environment SBOM requirement overrides."""
        policy = VerificationPolicy(
            enabled=True,
            require_sbom=False,
            trusted_issuers=[
                TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
            ],
            environments={
                "prod": EnvironmentPolicy(enforcement="enforce", require_sbom=True),
            },
        )
        assert policy.get_require_sbom_for_env("prod") is True
        assert policy.get_require_sbom_for_env("dev") is False  # default

    @pytest.mark.requirement("8B-FR-012")
    def test_grace_period_default(self) -> None:
        """Test that grace period defaults to 7 days."""
        policy = VerificationPolicy(
            enabled=True,
            trusted_issuers=[
                TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
            ],
        )
        assert policy.grace_period_days == 7

    @pytest.mark.requirement("8B-FR-012")
    def test_grace_period_custom(self) -> None:
        """Test that grace period can be customized."""
        policy = VerificationPolicy(
            enabled=True,
            grace_period_days=14,
            trusted_issuers=[
                TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
            ],
        )
        assert policy.grace_period_days == 14

    @pytest.mark.requirement("8B-FR-012")
    def test_grace_period_validation(self) -> None:
        """Test that grace period has bounds (0-90)."""
        # Valid bounds
        for days in [0, 30, 90]:
            policy = VerificationPolicy(
                enabled=True,
                grace_period_days=days,
                trusted_issuers=[
                    TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
                ],
            )
            assert policy.grace_period_days == days

        # Invalid: negative
        with pytest.raises(ValidationError):
            VerificationPolicy(
                enabled=True,
                grace_period_days=-1,
                trusted_issuers=[
                    TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
                ],
            )

        # Invalid: too large
        with pytest.raises(ValidationError):
            VerificationPolicy(
                enabled=True,
                grace_period_days=91,
                trusted_issuers=[
                    TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
                ],
            )

    @pytest.mark.requirement("8B-FR-012")
    def test_is_within_grace_period(self) -> None:
        """Test grace period calculation for certificate rotation."""
        policy = VerificationPolicy(
            enabled=True,
            grace_period_days=7,
            trusted_issuers=[
                TrustedIssuer(issuer=HttpUrl("https://example.com"), subject="test")
            ],
        )

        now = datetime.now(timezone.utc)
        cert_expired_6_days_ago = now - timedelta(days=6)
        cert_expired_8_days_ago = now - timedelta(days=8)

        # Within grace period
        assert policy.is_within_grace_period(cert_expired_6_days_ago, now) is True
        # Outside grace period
        assert policy.is_within_grace_period(cert_expired_8_days_ago, now) is False


class TestSignatureMetadataSerialization:
    """Tests for SignatureMetadata annotation serialization (T013)."""

    @pytest.mark.requirement("8B-FR-011")
    def test_to_annotations_full(self) -> None:
        """Test serialization to OCI annotations with all fields."""
        metadata = SignatureMetadata(
            bundle="base64encodeddata==",
            mode="keyless",
            issuer="https://token.actions.githubusercontent.com",
            subject="repo:acme/floe:ref:refs/heads/main",
            signed_at=datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            rekor_log_index=12345678,
            certificate_fingerprint="sha256:abc123def456",
        )

        annotations = metadata.to_annotations()

        assert annotations["dev.floe.signature.bundle"] == "base64encodeddata=="
        assert annotations["dev.floe.signature.mode"] == "keyless"
        assert (
            annotations["dev.floe.signature.issuer"]
            == "https://token.actions.githubusercontent.com"
        )
        assert (
            annotations["dev.floe.signature.subject"]
            == "repo:acme/floe:ref:refs/heads/main"
        )
        assert "2026-01-15" in annotations["dev.floe.signature.signed-at"]
        assert annotations["dev.floe.signature.rekor-index"] == "12345678"
        assert (
            annotations["dev.floe.signature.cert-fingerprint"] == "sha256:abc123def456"
        )

    @pytest.mark.requirement("8B-FR-011")
    def test_to_annotations_minimal(self) -> None:
        """Test serialization without optional fields."""
        metadata = SignatureMetadata(
            bundle="data==",
            mode="key-based",
            subject="local-key",
            signed_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            certificate_fingerprint="sha256:xyz",
        )

        annotations = metadata.to_annotations()

        assert "dev.floe.signature.bundle" in annotations
        assert annotations["dev.floe.signature.mode"] == "key-based"
        assert "dev.floe.signature.issuer" not in annotations  # None
        assert "dev.floe.signature.rekor-index" not in annotations  # None

    @pytest.mark.requirement("8B-FR-011")
    def test_from_annotations_full(self) -> None:
        """Test parsing from OCI annotations with all fields."""
        annotations = {
            "dev.floe.signature.bundle": "base64data==",
            "dev.floe.signature.mode": "keyless",
            "dev.floe.signature.issuer": "https://example.com",
            "dev.floe.signature.subject": "test-subject",
            "dev.floe.signature.signed-at": "2026-01-15T10:30:00+00:00",
            "dev.floe.signature.rekor-index": "999",
            "dev.floe.signature.cert-fingerprint": "sha256:fingerprint",
        }

        metadata = SignatureMetadata.from_annotations(annotations)

        assert metadata is not None
        assert metadata.bundle == "base64data=="
        assert metadata.mode == "keyless"
        assert metadata.issuer == "https://example.com"
        assert metadata.subject == "test-subject"
        assert metadata.rekor_log_index == 999
        assert metadata.certificate_fingerprint == "sha256:fingerprint"

    @pytest.mark.requirement("8B-FR-011")
    def test_from_annotations_returns_none_if_unsigned(self) -> None:
        """Test that from_annotations returns None for unsigned artifacts."""
        annotations: dict[str, str] = {}  # No signature annotations
        metadata = SignatureMetadata.from_annotations(annotations)
        assert metadata is None

    @pytest.mark.requirement("8B-FR-011")
    def test_roundtrip_serialization(self) -> None:
        """Test that to_annotations and from_annotations are inverse."""
        original = SignatureMetadata(
            bundle="testbundle==",
            mode="keyless",
            issuer="https://issuer.example.com",
            subject="test@example.com",
            signed_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            rekor_log_index=42,
            certificate_fingerprint="sha256:abc",
        )

        annotations = original.to_annotations()
        restored = SignatureMetadata.from_annotations(annotations)

        assert restored is not None
        assert restored.bundle == original.bundle
        assert restored.mode == original.mode
        assert restored.issuer == original.issuer
        assert restored.subject == original.subject
        assert restored.rekor_log_index == original.rekor_log_index
        assert restored.certificate_fingerprint == original.certificate_fingerprint


class TestVerificationResult:
    """Tests for VerificationResult model."""

    @pytest.mark.requirement("8B-FR-004")
    def test_valid_result(self) -> None:
        """Test creating a valid verification result."""
        result = VerificationResult(
            status="valid",
            signer_identity="repo:acme/floe:ref:refs/heads/main",
            issuer="https://token.actions.githubusercontent.com",
            verified_at=datetime.now(timezone.utc),
            rekor_verified=True,
        )
        assert result.is_valid
        assert result.status == "valid"

    @pytest.mark.requirement("8B-FR-004")
    def test_invalid_result(self) -> None:
        """Test creating an invalid verification result."""
        result = VerificationResult(
            status="invalid",
            verified_at=datetime.now(timezone.utc),
            failure_reason="Signature mismatch",
        )
        assert not result.is_valid
        assert result.failure_reason == "Signature mismatch"

    @pytest.mark.requirement("8B-FR-004")
    def test_unsigned_result(self) -> None:
        """Test creating an unsigned verification result."""
        result = VerificationResult(
            status="unsigned",
            verified_at=datetime.now(timezone.utc),
            failure_reason="No signature found",
        )
        assert not result.is_valid
        assert result.status == "unsigned"


class TestAttestationManifest:
    """Tests for AttestationManifest (SBOM) model."""

    @pytest.mark.requirement("8B-FR-007")
    def test_valid_sbom_attestation(self) -> None:
        """Test creating a valid SBOM attestation."""
        attestation = AttestationManifest(
            predicate_type="https://spdx.dev/Document",
            predicate={
                "spdxVersion": "SPDX-2.3",
                "name": "test-sbom",
                "packages": [],
            },
            subject=[
                Subject(
                    name="oci://harbor.example.com/floe:v1.0.0",
                    digest={"sha256": "abc123"},
                )
            ],
        )
        assert attestation.predicate_type == "https://spdx.dev/Document"
        assert len(attestation.subject) == 1


class TestVerificationBundle:
    """Tests for VerificationBundle (offline verification) model."""

    @pytest.mark.requirement("8B-FR-015")
    def test_valid_bundle(self) -> None:
        """Test creating a valid verification bundle."""
        bundle = VerificationBundle(
            version="1.0",
            artifact_digest="sha256:abc123",
            sigstore_bundle={"messageSignature": {}},
            certificate_chain=["-----BEGIN CERTIFICATE-----\n..."],
            rekor_entry={"logIndex": "12345"},
            created_at=datetime.now(timezone.utc),
        )
        assert bundle.version == "1.0"
        assert bundle.artifact_digest == "sha256:abc123"

    @pytest.mark.requirement("8B-FR-015")
    def test_bundle_without_rekor(self) -> None:
        """Test bundle for key-based signing (no Rekor)."""
        bundle = VerificationBundle(
            artifact_digest="sha256:abc123",
            sigstore_bundle={"messageSignature": {}},
            certificate_chain=[],
            created_at=datetime.now(timezone.utc),
        )
        assert bundle.rekor_entry is None
