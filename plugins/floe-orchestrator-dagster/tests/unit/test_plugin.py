"""Unit tests for DagsterOrchestratorPlugin.

These tests verify the Dagster orchestrator plugin implementation without
requiring external services.

Requirements Covered:
- FR-002: Implement all abstract methods from OrchestratorPlugin ABC
- FR-003: Plugin declares name, version, floe_api_version
- FR-004: Plugin inherits from OrchestratorPlugin and PluginMetadata
- FR-005: Generate valid Dagster Definitions from CompiledArtifacts
- FR-006: Create Dagster software-defined assets from TransformConfig
- FR-007: Preserve dbt model dependency graph as Dagster asset dependencies
- FR-008: Include transform metadata in asset metadata
- FR-009: Validate CompiledArtifacts schema before generating definitions
- SC-001: Plugin passes all 7 abstract method compliance tests
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from floe_core.plugins.orchestrator import OrchestratorPlugin

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestDagsterOrchestratorPluginMetadata:
    """Test plugin metadata properties.

    Validates FR-002, FR-003, FR-004 from spec:
    - FR-002: Implement all abstract methods from OrchestratorPlugin ABC
    - FR-003: Plugin declares name, version, floe_api_version
    - FR-004: Plugin inherits from OrchestratorPlugin and PluginMetadata
    """

    @pytest.mark.requirement("FR-003")
    def test_plugin_name(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin name is 'dagster'."""
        assert dagster_plugin.name == "dagster"

    @pytest.mark.requirement("FR-003")
    def test_plugin_version(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin version follows semver format."""
        version = dagster_plugin.version
        parts = version.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)

    @pytest.mark.requirement("FR-003")
    def test_floe_api_version(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test floe API version is specified."""
        api_version = dagster_plugin.floe_api_version
        assert api_version == "1.0"

    @pytest.mark.requirement("FR-003")
    def test_plugin_description(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin has a meaningful description."""
        assert isinstance(dagster_plugin.description, str)
        assert len(dagster_plugin.description) >= 10
        assert "dagster" in dagster_plugin.description.lower()


class TestDagsterOrchestratorPluginABCCompliance:
    """Test ABC compliance verification.

    Validates SC-001: Plugin passes all 7 abstract method compliance tests
    defined in OrchestratorPlugin ABC.
    """

    @pytest.mark.requirement("SC-001")
    def test_inherits_from_orchestrator_plugin(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin inherits from OrchestratorPlugin ABC."""
        assert isinstance(dagster_plugin, OrchestratorPlugin)

    @pytest.mark.requirement("SC-001")
    def test_create_definitions_callable(
        self, dagster_plugin: DagsterOrchestratorPlugin, valid_compiled_artifacts: Any
    ) -> None:
        """Test plugin implements create_definitions method."""
        # ABC compliance already validated by isinstance check above
        from dagster import Definitions

        result = dagster_plugin.create_definitions(valid_compiled_artifacts)
        assert isinstance(result, Definitions)

    @pytest.mark.requirement("SC-001")
    def test_create_assets_from_transforms_callable(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements create_assets_from_transforms method."""
        # ABC compliance already validated by isinstance check above
        result = dagster_plugin.create_assets_from_transforms([])
        assert isinstance(result, list)

    @pytest.mark.requirement("SC-001")
    def test_get_helm_values_callable(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin implements get_helm_values method."""
        # ABC compliance already validated by isinstance check above
        result = dagster_plugin.get_helm_values()
        assert isinstance(result, dict)

    @pytest.mark.requirement("SC-001")
    def test_validate_connection_callable(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements validate_connection method."""
        # ABC compliance already validated by isinstance check above
        from floe_core.plugins.orchestrator import ValidationResult

        result = dagster_plugin.validate_connection("http://localhost:9999", timeout=0.1)
        assert isinstance(result, ValidationResult)

    @pytest.mark.requirement("SC-001")
    def test_get_resource_requirements_callable(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test plugin implements get_resource_requirements method."""
        # ABC compliance already validated by isinstance check above
        from floe_core.plugins.orchestrator import ResourceSpec

        result = dagster_plugin.get_resource_requirements("small")
        assert isinstance(result, ResourceSpec)

    @pytest.mark.requirement("SC-001")
    def test_emit_lineage_event_callable(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin implements emit_lineage_event method."""
        # ABC compliance already validated by isinstance check above
        from floe_core.lineage import LineageDataset, RunState

        dagster_plugin.emit_lineage_event(
            RunState.START,
            "test_job",
            inputs=[LineageDataset(namespace="floe", name="input")],
            outputs=[LineageDataset(namespace="floe", name="output")],
        )

    @pytest.mark.requirement("SC-001")
    def test_schedule_job_callable(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test plugin implements schedule_job method."""
        # ABC compliance already validated by isinstance check above
        dagster_plugin.schedule_job("daily_refresh", "0 8 * * *", "UTC")


class TestDagsterOrchestratorPluginInstantiation:
    """Test plugin instantiation and basic operations."""

    @pytest.mark.requirement("FR-002")
    def test_plugin_can_be_instantiated(self) -> None:
        """Test plugin can be instantiated without arguments."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin

        plugin = DagsterOrchestratorPlugin()
        assert isinstance(plugin, DagsterOrchestratorPlugin)
        assert plugin.name == "dagster"

    @pytest.mark.requirement("FR-002")
    def test_plugin_can_be_imported_from_package(self) -> None:
        """Test plugin is exported from package __init__.py."""
        from floe_orchestrator_dagster import DagsterOrchestratorPlugin
        from floe_core.plugins.orchestrator import OrchestratorPlugin

        assert issubclass(DagsterOrchestratorPlugin, OrchestratorPlugin)

    @pytest.mark.requirement("FR-003")
    def test_version_exported_from_package(self) -> None:
        """Test __version__ is exported from package."""
        from floe_orchestrator_dagster import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0
        assert "." in __version__


class TestDagsterOrchestratorPluginCreateDefinitions:
    """Test create_definitions method.

    Validates FR-005: System MUST generate valid Dagster Definitions
    object from CompiledArtifacts.
    Validates FR-009: System MUST validate CompiledArtifacts schema
    before generating definitions.
    """

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_with_valid_artifacts(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: Any,
    ) -> None:
        """Test create_definitions succeeds with valid CompiledArtifacts."""
        from dagster import Definitions

        result = dagster_plugin.create_definitions(valid_compiled_artifacts)

        assert isinstance(result, Definitions)

    @pytest.mark.requirement("FR-005")
    def test_create_definitions_with_multiple_models(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts_with_models: Any,
    ) -> None:
        """Test create_definitions creates assets for multiple models."""
        from dagster import Definitions

        result = dagster_plugin.create_definitions(valid_compiled_artifacts_with_models)

        assert isinstance(result, Definitions)
        # Verify definitions were created - check that assets are accessible
        # The number of models in the fixture is 3
        assert len(result.assets) == 3


class TestDagsterOrchestratorPluginValidation:
    """Test CompiledArtifacts validation (FR-009).

    Validates FR-009: System MUST validate CompiledArtifacts schema
    before generating definitions.
    """

    @pytest.mark.requirement("FR-009")
    def test_create_definitions_rejects_empty_artifacts(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test create_definitions raises ValueError for empty artifacts."""
        with pytest.raises(ValueError, match="CompiledArtifacts validation failed"):
            dagster_plugin.create_definitions({})

    @pytest.mark.requirement("FR-009")
    def test_create_definitions_rejects_missing_metadata(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: Any,
    ) -> None:
        """Test create_definitions raises ValueError for missing metadata."""
        del valid_compiled_artifacts["metadata"]

        with pytest.raises(ValueError, match="metadata"):
            dagster_plugin.create_definitions(valid_compiled_artifacts)

    @pytest.mark.requirement("FR-009")
    def test_create_definitions_rejects_missing_identity(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        valid_compiled_artifacts: Any,
    ) -> None:
        """Test create_definitions raises ValueError for missing identity."""
        del valid_compiled_artifacts["identity"]

        with pytest.raises(ValueError, match="identity"):
            dagster_plugin.create_definitions(valid_compiled_artifacts)

    @pytest.mark.requirement("FR-009")
    def test_validation_error_includes_actionable_message(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validation error includes actionable guidance."""
        with pytest.raises(ValueError, match="Ensure you are passing output from 'floe compile'"):
            dagster_plugin.create_definitions({})


class TestDagsterOrchestratorPluginCreateAssets:
    """Test create_assets_from_transforms method.

    Validates FR-006: System MUST create Dagster software-defined assets
    from TransformConfig list.
    Validates FR-007: System MUST preserve dbt model dependency graph as
    Dagster asset dependencies.
    """

    @pytest.mark.requirement("FR-006")
    def test_create_assets_empty_list(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test create_assets_from_transforms returns empty list for empty input."""
        assets = dagster_plugin.create_assets_from_transforms([])
        assert isinstance(assets, list)
        assert len(assets) == 0

    @pytest.mark.requirement("FR-006")
    def test_create_assets_single_transform(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: Any,
    ) -> None:
        """Test create_assets_from_transforms creates asset for single transform."""
        assets = dagster_plugin.create_assets_from_transforms([sample_transform_config])
        assert len(assets) == 1

    @pytest.mark.requirement("FR-006")
    def test_create_assets_multiple_transforms(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_configs: list[Any],
    ) -> None:
        """Test create_assets_from_transforms creates assets for multiple transforms."""
        assets = dagster_plugin.create_assets_from_transforms(sample_transform_configs)
        assert len(assets) == 3  # raw_customers, stg_customers, dim_customers

    @pytest.mark.requirement("FR-007")
    def test_create_assets_preserves_dependencies(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_configs: list[Any],
    ) -> None:
        """Test create_assets_from_transforms preserves dependency graph."""
        from dagster import AssetKey

        assets = dagster_plugin.create_assets_from_transforms(sample_transform_configs)

        # Find dim_customers asset and check its dependencies
        # dim_customers depends on stg_customers
        dim_asset = next(a for a in assets if a.key.path[-1] == "dim_customers")
        assert AssetKey(["stg_customers"]) in dim_asset.dependency_keys

    @pytest.mark.requirement("FR-008")
    def test_create_assets_includes_transform_metadata(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: Any,
    ) -> None:
        """Test asset includes transform metadata.

        Validates FR-008: System MUST include transform metadata (tags,
        compute target, schema) in asset metadata.
        """
        assets = dagster_plugin.create_assets_from_transforms([sample_transform_config])
        assert len(assets) == 1

        asset = assets[0]
        # Access metadata from the asset's spec
        metadata = asset.specs_by_key[asset.key].metadata

        # Verify all transform metadata is present
        assert metadata["compute"] == "duckdb"
        assert metadata["schema"] == "staging"
        assert metadata["materialization"] == "view"
        assert metadata["tags"] == ["daily", "core"]
        assert metadata["path"] == "models/staging/stg_customers.sql"


class TestDagsterOrchestratorPluginSkeletonMethods:
    """Test implemented plugin methods.

    These tests verify the plugin methods work correctly.
    """

    @pytest.mark.requirement("FR-010")
    def test_get_helm_values_returns_dict(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test get_helm_values returns a dictionary."""
        result = dagster_plugin.get_helm_values()
        assert isinstance(result, dict)
        assert "dagster-webserver" in result
        assert "dagster-daemon" in result
        assert "dagster-user-code" in result

    @pytest.mark.requirement("FR-011")
    def test_validate_connection_returns_validation_result(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test validate_connection returns ValidationResult."""
        from floe_core.plugins.orchestrator import ValidationResult

        # With no Dagster running, should return failure
        result = dagster_plugin.validate_connection(
            dagster_url="http://localhost:9999",  # Non-existent
            timeout=1.0,
        )

        assert isinstance(result, ValidationResult)
        assert result.success is False
        assert len(result.errors) >= 1

    @pytest.mark.requirement("FR-012")
    def test_get_resource_requirements_small(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements returns ResourceSpec for small."""
        from floe_core.plugins.orchestrator import ResourceSpec

        result = dagster_plugin.get_resource_requirements("small")
        assert isinstance(result, ResourceSpec)
        assert result.cpu_request == "100m"
        assert result.memory_limit == "512Mi"

    @pytest.mark.requirement("FR-012")
    def test_get_resource_requirements_invalid_size(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test get_resource_requirements raises ValueError for invalid size."""
        with pytest.raises(ValueError, match="Invalid workload_size"):
            dagster_plugin.get_resource_requirements("invalid")

    @pytest.mark.requirement("FR-013")
    def test_emit_lineage_event_no_backend_is_noop(
        self, dagster_plugin: DagsterOrchestratorPlugin
    ) -> None:
        """Test emit_lineage_event is no-op when no backend configured."""
        from floe_core.lineage import LineageDataset, RunState

        # Should not raise - graceful no-op
        dagster_plugin.emit_lineage_event(
            RunState.START,
            "test_job",
            inputs=[LineageDataset(namespace="floe", name="input")],
            outputs=[LineageDataset(namespace="floe", name="output")],
        )

    @pytest.mark.requirement("FR-014")
    def test_schedule_job_creates_schedule(self, dagster_plugin: DagsterOrchestratorPlugin) -> None:
        """Test schedule_job creates a ScheduleDefinition."""
        # Should not raise - schedule is created successfully
        dagster_plugin.schedule_job("daily_refresh", "0 8 * * *", "UTC")

        # Verify schedule was stored
        assert hasattr(dagster_plugin, "_schedules")
        assert len(dagster_plugin._schedules) == 1
        assert dagster_plugin._schedules[0].name == "daily_refresh_schedule"
