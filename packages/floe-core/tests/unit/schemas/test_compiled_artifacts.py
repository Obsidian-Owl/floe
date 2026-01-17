"""Unit tests for CompiledArtifacts extension models.

Tests validation of CompiledArtifacts v0.2.0 extensions including:
- PluginRef model
- ResolvedPlugins model
- ResolvedModel model
- ResolvedTransforms model
- ResolvedGovernance model
- Extended CompiledArtifacts fields

Task: T023
Requirements: FR-003, FR-007
"""

from __future__ import annotations

from datetime import datetime
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
        floe_version="0.2.0",
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
    def test_version_default_is_0_2_0(self) -> None:
        """Test that default version is 0.2.0."""
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
        """Test CompiledArtifacts with all v0.2.0 fields populated."""
        artifacts = CompiledArtifacts(
            version="0.2.0",
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
        assert artifacts.version == "0.2.0"
        assert artifacts.plugins is not None
        assert artifacts.transforms is not None
        assert artifacts.dbt_profiles is not None
        assert artifacts.governance is not None
