"""Unit tests for CompiledArtifacts extension models.

Tests validation of CompiledArtifacts v0.2.0 extensions including:
- PluginRef model
- ResolvedPlugins model
- ResolvedModel model
- ResolvedTransforms model
- ResolvedGovernance model
- Extended CompiledArtifacts fields
- YAML serialization (T060)

Task: T023, T060
Requirements: FR-003, FR-007, FR-011
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.compiled_artifacts import (
    CompilationMetadata,
    CompiledArtifacts,
    ObservabilityConfig,
    PluginRef,
    ProductIdentity,
    ResolvedGovernance,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
)
from floe_core.schemas.versions import COMPILED_ARTIFACTS_VERSION
from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig


@pytest.fixture
def sample_telemetry_config() -> TelemetryConfig:
    """Create a sample TelemetryConfig for testing."""
    return TelemetryConfig(
        enabled=True,
        resource_attributes=ResourceAttributes(
            service_name="test-pipeline",
            service_version="1.0.0",
            deployment_environment="dev",
            floe_namespace="test",
            floe_product_name="test-product",
            floe_product_version="1.0.0",
            floe_mode="dev",
        ),
    )


@pytest.fixture
def sample_observability_config(sample_telemetry_config: TelemetryConfig) -> ObservabilityConfig:
    """Create a sample ObservabilityConfig for testing."""
    return ObservabilityConfig(
        telemetry=sample_telemetry_config,
        lineage=True,
        lineage_namespace="test-namespace",
    )


@pytest.fixture
def sample_compilation_metadata() -> CompilationMetadata:
    """Create a sample CompilationMetadata for testing."""
    return CompilationMetadata(
        compiled_at=datetime.now(),
        floe_version=COMPILED_ARTIFACTS_VERSION,
        source_hash="sha256:abc123",
        product_name="test-product",
        product_version="1.0.0",
    )


@pytest.fixture
def sample_product_identity() -> ProductIdentity:
    """Create a sample ProductIdentity for testing."""
    return ProductIdentity(
        product_id="default.test_product",
        domain="default",
        repository="github.com/acme/test",
    )


class TestPluginRef:
    """Tests for PluginRef model validation."""

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_plugin_ref_minimal(self) -> None:
        """Test that minimal valid PluginRef is accepted."""
        ref = PluginRef(type="duckdb", version="0.9.0")
        assert ref.type == "duckdb"
        assert ref.version == "0.9.0"
        assert ref.config is None

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_plugin_ref_with_config(self) -> None:
        """Test that PluginRef with config is accepted."""
        ref = PluginRef(
            type="duckdb",
            version="0.9.0",
            config={"threads": 4, "memory_limit": "8GB"},
        )
        assert ref.type == "duckdb"
        assert ref.version == "0.9.0"
        assert ref.config == {"threads": 4, "memory_limit": "8GB"}

    @pytest.mark.requirement("2B-FR-007")
    def test_invalid_version_not_semver(self) -> None:
        """Test that non-semver version is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginRef(type="duckdb", version="0.9")
        assert "version" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_invalid_type_empty(self) -> None:
        """Test that empty type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PluginRef(type="", version="0.9.0")
        assert "type" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_frozen_immutable(self) -> None:
        """Test that PluginRef is immutable (frozen=True)."""
        ref = PluginRef(type="duckdb", version="0.9.0")
        with pytest.raises(ValidationError):
            ref.type = "snowflake"  # type: ignore[misc]


class TestResolvedPlugins:
    """Tests for ResolvedPlugins model validation."""

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_resolved_plugins_required_only(self) -> None:
        """Test that ResolvedPlugins with required plugins is accepted."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        )
        assert plugins.compute.type == "duckdb"
        assert plugins.orchestrator.type == "dagster"
        assert plugins.catalog is None
        assert plugins.storage is None

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_resolved_plugins_all(self) -> None:
        """Test that ResolvedPlugins with all plugins is accepted."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="polaris", version="0.1.0"),
            storage=PluginRef(type="s3", version="1.0.0"),
            ingestion=PluginRef(type="dlt", version="0.4.0"),
            semantic=PluginRef(type="cube", version="0.35.0"),
        )
        assert plugins.compute.type == "duckdb"
        assert plugins.catalog is not None
        assert plugins.catalog.type == "polaris"

    @pytest.mark.requirement("2B-FR-007")
    def test_missing_compute_rejected(self) -> None:
        """Test that missing required compute plugin is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedPlugins(
                orchestrator=PluginRef(type="dagster", version="1.5.0"),  # type: ignore[call-arg]
            )
        assert "compute" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_missing_orchestrator_rejected(self) -> None:
        """Test that missing required orchestrator plugin is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),  # type: ignore[call-arg]
            )
        assert "orchestrator" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_lineage_backend_serialization_roundtrip(self) -> None:
        """Test lineage_backend field serialization roundtrip (v0.5.0)."""
        lineage_ref = PluginRef(type="marquez", version="0.20.0")
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=lineage_ref,
        )

        data = plugins.model_dump(mode="json")
        restored = ResolvedPlugins.model_validate(data)

        assert restored.lineage_backend is not None
        assert restored.lineage_backend.type == "marquez"
        assert restored.lineage_backend.version == "0.20.0"

    @pytest.mark.requirement("2B-FR-007")
    def test_lineage_backend_backward_compatibility(self) -> None:
        """Test backward compatibility: v0.4.0 without lineage_backend deserializes correctly."""
        data = {
            "compute": {"type": "duckdb", "version": "0.9.0"},
            "orchestrator": {"type": "dagster", "version": "1.5.0"},
        }

        plugins = ResolvedPlugins.model_validate(data)

        assert plugins.lineage_backend is None
        assert plugins.compute.type == "duckdb"
        assert plugins.orchestrator.type == "dagster"

    @pytest.mark.requirement("2B-FR-007")
    def test_lineage_backend_forward_compatibility(self) -> None:
        """Test forward compatibility: v0.5.0 with lineage_backend serializes correctly."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            lineage_backend=PluginRef(type="atlan", version="1.0.0"),
        )

        data = plugins.model_dump(mode="json")

        assert "lineage_backend" in data
        assert data["lineage_backend"]["type"] == "atlan"
        assert data["lineage_backend"]["version"] == "1.0.0"

    @pytest.mark.requirement("2B-FR-007")
    def test_lineage_backend_default_none(self) -> None:
        """Test lineage_backend defaults to None when not specified."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        )

        assert plugins.lineage_backend is None


class TestResolvedModel:
    """Tests for ResolvedModel validation."""

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_resolved_model_minimal(self) -> None:
        """Test that minimal valid ResolvedModel is accepted."""
        model = ResolvedModel(name="stg_customers", compute="duckdb")
        assert model.name == "stg_customers"
        assert model.compute == "duckdb"
        assert model.tags is None
        assert model.depends_on is None

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_resolved_model_full(self) -> None:
        """Test that full ResolvedModel is accepted."""
        model = ResolvedModel(
            name="fct_orders",
            compute="snowflake",
            tags=["fact", "orders"],
            depends_on=["stg_orders", "stg_customers"],
        )
        assert model.name == "fct_orders"
        assert model.compute == "snowflake"
        assert model.tags == ["fact", "orders"]
        assert model.depends_on == ["stg_orders", "stg_customers"]

    @pytest.mark.requirement("2B-FR-007")
    def test_compute_never_none(self) -> None:
        """Test that compute is required (never None)."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedModel(name="stg_customers")  # type: ignore[call-arg]
        assert "compute" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_name_required(self) -> None:
        """Test that name is required."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedModel(compute="duckdb")  # type: ignore[call-arg]
        assert "name" in str(exc_info.value)


class TestResolvedTransforms:
    """Tests for ResolvedTransforms validation."""

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_resolved_transforms(self) -> None:
        """Test that valid ResolvedTransforms is accepted."""
        transforms = ResolvedTransforms(
            models=[
                ResolvedModel(name="stg_customers", compute="duckdb"),
                ResolvedModel(name="fct_orders", compute="duckdb"),
            ],
            default_compute="duckdb",
        )
        assert len(transforms.models) == 2
        assert transforms.default_compute == "duckdb"

    @pytest.mark.requirement("2B-FR-007")
    def test_models_required_nonempty(self) -> None:
        """Test that models list must have at least one entry."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedTransforms(models=[], default_compute="duckdb")
        assert "models" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_default_compute_required(self) -> None:
        """Test that default_compute is required."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedTransforms(  # type: ignore[call-arg]
                models=[ResolvedModel(name="stg_customers", compute="duckdb")],
            )
        assert "default_compute" in str(exc_info.value)


class TestResolvedGovernance:
    """Tests for ResolvedGovernance validation."""

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_governance_all_fields(self) -> None:
        """Test that full ResolvedGovernance is accepted."""
        governance = ResolvedGovernance(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
        )
        assert governance.pii_encryption == "required"
        assert governance.audit_logging == "enabled"
        assert governance.policy_enforcement_level == "strict"
        assert governance.data_retention_days == 90

    @pytest.mark.requirement("2B-FR-007")
    def test_valid_governance_all_optional(self) -> None:
        """Test that ResolvedGovernance with all None is accepted."""
        governance = ResolvedGovernance()
        assert governance.pii_encryption is None
        assert governance.audit_logging is None
        assert governance.policy_enforcement_level is None
        assert governance.data_retention_days is None

    @pytest.mark.requirement("2B-FR-007")
    def test_invalid_pii_encryption_value(self) -> None:
        """Test that invalid pii_encryption value is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(pii_encryption="mandatory")  # type: ignore[arg-type]
        assert "pii_encryption" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_invalid_audit_logging_value(self) -> None:
        """Test that invalid audit_logging value is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(audit_logging="on")  # type: ignore[arg-type]
        assert "audit_logging" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_invalid_policy_enforcement_level_value(self) -> None:
        """Test that invalid policy_enforcement_level is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(policy_enforcement_level="high")  # type: ignore[arg-type]
        assert "policy_enforcement_level" in str(exc_info.value)

    @pytest.mark.requirement("2B-FR-007")
    def test_invalid_data_retention_days_zero(self) -> None:
        """Test that data_retention_days must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(data_retention_days=0)
        assert "data_retention_days" in str(exc_info.value)


class TestCompiledArtifactsExtensions:
    """Tests for CompiledArtifacts v0.2.0 extensions."""

    @pytest.mark.requirement("2B-FR-007")
    def test_version_default_is_0_3_0(self) -> None:
        """Test that default version is 0.3.0."""
        artifacts = CompiledArtifacts(
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version=COMPILED_ARTIFACTS_VERSION,
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
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION

    @pytest.mark.requirement("2B-FR-007")
    def test_compiled_artifacts_with_plugins(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test CompiledArtifacts with plugins field."""
        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
        )
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            plugins=plugins,
        )
        assert artifacts.plugins is not None
        assert artifacts.plugins.compute.type == "duckdb"

    @pytest.mark.requirement("2B-FR-007")
    def test_compiled_artifacts_with_transforms(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test CompiledArtifacts with transforms field."""
        transforms = ResolvedTransforms(
            models=[ResolvedModel(name="stg_customers", compute="duckdb")],
            default_compute="duckdb",
        )
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            transforms=transforms,
        )
        assert artifacts.transforms is not None
        assert len(artifacts.transforms.models) == 1

    @pytest.mark.requirement("2B-FR-007")
    def test_compiled_artifacts_with_dbt_profiles(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test CompiledArtifacts with dbt_profiles field."""
        dbt_profiles: dict[str, Any] = {
            "default": {
                "target": "dev",
                "outputs": {
                    "dev": {"type": "duckdb", "path": ":memory:"},
                },
            }
        }
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            dbt_profiles=dbt_profiles,
        )
        assert artifacts.dbt_profiles is not None
        assert artifacts.dbt_profiles["default"]["target"] == "dev"

    @pytest.mark.requirement("2B-FR-007")
    def test_compiled_artifacts_with_governance(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test CompiledArtifacts with governance field."""
        governance = ResolvedGovernance(
            pii_encryption="required",
            audit_logging="enabled",
        )
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            governance=governance,
        )
        assert artifacts.governance is not None
        assert artifacts.governance.pii_encryption == "required"

    @pytest.mark.requirement("2B-FR-007")
    def test_compiled_artifacts_all_new_fields_optional(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test that all new v0.2.0 fields are optional for backward compatibility."""
        # Should not raise - all new fields optional
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
        )
        assert artifacts.plugins is None
        assert artifacts.transforms is None
        assert artifacts.dbt_profiles is None
        assert artifacts.governance is None

    @pytest.mark.requirement("2B-FR-007")
    def test_compiled_artifacts_full(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test CompiledArtifacts with all v0.3.0 fields populated."""
        artifacts = CompiledArtifacts(
            version=COMPILED_ARTIFACTS_VERSION,
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            mode="simple",
            observability=sample_observability_config,
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
            ),
            transforms=ResolvedTransforms(
                models=[ResolvedModel(name="stg_customers", compute="duckdb")],
                default_compute="duckdb",
            ),
            dbt_profiles={"default": {"target": "dev", "outputs": {}}},
            governance=ResolvedGovernance(pii_encryption="required"),
        )
        assert artifacts.version == COMPILED_ARTIFACTS_VERSION
        assert artifacts.plugins is not None
        assert artifacts.transforms is not None
        assert artifacts.dbt_profiles is not None
        assert artifacts.governance is not None


class TestYamlSerialization:
    """Tests for YAML file serialization (T060).

    These tests validate FR-011: YAML format support for CompiledArtifacts.
    Tests are written in TDD style - they FAIL until to_yaml_file/from_yaml_file
    are implemented in T062-T063.

    Requirements: FR-011
    """

    @pytest.fixture
    def full_artifacts(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> CompiledArtifacts:
        """Create a fully-populated CompiledArtifacts for YAML tests."""
        return CompiledArtifacts(
            version=COMPILED_ARTIFACTS_VERSION,
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            mode="simple",
            observability=sample_observability_config,
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
                catalog=PluginRef(type="polaris", version="0.1.0"),
            ),
            transforms=ResolvedTransforms(
                models=[
                    ResolvedModel(name="stg_customers", compute="duckdb", tags=["staging"]),
                    ResolvedModel(
                        name="fct_orders",
                        compute="duckdb",
                        tags=["fact"],
                        depends_on=["stg_customers"],
                    ),
                ],
                default_compute="duckdb",
            ),
            dbt_profiles={
                "test-product": {
                    "target": "dev",
                    "outputs": {
                        "dev": {"type": "duckdb", "path": ":memory:"},
                    },
                }
            },
            governance=ResolvedGovernance(
                pii_encryption="required",
                audit_logging="enabled",
                policy_enforcement_level="strict",
                data_retention_days=90,
            ),
        )

    @pytest.mark.requirement("FR-011")
    def test_to_yaml_file_writes_valid_yaml(
        self,
        full_artifacts: CompiledArtifacts,
        tmp_path: Path,
    ) -> None:
        """Test that to_yaml_file writes a valid YAML file.

        Validates:
        - File is created at specified path
        - Content is valid YAML (parseable)
        - Parent directories are created if needed
        """
        yaml_path = tmp_path / "target" / "compiled_artifacts.yaml"

        # This should write the artifacts to YAML
        full_artifacts.to_yaml_file(yaml_path)

        # File must exist
        assert yaml_path.exists(), "YAML file was not created"

        # Content must be valid YAML
        import yaml

        content = yaml_path.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict), "YAML content must be a dictionary"

    @pytest.mark.requirement("FR-011")
    def test_from_yaml_file_reads_correctly(
        self,
        full_artifacts: CompiledArtifacts,
        tmp_path: Path,
    ) -> None:
        """Test that from_yaml_file reads YAML correctly.

        Validates:
        - Artifacts can be loaded from YAML file
        - Loaded artifacts have correct type
        - Key fields are preserved
        """
        yaml_path = tmp_path / "compiled_artifacts.yaml"

        # Write then read back
        full_artifacts.to_yaml_file(yaml_path)
        loaded = CompiledArtifacts.from_yaml_file(yaml_path)

        # Must be correct type
        assert isinstance(loaded, CompiledArtifacts)

        # Key fields preserved
        assert loaded.version == full_artifacts.version
        assert loaded.mode == full_artifacts.mode
        assert loaded.metadata.product_name == full_artifacts.metadata.product_name

    @pytest.mark.requirement("FR-011")
    def test_yaml_json_semantic_equivalence(
        self,
        full_artifacts: CompiledArtifacts,
        tmp_path: Path,
    ) -> None:
        """Test that YAML and JSON produce semantically equivalent artifacts.

        Validates:
        - Roundtrip through YAML produces identical artifact to JSON roundtrip
        - All fields are preserved in both formats
        """
        json_path = tmp_path / "artifacts.json"
        yaml_path = tmp_path / "artifacts.yaml"

        # Write to both formats
        full_artifacts.to_json_file(json_path)
        full_artifacts.to_yaml_file(yaml_path)

        # Load from both formats
        from_json = CompiledArtifacts.from_json_file(json_path)
        from_yaml = CompiledArtifacts.from_yaml_file(yaml_path)

        # They should be semantically equivalent
        # Compare via model_dump to avoid datetime comparison issues
        assert from_json.model_dump(mode="json") == from_yaml.model_dump(mode="json")

    @pytest.mark.requirement("FR-011")
    def test_yaml_preserves_all_fields(
        self,
        full_artifacts: CompiledArtifacts,
        tmp_path: Path,
    ) -> None:
        """Test that YAML serialization preserves all artifact fields.

        Validates each major section is preserved through roundtrip:
        - metadata
        - identity
        - observability
        - plugins
        - transforms
        - dbt_profiles
        - governance
        """
        yaml_path = tmp_path / "full_artifacts.yaml"

        # Roundtrip
        full_artifacts.to_yaml_file(yaml_path)
        loaded = CompiledArtifacts.from_yaml_file(yaml_path)

        # Metadata preserved
        assert loaded.metadata.product_name == full_artifacts.metadata.product_name
        assert loaded.metadata.product_version == full_artifacts.metadata.product_version
        assert loaded.metadata.floe_version == full_artifacts.metadata.floe_version

        # Identity preserved
        assert loaded.identity.product_id == full_artifacts.identity.product_id
        assert loaded.identity.domain == full_artifacts.identity.domain
        assert loaded.identity.repository == full_artifacts.identity.repository

        # Observability preserved
        assert loaded.observability.lineage == full_artifacts.observability.lineage
        assert (
            loaded.observability.lineage_namespace == full_artifacts.observability.lineage_namespace
        )

        # Plugins preserved
        assert loaded.plugins is not None
        assert loaded.plugins.compute.type == "duckdb"
        assert loaded.plugins.orchestrator.type == "dagster"
        assert loaded.plugins.catalog is not None
        assert loaded.plugins.catalog.type == "polaris"

        # Transforms preserved
        assert loaded.transforms is not None
        assert len(loaded.transforms.models) == 2
        assert loaded.transforms.models[0].name == "stg_customers"
        assert loaded.transforms.models[1].name == "fct_orders"
        assert loaded.transforms.models[1].depends_on == ["stg_customers"]
        assert loaded.transforms.default_compute == "duckdb"

        # dbt_profiles preserved
        assert loaded.dbt_profiles is not None
        assert "test-product" in loaded.dbt_profiles
        assert loaded.dbt_profiles["test-product"]["target"] == "dev"

        # Governance preserved
        assert loaded.governance is not None
        assert loaded.governance.pii_encryption == "required"
        assert loaded.governance.audit_logging == "enabled"
        assert loaded.governance.policy_enforcement_level == "strict"
        assert loaded.governance.data_retention_days == 90

    @pytest.mark.requirement("FR-011")
    def test_from_yaml_file_not_found(self, tmp_path: Path) -> None:
        """Test that from_yaml_file raises FileNotFoundError for missing file."""
        nonexistent = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            CompiledArtifacts.from_yaml_file(nonexistent)

    @pytest.mark.requirement("FR-011")
    def test_from_yaml_file_invalid_yaml(self, tmp_path: Path) -> None:
        """Test that from_yaml_file raises error for invalid YAML."""
        invalid_yaml_path = tmp_path / "invalid.yaml"
        invalid_yaml_path.write_text("{ invalid yaml: [no closing bracket")

        # Should raise YAML parse error
        import yaml

        with pytest.raises(yaml.YAMLError):
            CompiledArtifacts.from_yaml_file(invalid_yaml_path)

    @pytest.mark.requirement("FR-011")
    def test_from_yaml_file_validation_error(self, tmp_path: Path) -> None:
        """Test that from_yaml_file raises ValidationError for invalid schema."""
        invalid_schema_path = tmp_path / "invalid_schema.yaml"
        # Valid YAML but missing required fields
        invalid_schema_path.write_text("version: '0.2.0'\nmode: simple\n")

        with pytest.raises(ValidationError):
            CompiledArtifacts.from_yaml_file(invalid_schema_path)
