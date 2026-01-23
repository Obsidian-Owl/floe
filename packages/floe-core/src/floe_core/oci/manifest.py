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


# =============================================================================
# Manifest Parsing (for inspect/list operations)
# =============================================================================


def parse_manifest_response(
    manifest_data: dict[str, Any],
    *,
    default_artifact_type: str = "application/octet-stream",
) -> ArtifactManifest:
    """Parse OCI manifest response data into ArtifactManifest.

    Converts raw manifest data from registry API response into a typed
    ArtifactManifest object. Handles both OCI v1.0 (config mediaType)
    and OCI v1.1 (artifactType) formats.

    Args:
        manifest_data: Raw manifest dictionary from registry API.
        default_artifact_type: Fallback artifact type if not specified
            in manifest. Defaults to "application/octet-stream".

    Returns:
        ArtifactManifest with parsed metadata.

    Example:
        >>> manifest_data = {"layers": [...], "annotations": {...}}
        >>> manifest = parse_manifest_response(manifest_data)
        >>> print(f"Digest: {manifest.digest}")
    """
    from floe_core.schemas.oci import SignatureStatus

    # Calculate manifest digest (sha256 of canonical JSON)
    manifest_json = json.dumps(manifest_data, separators=(",", ":"), sort_keys=True)
    manifest_digest = calculate_digest(manifest_json.encode("utf-8"))

    # Parse layers
    layers_data = manifest_data.get("layers", [])
    layers, total_size = parse_layers(layers_data)

    # Extract artifact type (OCI v1.1) or fall back to config mediaType
    artifact_type = manifest_data.get("artifactType", "")
    if not artifact_type:
        config_data = manifest_data.get("config", {})
        artifact_type = config_data.get("mediaType", default_artifact_type)

    # Extract annotations
    annotations = manifest_data.get("annotations", {})

    # Parse created timestamp from annotations
    created_at = parse_created_timestamp(annotations)

    # Build ArtifactManifest
    manifest = ArtifactManifest(
        digest=manifest_digest,
        artifact_type=artifact_type,
        size=total_size,
        created_at=created_at,
        annotations=annotations,
        layers=layers,
        signature_status=SignatureStatus.UNSIGNED,  # Placeholder for Epic 8B
    )

    logger.debug(
        "manifest_parsed",
        digest=manifest_digest,
        size=total_size,
        layer_count=len(layers),
        artifact_type=artifact_type,
    )

    return manifest


def parse_layers(
    layers_data: list[dict[str, Any]],
) -> tuple[list[ArtifactLayer], int]:
    """Parse layer data from manifest into ArtifactLayer objects.

    Args:
        layers_data: List of layer dictionaries from manifest.

    Returns:
        Tuple of (layers list, total size in bytes).

    Example:
        >>> layers_data = [{"digest": "sha256:...", "size": 1234}]
        >>> layers, total_size = parse_layers(layers_data)
        >>> len(layers)
        1
        >>> total_size
        1234
    """
    layers: list[ArtifactLayer] = []
    total_size = 0

    for layer_data in layers_data:
        layer = ArtifactLayer(
            digest=layer_data.get("digest", ""),
            media_type=layer_data.get("mediaType", ""),
            size=layer_data.get("size", 0),
            annotations=layer_data.get("annotations", {}),
        )
        layers.append(layer)
        total_size += layer.size

    return layers, total_size


def calculate_layers_total_size(
    layers_data: list[dict[str, Any]],
) -> int:
    """Calculate total size from layers data without validation.

    This is a lightweight function that sums layer sizes without
    creating ArtifactLayer objects. Use when you only need the
    total size and don't need validated layer objects.

    Args:
        layers_data: List of layer dictionaries from manifest.

    Returns:
        Total size in bytes.

    Example:
        >>> layers_data = [{"size": 1234}, {"size": 5678}]
        >>> calculate_layers_total_size(layers_data)
        6912
    """
    return sum(layer.get("size", 0) for layer in layers_data)


def parse_created_timestamp(
    annotations: dict[str, str],
) -> datetime:
    """Parse creation timestamp from manifest annotations.

    Looks for the standard OCI annotation "org.opencontainers.image.created"
    and parses it as an ISO 8601 timestamp. Falls back to current time
    if not present or invalid.

    Args:
        annotations: Manifest annotations dictionary.

    Returns:
        datetime object for the created timestamp.

    Example:
        >>> annotations = {"org.opencontainers.image.created": "2024-01-15T10:30:00Z"}
        >>> created = parse_created_timestamp(annotations)
        >>> created.year
        2024
    """
    created_str = annotations.get(
        "org.opencontainers.image.created",
        datetime.now(timezone.utc).isoformat(),
    )
    try:
        # Handle ISO format with or without Z suffix
        if created_str.endswith("Z"):
            created_str = created_str[:-1] + "+00:00"
        return datetime.fromisoformat(created_str)
    except ValueError:
        logger.warning(
            "invalid_created_timestamp",
            value=created_str,
        )
        return datetime.now(timezone.utc)


def calculate_manifest_digest(manifest_data: dict[str, Any]) -> str:
    """Calculate digest for manifest data.

    Uses canonical JSON encoding (sorted keys, minimal whitespace)
    to ensure consistent digest calculation.

    Args:
        manifest_data: Manifest dictionary.

    Returns:
        Digest string in OCI format: "sha256:<hex>"

    Example:
        >>> digest = calculate_manifest_digest({"schemaVersion": 2})
        >>> digest.startswith("sha256:")
        True
    """
    manifest_json = json.dumps(manifest_data, separators=(",", ":"), sort_keys=True)
    return calculate_digest(manifest_json.encode("utf-8"))


__all__ = [
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
]
