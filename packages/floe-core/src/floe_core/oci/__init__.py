"""OCI Client for floe CompiledArtifacts distribution.

This module provides an OCI-compliant artifact client for pushing, pulling,
inspecting, and listing floe CompiledArtifacts to/from OCI registries.

The client uses ORAS Python SDK for registry operations, integrates with
SecretsPlugin (Epic 7A) for authentication, and includes resilience patterns
(retry, circuit breaker), local caching, and OpenTelemetry observability.

Key Components:
- OCIClient: Main client for push/pull/inspect/list operations
- RegistryConfig: Configuration for registry endpoints (from manifest.yaml)
- ArtifactManifest: Metadata for pushed/pulled artifacts
- CacheManager: Local artifact caching with LRU eviction
- CircuitBreaker: Resilience pattern for registry availability
- RetryPolicy: Exponential backoff for transient failures

Media Type: application/vnd.floe.compiled-artifacts.v1+json

Example:
    >>> from floe_core.oci import OCIClient
    >>> from floe_core.schemas.compiled_artifacts import CompiledArtifacts
    >>>
    >>> # Create client from manifest config
    >>> client = OCIClient.from_manifest("manifest.yaml")
    >>>
    >>> # Push artifact
    >>> artifacts = CompiledArtifacts.from_json_file("target/compiled_artifacts.json")
    >>> digest = client.push(artifacts, tag="v1.0.0")
    >>>
    >>> # Pull artifact
    >>> artifacts = client.pull(tag="v1.0.0")
    >>>
    >>> # Inspect metadata
    >>> manifest = client.inspect(tag="v1.0.0")
    >>> print(f"Size: {manifest.size} bytes")
    >>>
    >>> # List available tags
    >>> tags = client.list(filter="v1.*")
    >>> for tag in tags:
    ...     print(f"{tag.name}: {tag.digest}")

See Also:
    - specs/08a-oci-client/spec.md: Feature specification
    - specs/08a-oci-client/research.md: Technology research
    - docs/architecture/: Four-layer architecture
"""

from __future__ import annotations

# Authentication providers (T007)
from floe_core.oci.auth import (
    AuthProvider,
    AzureMIAuthProvider,
    BasicAuthProvider,
    Credentials,
    GCPWIAuthProvider,
    IRSAAuthProvider,
    TokenAuthProvider,
    create_auth_provider,
)

# Cache manager (T010)
from floe_core.oci.cache import CacheManager

# Client (T012)
from floe_core.oci.client import (
    MUTABLE_TAG_PATTERNS,
    SEMVER_PATTERN,
    OCIClient,
)

# Error hierarchy (T002)
from floe_core.oci.errors import (
    ArtifactNotFoundError,
    AuthenticationError,
    CacheError,
    CircuitBreakerOpenError,
    DigestMismatchError,
    ImmutabilityViolationError,
    OCIError,
    RegistryUnavailableError,
)

# Metrics (T011)
from floe_core.oci.metrics import (
    CircuitBreakerStateValue,
    OCIMetrics,
    get_oci_metrics,
    set_oci_metrics,
)

# Resilience patterns (T008, T009)
from floe_core.oci.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryAttempt,
    RetryAttemptIterator,
    RetryPolicy,
    with_resilience,
)

# NOTE: Additional exports will be populated as modules are implemented:
# - T016: manifest.py (ArtifactManifest builder)

__all__: list[str] = [
    # Error hierarchy
    "OCIError",
    "AuthenticationError",
    "ArtifactNotFoundError",
    "ImmutabilityViolationError",
    "CircuitBreakerOpenError",
    "RegistryUnavailableError",
    "DigestMismatchError",
    "CacheError",
    # Authentication (T007)
    "AuthProvider",
    "Credentials",
    "BasicAuthProvider",
    "TokenAuthProvider",
    "IRSAAuthProvider",
    "AzureMIAuthProvider",
    "GCPWIAuthProvider",
    "create_auth_provider",
    # Resilience (T008, T009)
    "RetryPolicy",
    "RetryAttempt",
    "RetryAttemptIterator",
    "CircuitBreaker",
    "CircuitState",
    "with_resilience",
    # Cache (T010)
    "CacheManager",
    # Metrics (T011)
    "OCIMetrics",
    "CircuitBreakerStateValue",
    "get_oci_metrics",
    "set_oci_metrics",
    # Client (T012)
    "OCIClient",
    "SEMVER_PATTERN",
    "MUTABLE_TAG_PATTERNS",
]
