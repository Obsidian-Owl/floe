"""Unit tests for FloeIngestionTranslator (T031).

The FloeIngestionTranslator customizes dagster-dlt's DagsterDltTranslator
to use floe naming conventions for ingestion assets.

Requirements:
    T031: Unit tests for FloeIngestionTranslator
    FR-061: Asset naming convention ingestion__{source}__{resource}
    FR-064: Asset metadata includes source_type and destination_table
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from dagster import AssetKey, build_op_context
from floe_core.plugins.ingestion import IngestionResult


class TestFloeIngestionTranslator:
    """Tests for FloeIngestionTranslator asset key naming and metadata."""

    @pytest.mark.requirement("4F-FR-061")
    def test_translator_naming_convention(self) -> None:
        """Test translator produces ingestion__{source}__{resource} naming.

        Given a dlt resource with source_name and resource_name, the
        translator should produce asset key: ingestion__{source}__{resource}.
        """
        from floe_orchestrator_dagster.assets.ingestion import FloeIngestionTranslator

        translator = FloeIngestionTranslator()

        mock_resource: MagicMock = MagicMock()
        mock_resource.source_name = "github"
        mock_resource.name = "issues"

        asset_key = translator.get_asset_key(mock_resource)
        assert asset_key == AssetKey("ingestion__github__issues")

    @pytest.mark.requirement("4F-FR-061")
    def test_translator_naming_different_sources(self) -> None:
        """Test translator naming works across different source/resource combos.

        Verifies the naming pattern holds for various source and resource
        name combinations.
        """
        from floe_orchestrator_dagster.assets.ingestion import FloeIngestionTranslator

        translator = FloeIngestionTranslator()

        test_cases = [
            ("postgres_db", "users", "ingestion__postgres_db__users"),
            ("rest_api", "orders", "ingestion__rest_api__orders"),
            ("s3_files", "invoices", "ingestion__s3_files__invoices"),
        ]

        for source_name, resource_name, expected_key in test_cases:
            mock_resource: MagicMock = MagicMock()
            mock_resource.source_name = source_name
            mock_resource.name = resource_name

            asset_key = translator.get_asset_key(mock_resource)
            assert asset_key == AssetKey(expected_key), f"Expected {expected_key}, got {asset_key}"

    @pytest.mark.requirement("4F-FR-064")
    def test_translator_includes_metadata(self) -> None:
        """Test translator includes source_type and destination_table metadata.

        Given a dlt resource, the translator should include metadata
        with source_type and destination_table attributes.
        """
        from floe_orchestrator_dagster.assets.ingestion import FloeIngestionTranslator

        translator = FloeIngestionTranslator(
            source_type="rest_api",
            destination_table="raw.github_issues",
        )

        mock_resource: MagicMock = MagicMock()
        mock_resource.source_name = "github"
        mock_resource.name = "issues"

        metadata = translator.get_metadata(mock_resource)
        assert metadata["source_type"] == "rest_api"
        assert metadata["destination_table"] == "raw.github_issues"

    @pytest.mark.requirement("4F-FR-064")
    def test_translator_metadata_empty_when_not_set(self) -> None:
        """Test translator returns empty metadata when source_type/destination not set.

        When no source_type or destination_table is provided to the translator,
        metadata should not contain these keys.
        """
        from floe_orchestrator_dagster.assets.ingestion import FloeIngestionTranslator

        translator = FloeIngestionTranslator()

        mock_resource: MagicMock = MagicMock()
        mock_resource.source_name = "github"
        mock_resource.name = "issues"

        metadata = translator.get_metadata(mock_resource)
        assert "source_type" not in metadata
        assert "destination_table" not in metadata


class TestCreateIngestionAssets:
    """Tests for create_ingestion_assets() factory."""

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_returns_asset_definitions(self) -> None:
        """Test factory returns a list of asset definitions.

        Given a valid PluginRef, the factory should return a non-empty
        list of Dagster AssetsDefinition objects.
        """
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {}

        assets = create_ingestion_assets(mock_ref)
        assert len(assets) == 1

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_has_ingestion_metadata(self) -> None:
        """Test factory asset includes ingestion type and version in metadata.

        The created asset should carry metadata identifying the ingestion
        plugin type and version.
        """
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {}

        assets = create_ingestion_assets(mock_ref)
        asset_def = assets[0]

        # Check the asset's metadata
        specs = list(asset_def.specs)
        assert len(specs) == 1
        metadata = specs[0].metadata
        assert metadata["ingestion_type"] == "dlt"
        assert metadata["ingestion_version"] == "0.1.0"

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_requires_ingestion_resource(self) -> None:
        """Test factory asset declares dependency on ingestion resource.

        The created asset should require the 'ingestion' resource key,
        ensuring the ingestion plugin is available at runtime.
        """
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {}

        assets = create_ingestion_assets(mock_ref)
        asset_def = assets[0]

        assert "ingestion" in asset_def.required_resource_keys

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_runs_ingestion_pipeline(self) -> None:
        """Materializing the asset must create and run the ingestion pipeline."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "source_type": "rest_api",
            "source_config": {"url": "https://example.test/api"},
            "destination_table": "raw.example",
            "write_mode": "replace",
            "schema_contract": "freeze",
        }
        ingestion_plugin = MagicMock()
        ingestion_plugin.name = "dlt"
        ingestion_plugin.version = "0.1.0"
        pipeline = object()
        result = IngestionResult(success=True, rows_loaded=12, duration_seconds=1.5)
        ingestion_plugin.create_pipeline.return_value = pipeline
        ingestion_plugin.run.return_value = result

        asset_def = create_ingestion_assets(mock_ref)[0]
        context = build_op_context(resources={"ingestion": ingestion_plugin})

        output = asset_def(context)

        ingestion_plugin.create_pipeline.assert_called_once()
        config = ingestion_plugin.create_pipeline.call_args.args[0]
        assert config.source_type == "rest_api"
        assert config.source_config == {"url": "https://example.test/api"}
        assert config.destination_table == "raw.example"
        assert config.write_mode == "replace"
        assert config.schema_contract == "freeze"
        ingestion_plugin.run.assert_called_once_with(pipeline)
        assert output is result

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_raises_when_ingestion_run_fails(self) -> None:
        """Failed ingestion results must fail the Dagster asset loudly."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "source_type": "rest_api",
            "destination_table": "raw.example",
        }
        ingestion_plugin = MagicMock()
        ingestion_plugin.name = "dlt"
        ingestion_plugin.version = "0.1.0"
        pipeline = object()
        ingestion_plugin.create_pipeline.return_value = pipeline
        ingestion_plugin.run.return_value = IngestionResult(
            success=False,
            errors=["source auth failed"],
        )

        asset_def = create_ingestion_assets(mock_ref)[0]
        context = build_op_context(resources={"ingestion": ingestion_plugin})

        with pytest.raises(RuntimeError, match="source auth failed"):
            asset_def(context)

        ingestion_plugin.create_pipeline.assert_called_once()
        ingestion_plugin.run.assert_called_once_with(pipeline)
