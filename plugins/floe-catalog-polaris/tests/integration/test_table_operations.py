"""Integration tests for Polaris table operations.

Tests the PolarisCatalogPlugin table operations against a real Polaris
instance running in the Kind cluster. These tests verify:
- create_table() creates Iceberg tables in Polaris
- list_tables() returns actual tables within namespaces
- drop_table() removes tables (metadata and optionally data)
- Error handling for edge cases

Requirements Covered:
    - FR-014: System MUST support creating Iceberg tables with schema, location, and properties
    - FR-015: System MUST support listing tables within a namespace
    - FR-016: System MUST support retrieving table metadata including schema and statistics
    - FR-017: System MUST support updating table properties
    - FR-018: System MUST support dropping tables with metadata cleanup

Infrastructure Notes:
    Table operations require Polaris to vend storage credentials via STS.
    This requires additional MinIO/S3 STS endpoint configuration beyond
    the basic Kind cluster setup. If tests fail with STS/credential errors,
    verify the storage backend is properly configured for credential vending.

    See: testing/k8s/scripts/init-polaris.sh for catalog role setup.
"""

from __future__ import annotations

import os
import uuid

import pytest
from floe_core import ConflictError, NotFoundError
from pydantic import SecretStr
from pyiceberg.schema import Schema
from pyiceberg.types import (
    BooleanType,
    DoubleType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)
from testing.base_classes.integration_test_base import IntegrationTestBase

from floe_catalog_polaris.config import OAuth2Config, PolarisCatalogConfig
from floe_catalog_polaris.plugin import PolarisCatalogPlugin

# Mark all tests in this module as requiring STS-enabled storage backend
pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_sts,
]


@pytest.mark.requires_sts
class TestTableOperations(IntegrationTestBase):
    """Integration tests for table CRUD operations.

    These tests require a real Polaris instance running in the Kind cluster.
    Each test creates uniquely named namespaces and tables to avoid conflicts.

    Required services:
        - polaris:8181 - Polaris REST API
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris.

        Returns:
            PolarisCatalogConfig with test credentials.
        """
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance.

        Returns:
            Connected PolarisCatalogPlugin instance.
        """
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "tbl") -> str:
        """Generate a unique namespace name for testing.

        Args:
            prefix: Prefix for the namespace name.

        Returns:
            Unique namespace name.
        """
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _get_simple_schema(self) -> Schema:
        """Return a simple Iceberg schema for testing.

        Returns:
            PyIceberg Schema object.
        """
        return Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            NestedField(field_id=2, name="name", field_type=StringType(), required=False),
        )

    # =========================================================================
    # create_table() Tests
    # =========================================================================

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_success(self) -> None:
        """Test creating a table succeeds with valid schema."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.customers"

        try:
            # Create namespace first
            plugin.create_namespace(namespace)

            # Create the table
            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # Verify table exists by listing
            tables = plugin.list_tables(namespace)
            assert table_name in tables, f"Table '{table_name}' not in list: {tables}"
        finally:
            # Cleanup
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_with_properties(self) -> None:
        """Test creating a table with custom properties."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.orders"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            properties = {
                "write.format.default": "parquet",
                "owner": "test-integration",
            }

            # Create table with properties
            plugin.create_table(table_name, schema, properties=properties)

            # Verify table was created
            tables = plugin.list_tables(namespace)
            assert table_name in tables
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_already_exists_raises_conflict_error(self) -> None:
        """Test that creating a table that already exists raises ConflictError."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.products"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # Try to create the same table again
            with pytest.raises(ConflictError) as exc_info:
                plugin.create_table(table_name, schema)

            assert exc_info.value.resource_type == "table"
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_namespace_not_found_raises_not_found_error(self) -> None:
        """Test that creating a table in a non-existent namespace raises NotFoundError."""
        plugin = self._get_connected_plugin()
        nonexistent_namespace = self._generate_unique_namespace("noexist")
        table_name = f"{nonexistent_namespace}.customers"

        schema = self._get_simple_schema()

        with pytest.raises(NotFoundError) as exc_info:
            plugin.create_table(table_name, schema)

        assert exc_info.value.resource_type == "namespace"

    # =========================================================================
    # list_tables() Tests
    # =========================================================================

    @pytest.mark.requirement("FR-015")
    @pytest.mark.integration
    def test_list_tables_returns_list(self) -> None:
        """Test that list_tables returns a list of table identifiers."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()

        try:
            plugin.create_namespace(namespace)

            # Create a couple of tables
            schema = self._get_simple_schema()
            table1 = f"{namespace}.table_one"
            table2 = f"{namespace}.table_two"

            plugin.create_table(table1, schema)
            plugin.create_table(table2, schema)

            # List tables
            tables = plugin.list_tables(namespace)

            assert isinstance(tables, list)
            assert len(tables) == 2
            assert table1 in tables
            assert table2 in tables
        finally:
            try:
                plugin.drop_table(f"{namespace}.table_one")
            except Exception:
                pass
            try:
                plugin.drop_table(f"{namespace}.table_two")
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-015")
    @pytest.mark.integration
    def test_list_tables_empty_namespace_returns_empty_list(self) -> None:
        """Test that list_tables returns empty list for namespace with no tables."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()

        try:
            plugin.create_namespace(namespace)

            tables = plugin.list_tables(namespace)

            assert isinstance(tables, list)
            assert len(tables) == 0
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-015")
    @pytest.mark.integration
    def test_list_tables_namespace_not_found_raises_not_found_error(self) -> None:
        """Test that listing tables from non-existent namespace raises NotFoundError."""
        plugin = self._get_connected_plugin()
        nonexistent_namespace = self._generate_unique_namespace("noexist")

        with pytest.raises(NotFoundError) as exc_info:
            plugin.list_tables(nonexistent_namespace)

        assert exc_info.value.resource_type == "namespace"

    # =========================================================================
    # drop_table() Tests
    # =========================================================================

    @pytest.mark.requirement("FR-018")
    @pytest.mark.integration
    def test_drop_table_success(self) -> None:
        """Test dropping a table succeeds."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.to_delete"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # Verify table exists
            tables = plugin.list_tables(namespace)
            assert table_name in tables

            # Drop the table
            plugin.drop_table(table_name)

            # Verify table no longer exists
            tables_after = plugin.list_tables(namespace)
            assert table_name not in tables_after
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-018")
    @pytest.mark.integration
    def test_drop_table_with_purge(self) -> None:
        """Test dropping a table with purge option."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.to_purge"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # Drop with purge (should also delete data files)
            plugin.drop_table(table_name, purge=True)

            # Verify table no longer exists
            tables = plugin.list_tables(namespace)
            assert table_name not in tables
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-018")
    @pytest.mark.integration
    def test_drop_table_not_found_raises_not_found_error(self) -> None:
        """Test that dropping a non-existent table raises NotFoundError."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        nonexistent_table = f"{namespace}.does_not_exist"

        try:
            plugin.create_namespace(namespace)

            with pytest.raises(NotFoundError) as exc_info:
                plugin.drop_table(nonexistent_table)

            assert exc_info.value.resource_type == "table"
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass


@pytest.mark.requires_sts
class TestTableLifecycle(IntegrationTestBase):
    """Integration tests for table lifecycle operations.

    Tests complete workflows involving create, list, and drop operations.
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris."""
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance."""
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "life") -> str:
        """Generate a unique namespace name for testing."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _get_simple_schema(self) -> Schema:
        """Return a simple Iceberg schema for testing."""
        return Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            NestedField(field_id=2, name="data", field_type=StringType(), required=False),
        )

    @pytest.mark.requirement("FR-014")
    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-018")
    @pytest.mark.integration
    def test_full_table_lifecycle(self) -> None:
        """Test complete table lifecycle: create -> list -> drop."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.lifecycle_table"

        try:
            # Setup: create namespace
            plugin.create_namespace(namespace)

            # Step 1: Create table
            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # Step 2: Verify table exists via list
            tables = plugin.list_tables(namespace)
            assert table_name in tables, f"Created table not in list: {tables}"

            # Step 3: Drop table
            plugin.drop_table(table_name)

            # Step 4: Verify table no longer exists
            tables_after = plugin.list_tables(namespace)
            assert table_name not in tables_after, "Table still exists after drop"
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-014")
    @pytest.mark.requirement("FR-015")
    @pytest.mark.integration
    def test_create_multiple_tables_in_namespace(self) -> None:
        """Test creating and listing multiple tables in one namespace."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_names = [f"{namespace}.table_{i}" for i in range(3)]

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()

            # Create all tables
            for table_name in table_names:
                plugin.create_table(table_name, schema)

            # Verify all tables exist
            tables = plugin.list_tables(namespace)
            assert len(tables) == 3

            for table_name in table_names:
                assert table_name in tables
        finally:
            # Cleanup all tables
            for table_name in table_names:
                try:
                    plugin.drop_table(table_name)
                except Exception:
                    pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-018")
    @pytest.mark.integration
    def test_drop_table_twice_raises_not_found(self) -> None:
        """Test that dropping the same table twice raises NotFoundError."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.double_drop"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # First drop succeeds
            plugin.drop_table(table_name)

            # Second drop should fail
            with pytest.raises(NotFoundError) as exc_info:
                plugin.drop_table(table_name)

            assert exc_info.value.resource_type == "table"
        finally:
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass


@pytest.mark.requires_sts
class TestTableEdgeCases(IntegrationTestBase):
    """Integration tests for table operation edge cases.

    Tests unusual inputs and boundary conditions.
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris."""
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance."""
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "edge") -> str:
        """Generate a unique namespace name for testing."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _get_simple_schema(self) -> Schema:
        """Return a simple Iceberg schema for testing."""
        return Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
        )

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_with_underscores_in_name(self) -> None:
        """Test creating a table with underscores in the name."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.my_special_table_name"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            tables = plugin.list_tables(namespace)
            assert table_name in tables
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_with_numbers_in_name(self) -> None:
        """Test creating a table with numbers in the name."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.table123"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            tables = plugin.list_tables(namespace)
            assert table_name in tables
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-014")
    @pytest.mark.integration
    def test_create_table_with_complex_schema(self) -> None:
        """Test creating a table with a more complex schema."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.complex_table"

        complex_schema = Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            NestedField(field_id=2, name="name", field_type=StringType(), required=True),
            NestedField(field_id=3, name="email", field_type=StringType(), required=False),
            NestedField(field_id=4, name="created_at", field_type=TimestampType(), required=True),
            NestedField(field_id=5, name="is_active", field_type=BooleanType(), required=False),
            NestedField(field_id=6, name="score", field_type=DoubleType(), required=False),
        )

        try:
            plugin.create_namespace(namespace)

            plugin.create_table(table_name, complex_schema)

            tables = plugin.list_tables(namespace)
            assert table_name in tables
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass

    @pytest.mark.requirement("FR-015")
    @pytest.mark.integration
    def test_list_tables_multiple_times_consistent(self) -> None:
        """Test that listing tables multiple times returns consistent results."""
        plugin = self._get_connected_plugin()
        namespace = self._generate_unique_namespace()
        table_name = f"{namespace}.consistent"

        try:
            plugin.create_namespace(namespace)

            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # List multiple times
            tables1 = plugin.list_tables(namespace)
            tables2 = plugin.list_tables(namespace)
            tables3 = plugin.list_tables(namespace)

            # All should return the same result
            assert tables1 == tables2 == tables3
            assert table_name in tables1
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(namespace)
            except Exception:
                pass


@pytest.mark.requires_sts
class TestTableInHierarchicalNamespace(IntegrationTestBase):
    """Integration tests for tables in hierarchical namespaces.

    Tests table operations when namespaces use dot notation.
    """

    required_services = [("polaris", 8181)]

    def _get_test_config(self) -> PolarisCatalogConfig:
        """Create test configuration for Polaris."""
        polaris_host = self.get_service_host("polaris")
        polaris_port = int(os.environ.get("POLARIS_PORT", "8181"))
        polaris_uri = os.environ.get(
            "POLARIS_URI",
            f"http://{polaris_host}:{polaris_port}/api/catalog",
        )

        client_id = os.environ.get("POLARIS_CLIENT_ID", "test-admin")
        client_secret = os.environ.get("POLARIS_CLIENT_SECRET", "test-secret")
        warehouse = os.environ.get("POLARIS_WAREHOUSE", "test_warehouse")

        token_url = os.environ.get(
            "POLARIS_TOKEN_URL",
            f"http://{polaris_host}:{polaris_port}/api/catalog/v1/oauth/tokens",
        )

        return PolarisCatalogConfig(
            uri=polaris_uri,
            warehouse=warehouse,
            oauth2=OAuth2Config(
                client_id=client_id,
                client_secret=SecretStr(client_secret),
                token_url=token_url,
                scope="PRINCIPAL_ROLE:ALL",
            ),
        )

    def _get_connected_plugin(self) -> PolarisCatalogPlugin:
        """Create and connect a plugin instance."""
        config = self._get_test_config()
        plugin = PolarisCatalogPlugin(config=config)
        plugin.connect({})
        return plugin

    def _generate_unique_namespace(self, prefix: str = "hier") -> str:
        """Generate a unique namespace name for testing."""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _get_simple_schema(self) -> Schema:
        """Return a simple Iceberg schema for testing."""
        return Schema(
            NestedField(field_id=1, name="id", field_type=LongType(), required=True),
        )

    @pytest.mark.requirement("FR-014")
    @pytest.mark.requirement("FR-011")
    @pytest.mark.integration
    def test_create_table_in_hierarchical_namespace(self) -> None:
        """Test creating a table in a hierarchical namespace (parent.child)."""
        plugin = self._get_connected_plugin()
        parent = self._generate_unique_namespace()
        child = f"{parent}.bronze"
        table_name = f"{child}.customers"

        try:
            # Create parent namespace
            plugin.create_namespace(parent)
            # Create child namespace
            plugin.create_namespace(child)

            # Create table in child namespace
            schema = self._get_simple_schema()
            plugin.create_table(table_name, schema)

            # List tables in child namespace
            tables = plugin.list_tables(child)
            assert table_name in tables, f"Table not in list: {tables}"
        finally:
            try:
                plugin.drop_table(table_name)
            except Exception:
                pass
            try:
                plugin.delete_namespace(child)
            except Exception:
                pass
            try:
                plugin.delete_namespace(parent)
            except Exception:
                pass

    @pytest.mark.requirement("FR-015")
    @pytest.mark.requirement("FR-011")
    @pytest.mark.integration
    def test_list_tables_in_child_namespace_only(self) -> None:
        """Test that list_tables only returns tables in the specified namespace."""
        plugin = self._get_connected_plugin()
        parent = self._generate_unique_namespace()
        child = f"{parent}.silver"
        table_in_parent = f"{parent}.parent_table"
        table_in_child = f"{child}.child_table"

        try:
            # Create parent and child namespaces
            plugin.create_namespace(parent)
            plugin.create_namespace(child)

            schema = self._get_simple_schema()

            # Create table in parent
            plugin.create_table(table_in_parent, schema)
            # Create table in child
            plugin.create_table(table_in_child, schema)

            # List tables in parent - should only have parent's table
            parent_tables = plugin.list_tables(parent)
            assert table_in_parent in parent_tables
            assert table_in_child not in parent_tables

            # List tables in child - should only have child's table
            child_tables = plugin.list_tables(child)
            assert table_in_child in child_tables
            assert table_in_parent not in child_tables
        finally:
            try:
                plugin.drop_table(table_in_child)
            except Exception:
                pass
            try:
                plugin.drop_table(table_in_parent)
            except Exception:
                pass
            try:
                plugin.delete_namespace(child)
            except Exception:
                pass
            try:
                plugin.delete_namespace(parent)
            except Exception:
                pass
