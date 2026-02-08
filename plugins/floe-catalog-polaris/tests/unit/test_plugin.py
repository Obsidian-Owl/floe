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
    def test_plugin_has_floe_api_version_property(self, plugin: CatalogPlugin) -> None:
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
    def test_plugin_description_mentions_polaris(self, plugin: CatalogPlugin) -> None:
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
    def test_plugin_has_create_namespace_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has create_namespace() method."""
        assert hasattr(plugin, "create_namespace")
        assert callable(plugin.create_namespace)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_list_namespaces_method(self, plugin: CatalogPlugin) -> None:
        """Test plugin has list_namespaces() method."""
        assert hasattr(plugin, "list_namespaces")
        assert callable(plugin.list_namespaces)

    @pytest.mark.requirement("FR-006")
    def test_plugin_has_delete_namespace_method(self, plugin: CatalogPlugin) -> None:
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
    def test_plugin_has_vend_credentials_method(self, plugin: CatalogPlugin) -> None:
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
    def test_plugin_has_get_config_schema_method(self, plugin: CatalogPlugin) -> None:
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

    @pytest.mark.requirement("FR-058")
    def test_connect_includes_access_delegation_header_when_enabled(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test connect() includes X-Iceberg-Access-Delegation header when enabled.

        When credential_vending_enabled=True, the header should be set to
        'vended-credentials' to request that Polaris returns temporary
        credentials in table load responses.
        """
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ) as mock_load:
            plugin.connect({})

            config_kwargs = mock_load.call_args[1]
            assert config_kwargs.get("header.X-Iceberg-Access-Delegation") == (
                "vended-credentials"
            )

    @pytest.mark.requirement("FR-058")
    def test_connect_omits_access_delegation_header_when_disabled(self) -> None:
        """Test connect() omits X-Iceberg-Access-Delegation header when disabled.

        When credential_vending_enabled=False, the header should not be
        included in the catalog configuration.
        """
        from unittest.mock import MagicMock, patch

        from floe_catalog_polaris.config import PolarisCatalogConfig
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        # Create config with credential vending disabled
        config = PolarisCatalogConfig(
            uri="https://polaris.example.com/api/catalog",
            warehouse="test_warehouse",
            oauth2={
                "client_id": "test-client",
                "client_secret": "test-secret",
                "token_url": "https://auth.example.com/oauth/token",
            },
            credential_vending_enabled=False,
        )
        plugin = PolarisCatalogPlugin(config=config)
        mock_catalog = MagicMock()

        with patch(
            "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
        ) as mock_load:
            plugin.connect({})

            config_kwargs = mock_load.call_args[1]
            assert "header.X-Iceberg-Access-Delegation" not in config_kwargs


class TestPolarisCatalogPluginTracing:
    """Unit tests for PolarisCatalogPlugin OpenTelemetry tracing.

    These tests verify that connect() creates proper OTel spans with
    correct attributes for observability.
    """

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-030")
    def test_connect_creates_otel_span(self, plugin: CatalogPlugin) -> None:
        """Test connect() creates an OpenTelemetry span for the operation."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()
        mock_span = MagicMock()
        mock_tracer = MagicMock()

        with (
            patch(
                "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
            ),
            patch("floe_catalog_polaris.plugin.get_tracer", return_value=mock_tracer),
            patch("floe_catalog_polaris.plugin.catalog_span") as mock_catalog_span,
        ):
            mock_catalog_span.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_catalog_span.return_value.__exit__ = MagicMock(return_value=False)

            plugin.connect({})

            # Verify catalog_span was called with correct arguments
            mock_catalog_span.assert_called_once()
            call_args = mock_catalog_span.call_args
            assert call_args[0][0] == mock_tracer  # tracer arg
            assert call_args[0][1] == "connect"  # operation arg

    @pytest.mark.requirement("FR-030")
    def test_connect_span_has_catalog_attributes(self, plugin: CatalogPlugin) -> None:
        """Test connect() span includes catalog.name, catalog.uri, warehouse attributes."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()
        mock_span = MagicMock()
        mock_tracer = MagicMock()

        with (
            patch(
                "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
            ),
            patch("floe_catalog_polaris.plugin.get_tracer", return_value=mock_tracer),
            patch("floe_catalog_polaris.plugin.catalog_span") as mock_catalog_span,
        ):
            mock_catalog_span.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_catalog_span.return_value.__exit__ = MagicMock(return_value=False)

            plugin.connect({})

            # Verify span attributes
            call_kwargs = mock_catalog_span.call_args[1]
            assert call_kwargs["catalog_name"] == "polaris"
            assert (
                call_kwargs["catalog_uri"] == "https://polaris.example.com/api/catalog"
            )
            assert call_kwargs["warehouse"] == "test_warehouse"

    @pytest.mark.requirement("FR-031")
    def test_connect_sets_error_attributes_on_failure(
        self, plugin: CatalogPlugin
    ) -> None:
        """Test connect() sets error attributes on span when connection fails."""
        from unittest.mock import MagicMock, patch

        mock_span = MagicMock()
        mock_tracer = MagicMock()
        test_error = ConnectionError("Connection refused")

        with (
            patch("floe_catalog_polaris.plugin.load_catalog", side_effect=test_error),
            patch("floe_catalog_polaris.plugin.get_tracer", return_value=mock_tracer),
            patch("floe_catalog_polaris.plugin.catalog_span") as mock_catalog_span,
            patch("floe_catalog_polaris.plugin.set_error_attributes") as mock_set_error,
        ):
            mock_catalog_span.return_value.__enter__ = MagicMock(return_value=mock_span)
            mock_catalog_span.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(ConnectionError):
                plugin.connect({})

            # Verify set_error_attributes was called with the span and error
            mock_set_error.assert_called_once_with(mock_span, test_error)


class TestPolarisCatalogPluginLogging:
    """Unit tests for PolarisCatalogPlugin structlog logging.

    These tests verify that connect() emits proper structured logs
    for observability and debugging.
    """

    @pytest.fixture
    def plugin(self) -> CatalogPlugin:
        """Create a PolarisCatalogPlugin instance for testing."""
        from floe_catalog_polaris.plugin import PolarisCatalogPlugin

        config = _create_test_config()
        return PolarisCatalogPlugin(config=config)

    @pytest.mark.requirement("FR-029")
    def test_connect_logs_operation_start(self, plugin: CatalogPlugin) -> None:
        """Test connect() logs when connection attempt starts."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()
        mock_logger = MagicMock()

        with (
            patch(
                "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
            ),
            patch("floe_catalog_polaris.plugin.logger") as patched_logger,
        ):
            patched_logger.bind.return_value = mock_logger

            plugin.connect({})

            # Verify logger was bound with uri and warehouse
            patched_logger.bind.assert_called_once()
            bind_kwargs = patched_logger.bind.call_args[1]
            assert "uri" in bind_kwargs
            assert "warehouse" in bind_kwargs

            # Verify info log for start
            mock_logger.info.assert_any_call("connecting_to_polaris_catalog")

    @pytest.mark.requirement("FR-029")
    def test_connect_logs_success(self, plugin: CatalogPlugin) -> None:
        """Test connect() logs on successful connection."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()
        mock_logger = MagicMock()

        with (
            patch(
                "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
            ),
            patch("floe_catalog_polaris.plugin.logger") as patched_logger,
        ):
            patched_logger.bind.return_value = mock_logger

            plugin.connect({})

            # Verify success log
            mock_logger.info.assert_any_call("polaris_catalog_connected")

    @pytest.mark.requirement("FR-029")
    def test_connect_logs_failure(self, plugin: CatalogPlugin) -> None:
        """Test connect() logs on connection failure."""
        from unittest.mock import MagicMock, patch

        mock_logger = MagicMock()
        test_error = ConnectionError("Connection refused")

        with (
            patch("floe_catalog_polaris.plugin.load_catalog", side_effect=test_error),
            patch("floe_catalog_polaris.plugin.logger") as patched_logger,
        ):
            patched_logger.bind.return_value = mock_logger

            with pytest.raises(ConnectionError):
                plugin.connect({})

            # Verify error log with error details
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "polaris_catalog_connection_failed"
            assert "error" in call_args[1]

    @pytest.mark.requirement("FR-032")
    def test_connect_does_not_log_credentials(self, plugin: CatalogPlugin) -> None:
        """Test connect() does NOT log credentials or secrets."""
        from unittest.mock import MagicMock, patch

        mock_catalog = MagicMock()
        all_logs: list[tuple[str, dict[str, str]]] = []

        class MockBoundLogger:
            def info(self, event: str, **kwargs: str) -> None:
                all_logs.append((event, kwargs))

            def debug(self, event: str, **kwargs: str) -> None:
                all_logs.append((event, kwargs))

            def error(self, event: str, **kwargs: str) -> None:
                all_logs.append((event, kwargs))

        mock_bound = MockBoundLogger()

        with (
            patch(
                "floe_catalog_polaris.plugin.load_catalog", return_value=mock_catalog
            ),
            patch("floe_catalog_polaris.plugin.logger") as patched_logger,
        ):
            patched_logger.bind.return_value = mock_bound

            plugin.connect({})

            # Check no logs contain credentials
            for event, kwargs in all_logs:
                # Check event name doesn't contain secret
                assert "secret" not in event.lower()
                assert "password" not in event.lower()
                assert "credential" not in event.lower()

                # Check kwargs don't contain secret values
                for key, value in kwargs.items():
                    assert "test-secret" not in str(value)  # Our test secret
                    assert "client_secret" not in key.lower()
                    assert "password" not in key.lower()


class TestPolarisCatalogPluginEntryPoint:
    """Unit tests for PolarisCatalogPlugin entry point registration.

    These tests verify that the plugin is correctly registered via
    entry points and can be discovered by the plugin registry.
    """

    @pytest.mark.requirement("FR-006")
    def test_plugin_entry_point_is_registered(self) -> None:
        """Test plugin is registered under floe.catalogs entry point group."""
        from importlib.metadata import entry_points

        # Get all entry points for the floe.catalogs group
        eps = entry_points(group="floe.catalogs")

        # Find our plugin
        polaris_eps = [ep for ep in eps if ep.name == "polaris"]

        assert len(polaris_eps) == 1, "Expected one 'polaris' entry point"
        ep = polaris_eps[0]
        assert ep.name == "polaris"
        assert "PolarisCatalogPlugin" in ep.value

    @pytest.mark.requirement("FR-006")
    def test_plugin_can_be_loaded_via_entry_point(self) -> None:
        """Test plugin can be loaded dynamically via entry point."""
        from importlib.metadata import entry_points

        from floe_core import CatalogPlugin

        eps = entry_points(group="floe.catalogs")
        polaris_eps = [ep for ep in eps if ep.name == "polaris"]

        assert len(polaris_eps) == 1
        ep = polaris_eps[0]

        # Load the plugin class via entry point
        plugin_class = ep.load()

        # Verify it's the correct class
        assert plugin_class.__name__ == "PolarisCatalogPlugin"
        assert issubclass(plugin_class, CatalogPlugin)

    @pytest.mark.requirement("FR-006")
    def test_plugin_discoverable_via_registry(self) -> None:
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
