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

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from floe_core.schemas.compiled_artifacts import (
    CatalogDeploymentBinding,
    CompilationMetadata,
    CompiledArtifacts,
    CredentialRef,
    DagsterStorageBinding,
    DbtStorageBinding,
    DeploymentConfig,
    IngestionOutputTable,
    KubernetesSecretRef,
    ObservabilityConfig,
    PluginRef,
    PolarisCatalogDeploymentBinding,
    ProductIdentity,
    ResolvedGovernance,
    ResolvedModel,
    ResolvedPlugins,
    ResolvedTransforms,
    StorageBucketRequirement,
    StorageCapabilities,
    StorageCredentialBinding,
    StorageDeploymentBinding,
    StorageProvisioningIntent,
    StorageRuntimeBinding,
    StorageServiceEndpoint,
    StorageWarehouse,
)
from floe_core.schemas.telemetry import ResourceAttributes, TelemetryConfig
from floe_core.schemas.versions import (
    COMPILED_ARTIFACTS_VERSION,
    COMPILED_ARTIFACTS_VERSION_HISTORY,
)


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
def sample_observability_config(
    sample_telemetry_config: TelemetryConfig,
) -> ObservabilityConfig:
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


class TestCompilationMetadata:
    """Tests for compilation metadata validation."""

    @pytest.mark.requirement("SEC-COMPILED-ARTIFACTS")
    def test_product_name_rejects_python_string_breakout(self) -> None:
        """Product names embedded in generated Python must reject code injection."""
        with pytest.raises(ValidationError, match="product_name"):
            CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version=COMPILED_ARTIFACTS_VERSION,
                source_hash="sha256:abc123",
                product_name='bad"; import os; #',
                product_version="1.0.0",
            )

    @pytest.mark.requirement("SEC-COMPILED-ARTIFACTS")
    @pytest.mark.parametrize("product_name", ["customer-360", "test_analytics", "Product1"])
    def test_product_name_accepts_safe_identifiers(self, product_name: str) -> None:
        """Safe product names remain valid for compiled artifacts."""
        metadata = CompilationMetadata(
            compiled_at=datetime.now(),
            floe_version=COMPILED_ARTIFACTS_VERSION,
            source_hash="sha256:abc123",
            product_name=product_name,
            product_version="1.0.0",
        )

        assert metadata.product_name == product_name


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
            storage=PluginRef(type="minio", version="1.0.0"),
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


class TestIngestionOutputTable:
    @staticmethod
    def _make_table(source_path: str) -> IngestionOutputTable:
        return IngestionOutputTable(
            source_name="raw-transactions",
            source_type="filesystem",
            logical_table="bronze.raw_transactions",
            physical_table="bronze.raw_transactions",
            file_format="csv",
            source_path=source_path,
            write_mode="replace",
            schema_contract="evolve",
        )

    def test_ingestion_output_table_serializes_secret_free_state(self) -> None:
        table = IngestionOutputTable(
            source_name="raw-transactions",
            source_type="filesystem",
            table_format="iceberg",
            logical_table="bronze.raw_transactions",
            physical_table="bronze.raw_transactions",
            file_format="csv",
            source_path="./seeds/raw_transactions.csv",
            write_mode="replace",
            schema_contract="evolve",
            freshness_field="_loaded_at",
            quality_tier="bronze",
        )

        payload = table.model_dump(mode="json")

        assert payload["source_name"] == "raw-transactions"
        assert payload["logical_table"] == "bronze.raw_transactions"
        assert payload["physical_table"] == "bronze.raw_transactions"
        assert payload["quality_tier"] == "bronze"

    def test_ingestion_output_table_rejects_secret_like_path(self) -> None:
        with pytest.raises(ValidationError, match="source_path"):
            self._make_table("s3://example/raw.csv?signature=example")

    @pytest.mark.parametrize(
        "source_path",
        [
            " ./seeds/raw_transactions.csv",
            "./seeds/raw_transactions.csv ",
        ],
    )
    def test_ingestion_output_table_rejects_whitespace_padded_path(self, source_path: str) -> None:
        with pytest.raises(ValidationError, match="source_path"):
            self._make_table(source_path)

    def test_ingestion_output_table_rejects_absolute_local_path(self) -> None:
        with pytest.raises(ValidationError, match="source_path"):
            self._make_table("/var/data/raw_transactions.csv")

    def test_ingestion_output_table_rejects_unsupported_uri_scheme(self) -> None:
        with pytest.raises(ValidationError, match="source_path"):
            self._make_table("https://example.com/raw_transactions.csv")

    def test_ingestion_output_table_rejects_object_store_uri_without_bucket(self) -> None:
        with pytest.raises(ValidationError, match="source_path"):
            self._make_table("s3:///raw_transactions.csv")

    def test_ingestion_output_table_accepts_tokenized_filename(self) -> None:
        table = IngestionOutputTable(
            source_name="tokenized-customers",
            source_type="filesystem",
            logical_table="bronze.tokenized_customers",
            physical_table="bronze.tokenized_customers",
            file_format="csv",
            source_path="./data/tokenized_customers.csv",
            write_mode="replace",
            schema_contract="evolve",
        )

        assert table.source_path == "./data/tokenized_customers.csv"

    def test_ingestion_output_table_rejects_credential_query_path(self) -> None:
        with pytest.raises(ValidationError, match="source_path"):
            self._make_table("s3://bucket/raw.csv?X-Amz-Credential=value")

    @pytest.mark.parametrize(
        "table_name",
        [
            "bronze",
            "bronze.",
            ".raw_transactions",
            "bronze.raw.transactions",
            "bronze. raw_transactions",
            "bronze.raw transactions",
        ],
    )
    def test_ingestion_output_table_rejects_invalid_table_identifier(
        self,
        table_name: str,
    ) -> None:
        with pytest.raises(ValidationError, match="logical_table"):
            IngestionOutputTable(
                source_name="raw-transactions",
                source_type="filesystem",
                logical_table=table_name,
                physical_table="bronze.raw_transactions",
                file_format="csv",
                source_path="./seeds/raw_transactions.csv",
                write_mode="replace",
                schema_contract="evolve",
            )


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
        assert artifacts.ingestion_outputs == []

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


class TestStorageDeploymentBinding:
    """Tests for compiled storage deployment bindings."""

    def _rich_binding(self) -> StorageDeploymentBinding:
        credentials = StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="floe-platform-minio-credentials",
                namespace="floe-system",
                keys={
                    "accessKeyId": "access-key-id",
                    "secretAccessKey": "secret-access-key",  # pragma: allowlist secret
                },
            ),
        )
        return StorageDeploymentBinding(
            provider="minio",
            protocol="s3-compatible",
            endpoint=StorageServiceEndpoint(
                internal_url="http://floe-platform-minio:9000",
                external_url="http://localhost:9000",
                region="us-east-1",
                warehouse_path="s3://floe-iceberg",
                path_style_access=True,
            ),
            warehouse=StorageWarehouse(uri="s3://floe-iceberg", bucket="floe-iceberg"),
            allowed_locations=["s3://floe-iceberg"],
            buckets=[
                StorageBucketRequirement(
                    name="floe-iceberg",
                    uri="s3://floe-iceberg",
                    purpose="warehouse",
                    create_policy="create-if-missing",
                )
            ],
            credentials=credentials,
            capabilities=StorageCapabilities(
                protocols=["s3-compatible"],
                credential_modes=["kubernetes-secret"],
                sts_supported=False,
                path_style_access=True,
            ),
            provisioning=StorageProvisioningIntent(
                enabled=True,
                mode="helm-job",
                default_create_policy="create-if-missing",
            ),
            runtime=StorageRuntimeBinding(
                pyiceberg_properties={"s3.endpoint": "http://floe-platform-minio:9000"},
            ),
            dbt=DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
                env_refs={
                    "s3_access_key_id": "AWS_ACCESS_KEY_ID",
                    "s3_secret_access_key": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
                },
            ),
            dagster=DagsterStorageBinding(
                resource_key="minio_storage",
                asset_io_manager_key="iceberg_io_manager",
                env_refs={
                    "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
                    # pragma: allowlist nextline secret
                    "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",
                },
            ),
            notes=["Local MinIO storage deployment binding."],
        )

    def _binding(self) -> StorageDeploymentBinding:
        endpoint = StorageServiceEndpoint(
            internal_url="http://floe-platform-minio:9000",
            external_url="http://localhost:9000",
            region="us-east-1",
            warehouse_path="s3://floe-iceberg",
        )
        credentials = StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="floe-platform-minio-credentials",
                namespace="floe-system",
                keys={
                    "accessKeyId": "root-user",
                    "secretAccessKey": "root-password",  # pragma: allowlist secret
                },
            ),
        )
        return StorageDeploymentBinding(
            provider="minio",
            endpoint=endpoint,
            credentials=credentials,
            dbt=DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
                env_refs={
                    "s3_access_key_id": "AWS_ACCESS_KEY_ID",
                    "s3_secret_access_key": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
                },
            ),
            dagster=DagsterStorageBinding(
                resource_key="minio_storage",
                asset_io_manager_key="iceberg_io_manager",
                env_refs={
                    "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
                    # pragma: allowlist nextline secret
                    "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",
                },
            ),
            notes=["Local MinIO storage deployment binding."],
        )

    def test_storage_deployment_binding_serializes_without_secret_values(self) -> None:
        binding = self._binding()
        payload = binding.model_dump_json()

        assert "minio" + "admin" not in payload
        assert "rootPassword" not in payload
        assert "secretKey" not in payload
        assert "floe-platform-minio-credentials" in payload

    def test_rich_storage_deployment_binding_serializes_desired_state(self) -> None:
        binding = self._rich_binding()
        payload = binding.model_dump(mode="json")

        assert payload["provider"] == "minio"
        assert payload["protocol"] == "s3-compatible"
        assert payload["endpoint"]["path_style_access"] is True
        assert payload["warehouse"] == {
            "uri": "s3://floe-iceberg",
            "bucket": "floe-iceberg",
            "prefix": "",
        }
        assert payload["allowed_locations"] == ["s3://floe-iceberg"]
        assert payload["buckets"][0]["create_policy"] == "create-if-missing"
        assert payload["capabilities"] == {
            "protocols": ["s3-compatible"],
            "credential_modes": ["kubernetes-secret"],
            "identity_modes": [],
            "sts_supported": False,
            "path_style_access": True,
        }
        assert payload["provisioning"] == {
            "enabled": True,
            "mode": "helm-job",
            "default_create_policy": "create-if-missing",
        }
        assert payload["runtime"]["pyiceberg_properties"] == {
            "s3.endpoint": "http://floe-platform-minio:9000"
        }

    @pytest.mark.parametrize(
        ("field_name", "fragment"),
        [
            (
                "pyiceberg_properties",
                {"s3.secret-access-key": "raw-secret-value"},  # pragma: allowlist secret
            ),
            (
                "dbt_profile_fragment",
                {"outputs": {"dev": {"password": "raw-secret-value"}}},  # pragma: allowlist secret
            ),
            ("dagster_resources", {"storage": {"token": "raw-secret-value"}}),
            ("dbt_profile_fragment", {"settings": {"raw-secret-value"}}),
            ("dbt_profile_fragment", {"settings": {"storage-admin"}}),
            ("dbt_profile_fragment", {"settings": {"uri": "s3://storage-admin@localhost:9000"}}),
            ("dagster_resources", {"settings": frozenset({"raw-secret-value"})}),
        ],
    )
    def test_storage_runtime_binding_rejects_raw_secret_fragments(
        self,
        field_name: str,
        fragment: dict[str, Any],
    ) -> None:
        with pytest.raises(ValidationError, match="raw credential material"):
            StorageRuntimeBinding(**{field_name: fragment})

    @pytest.mark.parametrize(
        "fragment",
        [
            {"password": "raw-secret-value"},  # pragma: allowlist secret
            {"settings": {"value": "raw-secret-value"}},
            {"settings": {"raw-secret-value"}},
        ],
    )
    def test_dbt_storage_binding_rejects_raw_secret_profile_fragment(
        self,
        fragment: dict[str, Any],
    ) -> None:
        with pytest.raises(ValidationError, match="raw credential material"):
            DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
                profile_fragment=fragment,
            )

    @pytest.mark.parametrize(
        "resources",
        [
            {"storage": {"token": "raw-secret-value"}},
            {"storage": {"value": "raw-secret-value"}},
            {"storage": frozenset({"raw-secret-value"})},
            {"storage": {"credentials": {"endpoint_url": "http://minio:9000"}}},
        ],
    )
    def test_dagster_storage_binding_rejects_raw_secret_resources(
        self,
        resources: dict[str, Any],
    ) -> None:
        with pytest.raises(ValidationError, match="raw credential material"):
            DagsterStorageBinding(
                resource_key="minio_storage",
                asset_io_manager_key="iceberg_io_manager",
                resources=resources,
            )

    def test_compiled_artifacts_accept_deployment_storage_binding(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.1.0"),
                orchestrator=PluginRef(type="dagster", version="0.1.0"),
                catalog=PluginRef(type="polaris", version="0.1.0"),
                storage=PluginRef(type="minio", version="0.1.0"),
            ),
            deployment=DeploymentConfig(storage=self._binding()),
        )

        restored = CompiledArtifacts.model_validate(artifacts.model_dump(mode="json"))

        assert restored.deployment is not None
        assert restored.deployment.storage is not None
        assert restored.deployment.storage.provider == "minio"
        assert (
            restored.deployment.storage.endpoint.internal_url == "http://floe-platform-minio:9000"
        )
        assert restored.deployment.storage.dbt.profile_name == "floe"
        assert restored.deployment.storage.dagster.resource_key == "minio_storage"

    def test_compiled_artifacts_accept_storage_and_catalog_deployment_bindings(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        storage = self._rich_binding()
        catalog = CatalogDeploymentBinding(
            provider="polaris",
            polaris=PolarisCatalogDeploymentBinding(
                storage_type="S3",
                warehouse="floe-demo",
                default_base_location="s3://floe-iceberg",
                allowed_locations=["s3://floe-iceberg"],
                endpoint="http://localhost:9000",
                endpoint_internal="http://floe-platform-minio:9000",
                path_style_access=True,
                sts_unavailable=True,
                credential_refs={
                    "accessKeyId": storage.credentials.as_credential_ref("accessKeyId"),
                    "secretAccessKey": storage.credentials.as_credential_ref("secretAccessKey"),
                },
            ),
        )
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.1.0"),
                orchestrator=PluginRef(type="dagster", version="0.1.0"),
                catalog=PluginRef(type="polaris", version="0.1.0"),
                storage=PluginRef(type="minio", version="0.1.0"),
            ),
            deployment=DeploymentConfig(storage=storage, catalog=catalog),
        )

        restored = CompiledArtifacts.model_validate(artifacts.model_dump(mode="json"))
        serialized = restored.model_dump_json()

        assert restored.deployment is not None
        assert restored.deployment.storage is not None
        assert restored.deployment.catalog is not None
        assert restored.deployment.catalog.provider == "polaris"
        assert restored.deployment.catalog.polaris.default_base_location == "s3://floe-iceberg"
        assert restored.deployment.catalog.polaris.allowed_locations == ["s3://floe-iceberg"]
        assert restored.deployment.catalog.polaris.path_style_access is True
        assert restored.deployment.catalog.polaris.sts_unavailable is True
        assert (
            restored.deployment.catalog.polaris.credential_refs["secretAccessKey"].key
            == "secret-access-key"
        )
        assert "minio-secret-value" not in serialized
        assert "raw-secret-value" not in serialized

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: DbtStorageBinding(
                profile_name="floe",
                target_name="dev",
                schema_name="analytics",
                env_refs={"s3_access_key_id": ""},
            ),
            lambda: DagsterStorageBinding(
                resource_key="minio_storage",
                asset_io_manager_key="iceberg_io_manager",
                env_refs={"AWS_ACCESS_KEY_ID": ""},
            ),
        ],
    )
    def test_consumer_env_ref_values_reject_empty_strings(
        self,
        factory: Any,
    ) -> None:
        with pytest.raises(ValidationError):
            factory()


class TestGlueCatalogDeploymentBinding:
    """Tests for AWS Glue catalog deployment binding."""

    def test_glue_catalog_binding_serializes_secret_free_fields(self) -> None:
        from floe_core.schemas.compiled_artifacts import (
            CatalogDeploymentBinding,
            CredentialRef,
            GlueCatalogDeploymentBinding,
        )

        binding = CatalogDeploymentBinding(
            provider="glue",
            glue=GlueCatalogDeploymentBinding(
                catalog_name="glue",
                region="ap-southeast-2",
                warehouse="s3://floe-provider-tests/warehouse/",
                catalog_id="278833447053",
                database_prefix="floe_provider_",
                skip_archive=True,
                max_retries=5,
                retry_mode="standard",
                credential_refs={
                    "role": CredentialRef(
                        source="workload-identity",
                        name="floe-provider-tests",
                    )
                },
                properties={"glue.skip-archive": "true"},
            ),
        )

        payload = binding.model_dump(mode="json")

        assert payload["provider"] == "glue"
        assert payload["glue"]["region"] == "ap-southeast-2"
        assert payload["glue"]["warehouse"] == "s3://floe-provider-tests/warehouse/"
        assert payload["glue"]["catalog_id"] == "278833447053"
        assert payload["glue"]["credential_refs"]["role"]["source"] == "workload-identity"
        assert "raw-secret-value" not in binding.model_dump_json()

    def test_glue_provider_requires_glue_details(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import CatalogDeploymentBinding

        with pytest.raises(ValidationError, match="glue catalog deployment binding"):
            CatalogDeploymentBinding(provider="glue")

    def test_glue_binding_rejects_raw_secret_properties(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import GlueCatalogDeploymentBinding

        with pytest.raises(ValidationError, match="raw credential material"):
            GlueCatalogDeploymentBinding(
                region="ap-southeast-2",
                warehouse="s3://floe-provider-tests/warehouse/",
                properties={"glue.secret-access-key": "raw-secret-value"},
            )


class TestRuntimeCatalogConnection:
    """Tests for secret-free runtime catalog connection projection."""

    def test_runtime_catalog_connection_serializes_secret_free_fields(self) -> None:
        from floe_core.schemas.compiled_artifacts import (
            CredentialRef,
            RuntimeCatalogConnection,
        )

        connection = RuntimeCatalogConnection(
            catalog_name="polaris",
            catalog_uri="http://polaris:8181/api/catalog",
            warehouse="s3://floe-iceberg",
            storage_endpoint="http://floe-platform-minio:9000",
            region="us-east-1",
            path_style_access=True,
            properties={"token-refresh-enabled": "true"},
            credential_refs={
                "accessKeyId": CredentialRef(
                    source="kubernetes-secret",
                    name="floe-platform-minio-credentials",
                    key="root-user",
                )
            },
            env_refs={"PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL"},
        )

        payload = connection.model_dump(mode="json")

        assert payload["catalog_uri"] == "http://polaris:8181/api/catalog"
        assert payload["path_style_access"] is True
        assert payload["credential_refs"]["accessKeyId"]["name"] == (
            "floe-platform-minio-credentials"
        )
        assert connection.credential_refs["accessKeyId"].source == "kubernetes-secret"
        assert payload["env_refs"] == {
            "PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL"
        }

    def test_runtime_catalog_connection_rejects_raw_secret_material(self) -> None:
        from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection

        invalid_values = [
            {"properties": {"s3.secret-access-key": "raw-secret-value"}},
            # pragma: allowlist nextline secret
            {"catalog_uri": "http://user:raw-secret-value@polaris:8181/api/catalog"},
            {"storage_endpoint": "http://minio:9000?token=raw-secret-value"},
            {"catalog_uri": "http://polaris:8181/api/catalog?credential=abc123"},
            {"catalog_uri": "http://polaris:8181/api/catalog#credential=abc123"},
            {"catalog_uri": "http://polaris:8181/api/catalog?secret_access_key=abc123"},
            {"catalog_uri": "http://polaris:8181/api/catalog#aws_secret_access_key=abc123"},
            {"catalog_uri": "http://polaris:8181/api/catalog?X-Amz-Signature=abc123"},
            {"properties": {"catalog-uri": "http://polaris:8181/api/catalog?credential=abc123"}},
            {"warehouse": "s3://raw-secret-value/floe-iceberg"},
        ]
        for kwargs in invalid_values:
            with pytest.raises(ValidationError, match="raw credential material"):
                RuntimeCatalogConnection(catalog_name="polaris", **kwargs)

    def test_runtime_catalog_connection_allows_secret_named_env_refs(self) -> None:
        from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection

        connection = RuntimeCatalogConnection(
            catalog_name="polaris",
            env_refs={
                "session_token": "AWS_SESSION_TOKEN",
                # pragma: allowlist nextline secret
                "password": "ICEBERG_PASSWORD",
                "bearer": "OAUTH_BEARER_TOKEN",
            },
        )

        assert connection.env_refs == {
            "session_token": "AWS_SESSION_TOKEN",
            # pragma: allowlist nextline secret
            "password": "ICEBERG_PASSWORD",
            "bearer": "OAUTH_BEARER_TOKEN",
        }

    def test_runtime_catalog_connection_env_refs_must_be_env_var_names(self) -> None:
        from floe_core.schemas.compiled_artifacts import RuntimeCatalogConnection

        with pytest.raises(ValidationError, match="environment variable name"):
            RuntimeCatalogConnection(
                catalog_name="polaris",
                env_refs={"credential": "not-an-env-var"},
            )


class TestIngestionDeploymentBinding:
    """Contract tests for secret-free dlt ingestion deployment bindings."""

    def test_dlt_binding_accepts_secret_free_runtime_fragments(self) -> None:
        from floe_core.schemas.compiled_artifacts import (
            CatalogDeploymentBinding,
            CredentialRef,
            DeploymentConfig,
            DltIngestionBinding,
            IngestionDeploymentBinding,
            PolarisCatalogDeploymentBinding,
        )

        catalog = CatalogDeploymentBinding(
            provider="polaris",
            polaris=PolarisCatalogDeploymentBinding(
                storage_type="S3",
                warehouse="floe-demo",
                default_base_location="s3://floe-iceberg",
                allowed_locations=["s3://floe-iceberg"],
                endpoint="http://localhost:8181/api/catalog",
                endpoint_internal="http://polaris:8181/api/catalog",
                path_style_access=True,
                sts_unavailable=True,
                credential_refs={
                    "accessKeyId": CredentialRef(source="none", name="none"),
                    "secretAccessKey": CredentialRef(source="none", name="none"),
                },
            ),
        )
        binding = DltIngestionBinding(
            plugin_name="dlt",
            destination="filesystem",
            table_format="iceberg",
            source_filesystem={
                "endpoint_url": "http://floe-platform-minio:9000",
                "region_name": "us-east-1",
                "s3_url_style": "path",
            },
            destination_filesystem={
                "bucket_url": "s3://floe-iceberg",
                "credentials": {
                    "endpoint_url": "http://floe-platform-minio:9000",
                    "region_name": "us-east-1",
                    "s3_url_style": "path",
                },
            },
            iceberg_catalog_env={
                "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": "polaris",
                "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
                "PYICEBERG_CATALOG__POLARIS__TYPE": "rest",
                "PYICEBERG_CATALOG__POLARIS__URI": "http://polaris:8181/api/catalog",
                "PYICEBERG_CATALOG__POLARIS__WAREHOUSE": "floe-demo",
            },
            env_refs={
                "AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",  # pragma: allowlist secret
                "PYICEBERG_CATALOG__POLARIS__CREDENTIAL": "POLARIS_CREDENTIAL",
            },
        )

        deployment = DeploymentConfig(
            catalog=catalog,
            ingestion=IngestionDeploymentBinding(provider="dlt", dlt=binding),
        )

        assert deployment.catalog is not None
        assert deployment.catalog.polaris.warehouse == "floe-demo"
        assert deployment.ingestion is not None
        assert deployment.ingestion.dlt.destination == "filesystem"
        assert deployment.ingestion.dlt.table_format == "iceberg"
        assert deployment.ingestion.dlt.destination_filesystem["bucket_url"] == "s3://floe-iceberg"

    def test_dlt_binding_rejects_raw_secret_material(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import DltIngestionBinding

        with pytest.raises(ValidationError, match="raw credential material"):
            DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={},
                destination_filesystem={
                    "credentials": {
                        "aws_secret_access_key": "raw-secret-value",  # pragma: allowlist secret
                    }
                },
                iceberg_catalog_env={},
                env_refs={},
            )

    def test_dlt_binding_rejects_secret_values_in_allowed_credential_keys(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import DltIngestionBinding

        with pytest.raises(ValidationError, match="raw credential material"):
            DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={},
                destination_filesystem={
                    "credentials": {
                        "endpoint_url": "raw-secret-value",  # pragma: allowlist secret
                    }
                },
                iceberg_catalog_env={},
                env_refs={},
            )

    def test_dlt_binding_rejects_opaque_filesystem_fragment_values(self) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import DltIngestionBinding

        with pytest.raises(ValidationError, match="JSON-compatible"):
            DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={},
                destination_filesystem={"credentials": {"endpoint_url": object()}},
                iceberg_catalog_env={},
                env_refs={},
            )

    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
    def test_dlt_binding_rejects_non_finite_filesystem_fragment_numbers(
        self,
        value: float,
    ) -> None:
        from pydantic import ValidationError

        from floe_core.schemas.compiled_artifacts import DltIngestionBinding

        with pytest.raises(ValidationError, match="finite"):
            DltIngestionBinding(
                plugin_name="dlt",
                destination="filesystem",
                table_format="iceberg",
                source_filesystem={},
                destination_filesystem={"credentials": {"endpoint_url": value}},
                iceberg_catalog_env={},
                env_refs={},
            )


class TestStorageCredentialBinding:
    """Tests for storage credential binding validation."""

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: KubernetesSecretRef(name="Bad_Name", namespace="floe-system"),
            lambda: KubernetesSecretRef(name="storage-credentials", namespace="Bad_Namespace"),
        ],
    )
    def test_kubernetes_secret_ref_rejects_invalid_identifiers(
        self,
        factory: Any,
    ) -> None:
        with pytest.raises(ValidationError):
            factory()

    def test_kubernetes_secret_ref_accepts_dns_label_identifiers(self) -> None:
        ref = KubernetesSecretRef(
            name="storage-credentials",
            namespace="floe-system",
            keys={"accessKeyId": "root-user"},
        )

        assert ref.name == "storage-credentials"
        assert ref.namespace == "floe-system"

    @pytest.mark.parametrize(
        "binding_kwargs",
        [
            {"mode": "kubernetes-secret"},
            {"mode": "environment"},
            {"mode": "environment", "env_refs": {}},
            {"mode": "workload-identity"},
            {
                "mode": "none",
                "secret_ref": KubernetesSecretRef(
                    name="storage-credentials",
                    namespace="floe-system",
                ),
            },
            {"mode": "none", "env_refs": {"accessKeyId": "AWS_ACCESS_KEY_ID"}},
            {"mode": "none", "service_account_ref": "storage-service-account"},
            {
                "mode": "kubernetes-secret",
                "secret_ref": KubernetesSecretRef(
                    name="storage-credentials",
                    namespace="floe-system",
                ),
                "env_refs": {"accessKeyId": "AWS_ACCESS_KEY_ID"},
            },
            {
                "mode": "kubernetes-secret",
                "secret_ref": KubernetesSecretRef(
                    name="storage-credentials",
                    namespace="floe-system",
                ),
                "service_account_ref": "storage-service-account",
            },
            {
                "mode": "environment",
                "secret_ref": KubernetesSecretRef(
                    name="storage-credentials",
                    namespace="floe-system",
                ),
                "env_refs": {"accessKeyId": "AWS_ACCESS_KEY_ID"},
            },
            {
                "mode": "environment",
                "env_refs": {"accessKeyId": "AWS_ACCESS_KEY_ID"},
                "service_account_ref": "storage-service-account",
            },
            {
                "mode": "workload-identity",
                "secret_ref": KubernetesSecretRef(
                    name="storage-credentials",
                    namespace="floe-system",
                ),
                "service_account_ref": "storage-service-account",
            },
            {
                "mode": "workload-identity",
                "env_refs": {"accessKeyId": "AWS_ACCESS_KEY_ID"},
                "service_account_ref": "storage-service-account",
            },
        ],
    )
    def test_mode_inconsistent_credential_bindings_are_rejected(
        self,
        binding_kwargs: dict[str, Any],
    ) -> None:
        with pytest.raises(ValidationError):
            StorageCredentialBinding(**binding_kwargs)

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: KubernetesSecretRef(
                name="storage-credentials",
                namespace="floe-system",
                keys={"accessKeyId": ""},
            ),
            lambda: KubernetesSecretRef(name="storage-credentials"),
            lambda: CredentialRef(source="environment", name=""),
            lambda: CredentialRef(source="kubernetes-secret", name="storage-credentials", key=""),
            lambda: StorageCredentialBinding(mode="environment", env_refs={"accessKeyId": ""}),
            lambda: StorageCredentialBinding(mode="workload-identity", service_account_ref=""),
        ],
    )
    def test_empty_credential_reference_values_are_rejected(
        self,
        factory: Any,
    ) -> None:
        with pytest.raises(ValidationError):
            factory()

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: CredentialRef(source="kubernetes-secret", name="storage-credentials"),
            lambda: CredentialRef(
                source="environment",
                name="AWS_ACCESS_KEY_ID",
                key="accessKeyId",
            ),
            lambda: CredentialRef(
                source="workload-identity",
                name="storage-service-account",
                key="accessKeyId",
            ),
            lambda: CredentialRef(source="none", name="none", key="accessKeyId"),
        ],
    )
    def test_credential_ref_key_matches_source(
        self,
        factory: Any,
    ) -> None:
        with pytest.raises(ValidationError):
            factory()

    def test_environment_credential_ref_uses_configured_env_name(self) -> None:
        binding = StorageCredentialBinding(
            mode="environment",
            env_refs={"accessKeyId": "AWS_ACCESS_KEY_ID"},
        )

        ref = binding.as_credential_ref("accessKeyId")

        assert ref.source == "environment"
        assert ref.name == "AWS_ACCESS_KEY_ID"
        assert ref.key is None

    def test_environment_credential_ref_raises_for_missing_logical_key(self) -> None:
        binding = StorageCredentialBinding(
            mode="environment",
            env_refs={"accessKeyId": "AWS_ACCESS_KEY_ID"},
        )

        with pytest.raises(ValueError, match="not present in env_refs"):
            binding.as_credential_ref("secretAccessKey")

    def test_kubernetes_secret_credential_ref_raises_for_missing_logical_key(self) -> None:
        binding = StorageCredentialBinding(
            mode="kubernetes-secret",
            secret_ref=KubernetesSecretRef(
                name="storage-credentials",
                namespace="floe-system",
                keys={"accessKeyId": "root-user"},
            ),
        )

        with pytest.raises(ValueError, match="not present in secret_ref.keys"):
            binding.as_credential_ref("secretAccessKey")

    def test_workload_identity_credential_ref_uses_service_account(self) -> None:
        binding = StorageCredentialBinding(
            mode="workload-identity",
            service_account_ref="storage-service-account",
        )

        ref = binding.as_credential_ref("accessKeyId")

        assert ref.source == "workload-identity"
        assert ref.name == "storage-service-account"
        assert ref.key is None

    def test_none_credential_ref_is_stable(self) -> None:
        binding = StorageCredentialBinding(mode="none")

        ref = binding.as_credential_ref("accessKeyId")

        assert ref.source == "none"
        assert ref.name == "none"
        assert ref.key is None


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
    def test_to_yaml_file_preserves_legacy_sorted_key_order(
        self,
        full_artifacts: CompiledArtifacts,
        tmp_path: Path,
    ) -> None:
        """Test that YAML output keeps the pre-ConfigMap key ordering contract."""
        import yaml

        yaml_path = tmp_path / "compiled_artifacts.yaml"
        full_artifacts.to_yaml_file(yaml_path)

        expected = yaml.safe_dump(
            full_artifacts.model_dump(mode="json", by_alias=True),
            default_flow_style=False,
            allow_unicode=True,
        )
        assert yaml_path.read_text(encoding="utf-8") == expected

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
    def test_to_configmap_yaml_uses_default_name_and_omits_namespace(
        self,
        full_artifacts: CompiledArtifacts,
    ) -> None:
        """Test that ConfigMap serialization uses the documented defaults."""
        import yaml

        configmap = yaml.safe_load(full_artifacts.to_configmap_yaml())

        assert configmap["apiVersion"] == "v1"
        assert configmap["kind"] == "ConfigMap"
        assert configmap["metadata"]["name"] == "floe-compiled-values"
        assert "namespace" not in configmap["metadata"]
        assert isinstance(configmap["data"]["values.yaml"], str)

    @pytest.mark.requirement("FR-011")
    def test_to_configmap_yaml_wraps_existing_artifact_payload(
        self,
        full_artifacts: CompiledArtifacts,
    ) -> None:
        """Test that ConfigMap output wraps the existing artifact dump."""
        import yaml

        configmap = yaml.safe_load(
            full_artifacts.to_configmap_yaml(
                name="team-values",
                namespace="data-platform",
            )
        )

        embedded_values = yaml.safe_load(configmap["data"]["values.yaml"])

        assert configmap["metadata"]["name"] == "team-values"
        assert configmap["metadata"]["namespace"] == "data-platform"
        assert embedded_values == full_artifacts.model_dump(mode="json", by_alias=True)

    @pytest.mark.requirement("FR-011")
    def test_to_configmap_yaml_rejects_invalid_name(
        self, full_artifacts: CompiledArtifacts
    ) -> None:
        """Test that invalid ConfigMap names are rejected before rendering YAML."""
        with pytest.raises(ValueError, match="Invalid ConfigMap name"):
            full_artifacts.to_configmap_yaml(name="My ConfigMap!")

    @pytest.mark.requirement("FR-011")
    def test_to_configmap_yaml_rejects_name_with_trailing_newline(
        self,
        full_artifacts: CompiledArtifacts,
    ) -> None:
        """Test that trailing newlines are rejected in ConfigMap names."""
        with pytest.raises(ValueError, match="Invalid ConfigMap name"):
            full_artifacts.to_configmap_yaml(name="team-values\n")

    @pytest.mark.requirement("FR-011")
    def test_to_configmap_yaml_rejects_invalid_namespace(
        self,
        full_artifacts: CompiledArtifacts,
    ) -> None:
        """Test that invalid namespaces are rejected before rendering YAML."""
        with pytest.raises(ValueError, match="Invalid namespace"):
            full_artifacts.to_configmap_yaml(namespace="Invalid_Namespace")

    @pytest.mark.requirement("FR-011")
    def test_to_configmap_yaml_rejects_namespace_with_trailing_newline(
        self,
        full_artifacts: CompiledArtifacts,
    ) -> None:
        """Test that trailing newlines are rejected in namespaces."""
        with pytest.raises(ValueError, match="Invalid namespace"):
            full_artifacts.to_configmap_yaml(namespace="data-platform\n")

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


# ==============================================================================
# T1: Governance Lifecycle Fields + Version Bump
# ==============================================================================


class TestGovernanceLifecycleFields:
    """Tests for default_ttl_hours and snapshot_keep_last on ResolvedGovernance.

    AC-1: ResolvedGovernance MUST have default_ttl_hours: int | None and
    snapshot_keep_last: int | None, both defaulting to None with ge=1 and
    le=8760 (TTL) / le=100 (snapshots) validation.
    """

    # --- Happy path: fields exist and accept valid values ---

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_accept_valid_values(self) -> None:
        """Test that default_ttl_hours and snapshot_keep_last accept valid integers."""
        governance = ResolvedGovernance(
            default_ttl_hours=24,
            snapshot_keep_last=3,
        )
        assert governance.default_ttl_hours == 24
        assert governance.snapshot_keep_last == 3

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_default_to_none(self) -> None:
        """Test that both lifecycle fields default to None when omitted."""
        governance = ResolvedGovernance()
        assert governance.default_ttl_hours is None
        assert governance.snapshot_keep_last is None

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_explicit_none(self) -> None:
        """Test that both lifecycle fields accept explicit None."""
        governance = ResolvedGovernance(
            default_ttl_hours=None,
            snapshot_keep_last=None,
        )
        assert governance.default_ttl_hours is None
        assert governance.snapshot_keep_last is None

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_with_existing_fields(self) -> None:
        """Test lifecycle fields coexist with existing governance fields."""
        governance = ResolvedGovernance(
            pii_encryption="required",
            audit_logging="enabled",
            policy_enforcement_level="strict",
            data_retention_days=90,
            default_ttl_hours=720,
            snapshot_keep_last=10,
        )
        assert governance.pii_encryption == "required"
        assert governance.audit_logging == "enabled"
        assert governance.policy_enforcement_level == "strict"
        assert governance.data_retention_days == 90
        assert governance.default_ttl_hours == 720
        assert governance.snapshot_keep_last == 10

    # --- Boundary: minimum valid (1) ---

    @pytest.mark.requirement("T1-AC-1")
    def test_ttl_hours_minimum_valid(self) -> None:
        """Test that default_ttl_hours=1 is the minimum valid value."""
        governance = ResolvedGovernance(default_ttl_hours=1)
        assert governance.default_ttl_hours == 1

    @pytest.mark.requirement("T1-AC-1")
    def test_snapshot_keep_last_minimum_valid(self) -> None:
        """Test that snapshot_keep_last=1 is the minimum valid value."""
        governance = ResolvedGovernance(snapshot_keep_last=1)
        assert governance.snapshot_keep_last == 1

    # --- Boundary: maximum valid ---

    @pytest.mark.requirement("T1-AC-1")
    def test_ttl_hours_maximum_valid(self) -> None:
        """Test that default_ttl_hours=8760 (1 year) is the maximum valid value."""
        governance = ResolvedGovernance(default_ttl_hours=8760)
        assert governance.default_ttl_hours == 8760

    @pytest.mark.requirement("T1-AC-1")
    def test_snapshot_keep_last_maximum_valid(self) -> None:
        """Test that snapshot_keep_last=100 is the maximum valid value."""
        governance = ResolvedGovernance(snapshot_keep_last=100)
        assert governance.snapshot_keep_last == 100

    # --- Boundary: just above maximum (must reject) ---

    @pytest.mark.requirement("T1-AC-1")
    def test_ttl_hours_exceeds_maximum_rejected(self) -> None:
        """Test that default_ttl_hours=8761 exceeds the 1-year max and is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(default_ttl_hours=8761)
        errors = exc_info.value.errors()
        assert any(
            e["loc"] == ("default_ttl_hours",) and "less than or equal to" in str(e["msg"])
            for e in errors
        ), f"Expected le validation error for default_ttl_hours, got: {errors}"

    @pytest.mark.requirement("T1-AC-1")
    def test_snapshot_keep_last_exceeds_maximum_rejected(self) -> None:
        """Test that snapshot_keep_last=101 exceeds the max and is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(snapshot_keep_last=101)
        errors = exc_info.value.errors()
        assert any(
            e["loc"] == ("snapshot_keep_last",) and "less than or equal to" in str(e["msg"])
            for e in errors
        ), f"Expected le validation error for snapshot_keep_last, got: {errors}"

    # --- Below minimum (must reject) ---

    @pytest.mark.requirement("T1-AC-1")
    def test_ttl_hours_zero_rejected(self) -> None:
        """Test that default_ttl_hours=0 is rejected (ge=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(default_ttl_hours=0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("default_ttl_hours",) for e in errors), (
            f"Expected validation error for default_ttl_hours, got: {errors}"
        )

    @pytest.mark.requirement("T1-AC-1")
    def test_snapshot_keep_last_zero_rejected(self) -> None:
        """Test that snapshot_keep_last=0 is rejected (ge=1)."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(snapshot_keep_last=0)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("snapshot_keep_last",) for e in errors), (
            f"Expected validation error for snapshot_keep_last, got: {errors}"
        )

    @pytest.mark.requirement("T1-AC-1")
    def test_ttl_hours_negative_rejected(self) -> None:
        """Test that default_ttl_hours=-1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(default_ttl_hours=-1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("default_ttl_hours",) for e in errors), (
            f"Expected validation error for default_ttl_hours, got: {errors}"
        )

    @pytest.mark.requirement("T1-AC-1")
    def test_snapshot_keep_last_negative_rejected(self) -> None:
        """Test that snapshot_keep_last=-1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ResolvedGovernance(snapshot_keep_last=-1)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("snapshot_keep_last",) for e in errors), (
            f"Expected validation error for snapshot_keep_last, got: {errors}"
        )

    # --- Large overflow values ---

    @pytest.mark.requirement("T1-AC-1")
    def test_ttl_hours_very_large_rejected(self) -> None:
        """Test that default_ttl_hours=100000 is rejected."""
        with pytest.raises(ValidationError):
            ResolvedGovernance(default_ttl_hours=100000)

    @pytest.mark.requirement("T1-AC-1")
    def test_snapshot_keep_last_very_large_rejected(self) -> None:
        """Test that snapshot_keep_last=999 is rejected."""
        with pytest.raises(ValidationError):
            ResolvedGovernance(snapshot_keep_last=999)

    # --- Frozen immutability ---

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_are_frozen(self) -> None:
        """Test that lifecycle fields cannot be mutated after creation."""
        governance = ResolvedGovernance(default_ttl_hours=24, snapshot_keep_last=3)
        with pytest.raises(ValidationError):
            governance.default_ttl_hours = 48  # type: ignore[misc]
        with pytest.raises(ValidationError):
            governance.snapshot_keep_last = 5  # type: ignore[misc]

    # --- Serialization roundtrip ---

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_serialization_roundtrip(self) -> None:
        """Test that lifecycle fields survive model_dump / model_validate roundtrip."""
        governance = ResolvedGovernance(
            pii_encryption="required",
            default_ttl_hours=168,
            snapshot_keep_last=7,
        )
        data = governance.model_dump(mode="json")
        restored = ResolvedGovernance.model_validate(data)
        assert restored.default_ttl_hours == 168
        assert restored.snapshot_keep_last == 7
        assert restored.pii_encryption == "required"

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_none_serialization_roundtrip(self) -> None:
        """Test that None lifecycle fields survive roundtrip."""
        governance = ResolvedGovernance()
        data = governance.model_dump(mode="json")
        restored = ResolvedGovernance.model_validate(data)
        assert restored.default_ttl_hours is None
        assert restored.snapshot_keep_last is None

    @pytest.mark.requirement("T1-AC-1")
    def test_lifecycle_fields_present_in_json_schema(self) -> None:
        """Test that lifecycle fields appear in the JSON schema with correct constraints."""
        schema = ResolvedGovernance.model_json_schema()
        props = schema["properties"]

        def _int_branch(field_schema: dict[str, Any]) -> dict[str, Any]:
            """Extract the integer branch from anyOf (Pydantic v2 nullable output)."""
            any_of = field_schema.get("anyOf", [])
            for branch in any_of:
                if branch.get("type") == "integer":
                    return branch
            return field_schema  # fallback: flat schema

        assert "default_ttl_hours" in props, "default_ttl_hours missing from schema"
        ttl_int = _int_branch(props["default_ttl_hours"])
        # Check ge=1 constraint
        assert ttl_int.get("minimum") == 1 or ttl_int.get("exclusiveMinimum") == 0, (
            f"default_ttl_hours missing ge=1 constraint: {ttl_int}"
        )
        # Check le=8760 constraint
        assert ttl_int.get("maximum") == 8760 or ttl_int.get("exclusiveMaximum") == 8761, (
            f"default_ttl_hours missing le=8760 constraint: {ttl_int}"
        )

        assert "snapshot_keep_last" in props, "snapshot_keep_last missing from schema"
        snap_int = _int_branch(props["snapshot_keep_last"])
        # Check ge=1 constraint
        assert snap_int.get("minimum") == 1 or snap_int.get("exclusiveMinimum") == 0, (
            f"snapshot_keep_last missing ge=1 constraint: {snap_int}"
        )
        # Check le=100 constraint
        assert snap_int.get("maximum") == 100 or snap_int.get("exclusiveMaximum") == 101, (
            f"snapshot_keep_last missing le=100 constraint: {snap_int}"
        )


class TestCompiledArtifactsVersionBump:
    """Tests for AC-6: current contract version and history entries."""

    @pytest.mark.requirement("T1-AC-6")
    def test_compiled_artifacts_version_is_0_12_0(self) -> None:
        """Test that COMPILED_ARTIFACTS_VERSION is exactly '0.15.0'."""
        assert COMPILED_ARTIFACTS_VERSION == "0.15.0", (
            f"Expected version '0.15.0', got '{COMPILED_ARTIFACTS_VERSION}'"
        )

    @pytest.mark.requirement("T1-AC-6")
    def test_version_history_contains_0_12_0(self) -> None:
        """Test that COMPILED_ARTIFACTS_VERSION_HISTORY has a '0.15.0' entry."""
        assert "0.15.0" in COMPILED_ARTIFACTS_VERSION_HISTORY, (
            f"Version '0.15.0' not in history: {list(COMPILED_ARTIFACTS_VERSION_HISTORY.keys())}"
        )

    @pytest.mark.requirement("T1-AC-6")
    def test_version_history_0_12_0_references_iceberg_catalog_projection(self) -> None:
        """Test that the 0.15.0 history entry mentions contract additions."""
        entry = COMPILED_ARTIFACTS_VERSION_HISTORY.get("0.15.0", "")
        entry_lower = entry.lower()
        assert "iceberg" in entry_lower and "catalog" in entry_lower, (
            f"Version 0.15.0 history entry does not reference Iceberg catalog projection: '{entry}'"
        )

    @pytest.mark.requirement("T1-AC-6")
    def test_compiled_artifacts_default_version_is_0_12_0(self) -> None:
        """Test that CompiledArtifacts().version defaults to '0.15.0'."""
        artifacts = CompiledArtifacts(
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.9.0",
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
        assert artifacts.version == "0.15.0"


class TestGovernanceBackwardCompatibility:
    """Tests for AC-7: backward compatibility with pre-0.9.0 governance data."""

    @pytest.mark.requirement("T1-AC-7")
    def test_old_governance_dict_without_lifecycle_fields_deserializes(self) -> None:
        """Test that pre-0.9.0 governance JSON (no lifecycle fields) deserializes with None."""
        old_governance_data: dict[str, Any] = {
            "pii_encryption": "required",
            "audit_logging": "enabled",
            "policy_enforcement_level": "strict",
            "data_retention_days": 90,
        }
        governance = ResolvedGovernance.model_validate(old_governance_data)
        assert governance.pii_encryption == "required"
        assert governance.audit_logging == "enabled"
        assert governance.policy_enforcement_level == "strict"
        assert governance.data_retention_days == 90
        assert governance.default_ttl_hours is None
        assert governance.snapshot_keep_last is None

    @pytest.mark.requirement("T1-AC-7")
    def test_empty_governance_dict_deserializes(self) -> None:
        """Test that empty governance dict deserializes with all fields None."""
        governance = ResolvedGovernance.model_validate({})
        assert governance.default_ttl_hours is None
        assert governance.snapshot_keep_last is None
        assert governance.pii_encryption is None

    @pytest.mark.requirement("T1-AC-7")
    def test_new_governance_dict_with_lifecycle_fields_deserializes(self) -> None:
        """Test that 0.9.0 governance JSON with lifecycle fields deserializes correctly."""
        new_governance_data: dict[str, Any] = {
            "pii_encryption": "optional",
            "default_ttl_hours": 48,
            "snapshot_keep_last": 5,
        }
        governance = ResolvedGovernance.model_validate(new_governance_data)
        assert governance.pii_encryption == "optional"
        assert governance.default_ttl_hours == 48
        assert governance.snapshot_keep_last == 5

    @pytest.mark.requirement("T1-AC-7")
    def test_full_compiled_artifacts_without_lifecycle_fields_deserializes(
        self,
        sample_compilation_metadata: CompilationMetadata,
        sample_product_identity: ProductIdentity,
        sample_observability_config: ObservabilityConfig,
    ) -> None:
        """Test full CompiledArtifacts with old-style governance roundtrips correctly."""
        # Build artifacts with governance that has no lifecycle fields
        artifacts = CompiledArtifacts(
            metadata=sample_compilation_metadata,
            identity=sample_product_identity,
            observability=sample_observability_config,
            governance=ResolvedGovernance(
                pii_encryption="required",
                data_retention_days=365,
            ),
        )
        # Serialize to dict, remove lifecycle fields to simulate old format
        data = artifacts.model_dump(mode="json")
        gov_data = data["governance"]
        gov_data.pop("default_ttl_hours", None)
        gov_data.pop("snapshot_keep_last", None)

        # Deserialize - must not fail
        restored = CompiledArtifacts.model_validate(data)
        assert restored.governance is not None
        assert restored.governance.pii_encryption == "required"
        assert restored.governance.data_retention_days == 365
        assert restored.governance.default_ttl_hours is None
        assert restored.governance.snapshot_keep_last is None
