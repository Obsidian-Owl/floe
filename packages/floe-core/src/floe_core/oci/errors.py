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
    ├── ConcurrentSigningError     # Another process is signing the artifact
    │
    │   Promotion Lifecycle Exceptions (Epic 8C):
    ├── GateValidationError        # Promotion gate validation failed
    ├── InvalidTransitionError     # Invalid environment transition
    ├── TagExistsError             # Promotion tag already exists
    ├── VersionNotPromotedError    # Version not in target environment
    ├── AuthorizationError         # Operator not authorized
    ├── EnvironmentLockedError     # Target environment is locked
    └── SeparationOfDutiesError    # Same operator for consecutive environments

Exit Codes (per spec):
    0 - Success
    1 - General error (OCIError)
    2 - Authentication error (AuthenticationError)
    3 - Artifact not found (ArtifactNotFoundError)
    4 - Immutability violation (ImmutabilityViolationError)
    5 - Network/connectivity error (RegistryUnavailableError, CircuitBreakerOpenError)
    6 - Signature verification failed (SignatureVerificationError)
    7 - Concurrent signing lock failed (ConcurrentSigningError)
    8 - Gate validation failed (GateValidationError)
    9 - Invalid environment transition (InvalidTransitionError)
    10 - Tag already exists (TagExistsError)
    11 - Version not promoted (VersionNotPromotedError)
    12 - Authorization failed (AuthorizationError)
    13 - Environment locked (EnvironmentLockedError)
    14 - Separation of duties violation (SeparationOfDutiesError)

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


# =============================================================================
# Promotion Lifecycle Exceptions (Epic 8C)
# =============================================================================


class GateValidationError(OCIError):
    """Raised when a promotion gate validation fails.

    This error indicates that a validation gate (tests, security_scan, etc.)
    did not pass during artifact promotion. The promotion is blocked unless
    in dry-run mode.

    Attributes:
        gate: The gate type that failed (e.g., "tests", "security_scan").
        details: Description of why the gate failed.
        exit_code: CLI exit code (8).

    Example:
        >>> raise GateValidationError(
        ...     gate="security_scan",
        ...     details="Critical CVE found: CVE-2024-1234"
        ... )
    """

    exit_code: int = 8

    def __init__(self, gate: str, details: str) -> None:
        self.gate = gate
        self.details = details
        super().__init__(f"Gate '{gate}' validation failed: {details}")


class InvalidTransitionError(OCIError):
    """Raised when an invalid environment transition is attempted.

    This error indicates that the requested promotion path is not valid.
    Artifacts must be promoted through environments in the configured order.

    Attributes:
        from_env: The source environment name.
        to_env: The target environment name.
        reason: Description of why the transition is invalid.
        exit_code: CLI exit code (9).

    Example:
        >>> raise InvalidTransitionError(
        ...     from_env="prod",
        ...     to_env="dev",
        ...     reason="Cannot demote from prod to dev"
        ... )
    """

    exit_code: int = 9

    def __init__(self, from_env: str, to_env: str, reason: str) -> None:
        self.from_env = from_env
        self.to_env = to_env
        self.reason = reason
        super().__init__(f"Invalid transition from '{from_env}' to '{to_env}': {reason}")


class TagExistsError(OCIError):
    """Raised when attempting to create a tag that already exists.

    This error indicates that the target promotion tag already exists.
    Promotion tags are immutable once created.

    Attributes:
        tag: The tag that already exists.
        existing_digest: The digest of the existing artifact at that tag.
        exit_code: CLI exit code (10).

    Example:
        >>> raise TagExistsError(
        ...     tag="v1.0.0-staging",
        ...     existing_digest="sha256:abc123..."
        ... )
    """

    exit_code: int = 10

    def __init__(self, tag: str, existing_digest: str) -> None:
        self.tag = tag
        self.existing_digest = existing_digest
        super().__init__(
            f"Tag '{tag}' already exists with digest {existing_digest[:19]}... "
            "Promotion tags are immutable."
        )


class VersionNotPromotedError(OCIError):
    """Raised when a version has not been promoted to the required environment.

    This error indicates that the requested artifact version does not exist
    in the specified environment. It may not have been promoted yet.

    Attributes:
        tag: The tag/version that was requested.
        environment: The environment where the version was not found.
        available_versions: List of versions available in that environment.
        exit_code: CLI exit code (11).

    Example:
        >>> raise VersionNotPromotedError(
        ...     tag="v2.0.0",
        ...     environment="staging",
        ...     available_versions=["v1.0.0", "v1.1.0"]
        ... )
    """

    exit_code: int = 11

    def __init__(
        self,
        tag: str,
        environment: str,
        available_versions: list[str] | None = None,
    ) -> None:
        self.tag = tag
        self.environment = environment
        self.available_versions = available_versions or []

        msg = f"Version '{tag}' has not been promoted to '{environment}'"
        if self.available_versions:
            versions_preview = ", ".join(self.available_versions[:5])
            if len(self.available_versions) > 5:
                versions_preview += f" (and {len(self.available_versions) - 5} more)"
            msg += f". Available versions: {versions_preview}"
        super().__init__(msg)


class AuthorizationError(OCIError):
    """Raised when an operator is not authorized to perform a promotion.

    This error indicates that the operator does not have permission to
    promote to the target environment, or a separation of duties violation.
    Includes actionable guidance for the user (T132 - FR-048).

    Attributes:
        operator: The identity of the operator attempting the action.
        required_groups: Groups that have permission for this action.
        reason: Description of why authorization failed.
        environment: Target environment for the promotion (optional).
        allowed_operators: Specific operators allowed for this environment (optional).
        exit_code: CLI exit code (12).

    Example:
        >>> raise AuthorizationError(
        ...     operator="user@example.com",
        ...     required_groups=["platform-admins"],
        ...     reason="Not a member of required groups",
        ...     environment="prod",
        ... )
    """

    exit_code: int = 12

    def __init__(
        self,
        operator: str,
        required_groups: list[str],
        reason: str,
        environment: str | None = None,
        allowed_operators: list[str] | None = None,
    ) -> None:
        self.operator = operator
        self.required_groups = required_groups
        self.reason = reason
        self.environment = environment
        self.allowed_operators = allowed_operators

        # Build actionable error message (T132 - FR-048)
        message_parts = [f"Authorization failed for operator '{operator}'"]

        if environment:
            message_parts.append(f"to promote to '{environment}' environment")

        message_parts.append(f": {reason}")

        # Add actionable guidance
        guidance_parts = []

        if required_groups:
            groups_str = ", ".join(required_groups)
            guidance_parts.append(f"Required groups: [{groups_str}]")
            guidance_parts.append(
                "To get access: Request membership in one of the required groups "
                "from your platform administrator."
            )
        elif allowed_operators:
            operators_str = ", ".join(allowed_operators[:3])
            if len(allowed_operators) > 3:
                operators_str += f", ... ({len(allowed_operators) - 3} more)"
            guidance_parts.append(f"Allowed operators: [{operators_str}]")
            guidance_parts.append(
                "Contact a listed operator or your platform administrator "
                "to perform this promotion."
            )

        if environment:
            guidance_parts.append(
                f"Run 'floe promote info --env={environment}' to see authorization rules."
            )

        full_message = "".join(message_parts)
        if guidance_parts:
            full_message += "\n\n" + "\n".join(guidance_parts)

        super().__init__(full_message)

    def get_actionable_guidance(self) -> str:
        """Get actionable guidance for resolving authorization failure.

        Returns:
            Human-readable guidance on how to resolve the authorization issue.
        """
        guidance = []

        if self.required_groups:
            guidance.append(
                "1. Request access to one of the required groups: "
                f"{', '.join(self.required_groups)}"
            )
            guidance.append("2. Contact your platform administrator for group membership")
        elif self.allowed_operators:
            guidance.append("1. Contact one of the allowed operators to perform this promotion")
            guidance.append("2. Request to be added to the allowed_operators list")

        if self.environment:
            guidance.append(
                f"3. Review authorization rules: floe promote info --env={self.environment}"
            )

        guidance.append("4. Check your identity: floe whoami")

        return "\n".join(guidance)


class EnvironmentLockedError(OCIError):
    """Raised when attempting to promote to a locked environment.

    This error indicates that the target environment is locked and no
    promotions are allowed until it is unlocked.

    Attributes:
        environment: The locked environment name.
        locked_by: The operator who locked the environment.
        locked_at: When the environment was locked (ISO timestamp).
        reason: Why the environment was locked.
        exit_code: CLI exit code (13).

    Example:
        >>> raise EnvironmentLockedError(
        ...     environment="prod",
        ...     locked_by="sre@example.com",
        ...     locked_at="2026-01-15T10:30:00Z",
        ...     reason="Incident #123 - Database migration in progress"
        ... )
    """

    exit_code: int = 13

    def __init__(
        self,
        environment: str,
        locked_by: str,
        locked_at: str,
        reason: str,
    ) -> None:
        self.environment = environment
        self.locked_by = locked_by
        self.locked_at = locked_at
        self.reason = reason

        super().__init__(
            f"Environment '{environment}' is locked: {reason}. Locked by {locked_by} at {locked_at}"
        )


class SeparationOfDutiesError(OCIError):
    """Raised when separation of duties is violated during promotion.

    This error indicates that the same operator cannot promote to consecutive
    environments when separation_of_duties is enabled. A different operator
    must promote to the next environment.

    Implements FR-049 (separation rule), FR-050 (enable/disable), FR-052 (audit).

    Attributes:
        operator: The operator attempting the promotion.
        previous_operator: The operator who promoted to the source environment.
        from_env: The source environment.
        to_env: The target environment.
        exit_code: CLI exit code (14).

    Example:
        >>> raise SeparationOfDutiesError(
        ...     operator="alice@example.com",
        ...     previous_operator="alice@example.com",
        ...     from_env="staging",
        ...     to_env="prod"
        ... )
    """

    exit_code: int = 14

    def __init__(
        self,
        operator: str,
        previous_operator: str,
        from_env: str,
        to_env: str,
    ) -> None:
        self.operator = operator
        self.previous_operator = previous_operator
        self.from_env = from_env
        self.to_env = to_env

        msg = (
            f"Separation of duties violation: Operator '{operator}' cannot promote "
            f"from '{from_env}' to '{to_env}' because they also promoted to '{from_env}'.\n\n"
            f"Separation of duties requires different operators for consecutive promotions.\n"
            f"Previous promotion to '{from_env}' was performed by: {previous_operator}\n\n"
            f"Remediation:\n"
            f"  - Request a different team member to perform this promotion\n"
            f"  - Or disable separation_of_duties in the environment config"
        )
        super().__init__(msg)
