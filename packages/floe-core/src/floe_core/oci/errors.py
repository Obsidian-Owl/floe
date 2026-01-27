"""OCI Client exception hierarchy for floe-core.

This module defines all custom exceptions used in the OCI client.
All exceptions inherit from OCIError, the base exception class.

Exception Hierarchy:
    OCIError (base)
    ├── AuthenticationError        # Registry authentication failed
    ├── ArtifactNotFoundError      # Requested artifact/tag not found
    ├── ImmutabilityViolationError # Attempt to overwrite immutable tag
    ├── CircuitBreakerOpenError    # Circuit breaker is open, failing fast
    ├── RegistryUnavailableError   # Registry not reachable
    ├── DigestMismatchError        # Content digest verification failed
    ├── CacheError                 # Local cache operation failed
    ├── SignatureVerificationError # Artifact signature verification failed
    └── ConcurrentSigningError     # Another process is signing the artifact

Exit Codes (per spec):
    0 - Success
    1 - General error (OCIError)
    2 - Authentication error (AuthenticationError)
    3 - Artifact not found (ArtifactNotFoundError)
    4 - Immutability violation (ImmutabilityViolationError)
    5 - Network/connectivity error (RegistryUnavailableError, CircuitBreakerOpenError)
    6 - Signature verification failed (SignatureVerificationError)
    7 - Concurrent signing lock failed (ConcurrentSigningError)

Example:
    >>> from floe_core.oci.errors import ArtifactNotFoundError
    >>> raise ArtifactNotFoundError("v1.0.0", "oci://harbor.example.com/floe")
    Traceback (most recent call last):
        ...
    ArtifactNotFoundError: Artifact not found: v1.0.0 in oci://harbor.example.com/floe

See Also:
    - specs/08a-oci-client/spec.md: Error handling requirements
    - specs/08a-oci-client/quickstart.md: Exit codes documentation
"""

from __future__ import annotations


class OCIError(Exception):
    """Base exception for all OCI client errors.

    All OCI exceptions inherit from this class, allowing callers
    to catch all OCI errors with a single except clause.

    Attributes:
        exit_code: CLI exit code for this error type (default: 1).

    Example:
        >>> try:
        ...     client.push(artifacts, tag="v1.0.0")
        ... except OCIError as e:
        ...     print(f"OCI operation failed: {e}")
        ...     sys.exit(e.exit_code)
    """

    exit_code: int = 1

    pass


class AuthenticationError(OCIError):
    """Raised when registry authentication fails.

    This error indicates that credentials are missing, invalid, or expired.
    Check SecretsPlugin configuration and credential resolution.

    Attributes:
        registry: The registry URI where authentication failed.
        reason: Description of why authentication failed.
        exit_code: CLI exit code (2).

    Example:
        >>> raise AuthenticationError(
        ...     "oci://harbor.example.com/floe",
        ...     "Invalid username or password"
        ... )
        Traceback (most recent call last):
            ...
        AuthenticationError: Authentication failed for oci://...: Invalid username...
    """

    exit_code: int = 2

    def __init__(self, registry: str, reason: str) -> None:
        """Initialize AuthenticationError.

        Args:
            registry: The registry URI where authentication failed.
            reason: Description of why authentication failed.
        """
        self.registry = registry
        self.reason = reason
        super().__init__(f"Authentication failed for {registry}: {reason}")


class ArtifactNotFoundError(OCIError):
    """Raised when a requested artifact or tag is not found.

    This error indicates that the specified tag does not exist in the registry.
    Use `floe artifact list` to see available tags.

    Attributes:
        tag: The tag that was not found.
        registry: The registry URI where the artifact was sought.
        available_tags: Optional list of available tags for helpful error message.
        exit_code: CLI exit code (3).

    Example:
        >>> raise ArtifactNotFoundError(
        ...     "v2.0.0",
        ...     "oci://harbor.example.com/floe",
        ...     available_tags=["v1.0.0", "v1.1.0"]
        ... )
        Traceback (most recent call last):
            ...
        ArtifactNotFoundError: Artifact not found: v2.0.0 in oci://harbor.example.com/floe
    """

    exit_code: int = 3

    def __init__(
        self,
        tag: str,
        registry: str,
        available_tags: list[str] | None = None,
    ) -> None:
        """Initialize ArtifactNotFoundError.

        Args:
            tag: The tag that was not found.
            registry: The registry URI where the artifact was sought.
            available_tags: Optional list of available tags for helpful error message.
        """
        self.tag = tag
        self.registry = registry
        self.available_tags = available_tags

        msg = f"Artifact not found: {tag} in {registry}"
        if available_tags:
            tags_preview = ", ".join(available_tags[:5])
            if len(available_tags) > 5:
                tags_preview += f" (and {len(available_tags) - 5} more)"
            msg += f". Available tags: {tags_preview}"
        super().__init__(msg)


class ImmutabilityViolationError(OCIError):
    """Raised when attempting to overwrite an immutable tag.

    This error indicates that a push operation attempted to overwrite
    a semver tag (e.g., v1.0.0) which is immutable by policy.

    Attributes:
        tag: The immutable tag that already exists.
        registry: The registry URI where the tag exists.
        digest: The existing artifact's digest.
        exit_code: CLI exit code (4).

    Example:
        >>> raise ImmutabilityViolationError(
        ...     "v1.0.0",
        ...     "oci://harbor.example.com/floe",
        ...     "sha256:abc123..."
        ... )
        Traceback (most recent call last):
            ...
        ImmutabilityViolationError: Cannot overwrite immutable tag v1.0.0 in oci://harbor.example.com/floe
    """

    exit_code: int = 4

    def __init__(self, tag: str, registry: str, digest: str | None = None) -> None:
        """Initialize ImmutabilityViolationError.

        Args:
            tag: The immutable tag that already exists.
            registry: The registry URI where the tag exists.
            digest: The existing artifact's digest (if known).
        """
        self.tag = tag
        self.registry = registry
        self.digest = digest

        msg = f"Cannot overwrite immutable tag {tag} in {registry}"
        if digest:
            msg += f" (existing digest: {digest[:19]}...)"
        msg += ". Use a new version number."
        super().__init__(msg)


class CircuitBreakerOpenError(OCIError):
    """Raised when circuit breaker is open and failing fast.

    This error indicates that the registry has been unavailable for
    too many consecutive requests. Operations are being rejected
    without attempting network calls.

    Attributes:
        registry: The registry URI with open circuit breaker.
        failure_count: Number of consecutive failures that opened the circuit.
        recovery_at: Timestamp when half-open probing will begin.
        exit_code: CLI exit code (5).

    Example:
        >>> raise CircuitBreakerOpenError(
        ...     "oci://harbor.example.com/floe",
        ...     failure_count=5
        ... )
        Traceback (most recent call last):
            ...
        CircuitBreakerOpenError: Circuit breaker open for oci://harbor.example.com/floe
    """

    exit_code: int = 5

    def __init__(
        self,
        registry: str,
        failure_count: int = 0,
        recovery_at: str | None = None,
    ) -> None:
        """Initialize CircuitBreakerOpenError.

        Args:
            registry: The registry URI with open circuit breaker.
            failure_count: Number of consecutive failures that opened the circuit.
            recovery_at: ISO timestamp when half-open probing will begin.
        """
        self.registry = registry
        self.failure_count = failure_count
        self.recovery_at = recovery_at

        msg = f"Circuit breaker open for {registry}"
        if failure_count > 0:
            msg += f" (after {failure_count} failures)"
        if recovery_at:
            msg += f". Retry after {recovery_at}"
        super().__init__(msg)


class RegistryUnavailableError(OCIError):
    """Raised when the registry is not reachable.

    This error indicates a network connectivity issue or that the
    registry service is down. The client will retry with exponential
    backoff before raising this error.

    Attributes:
        registry: The registry URI that is unreachable.
        reason: Description of the connectivity failure.
        exit_code: CLI exit code (5).

    Example:
        >>> raise RegistryUnavailableError(
        ...     "oci://harbor.example.com/floe",
        ...     "Connection timed out"
        ... )
        Traceback (most recent call last):
            ...
        RegistryUnavailableError: Registry unavailable: oci://harbor.example.com/floe
    """

    exit_code: int = 5

    def __init__(self, registry: str, reason: str) -> None:
        """Initialize RegistryUnavailableError.

        Args:
            registry: The registry URI that is unreachable.
            reason: Description of the connectivity failure.
        """
        self.registry = registry
        self.reason = reason
        super().__init__(f"Registry unavailable: {registry}: {reason}")


class DigestMismatchError(OCIError):
    """Raised when content digest verification fails.

    This error indicates that the downloaded content does not match
    the expected digest, suggesting corruption or tampering.

    Attributes:
        expected: The expected digest (sha256:...).
        actual: The actual computed digest.
        artifact_ref: The artifact reference (tag or digest) being verified.

    Example:
        >>> raise DigestMismatchError(
        ...     "sha256:abc123...",
        ...     "sha256:def456...",
        ...     "v1.0.0"
        ... )
        Traceback (most recent call last):
            ...
        DigestMismatchError: Digest mismatch for v1.0.0
    """

    def __init__(self, expected: str, actual: str, artifact_ref: str) -> None:
        """Initialize DigestMismatchError.

        Args:
            expected: The expected digest (sha256:...).
            actual: The actual computed digest.
            artifact_ref: The artifact reference (tag or digest) being verified.
        """
        self.expected = expected
        self.actual = actual
        self.artifact_ref = artifact_ref
        super().__init__(
            f"Digest mismatch for {artifact_ref}: expected {expected[:19]}..., got {actual[:19]}..."
        )


class CacheError(OCIError):
    """Raised when a local cache operation fails.

    This error indicates a problem with the local artifact cache,
    such as file system errors, corruption, or locking issues.

    Attributes:
        operation: The cache operation that failed (get, put, evict).
        reason: Description of the failure.
        path: The cache path involved (if applicable).

    Example:
        >>> raise CacheError("put", "Disk full", Path("/var/cache/floe/oci"))
        Traceback (most recent call last):
            ...
        CacheError: Cache operation 'put' failed: Disk full
    """

    def __init__(self, operation: str, reason: str, path: str | None = None) -> None:
        """Initialize CacheError.

        Args:
            operation: The cache operation that failed (get, put, evict).
            reason: Description of the failure.
            path: The cache path involved (if applicable).
        """
        self.operation = operation
        self.reason = reason
        self.path = path

        msg = f"Cache operation '{operation}' failed: {reason}"
        if path:
            msg += f" (path: {path})"
        super().__init__(msg)


class SignatureVerificationError(OCIError):
    """Raised when artifact signature verification fails.

    This error indicates that an artifact's cryptographic signature could not
    be verified. This may mean the artifact is unsigned, the signature is
    invalid, or the signer is not in the trusted issuers list.

    Attributes:
        artifact_ref: The artifact reference that failed verification.
        reason: Description of why verification failed.
        expected_signer: Expected signer identity (from trusted_issuers).
        actual_signer: Actual signer identity found in signature.
        exit_code: CLI exit code (6).

    Remediation:
        - If unsigned: Run 'floe artifact sign <ref>' to sign the artifact
        - If signer mismatch: Update trusted_issuers in verification config
        - If expired: Re-sign the artifact with 'floe artifact sign --force'

    Example:
        >>> raise SignatureVerificationError(
        ...     "oci://harbor.example.com/floe:v1.0.0",
        ...     "Signer not in trusted issuers",
        ...     expected_signer="repo:acme/floe:ref:refs/heads/main",
        ...     actual_signer="repo:unknown/repo:ref:refs/heads/main"
        ... )
    """

    exit_code: int = 6

    def __init__(
        self,
        artifact_ref: str,
        reason: str,
        expected_signer: str | None = None,
        actual_signer: str | None = None,
    ) -> None:
        self.artifact_ref = artifact_ref
        self.reason = reason
        self.expected_signer = expected_signer
        self.actual_signer = actual_signer

        msg = f"Signature verification failed for {artifact_ref}: {reason}"
        if expected_signer and actual_signer:
            msg += f". Expected: {expected_signer}, Actual: {actual_signer}"

        msg += "\n\nRemediation:\n"
        if "unsigned" in reason.lower() or "no signature" in reason.lower():
            msg += f"  - Sign the artifact: floe artifact sign {artifact_ref}\n"
        elif "signer" in reason.lower() or "issuer" in reason.lower():
            msg += "  - Update trusted_issuers in verification config to include actual signer\n"
            msg += f"  - Or re-sign with authorized identity: floe artifact sign {artifact_ref}\n"
        elif "expired" in reason.lower():
            msg += f"  - Re-sign the artifact: floe artifact sign --force {artifact_ref}\n"
        else:
            msg += f"  - Re-sign the artifact: floe artifact sign {artifact_ref}\n"
            msg += "  - Verify network connectivity to Rekor transparency log\n"

        super().__init__(msg)


class ConcurrentSigningError(OCIError):
    """Raised when concurrent signing lock cannot be acquired.

    This error indicates that another process is currently signing the same
    artifact. Signing operations are serialized per-artifact to prevent race
    conditions when updating OCI annotations.

    Attributes:
        artifact_ref: The artifact reference that is locked.
        timeout_seconds: How long we waited before giving up.
        exit_code: CLI exit code (7).

    Remediation:
        Wait for the other signing process to complete, or increase the
        lock timeout via FLOE_SIGNING_LOCK_TIMEOUT environment variable.

    Example:
        >>> raise ConcurrentSigningError(
        ...     "oci://harbor.example.com/floe:v1.0.0",
        ...     timeout_seconds=30.0
        ... )
    """

    exit_code: int = 7

    def __init__(self, artifact_ref: str, timeout_seconds: float) -> None:
        self.artifact_ref = artifact_ref
        self.timeout_seconds = timeout_seconds

        msg = (
            f"Could not acquire signing lock for {artifact_ref} "
            f"(timeout: {timeout_seconds}s). Another process may be signing this artifact. "
            f"Retry later or increase FLOE_SIGNING_LOCK_TIMEOUT."
        )
        super().__init__(msg)
