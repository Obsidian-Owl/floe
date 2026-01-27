"""Artifact signing using Sigstore.

Implements:
    - FR-001: Cosign integration (sigstore-python primary, cosign CLI fallback)
    - FR-011: Signature metadata in OCI annotations
    - SC-007: OpenTelemetry tracing for signing operations

This module provides keyless signing using OIDC identity (GitHub Actions, GitLab CI)
and key-based signing for air-gapped environments.

Example:
    >>> from floe_core.oci.signing import SigningClient
    >>> from floe_core.schemas.signing import SigningConfig
    >>>
    >>> # Keyless signing in CI/CD
    >>> config = SigningConfig(mode="keyless", oidc_issuer="https://token.actions.githubusercontent.com")
    >>> client = SigningClient(config)
    >>> metadata = client.sign(artifact_bytes, artifact_ref="oci://harbor.example.com/floe:v1.0.0")

See Also:
    - specs/8b-artifact-signing/spec.md: Feature specification
    - specs/8b-artifact-signing/research.md: sigstore-python patterns
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterator

from opentelemetry import trace

from floe_core.schemas.signing import SignatureMetadata, SigningConfig

if TYPE_CHECKING:
    from sigstore.models import Bundle
    from sigstore.oidc import IdentityToken
    from sigstore.sign import Signer

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# OCI annotation keys for signature metadata
ANNOTATION_BUNDLE = "dev.floe.signature.bundle"
ANNOTATION_MODE = "dev.floe.signature.mode"
ANNOTATION_ISSUER = "dev.floe.signature.issuer"
ANNOTATION_SUBJECT = "dev.floe.signature.subject"
ANNOTATION_SIGNED_AT = "dev.floe.signature.signed-at"
ANNOTATION_REKOR_INDEX = "dev.floe.signature.rekor-index"
ANNOTATION_CERT_FINGERPRINT = "dev.floe.signature.cert-fingerprint"


@contextmanager
def _trace_span(name: str) -> Iterator[None]:
    """Context manager for creating OpenTelemetry spans.

    Args:
        name: Span name following floe.oci.* convention
    """
    with tracer.start_as_current_span(name):
        yield


def _with_span(name: str):
    """Decorator for adding OpenTelemetry tracing to methods.

    Args:
        name: Span name following floe.oci.* convention
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class SigningError(Exception):
    """Base exception for signing operations."""

    pass


class OIDCTokenError(SigningError):
    """Raised when OIDC token acquisition fails."""

    def __init__(self, reason: str, issuer: str | None = None) -> None:
        self.reason = reason
        self.issuer = issuer
        msg = f"Failed to acquire OIDC token: {reason}"
        if issuer:
            msg += f" (issuer: {issuer})"
        super().__init__(msg)


class SigningClient:
    """Client for signing artifacts using Sigstore.

    Supports both keyless (OIDC) and key-based signing modes.
    Keyless signing uses sigstore-python directly.
    Key-based signing may fall back to cosign CLI for KMS support.

    Attributes:
        config: SigningConfig with mode and credentials
        _identity_token: Cached OIDC identity token (keyless mode)

    Example:
        >>> config = SigningConfig(
        ...     mode="keyless",
        ...     oidc_issuer="https://token.actions.githubusercontent.com"
        ... )
        >>> client = SigningClient(config)
        >>> metadata = client.sign(b"artifact content", "oci://registry/repo:tag")
    """

    def __init__(self, config: SigningConfig) -> None:
        """Initialize SigningClient.

        Args:
            config: Signing configuration from manifest.yaml
        """
        self.config = config
        self._identity_token: IdentityToken | None = None

    @_with_span("floe.oci.sign")
    def sign(self, content: bytes, artifact_ref: str) -> SignatureMetadata:
        """Sign artifact content and return metadata.

        Args:
            content: Raw artifact bytes to sign
            artifact_ref: Full OCI artifact reference (for logging/tracing)

        Returns:
            SignatureMetadata containing the Sigstore bundle and metadata

        Raises:
            SigningError: If signing fails
            OIDCTokenError: If OIDC token cannot be acquired (keyless mode)
        """
        span = trace.get_current_span()
        span.set_attribute("floe.artifact.ref", artifact_ref)
        span.set_attribute("floe.signing.mode", self.config.mode)

        if self.config.mode == "keyless":
            return self._sign_keyless(content, artifact_ref)
        else:
            return self._sign_key_based(content, artifact_ref)

    def _sign_keyless(self, content: bytes, artifact_ref: str) -> SignatureMetadata:
        """Sign using keyless (OIDC) mode with sigstore-python.

        Args:
            content: Artifact bytes to sign
            artifact_ref: OCI reference for logging

        Returns:
            SignatureMetadata with bundle and identity information
        """
        from sigstore.models import Bundle, ClientTrustConfig
        from sigstore.sign import SigningContext

        # Get or refresh OIDC token
        with _trace_span("floe.oci.sign.oidc_token"):
            identity = self._get_identity_token()
            span = trace.get_current_span()
            span.set_attribute("floe.signing.issuer", str(identity.federated_issuer))

        # Create signing context with production trust config
        trust_config = ClientTrustConfig.production()
        context = SigningContext.from_trust_config(trust_config)

        # Sign the artifact
        with _trace_span("floe.oci.sign.fulcio"):
            with context.signer(identity, cache=True) as signer:
                with _trace_span("floe.oci.sign.rekor"):
                    bundle: Bundle = signer.sign_artifact(content)

        # Extract metadata from bundle
        return self._bundle_to_metadata(bundle, identity)

    def _sign_key_based(self, content: bytes, artifact_ref: str) -> SignatureMetadata:
        """Sign using key-based mode (private key or KMS).

        This is a placeholder for Phase 7 (User Story 5).
        Key-based signing may use cosign CLI for KMS support.

        Args:
            content: Artifact bytes to sign
            artifact_ref: OCI reference for logging

        Returns:
            SignatureMetadata with bundle

        Raises:
            NotImplementedError: Key-based signing not yet implemented
        """
        # TODO: T060 - Implement key-based signing
        raise NotImplementedError(
            "Key-based signing will be implemented in Phase 7 (T060). Use keyless mode for now."
        )

    def _get_identity_token(self) -> IdentityToken:
        """Get OIDC identity token for keyless signing.

        Attempts to detect ambient credentials from CI/CD environment
        (GitHub Actions, GitLab CI, etc.). Falls back to interactive
        OAuth flow if no ambient credentials are available.

        Returns:
            sigstore.oidc.IdentityToken

        Raises:
            OIDCTokenError: If token cannot be acquired
        """
        from sigstore.oidc import IdentityError, IdentityToken, detect_credential

        # Try ambient credential detection first (CI/CD environments)
        try:
            credential = detect_credential()
            if credential is not None:
                logger.debug("Detected ambient OIDC credential")
                return IdentityToken(credential)
        except IdentityError as e:
            logger.warning("Ambient credential detection failed: %s", e)

        # Fall back to interactive OAuth flow
        # This requires browser interaction, typically for local development
        try:
            from sigstore.models import ClientTrustConfig
            from sigstore.oidc import Issuer

            logger.info("No ambient credentials, initiating interactive OAuth flow")
            trust_config = ClientTrustConfig.production()
            issuer = Issuer(trust_config.signing_config.get_oidc_url())
            return issuer.identity_token()
        except IdentityError as e:
            raise OIDCTokenError(
                str(e), issuer=str(self.config.oidc_issuer) if self.config.oidc_issuer else None
            ) from e

    def _bundle_to_metadata(self, bundle: Bundle, identity: IdentityToken) -> SignatureMetadata:
        """Convert Sigstore bundle to SignatureMetadata.

        Args:
            bundle: Sigstore bundle with signature, certificate, and Rekor entry
            identity: OIDC identity token used for signing

        Returns:
            SignatureMetadata for OCI annotation storage
        """
        from sigstore.models import Bundle

        # Serialize bundle to JSON and base64 encode
        bundle_json = bundle.to_json()
        bundle_b64 = base64.b64encode(bundle_json.encode("utf-8")).decode("ascii")

        # Parse bundle for metadata extraction
        bundle_data = json.loads(bundle_json)

        # Extract Rekor log index if present
        rekor_index: int | None = None
        verification_material = bundle_data.get("verificationMaterial", {})
        tlog_entries = verification_material.get("tlogEntries", [])
        if tlog_entries:
            log_index = tlog_entries[0].get("logIndex")
            if log_index is not None:
                rekor_index = int(log_index)

        # Extract certificate and compute fingerprint
        cert_fingerprint = self._extract_cert_fingerprint(verification_material)

        # Record tracing attributes
        span = trace.get_current_span()
        span.set_attribute("floe.signing.subject", identity.identity or "")
        if rekor_index is not None:
            span.set_attribute("floe.signing.rekor_index", rekor_index)

        return SignatureMetadata(
            bundle=bundle_b64,
            mode="keyless",
            issuer=identity.federated_issuer,
            subject=identity.identity or "",
            signed_at=datetime.now(timezone.utc),
            rekor_log_index=rekor_index,
            certificate_fingerprint=cert_fingerprint,
        )

    def _extract_cert_fingerprint(self, verification_material: dict[str, Any]) -> str:
        """Extract certificate fingerprint from verification material.

        Args:
            verification_material: Bundle verification material dict

        Returns:
            SHA256 fingerprint of the signing certificate (hex)
        """
        # Try to get certificate from verification material
        cert_data = verification_material.get("certificate", {})
        raw_bytes = cert_data.get("rawBytes")

        if raw_bytes:
            # Decode base64 certificate and compute SHA256
            try:
                cert_der = base64.b64decode(raw_bytes)
                fingerprint = hashlib.sha256(cert_der).hexdigest()
                return fingerprint
            except Exception as e:
                logger.warning("Failed to compute certificate fingerprint: %s", e)

        return ""


def sign_artifact(
    content: bytes,
    artifact_ref: str,
    config: SigningConfig,
) -> SignatureMetadata:
    """Convenience function to sign an artifact.

    Args:
        content: Artifact bytes to sign
        artifact_ref: OCI artifact reference
        config: Signing configuration

    Returns:
        SignatureMetadata with signature bundle and metadata
    """
    client = SigningClient(config)
    return client.sign(content, artifact_ref)


__all__ = [
    "SigningClient",
    "SigningError",
    "OIDCTokenError",
    "sign_artifact",
    # Annotation keys
    "ANNOTATION_BUNDLE",
    "ANNOTATION_MODE",
    "ANNOTATION_ISSUER",
    "ANNOTATION_SUBJECT",
    "ANNOTATION_SIGNED_AT",
    "ANNOTATION_REKOR_INDEX",
    "ANNOTATION_CERT_FINGERPRINT",
]
