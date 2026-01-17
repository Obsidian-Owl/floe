"""Cross-package contract tests: floe-core to floe-dagster.

These tests validate that floe-dagster can correctly consume
CompiledArtifacts produced by floe-core's compilation pipeline.

Contract tests ensure:
- CompiledArtifacts can be imported from floe_core
- CompiledArtifacts can be loaded from JSON files
- Required fields for asset creation exist and have correct types
- dbt_profiles field is usable for dbt profile configuration

Requirements Covered:
- FR-004: CompiledArtifacts as stable cross-package contract
- SC-001: CompiledArtifacts schema stability
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest


class TestDagsterCanImportCompiledArtifacts:
    """Verify floe-dagster can import CompiledArtifacts from floe-core."""

    @pytest.mark.requirement("FR-004")
    def test_can_import_compiled_artifacts(self) -> None:
        """Test CompiledArtifacts can be imported from floe_core."""
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        assert CompiledArtifacts is not None
        assert hasattr(CompiledArtifacts, "model_validate")
        assert hasattr(CompiledArtifacts, "from_json_file")

    @pytest.mark.requirement("FR-004")
    def test_can_import_all_required_types(self) -> None:
        """Test all types needed for dagster integration can be imported."""
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

        # Verify all types are importable
        assert CompiledArtifacts is not None
        assert CompilationMetadata is not None
        assert ObservabilityConfig is not None
        assert ProductIdentity is not None
        assert PluginRef is not None
        assert ResolvedPlugins is not None
        assert ResolvedModel is not None
        assert ResolvedTransforms is not None


class TestDagsterCanLoadCompiledArtifactsFromFile:
    """Verify floe-dagster can load CompiledArtifacts from JSON files."""

    @pytest.fixture
    def sample_artifacts_json(self, tmp_path: Path) -> Path:
        """Create a sample compiled_artifacts.json file."""
        from floe_core.telemetry.config import ResourceAttributes, TelemetryConfig

        artifacts_data: dict[str, Any] = {
            "version": "0.2.0",
            "metadata": {
                "compiled_at": datetime.now().isoformat(),
                "floe_version": "0.2.0",
                "source_hash": "sha256:abc123def456",
                "product_name": "test-pipeline",
                "product_version": "1.0.0",
            },
            "identity": {
                "product_id": "default.test_pipeline",
                "domain": "default",
                "repository": "https://github.com/test/test-pipeline",
            },
            "mode": "simple",
            "inheritance_chain": [],
            "observability": {
                "telemetry": TelemetryConfig(
                    enabled=True,
                    resource_attributes=ResourceAttributes(
                        service_name="test-pipeline",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="default",
                        floe_product_name="test-pipeline",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ).model_dump(mode="json"),
                "lineage": True,
                "lineage_namespace": "test-pipeline",
            },
            "plugins": {
                "compute": {"type": "duckdb", "version": "0.9.0", "config": None},
                "orchestrator": {"type": "dagster", "version": "1.5.0", "config": None},
                "catalog": None,
                "storage": None,
                "ingestion": None,
                "semantic": None,
            },
            "transforms": {
                "models": [
                    {
                        "name": "stg_customers",
                        "compute": "duckdb",
                        "tags": ["staging"],
                        "depends_on": None,
                    },
                    {
                        "name": "fct_orders",
                        "compute": "duckdb",
                        "tags": ["marts"],
                        "depends_on": ["stg_customers"],
                    },
                ],
                "default_compute": "duckdb",
            },
            "dbt_profiles": {
                "test-pipeline": {
                    "target": "dev",
                    "outputs": {
                        "dev": {
                            "type": "duckdb",
                            "path": ":memory:",
                            "threads": 4,
                        }
                    },
                }
            },
            "governance": None,
        }

        json_path = tmp_path / "compiled_artifacts.json"
        json_path.write_text(json.dumps(artifacts_data, indent=2))
        return json_path

    @pytest.mark.requirement("FR-004")
    def test_can_load_from_json_file(self, sample_artifacts_json: Path) -> None:
        """Test CompiledArtifacts can be loaded from JSON file."""
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        artifacts = CompiledArtifacts.from_json_file(sample_artifacts_json)

        assert artifacts.version == "0.2.0"
        assert artifacts.metadata.product_name == "test-pipeline"

    @pytest.mark.requirement("FR-004")
    def test_loaded_artifacts_have_required_fields(
        self, sample_artifacts_json: Path
    ) -> None:
        """Test loaded artifacts have all fields required for dagster asset creation."""
        from floe_core.schemas.compiled_artifacts import CompiledArtifacts

        artifacts = CompiledArtifacts.from_json_file(sample_artifacts_json)

        # Required for asset naming
        assert artifacts.metadata.product_name is not None
        assert len(artifacts.metadata.product_name) > 0

        # Required for transform assets
        assert artifacts.transforms is not None
        assert artifacts.transforms.models is not None
        assert len(artifacts.transforms.models) > 0

        # Required for dbt execution
        assert artifacts.dbt_profiles is not None
        assert isinstance(artifacts.dbt_profiles, dict)

        # Required for plugin selection
        assert artifacts.plugins is not None
        assert artifacts.plugins.compute is not None
        assert artifacts.plugins.orchestrator is not None


class TestDagsterCanUseTransformsForAssetCreation:
    """Verify transforms field contains all data needed for Dagster asset creation."""

    @pytest.mark.requirement("FR-004")
    def test_resolved_model_has_required_fields(self) -> None:
        """Test ResolvedModel has all fields needed for asset definition."""
        from floe_core.schemas.compiled_artifacts import ResolvedModel

        model = ResolvedModel(
            name="stg_customers",
            compute="duckdb",
            tags=["staging", "customers"],
            depends_on=["raw_customers"],
        )

        # Asset name
        assert model.name == "stg_customers"
        assert isinstance(model.name, str)

        # Compute target for resource selection
        assert model.compute == "duckdb"
        assert isinstance(model.compute, str)

        # Tags for asset grouping
        assert model.tags == ["staging", "customers"]
        assert isinstance(model.tags, list)

        # Dependencies for DAG construction
        assert model.depends_on == ["raw_customers"]
        assert isinstance(model.depends_on, list)

    @pytest.mark.requirement("FR-004")
    def test_resolved_transforms_provides_default_compute(self) -> None:
        """Test ResolvedTransforms provides default compute for fallback."""
        from floe_core.schemas.compiled_artifacts import (
            ResolvedModel,
            ResolvedTransforms,
        )

        transforms = ResolvedTransforms(
            models=[
                ResolvedModel(name="stg_customers", compute="duckdb"),
            ],
            default_compute="duckdb",
        )

        # Default compute for resource configuration
        assert transforms.default_compute == "duckdb"
        assert isinstance(transforms.default_compute, str)

        # Models list for asset iteration
        assert len(transforms.models) == 1
        assert transforms.models[0].name == "stg_customers"


class TestDagsterCanUseDbtProfiles:
    """Verify dbt_profiles field is usable for dbt profile configuration."""

    @pytest.mark.requirement("FR-004")
    def test_dbt_profiles_structure(self) -> None:
        """Test dbt_profiles has expected structure for profiles.yml generation."""
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

        dbt_profiles: dict[str, Any] = {
            "my-pipeline": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": ":memory:",
                        "threads": 4,
                    }
                },
            }
        }

        artifacts = CompiledArtifacts(
            version="0.2.0",
            metadata=CompilationMetadata(
                compiled_at=datetime.now(),
                floe_version="0.2.0",
                source_hash="sha256:abc123",
                product_name="my-pipeline",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.my_pipeline",
                domain="default",
                repository="https://github.com/test/my-pipeline",
            ),
            inheritance_chain=[],
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    resource_attributes=ResourceAttributes(
                        service_name="my-pipeline",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="default",
                        floe_product_name="my-pipeline",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="my-pipeline",
            ),
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
            ),
            transforms=ResolvedTransforms(
                models=[ResolvedModel(name="stg_customers", compute="duckdb")],
                default_compute="duckdb",
            ),
            dbt_profiles=dbt_profiles,
        )

        # Verify dbt_profiles is usable
        assert artifacts.dbt_profiles is not None
        assert "my-pipeline" in artifacts.dbt_profiles

        profile = artifacts.dbt_profiles["my-pipeline"]
        assert "target" in profile
        assert profile["target"] == "dev"
        assert "outputs" in profile
        assert "dev" in profile["outputs"]

        output = profile["outputs"]["dev"]
        assert output["type"] == "duckdb"
        assert output["path"] == ":memory:"
        assert output["threads"] == 4

    @pytest.mark.requirement("FR-004")
    def test_dbt_profiles_can_be_serialized_to_yaml(self, tmp_path: Path) -> None:
        """Test dbt_profiles can be written to profiles.yml format."""
        import yaml

        dbt_profiles: dict[str, Any] = {
            "my-pipeline": {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "duckdb",
                        "path": ":memory:",
                        "threads": 4,
                    }
                },
            }
        }

        # Write to profiles.yml (as dagster would do)
        profiles_path = tmp_path / "profiles.yml"
        profiles_path.write_text(yaml.safe_dump(dbt_profiles))

        # Read back and verify
        loaded = yaml.safe_load(profiles_path.read_text())
        assert loaded["my-pipeline"]["target"] == "dev"
        assert loaded["my-pipeline"]["outputs"]["dev"]["type"] == "duckdb"


class TestDagsterCanUsePluginsForResourceConfiguration:
    """Verify plugins field provides data for Dagster resource configuration."""

    @pytest.mark.requirement("FR-004")
    def test_plugin_ref_provides_type_and_version(self) -> None:
        """Test PluginRef provides type and version for resource selection."""
        from floe_core.schemas.compiled_artifacts import PluginRef

        plugin = PluginRef(
            type="duckdb",
            version="0.9.0",
            config={"threads": 4, "memory_limit": "8GB"},
        )

        # Type for plugin selection
        assert plugin.type == "duckdb"
        assert isinstance(plugin.type, str)

        # Version for compatibility checks
        assert plugin.version == "0.9.0"
        assert isinstance(plugin.version, str)

        # Config for resource configuration
        assert plugin.config is not None
        assert plugin.config["threads"] == 4
        assert plugin.config["memory_limit"] == "8GB"

    @pytest.mark.requirement("FR-004")
    def test_resolved_plugins_provides_all_plugin_types(self) -> None:
        """Test ResolvedPlugins provides access to all plugin types."""
        from floe_core.schemas.compiled_artifacts import PluginRef, ResolvedPlugins

        plugins = ResolvedPlugins(
            compute=PluginRef(type="duckdb", version="0.9.0"),
            orchestrator=PluginRef(type="dagster", version="1.5.0"),
            catalog=PluginRef(type="polaris", version="0.1.0"),
            storage=None,
            ingestion=None,
            semantic=None,
        )

        # Required plugins
        assert plugins.compute.type == "duckdb"
        assert plugins.orchestrator.type == "dagster"

        # Optional plugins
        assert plugins.catalog is not None
        assert plugins.catalog.type == "polaris"
        assert plugins.storage is None
        assert plugins.ingestion is None
        assert plugins.semantic is None


class TestCompiledArtifactsRoundtrip:
    """Verify CompiledArtifacts can be serialized and deserialized correctly."""

    @pytest.mark.requirement("SC-001")
    def test_json_roundtrip(self, tmp_path: Path) -> None:
        """Test CompiledArtifacts JSON roundtrip preserves all data."""
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

        original = CompiledArtifacts(
            version="0.2.0",
            metadata=CompilationMetadata(
                compiled_at=datetime(2026, 1, 17, 12, 0, 0),
                floe_version="0.2.0",
                source_hash="sha256:abc123",
                product_name="roundtrip-test",
                product_version="1.0.0",
            ),
            identity=ProductIdentity(
                product_id="default.roundtrip_test",
                domain="default",
                repository="https://github.com/test/roundtrip-test",
            ),
            inheritance_chain=[],
            observability=ObservabilityConfig(
                telemetry=TelemetryConfig(
                    resource_attributes=ResourceAttributes(
                        service_name="roundtrip-test",
                        service_version="1.0.0",
                        deployment_environment="dev",
                        floe_namespace="default",
                        floe_product_name="roundtrip-test",
                        floe_product_version="1.0.0",
                        floe_mode="dev",
                    ),
                ),
                lineage_namespace="roundtrip-test",
            ),
            plugins=ResolvedPlugins(
                compute=PluginRef(type="duckdb", version="0.9.0"),
                orchestrator=PluginRef(type="dagster", version="1.5.0"),
            ),
            transforms=ResolvedTransforms(
                models=[
                    ResolvedModel(
                        name="stg_customers",
                        compute="duckdb",
                        tags=["staging"],
                        depends_on=["raw_customers"],
                    )
                ],
                default_compute="duckdb",
            ),
            dbt_profiles={
                "roundtrip-test": {
                    "target": "dev",
                    "outputs": {"dev": {"type": "duckdb", "path": ":memory:"}},
                }
            },
        )

        # Serialize to JSON
        json_path = tmp_path / "artifacts.json"
        original.to_json_file(json_path)

        # Deserialize back
        loaded = CompiledArtifacts.from_json_file(json_path)

        # Verify roundtrip
        assert loaded.version == original.version
        assert loaded.metadata.product_name == original.metadata.product_name
        assert loaded.identity.product_id == original.identity.product_id

        # Verify plugins roundtrip (with null checks for type safety)
        assert loaded.plugins is not None
        assert original.plugins is not None
        assert loaded.plugins.compute.type == original.plugins.compute.type

        # Verify transforms roundtrip (with null checks for type safety)
        assert loaded.transforms is not None
        assert original.transforms is not None
        assert len(loaded.transforms.models) == len(original.transforms.models)
        assert loaded.transforms.models[0].name == original.transforms.models[0].name

        assert loaded.dbt_profiles == original.dbt_profiles
