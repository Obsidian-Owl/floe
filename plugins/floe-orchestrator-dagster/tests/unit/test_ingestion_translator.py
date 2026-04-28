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


class SourceLike:
    """Small dlt-like source test double."""

    resources = ()


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

    def _executable_source_ref(self) -> MagicMock:
        """Build a PluginRef-like object with one executable source object."""
        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "github-events",
                    "source_type": "rest_api",
                    "source_config": {"source": SourceLike()},
                    "destination_table": "bronze.github_events",
                }
            ],
        }
        return mock_ref

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_returns_asset_definitions(self) -> None:
        """Test factory returns a list of asset definitions.

        Given a valid PluginRef, the factory should return a non-empty
        list of Dagster AssetsDefinition objects.
        """
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref = self._executable_source_ref()

        assets = create_ingestion_assets(mock_ref)
        assert len(assets) == 1

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_has_ingestion_metadata(self) -> None:
        """Test factory asset includes ingestion type and version in metadata.

        The created asset should carry metadata identifying the ingestion
        plugin type and version.
        """
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref = self._executable_source_ref()

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

        mock_ref = self._executable_source_ref()

        assets = create_ingestion_assets(mock_ref)
        asset_def = assets[0]

        assert "ingestion" in asset_def.required_resource_keys

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_creates_one_asset_per_configured_source(self) -> None:
        """Executable source configs get one asset per source."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        github_source = SourceLike()
        users_source = SourceLike()
        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "github-events",
                    "source_type": "rest_api",
                    "source_config": {"source": github_source},
                    "destination_table": "bronze.github_events",
                },
                {
                    "name": "warehouse_users",
                    "source_type": "sql_database",
                    "source_config": {"source": users_source},
                    "destination_table": "bronze.users",
                },
            ],
        }

        assets = create_ingestion_assets(mock_ref)

        assert len(assets) == 2
        assert {asset_def.key.path[-1] for asset_def in assets} == {
            "run_ingestion_github_events",
            "run_ingestion_warehouse_users",
        }

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_rejects_normal_json_sources_without_executable_source(self) -> None:
        """Normal compiled JSON config cannot create runnable dlt source objects yet."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "github-events",
                    "source_type": "rest_api",
                    "source_config": {"url": "https://example.test/events"},
                    "destination_table": "bronze.github_events",
                }
            ],
        }

        with pytest.raises(ValueError, match="executable dlt source object"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_rejects_empty_sources_list(self) -> None:
        """Configured ingestion must contain at least one source."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {"sources": []}

        with pytest.raises(ValueError, match="at least one ingestion source"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_rejects_empty_config(self) -> None:
        """Empty config must not synthesize a fake flat ingestion source."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {}

        with pytest.raises(ValueError, match="requires sources or explicit executable source"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_rejects_normalized_source_name_collisions(self) -> None:
        """Source names that normalize to the same asset key must fail loudly."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "github-events",
                    "source_type": "rest_api",
                    "source_config": {"source": SourceLike()},
                    "destination_table": "bronze.github_events",
                },
                {
                    "name": "github_events",
                    "source_type": "rest_api",
                    "source_config": {"source": SourceLike()},
                    "destination_table": "bronze.github_events_copy",
                },
            ],
        }

        with pytest.raises(ValueError, match="normalized ingestion asset name collision"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_runs_ingestion_pipeline(self) -> None:
        """Materializing the asset must create and run the ingestion pipeline."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        executable_source = SourceLike()
        mock_ref.config = {
            "source_type": "rest_api",
            "source_config": {
                "url": "https://example.test/api",
                "source": executable_source,
            },
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
        assert config.source_config == {
            "url": "https://example.test/api",
            "source": executable_source,
        }
        assert config.destination_table == "raw.example"
        assert config.write_mode == "replace"
        assert config.schema_contract == "freeze"
        ingestion_plugin.run.assert_called_once_with(
            pipeline,
            write_disposition="replace",
            table_name="example",
            schema_contract="freeze",
            cursor_field=None,
            primary_key=None,
            source=executable_source,
        )
        assert output is result

    @pytest.mark.requirement("4F-FR-060")
    def test_source_asset_runs_pipeline_with_source_specific_kwargs(self) -> None:
        """Per-source assets pass write/table/schema/cursor/primary kwargs to plugins."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        executable_source = SourceLike()
        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "orders-api",
                    "source_type": "rest_api",
                    "source_config": {
                        "url": "https://example.test/orders",
                        "source": executable_source,
                    },
                    "destination_table": "bronze.orders",
                    "write_mode": "merge",
                    "schema_contract": "freeze",
                    "cursor_field": "updated_at",
                    "primary_key": ["id"],
                }
            ],
        }
        ingestion_plugin = MagicMock()
        ingestion_plugin.name = "dlt"
        ingestion_plugin.version = "0.1.0"
        pipeline = object()
        result = IngestionResult(success=True, rows_loaded=5)
        ingestion_plugin.create_pipeline.return_value = pipeline
        ingestion_plugin.run.return_value = result

        asset_def = create_ingestion_assets(mock_ref)[0]
        context = build_op_context(resources={"ingestion": ingestion_plugin})

        output = asset_def(context)

        config = ingestion_plugin.create_pipeline.call_args.args[0]
        assert config.source_type == "rest_api"
        assert config.source_config == {
            "url": "https://example.test/orders",
            "source": executable_source,
        }
        assert config.destination_table == "bronze.orders"
        assert config.write_mode == "merge"
        assert config.schema_contract == "freeze"
        ingestion_plugin.run.assert_called_once_with(
            pipeline,
            write_disposition="merge",
            table_name="orders",
            schema_contract="freeze",
            cursor_field="updated_at",
            primary_key=["id"],
            source=executable_source,
        )
        assert output is result

    @pytest.mark.requirement("4F-FR-060")
    def test_source_asset_rejects_missing_dlt_source_object(self) -> None:
        """The helper fails loudly instead of inventing a dlt source object."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "users",
                    "source_type": "rest_api",
                    "source_config": {"url": "https://example.test/users"},
                    "destination_table": "bronze.users",
                }
            ],
        }
        with pytest.raises(ValueError, match="source_config.source"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_source_asset_rejects_plain_object_source(self) -> None:
        """Plain object() is not enough to prove executable dlt source semantics."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "users",
                    "source_type": "rest_api",
                    "source_config": {"source": object()},
                    "destination_table": "bronze.users",
                }
            ],
        }
        with pytest.raises(ValueError, match="source_config.source"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_source_asset_rejects_missing_source_type(self) -> None:
        """Source configs must declare source_type before assets are returned."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "users",
                    "source_config": {"source": SourceLike()},
                    "destination_table": "bronze.users",
                }
            ],
        }
        with pytest.raises(ValueError, match="source_type"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_source_asset_rejects_missing_destination_table(self) -> None:
        """Source configs must declare destination_table before assets are returned."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        mock_ref.config = {
            "sources": [
                {
                    "name": "users",
                    "source_type": "rest_api",
                    "source_config": {"source": SourceLike()},
                }
            ],
        }
        with pytest.raises(ValueError, match="destination_table"):
            create_ingestion_assets(mock_ref)

    @pytest.mark.requirement("4F-FR-060")
    def test_factory_asset_raises_when_ingestion_run_fails(self) -> None:
        """Failed ingestion results must fail the Dagster asset loudly."""
        from floe_orchestrator_dagster.assets.ingestion import create_ingestion_assets

        mock_ref: MagicMock = MagicMock()
        mock_ref.type = "dlt"
        mock_ref.version = "0.1.0"
        executable_source = SourceLike()
        mock_ref.config = {
            "source_type": "rest_api",
            "source_config": {"source": executable_source},
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
        ingestion_plugin.run.assert_called_once_with(
            pipeline,
            write_disposition="append",
            table_name="example",
            schema_contract="evolve",
            cursor_field=None,
            primary_key=None,
            source=executable_source,
        )
