"""Unit test fixtures for floe-compute-duckdb.

Unit tests use mocks and don't require external services.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def duckdb_plugin() -> Any:
    """Create a DuckDBComputePlugin instance for testing."""
    from floe_compute_duckdb import DuckDBComputePlugin

    return DuckDBComputePlugin()


@pytest.fixture
def memory_config() -> Any:
    """Create an in-memory DuckDB ComputeConfig for testing."""
    from floe_core import ComputeConfig

    return ComputeConfig(
        plugin="duckdb",
        threads=4,
        connection={
            "path": ":memory:",
        },
    )


@pytest.fixture
def catalog_config() -> Any:
    """Create an Iceberg CatalogConfig for testing."""
    from floe_core import CatalogConfig
    from pydantic import SecretStr

    return CatalogConfig(
        catalog_type="rest",
        catalog_name="ice",
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="floe_warehouse",
        credentials={
            "client_id": SecretStr("test_client"),
            "client_secret": SecretStr("test_secret"),
        },
    )
