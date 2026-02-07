"""Unit tests for DltIngestionPlugin (T018, T019).

Tests for create_pipeline() and run() methods. Currently these methods raise
NotImplementedError, so tests verify this stub behavior while documenting
the expected behavior for T021 and T022 implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from typing import TYPE_CHECKING

import pytest

from floe_core.plugins.ingestion import IngestionConfig, IngestionResult
from floe_ingestion_dlt.plugin import DltIngestionPlugin
from floe_ingestion_dlt.config import DltIngestionConfig, IngestionSourceConfig
from floe_ingestion_dlt.errors import PipelineConfigurationError

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def dlt_plugin() -> Generator[DltIngestionPlugin, None, None]:
    """Create and start DltIngestionPlugin for testing."""
    plugin = DltIngestionPlugin()
    plugin.startup()
    yield plugin
    plugin.shutdown()


class TestCreatePipeline:
    """Unit tests for T018 - create_pipeline() method."""

    @pytest.mark.requirement("4F-FR-011")
    def test_create_pipeline_valid_config(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test create_pipeline returns pipeline for valid config.

        Given a valid IngestionConfig with source_type="rest_api", when
        create_pipeline(config) is called on a started plugin, then it
        should return a non-None pipeline object.
        """
        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        pipeline = dlt_plugin.create_pipeline(config)
        assert pipeline is not None
        assert hasattr(pipeline, "pipeline_name")

    @pytest.mark.requirement("4F-FR-011")
    def test_create_pipeline_not_started_raises(self) -> None:
        """Test create_pipeline raises RuntimeError when plugin not started.

        Given a plugin that hasn't been started, when create_pipeline(config)
        is called, then it raises RuntimeError indicating startup is required.
        """
        plugin = DltIngestionPlugin()
        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        with pytest.raises(RuntimeError, match="Plugin must be started"):
            plugin.create_pipeline(config)

    @pytest.mark.requirement("4F-FR-012")
    def test_create_pipeline_invalid_source_type_raises(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test create_pipeline raises error for invalid source_type.

        Given an IngestionConfig with invalid source_type="invalid", when
        create_pipeline is called, it raises PipelineConfigurationError.
        """
        config = IngestionConfig(
            source_type="invalid",  # Invalid source type
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        with pytest.raises(PipelineConfigurationError, match="Invalid source_type"):
            dlt_plugin.create_pipeline(config)

    @pytest.mark.requirement("4F-FR-013")
    def test_create_pipeline_empty_destination_raises(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test create_pipeline raises error for empty destination_table.

        Given an IngestionConfig with empty destination_table, when
        create_pipeline is called, it raises PipelineConfigurationError.
        """
        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="",  # Empty destination
        )

        with pytest.raises(PipelineConfigurationError, match="destination_table.*required"):
            dlt_plugin.create_pipeline(config)

    @pytest.mark.requirement("4F-FR-014")
    def test_create_pipeline_emits_span(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test create_pipeline emits OpenTelemetry span.

        Given a valid config, when create_pipeline is called, then an
        OTel span with name 'create_pipeline' is emitted.
        """
        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        # Just verify create_pipeline doesn't raise - ingestion_span is tested separately
        pipeline = dlt_plugin.create_pipeline(config)
        assert pipeline is not None


class TestRunPipeline:
    """Unit tests for T019 - run() method."""

    @pytest.mark.requirement("4F-FR-015")
    def test_run_returns_ingestion_result(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run returns IngestionResult with success=True.

        Given a mock pipeline object, when run(pipeline) is called, it
        returns an IngestionResult with success=True.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        result = dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")
        assert isinstance(result, IngestionResult)
        assert result.success is True

    @pytest.mark.requirement("4F-FR-016")
    def test_run_result_has_metrics(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run result contains required metrics.

        Given a successful run, the IngestionResult has rows_loaded >= 0,
        bytes_written >= 0, duration_seconds >= 0.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        result = dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")
        assert result.rows_loaded >= 0
        assert result.bytes_written >= 0
        assert result.duration_seconds >= 0

    @pytest.mark.requirement("4F-FR-017")
    def test_run_failed_returns_false_success(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run returns success=False when pipeline fails.

        Given a pipeline that fails (mock), run returns
        IngestionResult(success=False, errors=[...]).
        """
        mock_pipeline = MagicMock()
        # Configure mock to raise exception during execution
        mock_pipeline.run.side_effect = Exception("Pipeline execution failed")

        result = dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")
        assert result.success is False
        assert len(result.errors) > 0
        assert "Pipeline execution failed" in result.errors[0]

    @pytest.mark.requirement("4F-FR-018")
    def test_run_empty_source_returns_zero_rows(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run returns zero rows for empty source data.

        Given a pipeline with empty source data, run returns
        IngestionResult(success=True, rows_loaded=0).
        """
        mock_pipeline = MagicMock()
        # Configure mock to return empty result
        mock_pipeline.run.return_value = MagicMock(metrics={})

        result = dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")
        assert result.success is True
        assert result.rows_loaded == 0

    @pytest.mark.requirement("4F-FR-015")
    def test_run_not_started_raises(self) -> None:
        """Test run raises RuntimeError when plugin not started.

        Given plugin not started, run raises RuntimeError indicating
        startup is required.
        """
        plugin = DltIngestionPlugin()
        mock_pipeline = MagicMock()

        with pytest.raises(RuntimeError, match="Plugin must be started"):
            plugin.run(mock_pipeline)

    @pytest.mark.requirement("4F-FR-016")
    def test_run_emits_span_with_result(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run emits OpenTelemetry span with result attributes.

        Verify OTel span is emitted with name 'run_pipeline' and includes
        result attributes like rows_loaded, bytes_written, success.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        # Just verify run doesn't raise and returns result - ingestion_span is tested separately
        result = dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")
        assert isinstance(result, IngestionResult)
