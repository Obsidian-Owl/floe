"""Integration test fixtures for floe-compute-duckdb.

Integration tests require DuckDB to be available and may use real
database connections.
"""

from __future__ import annotations

# Import shared fixtures from parent conftest
from tests.conftest import catalog_config, duckdb_plugin, memory_config

__all__ = ["catalog_config", "duckdb_plugin", "memory_config"]
