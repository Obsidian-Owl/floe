"""Plugin compliance tests for PolarisCatalogPlugin.

This module validates that PolarisCatalogPlugin correctly implements the
CatalogPlugin ABC by inheriting from BaseCatalogPluginTests.

All tests from BaseCatalogPluginTests are automatically run against
the Polaris plugin, ensuring:
- Plugin metadata (name, version, floe_api_version)
- Method existence (connect, create_namespace, etc.)
- Lifecycle methods (startup, shutdown)
- Config schema validation
- Health check return types

Requirements Covered:
    - FR-004: Plugin metadata compliance
    - FR-006: PolarisCatalogPlugin implements CatalogPlugin ABC
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

from testing.base_classes import BaseCatalogPluginTests

if TYPE_CHECKING:
    from floe_core import CatalogPlugin


class TestPolarisCatalogPluginCompliance(BaseCatalogPluginTests):
    """Validate PolarisCatalogPlugin compliance with CatalogPlugin ABC.

    Inherits all tests from BaseCatalogPluginTests to automatically verify
    that the Polaris plugin meets all interface requirements.

    The catalog_plugin fixture provides a configured PolarisCatalogPlugin
    instance for each test.
    """

    @pytest.fixture
    def catalog_plugin(self) -> CatalogPlugin:
        """Return a configured PolarisCatalogPlugin for testing.

        Returns:
            PolarisCatalogPlugin instance with test configuration.
        """
        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
        )
        return PolarisCatalogPlugin(config=config)
