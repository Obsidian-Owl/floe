"""Unit tests for PolarisCatalogPlugin instantiation.

This module tests the PolarisCatalogPlugin class instantiation and
metadata properties, verifying it correctly implements the CatalogPlugin ABC.

Requirements Covered:
    - FR-006: PolarisCatalogPlugin implements CatalogPlugin ABC
    - FR-004: Plugin metadata (name, version, floe_api_version)

Note: These tests are written TDD-style BEFORE implementation (T031).
They will FAIL until PolarisCatalogPlugin is implemented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig

if TYPE_CHECKING:
    from floe_core import CatalogPlugin


def _create_test_config() -> PolarisCatalogConfig:
    """Create a valid PolarisCatalogConfig for testing."""
    return PolarisCatalogConfig(
        uri="https://polaris.example.com/api/catalog",
        warehouse="test_warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        ),
    )


class TestPolarisCatalogPluginInstantiation:
    """Unit tests for PolarisCatalogPlugin instantiation."""

    @pytest.mark.requirement("FR-006")
    def test_plugin_can_be_imported(self) -> None:
        """Test PolarisCatalogPlugin can be imported from package."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        assert PolarisCatalogPlugin is not None

    @pytest.mark.requirement("FR-006")
    def test_plugin_is_subclass_of_catalog_plugin(self) -> None:
        """Test PolarisCatalogPlugin inherits from CatalogPlugin ABC."""
        from floe_core import CatalogPlugin

        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        assert issubclass(PolarisCatalogPlugin, CatalogPlugin)

    @pytest.mark.requirement("FR-006")
    def test_plugin_can_be_instantiated_with_config(self) -> None:
        """Test PolarisCatalogPlugin can be instantiated with valid config."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        assert plugin is not None

    @pytest.mark.requirement("FR-006")
    def test_plugin_stores_config(self) -> None:
        """Test PolarisCatalogPlugin stores config after instantiation."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        plugin = PolarisCatalogPlugin(config=config)

        assert plugin.config == config


class TestPolarisCatalogPluginMetadata:
    """Unit tests for PolarisCatalogPlugin metadata properties."""

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_name_property(self, plugin: CatalogPlugin) -> None:
        """Test plugin has a name property."""
        assert hasattr(plugin, "name")
        assert isinstance(plugin.name, str)
        assert len(plugin.name) > 0

    @pytest.mark.requirement("FR-004")
    def test_plugin_name_is_polaris(self, plugin: CatalogPlugin) -> None:
        """Test plugin name is 'polaris'."""
        assert plugin.name == "polaris"

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_version_property(self, plugin: CatalogPlugin) -> None:
        """Test plugin has a version property."""
        assert hasattr(plugin, "version")
        assert isinstance(plugin.version, str)
        assert len(plugin.version) > 0

    @pytest.mark.requirement("FR-004")
    def test_plugin_version_is_semver(self, plugin: CatalogPlugin) -> None:
        """Test plugin version follows semantic versioning format."""
        import re

        version = plugin.version
        # Basic semver pattern: X.Y.Z with optional pre-release
        semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$"
        assert re.match(semver_pattern, version), f"Version '{version}' not semver"

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_floe_api_version_property(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test plugin has floe_api_version property."""
        assert hasattr(plugin, "floe_api_version")
        assert isinstance(plugin.floe_api_version, str)
        assert len(plugin.floe_api_version) > 0

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_description_property(self, plugin: CatalogPlugin) -> None:
        """Test plugin has a description property."""
        assert hasattr(plugin, "description")
        assert isinstance(plugin.description, str)

    @pytest.mark.requirement("FR-004")
    def test_plugin_description_mentions_polaris(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test plugin description mentions Polaris."""
        assert "polaris" in plugin.description.lower()

    @pytest.mark.requirement("FR-004")
    def test_plugin_has_dependencies_property(self, plugin: CatalogPlugin) -> None:
        """Test plugin has a dependencies property."""
        assert hasattr(plugin, "dependencies")
        assert isinstance(plugin.dependencies, list)


class TestPolarisCatalogPluginMethods:
    """Unit tests for PolarisCatalogPlugin method existence."""

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_connect_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has connect() method."""
        assert hasattr(plugin, "connect")
        assert callable(plugin.connect)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_create_namespace_method(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test plugin has create_namespace() method."""
        assert hasattr(plugin, "create_namespace")
        assert callable(plugin.create_namespace)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_list_namespaces_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has list_namespaces() method."""
        assert hasattr(plugin, "list_namespaces")
        assert callable(plugin.list_namespaces)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_delete_namespace_method(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test plugin has delete_namespace() method."""
        assert hasattr(plugin, "delete_namespace")
        assert callable(plugin.delete_namespace)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_create_table_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has create_table() method."""
        assert hasattr(plugin, "create_table")
        assert callable(plugin.create_table)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_list_tables_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has list_tables() method."""
        assert hasattr(plugin, "list_tables")
        assert callable(plugin.list_tables)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_drop_table_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has drop_table() method."""
        assert hasattr(plugin, "drop_table")
        assert callable(plugin.drop_table)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_vend_credentials_method(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test plugin has vend_credentials() method."""
        assert hasattr(plugin, "vend_credentials")
        assert callable(plugin.vend_credentials)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_health_check_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has health_check() method."""
        assert hasattr(plugin, "health_check")
        assert callable(plugin.health_check)


class TestPolarisCatalogPluginLifecycle:
    """Unit tests for PolarisCatalogPlugin lifecycle methods."""

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_startup_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has startup() lifecycle method."""
        assert hasattr(plugin, "startup")
        assert callable(plugin.startup)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_shutdown_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has shutdown() lifecycle method."""
        assert hasattr(plugin, "shutdown")
        assert callable(plugin.shutdown)

    @pytest.mark.requirement("FR-006")
    def test_startup_does_not_raise(self, plugin: CatalogPlugin) -> None:
        """Test startup() can be called without raising."""
        # Should not raise
        plugin.startup()

    @pytest.mark.requirement("FR-006")
    def test_shutdown_does_not_raise(self, plugin: CatalogPlugin) -> None:
        """Test shutdown() can be called without raising."""
        # Should not raise
        plugin.shutdown()


class TestPolarisCatalogPluginConfigSchema:
    """Unit tests for PolarisCatalogPlugin config schema."""

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_get_config_schema_method(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test plugin has get_config_schema() method."""
        assert hasattr(plugin, "get_config_schema")
        assert callable(plugin.get_config_schema)

    @pytest.mark.requirement("FR-006")
    def test_config_schema_returns_polaris_config_class(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test get_config_schema() returns PolarisCatalogConfig class."""
        from pydantic import BaseModel

        schema = plugin.get_config_schema()

        assert schema is not None
        assert isinstance(schema, type)
        assert issubclass(schema, BaseModel)

    @pytest.mark.requirement("FR-006")
    def test_config_schema_is_polaris_catalog_config(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test get_config_schema() returns PolarisCatalogConfig specifically."""
        schema = plugin.get_config_schema()

        assert schema.__name__ == "PolarisCatalogConfig"


class TestPolarisCatalogPluginConnect:
    """Unit tests for PolarisCatalogPlugin connect() method.

    These tests use mocking to verify the connect() method builds
    the correct configuration without requiring a real Polaris instance.
    """

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-006")
    def test_connect_method_is_callable(self, plugin: CatalogPlugin) -> None:
        """Test connect() method exists and is callable."""
        assert hasattr(plugin, "connect")
        assert callable(plugin.connect)

    @pytest.mark.requirement("FR-009")
    def test_connect_builds_rest_catalog_config(self, plugin: CatalogPlugin) -> None:
        """Test connect() builds proper REST catalog configuration.

        This test mocks pyiceberg.catalog.load_catalog to verify
        the configuration passed to it is correct.
        """
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ) as mock_load:
            result = plugin.connect({})

            # Verify load_catalog was called
            mock_load.assert_called_once()

            # Get the call arguments
            call_args = mock_load.call_args
            catalog_name = call_args[0][0]  # First positional arg
            config_kwargs = call_args[1]  # Keyword args

            # Verify catalog name
            assert catalog_name == "polaris"

            # Verify config keys
            assert config_kwargs["type"] == "rest"
            assert config_kwargs["uri"] == "https://polaris.example.com/api/catalog"
            assert config_kwargs["warehouse"] == "test_warehouse"
            assert "credential" in config_kwargs
            assert "test-client:" in config_kwargs["credential"]
            assert config_kwargs["token-refresh-enabled"] == "true"

            # Verify result is the mock catalog
            assert result == mock_catalog

    @pytest.mark.requirement("FR-009")
    def test_connect_includes_oauth2_token_url(self, plugin: CatalogPlugin) -> None:
        """Test connect() includes OAuth2 token URL in config."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ) as mock_load:
            plugin.connect({})

            config_kwargs = mock_load.call_args[1]
            assert config_kwargs["oauth2-server-uri"] == (
                "https://auth.example.com/oauth/token"
            )

    @pytest.mark.requirement("FR-009")
    def test_connect_accepts_scope_override(self, plugin: CatalogPlugin) -> None:
        """Test connect() accepts scope parameter override."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ) as mock_load:
            plugin.connect({"scope": "PRINCIPAL_ROLE:data_engineer"})

            config_kwargs = mock_load.call_args[1]
            assert config_kwargs["scope"] == "PRINCIPAL_ROLE:data_engineer"

    @pytest.mark.requirement("FR-009")
    def test_connect_merges_additional_config(self, plugin: CatalogPlugin) -> None:
        """Test connect() merges additional configuration from argument."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ) as mock_load:
            plugin.connect({"py-io-impl": "pyiceberg.io.fsspec.FsspecFileIO"})

            config_kwargs = mock_load.call_args[1]
            assert config_kwargs["py-io-impl"] == "pyiceberg.io.fsspec.FsspecFileIO"

    @pytest.mark.requirement("FR-009")
    def test_connect_stores_catalog_reference(self) -> None:
        """Test connect() stores the catalog reference internally."""
        from unittest.mock import MagicMock, patch

        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ):
            plugin.connect({})

            # Access private attribute to verify storage
            assert plugin._catalog == mock_catalog
