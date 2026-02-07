"""Root conftest for floe-ingestion-dlt tests.

Provides shared fixtures available to both unit and integration tests.
Imports reusable fixtures from testing.fixtures.ingestion.
"""

from __future__ import annotations

import pytest
from floe_ingestion_dlt.plugin import DltIngestionPlugin

# Re-export shared fixtures so they're available in all test tiers
from testing.fixtures.ingestion import (  # noqa: F401
    create_dlt_ingestion_config,
    create_ingestion_source_config,
    dlt_config,
    dlt_plugin,
    mock_dlt_source,
    sample_ingestion_config,
    sample_ingestion_source_config,
)


@pytest.fixture
def plugin_instance() -> DltIngestionPlugin:
    """Create a bare DltIngestionPlugin instance without lifecycle.

    Returns:
        Uninitialized DltIngestionPlugin (no startup called).
    """
    return DltIngestionPlugin()
