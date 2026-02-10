"""Artifact signature verification using Sigstore.

Implements:
    - FR-009: Verification policy configuration
    - FR-010: Identity policy matching (issuer + subject)
    - FR-011: Rekor transparency log verification
    - FR-015: Key-based verification for air-gapped environments
    - SC-007: OpenTelemetry tracing for verification operations
    - FR-013: Audit logging for verification attempts

This module provides signature verification for OCI artifacts using sigstore-python.
It supports keyless verification (OIDC-based) with identity policy matching, and
key-based verification for air-gapped environments using cosign CLI.

Example:
    >>> from floe_core.oci.verification import VerificationClient
    >>> from floe_core.schemas.signing import VerificationPolicy, TrustedIssuer
    >>>
    >>> # Configure verification policy
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
    >>> client = VerificationClient(policy)
    >>> result = client.verify(content, signature_metadata, artifact_ref="oci://...")

See Also:
    - specs/8b-artifact-signing/spec.md: Feature specification
    - specs/8b-artifact-signing/research.md: sigstore-python verification patterns
"""

from __future__ import annotations

import base64
import json
import logging
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse, urlunparse

from opentelemetry import trace

from floe_core.oci.errors import SignatureVerificationError
from floe_core.schemas.signing import (
    SignatureMetadata,
    TrustedIssuer,
    VerificationAuditEvent,
    VerificationBundle,
    VerificationPolicy,
    VerificationResult,
)
from floe_core.telemetry.sanitization import sanitize_error_message

if TYPE_CHECKING:
    from sigstore.models import Bundle
    from sigstore.verify import Verifier

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def _normalize_issuer(issuer_url: str) -> str:
    parsed = urlparse(issuer_url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    elif scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]

    path = parsed.path.rstrip("/") or ""

    return urlunparse((scheme, netloc, path, "", "", ""))


MAX_BUNDLE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit for Sigstore bundles
MAX_SUBJECT_LENGTH = 1024  # Max subject length for regex matching (ReDoS protection)

# Security: Allowed key file extensions
_ALLOWED_KEY_EXTENSIONS = frozenset({".key", ".pem", ".pub", ".crt", ".cert"})

# Security: Regex pattern for validating key reference names
_VALID_KEY_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _decode_bundle_with_size_limit(bundle_b64: str, max_size: int = MAX_BUNDLE_SIZE_BYTES) -> str:
    """Decode base64 bundle with size limit to prevent memory exhaustion.

    Args:
        bundle_b64: Base64-encoded bundle string
        max_size: Maximum allowed decoded size in bytes

    Returns:
        Decoded UTF-8 string

    Raises:
        ValueError: If bundle exceeds size limit or is malformed
    """
    estimated_decoded_size = len(bundle_b64) * 3 // 4
    if estimated_decoded_size > max_size:
        raise ValueError(
            f"Bundle size (estimated {estimated_decoded_size} bytes) "
            f"exceeds limit ({max_size} bytes)"
        )

    try:
        bundle_bytes = base64.b64decode(bundle_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}") from e

    if len(bundle_bytes) > max_size:
        raise ValueError(
            f"Bundle size ({len(bundle_bytes)} bytes) exceeds limit ({max_size} bytes)"
        )

    try:
        return bundle_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(f"Bundle is not valid UTF-8: {e}") from e


class VerificationError(Exception):
    """Base exception for verification operations."""

    pass


class PolicyViolationError(VerificationError):
    """Raised when signature doesn't match verification policy."""

    def __init__(
        self,
        reason: str,
        expected_issuer: str | None = None,
        expected_subject: str | None = None,
        actual_issuer: str | None = None,
        actual_subject: str | None = None,
    ) -> None:
        self.reason = reason
        self.expected_issuer = expected_issuer
        self.expected_subject = expected_subject
        self.actual_issuer = actual_issuer
        self.actual_subject = actual_subject
        super().__init__(reason)


class CosignNotAvailableError(VerificationError):
    """Raised when cosign CLI is not available for key-based verification."""

    def __init__(self) -> None:
        super().__init__(
            "cosign CLI not found. Key-based verification requires cosign. "
            "Install with: brew install cosign (macOS) or "
            "https://github.com/sigstore/cosign#installation"
        )


class KeyVerificationError(VerificationError):
    """Raised when key-based signature verification fails."""

    def __init__(self, reason: str, key_ref: str | None = None) -> None:
        self.reason = reason
        self.key_ref = key_ref
        msg = f"Key-based verification failed: {reason}"
        if key_ref:
            msg += f" (key: {key_ref})"
        super().__init__(msg)


def check_cosign_available() -> bool:
    """Check if cosign CLI is available on PATH."""
    return shutil.which("cosign") is not None


class VerificationClient:
    """Client for verifying artifact signatures using Sigstore.

    Supports keyless (OIDC) verification with identity policy matching.
    Verifies signatures against configured trusted issuers and subjects.

    Attributes:
        policy: VerificationPolicy with trusted issuers and enforcement settings
        environment: Optional environment name for per-env policy overrides

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
        >>> client = VerificationClient(policy)
        >>> result = client.verify(content, metadata, "oci://registry/repo:tag")
    """

    def __init__(
        self,
        policy: VerificationPolicy,
        environment: str | None = None,
    ) -> None:
        """Initialize VerificationClient.

        Args:
            policy: Verification policy from manifest.yaml
            environment: Environment name for per-env policy overrides
        """
        self.policy = policy
        self.environment = environment
        self._verifier: Verifier | None = None

    @property
    def enforcement(self) -> Literal["enforce", "warn", "off"]:
        """Get effective enforcement level for current environment."""
        if self.environment:
            return self.policy.get_enforcement_for_env(self.environment)
        return self.policy.enforcement

    @property
    def require_sbom(self) -> bool:
        """Get effective SBOM requirement for current environment."""
        if self.environment:
            return self.policy.get_require_sbom_for_env(self.environment)
        return self.policy.require_sbom

    @property
    def is_enabled(self) -> bool:
        """Check if verification is enabled."""
        return self.policy.enabled and self.enforcement != "off"

    def verify(
        self,
        content: bytes,
        metadata: SignatureMetadata | None,
        artifact_ref: str,
        artifact_digest: str | None = None,
    ) -> VerificationResult:
        """Verify artifact signature against policy.

        Args:
            content: Raw artifact bytes to verify
            metadata: SignatureMetadata from OCI annotations (None if unsigned)
            artifact_ref: Full OCI artifact reference (for logging/tracing)
            artifact_digest: SHA256 digest of artifact (for audit logging)

        Returns:
            VerificationResult with status and signer information

        Raises:
            SignatureVerificationError: If enforcement="enforce" and verification fails
        """
        with tracer.start_as_current_span("floe.oci.verify") as span:
            span.set_attribute("floe.artifact.ref", artifact_ref)
            span.set_attribute("floe.verification.enforcement", self.enforcement)
            if self.environment:
                span.set_attribute("floe.verification.environment", self.environment)

            # Handle unsigned artifacts
            if metadata is None:
                return self._handle_unsigned(artifact_ref, artifact_digest)

            # Verify the signature
            try:
                result = self._verify_signature(content, metadata, artifact_ref)
                span.set_attribute("floe.verification.status", result.status)

                if result.is_valid and self.require_sbom:
                    sbom_result = self._verify_sbom_present(artifact_ref, span)
                    if sbom_result is not None:
                        result = sbom_result

                # Log audit event
                self._log_audit_event(
                    artifact_ref=artifact_ref,
                    artifact_digest=artifact_digest or "",
                    result=result,
                    success=result.is_valid,
                )

                # Handle enforcement
                if not result.is_valid:
                    self._handle_verification_failure(result, artifact_ref)

                return result

            except Exception as e:
                sanitized_msg = sanitize_error_message(str(e))
                span.set_attribute("exception.type", type(e).__name__)
                span.set_attribute("exception.message", sanitized_msg)
                span.set_status(trace.Status(trace.StatusCode.ERROR, sanitized_msg))

                # Create failure result
                result = VerificationResult(
                    status="invalid",
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=str(e),
                )

                # Log audit event
                self._log_audit_event(
                    artifact_ref=artifact_ref,
                    artifact_digest=artifact_digest or "",
                    result=result,
                    success=False,
                )

                self._handle_verification_failure(result, artifact_ref)
                return result

    def _verify_signature(
        self,
        content: bytes,
        metadata: SignatureMetadata,
        artifact_ref: str,
    ) -> VerificationResult:
        """Verify signature using appropriate method based on signing mode.

        Routes to keyless (sigstore-python) or key-based (cosign CLI) verification
        based on the signature metadata mode.

        Args:
            content: Artifact bytes
            metadata: Signature metadata with bundle
            artifact_ref: Artifact reference for logging

        Returns:
            VerificationResult with verification status
        """
        if metadata.mode == "key-based":
            return self._verify_key_based(content, metadata, artifact_ref)
        return self._verify_keyless(content, metadata, artifact_ref)

    def _verify_keyless(
        self,
        content: bytes,
        metadata: SignatureMetadata,
        artifact_ref: str,
    ) -> VerificationResult:
        """Verify keyless (OIDC) signature using sigstore-python.

        Args:
            content: Artifact bytes
            metadata: Signature metadata with bundle
            artifact_ref: Artifact reference for logging

        Returns:
            VerificationResult with verification status
        """
        from sigstore.models import Bundle
        from sigstore.verify import Verifier
        from sigstore.verify.policy import Identity

        with tracer.start_as_current_span("floe.oci.verify.bundle"):
            try:
                bundle_json = _decode_bundle_with_size_limit(metadata.bundle)
                bundle = Bundle.from_json(bundle_json)
            except ValueError as e:
                logger.error("Failed to decode Sigstore bundle: %s", e)
                return VerificationResult(
                    status="invalid",
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=f"Invalid Sigstore bundle: {e}",
                )
            except Exception as e:
                logger.error("Failed to parse Sigstore bundle: %s", e)
                return VerificationResult(
                    status="invalid",
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=f"Invalid Sigstore bundle: {e}",
                )

        if self._verifier is None:
            offline = not self.policy.require_rekor
            self._verifier = Verifier.production(offline=offline)
        verifier = self._verifier

        with tracer.start_as_current_span("floe.oci.verify.policy"):
            matched_issuer = self._match_trusted_issuer(metadata)
            if matched_issuer is None:
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    issuer=metadata.issuer,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason="Signer not in trusted issuers list",
                )

            identity = Identity(
                identity=matched_issuer.subject or matched_issuer.subject_regex or "",
                issuer=str(matched_issuer.issuer),
            )

        span_name = (
            "floe.oci.verify.rekor" if self.policy.require_rekor else "floe.oci.verify.offline"
        )
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("floe.verification.offline", not self.policy.require_rekor)
            try:
                verifier.verify_artifact(
                    input_=content,
                    bundle=bundle,
                    policy=identity,
                )

                rekor_verified = self._check_rekor_entry(bundle)

                if self.policy.require_rekor and not rekor_verified:
                    return VerificationResult(
                        status="invalid",
                        signer_identity=metadata.subject,
                        issuer=metadata.issuer,
                        verified_at=datetime.now(timezone.utc),
                        rekor_verified=False,
                        failure_reason="Rekor transparency log entry required but not found",
                    )

                return VerificationResult(
                    status="valid",
                    signer_identity=metadata.subject,
                    issuer=metadata.issuer,
                    verified_at=datetime.now(timezone.utc),
                    rekor_verified=rekor_verified,
                )

            except Exception as e:
                # FR-012: Check if failure is due to expired cert within grace period
                if self._is_certificate_expired_error(e):
                    cert_expiry = self._get_certificate_expiration(bundle)
                    if cert_expiry and self.policy.is_within_grace_period(cert_expiry):
                        logger.warning(
                            "Certificate expired but within grace period: %s (expires: %s)",
                            artifact_ref,
                            cert_expiry.isoformat(),
                        )
                        span.set_attribute("floe.verification.grace_period", True)
                        span.set_attribute(
                            "floe.verification.cert_expired_at", cert_expiry.isoformat()
                        )
                        rekor_verified = self._check_rekor_entry(bundle)
                        return VerificationResult(
                            status="valid",
                            signer_identity=metadata.subject,
                            issuer=metadata.issuer,
                            verified_at=datetime.now(timezone.utc),
                            rekor_verified=rekor_verified,
                            certificate_expired_at=cert_expiry,
                            within_grace_period=True,
                        )

                logger.error("Signature verification failed: %s", e)
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    issuer=metadata.issuer,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=str(e),
                )

    def _verify_key_based(
        self,
        content: bytes,
        metadata: SignatureMetadata,
        artifact_ref: str,
    ) -> VerificationResult:
        """Verify key-based signature using cosign CLI.

        Used for air-gapped environments where signatures are created with
        private keys instead of OIDC identity.

        Args:
            content: Artifact bytes
            metadata: Signature metadata with signature bundle
            artifact_ref: Artifact reference for logging

        Returns:
            VerificationResult with verification status
        """
        with tracer.start_as_current_span("floe.oci.verify.key_based") as span:
            if not check_cosign_available():
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason="cosign CLI not available for key-based verification",
                )

            public_key_ref = self._resolve_public_key_ref()
            if public_key_ref is None:
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason="No public_key_ref configured for key-based verification",
                )

            span.set_attribute("floe.verification.key_ref", public_key_ref[:50])

            try:
                bundle_json = _decode_bundle_with_size_limit(metadata.bundle)
                bundle_data = json.loads(bundle_json)
            except json.JSONDecodeError as e:
                logger.error("Failed to parse signature bundle JSON: %s", e)
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=f"Invalid signature bundle JSON: {e}",
                )
            except ValueError as e:
                logger.error("Failed to decode signature bundle: %s", e)
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=f"Invalid signature bundle: {e}",
                )

            verification_success = self._cosign_verify_blob(content, bundle_data, public_key_ref)

            if verification_success:
                return VerificationResult(
                    status="valid",
                    signer_identity=metadata.subject,
                    verified_at=datetime.now(timezone.utc),
                    rekor_verified=False,
                )
            else:
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason="Signature verification failed",
                )

    def _resolve_public_key_ref(self) -> str | None:
        """Resolve public key reference from policy configuration.

        Returns:
            Public key path or KMS URI, or None if not configured
        """
        if self.policy.public_key_ref is None:
            return None

        key_ref = self.policy.public_key_ref

        if key_ref.source.value == "file":
            key_path = Path(key_ref.name).resolve()
            if key_path.suffix.lower() not in _ALLOWED_KEY_EXTENSIONS:
                logger.error(
                    "Invalid key file extension: %s. Allowed: %s",
                    key_path.suffix,
                    ", ".join(sorted(_ALLOWED_KEY_EXTENSIONS)),
                )
                return None
            if not key_path.exists():
                logger.error("Public key file not found: %s", key_path)
                return None
            return str(key_path)

        if key_ref.source.value == "env":
            import os

            if not _VALID_KEY_NAME_PATTERN.match(key_ref.name):
                logger.error(
                    "Invalid key name format: %s. "
                    "Must contain only alphanumeric, hyphens, underscores.",
                    key_ref.name,
                )
                return None
            env_var_name = f"FLOE_{key_ref.name.upper().replace('-', '_')}"
            env_value = os.environ.get(env_var_name)
            if not env_value:
                logger.error("Environment variable not set: %s", env_var_name)
                return None
            return env_value

        if key_ref.source.value == "kubernetes":
            logger.error("Kubernetes secret references not yet supported for verification")
            return None

        logger.error("Unsupported key source: %s", key_ref.source.value)
        return None

    def _cosign_verify_blob(
        self,
        content: bytes,
        bundle_data: dict[str, Any],
        public_key_ref: str,
    ) -> bool:
        """Verify signature using cosign verify-blob CLI.

        Args:
            content: Original content bytes
            bundle_data: Signature bundle from signing
            public_key_ref: Public key path or KMS URI

        Returns:
            True if verification succeeded, False otherwise
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            content_file = tmpdir_path / "content.bin"
            signature_file = tmpdir_path / "signature.sig"

            content_file.write_bytes(content)

            signature_b64 = bundle_data.get("base64Signature")
            if signature_b64 is None:
                sig_content = bundle_data.get("dsseEnvelope", {}).get("signature")
                if sig_content:
                    signature_b64 = sig_content

            if signature_b64 is None:
                logger.error("No signature found in bundle")
                return False

            signature_file.write_text(signature_b64)

            cmd = [
                "cosign",
                "verify-blob",
                "--key",
                public_key_ref,
                "--signature",
                str(signature_file),
                str(content_file),
            ]

            logger.debug("Running cosign verify-blob: %s", " ".join(cmd[:5]) + " ...")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )

                if result.returncode == 0:
                    logger.debug("Key-based signature verification succeeded")
                    return True
                else:
                    logger.error("cosign verify-blob failed: %s", result.stderr)
                    return False

            except subprocess.TimeoutExpired:
                logger.error("cosign verify-blob timed out after 60 seconds")
                return False
            except Exception as e:
                logger.error("cosign verify-blob error: %s", e)
                return False

    def _match_trusted_issuer(self, metadata: SignatureMetadata) -> TrustedIssuer | None:
        """Match signature against trusted issuers.

        Args:
            metadata: Signature metadata with issuer and subject

        Returns:
            Matching TrustedIssuer or None if no match
        """
        for trusted in self.policy.trusted_issuers:
            if metadata.issuer:
                if _normalize_issuer(str(trusted.issuer)) != _normalize_issuer(metadata.issuer):
                    continue

            if trusted.subject:
                if trusted.subject == metadata.subject:
                    return trusted
            elif trusted.subject_regex:
                if len(metadata.subject) > MAX_SUBJECT_LENGTH:
                    logger.warning(
                        "Subject too long for regex matching (%d > %d), skipping",
                        len(metadata.subject),
                        MAX_SUBJECT_LENGTH,
                    )
                    continue
                try:
                    if re.match(trusted.subject_regex, metadata.subject):
                        return trusted
                except re.error:
                    logger.warning("Invalid regex in trusted issuer: %s", trusted.subject_regex)
                    continue

        return None

    def _check_rekor_entry(self, bundle: Bundle) -> bool:
        """Check if bundle contains valid Rekor transparency log entry.

        Args:
            bundle: Sigstore bundle to check

        Returns:
            True if Rekor entry exists and is valid
        """
        try:
            bundle_json = json.loads(bundle.to_json())
            verification_material = bundle_json.get("verificationMaterial", {})
            tlog_entries = verification_material.get("tlogEntries", [])
            return len(tlog_entries) > 0
        except Exception:
            return False

    def _get_certificate_expiration(self, bundle: Bundle) -> datetime | None:
        """Extract certificate expiration time from Sigstore bundle.

        Used for grace period calculations during certificate rotation (FR-012).

        Args:
            bundle: Sigstore bundle containing signing certificate

        Returns:
            Certificate not_valid_after timestamp, or None if cannot be extracted
        """
        try:
            # sigstore.models.Bundle exposes signing_certificate property
            cert = bundle.signing_certificate
            if cert is not None:
                return cert.not_valid_after_utc
        except Exception as e:
            logger.debug("Could not extract certificate expiration: %s", e)
        return None

    def _is_certificate_expired_error(self, error: Exception) -> bool:
        """Check if verification error is due to certificate expiration.

        Args:
            error: Exception from verification

        Returns:
            True if error indicates certificate expiration
        """
        error_msg = str(error).lower()
        expiration_indicators = [
            "expired",
            "not valid after",
            "certificate validity",
            "cert validity",
            "invalid signing cert",
        ]
        return any(indicator in error_msg for indicator in expiration_indicators)

    def _verify_sbom_present(
        self,
        artifact_ref: str,
        span: Any,
    ) -> VerificationResult | None:
        """Verify that artifact has SBOM attestation if required.

        Args:
            artifact_ref: Artifact reference to check
            span: OTel span for tracing

        Returns:
            VerificationResult with failure if SBOM missing, None if SBOM present
        """
        from floe_core.oci.attestation import retrieve_sbom

        span.set_attribute("floe.verification.require_sbom", True)

        try:
            sbom = retrieve_sbom(artifact_ref)
            if sbom is None:
                span.set_attribute("floe.verification.sbom_present", False)
                logger.warning(
                    "SBOM attestation required but not found: %s",
                    artifact_ref,
                )
                return VerificationResult(
                    status="invalid",
                    verified_at=datetime.now(timezone.utc),
                    failure_reason="SBOM attestation required but not found",
                )

            span.set_attribute("floe.verification.sbom_present", True)
            logger.debug("SBOM attestation verified: %s", artifact_ref)
            return None

        except Exception as e:
            logger.error("Failed to retrieve SBOM attestation: %s", e)
            return VerificationResult(
                status="invalid",
                verified_at=datetime.now(timezone.utc),
                failure_reason=f"Failed to verify SBOM attestation: {e}",
            )

    def _handle_unsigned(
        self,
        artifact_ref: str,
        artifact_digest: str | None,
    ) -> VerificationResult:
        """Handle unsigned artifact based on enforcement level.

        Args:
            artifact_ref: Artifact reference for error messages
            artifact_digest: Artifact digest for audit logging

        Returns:
            VerificationResult with unsigned status

        Raises:
            SignatureVerificationError: If enforcement="enforce"
        """
        result = VerificationResult(
            status="unsigned",
            verified_at=datetime.now(timezone.utc),
            failure_reason="Artifact is not signed",
        )

        # Log audit event
        self._log_audit_event(
            artifact_ref=artifact_ref,
            artifact_digest=artifact_digest or "",
            result=result,
            success=False,
        )

        self._handle_verification_failure(result, artifact_ref)
        return result

    def _handle_verification_failure(
        self,
        result: VerificationResult,
        artifact_ref: str,
    ) -> None:
        """Handle verification failure based on enforcement level.

        Args:
            result: Verification result with failure details
            artifact_ref: Artifact reference for error messages

        Raises:
            SignatureVerificationError: If enforcement="enforce"
        """
        if result.is_valid:
            return

        if self.enforcement == "enforce":
            raise SignatureVerificationError(
                artifact_ref=artifact_ref,
                reason=result.failure_reason or "Verification failed",
                expected_signer=self._format_expected_signers(),
                actual_signer=result.signer_identity,
            )
        elif self.enforcement == "warn":
            logger.warning(
                "Signature verification failed for %s: %s (enforcement=warn, continuing)",
                artifact_ref,
                result.failure_reason,
            )

    def _format_expected_signers(self) -> str:
        """Format expected signers for error messages."""
        signers = []
        for issuer in self.policy.trusted_issuers:
            subject = issuer.subject or issuer.subject_regex or "*"
            signers.append(f"{issuer.issuer}:{subject}")
        return ", ".join(signers) if signers else "none configured"

    def _log_audit_event(
        self,
        artifact_ref: str,
        artifact_digest: str,
        result: VerificationResult,
        success: bool,
    ) -> None:
        """Log structured audit event for verification attempt.

        Args:
            artifact_ref: Artifact reference
            artifact_digest: Artifact SHA256 digest
            result: Verification result
            success: Whether verification passed
        """
        span = trace.get_current_span()
        span_context = span.get_span_context()

        audit_event = VerificationAuditEvent(
            artifact_ref=artifact_ref,
            artifact_digest=artifact_digest,
            policy_enforcement=self.enforcement,
            environment=self.environment,
            expected_issuers=[str(i.issuer) for i in self.policy.trusted_issuers],
            actual_issuer=result.issuer,
            actual_subject=result.signer_identity,
            signature_status=result.status,
            rekor_verified=result.rekor_verified,
            timestamp=datetime.now(timezone.utc),
            trace_id=(format(span_context.trace_id, "032x") if span_context.is_valid else ""),
            span_id=(format(span_context.span_id, "016x") if span_context.is_valid else ""),
            success=success,
            failure_reason=result.failure_reason,
        )

        # Log as structured JSON
        logger.info(
            "Verification audit: %s",
            audit_event.model_dump_json(),
            extra={"audit_event": audit_event.model_dump()},
        )


def verify_artifact(
    content: bytes,
    metadata: SignatureMetadata | None,
    artifact_ref: str,
    policy: VerificationPolicy,
    environment: str | None = None,
) -> VerificationResult:
    """Convenience function to verify an artifact signature.

    Args:
        content: Artifact bytes to verify
        metadata: Signature metadata from OCI annotations
        artifact_ref: OCI artifact reference
        policy: Verification policy
        environment: Optional environment for per-env policy

    Returns:
        VerificationResult with verification status
    """
    client = VerificationClient(policy, environment)
    return client.verify(content, metadata, artifact_ref)


def export_verification_bundle(
    artifact_digest: str,
    metadata: SignatureMetadata,
) -> VerificationBundle:
    """Export offline verification bundle for air-gapped environments (FR-015).

    Creates a self-contained bundle with all materials needed to verify
    a signature without network access to Sigstore/Rekor.

    Args:
        artifact_digest: SHA256 digest of the signed artifact
        metadata: Signature metadata containing the Sigstore bundle

    Returns:
        VerificationBundle with sigstore bundle, cert chain, and Rekor entry
    """
    from floe_core.schemas.signing import VerificationBundle

    bundle_json = _decode_bundle_with_size_limit(metadata.bundle)
    sigstore_bundle = json.loads(bundle_json)

    certificate_chain: list[str] = []
    verification_material = sigstore_bundle.get("verificationMaterial", {})
    cert_data = verification_material.get("certificate", {})
    if cert_data.get("rawBytes"):
        certificate_chain.append(cert_data["rawBytes"])

    rekor_entry: dict[str, object] | None = None
    tlog_entries = verification_material.get("tlogEntries", [])
    if tlog_entries:
        rekor_entry = tlog_entries[0]

    return VerificationBundle(
        version="1.0",
        artifact_digest=artifact_digest,
        sigstore_bundle=sigstore_bundle,
        certificate_chain=certificate_chain,
        rekor_entry=rekor_entry,
        created_at=datetime.now(timezone.utc),
    )


def load_verification_policy_from_manifest(
    manifest_path: Path,
) -> VerificationPolicy | None:
    """Load verification policy from manifest.yaml file.

    This function extracts the verification policy configuration from a
    manifest.yaml file. It handles missing files, invalid YAML, and
    missing verification sections gracefully.

    Args:
        manifest_path: Path to manifest.yaml file

    Returns:
        VerificationPolicy if found and valid, None if not configured

    Raises:
        yaml.YAMLError: If YAML parsing fails
        pydantic.ValidationError: If verification policy data is invalid
    """
    import yaml

    from floe_core.schemas.signing import VerificationPolicy

    if not manifest_path.exists():
        return None

    with manifest_path.open() as f:
        manifest_data = yaml.safe_load(f)

    if manifest_data is None:
        return None

    artifacts_config = manifest_data.get("artifacts", {})
    verification_data = artifacts_config.get("verification")

    if verification_data is None:
        return None

    return VerificationPolicy.model_validate(verification_data)


__all__ = [
    "VerificationClient",
    "VerificationError",
    "PolicyViolationError",
    "CosignNotAvailableError",
    "KeyVerificationError",
    "check_cosign_available",
    "verify_artifact",
    "export_verification_bundle",
    "load_verification_policy_from_manifest",
]
