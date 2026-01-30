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

# Attestation (Epic 8B)
from floe_core.oci.attestation import (
    IN_TOTO_STATEMENT_TYPE,
    SPDX_PREDICATE_TYPE,
    AttestationAttachError,
    AttestationError,
    CosignNotFoundError,
    SBOMGenerationError,
    SyftNotFoundError,
    attach_attestation,
    check_cosign_available,
    check_syft_available,
    create_in_toto_statement,
    generate_sbom,
    generate_sbom_for_python_project,
    retrieve_attestations,
    retrieve_sbom,
)

# Authentication providers (T007)
from floe_core.oci.auth import (
    AnonymousAuthProvider,
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
from floe_core.oci.client import OCIClient

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

# Layer helpers (T044 - extracted from client.py)
from floe_core.oci.layers import (
    MUTABLE_TAG_PATTERNS,
    SEMVER_PATTERN,
    PullOperations,
    PushOperations,
    TagClassifier,
    URIParser,
    create_temp_layer_files,
)

# Manifest operations (T016, T043)
from floe_core.oci.manifest import (
    # Build operations (push)
    build_manifest,
    calculate_digest,
    # Parse operations (pull/inspect)
    calculate_layers_total_size,
    calculate_manifest_digest,
    create_empty_config,
    parse_created_timestamp,
    parse_layers,
    parse_manifest_response,
    serialize_layer,
)

# Metrics (T011)
from floe_core.oci.metrics import (
    CircuitBreakerStateValue,
    OCIMetrics,
    get_oci_metrics,
    set_oci_metrics,
)

# Promotion (Epic 8C)
from floe_core.oci.promotion import PromotionController

# Resilience patterns (T008, T009)
from floe_core.oci.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryAttempt,
    RetryAttemptIterator,
    RetryPolicy,
    with_resilience,
)

# Signing (Epic 8B)
from floe_core.oci.signing import (
    ANNOTATION_BUNDLE,
    ANNOTATION_CERT_FINGERPRINT,
    ANNOTATION_ISSUER,
    ANNOTATION_MODE,
    ANNOTATION_REKOR_INDEX,
    ANNOTATION_SIGNED_AT,
    ANNOTATION_SUBJECT,
    OIDCTokenError,
    SigningClient,
    SigningError,
    sign_artifact,
)

# Verification (Epic 8B)
from floe_core.oci.verification import (
    PolicyViolationError,
    VerificationClient,
    VerificationError,
    load_verification_policy_from_manifest,
    verify_artifact,
)

# Configuration schemas (from floe_core.schemas.oci)
from floe_core.schemas.oci import (
    ArtifactManifest,
    ArtifactTag,
    CacheConfig,
    RegistryConfig,
)

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
    "AnonymousAuthProvider",
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
    # Layer helpers (T044)
    "SEMVER_PATTERN",
    "MUTABLE_TAG_PATTERNS",
    "TagClassifier",
    "URIParser",
    "PullOperations",
    "PushOperations",
    "create_temp_layer_files",
    # Manifest operations (T016, T043)
    # Build operations (push)
    "build_manifest",
    "calculate_digest",
    "create_empty_config",
    "serialize_layer",
    # Parse operations (pull/inspect)
    "calculate_layers_total_size",
    "calculate_manifest_digest",
    "parse_created_timestamp",
    "parse_layers",
    "parse_manifest_response",
    # Configuration schemas
    "RegistryConfig",
    "CacheConfig",
    "ArtifactManifest",
    "ArtifactTag",
    # Signing (Epic 8B)
    "SigningClient",
    "SigningError",
    "OIDCTokenError",
    "sign_artifact",
    "ANNOTATION_BUNDLE",
    "ANNOTATION_MODE",
    "ANNOTATION_ISSUER",
    "ANNOTATION_SUBJECT",
    "ANNOTATION_SIGNED_AT",
    "ANNOTATION_REKOR_INDEX",
    "ANNOTATION_CERT_FINGERPRINT",
    # Verification (Epic 8B)
    "VerificationClient",
    "VerificationError",
    "PolicyViolationError",
    "load_verification_policy_from_manifest",
    "verify_artifact",
    # Attestation (Epic 8B)
    "IN_TOTO_STATEMENT_TYPE",
    "SPDX_PREDICATE_TYPE",
    "AttestationAttachError",
    "AttestationError",
    "CosignNotFoundError",
    "SBOMGenerationError",
    "SyftNotFoundError",
    "attach_attestation",
    "check_cosign_available",
    "check_syft_available",
    "create_in_toto_statement",
    "generate_sbom",
    "generate_sbom_for_python_project",
    "retrieve_attestations",
    "retrieve_sbom",
    # Promotion (Epic 8C)
    "PromotionController",
]
