"""Artifact signature verification using Sigstore.

Implements:
    - FR-009: Verification policy configuration
    - FR-010: Identity policy matching (issuer + subject)
    - FR-011: Rekor transparency log verification
    - SC-007: OpenTelemetry tracing for verification operations
    - FR-013: Audit logging for verification attempts

This module provides signature verification for OCI artifacts using sigstore-python.
It supports keyless verification (OIDC-based) with identity policy matching.

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
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from opentelemetry import trace

from floe_core.oci.errors import SignatureVerificationError
from floe_core.schemas.signing import (
    SignatureMetadata,
    TrustedIssuer,
    VerificationAuditEvent,
    VerificationPolicy,
    VerificationResult,
)

if TYPE_CHECKING:
    from sigstore.models import Bundle
    from sigstore.verify import Verifier
    from sigstore.verify.policy import VerificationPolicy as SigstorePolicy

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


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
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

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
        """Verify signature using sigstore-python.

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

        # Parse the Sigstore bundle from metadata
        with tracer.start_as_current_span("floe.oci.verify.bundle"):
            try:
                bundle_json = base64.b64decode(metadata.bundle).decode("utf-8")
                bundle = Bundle.from_json(bundle_json)
            except Exception as e:
                logger.error("Failed to parse Sigstore bundle: %s", e)
                return VerificationResult(
                    status="invalid",
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=f"Invalid Sigstore bundle: {e}",
                )

        # Get or create verifier
        if self._verifier is None:
            self._verifier = Verifier.production()
        verifier = self._verifier

        # Match against trusted issuers
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

            # Create identity policy for verification
            identity = Identity(
                identity=matched_issuer.subject or matched_issuer.subject_regex or "",
                issuer=str(matched_issuer.issuer),
            )

        # Verify with Rekor if required
        with tracer.start_as_current_span("floe.oci.verify.rekor"):
            try:
                # sigstore-python's verify_artifact raises on failure
                verifier.verify_artifact(  # type: ignore[union-attr]
                    input_=content,
                    bundle=bundle,
                    policy=identity,
                )

                # Verification succeeded
                rekor_verified = self._check_rekor_entry(bundle)

                # Check Rekor requirement
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
                logger.error("Signature verification failed: %s", e)
                return VerificationResult(
                    status="invalid",
                    signer_identity=metadata.subject,
                    issuer=metadata.issuer,
                    verified_at=datetime.now(timezone.utc),
                    failure_reason=str(e),
                )

    def _match_trusted_issuer(self, metadata: SignatureMetadata) -> TrustedIssuer | None:
        """Match signature against trusted issuers.

        Args:
            metadata: Signature metadata with issuer and subject

        Returns:
            Matching TrustedIssuer or None if no match
        """
        for trusted in self.policy.trusted_issuers:
            # Check issuer matches (normalize trailing slashes)
            if metadata.issuer:
                trusted_issuer = str(trusted.issuer).rstrip("/")
                actual_issuer = metadata.issuer.rstrip("/")
                if trusted_issuer != actual_issuer:
                    continue

            # Check subject matches (exact or regex)
            if trusted.subject:
                if trusted.subject == metadata.subject:
                    return trusted
            elif trusted.subject_regex:
                if re.match(trusted.subject_regex, metadata.subject):
                    return trusted

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
            trace_id=format(span_context.trace_id, "032x") if span_context.is_valid else "",
            span_id=format(span_context.span_id, "016x") if span_context.is_valid else "",
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


__all__ = [
    "VerificationClient",
    "VerificationError",
    "PolicyViolationError",
    "verify_artifact",
]
