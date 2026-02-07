"""Unit test conftest for floe-ingestion-dlt.

Provides fixtures for unit tests that use mocks and fakes.
No external service dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from floe_ingestion_dlt.config import IngestionSourceConfig, RetryConfig
from floe_ingestion_dlt.errors import ErrorCategory, IngestionError


@pytest.fixture
def mock_dlt_pipeline() -> MagicMock:
    """Mock dlt pipeline for unit testing.

    Returns:
        MagicMock configured as a dlt pipeline object.
    """
    pipeline = MagicMock()
    pipeline.pipeline_name = "test_pipeline"
    pipeline.dataset_name = "test_dataset"
    return pipeline


@pytest.fixture
def retry_config() -> RetryConfig:
    """RetryConfig with fast settings for unit tests.

    Returns:
        RetryConfig with minimal delays for fast test execution.
    """
    return RetryConfig(max_retries=2, initial_delay_seconds=0.1)


@pytest.fixture
def sample_source_configs() -> list[IngestionSourceConfig]:
    """Multiple IngestionSourceConfig instances for multi-source tests.

    Returns:
        List of 3 source configs covering different source types.
    """
    return [
        IngestionSourceConfig(
            name="rest_source",
            source_type="rest_api",
            source_config={"base_url": "https://api.example.com"},
            destination_table="bronze.raw_rest_data",
        ),
        IngestionSourceConfig(
            name="sql_source",
            source_type="sql_database",
            source_config={"connection_string": "postgresql://localhost/test"},
            destination_table="bronze.raw_sql_data",
        ),
        IngestionSourceConfig(
            name="file_source",
            source_type="filesystem",
            source_config={"bucket_url": "s3://test-bucket"},
            destination_table="bronze.raw_file_data",
        ),
    ]


@pytest.fixture
def transient_error() -> IngestionError:
    """Sample transient IngestionError for retry testing.

    Returns:
        IngestionError with TRANSIENT category.
    """
    return IngestionError(
        "Connection timeout",
        source_type="rest_api",
        destination_table="bronze.raw_events",
        category=ErrorCategory.TRANSIENT,
    )


@pytest.fixture
def permanent_error() -> IngestionError:
    """Sample permanent IngestionError for retry testing.

    Returns:
        IngestionError with PERMANENT category.
    """
    return IngestionError(
        "Authentication failed",
        source_type="rest_api",
        destination_table="bronze.raw_events",
        category=ErrorCategory.PERMANENT,
    )
