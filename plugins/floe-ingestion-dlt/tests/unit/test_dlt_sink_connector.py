"""Unit tests for DltIngestionPlugin SinkConnector mixin implementation.

Epic 4G: Reverse ETL Sink Plugin
Tests the SinkConnector interface implementation on DltIngestionPlugin,
which enables writing data from Iceberg Gold layer to external destinations.

These tests follow TDD - they will FAIL until the SinkConnector methods
are implemented on DltIngestionPlugin.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from floe_core.plugins.ingestion import IngestionPlugin
from floe_core.plugins.sink import SinkConnector, SinkConfig, EgressResult
from floe_ingestion_dlt.plugin import DltIngestionPlugin
from floe_ingestion_dlt.errors import SinkConfigurationError

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def dlt_plugin() -> Generator[DltIngestionPlugin, None, None]:
    """Create started DltIngestionPlugin instance for testing.

    Mocks the dlt import during startup since dlt is a runtime
    dependency not available in the unit test environment.

    Yields:
        Started DltIngestionPlugin instance

    Cleanup:
        Shuts down plugin after test
    """
    mock_dlt = MagicMock()
    mock_dlt.__version__ = "1.20.0"
    with patch.dict("sys.modules", {"dlt": mock_dlt}):
        plugin = DltIngestionPlugin()
        plugin.startup()
        yield plugin
        plugin.shutdown()


class TestDltSinkConnector:
    """Tests for DltIngestionPlugin SinkConnector interface implementation."""

    @pytest.mark.requirement("4G-FR-005")
    def test_isinstance_sink_connector(self, dlt_plugin: DltIngestionPlugin) -> None:
        """Test DltIngestionPlugin implements both SinkConnector and IngestionPlugin.

        Validates that the plugin correctly implements the dual interface
        pattern required for reverse ETL functionality.
        """
        assert isinstance(dlt_plugin, SinkConnector)
        assert isinstance(dlt_plugin, IngestionPlugin)

    @pytest.mark.requirement("4G-FR-006")
    def test_list_available_sinks_returns_list(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test list_available_sinks returns list containing expected sink types.

        Validates that the plugin exposes rest_api and sql_database sinks
        as specified in the architecture.
        """
        result = dlt_plugin.list_available_sinks()

        assert isinstance(result, list)
        assert len(result) >= 2
        assert "rest_api" in result
        assert "sql_database" in result

    @pytest.mark.requirement("4G-FR-006")
    def test_list_available_sinks_returns_strings(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test all items in list_available_sinks are strings.

        Validates type safety of the available sinks list.
        """
        result = dlt_plugin.list_available_sinks()

        for sink_type in result:
            assert isinstance(sink_type, str)

    @pytest.mark.requirement("4G-FR-007")
    def test_create_sink_with_valid_config(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test create_sink succeeds with valid configuration.

        Validates that sink creation works for the rest_api destination
        with proper connection configuration.
        """
        config = SinkConfig(
            sink_type="rest_api",
            connection_config={"base_url": "https://api.example.com"},
        )

        sink = dlt_plugin.create_sink(config)

        assert sink is not None

    @pytest.mark.requirement("4G-FR-007")
    def test_create_sink_with_invalid_config_raises_error(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test create_sink raises SinkConfigurationError for invalid sink type.

        Validates proper error handling when an unsupported sink type
        is requested.
        """
        config = SinkConfig(
            sink_type="invalid_type_xyz",
            connection_config={},
        )

        with pytest.raises(SinkConfigurationError):
            dlt_plugin.create_sink(config)

    @pytest.mark.requirement("4G-FR-008")
    def test_write_with_mock_data_returns_egress_result(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test write method returns EgressResult with mock data.

        Validates that data writing succeeds and returns proper metrics
        including success status and row count.
        """
        mock_sink = MagicMock()
        mock_data = MagicMock()
        mock_data.num_rows = 100

        result = dlt_plugin.write(mock_sink, mock_data)

        assert isinstance(result, EgressResult)
        assert result.success is True
        assert result.rows_delivered >= 0

    @pytest.mark.requirement("4G-FR-008")
    def test_write_with_empty_table_succeeds(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test write succeeds with empty table (0 rows).

        Validates that writing an empty table is handled correctly
        and returns appropriate metrics.
        """
        mock_sink = MagicMock()
        mock_data = MagicMock()
        mock_data.num_rows = 0

        result = dlt_plugin.write(mock_sink, mock_data)

        assert result.success is True
        assert result.rows_delivered == 0

    @pytest.mark.requirement("4G-FR-008")
    def test_write_returns_egress_result_type(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test write returns exactly an EgressResult instance.

        Validates type safety - result must be EgressResult,
        not a subclass or dict-like object.
        """
        mock_sink = MagicMock()
        mock_data = MagicMock()
        mock_data.num_rows = 50

        result = dlt_plugin.write(mock_sink, mock_data)

        assert type(result) is EgressResult

    @pytest.mark.requirement("4G-FR-009")
    def test_get_source_config_returns_iceberg_config(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test get_source_config returns Iceberg catalog configuration.

        Validates that the plugin generates proper source configuration
        for reading from the Iceberg Gold layer via Polaris catalog.
        """
        catalog_config = {
            "uri": "http://polaris:8181/api/catalog",
            "warehouse": "floe_warehouse",
        }

        result = dlt_plugin.get_source_config(catalog_config)

        assert isinstance(result, dict)
        # Check for expected keys (exact keys depend on implementation)
        assert len(result) > 0
        # At minimum, should contain catalog connection info
        assert "uri" in result or "catalog_uri" in result

    @pytest.mark.requirement("4G-FR-005")
    def test_sink_methods_require_started_state(self) -> None:
        """Test sink methods raise RuntimeError when plugin not started.

        Validates that all SinkConnector methods enforce the startup
        lifecycle requirement before allowing operations.
        """
        unstarted_plugin = DltIngestionPlugin()

        # Test list_available_sinks
        with pytest.raises(RuntimeError, match="start"):
            unstarted_plugin.list_available_sinks()

        # Test create_sink
        config = SinkConfig(sink_type="rest_api", connection_config={})
        with pytest.raises(RuntimeError, match="start"):
            unstarted_plugin.create_sink(config)

        # Test write
        mock_sink = MagicMock()
        mock_data = MagicMock()
        with pytest.raises(RuntimeError, match="start"):
            unstarted_plugin.write(mock_sink, mock_data)

        # Test get_source_config
        with pytest.raises(RuntimeError, match="start"):
            unstarted_plugin.get_source_config({})

    @pytest.mark.requirement("4G-SC-007")
    def test_write_completes_within_5s_for_1000_rows(
        self, dlt_plugin: DltIngestionPlugin
    ) -> None:
        """Test write() completes within 5 seconds for 1000-row dataset.

        Performance smoke test validating that the write path can handle
        a moderately-sized dataset within acceptable latency bounds.
        Uses a mock sink to isolate write-path overhead from network I/O.
        """
        import time

        import pyarrow as pa

        # Create 1000-row Arrow table
        table = pa.table(
            {
                "id": list(range(1000)),
                "name": [f"row_{i}" for i in range(1000)],
                "value": [float(i) * 1.5 for i in range(1000)],
            }
        )

        mock_sink = MagicMock()

        start = time.monotonic()
        result = dlt_plugin.write(mock_sink, table)
        elapsed = time.monotonic() - start

        assert result.success is True
        assert elapsed < 5.0, f"write() took {elapsed:.2f}s, exceeding 5s limit"
