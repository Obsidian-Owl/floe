"""Facet builder classes for OpenLineage integration.

This module provides builder classes for constructing OpenLineage facets
from various data sources. All builders use static methods and maintain
no state, following a functional approach.

Facets are metadata dictionaries that attach to datasets, runs, or jobs
in the OpenLineage specification. This module supports both standard
OpenLineage facets and custom floe-specific facets.

See Also:
    - ADR-0007: OpenLineage enforced
    - Epic 6B: OpenLineage Integration
    - OpenLineage spec: https://openlineage.io/docs/spec/facets/
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


class SchemaFacetBuilder:
    """Builder for OpenLineage SchemaDatasetFacet.

    Constructs schema facets from column definitions, typically extracted
    from dbt models, Iceberg tables, or other data sources.

    Examples:
        >>> columns = [{"name": "id", "type": "INTEGER"}, {"name": "name", "type": "VARCHAR"}]
        >>> facet = SchemaFacetBuilder.from_columns(columns)
        >>> facet["fields"][0]["name"]
        'id'
    """

    @staticmethod
    def from_columns(columns: list[dict[str, Any]]) -> dict[str, Any]:
        """Build SchemaDatasetFacet from column definitions.

        Args:
            columns: List of column dicts with "name" and "type" keys.
                Example: [{"name": "id", "type": "INTEGER"}]

        Returns:
            OpenLineage SchemaDatasetFacet dict with _producer, _schemaURL, and fields.

        Examples:
            >>> columns = [{"name": "customer_id", "type": "BIGINT"}]
            >>> facet = SchemaFacetBuilder.from_columns(columns)
            >>> facet["_producer"]
            'floe'
            >>> len(facet["fields"])
            1
        """
        return {
            "_producer": "floe",
            "_schemaURL": "https://openlineage.io/spec/facets/1-1-1/SchemaDatasetFacet.json",
            "fields": [{"name": col["name"], "type": col["type"]} for col in columns],
        }


class StatisticsFacetBuilder:
    """Builder for OpenLineage OutputStatisticsOutputDatasetFacet.

    Constructs statistics facets from row counts, byte counts, and file counts.
    Used to track dataset size and volume metrics.

    Examples:
        >>> facet = StatisticsFacetBuilder.from_counts(row_count=1000, bytes_count=50000)
        >>> facet["rowCount"]
        1000
    """

    @staticmethod
    def from_counts(
        row_count: int | None = None,
        bytes_count: int | None = None,
        file_count: int | None = None,
    ) -> dict[str, Any]:
        """Build OutputStatisticsOutputDatasetFacet from counts.

        Args:
            row_count: Number of rows in the dataset.
            bytes_count: Size of the dataset in bytes.
            file_count: Number of files in the dataset.

        Returns:
            OpenLineage OutputStatisticsOutputDatasetFacet dict.

        Examples:
            >>> facet = StatisticsFacetBuilder.from_counts(row_count=500)
            >>> facet["rowCount"]
            500
            >>> "bytesCount" in facet
            False
        """
        facet: dict[str, Any] = {
            "_producer": "floe",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-2/OutputStatisticsOutputDatasetFacet.json",
        }
        if row_count is not None:
            facet["rowCount"] = row_count
        if bytes_count is not None:
            facet["bytesCount"] = bytes_count
        if file_count is not None:
            facet["fileCount"] = file_count
        return facet


class QualityFacetBuilder:
    """Builder for OpenLineage DataQualityAssertionsDatasetFacet.

    Constructs quality facets from quality check results, typically from
    dbt tests or data quality plugins.

    Examples:
        >>> results = [{"name": "not_null_id", "passed": True, "dimension": "completeness"}]
        >>> facet = QualityFacetBuilder.from_check_results(results)
        >>> facet["assertions"][0]["assertion"]
        'not_null_id'
    """

    @staticmethod
    def from_check_results(results: list[dict[str, Any]]) -> dict[str, Any]:
        """Build DataQualityAssertionsDatasetFacet from check results.

        Args:
            results: List of check result dicts with "name", "passed", and "dimension" keys.
                Example: [{"name": "not_null_id", "passed": True, "dimension": "completeness"}]

        Returns:
            OpenLineage DataQualityAssertionsDatasetFacet dict.

        Examples:
            >>> results = [
            ...     {"name": "unique_id", "passed": True, "dimension": "validity"},
            ...     {"name": "positive_amount", "passed": False, "dimension": "accuracy"},
            ... ]
            >>> facet = QualityFacetBuilder.from_check_results(results)
            >>> len(facet["assertions"])
            2
            >>> facet["assertions"][1]["success"]
            False
        """
        assertions = []
        for result in results:
            assertions.append(
                {
                    "assertion": result["name"],
                    "success": result["passed"],
                    "column": result.get("column"),
                }
            )

        return {
            "_producer": "floe",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityAssertionsDatasetFacet.json",
            "assertions": assertions,
        }


class TraceCorrelationFacetBuilder:
    """Builder for custom trace correlation facet.

    Extracts trace_id and span_id from the current OpenTelemetry context
    to correlate lineage events with distributed traces.

    Examples:
        >>> facet = TraceCorrelationFacetBuilder.from_otel_context()
        >>> # Returns None if no active OTel context
        >>> facet is None
        True
    """

    @staticmethod
    def from_otel_context() -> dict[str, Any] | None:
        """Build trace correlation facet from current OTel context.

        Extracts trace_id and span_id from the active OpenTelemetry span.
        Returns None if OpenTelemetry is not available or no span is active.

        Returns:
            Custom trace correlation facet dict, or None if no active context.

        Examples:
            >>> # With active OTel span
            >>> facet = TraceCorrelationFacetBuilder.from_otel_context()
            >>> # facet would contain trace_id and span_id if span is active
        """
        try:
            from opentelemetry.trace import get_current_span
        except ImportError:
            return None

        span = get_current_span()
        if span is None or not span.is_recording():
            return None

        context = span.get_span_context()
        if not context.is_valid:
            return None

        return {
            "_producer": "floe",
            "_schemaURL": "https://floe.dev/lineage/facets/v1/TraceCorrelationFacet.json",
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
        }


class ParentRunFacetBuilder:
    """Builder for OpenLineage ParentRunFacet.

    Constructs parent run facets to establish hierarchical relationships
    between job runs (e.g., a dbt model run as child of a Dagster asset run).

    Examples:
        >>> parent_id = UUID("12345678-1234-5678-1234-567812345678")
        >>> facet = ParentRunFacetBuilder.from_parent(
        ...     parent_run_id=parent_id,
        ...     parent_job_name="dagster_asset",
        ...     parent_job_namespace="floe"
        ... )
        >>> facet["run"]["runId"]
        '12345678-1234-5678-1234-567812345678'
    """

    @staticmethod
    def from_parent(
        parent_run_id: UUID,
        parent_job_name: str,
        parent_job_namespace: str,
    ) -> dict[str, Any]:
        """Build ParentRunFacet from parent run information.

        Args:
            parent_run_id: UUID of the parent run.
            parent_job_name: Name of the parent job.
            parent_job_namespace: Namespace of the parent job.

        Returns:
            OpenLineage ParentRunFacet dict.

        Examples:
            >>> from uuid import uuid4
            >>> parent_id = uuid4()
            >>> facet = ParentRunFacetBuilder.from_parent(
            ...     parent_run_id=parent_id,
            ...     parent_job_name="parent_job",
            ...     parent_job_namespace="floe"
            ... )
            >>> facet["job"]["name"]
            'parent_job'
        """
        return {
            "_producer": "floe",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-1/ParentRunFacet.json",
            "run": {"runId": str(parent_run_id)},
            "job": {
                "namespace": parent_job_namespace,
                "name": parent_job_name,
            },
        }


class SQLJobFacetBuilder:
    """Builder for OpenLineage SQLJobFacet.

    Constructs SQL job facets from SQL query strings, typically from
    dbt models or other SQL-based transformations.

    Examples:
        >>> facet = SQLJobFacetBuilder.from_query("SELECT * FROM customers")
        >>> facet["query"]
        'SELECT * FROM customers'
    """

    @staticmethod
    def from_query(sql: str) -> dict[str, Any]:
        """Build SQLJobFacet from SQL query string.

        Args:
            sql: SQL query string.

        Returns:
            OpenLineage SQLJobFacet dict.

        Examples:
            >>> facet = SQLJobFacetBuilder.from_query("SELECT id, name FROM users")
            >>> facet["query"]
            'SELECT id, name FROM users'
            >>> facet["_producer"]
            'floe'
        """
        return {
            "_producer": "floe",
            "_schemaURL": "https://openlineage.io/spec/facets/1-0-1/SQLJobFacet.json",
            "query": sql,
        }


class IcebergSnapshotFacetBuilder:
    """Builder for custom Iceberg snapshot facet.

    Constructs Iceberg-specific facets from snapshot metadata, tracking
    snapshot IDs, timestamps, operations, and summary statistics.

    Examples:
        >>> facet = IcebergSnapshotFacetBuilder.from_snapshot(
        ...     snapshot_id=123456789,
        ...     timestamp_ms=1609459200000,
        ...     operation="append",
        ...     summary={"added-files": "5", "added-records": "1000"}
        ... )
        >>> facet["snapshot_id"]
        123456789
    """

    @staticmethod
    def from_snapshot(
        snapshot_id: int,
        timestamp_ms: int,
        operation: str,
        summary: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build Iceberg snapshot facet from snapshot metadata.

        Args:
            snapshot_id: Iceberg snapshot ID.
            timestamp_ms: Snapshot timestamp in milliseconds since epoch.
            operation: Snapshot operation (append, overwrite, delete, etc.).
            summary: Optional summary statistics dict.

        Returns:
            Custom Iceberg snapshot facet dict.

        Examples:
            >>> facet = IcebergSnapshotFacetBuilder.from_snapshot(
            ...     snapshot_id=987654321,
            ...     timestamp_ms=1640995200000,
            ...     operation="overwrite"
            ... )
            >>> facet["operation"]
            'overwrite'
            >>> facet["_schemaURL"]
            'https://floe.dev/lineage/facets/v1/IcebergSnapshotFacet.json'
        """
        facet: dict[str, Any] = {
            "_producer": "floe",
            "_schemaURL": "https://floe.dev/lineage/facets/v1/IcebergSnapshotFacet.json",
            "snapshot_id": snapshot_id,
            "timestamp_ms": timestamp_ms,
            "operation": operation,
        }
        if summary is not None:
            facet["summary"] = summary
        return facet


class ColumnLineageFacetBuilder:
    """Builder for OpenLineage ColumnLineageDatasetFacet.

    Constructs column-level lineage facets from dbt manifest metadata,
    mapping downstream columns to their upstream sources.

    Examples:
        >>> model_columns = {"revenue": {"name": "revenue", "data_type": "DECIMAL"}}
        >>> upstream = [{"namespace": "prod", "name": "orders", "field": "amount"}]
        >>> facet = ColumnLineageFacetBuilder.from_dbt_columns(model_columns, upstream)
        >>> "revenue" in facet["fields"]
        True
    """

    @staticmethod
    def from_dbt_columns(
        model_columns: dict[str, dict[str, Any]],
        upstream_models: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build ColumnLineageDatasetFacet from dbt manifest columns.

        Maps model columns to their upstream sources. If a model has explicit
        column dependencies in the manifest, those are used. Otherwise, assumes
        IDENTITY transformation from all upstream columns with matching names.

        Args:
            model_columns: Dict of column definitions from dbt manifest.
                Example: {"col_name": {"name": "col_name", "data_type": "VARCHAR"}}
            upstream_models: List of upstream model dicts with namespace, name, and field.
                Example: [{"namespace": "prod", "name": "stg_orders", "field": "order_id"}]

        Returns:
            OpenLineage ColumnLineageDatasetFacet dict.

        Examples:
            >>> columns = {
            ...     "customer_id": {"name": "customer_id", "data_type": "BIGINT"},
            ...     "order_count": {"name": "order_count", "data_type": "INTEGER"},
            ... }
            >>> upstream = [
            ...     {"namespace": "staging", "name": "stg_customers", "field": "customer_id"},
            ...     {"namespace": "staging", "name": "stg_orders", "field": "customer_id"},
            ... ]
            >>> facet = ColumnLineageFacetBuilder.from_dbt_columns(columns, upstream)
            >>> "customer_id" in facet["fields"]
            True
        """
        fields: dict[str, Any] = {}

        for col_name, col_def in model_columns.items():
            # Find upstream columns with matching name (IDENTITY transformation)
            input_fields = [
                {
                    "namespace": upstream["namespace"],
                    "name": upstream["name"],
                    "field": upstream["field"],
                }
                for upstream in upstream_models
                if upstream["field"] == col_name
            ]

            fields[col_name] = {
                "inputFields": input_fields,
                "transformationType": "IDENTITY",
                "transformationDescription": "",
            }

        return {
            "_producer": "floe",
            "_schemaURL": "https://openlineage.io/spec/facets/1-1-0/ColumnLineageDatasetFacet.json",
            "fields": fields,
        }


__all__ = [
    "SchemaFacetBuilder",
    "StatisticsFacetBuilder",
    "QualityFacetBuilder",
    "TraceCorrelationFacetBuilder",
    "ParentRunFacetBuilder",
    "SQLJobFacetBuilder",
    "IcebergSnapshotFacetBuilder",
    "ColumnLineageFacetBuilder",
]
