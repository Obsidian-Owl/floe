"""Unit tests for asset creation in DagsterOrchestratorPlugin.

These tests verify the create_assets_from_transforms() method and related
asset creation functionality, including dependency handling and metadata.

Note: @pytest.mark.requirement markers are used for traceability to spec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from floe_core.plugins.orchestrator import TransformConfig

if TYPE_CHECKING:
    from floe_orchestrator_dagster import DagsterOrchestratorPlugin


class TestAssetCreationBasics:
    """Test basic asset creation from TransformConfig.

    Validates FR-006: System MUST create Dagster software-defined assets
    from TransformConfig list.
    """

    @pytest.mark.requirement("FR-006")
    def test_create_assets_returns_list(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test create_assets_from_transforms returns a list."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        assert isinstance(result, list)

    @pytest.mark.requirement("FR-006")
    def test_create_assets_returns_assets_definitions(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test create_assets_from_transforms returns AssetsDefinition objects."""
        from dagster import AssetsDefinition

        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        assert len(result) == 1
        assert isinstance(result[0], AssetsDefinition)

    @pytest.mark.requirement("FR-006")
    def test_asset_has_correct_key(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset key matches transform name."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        assert asset.key.path[-1] == sample_transform_config.name

    @pytest.mark.requirement("FR-006")
    def test_create_assets_empty_list(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test create_assets_from_transforms handles empty list."""
        result = dagster_plugin.create_assets_from_transforms([])

        assert result == []

    @pytest.mark.requirement("FR-006")
    def test_create_assets_multiple_transforms(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_configs: list[TransformConfig],
    ) -> None:
        """Test create_assets_from_transforms handles multiple transforms."""
        result = dagster_plugin.create_assets_from_transforms(sample_transform_configs)

        assert len(result) == len(sample_transform_configs)


class TestAssetDependencies:
    """Test asset dependency handling.

    Validates FR-007: System MUST preserve dbt model dependency graph as
    Dagster asset dependencies.
    """

    @pytest.mark.requirement("FR-007")
    def test_asset_with_single_dependency(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test asset with single dependency has correct deps."""
        from dagster import AssetKey

        transform = TransformConfig(
            name="child_model",
            depends_on=["parent_model"],
        )

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        assert AssetKey(["parent_model"]) in asset.dependency_keys

    @pytest.mark.requirement("FR-007")
    def test_asset_with_multiple_dependencies(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test asset with multiple dependencies has all deps."""
        from dagster import AssetKey

        transform = TransformConfig(
            name="mart_model",
            depends_on=["stg_orders", "stg_customers", "stg_products"],
        )

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        assert AssetKey(["stg_orders"]) in asset.dependency_keys
        assert AssetKey(["stg_customers"]) in asset.dependency_keys
        assert AssetKey(["stg_products"]) in asset.dependency_keys

    @pytest.mark.requirement("FR-007")
    def test_asset_without_dependencies(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test asset without transform dependencies only has resource deps.

        Note: Dagster treats required_resource_keys (e.g., 'dbt') as
        dependency_keys, so an asset with no transform dependencies
        will still have the 'dbt' resource dependency.
        """
        from dagster import AssetKey

        transform = TransformConfig(name="source_model")

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        # Asset should only have 'dbt' resource dependency, no model deps
        assert asset.dependency_keys == {AssetKey(["dbt"])}

    @pytest.mark.requirement("FR-007")
    def test_dependency_chain_preserved(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_configs: list[TransformConfig],
    ) -> None:
        """Test full dependency chain is preserved across assets."""
        from dagster import AssetKey

        result = dagster_plugin.create_assets_from_transforms(sample_transform_configs)

        # Find each asset and verify dependencies
        asset_by_name = {a.key.path[-1]: a for a in result}

        # raw_customers has only 'dbt' resource dependency
        # (Dagster treats required_resource_keys as dependency_keys)
        assert asset_by_name["raw_customers"].dependency_keys == {AssetKey(["dbt"])}

        # stg_customers depends on raw_customers + dbt resource
        assert AssetKey(["raw_customers"]) in asset_by_name["stg_customers"].dependency_keys
        assert AssetKey(["dbt"]) in asset_by_name["stg_customers"].dependency_keys

        # dim_customers depends on stg_customers + dbt resource
        assert AssetKey(["stg_customers"]) in asset_by_name["dim_customers"].dependency_keys
        assert AssetKey(["dbt"]) in asset_by_name["dim_customers"].dependency_keys


class TestAssetMetadata:
    """Test asset metadata handling.

    Validates FR-008: System MUST include transform metadata (tags,
    compute target, schema) in asset metadata.
    """

    @pytest.mark.requirement("FR-008")
    def test_asset_includes_compute_target(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset metadata includes compute target."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        assert metadata["compute"] == sample_transform_config.compute

    @pytest.mark.requirement("FR-008")
    def test_asset_includes_schema_name(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset metadata includes schema name."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        assert metadata["schema"] == sample_transform_config.schema_name

    @pytest.mark.requirement("FR-008")
    def test_asset_includes_materialization(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset metadata includes materialization type."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        assert metadata["materialization"] == sample_transform_config.materialization

    @pytest.mark.requirement("FR-008")
    def test_asset_includes_tags(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset metadata includes tags."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        assert metadata["tags"] == sample_transform_config.tags

    @pytest.mark.requirement("FR-008")
    def test_asset_includes_path(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset metadata includes model path."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        assert metadata["path"] == sample_transform_config.path

    @pytest.mark.requirement("FR-008")
    def test_asset_metadata_omits_none_values(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test asset metadata omits fields with None values."""
        # Create transform with minimal fields
        transform = TransformConfig(name="minimal_model")

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        # Should not have compute, schema, etc. if they were None
        assert "compute" not in metadata
        assert "schema" not in metadata

    @pytest.mark.requirement("FR-008")
    def test_all_metadata_fields_included(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test all expected metadata fields are included."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata

        # All fields from a fully populated TransformConfig
        expected_fields = ["compute", "schema", "materialization", "tags", "path"]
        for field in expected_fields:
            assert field in metadata, f"Missing metadata field: {field}"


class TestAssetDescription:
    """Test asset description generation."""

    @pytest.mark.requirement("FR-006")
    def test_asset_has_description(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset has a description."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        spec = asset.specs_by_key[asset.key]
        assert isinstance(spec.description, str)
        assert len(spec.description) > 0

    @pytest.mark.requirement("FR-006")
    def test_asset_description_includes_model_name(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
        sample_transform_config: TransformConfig,
    ) -> None:
        """Test asset description includes model name."""
        result = dagster_plugin.create_assets_from_transforms([sample_transform_config])

        asset = result[0]
        spec = asset.specs_by_key[asset.key]
        assert sample_transform_config.name in spec.description


class TestAssetEdgeCases:
    """Test edge cases in asset creation."""

    @pytest.mark.requirement("FR-006")
    def test_transform_with_empty_tags(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test transform with empty tags list.

        Empty lists are falsy in Python, so _build_asset_metadata() omits them.
        This is expected behavior - no tags means no tags metadata.
        """
        transform = TransformConfig(
            name="model_no_tags",
            compute="duckdb",
            tags=[],
        )

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        metadata = asset.specs_by_key[asset.key].metadata
        # Empty tags list is omitted from metadata (falsy check)
        assert "tags" not in metadata

    @pytest.mark.requirement("FR-007")
    def test_transform_with_empty_depends_on(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test transform with empty depends_on list has only resource deps.

        Note: Dagster treats required_resource_keys as dependency_keys.
        """
        from dagster import AssetKey

        transform = TransformConfig(
            name="model_no_deps",
            depends_on=[],
        )

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        # Only 'dbt' resource dependency, no model dependencies
        assert asset.dependency_keys == {AssetKey(["dbt"])}

    @pytest.mark.requirement("FR-006")
    def test_transform_name_with_underscores(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test transform name with underscores is preserved."""
        transform = TransformConfig(name="stg_customer_orders_v2")

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        assert asset.key.path[-1] == "stg_customer_orders_v2"

    @pytest.mark.requirement("FR-006")
    def test_transform_with_long_name(
        self,
        dagster_plugin: DagsterOrchestratorPlugin,
    ) -> None:
        """Test transform with long name is handled."""
        long_name = "very_long_model_name_" + "x" * 100
        transform = TransformConfig(name=long_name)

        result = dagster_plugin.create_assets_from_transforms([transform])

        asset = result[0]
        assert asset.key.path[-1] == long_name
