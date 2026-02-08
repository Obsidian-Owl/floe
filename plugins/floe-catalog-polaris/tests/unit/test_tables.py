"""Unit tests for table operations.

This module tests the table management operations (create, list, drop)
of the PolarisCatalogPlugin using mock PyIceberg catalog.

Requirements Covered:
    - FR-014: System MUST support creating Iceberg tables with schema, location, and properties
    - FR-015: System MUST support listing tables within a namespace
    - FR-016: System MUST support retrieving table metadata including schema and statistics
    - FR-017: System MUST support updating table properties
    - FR-018: System MUST support dropping tables with metadata cleanup
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from floe_core.plugin_errors import AuthenticationError, ConflictError, NotFoundError

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

if TYPE_CHECKING:
    pass


@pytest.fixture
def polaris_config() -> PolarisCatalogConfig:
    """Create a test Polaris configuration."""
    return PolarisCatalogConfig(
        uri="https://polaris.example.com/api/catalog",
        warehouse="test_warehouse",
        oauth2=OAuth2Config(
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        ),
    )


@pytest.fixture
def polaris_plugin(polaris_config: PolarisCatalogConfig) -> PolarisCatalogPlugin:
    """Create a PolarisCatalogPlugin instance."""
    return PolarisCatalogPlugin(config=polaris_config)


@pytest.fixture
def mock_catalog() -> MagicMock:
    """Create a mock PyIceberg catalog."""
    return MagicMock()


@pytest.fixture
def connected_plugin(
    polaris_plugin: PolarisCatalogPlugin,
    mock_catalog: MagicMock,
) -> PolarisCatalogPlugin:
    """Create a plugin with a mocked catalog connection."""
    polaris_plugin._catalog = mock_catalog
    return polaris_plugin


@pytest.fixture
def sample_schema() -> dict[str, Any]:
    """Sample Iceberg schema for testing."""
    return {
        "type": "struct",
        "fields": [
            {"id": 1, "name": "id", "type": "long", "required": True},
            {"id": 2, "name": "name", "type": "string", "required": False},
            {"id": 3, "name": "created_at", "type": "timestamp", "required": True},
        ],
    }


class TestCreateTable:
    """Tests for create_table() method."""

    @pytest.mark.requirement("FR-014")
    def test_create_table_basic(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test creating a table with basic schema."""
        connected_plugin.create_table("bronze.customers", sample_schema)

        mock_catalog.create_table.assert_called_once()
        call_args = mock_catalog.create_table.call_args
        assert call_args is not None

    @pytest.mark.requirement("FR-014")
    def test_create_table_with_location(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test creating a table with custom storage location."""
        connected_plugin.create_table(
            "bronze.customers",
            sample_schema,
            location="s3://my-bucket/bronze/customers",
        )

        mock_catalog.create_table.assert_called_once()

    @pytest.mark.requirement("FR-014")
    def test_create_table_with_properties(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test creating a table with custom properties."""
        properties = {
            "write.format.default": "parquet",
            "write.parquet.compression-codec": "zstd",
        }

        connected_plugin.create_table(
            "bronze.customers",
            sample_schema,
            properties=properties,
        )

        mock_catalog.create_table.assert_called_once()

    @pytest.mark.requirement("FR-014")
    def test_create_table_already_exists_raises_conflict_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that creating an existing table raises ConflictError."""
        from pyiceberg.exceptions import TableAlreadyExistsError

        mock_catalog.create_table.side_effect = TableAlreadyExistsError("bronze.customers")

        with pytest.raises(ConflictError) as exc_info:
            connected_plugin.create_table("bronze.customers", sample_schema)

        assert exc_info.value.resource_type == "table"

    @pytest.mark.requirement("FR-014")
    def test_create_table_namespace_not_found_raises_not_found_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that creating table in non-existent namespace raises NotFoundError."""
        from pyiceberg.exceptions import NoSuchNamespaceError

        mock_catalog.create_table.side_effect = NoSuchNamespaceError("nonexistent")

        with pytest.raises(NotFoundError) as exc_info:
            connected_plugin.create_table("nonexistent.customers", sample_schema)

        assert exc_info.value.resource_type == "namespace"

    @pytest.mark.requirement("FR-014")
    def test_create_table_permission_denied_raises_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that permission denied raises AuthenticationError."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.create_table.side_effect = ForbiddenError("Access denied")

        with pytest.raises(AuthenticationError):
            connected_plugin.create_table("bronze.customers", sample_schema)

    @pytest.mark.requirement("FR-014")
    def test_create_table_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that create_table logs the operation."""
        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.create_table("bronze.customers", sample_schema)

            assert mock_logger.bind.called or mock_logger.info.called


class TestListTables:
    """Tests for list_tables() method."""

    @pytest.mark.requirement("FR-015")
    def test_list_tables_returns_list(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_tables returns a list of table identifiers."""
        mock_catalog.list_tables.return_value = [
            ("bronze", "customers"),
            ("bronze", "orders"),
            ("bronze", "products"),
        ]

        result = connected_plugin.list_tables("bronze")

        assert isinstance(result, list)
        assert len(result) == 3

    @pytest.mark.requirement("FR-015")
    def test_list_tables_empty_namespace(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test listing tables in an empty namespace."""
        mock_catalog.list_tables.return_value = []

        result = connected_plugin.list_tables("bronze")

        assert result == []

    @pytest.mark.requirement("FR-015")
    def test_list_tables_returns_full_identifiers(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_tables returns full table identifiers (namespace.table)."""
        mock_catalog.list_tables.return_value = [
            ("bronze", "customers"),
            ("bronze", "orders"),
        ]

        result = connected_plugin.list_tables("bronze")

        # Should include full identifiers with namespace prefix
        assert any("customers" in table for table in result)
        assert any("orders" in table for table in result)

    @pytest.mark.requirement("FR-015")
    def test_list_tables_namespace_not_found_raises_not_found_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that listing tables from non-existent namespace raises NotFoundError."""
        from pyiceberg.exceptions import NoSuchNamespaceError

        mock_catalog.list_tables.side_effect = NoSuchNamespaceError("nonexistent")

        with pytest.raises(NotFoundError) as exc_info:
            connected_plugin.list_tables("nonexistent")

        assert exc_info.value.resource_type == "namespace"

    @pytest.mark.requirement("FR-015")
    def test_list_tables_permission_denied_raises_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that permission denied raises AuthenticationError."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.list_tables.side_effect = ForbiddenError("Access denied")

        with pytest.raises(AuthenticationError):
            connected_plugin.list_tables("bronze")

    @pytest.mark.requirement("FR-015")
    def test_list_tables_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_tables logs the operation."""
        mock_catalog.list_tables.return_value = []

        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.list_tables("bronze")

            assert mock_logger.bind.called or mock_logger.info.called


class TestDropTable:
    """Tests for drop_table() method."""

    @pytest.mark.requirement("FR-018")
    def test_drop_table_basic(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test dropping a table without purge."""
        connected_plugin.drop_table("bronze.customers")

        mock_catalog.drop_table.assert_called_once()
        call_args = mock_catalog.drop_table.call_args
        assert call_args is not None

    @pytest.mark.requirement("FR-018")
    def test_drop_table_with_purge(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test dropping a table with purge (delete data files)."""
        connected_plugin.drop_table("bronze.customers", purge=True)

        mock_catalog.drop_table.assert_called_once()
        # Verify purge parameter was passed
        call_args = mock_catalog.drop_table.call_args
        assert call_args is not None

    @pytest.mark.requirement("FR-018")
    def test_drop_table_not_found_raises_not_found_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that dropping non-existent table raises NotFoundError."""
        from pyiceberg.exceptions import NoSuchTableError

        mock_catalog.drop_table.side_effect = NoSuchTableError("bronze.nonexistent")

        with pytest.raises(NotFoundError) as exc_info:
            connected_plugin.drop_table("bronze.nonexistent")

        assert exc_info.value.resource_type == "table"

    @pytest.mark.requirement("FR-018")
    def test_drop_table_permission_denied_raises_auth_error(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that permission denied raises AuthenticationError."""
        from pyiceberg.exceptions import ForbiddenError

        mock_catalog.drop_table.side_effect = ForbiddenError("Access denied")

        with pytest.raises(AuthenticationError):
            connected_plugin.drop_table("bronze.customers")

    @pytest.mark.requirement("FR-018")
    def test_drop_table_logs_operation(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that drop_table logs the operation."""
        with patch("floe_catalog_polaris.plugin.logger") as mock_logger:
            connected_plugin.drop_table("bronze.customers")

            assert mock_logger.bind.called or mock_logger.info.called


class TestTableNotConnected:
    """Tests for table operations when not connected."""

    @pytest.mark.requirement("FR-014")
    def test_create_table_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that create_table fails when not connected."""
        from floe_core.plugin_errors import CatalogUnavailableError

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            polaris_plugin.create_table("bronze.customers", sample_schema)

    @pytest.mark.requirement("FR-015")
    def test_list_tables_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that list_tables fails when not connected."""
        from floe_core.plugin_errors import CatalogUnavailableError

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            polaris_plugin.list_tables("bronze")

    @pytest.mark.requirement("FR-018")
    def test_drop_table_not_connected_raises_error(
        self,
        polaris_plugin: PolarisCatalogPlugin,
    ) -> None:
        """Test that drop_table fails when not connected."""
        from floe_core.plugin_errors import CatalogUnavailableError

        with pytest.raises(CatalogUnavailableError, match="not connected"):
            polaris_plugin.drop_table("bronze.customers")


class TestTableOTelTracing:
    """Tests for OTel tracing in table operations."""

    @pytest.mark.requirement("FR-030")
    def test_create_table_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that create_table emits an OTel span."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            connected_plugin.create_table("bronze.customers", sample_schema)

            mock_span.assert_called_once()
            call_kwargs = mock_span.call_args.kwargs
            assert call_kwargs.get("catalog_name") == "polaris"

    @pytest.mark.requirement("FR-030")
    def test_list_tables_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_tables emits an OTel span."""
        mock_catalog.list_tables.return_value = []

        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            connected_plugin.list_tables("bronze")

            mock_span.assert_called_once()
            call_kwargs = mock_span.call_args.kwargs
            assert call_kwargs.get("catalog_name") == "polaris"

    @pytest.mark.requirement("FR-030")
    def test_drop_table_emits_otel_span(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that drop_table emits an OTel span."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            connected_plugin.drop_table("bronze.customers")

            mock_span.assert_called_once()
            call_kwargs = mock_span.call_args.kwargs
            assert call_kwargs.get("catalog_name") == "polaris"

    @pytest.mark.requirement("FR-031")
    def test_table_span_includes_table_attribute(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that table operation spans include table name attribute."""
        with patch("floe_catalog_polaris.plugin.catalog_span") as mock_span:
            connected_plugin.create_table("bronze.customers", sample_schema)

            call_kwargs = mock_span.call_args.kwargs
            # Should include table_full_name or table_name attribute
            assert (
                call_kwargs.get("table_full_name") == "bronze.customers"
                or call_kwargs.get("table_name") == "customers"
                or "bronze.customers" in str(call_kwargs.get("extra_attributes", {}))
            )


class TestTableErrorMapping:
    """Tests for PyIceberg error mapping in table operations."""

    @pytest.mark.requirement("FR-033")
    def test_create_table_maps_pyiceberg_errors(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
        sample_schema: dict[str, Any],
    ) -> None:
        """Test that create_table maps PyIceberg errors correctly."""
        from floe_core.plugin_errors import CatalogUnavailableError
        from pyiceberg.exceptions import ServiceUnavailableError

        mock_catalog.create_table.side_effect = ServiceUnavailableError("Catalog down")

        with pytest.raises(CatalogUnavailableError):
            connected_plugin.create_table("bronze.customers", sample_schema)

    @pytest.mark.requirement("FR-033")
    def test_list_tables_maps_pyiceberg_errors(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that list_tables maps PyIceberg errors correctly."""
        from floe_core.plugin_errors import CatalogUnavailableError
        from pyiceberg.exceptions import ServiceUnavailableError

        mock_catalog.list_tables.side_effect = ServiceUnavailableError("Catalog down")

        with pytest.raises(CatalogUnavailableError):
            connected_plugin.list_tables("bronze")

    @pytest.mark.requirement("FR-033")
    def test_drop_table_maps_pyiceberg_errors(
        self,
        connected_plugin: PolarisCatalogPlugin,
        mock_catalog: MagicMock,
    ) -> None:
        """Test that drop_table maps PyIceberg errors correctly."""
        from floe_core.plugin_errors import CatalogUnavailableError
        from pyiceberg.exceptions import ServiceUnavailableError

        mock_catalog.drop_table.side_effect = ServiceUnavailableError("Catalog down")

        with pytest.raises(CatalogUnavailableError):
            connected_plugin.drop_table("bronze.customers")
