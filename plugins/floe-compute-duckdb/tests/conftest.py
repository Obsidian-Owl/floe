"""Shared pytest fixtures for floe-compute-duckdb tests.

This module provides common fixtures used across unit and integration tests
for the DuckDB compute plugin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def duckdb_plugin() -> Any:
    """Create a DuckDBComputePlugin instance for testing.

    Returns:
        A configured DuckDBComputePlugin instance.

    Example:
        >>> def test_plugin_name(duckdb_plugin):
        ...     assert duckdb_plugin.name == "duckdb"
    """
    from floe_compute_duckdb import DuckDBComputePlugin

    return DuckDBComputePlugin()


@pytest.fixture
def memory_config() -> Any:
    """Create an in-memory DuckDB ComputeConfig for testing.

    Returns:
        ComputeConfig configured for in-memory DuckDB.

    Example:
        >>> def test_memory_connection(duckdb_plugin, memory_config):
        ...     result = duckdb_plugin.validate_connection(memory_config)
        ...     assert result.success
    """
    from floe_core.plugins.compute import ComputeConfig

    return ComputeConfig(
        database="test",
        extra={
            "path": ":memory:",
            "threads": 4,
        },
    )


@pytest.fixture
def catalog_config() -> Any:
    """Create an Iceberg CatalogConfig for testing.

    Returns:
        CatalogConfig configured for a test Polaris catalog.

    Example:
        >>> def test_catalog_attachment(duckdb_plugin, catalog_config):
        ...     sql = duckdb_plugin.get_catalog_attachment_sql(catalog_config)
        ...     assert sql is not None
    """
    from floe_core.plugins.compute import CatalogConfig

    return CatalogConfig(
        catalog_name="ice",
        catalog_uri="http://polaris:8181/api/catalog",
        warehouse="floe_warehouse",
        credentials={
            "client_id": "test_client",
            "client_secret": "test_secret",
        },
    )
