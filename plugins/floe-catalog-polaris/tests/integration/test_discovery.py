"""Integration tests for Polaris catalog plugin discovery via entry points.

Tests for:
- FR-006: Plugin is discoverable via floe.catalogs entry point
- FR-004: Plugin correctly implements PluginMetadata
- FR-024: Plugin entry point discovery

These tests verify that the Polaris catalog plugin is correctly registered
via entry points and can be discovered at runtime.

This module uses BasePluginDiscoveryTests to provide standard discovery
test cases, reducing test duplication across plugins.

Task ID: T049
Phase: 7 - US7 (Reduce Test Duplication)
User Story: US7 - Reduce Test Duplication
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

import pytest

from floe_core import CatalogPlugin
from testing.base_classes import BasePluginDiscoveryTests

if TYPE_CHECKING:
    pass


@pytest.mark.integration
class TestPolarisCatalogPluginDiscovery(BasePluginDiscoveryTests):
    """Integration tests for Polaris catalog plugin discovery.

    Inherits standard discovery tests from BasePluginDiscoveryTests:
    - Entry point registration tests
    - Plugin loading tests
    - Metadata presence tests
    - ABC compliance tests
    - Lifecycle method presence tests

    Polaris-specific tests are added below.
    """

    # Required class variables for BasePluginDiscoveryTests
    entry_point_group: ClassVar[str] = "floe.catalogs"
    expected_name: ClassVar[str] = "polaris"
    expected_module_prefix: ClassVar[str] = "floe_catalog_polaris"
    expected_class_name: ClassVar[str] = "PolarisCatalogPlugin"
    expected_plugin_abc: ClassVar[type[Any]] = CatalogPlugin

    def create_plugin_instance(self, plugin_class: type[Any]) -> Any:
        """Create a PolarisCatalogPlugin instance with required config.

        Polaris plugin requires OAuth2 configuration to instantiate.
        """
        from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig

        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2=OAuth2Config(
                client_id="test-client",
                client_secret="test-secret",
                token_url="https://auth.example.com/oauth/token",
            ),
        )
        return plugin_class(config=config)

    # =========================================================================
    # Polaris-Specific Tests
    # =========================================================================

    @pytest.mark.requirement("FR-004")
    def test_polaris_plugin_description_mentions_polaris(self) -> None:
        """Test Polaris plugin description mentions Polaris."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        assert "polaris" in plugin.description.lower()

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_has_catalog_methods(self) -> None:
        """Test Polaris plugin has required CatalogPlugin methods."""
        from importlib.metadata import entry_points

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        # Required CatalogPlugin methods
        assert hasattr(plugin, "connect")
        assert hasattr(plugin, "create_namespace")
        assert hasattr(plugin, "list_namespaces")
        assert hasattr(plugin, "delete_namespace")
        assert hasattr(plugin, "create_table")
        assert hasattr(plugin, "list_tables")
        assert hasattr(plugin, "drop_table")
        assert hasattr(plugin, "vend_credentials")

        assert callable(plugin.connect)
        assert callable(plugin.create_namespace)
        assert callable(plugin.vend_credentials)

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_config_schema_returns_polaris_config(self) -> None:
        """Test get_config_schema() returns PolarisCatalogConfig class."""
        from importlib.metadata import entry_points

        from pydantic import BaseModel

        eps = entry_points(group=self.entry_point_group)
        matching = [ep for ep in eps if ep.name == self.expected_name]

        assert len(matching) == 1
        plugin_class = matching[0].load()
        plugin = self.create_plugin_instance(plugin_class)

        schema = plugin.get_config_schema()

        assert schema is not None
        assert isinstance(schema, type)
        assert issubclass(schema, BaseModel)
        assert schema.__name__ == "PolarisCatalogConfig"

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_discoverable_via_registry(self) -> None:
        """Test plugin can be discovered via floe-core plugin registry."""
        from floe_core.plugin_registry import PluginRegistry
        from floe_core.plugin_types import PluginType

        registry = PluginRegistry()
        registry.discover_all()

        # Use list_all() which returns discovered names without loading
        all_plugins = registry.list_all()
        catalog_plugin_names = all_plugins[PluginType.CATALOG]

        # Verify polaris is in the discovered plugins
        assert "polaris" in catalog_plugin_names
