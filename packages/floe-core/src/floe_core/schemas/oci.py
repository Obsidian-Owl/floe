"""OCI Client Schemas for floe CompiledArtifacts distribution.

This module defines the Pydantic v2 schemas for OCI registry configuration,
artifact metadata, and local caching as specified in Epic 8A.

These schemas are contracts - changes require versioning per Constitution Principle IV.

Key Components:
    RegistryConfig: Top-level registry configuration from manifest.yaml
    ArtifactManifest: Metadata returned by inspect operations
    CacheEntry: Local cache entry metadata
    CacheIndex: Index of all cached artifacts

Media Type: application/vnd.floe.compiled-artifacts.v1+json

See Also:
    - specs/08a-oci-client/spec.md: Feature specification
    - specs/08a-oci-client/contracts/: Contract definitions
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from floe_core.schemas.secrets import SecretReference

# =============================================================================
# Utility Functions
# =============================================================================


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# =============================================================================
# Constants
# =============================================================================

FLOE_ARTIFACT_TYPE = "application/vnd.floe.compiled-artifacts.v1+json"
"""Media type for floe CompiledArtifacts OCI artifacts."""

OCI_EMPTY_CONFIG_TYPE = "application/vnd.oci.empty.v1+json"
"""Media type for OCI empty config blob (used when no config needed)."""


# =============================================================================
# Registry Configuration Schemas
# =============================================================================


class AuthType(str, Enum):
    """Authentication types for OCI registries."""

    ANONYMOUS = "anonymous"
    BASIC = "basic"
    TOKEN = "token"
    AWS_IRSA = "aws-irsa"
    AZURE_MANAGED_IDENTITY = "azure-managed-identity"
    GCP_WORKLOAD_IDENTITY = "gcp-workload-identity"


class RegistryAuth(BaseModel):
    """Authentication configuration for OCI registry.

    For basic/token auth, credentials_ref must point to a Kubernetes Secret
    or other secret store via SecretsPlugin (Epic 7A).

    For cloud provider auth (IRSA, MI, WI), authentication is automatic
    and credentials_ref should be None.

    Examples:
        >>> auth = RegistryAuth(
        ...     type=AuthType.BASIC,
        ...     credentials_ref=SecretReference(source="kubernetes", name="registry-creds")
        ... )
        >>> auth.type
        <AuthType.BASIC: 'basic'>
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: AuthType = Field(
        ...,
        description="Authentication type for registry access",
    )
    credentials_ref: SecretReference | None = Field(
        default=None,
        description="Secret reference for basic/token auth (must be None for cloud providers)",
    )

    @field_validator("credentials_ref")
    @classmethod
    def validate_credentials_ref(
        cls, v: SecretReference | None, info: ValidationInfo
    ) -> SecretReference | None:
        """Validate credentials_ref based on auth type."""
        data: dict[str, Any] = info.data if info.data else {}
        auth_type = data.get("type")
        if auth_type in (AuthType.BASIC, AuthType.TOKEN) and v is None:
            raise ValueError(f"credentials_ref required for auth type '{auth_type}'")
        if (
            auth_type
            in (
                AuthType.ANONYMOUS,
                AuthType.AWS_IRSA,
                AuthType.AZURE_MANAGED_IDENTITY,
                AuthType.GCP_WORKLOAD_IDENTITY,
            )
            and v is not None
        ):
            raise ValueError(f"credentials_ref must be None for auth type '{auth_type}'")
        return v


class RetryConfig(BaseModel):
    """Retry policy configuration for transient failures.

    Uses exponential backoff with optional jitter to prevent thundering herd.

    Examples:
        >>> config = RetryConfig(max_attempts=5, initial_delay_ms=500)
        >>> config.initial_delay_ms
        500
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts",
    )
    initial_delay_ms: int = Field(
        default=1000,
        ge=100,
        description="Initial delay between retries in milliseconds",
    )
    backoff_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Multiplier for exponential backoff",
    )
    max_delay_ms: int = Field(
        default=30000,
        ge=1000,
        description="Maximum delay cap in milliseconds",
    )
    jitter: bool = Field(
        default=True,
        description="Add random jitter to delays to prevent thundering herd",
    )


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration for registry availability.

    Implements the circuit breaker pattern with CLOSED, OPEN, and HALF_OPEN states.

    State transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After recovery_timeout_ms
    - HALF_OPEN -> CLOSED: On successful probe
    - HALF_OPEN -> OPEN: On failed probe

    Examples:
        >>> config = CircuitBreakerConfig(failure_threshold=3)
        >>> config.recovery_timeout_ms
        60000
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable circuit breaker pattern",
    )
    failure_threshold: int = Field(
        default=5,
        ge=1,
        description="Number of consecutive failures before opening circuit",
    )
    recovery_timeout_ms: int = Field(
        default=60000,
        ge=1000,
        description="Time in OPEN state before transitioning to HALF_OPEN",
    )
    half_open_requests: int = Field(
        default=1,
        ge=1,
        description="Number of probe requests allowed in HALF_OPEN state",
    )


class ResilienceConfig(BaseModel):
    """Resilience configuration combining retry and circuit breaker.

    Examples:
        >>> config = ResilienceConfig()
        >>> config.retry.max_attempts
        3
        >>> config.circuit_breaker.enabled
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry policy configuration",
    )
    circuit_breaker: CircuitBreakerConfig = Field(
        default_factory=CircuitBreakerConfig,
        description="Circuit breaker configuration",
    )


class CacheConfig(BaseModel):
    """Local cache configuration for pulled artifacts.

    Immutable tags (semver, digests) are cached indefinitely.
    Mutable tags (latest-*) use TTL-based expiry.

    Examples:
        >>> config = CacheConfig(max_size_gb=20, ttl_hours=12)
        >>> config.path
        PosixPath('/var/cache/floe/oci')
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="Enable local artifact caching",
    )
    path: Path = Field(
        default=Path("/var/cache/floe/oci"),
        description="Local directory path for cache storage",
    )
    max_size_gb: int = Field(
        default=10,
        ge=1,
        description="Maximum cache size in gigabytes",
    )
    ttl_hours: int = Field(
        default=24,
        ge=1,
        description="Time-to-live for mutable tag cache entries (hours)",
    )


class RegistryConfig(BaseModel):
    """Complete OCI registry configuration.

    This is the top-level schema for the `artifacts.registry` section
    in manifest.yaml. It configures authentication, caching, and
    resilience for all OCI operations.

    Examples:
        >>> config = RegistryConfig(
        ...     uri="oci://harbor.example.com/floe-platform",
        ...     auth=RegistryAuth(type=AuthType.AWS_IRSA)
        ... )
        >>> config.tls_verify
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str = Field(
        ...,
        min_length=1,
        pattern=r"^oci://[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9](/[a-zA-Z0-9._-]+)*$",
        description="OCI registry URI (e.g., oci://harbor.example.com/namespace)",
        examples=[
            "oci://harbor.example.com/floe-platform",
            "oci://123456789.dkr.ecr.us-east-1.amazonaws.com/floe",
            "oci://myregistry.azurecr.io/floe",
        ],
    )
    auth: RegistryAuth = Field(
        ...,
        description="Authentication configuration",
    )
    tls_verify: bool = Field(
        default=True,
        description="Verify TLS certificates (disable only for local testing)",
    )
    cache: CacheConfig = Field(
        default_factory=CacheConfig,
        description="Local cache configuration",
    )
    resilience: ResilienceConfig = Field(
        default_factory=ResilienceConfig,
        description="Retry and circuit breaker configuration",
    )

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Validate OCI URI format."""
        if not v.startswith("oci://"):
            raise ValueError("Registry URI must start with 'oci://'")
        return v


# =============================================================================
# Artifact Manifest Schemas
# =============================================================================


class SignatureStatus(str, Enum):
    """Signature verification status for artifacts.

    Prepared for Epic 8B (Artifact Signing) integration.
    """

    UNSIGNED = "unsigned"  # No signature found
    VALID = "valid"  # Signature verified successfully
    INVALID = "invalid"  # Signature verification failed
    UNKNOWN = "unknown"  # Unable to verify (missing key/issuer)


class PromotionStatus(str, Enum):
    """Promotion workflow status for artifacts.

    Prepared for Epic 8C (Artifact Promotion) integration.

    Tracks whether an artifact has been promoted through environments
    (e.g., dev -> staging -> production).
    """

    NOT_PROMOTED = "not_promoted"  # Artifact has not been promoted
    PROMOTED = "promoted"  # Artifact has been promoted to target environment
    PENDING = "pending"  # Promotion is in progress or awaiting approval


class ArtifactLayer(BaseModel):
    """Individual content layer within an OCI artifact.

    Each artifact contains one or more layers representing the actual content.
    For floe CompiledArtifacts, there is typically one layer containing the
    compiled_artifacts.json blob.

    Examples:
        >>> layer = ArtifactLayer(
        ...     digest="sha256:abc123...",
        ...     media_type="application/vnd.floe.compiled-artifacts.v1+json",
        ...     size=12345
        ... )
        >>> layer.media_type
        'application/vnd.floe.compiled-artifacts.v1+json'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    digest: str = Field(
        ...,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Layer content digest (SHA256)",
        examples=["sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )
    media_type: str = Field(
        ...,
        min_length=1,
        description="Layer media type",
        examples=[
            "application/vnd.floe.compiled-artifacts.v1+json",
            "application/vnd.oci.image.layer.v1.tar+gzip",
        ],
    )
    size: int = Field(
        ...,
        ge=0,
        description="Layer size in bytes",
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="Layer annotations (key-value metadata)",
    )


class ArtifactManifest(BaseModel):
    """Metadata for an OCI artifact.

    Returned by inspect operations. Contains digest, size, creation time,
    layers, and optional signature status (Epic 8B integration).

    The artifact_type identifies this as a floe CompiledArtifacts artifact,
    enabling registry filtering and discovery.

    Examples:
        >>> manifest = ArtifactManifest(
        ...     digest="sha256:abc123...",
        ...     artifact_type=FLOE_ARTIFACT_TYPE,
        ...     size=12345,
        ...     created_at=datetime.utcnow(),
        ...     layers=[
        ...         ArtifactLayer(
        ...             digest="sha256:def456...",
        ...             media_type=FLOE_ARTIFACT_TYPE,
        ...             size=12345
        ...         )
        ...     ]
        ... )
        >>> manifest.artifact_type
        'application/vnd.floe.compiled-artifacts.v1+json'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    digest: str = Field(
        ...,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Artifact manifest digest (SHA256)",
        examples=["sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )
    artifact_type: str = Field(
        ...,
        min_length=1,
        description="OCI artifact type (mediaType)",
        examples=[FLOE_ARTIFACT_TYPE],
    )
    size: int = Field(
        ...,
        ge=0,
        description="Total artifact size in bytes (sum of all layers)",
    )
    created_at: datetime = Field(
        ...,
        description="Artifact creation timestamp",
    )
    annotations: dict[str, str] = Field(
        default_factory=dict,
        description="OCI manifest annotations",
        examples=[
            {
                "org.opencontainers.image.created": "2026-01-19T10:00:00Z",
                "io.floe.product.name": "my-data-product",
                "io.floe.product.version": "1.0.0",
            }
        ],
    )
    layers: list[ArtifactLayer] = Field(
        ...,
        min_length=1,
        description="Content layers in the artifact",
    )
    signature_status: SignatureStatus = Field(
        default=SignatureStatus.UNSIGNED,
        description="Signature verification status (Epic 8B integration)",
    )
    promotion_status: PromotionStatus = Field(
        default=PromotionStatus.NOT_PROMOTED,
        description="Promotion workflow status (Epic 8C integration)",
    )

    @property
    def is_signed(self) -> bool:
        """Check if artifact has a valid signature."""
        return self.signature_status == SignatureStatus.VALID

    @property
    def is_promoted(self) -> bool:
        """Check if artifact has been promoted."""
        return self.promotion_status == PromotionStatus.PROMOTED

    @property
    def product_name(self) -> str | None:
        """Extract product name from annotations."""
        return self.annotations.get("io.floe.product.name")

    @property
    def product_version(self) -> str | None:
        """Extract product version from annotations."""
        return self.annotations.get("io.floe.product.version")


class ArtifactTag(BaseModel):
    """Tag reference for an artifact in a registry.

    Used in list operations to represent available tags.

    Examples:
        >>> tag = ArtifactTag(
        ...     name="v1.0.0",
        ...     digest="sha256:abc123...",
        ...     created_at=datetime.utcnow()
        ... )
        >>> tag.is_semver
        True
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="Tag name",
        examples=["v1.0.0", "latest-dev", "sha256:abc123..."],
    )
    digest: str = Field(
        ...,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Artifact digest this tag points to",
    )
    created_at: datetime = Field(
        ...,
        description="Tag creation timestamp",
    )
    size: int = Field(
        default=0,
        ge=0,
        description="Artifact size in bytes",
    )

    @property
    def is_semver(self) -> bool:
        """Check if tag follows semver pattern (immutable)."""
        return bool(re.match(r"^v?\d+\.\d+\.\d+", self.name))

    @property
    def is_mutable(self) -> bool:
        """Check if tag is mutable (can be overwritten)."""
        # Semver tags and digest references are immutable
        if self.is_semver:
            return False
        if self.name.startswith("sha256:"):
            return False
        # latest-* tags are mutable
        return True


# =============================================================================
# Cache Schemas
# =============================================================================


class CacheEntry(BaseModel):
    """Metadata for a cached OCI artifact.

    Tracks where the artifact is stored locally, when it was pulled,
    and when it expires (for mutable tags). Immutable tags (semver, digests)
    have expires_at=None and are cached indefinitely.

    The last_accessed field is used for LRU eviction when cache exceeds max size.

    Examples:
        >>> entry = CacheEntry(
        ...     digest="sha256:abc123...",
        ...     tag="v1.0.0",
        ...     registry="oci://harbor.example.com/floe",
        ...     pulled_at=_utc_now(),
        ...     expires_at=None,  # Immutable tag
        ...     size=12345,
        ...     path=Path("/var/cache/floe/oci/sha256/abc123"),
        ...     last_accessed=_utc_now()
        ... )
        >>> entry.is_expired
        False
    """

    model_config = ConfigDict(frozen=False, extra="forbid")  # Mutable for last_accessed updates

    digest: str = Field(
        ...,
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Artifact content digest (SHA256)",
        examples=["sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )
    tag: str = Field(
        ...,
        min_length=1,
        description="Tag that was pulled (e.g., v1.0.0, latest-dev)",
        examples=["v1.0.0", "latest-dev"],
    )
    registry: str = Field(
        ...,
        min_length=1,
        description="Source registry URI",
        examples=["oci://harbor.example.com/floe-platform"],
    )
    pulled_at: datetime = Field(
        ...,
        description="Timestamp when artifact was cached",
    )
    expires_at: datetime | None = Field(
        ...,
        description="TTL expiry timestamp (None for immutable tags)",
    )
    size: int = Field(
        ...,
        ge=0,
        description="Artifact size in bytes",
    )
    path: Path = Field(
        ...,
        description="Local filesystem path to cached content",
    )
    last_accessed: datetime = Field(
        ...,
        description="Last access timestamp (for LRU eviction)",
    )

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired.

        Returns True if:
        - expires_at is set AND current time is past expires_at

        Returns False if:
        - expires_at is None (immutable tag, never expires)
        - expires_at is in the future
        """
        if self.expires_at is None:
            return False
        return _utc_now() > self.expires_at

    @property
    def is_immutable(self) -> bool:
        """Check if this entry is for an immutable tag.

        Immutable tags have expires_at=None and include:
        - Semver tags (v1.0.0, v2.3.4)
        - Digest references (sha256:...)
        """
        return self.expires_at is None

    def touch(self) -> None:
        """Update last_accessed timestamp for LRU tracking."""
        self.last_accessed = _utc_now()


class CacheIndex(BaseModel):
    """Index of all cached artifacts.

    Stored as index.json in the cache directory. Maps digests to cache entries
    for fast lookup and provides aggregate statistics.

    Examples:
        >>> index = CacheIndex(
        ...     entries={"sha256:abc123...": entry},
        ...     total_size=12345,
        ...     last_updated=_utc_now()
        ... )
        >>> len(index.entries)
        1
    """

    model_config = ConfigDict(frozen=False, extra="forbid")  # Mutable for updates

    entries: dict[str, CacheEntry] = Field(
        default_factory=dict,
        description="Map of digest to cache entry",
    )
    total_size: int = Field(
        default=0,
        ge=0,
        description="Total size of all cached artifacts in bytes",
    )
    last_updated: datetime = Field(
        default_factory=_utc_now,
        description="Last index update timestamp",
    )

    def add_entry(self, entry: CacheEntry) -> None:
        """Add or update a cache entry."""
        if entry.digest in self.entries:
            # Update existing - adjust total size
            old_entry = self.entries[entry.digest]
            self.total_size -= old_entry.size
        self.entries[entry.digest] = entry
        self.total_size += entry.size
        self.last_updated = _utc_now()

    def remove_entry(self, digest: str) -> CacheEntry | None:
        """Remove a cache entry by digest."""
        if digest in self.entries:
            entry = self.entries.pop(digest)
            self.total_size -= entry.size
            self.last_updated = _utc_now()
            return entry
        return None

    def get_lru_entries(self, count: int) -> list[CacheEntry]:
        """Get the N least recently used entries.

        Only returns entries for immutable tags (mutable tags are already
        subject to TTL expiry).
        """
        immutable_entries = [e for e in self.entries.values() if e.is_immutable]
        sorted_entries = sorted(immutable_entries, key=lambda e: e.last_accessed)
        return sorted_entries[:count]

    def get_expired_entries(self) -> list[CacheEntry]:
        """Get all expired cache entries."""
        return [e for e in self.entries.values() if e.is_expired]
