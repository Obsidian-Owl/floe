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

# NOTE: Exports will be populated as modules are implemented in subsequent tasks:
# - T002: errors.py (AuthenticationError, ArtifactNotFoundError, etc.)
# - T007: auth.py (AuthProvider, BasicAuthProvider, TokenAuthProvider)
# - T008-T009: resilience.py (RetryPolicy, CircuitBreaker)
# - T010: cache.py (CacheManager, CacheEntry)
# - T011: metrics.py (OpenTelemetry metrics)
# - T012: client.py (OCIClient)
# - T016: manifest.py (ArtifactManifest builder)

# Placeholder for __all__ - will be expanded as modules are implemented
__all__: list[str] = []
