"""IcebergTableManager - Internal utility for PyIceberg table operations.

This module provides the IcebergTableManager class, which wraps PyIceberg
table operations with a consistent API for table creation, schema evolution,
writes, and snapshot management.

IcebergTableManager is NOT a plugin - Iceberg is enforced (ADR-0005), not pluggable.
It accepts CatalogPlugin and StoragePlugin via dependency injection.

Example:
    >>> from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
    >>> from floe_iceberg.models import TableConfig, WriteConfig, WriteMode
    >>>
    >>> manager = IcebergTableManager(
    ...     catalog_plugin=polaris_plugin,
    ...     storage_plugin=s3_plugin,
    ...     config=IcebergTableManagerConfig(max_commit_retries=3),
    ... )
    >>> table = manager.create_table(table_config)
    >>> manager.write_data(table, data, WriteConfig(mode=WriteMode.APPEND))

See Also:
    - IcebergTableManagerConfig: Configuration model
    - CatalogPlugin: Abstract interface for catalog plugins
    - StoragePlugin: Abstract interface for storage plugins
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_iceberg.errors import (
    NoSuchNamespaceError,
    NoSuchTableError,
    TableAlreadyExistsError,
    ValidationError,
)
from floe_iceberg.models import IcebergTableManagerConfig, TableConfig

if TYPE_CHECKING:
    from floe_core.plugins.catalog import Catalog, CatalogPlugin
    from floe_core.plugins.storage import FileIO, StoragePlugin

    # Type alias for PyIceberg Table
    Table = Any


class IcebergTableManager:
    """Internal utility class for Iceberg table operations.

    Wraps PyIceberg complexity with a consistent API for:
    - Table creation with schema and partitioning
    - Schema evolution (add/rename/widen columns)
    - Data writes (append, overwrite, upsert)
    - Snapshot management (list, rollback, expire)
    - Table compaction

    This class is NOT a plugin. Iceberg is enforced per ADR-0005.
    It accepts CatalogPlugin and StoragePlugin via dependency injection.

    Attributes:
        catalog: Connected PyIceberg catalog instance.
        fileio: PyIceberg FileIO for storage operations.
        config: Manager configuration.

    Example:
        >>> manager = IcebergTableManager(
        ...     catalog_plugin=polaris_plugin,
        ...     storage_plugin=s3_plugin,
        ... )
        >>> manager.table_exists("bronze.customers")
        False
    """

    def __init__(
        self,
        catalog_plugin: CatalogPlugin,
        storage_plugin: StoragePlugin,
        config: IcebergTableManagerConfig | None = None,
    ) -> None:
        """Initialize IcebergTableManager with plugin dependencies.

        Connects to the catalog and retrieves FileIO during initialization.
        If config is not provided, uses default IcebergTableManagerConfig.

        Args:
            catalog_plugin: CatalogPlugin instance for catalog operations.
            storage_plugin: StoragePlugin instance for storage operations.
            config: Optional manager configuration. Defaults to IcebergTableManagerConfig().

        Raises:
            TypeError: If catalog_plugin or storage_plugin is not the expected type.
            ConnectionError: If unable to connect to the catalog.
            RuntimeError: If unable to retrieve FileIO from storage plugin.

        Example:
            >>> from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
            >>> manager = IcebergTableManager(
            ...     catalog_plugin=polaris_plugin,
            ...     storage_plugin=s3_plugin,
            ...     config=IcebergTableManagerConfig(max_commit_retries=5),
            ... )
        """
        # Validate plugin types using duck typing
        self._validate_catalog_plugin(catalog_plugin)
        self._validate_storage_plugin(storage_plugin)

        # Store plugin references
        self._catalog_plugin = catalog_plugin
        self._storage_plugin = storage_plugin

        # Use provided config or default
        self._config = config if config is not None else IcebergTableManagerConfig()

        # Set up structured logging with context
        self._log = structlog.get_logger(__name__).bind(
            catalog_plugin=getattr(catalog_plugin, "name", "unknown"),
            storage_plugin=getattr(storage_plugin, "name", "unknown"),
        )

        self._log.debug("initializing_iceberg_table_manager")

        # Connect to catalog (FR-009)
        self._catalog = self._connect_to_catalog()

        # Retrieve FileIO (FR-010)
        self._fileio = self._retrieve_fileio()

        self._log.info(
            "iceberg_table_manager_initialized",
            max_commit_retries=self._config.max_commit_retries,
            default_retention_days=self._config.default_retention_days,
        )

    def _validate_catalog_plugin(self, catalog_plugin: Any) -> None:
        """Validate catalog plugin has required interface.

        Args:
            catalog_plugin: Plugin to validate.

        Raises:
            TypeError: If plugin doesn't have required methods.
        """
        required_attrs = ["connect", "name"]
        for attr in required_attrs:
            if not hasattr(catalog_plugin, attr):
                msg = f"catalog_plugin must have '{attr}' attribute"
                raise TypeError(msg)

    def _validate_storage_plugin(self, storage_plugin: Any) -> None:
        """Validate storage plugin has required interface.

        Args:
            storage_plugin: Plugin to validate.

        Raises:
            TypeError: If plugin doesn't have required methods.
        """
        required_attrs = ["get_pyiceberg_fileio", "name"]
        for attr in required_attrs:
            if not hasattr(storage_plugin, attr):
                msg = f"storage_plugin must have '{attr}' attribute"
                raise TypeError(msg)

    def _connect_to_catalog(self) -> Catalog:
        """Connect to the catalog via CatalogPlugin.

        Returns:
            Connected PyIceberg Catalog instance.

        Raises:
            ConnectionError: If unable to connect to catalog.
        """
        self._log.debug("connecting_to_catalog")

        # Build connection config - in production this would come from environment
        # For now, use minimal config that MockCatalogPlugin accepts
        connect_config: dict[str, Any] = {
            "uri": "memory://",  # Mock URI for testing
            "warehouse": "default",
        }

        catalog = self._catalog_plugin.connect(connect_config)

        self._log.debug("catalog_connected")
        return catalog

    def _retrieve_fileio(self) -> FileIO:
        """Retrieve FileIO from StoragePlugin.

        Returns:
            PyIceberg FileIO instance.

        Raises:
            RuntimeError: If unable to retrieve FileIO.
        """
        self._log.debug("retrieving_fileio")

        fileio = self._storage_plugin.get_pyiceberg_fileio()

        self._log.debug("fileio_retrieved")
        return fileio

    # =========================================================================
    # Public Properties
    # =========================================================================

    @property
    def catalog(self) -> Catalog:
        """Return the connected catalog instance.

        Returns:
            Connected PyIceberg Catalog.
        """
        return self._catalog

    @property
    def fileio(self) -> FileIO:
        """Return the FileIO instance.

        Returns:
            PyIceberg FileIO for storage operations.
        """
        return self._fileio

    @property
    def config(self) -> IcebergTableManagerConfig:
        """Return the manager configuration.

        Returns:
            IcebergTableManagerConfig instance.
        """
        return self._config

    # =========================================================================
    # Table Operations
    # =========================================================================

    def create_table(
        self,
        config: TableConfig,
        if_not_exists: bool = False,
    ) -> Table:
        """Create an Iceberg table with specified configuration.

        Creates a new table in the catalog with schema, partitioning,
        and properties from the configuration.

        Args:
            config: TableConfig with namespace, name, schema, partition spec.
            if_not_exists: If True, return existing table instead of raising error.
                Default False (fail fast principle).

        Returns:
            PyIceberg Table instance (or mock table in unit tests).

        Raises:
            TableAlreadyExistsError: If table exists and if_not_exists=False.
            NoSuchNamespaceError: If namespace doesn't exist.
            ValidationError: If config is invalid.

        Example:
            >>> config = TableConfig(
            ...     namespace="bronze",
            ...     table_name="customers",
            ...     table_schema=schema,
            ...     partition_spec=partition_spec,
            ... )
            >>> table = manager.create_table(config)
            >>> # Idempotent creation
            >>> table = manager.create_table(config, if_not_exists=True)
        """
        identifier = config.identifier

        self._log.debug(
            "create_table_requested",
            identifier=identifier,
            if_not_exists=if_not_exists,
        )

        # Validate namespace exists
        self._validate_namespace_exists(config.namespace)

        # Check if table already exists
        if self.table_exists(identifier):
            if if_not_exists:
                self._log.info(
                    "table_already_exists_returning_existing",
                    identifier=identifier,
                )
                return self.load_table(identifier)
            msg = f"Table '{identifier}' already exists"
            raise TableAlreadyExistsError(msg)

        # Convert schema to dict for catalog plugin
        schema_dict = self._table_schema_to_dict(config.table_schema)

        # Create table via catalog plugin
        self._catalog_plugin.create_table(
            identifier=identifier,
            schema=schema_dict,
            location=config.location,
            properties=config.properties,
        )

        self._log.info(
            "table_created",
            identifier=identifier,
            has_partitioning=config.partition_spec is not None,
        )

        # Load and return the created table
        return self.load_table(identifier)

    def load_table(self, identifier: str) -> Table:
        """Load an existing table by identifier.

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").

        Returns:
            PyIceberg Table instance (or mock table in unit tests).

        Raises:
            NoSuchTableError: If table doesn't exist.
            ValidationError: If identifier format is invalid.

        Example:
            >>> table = manager.load_table("bronze.customers")
        """
        self._log.debug("load_table_requested", identifier=identifier)

        # Validate identifier format
        self._validate_identifier(identifier)

        # Check if table exists
        if not self.table_exists(identifier):
            msg = f"Table '{identifier}' does not exist"
            raise NoSuchTableError(msg)

        # Load table from catalog
        table = self._catalog.load_table(identifier)

        self._log.debug("table_loaded", identifier=identifier)

        return table

    def table_exists(self, identifier: str) -> bool:
        """Check if a table exists.

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").

        Returns:
            True if table exists, False otherwise.

        Example:
            >>> if not manager.table_exists("bronze.new_table"):
            ...     manager.create_table(config)
        """
        self._log.debug("table_exists_check", identifier=identifier)

        # Parse identifier to get namespace and table name
        parts = identifier.rsplit(".", 1)
        if len(parts) < 2:
            # Invalid identifier format - can't exist
            return False

        namespace = parts[0]
        table_name = parts[1]

        # Check if namespace exists
        if namespace not in self._catalog_plugin._namespaces:
            return False

        # Check if table exists in catalog
        full_identifier = f"{namespace}.{table_name}"
        return full_identifier in self._catalog_plugin._tables

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _validate_namespace_exists(self, namespace: str) -> None:
        """Validate that a namespace exists in the catalog.

        Args:
            namespace: Namespace to validate.

        Raises:
            NoSuchNamespaceError: If namespace doesn't exist.
        """
        if namespace not in self._catalog_plugin._namespaces:
            msg = f"Namespace '{namespace}' does not exist"
            raise NoSuchNamespaceError(msg)

    def _validate_identifier(self, identifier: str) -> None:
        """Validate table identifier format.

        Args:
            identifier: Table identifier to validate.

        Raises:
            ValidationError: If identifier format is invalid.
        """
        parts = identifier.rsplit(".", 1)
        if len(parts) < 2:
            msg = f"Invalid identifier format: '{identifier}'. Expected 'namespace.table'"
            raise ValidationError(msg)

    def _table_schema_to_dict(self, table_schema: Any) -> dict[str, Any]:
        """Convert TableSchema to dictionary for catalog plugin.

        Args:
            table_schema: TableSchema model instance.

        Returns:
            Dictionary representation of the schema.
        """
        return {
            "fields": [
                {
                    "field_id": field.field_id,
                    "name": field.name,
                    "type": field.field_type.value,
                    "required": field.required,
                    "doc": field.doc,
                }
                for field in table_schema.fields
            ]
        }

    # =========================================================================
    # Table Operations (to be implemented in later tasks)
    # =========================================================================

    # evolve_schema() - T039
    # write_data() - T048
    # list_snapshots() - T059
    # rollback_to_snapshot() - T067
    # expire_snapshots() - T077
    # compact_table() - T088


__all__ = ["IcebergTableManager"]
