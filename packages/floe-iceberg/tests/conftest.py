"""Shared test fixtures for floe-iceberg package.

This module provides pytest fixtures used across unit and integration tests.
It includes mock implementations of CatalogPlugin and StoragePlugin for
unit testing IcebergTableManager without external dependencies.

Note:
    No __init__.py files in test directories - pytest uses importlib mode
    which causes namespace collisions with __init__.py files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


# =============================================================================
# Mock Catalog Protocol Implementation
# =============================================================================


class MockCatalog:
    """Mock implementation of PyIceberg Catalog protocol.

    Provides minimal interface for testing IcebergTableManager without
    requiring a real catalog connection.

    Attributes:
        namespaces: List of existing namespaces.
        tables: Dictionary mapping namespace to table names.
        loaded_tables: Dictionary of loaded table objects.
        _parent_plugin: Reference to parent MockCatalogPlugin for table info.
    """

    def __init__(self, parent_plugin: MockCatalogPlugin | None = None) -> None:
        """Initialize mock catalog with empty collections.

        Args:
            parent_plugin: Optional reference to parent MockCatalogPlugin.
        """
        self.namespaces: list[tuple[str, ...]] = []
        self.tables: dict[str, list[str]] = {}
        self.loaded_tables: dict[str, MagicMock] = {}
        self._parent_plugin = parent_plugin

    def list_namespaces(self) -> list[tuple[str, ...]]:
        """List all namespaces in the catalog."""
        return self.namespaces

    def list_tables(self, namespace: str) -> list[str]:
        """List all tables in a namespace."""
        return self.tables.get(namespace, [])

    def load_table(self, identifier: str) -> MagicMock:
        """Load a table by identifier.

        Args:
            identifier: Full table identifier (e.g., "namespace.table").

        Returns:
            Mock table object with standard Iceberg table interface.
        """
        if identifier not in self.loaded_tables:
            # Get table info from parent plugin if available
            table_info: dict[str, Any] = {}
            if self._parent_plugin and identifier in self._parent_plugin._tables:
                table_info = self._parent_plugin._tables[identifier]

            # Create a mock table with common attributes
            mock_table = MagicMock()
            mock_table.identifier = identifier
            mock_table.metadata_location = (
                f"s3://warehouse/{identifier}/metadata/v1.metadata.json"
            )

            # Create a proper mock schema with fields
            mock_schema = MagicMock()
            schema_info = table_info.get("schema", {})

            # Build mock fields from schema info
            mock_fields = []
            for field_dict in schema_info.get("fields", []):
                mock_field = MagicMock()
                mock_field.name = field_dict.get("name", "")
                mock_field.field_id = field_dict.get("field_id", 0)
                mock_field.required = field_dict.get("required", False)
                mock_fields.append(mock_field)

            mock_schema.fields = mock_fields
            mock_table.schema.return_value = mock_schema

            mock_table.current_snapshot.return_value = None
            # Store table data for testing (schema, snapshots, etc.)
            mock_table._table_data = {
                "schema": schema_info,
                "snapshots": [],
                "properties": table_info.get("properties", {}),
            }
            self.loaded_tables[identifier] = mock_table
        return self.loaded_tables[identifier]


# =============================================================================
# Mock FileIO Protocol Implementation
# =============================================================================


class MockFileIO:
    """Mock implementation of PyIceberg FileIO protocol.

    Provides minimal interface for testing without real storage operations.
    """

    def __init__(self) -> None:
        """Initialize mock FileIO."""
        self.written_files: dict[str, bytes] = {}
        self.deleted_files: list[str] = []

    def new_input(self, location: str) -> MagicMock:
        """Create a new input file for reading.

        Args:
            location: Storage location URI.

        Returns:
            Mock input file object.
        """
        mock_input = MagicMock()
        mock_input.location = location
        return mock_input

    def new_output(self, location: str) -> MagicMock:
        """Create a new output file for writing.

        Args:
            location: Storage location URI.

        Returns:
            Mock output file object.
        """
        mock_output = MagicMock()
        mock_output.location = location
        return mock_output

    def delete(self, location: str) -> None:
        """Delete a file at the specified location.

        Args:
            location: Storage location URI to delete.
        """
        self.deleted_files.append(location)


# =============================================================================
# Mock CatalogPlugin Fixture
# =============================================================================


class MockCatalogPlugin:
    """Mock implementation of CatalogPlugin for unit testing.

    Implements all abstract methods from CatalogPlugin ABC without
    requiring real catalog connectivity.

    Attributes:
        _catalog: Internal MockCatalog instance.
        _connected: Whether connect() has been called.
        connect_config: Configuration passed to connect().
    """

    def __init__(self) -> None:
        """Initialize mock catalog plugin."""
        self._catalog = MockCatalog(parent_plugin=self)
        self._connected = False
        self.connect_config: dict[str, Any] | None = None
        self._namespaces: dict[str, dict[str, str]] = {}
        self._tables: dict[str, dict[str, Any]] = {}

    # PluginMetadata properties
    @property
    def name(self) -> str:
        """Plugin name."""
        return "mock-catalog"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Floe API version compatibility."""
        return "1.0"

    # CatalogPlugin methods
    def connect(self, config: dict[str, Any]) -> MockCatalog:
        """Connect to the mock catalog.

        Args:
            config: Connection configuration (stored for inspection).

        Returns:
            MockCatalog instance.
        """
        self.connect_config = config
        self._connected = True
        return self._catalog

    def create_namespace(
        self,
        namespace: str,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new namespace.

        Args:
            namespace: Namespace name to create.
            properties: Optional namespace properties.
        """
        self._namespaces[namespace] = properties or {}
        self._catalog.namespaces.append((namespace,))
        self._catalog.tables[namespace] = []

    def list_namespaces(self, parent: str | None = None) -> list[str]:
        """List namespaces.

        Args:
            parent: Optional parent namespace filter.

        Returns:
            List of namespace names.
        """
        if parent:
            return [ns for ns in self._namespaces if ns.startswith(f"{parent}.")]
        return list(self._namespaces.keys())

    def delete_namespace(self, namespace: str) -> None:
        """Delete a namespace.

        Args:
            namespace: Namespace name to delete.
        """
        if namespace in self._namespaces:
            del self._namespaces[namespace]
            self._catalog.namespaces = [
                ns for ns in self._catalog.namespaces if ns[0] != namespace
            ]
            if namespace in self._catalog.tables:
                del self._catalog.tables[namespace]

    def create_table(
        self,
        identifier: str,
        schema: dict[str, Any],
        location: str | None = None,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Create a new table.

        Args:
            identifier: Full table identifier (namespace.table).
            schema: Iceberg schema definition.
            location: Optional storage location.
            properties: Optional table properties.
        """
        self._tables[identifier] = {
            "schema": schema,
            "location": location,
            "properties": properties or {},
        }
        namespace = identifier.split(".")[0]
        if namespace in self._catalog.tables:
            self._catalog.tables[namespace].append(identifier)

    def list_tables(self, namespace: str) -> list[str]:
        """List tables in a namespace.

        Args:
            namespace: Namespace to list tables from.

        Returns:
            List of table identifiers.
        """
        return self._catalog.tables.get(namespace, [])

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop a table.

        Args:
            identifier: Full table identifier.
            purge: Whether to purge underlying data (unused in mock).
        """
        _ = purge  # Mark as used - mock doesn't differentiate purge behavior
        if identifier in self._tables:
            del self._tables[identifier]
            namespace = identifier.split(".")[0]
            if namespace in self._catalog.tables:
                self._catalog.tables[namespace] = [
                    t for t in self._catalog.tables[namespace] if t != identifier
                ]

    def vend_credentials(
        self,
        table_path: str,
        operations: list[str],
    ) -> dict[str, Any]:
        """Vend mock credentials.

        Args:
            table_path: Table path for credential scoping (unused in mock).
            operations: Requested operations (unused in mock).

        Returns:
            Mock credential dictionary.
        """
        # Mark as used to satisfy linters - mock returns fixed credentials
        _ = (table_path, operations)
        return {
            "access_key": "mock-access-key",
            "secret_key": "mock-secret-key",
            "token": "mock-session-token",
            "expiration": "2099-12-31T23:59:59Z",
        }


# =============================================================================
# Mock StoragePlugin Fixture
# =============================================================================


class MockStoragePlugin:
    """Mock implementation of StoragePlugin for unit testing.

    Implements all abstract methods from StoragePlugin ABC without
    requiring real storage connectivity.

    Attributes:
        _fileio: Internal MockFileIO instance.
        warehouse_bucket: Mock bucket name for warehouse URIs.
    """

    def __init__(self) -> None:
        """Initialize mock storage plugin."""
        self._fileio = MockFileIO()
        self.warehouse_bucket = "mock-warehouse-bucket"

    # PluginMetadata properties
    @property
    def name(self) -> str:
        """Plugin name."""
        return "mock-storage"

    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"

    @property
    def floe_api_version(self) -> str:
        """Floe API version compatibility."""
        return "1.0"

    # StoragePlugin methods
    def get_pyiceberg_fileio(self) -> MockFileIO:
        """Get mock FileIO instance.

        Returns:
            MockFileIO instance for testing.
        """
        return self._fileio

    def get_warehouse_uri(self, namespace: str) -> str:
        """Generate warehouse URI for namespace.

        Args:
            namespace: Catalog namespace.

        Returns:
            Mock S3 URI for the namespace.
        """
        return f"s3://{self.warehouse_bucket}/warehouse/{namespace}"

    def get_dbt_profile_config(self) -> dict[str, Any]:
        """Get mock dbt profile configuration.

        Returns:
            Mock dbt storage configuration.
        """
        return {
            "s3_region": "us-east-1",
            "s3_access_key_id": "{{ env_var('AWS_ACCESS_KEY_ID') }}",
            "s3_secret_access_key": "{{ env_var('AWS_SECRET_ACCESS_KEY') }}",
        }

    def get_dagster_io_manager_config(self) -> dict[str, Any]:
        """Get mock Dagster IOManager configuration.

        Returns:
            Mock Dagster storage configuration.
        """
        return {
            "bucket": self.warehouse_bucket,
            "prefix": "dagster-assets",
            "region_name": "us-east-1",
        }

    def get_helm_values_override(self) -> dict[str, Any]:
        """Get empty Helm values (mock is external storage).

        Returns:
            Empty dict (no deployment needed for mock).
        """
        return {}


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_catalog() -> MockCatalog:
    """Create a fresh MockCatalog instance.

    Returns:
        MockCatalog instance for direct catalog protocol testing.
    """
    return MockCatalog()


@pytest.fixture
def mock_fileio() -> MockFileIO:
    """Create a fresh MockFileIO instance.

    Returns:
        MockFileIO instance for direct FileIO protocol testing.
    """
    return MockFileIO()


@pytest.fixture
def mock_catalog_plugin() -> MockCatalogPlugin:
    """Create a fresh MockCatalogPlugin instance.

    Returns:
        MockCatalogPlugin instance for IcebergTableManager testing.

    Example:
        >>> def test_manager_init(mock_catalog_plugin, mock_storage_plugin):
        ...     manager = IcebergTableManager(
        ...         catalog_plugin=mock_catalog_plugin,
        ...         storage_plugin=mock_storage_plugin,
        ...     )
        ...     assert manager is not None
    """
    return MockCatalogPlugin()


@pytest.fixture
def mock_storage_plugin() -> MockStoragePlugin:
    """Create a fresh MockStoragePlugin instance.

    Returns:
        MockStoragePlugin instance for IcebergTableManager testing.

    Example:
        >>> def test_manager_write(mock_catalog_plugin, mock_storage_plugin):
        ...     manager = IcebergTableManager(
        ...         catalog_plugin=mock_catalog_plugin,
        ...         storage_plugin=mock_storage_plugin,
        ...     )
        ...     # Test write operations
    """
    return MockStoragePlugin()


@pytest.fixture
def connected_catalog_plugin(
    mock_catalog_plugin: MockCatalogPlugin,
) -> MockCatalogPlugin:
    """Create a MockCatalogPlugin that is already connected.

    Args:
        mock_catalog_plugin: Fresh mock catalog plugin.

    Returns:
        Connected MockCatalogPlugin instance.
    """
    mock_catalog_plugin.connect({"uri": "mock://catalog", "warehouse": "test"})
    return mock_catalog_plugin


@pytest.fixture
def catalog_with_namespace(
    connected_catalog_plugin: MockCatalogPlugin,
) -> Generator[MockCatalogPlugin, None, None]:
    """Create a connected catalog with a test namespace.

    Args:
        connected_catalog_plugin: Connected mock catalog plugin.

    Yields:
        MockCatalogPlugin with 'test_namespace' created.
    """
    connected_catalog_plugin.create_namespace(
        "test_namespace",
        {"location": "s3://mock-warehouse-bucket/warehouse/test_namespace"},
    )
    yield connected_catalog_plugin
