"""Unit tests for sink error classes in reverse ETL (Epic 4G).

This module tests the NEW error classes that will be added for reverse ETL:
- SinkConnectionError: For errors connecting to downstream operational systems
- SinkWriteError: For errors writing data to sinks (e.g., CRM, OLTP databases)
- SinkConfigurationError: For misconfigured sink connections or credentials

These tests are written using TDD - they will FAIL until the error classes
are implemented in floe_ingestion_dlt.errors module.

All error classes follow the same pattern as existing ingestion errors:
- Inherit from IngestionError
- Use keyword-only parameters with defaults
- Have category-specific defaults (TRANSIENT vs CONFIGURATION)
- Include context suffix for debugging
"""

from __future__ import annotations

import pytest

from floe_ingestion_dlt.errors import (
    ErrorCategory,
    IngestionError,
    SinkConfigurationError,
    SinkConnectionError,
    SinkWriteError,
)


class TestSinkErrorClasses:
    """Test suite for NEW sink error classes (Epic 4G - Reverse ETL)."""

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_connection_error_default_category_transient(self) -> None:
        """Test SinkConnectionError has TRANSIENT default category."""
        error = SinkConnectionError(
            message="Failed to connect to destination",
            source_type="salesforce",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_write_error_default_category_transient(self) -> None:
        """Test SinkWriteError has TRANSIENT default category."""
        error = SinkWriteError(
            message="Failed to write records to sink",
            destination_table="gold.customers",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_configuration_error_default_category_configuration(self) -> None:
        """Test SinkConfigurationError has CONFIGURATION default category."""
        error = SinkConfigurationError(
            message="Invalid sink credentials",
            source_type="sql_database",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.CONFIGURATION

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_connection_error_inherits_from_ingestion_error(self) -> None:
        """Test SinkConnectionError inherits from IngestionError."""
        error = SinkConnectionError(
            message="connection failed", source_type="rest_api", pipeline_name="test"
        )
        assert isinstance(error, IngestionError)

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_write_error_inherits_from_ingestion_error(self) -> None:
        """Test SinkWriteError inherits from IngestionError."""
        error = SinkWriteError(
            message="write failed",
            destination_table="gold.orders",
            pipeline_name="test",
        )
        assert isinstance(error, IngestionError)

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_configuration_error_inherits_from_ingestion_error(self) -> None:
        """Test SinkConfigurationError inherits from IngestionError."""
        error = SinkConfigurationError(
            message="config invalid", source_type="sql_database", pipeline_name="test"
        )
        assert isinstance(error, IngestionError)

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_connection_error_includes_context_suffix(self) -> None:
        """Test SinkConnectionError includes context in string representation."""
        error = SinkConnectionError(
            message="connection failed", source_type="rest_api", pipeline_name="test"
        )
        error_str = str(error)
        assert "rest_api" in error_str
        assert "connection failed" in error_str

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_write_error_includes_context_suffix(self) -> None:
        """Test SinkWriteError includes destination_table in string representation."""
        error = SinkWriteError(
            message="write failed",
            destination_table="gold.customers",
            pipeline_name="test",
        )
        error_str = str(error)
        assert "gold.customers" in error_str
        assert "write failed" in error_str

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_configuration_error_includes_context_suffix(self) -> None:
        """Test SinkConfigurationError includes source_type in string representation."""
        error = SinkConfigurationError(
            message="invalid config",
            source_type="sql_database",
            pipeline_name="test",
        )
        error_str = str(error)
        assert "sql_database" in error_str
        assert "invalid config" in error_str

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_errors_carry_message_attribute(self) -> None:
        """Test sink errors carry the original message as an attribute."""
        original_message = "Sink connection timeout after 30s"
        error = SinkConnectionError(
            message=original_message, source_type="rest_api", pipeline_name="test"
        )
        assert error.message == original_message

    @pytest.mark.requirement("4G-FR-013")
    def test_sink_connection_error_custom_category_override(self) -> None:
        """Test SinkConnectionError allows custom category override."""
        error = SinkConnectionError(
            message="permanent failure",
            source_type="rest_api",
            pipeline_name="test",
            category=ErrorCategory.PERMANENT,
        )
        assert error.category == ErrorCategory.PERMANENT
