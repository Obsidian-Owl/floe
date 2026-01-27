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
import errno
import fcntl
import hashlib
import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opentelemetry import trace

from floe_core.oci.errors import ConcurrentSigningError
from floe_core.schemas.signing import SignatureMetadata, SigningConfig

if TYPE_CHECKING:
    from sigstore.models import Bundle
    from sigstore.oidc import IdentityToken

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

# OIDC token retry configuration
# Max retries for transient OIDC token failures (network issues, temporary unavailability)
OIDC_MAX_RETRIES = int(os.environ.get("FLOE_OIDC_TOKEN_MAX_RETRIES", "3"))
OIDC_RETRY_BASE_DELAY = 0.5  # Base delay in seconds for exponential backoff
OIDC_RETRY_MAX_DELAY = 8.0  # Maximum delay cap in seconds
OIDC_RETRY_JITTER = 0.1  # Random jitter added to delay (0-0.1s)


@contextmanager
def _trace_span(name: str) -> Iterator[None]:
    """Context manager for creating OpenTelemetry spans.

    Args:
        name: Span name following floe.oci.* convention
    """
    with tracer.start_as_current_span(name):
        yield


def _with_span(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for adding OpenTelemetry tracing to methods.

    Args:
        name: Span name following floe.oci.* convention
    """
    import functools

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with tracer.start_as_current_span(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class SigningError(Exception):
    """Base exception for signing operations."""

    pass


class OIDCTokenError(SigningError):
    """Raised when OIDC token acquisition fails.

    Remediation:
        - In CI/CD: Ensure OIDC is enabled (GitHub Actions: permissions.id-token: write)
        - Locally: Run 'floe sign' to trigger interactive OAuth flow
        - Check network connectivity to OIDC issuer
    """

    def __init__(self, reason: str, issuer: str | None = None) -> None:
        self.reason = reason
        self.issuer = issuer
        msg = f"Failed to acquire OIDC token: {reason}"
        if issuer:
            msg += f" (issuer: {issuer})"
        msg += "\n\nRemediation:\n"
        msg += "  - In CI/CD: Ensure OIDC is enabled (GitHub: permissions.id-token: write)\n"
        msg += "  - Locally: 'floe sign' triggers interactive OAuth\n"
        msg += "  - Check network connectivity to OIDC issuer"
        super().__init__(msg)


class CosignNotAvailableError(SigningError):
    """Raised when cosign CLI is not available for key-based signing."""

    def __init__(self) -> None:
        super().__init__(
            "cosign CLI not found. Key-based signing requires cosign. "
            "Install with: brew install cosign (macOS) or "
            "https://github.com/sigstore/cosign#installation"
        )


class KeyLoadError(SigningError):
    """Raised when private key cannot be loaded.

    Remediation:
        - Verify key file exists and is readable
        - For KMS: Check IAM permissions and key ARN
        - For env var: Ensure FLOE_SIGNING_KEY_REF is set correctly
    """

    def __init__(self, reason: str, key_ref: str | None = None) -> None:
        self.reason = reason
        self.key_ref = key_ref
        msg = f"Failed to load private key: {reason}"
        if key_ref:
            msg += f" (ref: {key_ref})"
        msg += "\n\nRemediation:\n"
        msg += "  - Verify key file exists and is readable\n"
        msg += "  - For KMS: Check IAM permissions and key ARN\n"
        msg += "  - For env var: Ensure the referenced variable is set"
        super().__init__(msg)


def check_cosign_available() -> bool:
    """Check if cosign CLI is available on PATH."""
    return shutil.which("cosign") is not None


# Default lock timeout in seconds (configurable via FLOE_SIGNING_LOCK_TIMEOUT)
DEFAULT_LOCK_TIMEOUT = 30.0

# Lock retry interval in seconds
LOCK_RETRY_INTERVAL = 0.1


def _get_lock_dir() -> Path:
    """Get the directory for signing lock files."""
    lock_dir = Path(tempfile.gettempdir()) / "floe" / "signing-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir


def _artifact_lock_path(artifact_ref: str) -> Path:
    """Generate a unique lock file path for an artifact reference."""
    ref_hash = hashlib.sha256(artifact_ref.encode()).hexdigest()[:16]
    return _get_lock_dir() / f"signing-{ref_hash}.lock"


@contextmanager
def signing_lock(artifact_ref: str, timeout_seconds: float | None = None) -> Iterator[None]:
    """Context manager for serializing concurrent signing operations.

    Uses file-based locking to ensure only one process can sign a given
    artifact at a time. This prevents race conditions when updating
    OCI manifest annotations.

    Args:
        artifact_ref: The artifact reference being signed
        timeout_seconds: How long to wait for the lock (default: 30s)

    Yields:
        None when lock is acquired

    Raises:
        ConcurrentSigningError: If lock cannot be acquired within timeout
    """
    if timeout_seconds is None:
        timeout_seconds = float(os.environ.get("FLOE_SIGNING_LOCK_TIMEOUT", DEFAULT_LOCK_TIMEOUT))

    lock_path = _artifact_lock_path(artifact_ref)
    lock_path.touch(exist_ok=True)

    start_time = time.monotonic()
    lock_fd = os.open(str(lock_path), os.O_RDWR)

    lock_acquired = False
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired = True
                logger.debug("Acquired signing lock for %s at %s", artifact_ref, lock_path)
                break
            except OSError as e:
                if e.errno not in (errno.EAGAIN, errno.EWOULDBLOCK):
                    raise

                elapsed = time.monotonic() - start_time
                if elapsed >= timeout_seconds:
                    raise ConcurrentSigningError(artifact_ref, timeout_seconds) from e

                time.sleep(LOCK_RETRY_INTERVAL)

        yield

    finally:
        if lock_acquired:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


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
    def sign(
        self,
        content: bytes,
        artifact_ref: str,
        lock_timeout: float | None = None,
    ) -> SignatureMetadata:
        """Sign artifact content and return metadata.

        Signing operations are serialized per-artifact using file-based locking
        to prevent race conditions when multiple processes attempt to sign the
        same artifact concurrently.

        Args:
            content: Raw artifact bytes to sign
            artifact_ref: Full OCI artifact reference (for logging/tracing)
            lock_timeout: Optional override for lock timeout (default: 30s)

        Returns:
            SignatureMetadata containing the Sigstore bundle and metadata

        Raises:
            SigningError: If signing fails
            OIDCTokenError: If OIDC token cannot be acquired (keyless mode)
            ConcurrentSigningError: If lock cannot be acquired within timeout
        """
        span = trace.get_current_span()
        span.set_attribute("floe.artifact.ref", artifact_ref)
        span.set_attribute("floe.signing.mode", self.config.mode)

        with signing_lock(artifact_ref, lock_timeout):
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
        from sigstore.sign import SigningContext

        with _trace_span("floe.oci.sign.oidc_token"):
            identity = self._get_identity_token()
            span = trace.get_current_span()
            span.set_attribute("floe.signing.issuer", str(identity.federated_issuer))

        context = SigningContext.production()

        with _trace_span("floe.oci.sign.fulcio"):
            with context.signer(identity, cache=True) as signer:
                with _trace_span("floe.oci.sign.rekor"):
                    bundle: Bundle = signer.sign_artifact(content)

        return self._bundle_to_metadata(bundle, identity)

    def _sign_key_based(self, content: bytes, artifact_ref: str) -> SignatureMetadata:
        """Sign using key-based mode (private key or KMS).

        Uses cosign CLI for signing with local key files or KMS references.
        No transparency log entry is created (air-gapped mode).

        Args:
            content: Artifact bytes to sign
            artifact_ref: OCI reference for logging

        Returns:
            SignatureMetadata with signature bundle

        Raises:
            CosignNotAvailableError: If cosign CLI is not installed
            KeyLoadError: If private key cannot be loaded
            SigningError: If signing operation fails
        """
        if not check_cosign_available():
            raise CosignNotAvailableError()

        key_ref = self._resolve_key_reference()

        with _trace_span("floe.oci.sign.key_based"):
            signature_bundle = self._cosign_sign_blob(content, key_ref)
            return self._key_signature_to_metadata(signature_bundle, key_ref)

    def _resolve_key_reference(self) -> str:
        """Resolve the key reference from config.

        Returns:
            Key path or KMS URI for cosign

        Raises:
            KeyLoadError: If key reference cannot be resolved
        """
        if self.config.private_key_ref is None:
            raise KeyLoadError("No private_key_ref configured for key-based signing")

        key_ref = self.config.private_key_ref

        if key_ref.source.value == "file":
            key_path = Path(key_ref.name)
            if not key_path.exists():
                raise KeyLoadError(f"Key file not found: {key_path}", key_ref.name)
            return str(key_path)

        if key_ref.source.value == "env":
            import os

            env_var_name = f"FLOE_{key_ref.name.upper().replace('-', '_')}"
            env_value = os.environ.get(env_var_name)
            if not env_value:
                raise KeyLoadError(f"Environment variable not set: {env_var_name}", key_ref.name)
            return env_value

        if key_ref.source.value == "kubernetes":
            raise KeyLoadError(
                "Kubernetes secret references not yet supported for key-based signing. "
                "Use file or KMS key reference.",
                key_ref.name,
            )

        raise KeyLoadError(f"Unsupported key source: {key_ref.source.value}", key_ref.name)

    def _cosign_sign_blob(self, content: bytes, key_ref: str) -> dict[str, Any]:
        """Sign content using cosign CLI.

        Args:
            content: Bytes to sign
            key_ref: Key path or KMS URI

        Returns:
            Signature bundle as dict

        Raises:
            SigningError: If cosign signing fails
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            content_file = tmpdir_path / "content.bin"
            signature_file = tmpdir_path / "signature.sig"
            bundle_file = tmpdir_path / "bundle.json"

            content_file.write_bytes(content)

            is_kms = key_ref.startswith(("awskms://", "gcpkms://", "azurekms://", "hashivault://"))

            cmd = [
                "cosign",
                "sign-blob",
                "--key",
                key_ref,
                "--output-signature",
                str(signature_file),
                "--output-bundle",
                str(bundle_file),
                "--tlog-upload=false",
                str(content_file),
            ]

            if not is_kms:
                cmd.insert(3, "--yes")

            logger.debug("Running cosign sign-blob: %s", " ".join(cmd[:5]) + " ...")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )

                if result.returncode != 0:
                    raise SigningError(f"cosign sign-blob failed: {result.stderr}")

                if bundle_file.exists():
                    bundle_data: dict[str, Any] = json.loads(bundle_file.read_text())
                    return bundle_data

                if signature_file.exists():
                    signature_b64 = signature_file.read_text().strip()
                    return {"base64Signature": signature_b64, "keyRef": key_ref}

                raise SigningError("cosign did not produce signature output")

            except subprocess.TimeoutExpired as e:
                raise SigningError("cosign sign-blob timed out after 60 seconds") from e
            except json.JSONDecodeError as e:
                raise SigningError(f"Invalid JSON output from cosign: {e}") from e

    def _key_signature_to_metadata(self, bundle: dict[str, Any], key_ref: str) -> SignatureMetadata:
        """Convert cosign key-based signature to SignatureMetadata.

        Args:
            bundle: Signature bundle from cosign
            key_ref: Key reference used for signing

        Returns:
            SignatureMetadata for OCI annotations
        """
        bundle_json = json.dumps(bundle)
        bundle_b64 = base64.b64encode(bundle_json.encode("utf-8")).decode("ascii")

        key_fingerprint = self._compute_key_fingerprint(key_ref)

        span = trace.get_current_span()
        span.set_attribute("floe.signing.key_ref", key_ref[:50] if len(key_ref) > 50 else key_ref)

        return SignatureMetadata(
            bundle=bundle_b64,
            mode="key-based",
            issuer=None,
            subject=key_ref,
            signed_at=datetime.now(timezone.utc),
            rekor_log_index=None,
            certificate_fingerprint=key_fingerprint,
        )

    def _compute_key_fingerprint(self, key_ref: str) -> str:
        """Compute fingerprint for key reference.

        For KMS keys, returns a hash of the key URI.
        For file keys, returns hash of the public key if extractable.

        Args:
            key_ref: Key path or KMS URI

        Returns:
            Fingerprint string (may be empty if not computable)
        """
        if key_ref.startswith(("awskms://", "gcpkms://", "azurekms://", "hashivault://")):
            return hashlib.sha256(key_ref.encode()).hexdigest()[:16]

        try:
            key_path = Path(key_ref)
            if key_path.exists():
                key_content = key_path.read_bytes()
                return hashlib.sha256(key_content).hexdigest()[:16]
        except Exception:
            pass

        return ""

    def _get_identity_token(self) -> IdentityToken:
        """Get OIDC identity token for keyless signing.

        Attempts to detect ambient credentials from CI/CD environment
        (GitHub Actions, GitLab CI, etc.). Falls back to interactive
        OAuth flow if no ambient credentials are available.

        Implements exponential backoff retry for transient failures.
        Configure via FLOE_OIDC_TOKEN_MAX_RETRIES (default: 3).

        Returns:
            sigstore.oidc.IdentityToken

        Raises:
            OIDCTokenError: If token cannot be acquired after all retries
        """
        from sigstore.oidc import IdentityError

        last_error: IdentityError | None = None

        for attempt in range(OIDC_MAX_RETRIES):
            try:
                token = self._attempt_token_acquisition()
                if token is not None:
                    return token
            except IdentityError as e:
                last_error = e
                if attempt < OIDC_MAX_RETRIES - 1:
                    delay = min(
                        OIDC_RETRY_BASE_DELAY * (2**attempt) + random.uniform(0, OIDC_RETRY_JITTER),
                        OIDC_RETRY_MAX_DELAY,
                    )
                    logger.warning(
                        "OIDC token acquisition failed (attempt %d/%d): %s. Retrying in %.2fs",
                        attempt + 1,
                        OIDC_MAX_RETRIES,
                        e,
                        delay,
                    )
                    time.sleep(delay)

        issuer_str = str(self.config.oidc_issuer) if self.config.oidc_issuer else None
        raise OIDCTokenError(
            f"Failed after {OIDC_MAX_RETRIES} attempts: {last_error}",
            issuer=issuer_str,
        )

    def _attempt_token_acquisition(self) -> IdentityToken | None:
        """Single attempt to acquire OIDC token.

        Returns:
            IdentityToken if successful, None if ambient detection found nothing

        Raises:
            IdentityError: On token acquisition failure
        """
        from sigstore.oidc import IdentityError, IdentityToken, Issuer, detect_credential

        try:
            credential = detect_credential()
            if credential is not None:
                logger.debug("Detected ambient OIDC credential")
                return IdentityToken(credential)
        except IdentityError as e:
            logger.warning("Ambient credential detection failed: %s", e)
            raise

        logger.info("No ambient credentials, initiating interactive OAuth flow")
        issuer = Issuer.production()
        return issuer.identity_token()

    def _bundle_to_metadata(self, bundle: Bundle, identity: IdentityToken) -> SignatureMetadata:
        """Convert Sigstore bundle to SignatureMetadata.

        Args:
            bundle: Sigstore bundle with signature, certificate, and Rekor entry
            identity: OIDC identity token used for signing

        Returns:
            SignatureMetadata for OCI annotation storage
        """

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
    result: SignatureMetadata = client.sign(content, artifact_ref)
    return result


__all__ = [
    "SigningClient",
    "SigningError",
    "OIDCTokenError",
    "CosignNotAvailableError",
    "KeyLoadError",
    "check_cosign_available",
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
