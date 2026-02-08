"""Unit tests for DltIngestionPlugin (T018, T019).

Tests for create_pipeline() and run() methods. Currently these methods raise
NotImplementedError, so tests verify this stub behavior while documenting
the expected behavior for T021 and T022 implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from floe_core.plugins.ingestion import IngestionConfig, IngestionResult

from floe_ingestion_dlt.errors import PipelineConfigurationError
from floe_ingestion_dlt.plugin import DltIngestionPlugin

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
    def test_create_pipeline_invalid_source_type_raises(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
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
    def test_create_pipeline_empty_destination_raises(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test create_pipeline raises error for empty destination_table.

        Given an IngestionConfig with empty destination_table, when
        create_pipeline is called, it raises PipelineConfigurationError.
        """
        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="",  # Empty destination
        )

        with pytest.raises(
            PipelineConfigurationError, match="destination_table.*required"
        ):
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
    def test_run_failed_returns_false_success(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
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
    def test_run_empty_source_returns_zero_rows(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
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

    @pytest.mark.requirement("4F-FR-022")
    def test_run_append_write_disposition(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run passes write_disposition='append' to pipeline.run().

        Given write_disposition="append" kwarg, when run() is called,
        then pipeline.run() is invoked with write_disposition="append".
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")

        # Verify pipeline.run was called with correct write_disposition
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert call_kwargs["write_disposition"] == "append"

    @pytest.mark.requirement("4F-FR-023")
    def test_run_replace_write_disposition(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run passes write_disposition='replace' to pipeline.run().

        Given write_disposition="replace" kwarg, when run() is called,
        then pipeline.run() is invoked with write_disposition="replace".
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(mock_pipeline, source=[], write_disposition="replace")

        # Verify pipeline.run was called with correct write_disposition
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert call_kwargs["write_disposition"] == "replace"

    @pytest.mark.requirement("4F-FR-024")
    def test_run_merge_write_disposition(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run passes write_disposition='merge' to pipeline.run().

        Given write_disposition="merge" kwarg, when run() is called,
        then pipeline.run() is invoked with write_disposition="merge".
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(mock_pipeline, source=[], write_disposition="merge")

        # Verify pipeline.run was called with correct write_disposition
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert call_kwargs["write_disposition"] == "merge"

    @pytest.mark.requirement("4F-FR-024")
    def test_run_merge_with_table_name(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run passes table_name kwarg to pipeline.run().

        Given table_name kwarg with write_disposition="merge", when run()
        is called, then both parameters are passed to pipeline.run().
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="merge",
            table_name="bronze.raw_data",
        )

        # Verify pipeline.run was called with both kwargs
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert call_kwargs["write_disposition"] == "merge"
        assert call_kwargs["table_name"] == "bronze.raw_data"

    @pytest.mark.requirement("4F-FR-031")
    def test_run_passes_schema_contract_evolve(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run passes schema_contract dict to pipeline.run() for evolve.

        Given schema_contract="evolve" kwarg, when run() is called, then
        pipeline.run() is invoked with schema_contract dict with all fields
        set to "evolve".
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
            schema_contract="evolve",
        )

        # Verify pipeline.run was called with schema_contract dict
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert "schema_contract" in call_kwargs
        assert call_kwargs["schema_contract"] == {
            "columns": "evolve",
            "tables": "evolve",
            "data_type": "evolve",
        }

    @pytest.mark.requirement("4F-FR-032")
    def test_run_passes_schema_contract_freeze(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run passes schema_contract dict to pipeline.run() for freeze.

        Given schema_contract="freeze" kwarg, when run() is called, then
        pipeline.run() is invoked with schema_contract dict with all fields
        set to "freeze".
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
            schema_contract="freeze",
        )

        # Verify pipeline.run was called with schema_contract dict
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert "schema_contract" in call_kwargs
        assert call_kwargs["schema_contract"] == {
            "columns": "freeze",
            "tables": "freeze",
            "data_type": "freeze",
        }

    @pytest.mark.requirement("4F-FR-033")
    def test_run_passes_schema_contract_discard_value(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run passes schema_contract dict to pipeline.run() for discard_value.

        Given schema_contract="discard_value" kwarg, when run() is called, then
        pipeline.run() is invoked with schema_contract dict with columns and
        data_type set to "discard_value", tables set to "evolve".
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
            schema_contract="discard_value",
        )

        # Verify pipeline.run was called with schema_contract dict
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert "schema_contract" in call_kwargs
        assert call_kwargs["schema_contract"] == {
            "columns": "discard_value",
            "tables": "evolve",
            "data_type": "discard_value",
        }

    @pytest.mark.requirement("4F-FR-035")
    def test_run_schema_contract_violation_raises(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run returns failure with SchemaContractViolation info.

        Given pipeline.run() raises an exception with "schema" and "contract"
        in message, when run() is called, then it returns
        IngestionResult(success=False) with SchemaContractViolation info in errors.
        """
        mock_pipeline = MagicMock()
        # Configure mock to raise schema contract violation
        mock_pipeline.run.side_effect = Exception(
            "Schema contract violation: column 'new_field' not allowed"
        )

        result = dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
            schema_contract="freeze",
        )

        # Verify result indicates failure with schema contract violation
        assert result.success is False
        assert len(result.errors) > 0
        assert "schema contract violation" in result.errors[0].lower()

    @pytest.mark.requirement("4F-FR-034")
    def test_run_default_schema_contract_is_evolve(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run uses 'evolve' as default when no schema_contract kwarg passed.

        Given no schema_contract kwarg, when run() is called, then
        pipeline.run() is invoked with schema_contract dict set to "evolve" mode.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        # Call run() without schema_contract kwarg
        dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
        )

        # Verify pipeline.run was called with default evolve schema_contract
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert "schema_contract" in call_kwargs
        assert call_kwargs["schema_contract"] == {
            "columns": "evolve",
            "tables": "evolve",
            "data_type": "evolve",
        }


class TestGetDestinationConfig:
    """Unit tests for T024 - get_destination_config() method."""

    @pytest.mark.requirement("4F-FR-019")
    def test_get_destination_config_basic(self) -> None:
        """Test get_destination_config() with basic catalog configuration.

        Given catalog_config with uri and warehouse, when get_destination_config()
        is called, then it returns dict with destination="iceberg",
        catalog_type="rest", catalog_uri, and warehouse.
        """
        plugin = DltIngestionPlugin()
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
        }

        result = plugin.get_destination_config(catalog_config)

        assert result["destination"] == "iceberg"
        assert result["catalog_type"] == "rest"
        assert result["catalog_uri"] == "http://polaris:8181/api/catalog"
        assert result["warehouse"] == "floe_warehouse"

    @pytest.mark.requirement("4F-FR-020")
    def test_get_destination_config_s3_config(self) -> None:
        """Test get_destination_config() with S3/MinIO configuration.

        Given catalog_config with s3_endpoint, s3_access_key, s3_secret_key,
        s3_region, when get_destination_config() is called, then all S3
        parameters are mapped to output dict.
        """
        plugin = DltIngestionPlugin()
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
            "s3_endpoint": "http://minio:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",  # pragma: allowlist secret
            "s3_region": "us-east-1",
        }

        result = plugin.get_destination_config(catalog_config)

        assert result["destination"] == "iceberg"
        assert result["catalog_type"] == "rest"
        assert result["s3_endpoint"] == "http://minio:9000"
        assert result["s3_access_key"] == "minioadmin"
        assert result["s3_secret_key"] == "minioadmin"  # pragma: allowlist secret
        assert result["s3_region"] == "us-east-1"

    @pytest.mark.requirement("4F-FR-019")
    def test_get_destination_config_minimal(self) -> None:
        """Test get_destination_config() with empty catalog_config.

        Given empty catalog_config {}, when get_destination_config() is called,
        then it returns dict with just destination and catalog_type (base fields).
        """
        plugin = DltIngestionPlugin()
        catalog_config: dict[str, str] = {}

        result = plugin.get_destination_config(catalog_config)

        assert result["destination"] == "iceberg"
        assert result["catalog_type"] == "rest"
        assert "catalog_uri" not in result
        assert "warehouse" not in result
        assert "s3_endpoint" not in result

    @pytest.mark.requirement("4F-FR-020")
    def test_get_destination_config_partial_s3(self) -> None:
        """Test get_destination_config() with partial S3 configuration.

        Given catalog_config with only s3_endpoint (no keys/region), when
        get_destination_config() is called, then only s3_endpoint appears
        in output dict (no empty/null S3 fields).
        """
        plugin = DltIngestionPlugin()
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
            "s3_endpoint": "http://minio:9000",
        }

        result = plugin.get_destination_config(catalog_config)

        assert result["destination"] == "iceberg"
        assert result["catalog_type"] == "rest"
        assert result["s3_endpoint"] == "http://minio:9000"
        # Verify keys/region are not present
        assert "s3_access_key" not in result
        assert "s3_secret_key" not in result
        assert "s3_region" not in result

    @pytest.mark.requirement("4F-FR-019")
    def test_get_destination_config_not_started_ok(self) -> None:
        """Test get_destination_config() does not require plugin to be started.

        get_destination_config is a pure mapping function that doesn't
        depend on plugin state. It should work without calling startup().
        """
        plugin = DltIngestionPlugin()  # NOT started
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
        }

        # Should not raise RuntimeError
        result = plugin.get_destination_config(catalog_config)

        assert result["destination"] == "iceberg"
        assert result["catalog_type"] == "rest"


class TestIncrementalLoading:
    """Unit tests for incremental loading support (T045)."""

    @pytest.mark.requirement("4F-FR-038")
    def test_run_with_cursor_field_logs_incremental(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() accepts cursor_field kwarg and logs incremental mode.

        Given cursor_field kwarg is passed, when run() is called, then it
        accepts the parameter without error and returns IngestionResult.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        result = dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
            cursor_field="updated_at",
        )

        # Verify result is successful
        assert isinstance(result, IngestionResult)
        assert result.success is True

    @pytest.mark.requirement("4F-FR-042")
    def test_run_with_primary_key_passes_to_pipeline(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() passes primary_key kwarg to pipeline.run() with merge.

        Given primary_key and write_disposition="merge" kwargs, when run()
        is called, then primary_key is passed to pipeline.run().
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="merge",
            primary_key="id",
        )

        # Verify pipeline.run was called with primary_key
        mock_pipeline.run.assert_called_once()
        call_kwargs = mock_pipeline.run.call_args.kwargs
        assert call_kwargs["write_disposition"] == "merge"
        assert call_kwargs["primary_key"] == "id"

    @pytest.mark.requirement("4F-FR-040")
    def test_run_without_cursor_field_default_none(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() proceeds normally when no cursor_field kwarg provided.

        Given no cursor_field kwarg (non-incremental mode), when run() is
        called, then it proceeds normally and returns IngestionResult.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        result = dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
        )

        # Verify result is successful (non-incremental mode works)
        assert isinstance(result, IngestionResult)
        assert result.success is True

    @pytest.mark.requirement("4F-FR-043")
    def test_run_rows_loaded_from_metrics(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test rows_loaded in IngestionResult comes from pipeline metrics.

        Given pipeline.run() returns metrics, when run() is called, then
        IngestionResult.rows_loaded reflects the metrics extraction logic.
        """
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        result = dlt_plugin.run(
            mock_pipeline,
            source=[],
            write_disposition="append",
        )

        # Verify rows_loaded is derived from metrics (0 for empty metrics)
        assert isinstance(result, IngestionResult)
        assert result.rows_loaded == 0


class TestOTelSpanEmission:
    """Unit tests for T046 - OTel span emission verification."""

    @pytest.mark.requirement("4F-FR-044")
    def test_create_pipeline_emits_otel_span(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test create_pipeline() emits OTel span via tracer.

        Given a valid config, when create_pipeline() is called, then
        get_tracer() is called and tracer.start_as_current_span is invoked
        with span name containing "create_pipeline".
        """
        from unittest.mock import patch

        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        with patch("floe_ingestion_dlt.plugin.get_tracer") as mock_get_tracer:
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            # Call create_pipeline
            dlt_plugin.create_pipeline(config)

            # Verify get_tracer was called
            mock_get_tracer.assert_called_once()

            # Verify tracer.start_as_current_span was called with correct name
            mock_tracer.start_as_current_span.assert_called()
            call_args = mock_tracer.start_as_current_span.call_args
            span_name = call_args[0][0]
            assert "create_pipeline" in span_name

    @pytest.mark.requirement("4F-FR-044")
    def test_run_emits_otel_span(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run() emits OTel span via tracer.

        Given a mock pipeline, when run() is called, then get_tracer() is
        called and tracer.start_as_current_span is invoked with span name
        containing "run".
        """
        from unittest.mock import patch

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        with patch("floe_ingestion_dlt.plugin.get_tracer") as mock_get_tracer:
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            # Call run
            dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")

            # Verify get_tracer was called
            mock_get_tracer.assert_called()

            # Verify tracer.start_as_current_span was called with correct name
            mock_tracer.start_as_current_span.assert_called()
            call_args = mock_tracer.start_as_current_span.call_args
            span_name = call_args[0][0]
            assert "run" in span_name

    @pytest.mark.requirement("4F-FR-046")
    def test_run_span_records_result_attributes(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() calls record_ingestion_result with span and result.

        Given a successful pipeline run, when run() completes, then
        record_ingestion_result() is called with the span and result.
        """
        from unittest.mock import patch

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = MagicMock(metrics={})

        with patch("floe_ingestion_dlt.plugin.record_ingestion_result") as mock_record:
            result = dlt_plugin.run(
                mock_pipeline, source=[], write_disposition="append"
            )

            # Verify record_ingestion_result was called with span and result
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            # First arg is span, second arg is result
            recorded_result = call_args[0][1]
            assert recorded_result == result

    @pytest.mark.requirement("4F-FR-047")
    def test_run_span_records_error_on_failure(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() calls record_ingestion_error when pipeline fails.

        Given pipeline.run() raises exception, when run() handles error,
        then record_ingestion_error() is called with span and exception.
        """
        from unittest.mock import patch

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = Exception("Pipeline execution failed")

        with patch("floe_ingestion_dlt.plugin.record_ingestion_error") as mock_record:
            # Call run (doesn't raise, returns failed result)
            result = dlt_plugin.run(
                mock_pipeline, source=[], write_disposition="append"
            )

            # Verify record_ingestion_error was called
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            # First arg is span, second arg is exception
            recorded_error = call_args[0][1]
            assert isinstance(recorded_error, Exception)
            assert str(recorded_error) == "Pipeline execution failed"

            # Verify result indicates failure
            assert result.success is False

    @pytest.mark.requirement("4F-FR-044")
    def test_startup_emits_otel_span(self) -> None:
        """Test startup() emits OTel span via tracer.

        Given a plugin that hasn't been started, when startup() is called,
        then get_tracer() is called and tracer.start_as_current_span is
        invoked with span name containing "startup".
        """
        from unittest.mock import patch

        plugin = DltIngestionPlugin()

        with patch("floe_ingestion_dlt.plugin.get_tracer") as mock_get_tracer:
            mock_tracer = MagicMock()
            mock_get_tracer.return_value = mock_tracer

            # Call startup
            plugin.startup()

            # Verify get_tracer was called
            mock_get_tracer.assert_called_once()

            # Verify tracer.start_as_current_span was called with correct name
            mock_tracer.start_as_current_span.assert_called()
            call_args = mock_tracer.start_as_current_span.call_args
            span_name = call_args[0][0]
            assert "startup" in span_name


class TestStructuredLogging:
    """Unit tests for T047 - structured logging verification."""

    @pytest.mark.requirement("4F-FR-048")
    def test_create_pipeline_logs_pipeline_created(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test create_pipeline() logs 'pipeline_created' event.

        Given a valid config, when create_pipeline() is called, then
        logger.info is called with event="pipeline_created" and includes
        pipeline_name, source_type, destination_table.
        """
        from unittest.mock import patch

        config = IngestionConfig(
            source_type="rest_api",
            source_config={"url": "https://api.example.com"},
            destination_table="bronze.raw_data",
        )

        with patch("floe_ingestion_dlt.plugin.logger") as mock_logger:
            dlt_plugin.create_pipeline(config)

            # Verify logger.info was called with pipeline_created
            mock_logger.info.assert_called()
            # Find the pipeline_created call
            found = False
            for call in mock_logger.info.call_args_list:
                if call[0][0] == "pipeline_created":
                    found = True
                    kwargs = call[1]
                    assert "source_type" in kwargs
                    assert "destination_table" in kwargs
                    assert kwargs["source_type"] == "rest_api"
                    assert kwargs["destination_table"] == "bronze.raw_data"
            assert found, "pipeline_created event not logged"

    @pytest.mark.requirement("4F-FR-048")
    def test_run_logs_pipeline_run_starting(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() logs 'pipeline_run_starting' event.

        Given a mock pipeline, when run() is called, then logger.info is
        called with event="pipeline_run_starting".
        """
        from unittest.mock import patch

        mock_pipeline = MagicMock()
        mock_pipeline.pipeline_name = "test_pipeline"
        mock_pipeline.run.return_value = MagicMock(metrics={})

        with patch("floe_ingestion_dlt.plugin.logger") as mock_logger:
            dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")

            # Verify logger.info was called with pipeline_run_starting
            mock_logger.info.assert_called()
            # Find the pipeline_run_starting call
            found = False
            for call in mock_logger.info.call_args_list:
                if call[0][0] == "pipeline_run_starting":
                    found = True
            assert found, "pipeline_run_starting event not logged"

    @pytest.mark.requirement("4F-FR-048")
    def test_run_logs_pipeline_run_completed(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test run() logs 'pipeline_run_completed' event on success.

        Given a successful pipeline run, when run() completes, then
        logger.info is called with event="pipeline_run_completed" and
        includes rows_loaded and duration_seconds.
        """
        from unittest.mock import patch

        mock_pipeline = MagicMock()
        mock_pipeline.pipeline_name = "test_pipeline"
        mock_pipeline.run.return_value = MagicMock(metrics={})

        with patch("floe_ingestion_dlt.plugin.logger") as mock_logger:
            dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")

            # Verify logger.info was called with pipeline_run_completed
            mock_logger.info.assert_called()
            # Find the pipeline_run_completed call
            found = False
            for call in mock_logger.info.call_args_list:
                if call[0][0] == "pipeline_run_completed":
                    found = True
                    kwargs = call[1]
                    assert "rows_loaded" in kwargs
                    assert "duration_seconds" in kwargs
            assert found, "pipeline_run_completed event not logged"

    @pytest.mark.requirement("4F-FR-048")
    def test_run_logs_pipeline_run_failed(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test run() logs 'pipeline_run_failed' event on failure.

        Given pipeline.run() raises exception, when run() handles error,
        then logger.error is called with event="pipeline_run_failed".
        """
        from unittest.mock import patch

        mock_pipeline = MagicMock()
        mock_pipeline.pipeline_name = "test_pipeline"
        mock_pipeline.run.side_effect = Exception("Pipeline execution failed")

        with patch("floe_ingestion_dlt.plugin.logger") as mock_logger:
            # Call run (doesn't raise, returns failed result)
            dlt_plugin.run(mock_pipeline, source=[], write_disposition="append")

            # Verify logger.error was called with pipeline_run_failed
            mock_logger.error.assert_called()
            # Find the pipeline_run_failed call
            found = False
            for call in mock_logger.error.call_args_list:
                if call[0][0] == "pipeline_run_failed":
                    found = True
            assert found, "pipeline_run_failed event not logged"

    @pytest.mark.requirement("4F-FR-048")
    def test_get_destination_config_logs_config_generated(self) -> None:
        """Test get_destination_config() logs 'destination_config_generated' event.

        Given catalog_config dict, when get_destination_config() is called,
        then logger.info is called with event="destination_config_generated".
        """
        from unittest.mock import patch

        plugin = DltIngestionPlugin()
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
        }

        with patch("floe_ingestion_dlt.plugin.logger") as mock_logger:
            plugin.get_destination_config(catalog_config)

            # Verify logger.info was called with destination_config_generated
            mock_logger.info.assert_called()
            # Find the destination_config_generated call
            found = False
            for call in mock_logger.info.call_args_list:
                if call[0][0] == "destination_config_generated":
                    found = True
            assert found, "destination_config_generated event not logged"

    @pytest.mark.requirement("4F-FR-049")
    def test_secrets_not_logged(self) -> None:
        """Test get_destination_config() does not log secret values.

        Given catalog_config with s3_secret_key and s3_access_key, when
        get_destination_config() is called, then logger.info calls do NOT
        include the actual secret values in any arguments.
        """
        from unittest.mock import patch

        plugin = DltIngestionPlugin()
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
            "s3_endpoint": "http://minio:9000",
            "s3_access_key": "sensitive-access-key-12345",
            "s3_secret_key": "super-secret-key-67890",  # pragma: allowlist secret
        }

        with patch("floe_ingestion_dlt.plugin.logger") as mock_logger:
            plugin.get_destination_config(catalog_config)

            # Verify secrets are NOT in any logger call
            for call in mock_logger.info.call_args_list:
                call_str = str(call)
                assert (
                    "sensitive-access-key-12345" not in call_str
                ), "s3_access_key value leaked in logs"
                assert (
                    "super-secret-key-67890" not in call_str
                ), "s3_secret_key value leaked in logs"
