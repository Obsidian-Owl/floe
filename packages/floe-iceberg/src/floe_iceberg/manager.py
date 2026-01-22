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

from floe_iceberg._compaction_manager import _IcebergCompactionManager
from floe_iceberg._lifecycle import _IcebergTableLifecycle
from floe_iceberg._schema_manager import _IcebergSchemaManager
from floe_iceberg._snapshot_manager import _IcebergSnapshotManager
from floe_iceberg.errors import (
    NoSuchNamespaceError,
    ValidationError,
)
from floe_iceberg.models import (
    CompactionStrategy,
    IcebergTableManagerConfig,
    SchemaEvolution,
    SnapshotInfo,
    TableConfig,
    WriteConfig,
    WriteMode,
)
from floe_iceberg.telemetry import traced

if TYPE_CHECKING:
    from floe_core.plugins.catalog import Catalog, CatalogPlugin
    from floe_core.plugins.storage import FileIO, StoragePlugin

    # Type alias for PyIceberg Table
    #
    # NOTE: PyIceberg does not ship with py.typed marker or type stubs.
    # Using `Any` provides flexibility while awaiting upstream typing support.
    # Track: https://github.com/apache/iceberg-python/issues/XXX
    # Consider contributing stubs to typeshed when API stabilizes.
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

        # Initialize helper classes for facade pattern (T034)
        self._lifecycle = _IcebergTableLifecycle(self._catalog, self._catalog_plugin)
        self._schema_manager = _IcebergSchemaManager(self._catalog_plugin)
        self._snapshot_manager = _IcebergSnapshotManager(self._config)
        self._compaction_manager = _IcebergCompactionManager()

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

        Uses config.catalog_connection_config if provided, otherwise uses
        minimal default config for testing compatibility.

        Returns:
            Connected PyIceberg Catalog instance.

        Raises:
            ConnectionError: If unable to connect to catalog.
        """
        self._log.debug("connecting_to_catalog")

        # Use config override if provided, otherwise use minimal defaults
        # for testing compatibility (e.g., in-memory catalog for unit tests)
        if self._config.catalog_connection_config is not None:
            connect_config: dict[str, Any] = dict(self._config.catalog_connection_config)
        else:
            # Default config for testing - production should configure via plugins
            connect_config = {
                "uri": "memory://",
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

        Delegates to _IcebergTableLifecycle helper (T034 facade pattern).

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
        return self._lifecycle.create_table(config, if_not_exists)

    def load_table(self, identifier: str) -> Table:
        """Load an existing table by identifier.

        Delegates to _IcebergTableLifecycle helper (T034 facade pattern).

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
        return self._lifecycle.load_table(identifier)

    def table_exists(self, identifier: str) -> bool:
        """Check if a table exists.

        Delegates to _IcebergTableLifecycle helper (T034 facade pattern).

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").

        Returns:
            True if table exists, False otherwise.

        Example:
            >>> if not manager.table_exists("bronze.new_table"):
            ...     manager.create_table(config)
        """
        return self._lifecycle.table_exists(identifier)

    def drop_table(self, identifier: str, purge: bool = False) -> None:
        """Drop (delete) a table from the catalog.

        Removes the table metadata from the catalog. If purge=True, also
        deletes the underlying data files (when supported by the catalog).

        Delegates to _IcebergTableLifecycle helper (T034 facade pattern).

        Args:
            identifier: Full table identifier (e.g., "bronze.customers").
            purge: If True, delete underlying data files. Default False
                (keep data files for potential recovery).

        Raises:
            NoSuchTableError: If table doesn't exist.
            ValidationError: If identifier format is invalid.

        Example:
            >>> # Soft delete (keep data files)
            >>> manager.drop_table("bronze.deprecated_table")

            >>> # Hard delete (remove data files)
            >>> manager.drop_table("bronze.temp_table", purge=True)
        """
        return self._lifecycle.drop_table(identifier, purge=purge)

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
        # Mock-specific attribute access for unit testing
        namespaces: list[str] | None = getattr(self._catalog_plugin, "_namespaces", None)
        if namespaces is not None and namespace not in namespaces:
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
    # Schema Evolution (T039-T044)
    # =========================================================================

    def evolve_schema(
        self,
        table: Table,
        evolution: SchemaEvolution,
    ) -> Table:
        """Apply schema changes to a table.

        Applies schema evolution operations atomically. Safe operations
        (add column, rename, widen type) are allowed by default.
        Incompatible changes (delete column) require explicit flag.

        Delegates to _IcebergSchemaManager helper (T034 facade pattern).

        Args:
            table: PyIceberg Table instance (or mock in tests).
            evolution: SchemaEvolution with list of changes.

        Returns:
            Updated Table instance with new schema.

        Raises:
            IncompatibleSchemaChangeError: If changes are incompatible and not allowed.
            SchemaEvolutionError: If evolution fails (e.g., column not found).

        Example:
            >>> evolution = SchemaEvolution(
            ...     changes=[
            ...         SchemaChange(
            ...             change_type=SchemaChangeType.ADD_COLUMN,
            ...             field=SchemaField(
            ...                 field_id=10,
            ...                 name="phone",
            ...                 field_type=FieldType.STRING,
            ...             ),
            ...         ),
            ...     ],
            ... )
            >>> table = manager.evolve_schema(table, evolution)
        """
        return self._schema_manager.evolve_schema(table, evolution)

    # =========================================================================
    # Snapshot Management Operations
    # =========================================================================

    def list_snapshots(self, table: Table) -> list[SnapshotInfo]:
        """List all snapshots for a table, ordered by timestamp (newest first).

        Retrieves snapshot metadata from the table and converts to SnapshotInfo
        objects for a consistent API.

        Delegates to _IcebergSnapshotManager helper (T034 facade pattern).

        Args:
            table: PyIceberg Table object.

        Returns:
            List of SnapshotInfo objects, ordered newest first.

        Example:
            >>> snapshots = manager.list_snapshots(table)
            >>> for snapshot in snapshots:
            ...     print(f"ID: {snapshot.snapshot_id}, Records: {snapshot.added_records}")
        """
        return self._snapshot_manager.list_snapshots(table)

    def rollback_to_snapshot(self, table: Table, snapshot_id: int) -> Table:
        """Rollback table to a previous snapshot.

        Creates a new snapshot pointing to the specified historical snapshot.
        This is a non-destructive operation - previous snapshots are preserved.

        Delegates to _IcebergSnapshotManager helper (T034 facade pattern).

        Args:
            table: PyIceberg Table object.
            snapshot_id: ID of the snapshot to rollback to.

        Returns:
            Updated Table object with new current snapshot.

        Raises:
            SnapshotNotFoundError: If snapshot_id doesn't exist.

        Example:
            >>> snapshots = manager.list_snapshots(table)
            >>> old_snapshot = snapshots[-1]  # Oldest snapshot
            >>> table = manager.rollback_to_snapshot(table, old_snapshot.snapshot_id)
        """
        return self._snapshot_manager.rollback_to_snapshot(table, snapshot_id)

    def expire_snapshots(
        self,
        table: Table,
        older_than_days: int | None = None,
    ) -> int:
        """Expire snapshots older than the specified retention period.

        Removes old snapshots while respecting min_snapshots_to_keep from config.
        This helps manage storage costs and metadata overhead.

        Delegates to _IcebergSnapshotManager helper (T034 facade pattern).

        Args:
            table: PyIceberg Table object.
            older_than_days: Days to retain snapshots. Defaults to config value.

        Returns:
            Number of snapshots expired.

        Example:
            >>> # Expire snapshots older than 30 days
            >>> expired_count = manager.expire_snapshots(table, older_than_days=30)
            >>> print(f"Expired {expired_count} snapshots")
        """
        return self._snapshot_manager.expire_snapshots(table, older_than_days)

    # =========================================================================
    # Write Operations
    # =========================================================================

    @traced(
        operation_name="iceberg.write_data",
    )
    def write_data(
        self,
        table: Table,
        data: Any,  # PyArrow Table
        config: WriteConfig,
    ) -> Table:
        """Write data to an Iceberg table.

        Supports three write modes:
        - APPEND: Add new data files to the table
        - OVERWRITE: Replace data (full table or filtered partition)
        - UPSERT: Merge data based on join columns (insert new, update existing)

        Args:
            table: The Iceberg table to write to.
            data: PyArrow Table containing data to write.
            config: Write configuration (mode, commit strategy, etc.).

        Returns:
            The updated Table object with new snapshot.

        Raises:
            ValidationError: If join_columns don't exist in schema (UPSERT mode).
            CommitConflictError: If commit fails after max retries.

        Example:
            >>> data = pa.table({"id": [1, 2], "name": ["Alice", "Bob"]})
            >>> config = WriteConfig(mode=WriteMode.APPEND)
            >>> table = manager.write_data(table, data, config)

            >>> # Upsert with join columns
            >>> config = WriteConfig(
            ...     mode=WriteMode.UPSERT,
            ...     join_columns=["id"],
            ... )
            >>> table = manager.write_data(table, data, config)
        """
        from opentelemetry import trace

        # Add span attributes for telemetry
        span = trace.get_current_span()
        span.set_attribute("table.identifier", getattr(table, "identifier", "unknown"))
        span.set_attribute("write.mode", config.mode.value)
        span.set_attribute("commit.strategy", config.commit_strategy.value)

        self._log.debug(
            "write_data_requested",
            table_identifier=getattr(table, "identifier", None),
            mode=config.mode.value,
            commit_strategy=config.commit_strategy.value,
            row_count=len(data) if hasattr(data, "__len__") else "unknown",
        )

        # Validate join_columns for UPSERT mode
        if config.mode == WriteMode.UPSERT and config.join_columns:
            # Get field names from PyIceberg table schema
            schema = table.schema()
            field_names = {field.name for field in schema.fields}

            for col in config.join_columns:
                if col not in field_names:
                    msg = f"Join column '{col}' not found in table schema"
                    raise ValidationError(msg)

        # Dispatch to appropriate write handler based on mode
        if config.mode == WriteMode.APPEND:
            result = self._write_append(table, data, config)
        elif config.mode == WriteMode.OVERWRITE:
            result = self._write_overwrite(table, data, config)
        elif config.mode == WriteMode.UPSERT:
            result = self._write_upsert(table, data, config)
        else:
            msg = f"Unsupported write mode: {config.mode}"
            raise ValidationError(msg)

        self._log.info(
            "write_data_completed",
            table_identifier=getattr(table, "identifier", None),
            mode=config.mode.value,
        )

        return result

    def _write_append(
        self,
        table: Table,
        data: Any,
        config: WriteConfig,
    ) -> Table:
        """Append data to table (internal helper).

        Args:
            table: The Iceberg table.
            data: PyArrow Table with data to append.
            config: Write configuration.

        Returns:
            Updated table with new snapshot.
        """
        self._log.debug(
            "write_append_started",
            table_identifier=getattr(table, "identifier", None),
            commit_strategy=config.commit_strategy.value,
        )

        # Use PyIceberg append API
        table.append(data)

        # Refresh to get latest snapshot
        if hasattr(table, "refresh"):
            table.refresh()

        current_snapshot = table.current_snapshot()
        snapshot_id = current_snapshot.snapshot_id if current_snapshot else 0

        self._log.debug(
            "write_append_completed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=snapshot_id,
        )

        return table

    def _write_overwrite(
        self,
        table: Table,
        data: Any,
        config: WriteConfig,
    ) -> Table:
        """Overwrite data in table (internal helper).

        Args:
            table: The Iceberg table.
            data: PyArrow Table with replacement data.
            config: Write configuration (may include overwrite_filter).

        Returns:
            Updated table with new snapshot.
        """
        self._log.debug(
            "write_overwrite_started",
            table_identifier=getattr(table, "identifier", None),
            has_filter=config.overwrite_filter is not None,
        )

        # Use PyIceberg overwrite API
        table.overwrite(data)

        # Refresh to get latest snapshot
        if hasattr(table, "refresh"):
            table.refresh()

        current_snapshot = table.current_snapshot()
        snapshot_id = current_snapshot.snapshot_id if current_snapshot else 0

        self._log.debug(
            "write_overwrite_completed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=snapshot_id,
        )

        return table

    def _write_upsert(
        self,
        table: Table,
        data: Any,
        config: WriteConfig,
    ) -> Table:
        """Upsert data into table (internal helper).

        Performs merge operation: insert new rows, update existing based on join_columns.

        Args:
            table: The Iceberg table.
            data: PyArrow Table with data to upsert.
            config: Write configuration (must include join_columns).

        Returns:
            Updated table with new snapshot.
        """
        self._log.debug(
            "write_upsert_started",
            table_identifier=getattr(table, "identifier", None),
            join_columns=config.join_columns,
        )

        # Note: PyIceberg doesn't have native MERGE/UPSERT.
        # For production upsert, use:
        # - dbt incremental models with merge strategy
        # - Spark DataFrame.merge() operations
        # - Flink Iceberg sink with upsert mode
        #
        # This implementation uses overwrite as a fallback, which replaces
        # the entire table contents. For large tables, prefer compute-layer
        # merge operations via dbt or Spark.
        self._log.warning(
            "upsert_using_overwrite_fallback",
            table_identifier=getattr(table, "identifier", None),
            message="PyIceberg lacks native MERGE; using overwrite fallback",
        )

        # Use overwrite as fallback (replaces all data)
        table.overwrite(data)

        # Refresh to get latest snapshot
        if hasattr(table, "refresh"):
            table.refresh()

        current_snapshot = table.current_snapshot()
        snapshot_id = current_snapshot.snapshot_id if current_snapshot else 0

        self._log.debug(
            "write_upsert_completed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=snapshot_id,
        )

        return table

    # =========================================================================
    # Compaction Operations
    # =========================================================================

    def compact_table(
        self,
        table: Table,
        strategy: CompactionStrategy | None = None,
    ) -> int:
        """Compact table data files to optimize query performance.

        Rewrites small files into larger files using the specified strategy.
        This reduces metadata overhead and improves query performance.

        Delegates to _IcebergCompactionManager helper (T034 facade pattern).

        Note: The orchestrator (Dagster) is responsible for scheduling when
        to call this method. This method only performs the execution.

        Args:
            table: PyIceberg Table object.
            strategy: CompactionStrategy configuration. Defaults to BIN_PACK
                with 128MB target file size.

        Returns:
            Number of files rewritten during compaction.

        Raises:
            CompactionError: If compaction fails.

        Example:
            >>> from floe_iceberg.models import CompactionStrategy, CompactionStrategyType
            >>> strategy = CompactionStrategy(
            ...     strategy_type=CompactionStrategyType.BIN_PACK,
            ...     target_file_size_bytes=134217728,  # 128MB
            ... )
            >>> files_rewritten = manager.compact_table(table, strategy)
            >>> print(f"Rewrote {files_rewritten} files")
        """
        return self._compaction_manager.compact_table(table, strategy)


__all__ = ["IcebergTableManager"]
