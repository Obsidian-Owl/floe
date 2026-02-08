"""Tests for OpenLineage facet builders.

This module tests the facet builder classes that construct OpenLineage
facets from various data sources.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

from floe_core.lineage.facets import (
    ColumnLineageFacetBuilder,
    IcebergSnapshotFacetBuilder,
    ParentRunFacetBuilder,
    QualityFacetBuilder,
    SchemaFacetBuilder,
    SQLJobFacetBuilder,
    StatisticsFacetBuilder,
    TraceCorrelationFacetBuilder,
)


class TestSchemaFacetBuilder:
    """Tests for SchemaFacetBuilder."""

    def test_from_columns_basic(self) -> None:
        """Build schema facet from basic column list."""
        columns = [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "VARCHAR"},
        ]
        facet = SchemaFacetBuilder.from_columns(columns)

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "SchemaDatasetFacet" in facet["_schemaURL"]
        assert len(facet["fields"]) == 2
        assert facet["fields"][0]["name"] == "id"
        assert facet["fields"][0]["type"] == "INTEGER"
        assert facet["fields"][1]["name"] == "name"
        assert facet["fields"][1]["type"] == "VARCHAR"

    def test_from_columns_empty(self) -> None:
        """Build schema facet from empty column list."""
        facet = SchemaFacetBuilder.from_columns([])
        assert facet["fields"] == []

    def test_from_columns_complex_types(self) -> None:
        """Build schema facet with complex data types."""
        columns = [
            {"name": "metadata", "type": "STRUCT<key:STRING,value:STRING>"},
            {"name": "tags", "type": "ARRAY<STRING>"},
        ]
        facet = SchemaFacetBuilder.from_columns(columns)
        assert len(facet["fields"]) == 2
        assert facet["fields"][0]["type"] == "STRUCT<key:STRING,value:STRING>"


class TestStatisticsFacetBuilder:
    """Tests for StatisticsFacetBuilder."""

    def test_from_counts_all_fields(self) -> None:
        """Build statistics facet with all count fields."""
        facet = StatisticsFacetBuilder.from_counts(
            row_count=1000,
            bytes_count=50000,
            file_count=5,
        )

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "OutputStatisticsOutputDatasetFacet" in facet["_schemaURL"]
        assert facet["rowCount"] == 1000
        assert facet["bytesCount"] == 50000
        assert facet["fileCount"] == 5

    def test_from_counts_partial(self) -> None:
        """Build statistics facet with only some fields."""
        facet = StatisticsFacetBuilder.from_counts(row_count=500)
        assert facet["rowCount"] == 500
        assert "bytesCount" not in facet
        assert "fileCount" not in facet

    def test_from_counts_none(self) -> None:
        """Build statistics facet with no counts."""
        facet = StatisticsFacetBuilder.from_counts()
        assert "rowCount" not in facet
        assert "bytesCount" not in facet
        assert "fileCount" not in facet
        assert facet["_producer"] == "floe"


class TestQualityFacetBuilder:
    """Tests for QualityFacetBuilder."""

    def test_from_check_results_basic(self) -> None:
        """Build quality facet from check results."""
        results = [
            {"name": "not_null_id", "passed": True, "dimension": "completeness"},
            {"name": "unique_id", "passed": True, "dimension": "validity"},
            {"name": "positive_amount", "passed": False, "dimension": "accuracy"},
        ]
        facet = QualityFacetBuilder.from_check_results(results)

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "DataQualityAssertionsDatasetFacet" in facet["_schemaURL"]
        assert len(facet["assertions"]) == 3
        assert facet["assertions"][0]["assertion"] == "not_null_id"
        assert facet["assertions"][0]["success"] is True
        assert facet["assertions"][2]["success"] is False

    def test_from_check_results_with_column(self) -> None:
        """Build quality facet with column information."""
        results = [
            {
                "name": "not_null_email",
                "passed": True,
                "dimension": "completeness",
                "column": "email",
            }
        ]
        facet = QualityFacetBuilder.from_check_results(results)
        assert facet["assertions"][0]["column"] == "email"

    def test_from_check_results_empty(self) -> None:
        """Build quality facet from empty results."""
        facet = QualityFacetBuilder.from_check_results([])
        assert facet["assertions"] == []


class TestTraceCorrelationFacetBuilder:
    """Tests for TraceCorrelationFacetBuilder."""

    @pytest.mark.requirement("REQ-521")
    def test_from_otel_context_with_active_span(self) -> None:
        """Extract trace correlation from active OTel span."""
        # Mock OpenTelemetry span
        mock_context = MagicMock()
        mock_context.trace_id = 0x12345678901234567890123456789012
        mock_context.span_id = 0x1234567890123456
        mock_context.is_valid = True

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            facet = TraceCorrelationFacetBuilder.from_otel_context()

        assert facet is not None
        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "TraceCorrelationFacet" in facet["_schemaURL"]
        assert "trace_id" in facet
        assert "span_id" in facet
        assert len(facet["trace_id"]) == 32  # 128-bit trace_id as hex
        assert len(facet["span_id"]) == 16  # 64-bit span_id as hex

    @pytest.mark.requirement("REQ-521")
    def test_from_otel_context_no_active_span(self) -> None:
        """Return None when no active OTel span."""
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            facet = TraceCorrelationFacetBuilder.from_otel_context()

        assert facet is None

    @pytest.mark.requirement("REQ-521")
    def test_from_otel_context_no_opentelemetry(self) -> None:
        """Return None when OpenTelemetry not available."""
        import sys

        original_module = sys.modules.get("opentelemetry.trace")

        if "opentelemetry.trace" in sys.modules:
            del sys.modules["opentelemetry.trace"]

        try:
            with patch.dict("sys.modules", {"opentelemetry.trace": None}):
                facet = TraceCorrelationFacetBuilder.from_otel_context()
            assert facet is None
        finally:
            if original_module is not None:
                sys.modules["opentelemetry.trace"] = original_module

    @pytest.mark.requirement("REQ-521")
    def test_from_otel_context_invalid_context(self) -> None:
        """Return None when span context is invalid."""
        mock_context = MagicMock()
        mock_context.is_valid = False

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            facet = TraceCorrelationFacetBuilder.from_otel_context()

        assert facet is None


class TestParentRunFacetBuilder:
    """Tests for ParentRunFacetBuilder."""

    def test_from_parent_basic(self) -> None:
        """Build parent run facet from parent information."""
        parent_id = uuid4()
        facet = ParentRunFacetBuilder.from_parent(
            parent_run_id=parent_id,
            parent_job_name="dagster_asset",
            parent_job_namespace="floe",
        )

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "ParentRunFacet" in facet["_schemaURL"]
        assert facet["run"]["runId"] == str(parent_id)
        assert facet["job"]["name"] == "dagster_asset"
        assert facet["job"]["namespace"] == "floe"

    def test_from_parent_uuid_string_conversion(self) -> None:
        """Parent run ID is converted to string."""
        parent_id = UUID("12345678-1234-5678-1234-567812345678")
        facet = ParentRunFacetBuilder.from_parent(
            parent_run_id=parent_id,
            parent_job_name="test_job",
            parent_job_namespace="test_ns",
        )
        assert isinstance(facet["run"]["runId"], str)
        assert facet["run"]["runId"] == "12345678-1234-5678-1234-567812345678"


class TestSQLJobFacetBuilder:
    """Tests for SQLJobFacetBuilder."""

    def test_from_query_basic(self) -> None:
        """Build SQL job facet from query string."""
        sql = "SELECT * FROM customers WHERE active = true"
        facet = SQLJobFacetBuilder.from_query(sql)

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "SQLJobFacet" in facet["_schemaURL"]
        assert facet["query"] == sql

    def test_from_query_multiline(self) -> None:
        """Build SQL job facet from multiline query."""
        sql = """
        SELECT
            customer_id,
            SUM(amount) as total
        FROM orders
        GROUP BY customer_id
        """
        facet = SQLJobFacetBuilder.from_query(sql)
        assert facet["query"] == sql


class TestIcebergSnapshotFacetBuilder:
    """Tests for IcebergSnapshotFacetBuilder."""

    @pytest.mark.requirement("REQ-531")
    def test_from_snapshot_basic(self) -> None:
        """Build Iceberg snapshot facet from snapshot metadata."""
        facet = IcebergSnapshotFacetBuilder.from_snapshot(
            snapshot_id=123456789,
            timestamp_ms=1609459200000,
            operation="append",
        )

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "IcebergSnapshotFacet" in facet["_schemaURL"]
        assert facet["snapshot_id"] == 123456789
        assert facet["timestamp_ms"] == 1609459200000
        assert facet["operation"] == "append"
        assert "summary" not in facet

    @pytest.mark.requirement("REQ-531")
    def test_from_snapshot_with_summary(self) -> None:
        """Build Iceberg snapshot facet with summary statistics."""
        summary = {
            "added-files": "5",
            "added-records": "1000",
            "total-files": "25",
        }
        facet = IcebergSnapshotFacetBuilder.from_snapshot(
            snapshot_id=987654321,
            timestamp_ms=1640995200000,
            operation="overwrite",
            summary=summary,
        )

        assert facet["summary"] == summary
        assert facet["summary"]["added-files"] == "5"

    @pytest.mark.requirement("REQ-531")
    def test_from_snapshot_operations(self) -> None:
        """Build Iceberg snapshot facets for different operations."""
        operations = ["append", "overwrite", "delete", "replace"]
        for op in operations:
            facet = IcebergSnapshotFacetBuilder.from_snapshot(
                snapshot_id=1,
                timestamp_ms=1000,
                operation=op,
            )
            assert facet["operation"] == op


class TestColumnLineageFacetBuilder:
    """Tests for ColumnLineageFacetBuilder."""

    def test_from_dbt_columns_basic(self) -> None:
        """Build column lineage facet from dbt columns."""
        model_columns = {
            "customer_id": {"name": "customer_id", "data_type": "BIGINT"},
            "order_count": {"name": "order_count", "data_type": "INTEGER"},
        }
        upstream_models = [
            {"namespace": "staging", "name": "stg_customers", "field": "customer_id"},
            {"namespace": "staging", "name": "stg_orders", "field": "customer_id"},
        ]

        facet = ColumnLineageFacetBuilder.from_dbt_columns(
            model_columns, upstream_models
        )

        assert facet["_producer"] == "floe"
        assert "_schemaURL" in facet
        assert "ColumnLineageDatasetFacet" in facet["_schemaURL"]
        assert "customer_id" in facet["fields"]
        assert len(facet["fields"]["customer_id"]["inputFields"]) == 2
        assert facet["fields"]["customer_id"]["transformationType"] == "IDENTITY"

    def test_from_dbt_columns_no_upstream(self) -> None:
        """Build column lineage facet with no upstream matches."""
        model_columns = {
            "new_column": {"name": "new_column", "data_type": "VARCHAR"},
        }
        upstream_models = [
            {"namespace": "staging", "name": "stg_data", "field": "other_column"},
        ]

        facet = ColumnLineageFacetBuilder.from_dbt_columns(
            model_columns, upstream_models
        )

        assert "new_column" in facet["fields"]
        assert facet["fields"]["new_column"]["inputFields"] == []

    def test_from_dbt_columns_multiple_sources(self) -> None:
        """Build column lineage facet with multiple upstream sources."""
        model_columns = {
            "id": {"name": "id", "data_type": "BIGINT"},
        }
        upstream_models = [
            {"namespace": "bronze", "name": "raw_orders", "field": "id"},
            {"namespace": "bronze", "name": "raw_customers", "field": "id"},
            {"namespace": "silver", "name": "stg_orders", "field": "id"},
        ]

        facet = ColumnLineageFacetBuilder.from_dbt_columns(
            model_columns, upstream_models
        )

        assert len(facet["fields"]["id"]["inputFields"]) == 3
        assert facet["fields"]["id"]["inputFields"][0]["namespace"] == "bronze"
        assert facet["fields"]["id"]["inputFields"][0]["name"] == "raw_orders"


class TestCustomFacetSchemaURLs:
    """Tests for custom facet _schemaURL format."""

    @pytest.mark.requirement("REQ-529")
    def test_trace_correlation_schema_url(self) -> None:
        """Trace correlation facet uses custom floe schema URL."""
        mock_context = MagicMock()
        mock_context.trace_id = 0x12345678901234567890123456789012
        mock_context.span_id = 0x1234567890123456
        mock_context.is_valid = True

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_span.get_span_context.return_value = mock_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            facet = TraceCorrelationFacetBuilder.from_otel_context()

        assert facet is not None
        assert facet["_schemaURL"].startswith("https://floe.dev/lineage/facets/v1/")
        assert "TraceCorrelationFacet.json" in facet["_schemaURL"]

    @pytest.mark.requirement("REQ-529")
    def test_iceberg_snapshot_schema_url(self) -> None:
        """Iceberg snapshot facet uses custom floe schema URL."""
        facet = IcebergSnapshotFacetBuilder.from_snapshot(
            snapshot_id=1,
            timestamp_ms=1000,
            operation="append",
        )
        assert facet["_schemaURL"].startswith("https://floe.dev/lineage/facets/v1/")
        assert "IcebergSnapshotFacet.json" in facet["_schemaURL"]

    def test_standard_facets_use_openlineage_urls(self) -> None:
        """Standard OpenLineage facets use official schema URLs."""
        schema_facet = SchemaFacetBuilder.from_columns([])
        assert "openlineage.io" in schema_facet["_schemaURL"]

        stats_facet = StatisticsFacetBuilder.from_counts()
        assert "openlineage.io" in stats_facet["_schemaURL"]

        quality_facet = QualityFacetBuilder.from_check_results([])
        assert "openlineage.io" in quality_facet["_schemaURL"]

        parent_facet = ParentRunFacetBuilder.from_parent(
            parent_run_id=uuid4(),
            parent_job_name="test",
            parent_job_namespace="test",
        )
        assert "openlineage.io" in parent_facet["_schemaURL"]

        sql_facet = SQLJobFacetBuilder.from_query("SELECT 1")
        assert "openlineage.io" in sql_facet["_schemaURL"]

        column_facet = ColumnLineageFacetBuilder.from_dbt_columns({}, [])
        assert "openlineage.io" in column_facet["_schemaURL"]
