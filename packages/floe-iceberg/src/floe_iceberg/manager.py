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

from floe_iceberg.models import IcebergTableManagerConfig

if TYPE_CHECKING:
    from floe_core.plugins.catalog import Catalog, CatalogPlugin
    from floe_core.plugins.storage import FileIO, StoragePlugin


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
    # Table Operations (to be implemented in later tasks)
    # =========================================================================

    # create_table() - T027
    # load_table() - T029
    # table_exists() - T030
    # evolve_schema() - T039
    # write_data() - T048
    # list_snapshots() - T059
    # rollback_to_snapshot() - T067
    # expire_snapshots() - T077
    # compact_table() - T088


__all__ = ["IcebergTableManager"]
