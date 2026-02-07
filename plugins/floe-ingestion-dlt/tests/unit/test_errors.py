"""Unit tests for error hierarchy (T050).

Tests error inheritance, default categories, and context propagation.
"""

from __future__ import annotations

import pytest

from floe_ingestion_dlt.errors import (
    ErrorCategory,
    IngestionError,
    SourceConnectionError,
    DestinationWriteError,
    SchemaContractViolation,
    PipelineConfigurationError,
)


class TestErrorHierarchy:
    """Test error hierarchy and default categories."""

    @pytest.mark.requirement("4F-FR-055")
    def test_ingestion_error_is_base_exception(self) -> None:
        """Test IngestionError inherits from Exception."""
        error = IngestionError(
            message="test error",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert isinstance(error, Exception)

    @pytest.mark.requirement("4F-FR-055")
    def test_source_connection_error_inherits_ingestion_error(self) -> None:
        """Test SourceConnectionError inherits from IngestionError."""
        error = SourceConnectionError(
            message="connection failed",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert isinstance(error, IngestionError)
        assert isinstance(error, Exception)

    @pytest.mark.requirement("4F-FR-055")
    def test_destination_write_error_inherits_ingestion_error(self) -> None:
        """Test DestinationWriteError inherits from IngestionError."""
        error = DestinationWriteError(
            message="write failed",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert isinstance(error, IngestionError)
        assert isinstance(error, Exception)

    @pytest.mark.requirement("4F-FR-055")
    def test_schema_contract_violation_inherits_ingestion_error(self) -> None:
        """Test SchemaContractViolation inherits from IngestionError."""
        error = SchemaContractViolation(
            message="schema mismatch",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert isinstance(error, IngestionError)
        assert isinstance(error, Exception)

    @pytest.mark.requirement("4F-FR-055")
    def test_pipeline_config_error_inherits_ingestion_error(self) -> None:
        """Test PipelineConfigurationError inherits from IngestionError."""
        error = PipelineConfigurationError(
            message="config invalid",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert isinstance(error, IngestionError)
        assert isinstance(error, Exception)

    @pytest.mark.requirement("4F-FR-056")
    def test_ingestion_error_carries_context(self) -> None:
        """Test IngestionError carries context fields."""
        error = IngestionError(
            message="test error",
            source_type="github",
            destination_table="repos.commits",
            pipeline_name="github_pipeline",
        )
        assert error.source_type == "github"
        assert error.destination_table == "repos.commits"
        assert error.pipeline_name == "github_pipeline"

    @pytest.mark.requirement("4F-FR-056")
    def test_source_connection_error_default_category_transient(self) -> None:
        """Test SourceConnectionError has TRANSIENT default category."""
        error = SourceConnectionError(
            message="connection failed",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4F-FR-056")
    def test_destination_write_error_default_category_transient(self) -> None:
        """Test DestinationWriteError has TRANSIENT default category."""
        error = DestinationWriteError(
            message="write failed",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.TRANSIENT

    @pytest.mark.requirement("4F-FR-056")
    def test_schema_contract_violation_default_category_permanent(self) -> None:
        """Test SchemaContractViolation has PERMANENT default category."""
        error = SchemaContractViolation(
            message="schema mismatch",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.PERMANENT

    @pytest.mark.requirement("4F-FR-056")
    def test_pipeline_config_error_default_category_configuration(self) -> None:
        """Test PipelineConfigurationError has CONFIGURATION default category."""
        error = PipelineConfigurationError(
            message="config invalid",
            source_type="test_source",
            destination_table="test_table",
            pipeline_name="test_pipeline",
        )
        assert error.category == ErrorCategory.CONFIGURATION

    @pytest.mark.requirement("4F-FR-056")
    def test_error_context_in_str_representation(self) -> None:
        """Test error string representation includes context fields."""
        error = IngestionError(
            message="test error",
            source_type="github",
            destination_table="repos.commits",
            pipeline_name="github_pipeline",
        )
        error_str = str(error)
        assert "test error" in error_str
        assert "github" in error_str
        assert "repos.commits" in error_str
        assert "github_pipeline" in error_str
