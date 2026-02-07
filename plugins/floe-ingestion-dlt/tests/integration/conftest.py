"""Integration test conftest for floe-ingestion-dlt.

Provides fixtures for integration tests requiring real services
(Polaris catalog, MinIO S3, dlt pipeline execution).
"""

from __future__ import annotations

import pytest
from floe_ingestion_dlt.config import IngestionSourceConfig
from floe_ingestion_dlt.plugin import DltIngestionPlugin

from testing.fixtures.ingestion import create_ingestion_source_config


@pytest.fixture
def integration_source_config() -> IngestionSourceConfig:
    """IngestionSourceConfig configured for integration test environment.

    Returns:
        Source config pointing to test infrastructure endpoints.
    """
    return create_ingestion_source_config(
        name="integration_test_source",
        source_type="rest_api",
        source_config={"base_url": "http://localhost:8080/api"},
        destination_table="bronze.integration_test_data",
    )


@pytest.fixture
def integration_plugin() -> DltIngestionPlugin:
    """DltIngestionPlugin instance for integration testing.

    Creates plugin, calls startup, returns it.
    Caller is responsible for shutdown if needed.

    Returns:
        Started DltIngestionPlugin instance.
    """
    plugin = DltIngestionPlugin()
    plugin.startup()
    return plugin
