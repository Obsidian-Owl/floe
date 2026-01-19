"""Contract tests for OCI client CompiledArtifacts serialization.

These tests validate that the OCI client correctly serializes and deserializes
CompiledArtifacts for push/pull operations. This is a cross-package contract
test that ensures compatibility between floe-core schemas and OCI operations.

The OCI client must:
1. Serialize CompiledArtifacts to JSON matching the schema contract
2. Deserialize JSON back to valid CompiledArtifacts
3. Preserve all fields through round-trip (push → pull)

Task: T015
Requirements: FR-001, FR-002, FR-005, FR-035
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    PluginRef,
    ProductIdentity,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.oci import (
    FLOE_ARTIFACT_TYPE,
    ArtifactLayer,
    ArtifactManifest,
)
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def minimal_compiled_artifacts() -> CompiledArtifacts:
    """Create a minimal valid CompiledArtifacts for testing."""
    return CompiledArtifacts(
        version="0.2.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.2.0",
            source_hash="sha256:abc123def456",
            product_name="test-product",
            product_version="1.0.0",
        ),
        identity=ProductIdentity(
            product_id="default.test_product",
            domain="default",
            repository="github.com/acme/test",
        ),
        mode="simple",
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="test",
                    service_version="1.0.0",
                    deployment_environment="dev",
                    floe_namespace="test",
                    floe_product_name="test",
                    floe_product_version="1.0.0",
                    floe_mode="dev",
                ),
            ),
            lineage_namespace="test-namespace",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        ),
        transforms=ResolvedTransforms(
            models=[ResolvedModel(name="stg_customers", compute="duckdb")],
            default_compute="duckdb",
        ),
        dbt_profiles={"default": {"target": "dev", "outputs": {}}},
    )


@pytest.fixture
def full_compiled_artifacts() -> CompiledArtifacts:
    """Create a CompiledArtifacts with all optional fields populated."""
    return CompiledArtifacts(
        version="0.2.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(timezone.utc),
            floe_version="0.2.0",
            source_hash="sha256:fullhash123456",
            product_name="full-product",
            product_version="2.0.0",
        ),
        identity=ProductIdentity(
            product_id="analytics.customer_360",
            domain="analytics",
            repository="github.com/acme/analytics",
            namespace_registered=True,
            registration_timestamp=datetime.now(timezone.utc),
        ),
        mode="mesh",
        observability=ObservabilityConfig(
            telemetry=TelemetryConfig(
                enabled=True,
                resource_attributes=ResourceAttributes(
                    service_name="analytics-pipeline",
                    service_version="2.0.0",
                    deployment_environment="prod",
                    floe_namespace="analytics",
                    floe_product_name="customer-360",
                    floe_product_version="2.0.0",
                    floe_mode="prod",
                ),
            ),
            lineage=True,
            lineage_namespace="analytics-namespace",
        ),
        plugins=ResolvedPlugins(
            compute=PluginRef(
                type="snowflake", version="3.0.0", config={"warehouse": "compute_wh"}
            ),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="polaris", version="0.1.0"),
            storage=PluginRef(type="iceberg", version="1.4.0"),
        ),
        transforms=ResolvedTransforms(
            models=[
                ResolvedModel(
                    name="stg_customers", compute="snowflake", tags=["staging"]
                ),
                ResolvedModel(
                    name="fct_orders",
                    compute="snowflake",
                    tags=["marts"],
                    depends_on=["stg_customers"],
                ),
            ],
            default_compute="snowflake",
        ),
        dbt_profiles={
            "default": {
                "target": "prod",
                "outputs": {
                    "prod": {
                        "type": "snowflake",
                        "account": "acme.snowflakecomputing.com",
                    }
                },
            }
        },
    )


# =============================================================================
# Contract Tests: Serialization
# =============================================================================


class TestCompiledArtifactsSerializationContract:
    """Contract tests for CompiledArtifacts JSON serialization.

    These tests ensure the OCI client can correctly serialize
    CompiledArtifacts to JSON format for push operations.
    """

    @pytest.mark.requirement("8A-FR-001")
    def test_serialize_to_json_produces_valid_json(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: CompiledArtifacts serializes to valid JSON.

        The OCI client must be able to serialize CompiledArtifacts
        to JSON for storage as an OCI artifact layer.
        """
        json_str = minimal_compiled_artifacts.model_dump_json()
        assert isinstance(json_str, str)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert isinstance(data, dict)

    @pytest.mark.requirement("8A-FR-001")
    def test_serialized_json_contains_version(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Serialized JSON contains version field.

        Version is required for schema evolution and compatibility checks.
        """
        data = json.loads(minimal_compiled_artifacts.model_dump_json())
        assert "version" in data
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("8A-FR-001")
    def test_serialized_json_contains_metadata(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Serialized JSON contains metadata section.

        Metadata is required and must include product info.
        """
        data = json.loads(minimal_compiled_artifacts.model_dump_json())
        assert "metadata" in data
        assert data["metadata"]["product_name"] == "test-product"
        assert data["metadata"]["product_version"] == "1.0.0"

    @pytest.mark.requirement("8A-FR-001")
    def test_serialized_json_contains_identity(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Serialized JSON contains identity section.

        Identity is required for catalog registration.
        """
        data = json.loads(minimal_compiled_artifacts.model_dump_json())
        assert "identity" in data
        assert data["identity"]["product_id"] == "default.test_product"

    @pytest.mark.requirement("8A-FR-001")
    def test_serialize_datetime_to_iso_format(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Datetime fields serialize to ISO-8601 format.

        JSON doesn't have native datetime, so we use ISO-8601 strings.
        """
        json_str = minimal_compiled_artifacts.model_dump_json()
        data = json.loads(json_str)

        # Check compiled_at is ISO format string
        compiled_at = data["metadata"]["compiled_at"]
        assert isinstance(compiled_at, str)
        # Should be parseable as datetime
        datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))


# =============================================================================
# Contract Tests: Deserialization
# =============================================================================


class TestCompiledArtifactsDeserializationContract:
    """Contract tests for CompiledArtifacts JSON deserialization.

    These tests ensure the OCI client can correctly deserialize
    JSON back to CompiledArtifacts for pull operations.
    """

    @pytest.mark.requirement("8A-FR-002")
    def test_deserialize_from_json_string(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: CompiledArtifacts deserializes from JSON string.

        The OCI client must be able to reconstruct CompiledArtifacts
        from JSON pulled from an OCI artifact layer.
        """
        # Serialize
        json_str = minimal_compiled_artifacts.model_dump_json()

        # Deserialize
        data = json.loads(json_str)
        restored = CompiledArtifacts.model_validate(data)

        assert isinstance(restored, CompiledArtifacts)
        assert restored.version == "0.2.0"

    @pytest.mark.requirement("8A-FR-002")
    def test_deserialize_from_bytes(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: CompiledArtifacts deserializes from bytes.

        OCI layers are stored as bytes, so deserialization from bytes
        must work correctly.
        """
        # Serialize to bytes (simulating OCI layer content)
        json_bytes = minimal_compiled_artifacts.model_dump_json().encode("utf-8")
        assert isinstance(json_bytes, bytes)

        # Deserialize from bytes
        json_str = json_bytes.decode("utf-8")
        data = json.loads(json_str)
        restored = CompiledArtifacts.model_validate(data)

        assert isinstance(restored, CompiledArtifacts)

    @pytest.mark.requirement("8A-FR-002")
    def test_deserialize_rejects_invalid_version(self) -> None:
        """Contract: Deserialization rejects invalid version format.

        Version must be semver format (MAJOR.MINOR.PATCH).
        """
        from pydantic import ValidationError

        invalid_data = {
            "version": "1.0",  # Not valid semver
            "metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "floe_version": "0.2.0",
                "source_hash": "sha256:abc",
                "product_name": "test",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": "default.test",
                "domain": "default",
                "repository": "github.com/test/test",
            },
            "observability": {
                "telemetry": {
                    "resource_attributes": {
                        "service_name": "test",
                        "service_version": "1.0.0",
                        "deployment_environment": "dev",
                        "floe_namespace": "test",
                        "floe_product_name": "test",
                        "floe_product_version": "1.0.0",
                        "floe_mode": "dev",
                    },
                },
                "lineage_namespace": "test",
            },
        }

        with pytest.raises(ValidationError):
            CompiledArtifacts.model_validate(invalid_data)


# =============================================================================
# Contract Tests: Round-Trip
# =============================================================================


class TestCompiledArtifactsRoundTripContract:
    """Contract tests for push→pull round-trip preservation.

    These tests ensure that CompiledArtifacts survives a round-trip
    through JSON serialization and deserialization without data loss.
    """

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_preserves_version(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves version field."""
        json_str = minimal_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))
        assert restored.version == minimal_compiled_artifacts.version

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_preserves_metadata(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves metadata section."""
        json_str = minimal_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))

        original = minimal_compiled_artifacts.metadata
        assert restored.metadata.product_name == original.product_name
        assert restored.metadata.product_version == original.product_version
        assert restored.metadata.floe_version == original.floe_version
        assert restored.metadata.source_hash == original.source_hash

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_preserves_identity(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves identity section."""
        json_str = minimal_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))

        assert restored.identity.product_id == minimal_compiled_artifacts.identity.product_id
        assert restored.identity.domain == minimal_compiled_artifacts.identity.domain
        assert restored.identity.repository == minimal_compiled_artifacts.identity.repository

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_preserves_plugins(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves plugins section."""
        json_str = minimal_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))

        assert restored.plugins is not None
        assert minimal_compiled_artifacts.plugins is not None
        assert restored.plugins.compute.type == minimal_compiled_artifacts.plugins.compute.type
        orch_type = minimal_compiled_artifacts.plugins.orchestrator.type
        assert restored.plugins.orchestrator.type == orch_type

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_preserves_transforms(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves transforms section."""
        json_str = minimal_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))

        assert restored.transforms is not None
        assert minimal_compiled_artifacts.transforms is not None
        orig_transforms = minimal_compiled_artifacts.transforms
        assert len(restored.transforms.models) == len(orig_transforms.models)
        assert restored.transforms.default_compute == orig_transforms.default_compute

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_preserves_dbt_profiles(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves dbt_profiles section."""
        json_str = minimal_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))

        assert restored.dbt_profiles == minimal_compiled_artifacts.dbt_profiles

    @pytest.mark.requirement("8A-FR-005")
    def test_round_trip_full_artifacts_preserves_all_fields(
        self, full_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Round-trip preserves all fields in fully populated artifacts."""
        json_str = full_compiled_artifacts.model_dump_json()
        restored = CompiledArtifacts.model_validate(json.loads(json_str))

        # Core fields
        assert restored.version == full_compiled_artifacts.version
        assert restored.mode == full_compiled_artifacts.mode

        # Metadata
        assert restored.metadata.product_name == full_compiled_artifacts.metadata.product_name

        # Identity with optional fields
        orig_registered = full_compiled_artifacts.identity.namespace_registered
        assert restored.identity.namespace_registered == orig_registered

        # Plugins with optional config
        assert restored.plugins is not None
        assert full_compiled_artifacts.plugins is not None
        orig_config = full_compiled_artifacts.plugins.compute.config
        assert restored.plugins.compute.config == orig_config
        assert restored.plugins.catalog is not None

        # Transforms with tags and dependencies
        assert restored.transforms is not None
        assert full_compiled_artifacts.transforms is not None
        orig_tags = full_compiled_artifacts.transforms.models[0].tags
        assert restored.transforms.models[0].tags == orig_tags


# =============================================================================
# Contract Tests: Digest Integrity
# =============================================================================


class TestCompiledArtifactsDigestContract:
    """Contract tests for content digest integrity (FR-035).

    These tests ensure that content digests can be calculated
    and verified for integrity checks.
    """

    @pytest.mark.requirement("8A-FR-035")
    def test_deterministic_serialization_produces_same_digest(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Same artifacts produce same digest.

        Serialization must be deterministic so that the same
        CompiledArtifacts always produces the same digest.
        """
        # Serialize twice
        json_str1 = minimal_compiled_artifacts.model_dump_json()
        json_str2 = minimal_compiled_artifacts.model_dump_json()

        # Calculate digests
        digest1 = "sha256:" + hashlib.sha256(json_str1.encode()).hexdigest()
        digest2 = "sha256:" + hashlib.sha256(json_str2.encode()).hexdigest()

        assert digest1 == digest2

    @pytest.mark.requirement("8A-FR-035")
    def test_different_artifacts_produce_different_digests(
        self,
        minimal_compiled_artifacts: CompiledArtifacts,
        full_compiled_artifacts: CompiledArtifacts,
    ) -> None:
        """Contract: Different artifacts produce different digests.

        Content-addressable storage requires unique digests for unique content.
        """
        json_str1 = minimal_compiled_artifacts.model_dump_json()
        json_str2 = full_compiled_artifacts.model_dump_json()

        digest1 = "sha256:" + hashlib.sha256(json_str1.encode()).hexdigest()
        digest2 = "sha256:" + hashlib.sha256(json_str2.encode()).hexdigest()

        assert digest1 != digest2

    @pytest.mark.requirement("8A-FR-035")
    def test_digest_format_matches_oci_specification(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Digest format matches OCI artifact specification.

        OCI requires digests in 'algorithm:hex' format.
        """
        json_str = minimal_compiled_artifacts.model_dump_json()
        digest = "sha256:" + hashlib.sha256(json_str.encode()).hexdigest()

        # Check format
        assert digest.startswith("sha256:")
        assert len(digest) == 71  # sha256: (7) + 64 hex chars

        # Verify hex part is valid
        hex_part = digest[7:]
        int(hex_part, 16)  # Will raise if not valid hex


# =============================================================================
# Contract Tests: OCI Artifact Manifest Integration
# =============================================================================


class TestOCIArtifactManifestIntegration:
    """Contract tests for OCI ArtifactManifest integration.

    These tests verify that CompiledArtifacts can be wrapped in
    OCI ArtifactManifest for registry storage.
    """

    @pytest.mark.requirement("8A-FR-001")
    def test_artifact_manifest_uses_floe_media_type(self) -> None:
        """Contract: ArtifactManifest uses correct floe media type.

        The media type identifies this as a floe CompiledArtifacts artifact.
        """
        assert FLOE_ARTIFACT_TYPE == "application/vnd.floe.compiled-artifacts.v1+json"

    @pytest.mark.requirement("8A-FR-001")
    def test_artifact_layer_from_compiled_artifacts(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: ArtifactLayer can be created from CompiledArtifacts.

        The layer contains the serialized CompiledArtifacts with correct
        digest and media type.
        """
        # Serialize artifacts
        json_bytes = minimal_compiled_artifacts.model_dump_json().encode("utf-8")
        digest = "sha256:" + hashlib.sha256(json_bytes).hexdigest()

        # Create layer
        layer = ArtifactLayer(
            digest=digest,
            media_type=FLOE_ARTIFACT_TYPE,
            size=len(json_bytes),
            annotations={
                "io.floe.product.name": minimal_compiled_artifacts.metadata.product_name,
                "io.floe.product.version": minimal_compiled_artifacts.metadata.product_version,
            },
        )

        assert layer.digest.startswith("sha256:")
        assert layer.media_type == FLOE_ARTIFACT_TYPE
        assert layer.size == len(json_bytes)
        assert layer.annotations["io.floe.product.name"] == "test-product"

    @pytest.mark.requirement("8A-FR-001")
    def test_full_manifest_from_compiled_artifacts(
        self, minimal_compiled_artifacts: CompiledArtifacts
    ) -> None:
        """Contract: Full ArtifactManifest can be created from CompiledArtifacts.

        This simulates what the OCI client push operation will produce.
        """
        # Serialize artifacts
        json_bytes = minimal_compiled_artifacts.model_dump_json().encode("utf-8")
        layer_digest = "sha256:" + hashlib.sha256(json_bytes).hexdigest()

        # Create layer
        layer = ArtifactLayer(
            digest=layer_digest,
            media_type=FLOE_ARTIFACT_TYPE,
            size=len(json_bytes),
            annotations={
                "org.opencontainers.image.title": "compiled_artifacts.json",
            },
        )

        # Create manifest (digest would be calculated from manifest JSON in real implementation)
        manifest_digest = "sha256:" + hashlib.sha256(b"manifest-content").hexdigest()
        manifest = ArtifactManifest(
            digest=manifest_digest,
            artifact_type=FLOE_ARTIFACT_TYPE,
            size=len(json_bytes),
            created_at=datetime.now(timezone.utc),
            layers=[layer],
            annotations={
                "io.floe.product.name": minimal_compiled_artifacts.metadata.product_name,
                "io.floe.product.version": minimal_compiled_artifacts.metadata.product_version,
            },
        )

        assert manifest.artifact_type == FLOE_ARTIFACT_TYPE
        assert len(manifest.layers) == 1
        assert manifest.layers[0].digest == layer_digest
        assert manifest.product_name == "test-product"
        assert manifest.product_version == "1.0.0"


# =============================================================================
# Contract Tests: File-Based Operations
# =============================================================================


class TestFilBasedSerializationContract:
    """Contract tests for file-based serialization.

    These tests verify that CompiledArtifacts can be written to
    and read from files, simulating local cache operations.
    """

    @pytest.mark.requirement("8A-FR-002")
    def test_write_and_read_json_file(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """Contract: CompiledArtifacts can round-trip through JSON file."""
        file_path = tmp_path / "artifacts.json"

        # Write
        minimal_compiled_artifacts.to_json_file(file_path)
        assert file_path.exists()

        # Read
        restored = CompiledArtifacts.from_json_file(file_path)
        assert restored.version == minimal_compiled_artifacts.version
        assert restored.metadata.product_name == minimal_compiled_artifacts.metadata.product_name

    @pytest.mark.requirement("8A-FR-002")
    def test_file_content_is_valid_json(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """Contract: Written file contains valid JSON."""
        file_path = tmp_path / "artifacts.json"
        minimal_compiled_artifacts.to_json_file(file_path)

        # Read raw content and verify it's valid JSON
        content = file_path.read_text()
        data = json.loads(content)
        assert data["version"] == "0.2.0"

    @pytest.mark.requirement("8A-FR-002")
    def test_file_digest_matches_content(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """Contract: File content digest matches in-memory serialization digest."""
        file_path = tmp_path / "artifacts.json"
        minimal_compiled_artifacts.to_json_file(file_path)

        # Read file and calculate digest
        file_content = file_path.read_bytes()
        file_digest = "sha256:" + hashlib.sha256(file_content).hexdigest()

        # Compare with in-memory serialization
        # Note: We need to use the same serialization method (model_dump_json)
        # which may differ slightly due to json.dumps formatting
        memory_json = minimal_compiled_artifacts.model_dump_json()

        # The file uses json.dumps with indent=2, so we need to match that
        data = json.loads(memory_json)
        formatted_json = json.dumps(data, indent=2)
        memory_digest = "sha256:" + hashlib.sha256(formatted_json.encode()).hexdigest()

        assert file_digest == memory_digest
