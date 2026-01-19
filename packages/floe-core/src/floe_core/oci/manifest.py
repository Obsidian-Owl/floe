"""OCI Artifact Manifest builder for floe CompiledArtifacts.

This module provides functions to create OCI artifact manifests from
CompiledArtifacts objects for push operations. Complies with OCI
distribution-spec v1.1.1 and ORAS artifact specification.

Key Functions:
    build_manifest: Create ArtifactManifest from CompiledArtifacts
    calculate_digest: Calculate SHA256 digest for content
    serialize_layer: Serialize CompiledArtifacts as OCI layer

Media Type: application/vnd.floe.compiled-artifacts.v1+json

Example:
    >>> from floe_core.oci.manifest import build_manifest, serialize_layer
    >>> from floe_core.schemas.compiled_artifacts import CompiledArtifacts
    >>>
    >>> artifacts = CompiledArtifacts.from_json_file("compiled_artifacts.json")
    >>> layer_content, layer_descriptor = serialize_layer(artifacts)
    >>> manifest = build_manifest(artifacts, layers=[layer_descriptor])
    >>>
    >>> print(f"Manifest digest: {manifest.digest}")
    >>> print(f"Layer size: {layer_descriptor.size} bytes")

See Also:
    - specs/08a-oci-client/spec.md: Feature specification
    - specs/08a-oci-client/research.md: OCI specification research
    - floe_core.schemas.oci: Schema definitions
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

from floe_core.schemas.oci import (
    FLOE_ARTIFACT_TYPE,
    OCI_EMPTY_CONFIG_TYPE,
    ArtifactLayer,
    ArtifactManifest,
)

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


logger = structlog.get_logger(__name__)


def calculate_digest(content: bytes) -> str:
    """Calculate SHA256 digest for content.

    Args:
        content: Raw bytes to calculate digest for.

    Returns:
        Digest string in OCI format: "sha256:<hex>"

    Example:
        >>> digest = calculate_digest(b'{"version": "0.2.0"}')
        >>> digest
        'sha256:8b5b9db0c13db24256c829aa364aa90c6d2eba318b9232a4ab9313b954d3555f'
    """
    hash_value = hashlib.sha256(content).hexdigest()
    return f"sha256:{hash_value}"


def serialize_layer(
    artifacts: CompiledArtifacts,
    *,
    annotations: dict[str, str] | None = None,
) -> tuple[bytes, ArtifactLayer]:
    """Serialize CompiledArtifacts as an OCI artifact layer.

    Serializes the CompiledArtifacts to JSON bytes and creates an
    ArtifactLayer descriptor with digest, size, and media type.

    Args:
        artifacts: CompiledArtifacts to serialize.
        annotations: Optional layer-level annotations.

    Returns:
        Tuple of (content_bytes, layer_descriptor).

    Example:
        >>> artifacts = CompiledArtifacts(...)
        >>> content, layer = serialize_layer(artifacts)
        >>> layer.media_type
        'application/vnd.floe.compiled-artifacts.v1+json'
        >>> layer.digest.startswith('sha256:')
        True
    """
    # Serialize to JSON bytes
    json_str = artifacts.model_dump_json()
    content = json_str.encode("utf-8")

    # Calculate digest
    digest = calculate_digest(content)

    # Build layer annotations
    layer_annotations: dict[str, str] = {
        "org.opencontainers.image.title": "compiled_artifacts.json",
    }
    if annotations:
        layer_annotations.update(annotations)

    # Create layer descriptor
    layer = ArtifactLayer(
        digest=digest,
        media_type=FLOE_ARTIFACT_TYPE,
        size=len(content),
        annotations=layer_annotations,
    )

    logger.debug(
        "layer_serialized",
        digest=digest,
        size=len(content),
        media_type=FLOE_ARTIFACT_TYPE,
    )

    return content, layer


def build_manifest(
    artifacts: CompiledArtifacts,
    *,
    layers: list[ArtifactLayer] | None = None,
    annotations: dict[str, str] | None = None,
    created_at: datetime | None = None,
) -> ArtifactManifest:
    """Build an OCI ArtifactManifest from CompiledArtifacts.

    Creates a complete OCI artifact manifest ready for push operations.
    If layers are not provided, automatically serializes the artifacts
    as a single layer.

    Args:
        artifacts: CompiledArtifacts to create manifest for.
        layers: Optional pre-created layer descriptors. If None,
            artifacts are serialized as a single layer.
        annotations: Optional manifest-level annotations. Product
            metadata is automatically added.
        created_at: Optional creation timestamp. Defaults to now.

    Returns:
        ArtifactManifest ready for registry push.

    Example:
        >>> artifacts = CompiledArtifacts(...)
        >>> manifest = build_manifest(artifacts, annotations={
        ...     "custom.key": "value"
        ... })
        >>> manifest.artifact_type
        'application/vnd.floe.compiled-artifacts.v1+json'
        >>> manifest.product_name
        'test-product'
    """
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    # If no layers provided, create from artifacts
    if layers is None:
        _, layer = serialize_layer(artifacts)
        layers = [layer]

    # Calculate total size
    total_size = sum(layer.size for layer in layers)

    # Build manifest annotations
    manifest_annotations: dict[str, str] = {
        "org.opencontainers.image.created": created_at.isoformat(),
        "io.floe.product.name": artifacts.metadata.product_name,
        "io.floe.product.version": artifacts.metadata.product_version,
        "io.floe.artifacts.version": artifacts.version,
    }
    if annotations:
        manifest_annotations.update(annotations)

    # Build the manifest content for digest calculation
    # This follows OCI image manifest v2 schema
    manifest_content = _build_manifest_content(
        layers=layers,
        annotations=manifest_annotations,
    )

    # Calculate manifest digest
    manifest_bytes = json.dumps(manifest_content, sort_keys=True).encode("utf-8")
    manifest_digest = calculate_digest(manifest_bytes)

    # Create ArtifactManifest
    manifest = ArtifactManifest(
        digest=manifest_digest,
        artifact_type=FLOE_ARTIFACT_TYPE,
        size=total_size,
        created_at=created_at,
        layers=layers,
        annotations=manifest_annotations,
    )

    logger.info(
        "manifest_built",
        digest=manifest_digest,
        size=total_size,
        layer_count=len(layers),
        product_name=artifacts.metadata.product_name,
        product_version=artifacts.metadata.product_version,
    )

    return manifest


def _build_manifest_content(
    layers: list[ArtifactLayer],
    annotations: dict[str, str],
) -> dict[str, Any]:
    """Build OCI manifest JSON content for digest calculation.

    This follows the OCI image manifest schema v2 with artifactType
    extension for ORAS artifacts.

    Args:
        layers: Layer descriptors.
        annotations: Manifest annotations.

    Returns:
        Dictionary representing OCI manifest JSON.
    """
    return {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "artifactType": FLOE_ARTIFACT_TYPE,
        "config": {
            "mediaType": OCI_EMPTY_CONFIG_TYPE,
            "digest": "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
            "size": 2,
        },
        "layers": [
            {
                "mediaType": layer.media_type,
                "digest": layer.digest,
                "size": layer.size,
                "annotations": layer.annotations,
            }
            for layer in layers
        ],
        "annotations": annotations,
    }


def create_empty_config() -> tuple[bytes, str]:
    """Create the empty config blob used in ORAS artifacts.

    ORAS artifacts use an empty JSON object {} as the config blob.
    This is a well-known blob with a fixed digest.

    Returns:
        Tuple of (config_bytes, config_digest).

    Example:
        >>> content, digest = create_empty_config()
        >>> content
        b'{}'
        >>> digest
        'sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'
    """
    content = b"{}"
    digest = calculate_digest(content)
    return content, digest


__all__ = [
    "build_manifest",
    "calculate_digest",
    "create_empty_config",
    "serialize_layer",
]
