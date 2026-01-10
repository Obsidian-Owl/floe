"""Unit tests for catalog plugin test fixtures.

Tests the mock catalog plugin and related fixtures for testing
CatalogPlugin implementations.

Requirements Covered:
    - REQ-041: CatalogPlugin test fixtures
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from testing.fixtures.catalog import (
    CatalogConnectionError,
    CatalogTestConfig,
    MockCatalog,
    MockCatalogPlugin,
    MockTable,
    MockTableIO,
    create_mock_catalog_plugin,
    generate_unique_namespace,
    get_catalog_connection_info,
    mock_catalog_plugin_context,
)

if TYPE_CHECKING:
    pass


class TestCatalogTestConfig:
    """Tests for CatalogTestConfig configuration model."""

    @pytest.mark.requirement("REQ-041")
    def test_default_values(self) -> None:
        """Test CatalogTestConfig has sensible defaults."""
        config = CatalogTestConfig()
        assert config.catalog_type == "mock"
        assert config.uri == "http://polaris:8181/api/catalog"
        assert config.warehouse == "test_warehouse"
        assert config.namespace_prefix == "test"
        assert config.k8s_namespace == "floe-test"

    @pytest.mark.requirement("REQ-041")
    def test_frozen_config(self) -> None:
        """Test CatalogTestConfig is configured as frozen (immutable)."""
        # Verify model_config has frozen=True
        assert CatalogTestConfig.model_config.get("frozen") is True

    @pytest.mark.requirement("REQ-041")
    def test_k8s_uri_property(self) -> None:
        """Test k8s_uri property generates correct K8s DNS name."""
        config = CatalogTestConfig(uri="http://polaris:8181/api/catalog")
        expected = "http://polaris.floe-test.svc.cluster.local:8181/api/catalog"
        assert config.k8s_uri == expected

    @pytest.mark.requirement("REQ-041")
    def test_credential_is_secret(self) -> None:
        """Test credential field uses SecretStr for security."""
        config = CatalogTestConfig()
        # Should not expose secret in string representation
        assert "secret" not in str(config.credential)
        # Should be able to get secret value when needed
        assert config.credential.get_secret_value() == "root:secret"


class TestMockCatalog:
    """Tests for MockCatalog in-memory catalog."""

    @pytest.mark.requirement("REQ-041")
    def test_create_and_list_namespaces(self) -> None:
        """Test creating and listing namespaces."""
        catalog = MockCatalog()
        assert catalog.list_namespaces() == []

        catalog.create_namespace(("test",))
        namespaces = catalog.list_namespaces()
        assert len(namespaces) == 1
        assert ("test",) in namespaces

    @pytest.mark.requirement("REQ-041")
    def test_create_namespace_with_properties(self) -> None:
        """Test creating namespace with properties."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",), {"location": "s3://bucket/test"})
        # Namespace should be created
        assert ("test",) in catalog.list_namespaces()

    @pytest.mark.requirement("REQ-041")
    def test_create_duplicate_namespace_fails(self) -> None:
        """Test creating duplicate namespace raises error."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))
        with pytest.raises(ValueError, match="already exists"):
            catalog.create_namespace(("test",))

    @pytest.mark.requirement("REQ-041")
    def test_drop_namespace(self) -> None:
        """Test dropping a namespace."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))
        assert ("test",) in catalog.list_namespaces()

        catalog.drop_namespace(("test",))
        assert ("test",) not in catalog.list_namespaces()

    @pytest.mark.requirement("REQ-041")
    def test_drop_nonexistent_namespace_fails(self) -> None:
        """Test dropping nonexistent namespace raises error."""
        catalog = MockCatalog()
        with pytest.raises(KeyError, match="not found"):
            catalog.drop_namespace(("nonexistent",))

    @pytest.mark.requirement("REQ-041")
    def test_drop_nonempty_namespace_fails(self) -> None:
        """Test dropping non-empty namespace raises error."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))
        catalog.create_table("test.table1", {"type": "struct", "fields": []})

        with pytest.raises(ValueError, match="not empty"):
            catalog.drop_namespace(("test",))

    @pytest.mark.requirement("REQ-041")
    def test_create_and_list_tables(self) -> None:
        """Test creating and listing tables."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))

        schema: dict[str, Any] = {"type": "struct", "fields": []}
        catalog.create_table("test.table1", schema)
        catalog.create_table("test.table2", schema)

        tables = catalog.list_tables("test")
        assert len(tables) == 2
        assert ("test", "table1") in tables
        assert ("test", "table2") in tables

    @pytest.mark.requirement("REQ-041")
    def test_create_duplicate_table_fails(self) -> None:
        """Test creating duplicate table raises error."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))
        schema: dict[str, Any] = {"type": "struct", "fields": []}
        catalog.create_table("test.table1", schema)

        with pytest.raises(ValueError, match="already exists"):
            catalog.create_table("test.table1", schema)

    @pytest.mark.requirement("REQ-041")
    def test_drop_table(self) -> None:
        """Test dropping a table."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))
        catalog.create_table("test.table1", {})

        catalog.drop_table("test.table1")
        assert catalog.list_tables("test") == []

    @pytest.mark.requirement("REQ-041")
    def test_drop_nonexistent_table_fails(self) -> None:
        """Test dropping nonexistent table raises error."""
        catalog = MockCatalog()
        with pytest.raises(KeyError, match="not found"):
            catalog.drop_table("test.nonexistent")

    @pytest.mark.requirement("REQ-041")
    def test_load_table(self) -> None:
        """Test loading a table returns MockTable."""
        catalog = MockCatalog()
        catalog.create_namespace(("test",))
        schema = {"type": "struct", "fields": [{"id": 1, "name": "id", "type": "long"}]}
        catalog.create_table("test.table1", schema, location="s3://bucket/table1")

        table = catalog.load_table("test.table1")
        assert isinstance(table, MockTable)
        assert table.identifier == "test.table1"
        assert table.schema == schema
        assert table.location == "s3://bucket/table1"

    @pytest.mark.requirement("REQ-041")
    def test_load_nonexistent_table_fails(self) -> None:
        """Test loading nonexistent table raises error."""
        catalog = MockCatalog()
        with pytest.raises(KeyError, match="not found"):
            catalog.load_table("test.nonexistent")


class TestMockTableIO:
    """Tests for MockTableIO with mock credentials."""

    @pytest.mark.requirement("REQ-041")
    def test_mock_credentials(self) -> None:
        """Test MockTableIO has mock credential properties."""
        table_io = MockTableIO()
        assert table_io.properties["s3.access-key-id"] == "MOCK_ACCESS_KEY"
        assert table_io.properties["s3.secret-access-key"] == "MOCK_SECRET_KEY"
        assert table_io.properties["s3.session-token"] == "MOCK_SESSION_TOKEN"
        assert "s3.session-token-expires-at" in table_io.properties


class TestMockCatalogPlugin:
    """Tests for MockCatalogPlugin implementation."""

    @pytest.mark.requirement("REQ-041")
    def test_plugin_metadata(self) -> None:
        """Test plugin has correct metadata."""
        plugin = MockCatalogPlugin()
        assert plugin.name == "mock"
        assert plugin.version == "0.1.0"
        assert plugin.floe_api_version == "0.1"
        assert plugin.description == "Mock catalog plugin for testing"
        assert plugin.dependencies == []

    @pytest.mark.requirement("REQ-041")
    def test_connect_returns_catalog(self) -> None:
        """Test connect returns MockCatalog instance."""
        plugin = MockCatalogPlugin()
        catalog = plugin.connect({})
        assert isinstance(catalog, MockCatalog)

    @pytest.mark.requirement("REQ-041")
    def test_operations_before_connect_fail(self) -> None:
        """Test operations before connect raise RuntimeError."""
        plugin = MockCatalogPlugin()
        with pytest.raises(RuntimeError, match="not connected"):
            plugin.create_namespace("test")
        with pytest.raises(RuntimeError, match="not connected"):
            plugin.list_namespaces()
        with pytest.raises(RuntimeError, match="not connected"):
            plugin.delete_namespace("test")

    @pytest.mark.requirement("REQ-041")
    def test_namespace_operations(self) -> None:
        """Test namespace CRUD operations."""
        plugin = MockCatalogPlugin()
        plugin.connect({})

        # Create
        plugin.create_namespace("test")
        assert "test" in plugin.list_namespaces()

        # List with parent
        plugin.create_namespace("test.child")
        namespaces = plugin.list_namespaces(parent="test")
        assert any("child" in ns for ns in namespaces)

        # Delete
        plugin.delete_namespace("test.child")
        plugin.delete_namespace("test")
        assert "test" not in plugin.list_namespaces()

    @pytest.mark.requirement("REQ-041")
    def test_table_operations(self) -> None:
        """Test table CRUD operations."""
        plugin = MockCatalogPlugin()
        plugin.connect({})
        plugin.create_namespace("test")

        schema: dict[str, Any] = {"type": "struct", "fields": []}

        # Create
        plugin.create_table("test.table1", schema)
        tables = plugin.list_tables("test")
        assert "test.table1" in tables

        # Drop
        plugin.drop_table("test.table1")
        assert plugin.list_tables("test") == []

    @pytest.mark.requirement("REQ-041")
    def test_vend_credentials(self) -> None:
        """Test credential vending returns mock credentials."""
        plugin = MockCatalogPlugin()
        plugin.connect({})
        plugin.create_namespace("test")
        plugin.create_table("test.table1", {})

        creds = plugin.vend_credentials("test.table1", ["READ"])
        assert creds["access_key"] == "MOCK_ACCESS_KEY"
        assert creds["secret_key"] == "MOCK_SECRET_KEY"
        assert creds["token"] == "MOCK_SESSION_TOKEN"
        assert "expiration" in creds

    @pytest.mark.requirement("REQ-041")
    def test_health_check(self) -> None:
        """Test health check returns status."""
        plugin = MockCatalogPlugin()

        # Not connected
        status = plugin.health_check()
        assert status["state"] == "unhealthy"

        # Connected
        plugin.connect({})
        status = plugin.health_check()
        assert status["state"] == "healthy"


class TestCatalogFixtureHelpers:
    """Tests for catalog fixture helper functions."""

    @pytest.mark.requirement("REQ-041")
    def test_create_mock_catalog_plugin(self) -> None:
        """Test create_mock_catalog_plugin factory function."""
        plugin = create_mock_catalog_plugin()
        assert isinstance(plugin, MockCatalogPlugin)

    @pytest.mark.requirement("REQ-041")
    def test_create_mock_catalog_plugin_with_config(self) -> None:
        """Test create_mock_catalog_plugin with custom config."""
        config = CatalogTestConfig(namespace_prefix="custom")
        plugin = create_mock_catalog_plugin(config)
        assert plugin._config.namespace_prefix == "custom"

    @pytest.mark.requirement("REQ-041")
    def test_mock_catalog_plugin_context(self) -> None:
        """Test mock_catalog_plugin_context context manager."""
        with mock_catalog_plugin_context() as plugin:
            assert isinstance(plugin, MockCatalogPlugin)
            # Should be connected automatically
            plugin.create_namespace("test")
            assert "test" in plugin.list_namespaces()

    @pytest.mark.requirement("REQ-041")
    def test_generate_unique_namespace(self) -> None:
        """Test generate_unique_namespace creates unique names."""
        ns1 = generate_unique_namespace("test")
        ns2 = generate_unique_namespace("test")

        assert ns1.startswith("test_")
        assert ns2.startswith("test_")
        assert ns1 != ns2

    @pytest.mark.requirement("REQ-041")
    def test_generate_unique_namespace_custom_prefix(self) -> None:
        """Test generate_unique_namespace with custom prefix."""
        ns = generate_unique_namespace("custom")
        assert ns.startswith("custom_")
        assert len(ns) == len("custom_") + 8  # prefix + 8 char UUID suffix

    @pytest.mark.requirement("REQ-041")
    def test_get_catalog_connection_info(self) -> None:
        """Test get_catalog_connection_info masks credentials."""
        config = CatalogTestConfig()
        info = get_catalog_connection_info(config)

        assert info["catalog_type"] == "mock"
        assert info["uri"] == config.uri
        assert info["warehouse"] == config.warehouse
        assert "credential" not in info  # Should be masked
        assert "secret" not in str(info)  # Double-check


class TestCatalogConnectionError:
    """Tests for CatalogConnectionError exception."""

    @pytest.mark.requirement("REQ-041")
    def test_exception_message(self) -> None:
        """Test exception can be raised with message."""
        with pytest.raises(CatalogConnectionError, match="test error"):
            raise CatalogConnectionError("test error")

    @pytest.mark.requirement("REQ-041")
    def test_exception_chaining(self) -> None:
        """Test exception can be chained with cause."""
        try:
            try:
                raise ValueError("original error")
            except ValueError as e:
                raise CatalogConnectionError("wrapped error") from e
        except CatalogConnectionError as e:
            assert str(e) == "wrapped error"
            assert isinstance(e.__cause__, ValueError)
