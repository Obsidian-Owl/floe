"""Artifact signing and verification schemas.

Implements:
    - FR-001: Cosign integration configuration
    - FR-009: Verification policy configuration
    - FR-011: Signature metadata in annotations
    - FR-012: Certificate rotation support
    - FR-013: Audit logging schemas
    - FR-015: Offline verification bundles

See Also:
    - specs/8b-artifact-signing/spec.md: Feature specification
    - specs/8b-artifact-signing/data-model.md: Data model specification
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from floe_core.schemas.secrets import SecretReference


class SigningConfig(BaseModel):
    """Configuration for artifact signing operations.

    Location: `manifest.yaml` at `artifacts.signing`

    Attributes:
        mode: Signing method (keyless for OIDC, key-based for private keys)
        oidc_issuer: OIDC provider URL (required for keyless mode)
        rekor_url: Rekor transparency log URL (default: production)
        fulcio_url: Fulcio CA URL (default: production)
        private_key_ref: Reference to private key (required for key-based mode)

    Example:
        >>> config = SigningConfig(mode="keyless", oidc_issuer="https://token.actions.githubusercontent.com")
        >>> config.mode
        'keyless'
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "mode": "keyless",
                    "oidc_issuer": "https://token.actions.githubusercontent.com",
                },
                {
                    "mode": "key-based",
                    "private_key_ref": {"source": "kubernetes", "name": "cosign-key"},
                },
            ]
        },
    )

    mode: Literal["keyless", "key-based"] = Field(
        description="Signing method: keyless (OIDC) or key-based (private key)"
    )
    oidc_issuer: HttpUrl | None = Field(
        default=None,
        description="OIDC provider URL for keyless signing",
    )
    rekor_url: HttpUrl = Field(
        default=HttpUrl("https://rekor.sigstore.io"),
        description="Rekor transparency log URL",
    )
    fulcio_url: HttpUrl = Field(
        default=HttpUrl("https://fulcio.sigstore.dev"),
        description="Fulcio CA URL for certificate issuance",
    )
    private_key_ref: SecretReference | None = Field(
        default=None,
        description="Reference to private key for key-based signing",
    )

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> SigningConfig:
        """Validate mode-specific field requirements."""
        if self.mode == "keyless" and not self.oidc_issuer:
            raise ValueError("oidc_issuer required for keyless mode")
        if self.mode == "key-based" and not self.private_key_ref:
            raise ValueError("private_key_ref required for key-based mode")
        if self.mode == "keyless" and self.private_key_ref:
            raise ValueError("private_key_ref not allowed for keyless mode")
        return self


class TrustedIssuer(BaseModel):
    """A trusted OIDC issuer for signature verification.

    Defines an allowed signer identity by OIDC issuer URL and subject.
    Either subject (exact match) or subject_regex (pattern) is required.

    Attributes:
        issuer: OIDC issuer URL (e.g., https://token.actions.githubusercontent.com)
        subject: Exact certificate subject to match
        subject_regex: Regex pattern for subject matching

    Example:
        >>> issuer = TrustedIssuer(
        ...     issuer="https://token.actions.githubusercontent.com",
        ...     subject="repo:acme/floe-platform:ref:refs/heads/main"
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issuer: HttpUrl = Field(description="OIDC issuer URL")
    subject: str | None = Field(
        default=None,
        description="Exact certificate subject to match",
    )
    subject_regex: str | None = Field(
        default=None,
        description="Regex pattern for subject matching",
    )

    @model_validator(mode="after")
    def validate_subject(self) -> TrustedIssuer:
        """Validate that exactly one of subject or subject_regex is provided."""
        if not self.subject and not self.subject_regex:
            raise ValueError("Either subject or subject_regex required")
        if self.subject and self.subject_regex:
            raise ValueError("subject and subject_regex are mutually exclusive")
        return self


class EnvironmentPolicy(BaseModel):
    """Per-environment verification policy override.

    Allows different enforcement levels per environment (dev/staging/prod).

    Attributes:
        enforcement: Override enforcement level for this environment
        require_sbom: Override SBOM requirement for this environment
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enforcement: Literal["enforce", "warn", "off"] = Field(description="Enforcement level override")
    require_sbom: bool | None = Field(
        default=None,
        description="Override SBOM requirement",
    )


class VerificationPolicy(BaseModel):
    """Policy for verifying artifact signatures.

    Location: `manifest.yaml` at `artifacts.verification`

    Attributes:
        enabled: Enable/disable signature verification
        enforcement: Default enforcement level
        trusted_issuers: List of trusted OIDC issuers
        require_rekor: Require transparency log entry
        require_sbom: Require SBOM attestation
        public_key_ref: Public key for key-based verification
        environments: Per-environment policy overrides
        grace_period_days: Days to accept expired certs during rotation

    Example:
        >>> policy = VerificationPolicy(
        ...     enabled=True,
        ...     enforcement="enforce",
        ...     trusted_issuers=[
        ...         TrustedIssuer(
        ...             issuer="https://token.actions.githubusercontent.com",
        ...             subject="repo:acme/floe:ref:refs/heads/main"
        ...         )
        ...     ]
        ... )
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "enabled": True,
                    "enforcement": "enforce",
                    "trusted_issuers": [
                        {
                            "issuer": "https://token.actions.githubusercontent.com",
                            "subject": "repo:acme/floe:ref:refs/heads/main",
                        }
                    ],
                }
            ]
        },
    )

    enabled: bool = Field(default=True, description="Enable signature verification")
    enforcement: Literal["enforce", "warn", "off"] = Field(
        default="warn",
        description="Enforcement level: enforce (fatal), warn (log), off (skip)",
    )
    trusted_issuers: list[TrustedIssuer] = Field(
        default_factory=list,
        description="List of trusted OIDC issuers",
    )
    require_rekor: bool = Field(
        default=True,
        description="Require Rekor transparency log entry",
    )
    require_sbom: bool = Field(
        default=False,
        description="Require SBOM attestation",
    )
    public_key_ref: SecretReference | None = Field(
        default=None,
        description="Public key for key-based verification",
    )
    environments: dict[str, EnvironmentPolicy] = Field(
        default_factory=dict,
        description="Per-environment policy overrides",
    )
    grace_period_days: Annotated[int, Field(ge=0, le=90)] = Field(
        default=7,
        description="Days to accept expired certs during rotation (FR-012)",
    )

    @model_validator(mode="after")
    def validate_verification_config(self) -> VerificationPolicy:
        """Validate verification configuration."""
        if self.enabled and not self.trusted_issuers and not self.public_key_ref:
            raise ValueError(
                "At least one of trusted_issuers or public_key_ref required when enabled"
            )
        return self

    def get_enforcement_for_env(self, env: str) -> Literal["enforce", "warn", "off"]:
        """Get effective enforcement level for an environment."""
        if env in self.environments:
            return self.environments[env].enforcement
        return self.enforcement

    def get_require_sbom_for_env(self, env: str) -> bool:
        """Get effective SBOM requirement for an environment."""
        if env in self.environments:
            env_policy = self.environments[env]
            if env_policy.require_sbom is not None:
                return env_policy.require_sbom
        return self.require_sbom

    def is_within_grace_period(
        self, cert_expired_at: datetime, now: datetime | None = None
    ) -> bool:
        """Check if expired cert is within rotation grace period (FR-012)."""
        if now is None:
            now = datetime.now(cert_expired_at.tzinfo)
        grace_end = cert_expired_at + timedelta(days=self.grace_period_days)
        return now <= grace_end


class SignatureMetadata(BaseModel):
    """Signature metadata stored in OCI artifact annotations.

    Attributes:
        bundle: Base64-encoded Sigstore bundle JSON
        mode: Signing mode used
        issuer: OIDC issuer URL (keyless only)
        subject: Certificate subject / signer identity
        signed_at: Signing timestamp
        rekor_log_index: Rekor transparency log index
        certificate_fingerprint: SHA256 of signing certificate
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle: str = Field(description="Base64-encoded Sigstore bundle")
    mode: Literal["keyless", "key-based"] = Field(description="Signing mode used")
    issuer: str | None = Field(default=None, description="OIDC issuer (keyless only)")
    subject: str = Field(description="Certificate subject / signer identity")
    signed_at: datetime = Field(description="Signing timestamp")
    rekor_log_index: int | None = Field(default=None, description="Rekor transparency log index")
    certificate_fingerprint: str = Field(description="SHA256 fingerprint of signing certificate")

    def to_annotations(self) -> dict[str, str]:
        """Convert to OCI annotation dict."""
        annotations = {
            "dev.floe.signature.bundle": self.bundle,
            "dev.floe.signature.mode": self.mode,
            "dev.floe.signature.subject": self.subject,
            "dev.floe.signature.signed-at": self.signed_at.isoformat(),
            "dev.floe.signature.cert-fingerprint": self.certificate_fingerprint,
        }
        if self.issuer:
            annotations["dev.floe.signature.issuer"] = self.issuer
        if self.rekor_log_index is not None:
            annotations["dev.floe.signature.rekor-index"] = str(self.rekor_log_index)
        return annotations

    @classmethod
    def from_annotations(cls, annotations: dict[str, str]) -> SignatureMetadata | None:
        """Parse from OCI annotations, returns None if not signed."""
        bundle = annotations.get("dev.floe.signature.bundle")
        if not bundle:
            return None

        mode_str = annotations.get("dev.floe.signature.mode", "keyless")
        if mode_str not in ("keyless", "key-based"):
            mode_str = "keyless"

        rekor_index_str = annotations.get("dev.floe.signature.rekor-index")
        rekor_index = int(rekor_index_str) if rekor_index_str else None

        return cls(
            bundle=bundle,
            mode=mode_str,  # type: ignore[arg-type]
            issuer=annotations.get("dev.floe.signature.issuer"),
            subject=annotations.get("dev.floe.signature.subject", ""),
            signed_at=datetime.fromisoformat(
                annotations.get("dev.floe.signature.signed-at", "1970-01-01T00:00:00")
            ),
            rekor_log_index=rekor_index,
            certificate_fingerprint=annotations.get("dev.floe.signature.cert-fingerprint", ""),
        )


class VerificationResult(BaseModel):
    """Result of signature verification operation.

    Attributes:
        status: Verification status (VALID, INVALID, UNSIGNED, UNKNOWN)
        signer_identity: Verified signer identity
        issuer: OIDC issuer if keyless
        verified_at: Verification timestamp
        rekor_verified: Transparency log verified
        certificate_chain: Certificate chain (PEM)
        failure_reason: Reason if verification failed
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["valid", "invalid", "unsigned", "unknown"] = Field(
        description="Verification status"
    )
    signer_identity: str | None = Field(default=None, description="Verified signer identity")
    issuer: str | None = Field(default=None, description="OIDC issuer if keyless")
    verified_at: datetime = Field(description="Verification timestamp")
    rekor_verified: bool = Field(default=False, description="Transparency log verified")
    certificate_chain: list[str] = Field(
        default_factory=list, description="Certificate chain (PEM)"
    )
    failure_reason: str | None = Field(default=None, description="Reason if verification failed")
    certificate_expired_at: datetime | None = Field(
        default=None, description="Certificate expiration time (FR-012 grace period)"
    )
    within_grace_period: bool = Field(
        default=False, description="True if expired cert accepted via grace period (FR-012)"
    )

    @property
    def is_valid(self) -> bool:
        """Check if verification succeeded."""
        return self.status == "valid"


class Subject(BaseModel):
    """Subject of an attestation (artifact reference)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Artifact reference")
    digest: dict[str, str] = Field(description="Digest map (sha256 -> value)")


class AttestationManifest(BaseModel):
    """SBOM or provenance attestation attached to artifact.

    Follows in-toto attestation format.

    Attributes:
        predicate_type: Attestation type URI
        predicate: Attestation payload (SBOM content)
        subject: Artifacts this attestation covers
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    predicate_type: str = Field(description="Attestation type (e.g., https://spdx.dev/Document)")
    predicate: dict[str, object] = Field(description="Attestation payload")
    subject: list[Subject] = Field(description="Artifacts this attestation covers")


class SigningAuditEvent(BaseModel):
    """Structured audit log for signing operations (FR-013)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: Literal["signing"] = Field(default="signing")
    artifact_ref: str = Field(description="Full OCI artifact reference")
    artifact_digest: str = Field(description="SHA256 digest of artifact")
    signing_mode: Literal["keyless", "key-based"] = Field(description="Mode used")
    signer_identity: str = Field(description="Certificate subject / signer ID")
    issuer: str | None = Field(default=None, description="OIDC issuer (keyless only)")
    rekor_log_index: int | None = Field(default=None, description="Rekor log entry")
    timestamp: datetime = Field(description="Operation timestamp")
    trace_id: str = Field(description="W3C trace context ID")
    span_id: str = Field(description="W3C span ID")
    success: bool = Field(description="Operation succeeded")
    error: str | None = Field(default=None, description="Error message if failed")


class VerificationAuditEvent(BaseModel):
    """Structured audit log for verification operations (FR-013)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: Literal["verification"] = Field(default="verification")
    artifact_ref: str = Field(description="Full OCI artifact reference")
    artifact_digest: str = Field(description="SHA256 digest of artifact")
    policy_enforcement: Literal["enforce", "warn", "off"] = Field(
        description="Active enforcement level"
    )
    environment: str | None = Field(default=None, description="Environment context")
    expected_issuers: list[str] = Field(
        default_factory=list, description="Configured trusted issuers"
    )
    actual_issuer: str | None = Field(default=None, description="Actual signer issuer")
    actual_subject: str | None = Field(default=None, description="Actual signer identity")
    signature_status: Literal["valid", "invalid", "unsigned", "unknown"] = Field(
        description="Verification result status"
    )
    rekor_verified: bool = Field(description="Transparency log checked")
    timestamp: datetime = Field(description="Operation timestamp")
    trace_id: str = Field(description="W3C trace context ID")
    span_id: str = Field(description="W3C span ID")
    success: bool = Field(description="Verification passed")
    failure_reason: str | None = Field(default=None, description="Reason if verification failed")


class VerificationBundle(BaseModel):
    """Offline bundle for air-gapped verification (FR-015).

    Contains all materials needed to verify a signature without network access.

    Attributes:
        version: Bundle format version
        artifact_digest: SHA256 of signed artifact
        sigstore_bundle: Full Sigstore bundle JSON
        certificate_chain: PEM-encoded cert chain
        rekor_entry: Rekor log entry (if available)
        created_at: Bundle creation timestamp
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal["1.0"] = Field(default="1.0", description="Bundle format version")
    artifact_digest: str = Field(description="SHA256 of signed artifact")
    sigstore_bundle: dict[str, object] = Field(description="Full Sigstore bundle JSON")
    certificate_chain: list[str] = Field(description="PEM-encoded cert chain")
    rekor_entry: dict[str, object] | None = Field(default=None, description="Rekor log entry")
    created_at: datetime = Field(description="Bundle creation timestamp")


__all__ = [
    "SigningConfig",
    "TrustedIssuer",
    "EnvironmentPolicy",
    "VerificationPolicy",
    "SignatureMetadata",
    "VerificationResult",
    "Subject",
    "AttestationManifest",
    "SigningAuditEvent",
    "VerificationAuditEvent",
    "VerificationBundle",
]
