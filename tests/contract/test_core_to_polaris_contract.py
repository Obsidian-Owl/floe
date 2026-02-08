"""Contract tests for floe-core to floe-catalog-polaris integration.

These tests validate that the PolarisCatalogPlugin from floe-catalog-polaris
correctly implements the CatalogPlugin ABC from floe-core.

This is a cross-package contract test that imports from BOTH packages to
ensure they can work together. It validates:
- PolarisCatalogPlugin is a valid CatalogPlugin implementation
- The plugin can be instantiated with valid configuration
- All ABC methods are implemented
- Plugin metadata properties are present and valid
- Config schema is a valid Pydantic model

Requirements Covered:
    - FR-006: PolarisCatalogPlugin implements CatalogPlugin ABC
    - FR-004: Plugin metadata (name, version, floe_api_version)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

# Import from floe-catalog-polaris (the contract consumer)
from floe_catalog_polaris import PolarisCatalogPlugin
from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig

# Import from floe-core (the contract provider)
from floe_core import HealthStatus, PluginMetadata
from floe_core.plugins import CatalogPlugin

if TYPE_CHECKING:
    pass


def _create_test_config() -> PolarisCatalogConfig:
    """Create a valid PolarisCatalogConfig for testing.

    Returns:
        PolarisCatalogConfig with test credentials.
    """
    return PolarisCatalogConfig(
        uri="https://polaris.example.com/api/catalog",
        warehouse="test_warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        ),
    )


class TestCoreToPolarisCatalogContract:
    """Contract tests validating PolarisCatalogPlugin implements CatalogPlugin."""

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_is_catalog_plugin_subclass(self) -> None:
        """Verify PolarisCatalogPlugin inherits from CatalogPlugin.

        This validates the inheritance relationship required by the plugin
        system.
        """
        assert issubclass(PolarisCatalogPlugin, CatalogPlugin)

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_inherits_from_plugin_metadata(self) -> None:
        """Verify PolarisCatalogPlugin inherits from PluginMetadata.

        PluginMetadata provides the standard metadata interface for all plugins.
        """
        assert issubclass(PolarisCatalogPlugin, PluginMetadata)

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_is_concrete_not_abstract(self) -> None:
        """Verify PolarisCatalogPlugin is a concrete class, not abstract.

        The plugin must be instantiable to be usable.
        """
        # While PolarisCatalogPlugin inherits from ABC indirectly,
        # it should be concrete (all abstract methods implemented)
        config = _create_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        assert plugin is not None

    @pytest.mark.requirement("FR-006")
    def test_polaris_plugin_can_be_instantiated(self) -> None:
        """Verify PolarisCatalogPlugin can be instantiated with config.

        This validates the constructor contract.
        """
        config = _create_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        assert isinstance(plugin, PolarisCatalogPlugin)
        assert isinstance(plugin, CatalogPlugin)
        assert plugin.config == config


class TestPolarisCatalogPluginMetadata:
    """Contract tests for plugin metadata compliance."""

    @pytest.fixture
    def plugin(self) -> PolarisCatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        return PolarisCatalogPlugin(config=_create_test_config())

    @pytest.mark.requirement("FR-004")
    def test_name_property_is_polaris(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify plugin name is 'polaris'."""
        assert plugin.name == "polaris"

    @pytest.mark.requirement("FR-004")
    def test_version_property_is_semver(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify plugin version follows semver format."""
        import re

        version = plugin.version
        assert isinstance(version, str)
        # Basic semver pattern: X.Y.Z with optional pre-release
        assert re.match(r"^\d+\.\d+\.\d+", version)

    @pytest.mark.requirement("FR-004")
    def test_floe_api_version_is_declared(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify plugin declares floe API version."""
        api_version = plugin.floe_api_version
        assert isinstance(api_version, str)
        assert len(api_version) > 0

    @pytest.mark.requirement("FR-004")
    def test_description_is_string(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify plugin has a description string."""
        assert isinstance(plugin.description, str)

    @pytest.mark.requirement("FR-004")
    def test_dependencies_is_list(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify plugin dependencies is a list."""
        assert isinstance(plugin.dependencies, list)


class TestPolarisCatalogPluginMethods:
    """Contract tests for required CatalogPlugin methods."""

    @pytest.fixture
    def plugin(self) -> PolarisCatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        return PolarisCatalogPlugin(config=_create_test_config())

    @pytest.mark.requirement("FR-001")
    def test_has_connect_method(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify connect() method exists and is callable."""
        assert hasattr(plugin, "connect")
        assert callable(plugin.connect)

    @pytest.mark.requirement("FR-002")
    def test_has_namespace_methods(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify namespace management methods exist."""
        assert hasattr(plugin, "create_namespace")
        assert callable(plugin.create_namespace)

        assert hasattr(plugin, "list_namespaces")
        assert callable(plugin.list_namespaces)

        assert hasattr(plugin, "delete_namespace")
        assert callable(plugin.delete_namespace)

    @pytest.mark.requirement("FR-003")
    def test_has_table_methods(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify table operation methods exist."""
        assert hasattr(plugin, "create_table")
        assert callable(plugin.create_table)

        assert hasattr(plugin, "list_tables")
        assert callable(plugin.list_tables)

        assert hasattr(plugin, "drop_table")
        assert callable(plugin.drop_table)

    @pytest.mark.requirement("FR-001")
    def test_has_vend_credentials_method(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify vend_credentials() method exists."""
        assert hasattr(plugin, "vend_credentials")
        assert callable(plugin.vend_credentials)

    @pytest.mark.requirement("FR-001")
    def test_has_health_check_method(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify health_check() method exists."""
        assert hasattr(plugin, "health_check")
        assert callable(plugin.health_check)

    @pytest.mark.requirement("FR-001")
    def test_health_check_returns_health_status(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify health_check() returns HealthStatus from floe-core.

        This validates the contract that plugins return the core HealthStatus type.
        """
        status = plugin.health_check(timeout=1.0)
        assert isinstance(status, HealthStatus)


class TestPolarisCatalogPluginConfigSchema:
    """Contract tests for plugin configuration schema."""

    @pytest.fixture
    def plugin(self) -> PolarisCatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        return PolarisCatalogPlugin(config=_create_test_config())

    @pytest.mark.requirement("FR-004")
    def test_get_config_schema_returns_pydantic_model(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify get_config_schema() returns a Pydantic BaseModel class."""
        from pydantic import BaseModel

        schema = plugin.get_config_schema()
        assert schema is not None
        assert isinstance(schema, type)
        assert issubclass(schema, BaseModel)

    @pytest.mark.requirement("FR-004")
    def test_config_schema_is_polaris_config(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify config schema is PolarisCatalogConfig."""
        schema = plugin.get_config_schema()
        assert schema is PolarisCatalogConfig


class TestPolarisCatalogPluginLifecycle:
    """Contract tests for plugin lifecycle methods."""

    @pytest.fixture
    def plugin(self) -> PolarisCatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        return PolarisCatalogPlugin(config=_create_test_config())

    @pytest.mark.requirement("FR-004")
    def test_startup_does_not_raise(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify startup() can be called without error."""
        # Should not raise
        plugin.startup()

    @pytest.mark.requirement("FR-004")
    def test_shutdown_does_not_raise(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify shutdown() can be called without error."""
        # Should not raise
        plugin.shutdown()

    @pytest.mark.requirement("FR-004")
    def test_lifecycle_sequence(self, plugin: PolarisCatalogPlugin) -> None:
        """Verify startup/shutdown can be called in sequence."""
        # Full lifecycle sequence
        plugin.startup()
        plugin.shutdown()
        # Should be idempotent
        plugin.shutdown()
