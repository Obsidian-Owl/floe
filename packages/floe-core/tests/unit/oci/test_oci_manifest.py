"""Unit tests for OCI manifest creation.

Tests for ArtifactManifest builder functionality including:
- Manifest creation from CompiledArtifacts
- Layer digest calculation (SHA256)
- Media type validation
- Annotation handling

Task: T014
Requirements: FR-040, FR-041
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from floe_core.schemas.oci import (
    FLOE_ARTIFACT_TYPE,
    OCI_EMPTY_CONFIG_TYPE,
    ArtifactLayer,
    ArtifactManifest,
    SignatureStatus,
)

if TYPE_CHECKING:
    from floe_core.schemas.compiled_artifacts import CompiledArtifacts


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_layer_content() -> bytes:
    """Return sample layer content for digest calculation."""
    return b'{"version": "0.2.0", "metadata": {"product_name": "test"}}'


@pytest.fixture
def sample_layer_digest(sample_layer_content: bytes) -> str:
    """Return the SHA256 digest of sample layer content."""
    return "sha256:" + hashlib.sha256(sample_layer_content).hexdigest()


@pytest.fixture
def sample_artifact_layer(sample_layer_digest: str) -> ArtifactLayer:
    """Create a sample ArtifactLayer for testing."""
    return ArtifactLayer(
        digest=sample_layer_digest,
        media_type=FLOE_ARTIFACT_TYPE,
        size=1234,
        annotations={"org.opencontainers.image.title": "compiled_artifacts.json"},
    )


@pytest.fixture
def sample_artifact_manifest(sample_artifact_layer: ArtifactLayer) -> ArtifactManifest:
    """Create a sample ArtifactManifest for testing."""
    return ArtifactManifest(
        digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        artifact_type=FLOE_ARTIFACT_TYPE,
        size=1234,
        created_at=datetime.now(timezone.utc),
        layers=[sample_artifact_layer],
        annotations={
            "org.opencontainers.image.created": "2026-01-19T10:00:00Z",
            "io.floe.product.name": "test-product",
            "io.floe.product.version": "1.0.0",
        },
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestArtifactManifestCreation:
    """Tests for ArtifactManifest creation and validation (FR-040)."""

    @pytest.mark.requirement("8A-FR-040")
    def test_create_artifact_manifest_with_required_fields(
        self, sample_artifact_layer: ArtifactLayer
    ) -> None:
        """Test ArtifactManifest creation with all required fields.

        Validates that an ArtifactManifest can be created with the minimum
        required fields and returns a valid manifest object.
        """
        manifest = ArtifactManifest(
            digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            artifact_type=FLOE_ARTIFACT_TYPE,
            size=1234,
            created_at=datetime.now(timezone.utc),
            layers=[sample_artifact_layer],
        )

        assert manifest.digest.startswith("sha256:")
        assert manifest.artifact_type == FLOE_ARTIFACT_TYPE
        assert manifest.size == 1234
        assert len(manifest.layers) == 1
        assert manifest.signature_status == SignatureStatus.UNSIGNED

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_media_type_is_floe_type(
        self, sample_artifact_manifest: ArtifactManifest
    ) -> None:
        """Test that artifact type is the floe CompiledArtifacts media type.

        Validates that the artifact_type field uses the correct media type:
        application/vnd.floe.compiled-artifacts.v1+json
        """
        assert (
            sample_artifact_manifest.artifact_type
            == "application/vnd.floe.compiled-artifacts.v1+json"
        )

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_annotations(
        self, sample_artifact_manifest: ArtifactManifest
    ) -> None:
        """Test ArtifactManifest annotations contain expected fields.

        Validates that annotations include product metadata.
        """
        assert "io.floe.product.name" in sample_artifact_manifest.annotations
        assert "io.floe.product.version" in sample_artifact_manifest.annotations
        assert (
            sample_artifact_manifest.annotations["io.floe.product.name"]
            == "test-product"
        )
        assert (
            sample_artifact_manifest.annotations["io.floe.product.version"] == "1.0.0"
        )

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_product_name_property(
        self, sample_artifact_manifest: ArtifactManifest
    ) -> None:
        """Test product_name property extracts from annotations."""
        assert sample_artifact_manifest.product_name == "test-product"

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_product_version_property(
        self, sample_artifact_manifest: ArtifactManifest
    ) -> None:
        """Test product_version property extracts from annotations."""
        assert sample_artifact_manifest.product_version == "1.0.0"

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_is_signed_property_unsigned(
        self, sample_artifact_manifest: ArtifactManifest
    ) -> None:
        """Test is_signed property returns False for unsigned manifests."""
        assert sample_artifact_manifest.is_signed is False

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_is_signed_property_valid(
        self, sample_artifact_layer: ArtifactLayer
    ) -> None:
        """Test is_signed property returns True for signed manifests."""
        manifest = ArtifactManifest(
            digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            artifact_type=FLOE_ARTIFACT_TYPE,
            size=1234,
            created_at=datetime.now(timezone.utc),
            layers=[sample_artifact_layer],
            signature_status=SignatureStatus.VALID,
        )
        assert manifest.is_signed is True


class TestLayerDigestCalculation:
    """Tests for layer digest calculation (FR-041)."""

    @pytest.mark.requirement("8A-FR-041")
    def test_layer_digest_is_sha256(self, sample_layer_content: bytes) -> None:
        """Test that layer digests use SHA256 algorithm.

        Validates that content digests are calculated using SHA256 and
        use the sha256: prefix format.
        """
        digest = "sha256:" + hashlib.sha256(sample_layer_content).hexdigest()
        assert digest.startswith("sha256:")
        assert len(digest) == 71  # sha256: (7) + 64 hex chars

    @pytest.mark.requirement("8A-FR-041")
    def test_layer_digest_matches_content(
        self, sample_layer_content: bytes, sample_layer_digest: str
    ) -> None:
        """Test that calculated digest matches expected value.

        Validates that SHA256 digest calculation is deterministic and
        produces the expected value for given content.
        """
        calculated_digest = "sha256:" + hashlib.sha256(sample_layer_content).hexdigest()
        assert calculated_digest == sample_layer_digest

    @pytest.mark.requirement("8A-FR-041")
    def test_layer_digest_different_for_different_content(self) -> None:
        """Test that different content produces different digests.

        Validates that digest calculation is content-dependent.
        """
        content1 = b'{"version": "0.1.0"}'
        content2 = b'{"version": "0.2.0"}'

        digest1 = "sha256:" + hashlib.sha256(content1).hexdigest()
        digest2 = "sha256:" + hashlib.sha256(content2).hexdigest()

        assert digest1 != digest2

    @pytest.mark.requirement("8A-FR-041")
    def test_artifact_layer_digest_validation(self) -> None:
        """Test that ArtifactLayer validates digest format.

        Validates that only valid sha256: prefixed digests are accepted.
        """
        from pydantic import ValidationError

        # Valid digest
        layer = ArtifactLayer(
            digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            media_type=FLOE_ARTIFACT_TYPE,
            size=100,
        )
        assert layer.digest.startswith("sha256:")

        # Invalid digest (wrong prefix)
        with pytest.raises(ValidationError, match="digest"):
            ArtifactLayer(
                digest="md5:d41d8cd98f00b204e9800998ecf8427e",
                media_type=FLOE_ARTIFACT_TYPE,
                size=100,
            )

        # Invalid digest (wrong length)
        with pytest.raises(ValidationError, match="digest"):
            ArtifactLayer(
                digest="sha256:abc123",
                media_type=FLOE_ARTIFACT_TYPE,
                size=100,
            )


class TestArtifactLayerCreation:
    """Tests for ArtifactLayer creation and validation."""

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_layer_with_annotations(self) -> None:
        """Test ArtifactLayer creation with annotations."""
        layer = ArtifactLayer(
            digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            media_type=FLOE_ARTIFACT_TYPE,
            size=12345,
            annotations={
                "org.opencontainers.image.title": "compiled_artifacts.json",
                "custom.annotation": "value",
            },
        )

        assert (
            layer.annotations["org.opencontainers.image.title"]
            == "compiled_artifacts.json"
        )
        assert layer.annotations["custom.annotation"] == "value"

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_layer_media_type_validation(self) -> None:
        """Test that ArtifactLayer requires non-empty media type."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="media_type"):
            ArtifactLayer(
                digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                media_type="",  # Empty media type
                size=100,
            )


class TestOCIConstants:
    """Tests for OCI media type constants."""

    @pytest.mark.requirement("8A-FR-040")
    def test_floe_artifact_type_constant(self) -> None:
        """Test FLOE_ARTIFACT_TYPE constant value."""
        assert FLOE_ARTIFACT_TYPE == "application/vnd.floe.compiled-artifacts.v1+json"

    @pytest.mark.requirement("8A-FR-040")
    def test_oci_empty_config_type_constant(self) -> None:
        """Test OCI_EMPTY_CONFIG_TYPE constant value."""
        assert OCI_EMPTY_CONFIG_TYPE == "application/vnd.oci.empty.v1+json"


class TestArtifactManifestValidation:
    """Tests for ArtifactManifest validation."""

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_requires_at_least_one_layer(self) -> None:
        """Test that ArtifactManifest requires at least one layer."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="layers"):
            ArtifactManifest(
                digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                artifact_type=FLOE_ARTIFACT_TYPE,
                size=0,
                created_at=datetime.now(timezone.utc),
                layers=[],  # Empty layers
            )

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_immutability(
        self, sample_artifact_manifest: ArtifactManifest
    ) -> None:
        """Test that ArtifactManifest is immutable (frozen=True)."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            sample_artifact_manifest.size = 9999

    @pytest.mark.requirement("8A-FR-040")
    def test_artifact_manifest_rejects_extra_fields(
        self, sample_artifact_layer: ArtifactLayer
    ) -> None:
        """Test that ArtifactManifest rejects undocumented fields."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="extra"):
            ArtifactManifest(
                digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                artifact_type=FLOE_ARTIFACT_TYPE,
                size=1234,
                created_at=datetime.now(timezone.utc),
                layers=[sample_artifact_layer],
                undocumented_field="should_fail",  # type: ignore[call-arg]
            )


class TestManifestBuilder:
    """Tests for manifest builder functionality (T016).

    Tests the build_manifest(), serialize_layer(), and calculate_digest()
    functions that create OCI artifact manifests from CompiledArtifacts.
    """

    @pytest.mark.requirement("8A-FR-040")
    def test_build_manifest_from_compiled_artifacts(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Test manifest builder creates valid manifest from artifacts.

        Verifies that build_manifest() creates an ArtifactManifest with:
        - Correct artifact type (floe media type)
        - Valid digest format
        - Product metadata in annotations
        """
        from floe_core.oci.manifest import build_manifest

        manifest = build_manifest(sample_compiled_artifacts)

        assert manifest.artifact_type == FLOE_ARTIFACT_TYPE
        assert manifest.digest.startswith("sha256:")
        assert len(manifest.digest) == 71  # sha256: + 64 hex chars
        assert manifest.product_name == sample_compiled_artifacts.metadata.product_name
        assert (
            manifest.product_version
            == sample_compiled_artifacts.metadata.product_version
        )

    @pytest.mark.requirement("8A-FR-041")
    def test_build_manifest_calculates_layer_digest(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Test manifest builder calculates correct layer digest.

        Verifies that the SHA256 digest of the serialized CompiledArtifacts
        matches the digest in the layer descriptor.
        """
        from floe_core.oci.manifest import build_manifest

        manifest = build_manifest(sample_compiled_artifacts)

        # Verify digest calculation matches manual calculation
        serialized = sample_compiled_artifacts.model_dump_json()
        expected_digest = "sha256:" + hashlib.sha256(serialized.encode()).hexdigest()
        assert manifest.layers[0].digest == expected_digest

    @pytest.mark.requirement("8A-FR-040")
    def test_serialize_layer_creates_valid_layer(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Test serialize_layer creates layer with correct metadata."""
        from floe_core.oci.manifest import serialize_layer

        content, layer = serialize_layer(sample_compiled_artifacts)

        assert isinstance(content, bytes)
        assert layer.media_type == FLOE_ARTIFACT_TYPE
        assert layer.size == len(content)
        assert layer.digest.startswith("sha256:")
        assert "org.opencontainers.image.title" in layer.annotations

    @pytest.mark.requirement("8A-FR-041")
    def test_calculate_digest_produces_valid_sha256(self) -> None:
        """Test calculate_digest produces valid SHA256 format."""
        from floe_core.oci.manifest import calculate_digest

        content = b'{"test": "data"}'
        digest = calculate_digest(content)

        assert digest.startswith("sha256:")
        assert len(digest) == 71
        # Verify it matches hashlib calculation
        expected = "sha256:" + hashlib.sha256(content).hexdigest()
        assert digest == expected

    @pytest.mark.requirement("8A-FR-040")
    def test_build_manifest_includes_annotations(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Test manifest includes required OCI annotations."""
        from floe_core.oci.manifest import build_manifest

        manifest = build_manifest(sample_compiled_artifacts)

        # Check required annotations
        assert "org.opencontainers.image.created" in manifest.annotations
        assert "io.floe.product.name" in manifest.annotations
        assert "io.floe.product.version" in manifest.annotations
        assert "io.floe.artifacts.version" in manifest.annotations

    @pytest.mark.requirement("8A-FR-040")
    def test_build_manifest_with_custom_annotations(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Test manifest builder accepts custom annotations."""
        from floe_core.oci.manifest import build_manifest

        custom_annotations = {
            "custom.annotation": "custom-value",
            "another.annotation": "another-value",
        }
        manifest = build_manifest(
            sample_compiled_artifacts,
            annotations=custom_annotations,
        )

        assert manifest.annotations["custom.annotation"] == "custom-value"
        assert manifest.annotations["another.annotation"] == "another-value"
        # Standard annotations should still be present
        assert "io.floe.product.name" in manifest.annotations

    @pytest.mark.requirement("8A-FR-040")
    def test_create_empty_config_produces_well_known_digest(self) -> None:
        """Test empty config has well-known ORAS digest."""
        from floe_core.oci.manifest import create_empty_config

        content, digest = create_empty_config()

        assert content == b"{}"
        # This is the well-known digest for empty JSON object
        expected = (
            "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
        )
        assert digest == expected

    @pytest.mark.requirement("8A-FR-040")
    def test_serialize_layer_with_custom_annotations(
        self, sample_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Test serialize_layer accepts custom layer annotations."""
        from floe_core.oci.manifest import serialize_layer

        custom_annotations = {"custom.layer": "value"}
        _, layer = serialize_layer(
            sample_compiled_artifacts,
            annotations=custom_annotations,
        )

        assert layer.annotations["custom.layer"] == "value"
        # Default annotation should still be present
        assert "org.opencontainers.image.title" in layer.annotations
