"""Base test classes for plugin compliance testing.

This package provides abstract base test classes that plugin implementations
must pass. Each plugin type has a corresponding base test class:

- BaseCatalogPluginTests: Tests for CatalogPlugin implementations

Usage:
    Plugin test classes inherit from the appropriate base class and
    provide a fixture for their concrete plugin implementation.

Example:
    >>> from testing.base_classes import BaseCatalogPluginTests
    >>>
    >>> class TestPolarisPlugin(BaseCatalogPluginTests):
    ...     @pytest.fixture
    ...     def catalog_plugin(self):
    ...         return PolarisCatalogPlugin(config)
"""

from __future__ import annotations

from testing.base_classes.base_catalog_plugin_tests import BaseCatalogPluginTests

__all__ = ["BaseCatalogPluginTests"]
