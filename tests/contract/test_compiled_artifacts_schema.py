"""Contract tests for CompiledArtifacts schema stability.

These tests ensure the CompiledArtifacts schema remains stable and
backward-compatible. Breaking changes should fail these tests.

The CompiledArtifacts schema is the SOLE contract between floe-core
and downstream packages (floe-dagster, floe-dbt, etc.).

Task: T024
Requirements: FR-004
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

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
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

# Path to contract JSON Schema
CONTRACTS_DIR = Path(__file__).parent.parent.parent / "specs" / "2b-compilation-pipeline" / "contracts"
CONTRACT_SCHEMA_PATH = CONTRACTS_DIR / "compiled-artifacts.json"


@pytest.fixture
def minimal_compiled_artifacts() -> CompiledArtifacts:
    """Create a minimal valid CompiledArtifacts for testing."""
    return CompiledArtifacts(
        version="0.2.0",
        metadata=CompilationMetadata(
            compiled_at=datetime.now(),
            floe_version="0.2.0",
            source_hash="sha256:abc123",
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


class TestCompiledArtifactsSchemaContract:
    """Contract tests for CompiledArtifacts schema stability.

    These tests ensure the schema structure remains stable and that
    the contract between floe-core and downstream packages is maintained.
    """

    @pytest.mark.requirement("2B-FR-004")
    def test_version_is_0_2_0_by_default(self) -> None:
        """Contract: Default version is 0.2.0.

        This ensures downstream packages can rely on version for compatibility.
        """
        artifacts = CompiledArtifacts(
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.2.0",
                source_hash="sha256:abc123",
                product_name="test",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test",
                domain="default",
                repository="github.com/acme/test",
            ),
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
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
                lineage_namespace="test",
            ),
        )
        assert artifacts.version == "0.2.0"

    @pytest.mark.requirement("2B-FR-004")
    def test_version_format_is_semver(self) -> None:
        """Contract: Version must be valid semver (MAJOR.MINOR.PATCH).

        This ensures predictable versioning for downstream compatibility checks.
        """
        # Valid semver versions
        for version in ["0.1.0", "0.2.0", "1.0.0", "10.20.30"]:
            artifacts = CompiledArtifacts(
                version=version,
                metadata=CompilationMetadata(
                    compiled_at=datetime.now(),
                    floe_version="0.2.0",
                    source_hash="sha256:abc",
                    product_name="test",
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.test",
                    domain="default",
                    repository="github.com/test/test",
                ),
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
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
                    lineage_namespace="test",
                ),
            )
            assert artifacts.version == version

        # Invalid versions must be rejected
        with pytest.raises(ValidationError):
            CompiledArtifacts(
                version="1.0",  # Not semver
                metadata=CompilationMetadata(
                    compiled_at=datetime.now(),
                    floe_version="0.2.0",
                    source_hash="sha256:abc",
                    product_name="test",
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.test",
                    domain="default",
                    repository="github.com/test/test",
                ),
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
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
                    lineage_namespace="test",
                ),
            )

    @pytest.mark.requirement("2B-FR-004")
    def test_core_required_fields_contract(self) -> None:
        """Contract: metadata, identity, observability are required.

        These are the minimum fields that MUST be present.
        Downstream packages can rely on these always being available.
        """
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        schema = CompiledArtifacts.model_json_schema()
        required_fields = set(schema.get("required", []))

        # These are the core required fields
        assert "metadata" in required_fields
        assert "identity" in required_fields
        assert "observability" in required_fields

    @pytest.mark.requirement("2B-FR-004")
    def test_extra_properties_forbidden(self) -> None:
        """Contract: extra='forbid' prevents undocumented fields.

        This ensures the contract is strictly enforced and downstream
        packages don't accidentally rely on undocumented fields.
        """
        with pytest.raises(ValidationError) as exc_info:
            CompiledArtifacts(
                metadata=CompilationMetadata(
                    compiled_at=datetime.now(),
                    floe_version="0.2.0",
                    source_hash="sha256:abc",
                    product_name="test",
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.test",
                    domain="default",
                    repository="github.com/test/test",
                ),
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
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
                    lineage_namespace="test",
                ),
                undocumented_field="should_fail",  # type: ignore[call-arg]
            )
        assert "undocumented_field" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-004")
    def test_immutability_contract(self, minimal_compiled_artifacts: CompiledArtifacts) -> None:
        """Contract: CompiledArtifacts is immutable (frozen=True).

        Once created, CompiledArtifacts should not be modified.
        This ensures downstream packages receive a consistent view.
        """
        with pytest.raises(ValidationError):
            minimal_compiled_artifacts.version = "1.0.0"  # type: ignore[misc]

    @pytest.mark.requirement("2B-FR-004")
    def test_mode_values_contract(self) -> None:
        """Contract: mode must be one of 'simple', 'centralized', 'mesh'.

        Downstream packages use mode to determine processing behavior.
        """
        valid_modes = ["simple", "centralized", "mesh"]

        for mode in valid_modes:
            artifacts = CompiledArtifacts(
                mode=mode,  # type: ignore[arg-type]
                metadata=CompilationMetadata(
                    compiled_at=datetime.now(),
                    floe_version="0.2.0",
                    source_hash="sha256:abc",
                    product_name="test",
                    product_version="1.0.0",
                ),
                identity=ProductIdentity(
                    product_id="default.test",
                    domain="default",
                    repository="github.com/test/test",
                ),
                observability=ObservabilityConfig(
                    telemetry=TelemetryConfig(
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
                    lineage_namespace="test",
                ),
            )
            assert artifacts.mode == mode

    @pytest.mark.requirement("2B-FR-004")
    def test_plugins_structure_contract(self, minimal_compiled_artifacts: CompiledArtifacts) -> None:
        """Contract: plugins contains compute and orchestrator (required).

        When present, plugins MUST have compute and orchestrator.
        Optional plugins (catalog, storage, etc.) may be None.
        """
        assert minimal_compiled_artifacts.plugins is not None
        assert minimal_compiled_artifacts.plugins.compute is not None
        assert minimal_compiled_artifacts.plugins.orchestrator is not None
        assert minimal_compiled_artifacts.plugins.compute.type == "duckdb"
        assert minimal_compiled_artifacts.plugins.orchestrator.type == "dagster"

    @pytest.mark.requirement("2B-FR-004")
    def test_transforms_structure_contract(self, minimal_compiled_artifacts: CompiledArtifacts) -> None:
        """Contract: transforms contains models list and default_compute.

        When present, transforms MUST have at least one model
        and a default_compute target.
        """
        assert minimal_compiled_artifacts.transforms is not None
        assert len(minimal_compiled_artifacts.transforms.models) >= 1
        assert minimal_compiled_artifacts.transforms.default_compute is not None

        # Each model must have name and compute (never None)
        for model in minimal_compiled_artifacts.transforms.models:
            assert model.name is not None
            assert model.compute is not None

    @pytest.mark.requirement("2B-FR-004")
    def test_dbt_profiles_structure_contract(self, minimal_compiled_artifacts: CompiledArtifacts) -> None:
        """Contract: dbt_profiles is a dictionary.

        When present, dbt_profiles is used directly by dbt.
        Structure follows dbt profiles.yml format.
        """
        assert minimal_compiled_artifacts.dbt_profiles is not None
        assert isinstance(minimal_compiled_artifacts.dbt_profiles, dict)

    @pytest.mark.requirement("2B-FR-004")
    def test_v020_fields_backward_compatible(self) -> None:
        """Contract: v0.2.0 fields (plugins, transforms, etc.) are optional.

        For backward compatibility, new v0.2.0 fields must be optional.
        v0.1.0 artifacts (without these fields) should still validate.
        """
        # This should work without plugins, transforms, dbt_profiles, governance
        artifacts = CompiledArtifacts(
            version="0.2.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.2.0",
                source_hash="sha256:abc",
                product_name="test",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.test",
                domain="default",
                repository="github.com/test/test",
            ),
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
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
                lineage_namespace="test",
            ),
            # Explicitly NOT providing plugins, transforms, dbt_profiles, governance
        )
        assert artifacts.plugins is None
        assert artifacts.transforms is None
        assert artifacts.dbt_profiles is None
        assert artifacts.governance is None

    @pytest.mark.requirement("2B-FR-004")
    def test_json_schema_export(self) -> None:
        """Contract: CompiledArtifacts can export JSON Schema.

        This enables IDE autocomplete and external validation.
        """
        schema = CompiledArtifacts.model_json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "version" in schema["properties"]
        assert "metadata" in schema["properties"]
        assert "identity" in schema["properties"]
        assert "observability" in schema["properties"]

    @pytest.mark.requirement("2B-FR-004")
    def test_serialization_round_trip(self, minimal_compiled_artifacts: CompiledArtifacts) -> None:
        """Contract: CompiledArtifacts can serialize to JSON and back.

        This ensures the contract can be passed between processes.
        """
        # Serialize to JSON
        json_str = minimal_compiled_artifacts.model_dump_json()
        assert isinstance(json_str, str)

        # Parse back
        data = json.loads(json_str)
        restored = CompiledArtifacts.model_validate(data)

        # Verify key fields are preserved
        assert restored.version == minimal_compiled_artifacts.version
        assert restored.mode == minimal_compiled_artifacts.mode
        assert restored.metadata.product_name == minimal_compiled_artifacts.metadata.product_name
        assert restored.identity.product_id == minimal_compiled_artifacts.identity.product_id


class TestResolvedPluginsContract:
    """Contract tests for ResolvedPlugins structure."""

    @pytest.mark.requirement("2B-FR-004")
    def test_compute_orchestrator_required(self) -> None:
        """Contract: compute and orchestrator are required in ResolvedPlugins."""
        # Both required - should work
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        )
        assert plugins.compute.type == "duckdb"
        assert plugins.orchestrator.type == "dagster"

        # Missing compute - should fail
        with pytest.raises(ValidationError):
            ResolvedPlugins(orchestrator=PluginRef(type="dagster", version="1.5.0"))  # type: ignore[call-arg]

        # Missing orchestrator - should fail
        with pytest.raises(ValidationError):
            ResolvedPlugins(compute=PluginRef(type="duckdb", version="0.9.0"))  # type: ignore[call-arg]

    @pytest.mark.requirement("2B-FR-004")
    def test_optional_plugins_contract(self) -> None:
        """Contract: catalog, storage, ingestion, semantic are optional."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            # catalog, storage, ingestion, semantic not provided
        )
        assert plugins.catalog is None
        assert plugins.storage is None
        assert plugins.ingestion is None
        assert plugins.semantic is None


class TestPluginRefContract:
    """Contract tests for PluginRef structure."""

    @pytest.mark.requirement("2B-FR-004")
    def test_plugin_ref_structure(self) -> None:
        """Contract: PluginRef has type, version, and optional config."""
        ref = PluginRef(
            type="duckdb",
            version="0.9.0",
            config={"threads": 4},
        )
        assert ref.type == "duckdb"
        assert ref.version == "0.9.0"
        assert ref.config == {"threads": 4}

    @pytest.mark.requirement("2B-FR-004")
    def test_version_must_be_semver(self) -> None:
        """Contract: PluginRef version must be semver."""
        with pytest.raises(ValidationError):
            PluginRef(type="duckdb", version="0.9")  # Not semver


class TestFileSerializationMethods:
    """Contract tests for file-based serialization methods.

    Tests T056, T057, T058 - file methods on CompiledArtifacts.
    """

    @pytest.mark.requirement("2B-FR-004")
    def test_to_json_file_writes_valid_json(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """T056: to_json_file writes valid JSON."""
        output_path = tmp_path / "artifacts.json"

        minimal_compiled_artifacts.to_json_file(output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["version"] == "0.2.0"
        assert "metadata" in data
        assert "plugins" in data

    @pytest.mark.requirement("2B-FR-004")
    def test_to_json_file_creates_parent_dirs(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """T056: to_json_file creates parent directories."""
        output_path = tmp_path / "deeply" / "nested" / "dir" / "artifacts.json"

        minimal_compiled_artifacts.to_json_file(output_path)

        assert output_path.exists()

    @pytest.mark.requirement("2B-FR-004")
    def test_from_json_file_loads_artifacts(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """T057: from_json_file loads CompiledArtifacts."""
        output_path = tmp_path / "artifacts.json"
        minimal_compiled_artifacts.to_json_file(output_path)

        loaded = CompiledArtifacts.from_json_file(output_path)

        assert loaded.version == minimal_compiled_artifacts.version
        assert loaded.metadata.product_name == minimal_compiled_artifacts.metadata.product_name
        assert loaded.mode == minimal_compiled_artifacts.mode

    @pytest.mark.requirement("2B-FR-004")
    def test_from_json_file_raises_on_missing_file(self, tmp_path: Path) -> None:
        """T057: from_json_file raises FileNotFoundError."""
        missing_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            CompiledArtifacts.from_json_file(missing_path)

    @pytest.mark.requirement("2B-FR-004")
    def test_from_json_file_raises_on_invalid_json(self, tmp_path: Path) -> None:
        """T057: from_json_file raises ValidationError on invalid JSON."""
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text('{"version": "invalid"}')  # Missing required fields

        with pytest.raises(ValidationError):
            CompiledArtifacts.from_json_file(invalid_path)

    @pytest.mark.requirement("2B-FR-004")
    def test_file_round_trip_preserves_data(
        self, minimal_compiled_artifacts: CompiledArtifacts, tmp_path: Path
    ) -> None:
        """T053: File round-trip preserves all data."""
        output_path = tmp_path / "roundtrip.json"

        # Write
        minimal_compiled_artifacts.to_json_file(output_path)

        # Read
        loaded = CompiledArtifacts.from_json_file(output_path)

        # Verify all fields preserved
        assert loaded.version == minimal_compiled_artifacts.version
        assert loaded.mode == minimal_compiled_artifacts.mode
        assert loaded.metadata.product_name == minimal_compiled_artifacts.metadata.product_name
        assert loaded.metadata.source_hash == minimal_compiled_artifacts.metadata.source_hash
        assert loaded.identity.product_id == minimal_compiled_artifacts.identity.product_id
        assert loaded.plugins is not None
        assert loaded.plugins.compute.type == "duckdb"
        assert loaded.transforms is not None
        assert len(loaded.transforms.models) == 1

    @pytest.mark.requirement("2B-FR-004")
    def test_export_json_schema_includes_metadata(self) -> None:
        """T058: export_json_schema includes $schema and $id."""
        schema = CompiledArtifacts.export_json_schema()

        assert "$schema" in schema
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert "$id" in schema
        assert "floe.dev" in schema["$id"]

    @pytest.mark.requirement("2B-FR-004")
    def test_export_json_schema_has_properties(self) -> None:
        """T058: export_json_schema has all expected properties."""
        schema = CompiledArtifacts.export_json_schema()

        assert "properties" in schema
        props = schema["properties"]
        assert "version" in props
        assert "metadata" in props
        assert "identity" in props
        assert "observability" in props
        assert "plugins" in props
        assert "transforms" in props
