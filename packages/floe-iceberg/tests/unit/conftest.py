"""Unit test configuration for floe-iceberg.

This conftest.py imports fixtures from the parent conftest.py.
Unit tests use mock plugins and do not require external services.

Note:
    No __init__.py files in test directories - pytest uses importlib mode.
"""

from __future__ import annotations

# Re-export fixtures from parent conftest for explicit discovery
# pytest will find them automatically, but this makes dependencies clear
from tests.conftest import (
    catalog_with_namespace,
    connected_catalog_plugin,
    mock_catalog,
    mock_catalog_plugin,
    mock_fileio,
    mock_storage_plugin,
)

__all__ = [
    "catalog_with_namespace",
    "connected_catalog_plugin",
    "mock_catalog",
    "mock_catalog_plugin",
    "mock_fileio",
    "mock_storage_plugin",
]
