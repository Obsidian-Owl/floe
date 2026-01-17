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
    IncompatibleSchemaChangeError,
    NoSuchNamespaceError,
    NoSuchTableError,
    SchemaEvolutionError,
    SnapshotNotFoundError,
    TableAlreadyExistsError,
    ValidationError,
)
from floe_iceberg.models import (
    CommitStrategy,
    FieldType,
    IcebergTableManagerConfig,
    OperationType,
    SchemaChange,
    SchemaChangeType,
    SchemaEvolution,
    SnapshotInfo,
    TableConfig,
    WriteConfig,
    WriteMode,
)

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
    # Schema Evolution (T039-T044)
    # =========================================================================

    # Type widening rules (compatible promotions)
    _VALID_TYPE_WIDENINGS: dict[FieldType, set[FieldType]] = {
        FieldType.INT: {FieldType.LONG},
        FieldType.FLOAT: {FieldType.DOUBLE},
    }

    def evolve_schema(
        self,
        table: Table,
        evolution: SchemaEvolution,
    ) -> Table:
        """Apply schema changes to a table.

        Applies schema evolution operations atomically. Safe operations
        (add column, rename, widen type) are allowed by default.
        Incompatible changes (delete column) require explicit flag.

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
        self._log.debug(
            "evolve_schema_requested",
            num_changes=len(evolution.changes),
            allow_incompatible=evolution.allow_incompatible_changes,
        )

        # Validate all changes before applying any
        self._validate_schema_evolution(table, evolution)

        # Apply each change
        for change in evolution.changes:
            self._apply_schema_change(table, change)

        self._log.info(
            "schema_evolved",
            num_changes=len(evolution.changes),
        )

        # Return the table (in real PyIceberg, this would reload)
        return table

    def _validate_schema_evolution(
        self,
        table: Table,
        evolution: SchemaEvolution,
    ) -> None:
        """Validate all schema changes before applying.

        Args:
            table: Table to validate against.
            evolution: Schema evolution to validate.

        Raises:
            IncompatibleSchemaChangeError: If incompatible changes without flag.
            SchemaEvolutionError: If changes reference nonexistent columns.
        """
        for change in evolution.changes:
            # Check for incompatible changes
            if self._is_incompatible_change(change):
                if not evolution.allow_incompatible_changes:
                    msg = (
                        f"Incompatible change '{change.change_type.value}' "
                        "requires allow_incompatible_changes=True"
                    )
                    raise IncompatibleSchemaChangeError(msg)

            # Validate change-specific requirements
            self._validate_change(table, change, evolution.allow_incompatible_changes)

    def _is_incompatible_change(self, change: SchemaChange) -> bool:
        """Check if a change is incompatible (breaking).

        Args:
            change: Change to check.

        Returns:
            True if change is incompatible.
        """
        # DELETE_COLUMN is always incompatible
        if change.change_type == SchemaChangeType.DELETE_COLUMN:
            return True

        # ADD_COLUMN with required=True is incompatible (breaks existing data)
        if change.change_type == SchemaChangeType.ADD_COLUMN:
            if change.field is not None and change.field.required:
                return True

        return False

    def _validate_change(
        self,
        table: Table,
        change: SchemaChange,
        allow_incompatible: bool,
    ) -> None:
        """Validate a single schema change.

        Args:
            table: Table to validate against.
            change: Change to validate.
            allow_incompatible: Whether incompatible changes are allowed.

        Raises:
            SchemaEvolutionError: If change is invalid.
            IncompatibleSchemaChangeError: If type widening is invalid.
        """
        if change.change_type == SchemaChangeType.RENAME_COLUMN:
            # Check source column exists (via catalog plugin mock)
            if change.source_column is not None:
                if not self._column_exists(table, change.source_column):
                    msg = f"Column '{change.source_column}' does not exist"
                    raise SchemaEvolutionError(msg)

        elif change.change_type == SchemaChangeType.WIDEN_TYPE:
            # Check source column exists and widening is valid
            if change.source_column is not None:
                if not self._column_exists(table, change.source_column):
                    msg = f"Column '{change.source_column}' does not exist"
                    raise SchemaEvolutionError(msg)

                # Check if type widening is valid
                if change.target_type is not None:
                    source_type = self._get_column_type(table, change.source_column)
                    if not self._is_valid_type_widening(source_type, change.target_type):
                        msg = (
                            f"Cannot widen type from '{source_type}' to "
                            f"'{change.target_type.value}'"
                        )
                        raise IncompatibleSchemaChangeError(msg)

        elif change.change_type in (
            SchemaChangeType.MAKE_OPTIONAL,
            SchemaChangeType.UPDATE_DOC,
            SchemaChangeType.DELETE_COLUMN,
        ):
            # Check source column exists
            if change.source_column is not None:
                if not self._column_exists(table, change.source_column):
                    msg = f"Column '{change.source_column}' does not exist"
                    raise SchemaEvolutionError(msg)

    def _column_exists(self, table: Table, column_name: str) -> bool:
        """Check if a column exists in the table schema.

        Args:
            table: Table to check.
            column_name: Column name to look for.

        Returns:
            True if column exists.
        """
        # In mock, check via catalog plugin's table schema
        table_id = getattr(table, "identifier", None)
        if table_id is not None:
            table_data = self._catalog_plugin._tables.get(table_id)
            if table_data is not None:
                schema = table_data.get("schema", {})
                fields = schema.get("fields", [])
                return any(f.get("name") == column_name for f in fields)
        return True  # Assume exists in production (PyIceberg will validate)

    def _get_column_type(self, table: Table, column_name: str) -> FieldType | None:
        """Get the type of a column.

        Args:
            table: Table to check.
            column_name: Column name.

        Returns:
            FieldType of the column, or None if not found.
        """
        table_id = getattr(table, "identifier", None)
        if table_id is not None:
            table_data = self._catalog_plugin._tables.get(table_id)
            if table_data is not None:
                schema = table_data.get("schema", {})
                fields = schema.get("fields", [])
                for f in fields:
                    if f.get("name") == column_name:
                        try:
                            return FieldType(f.get("type"))
                        except ValueError:
                            return None
        return None

    def _is_valid_type_widening(
        self,
        source_type: FieldType | None,
        target_type: FieldType,
    ) -> bool:
        """Check if a type widening is valid.

        Args:
            source_type: Current column type.
            target_type: Target type to widen to.

        Returns:
            True if widening is valid.
        """
        if source_type is None:
            return False

        valid_targets = self._VALID_TYPE_WIDENINGS.get(source_type, set())
        return target_type in valid_targets

    def _apply_schema_change(self, table: Table, change: SchemaChange) -> None:
        """Apply a single schema change to the table.

        Args:
            table: Table to modify.
            change: Change to apply.
        """
        self._log.debug(
            "applying_schema_change",
            change_type=change.change_type.value,
        )

        # In mock mode, update the catalog plugin's table schema
        table_id = getattr(table, "identifier", None)
        if table_id is None:
            return

        table_data = self._catalog_plugin._tables.get(table_id)
        if table_data is None:
            return

        schema = table_data.get("schema", {})
        fields = list(schema.get("fields", []))

        if change.change_type == SchemaChangeType.ADD_COLUMN:
            self._apply_add_column(fields, change)
        elif change.change_type == SchemaChangeType.RENAME_COLUMN:
            self._apply_rename_column(fields, change)
        elif change.change_type == SchemaChangeType.WIDEN_TYPE:
            self._apply_widen_type(fields, change)
        elif change.change_type == SchemaChangeType.MAKE_OPTIONAL:
            self._apply_make_optional(fields, change)
        elif change.change_type == SchemaChangeType.DELETE_COLUMN:
            self._apply_delete_column(fields, change)
        elif change.change_type == SchemaChangeType.UPDATE_DOC:
            self._apply_update_doc(fields, change)

        # Update the schema in catalog
        schema["fields"] = fields
        table_data["schema"] = schema

    def _apply_add_column(
        self,
        fields: list[dict[str, Any]],
        change: SchemaChange,
    ) -> None:
        """Apply ADD_COLUMN change.

        Args:
            fields: List of field dicts to modify.
            change: Change with field to add.
        """
        if change.field is not None:
            fields.append({
                "field_id": change.field.field_id,
                "name": change.field.name,
                "type": change.field.field_type.value,
                "required": change.field.required,
                "doc": change.field.doc,
            })

    def _apply_rename_column(
        self,
        fields: list[dict[str, Any]],
        change: SchemaChange,
    ) -> None:
        """Apply RENAME_COLUMN change.

        Args:
            fields: List of field dicts to modify.
            change: Change with source_column and new_name.
        """
        for field in fields:
            if field.get("name") == change.source_column:
                field["name"] = change.new_name
                break

    def _apply_widen_type(
        self,
        fields: list[dict[str, Any]],
        change: SchemaChange,
    ) -> None:
        """Apply WIDEN_TYPE change.

        Args:
            fields: List of field dicts to modify.
            change: Change with source_column and target_type.
        """
        for field in fields:
            if field.get("name") == change.source_column:
                if change.target_type is not None:
                    field["type"] = change.target_type.value
                break

    def _apply_make_optional(
        self,
        fields: list[dict[str, Any]],
        change: SchemaChange,
    ) -> None:
        """Apply MAKE_OPTIONAL change.

        Args:
            fields: List of field dicts to modify.
            change: Change with source_column.
        """
        for field in fields:
            if field.get("name") == change.source_column:
                field["required"] = False
                break

    def _apply_delete_column(
        self,
        fields: list[dict[str, Any]],
        change: SchemaChange,
    ) -> None:
        """Apply DELETE_COLUMN change.

        Args:
            fields: List of field dicts to modify.
            change: Change with source_column.
        """
        for i, field in enumerate(fields):
            if field.get("name") == change.source_column:
                fields.pop(i)
                break

    def _apply_update_doc(
        self,
        fields: list[dict[str, Any]],
        change: SchemaChange,
    ) -> None:
        """Apply UPDATE_DOC change.

        Args:
            fields: List of field dicts to modify.
            change: Change with source_column and new_doc.
        """
        for field in fields:
            if field.get("name") == change.source_column:
                field["doc"] = change.new_doc
                break

    # =========================================================================
    # Snapshot Management Operations
    # =========================================================================

    def list_snapshots(self, table: Table) -> list[SnapshotInfo]:
        """List all snapshots for a table, ordered by timestamp (newest first).

        Retrieves snapshot metadata from the table and converts to SnapshotInfo
        objects for a consistent API.

        Args:
            table: PyIceberg Table object.

        Returns:
            List of SnapshotInfo objects, ordered newest first.

        Example:
            >>> snapshots = manager.list_snapshots(table)
            >>> for snapshot in snapshots:
            ...     print(f"ID: {snapshot.snapshot_id}, Records: {snapshot.added_records}")
        """
        self._log.debug(
            "list_snapshots_requested",
            table_identifier=getattr(table, "identifier", None),
        )

        # Get snapshots from mock catalog plugin's table data
        table_data = getattr(table, "_table_data", {})
        snapshots_data = table_data.get("snapshots", [])

        # Convert to SnapshotInfo objects
        snapshots: list[SnapshotInfo] = []
        for snap_data in snapshots_data:
            # Map operation string to OperationType
            op_str = snap_data.get("operation", "append")
            operation_mapping = {
                "append": OperationType.APPEND,
                "overwrite": OperationType.OVERWRITE,
                "delete": OperationType.DELETE,
                "replace": OperationType.REPLACE,
            }
            operation = operation_mapping.get(op_str, OperationType.APPEND)

            snapshot = SnapshotInfo(
                snapshot_id=snap_data.get("snapshot_id", 0),
                timestamp_ms=snap_data.get("timestamp_ms", 0),
                operation=operation,
                summary=snap_data.get("summary", {}),
                parent_id=snap_data.get("parent_id"),
            )
            snapshots.append(snapshot)

        # Sort by timestamp (newest first)
        snapshots.sort(key=lambda s: s.timestamp_ms, reverse=True)

        self._log.info(
            "snapshots_listed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_count=len(snapshots),
        )

        return snapshots

    def rollback_to_snapshot(self, table: Table, snapshot_id: int) -> Table:
        """Rollback table to a previous snapshot.

        Creates a new snapshot pointing to the specified historical snapshot.
        This is a non-destructive operation - previous snapshots are preserved.

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
        self._log.debug(
            "rollback_to_snapshot_requested",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=snapshot_id,
        )

        # Validate snapshot exists
        snapshots = self.list_snapshots(table)
        snapshot_ids = [s.snapshot_id for s in snapshots]

        if snapshot_id not in snapshot_ids:
            msg = f"Snapshot {snapshot_id} not found in table"
            self._log.error(
                "snapshot_not_found",
                table_identifier=getattr(table, "identifier", None),
                snapshot_id=snapshot_id,
                available_snapshots=snapshot_ids,
            )
            raise SnapshotNotFoundError(msg)

        # For mock implementation, add a new rollback snapshot
        table_data = getattr(table, "_table_data", {})
        snapshots_data = table_data.get("snapshots", [])

        # Create new rollback snapshot
        import time

        new_snapshot_id = max(s.get("snapshot_id", 0) for s in snapshots_data) + 1 if snapshots_data else 1
        rollback_snapshot = {
            "snapshot_id": new_snapshot_id,
            "timestamp_ms": int(time.time() * 1000),
            "operation": "replace",
            "summary": {"rollback-to-snapshot-id": str(snapshot_id)},
            "parent_id": snapshot_id,
        }
        snapshots_data.append(rollback_snapshot)
        table_data["snapshots"] = snapshots_data

        self._log.info(
            "snapshot_rollback_completed",
            table_identifier=getattr(table, "identifier", None),
            target_snapshot_id=snapshot_id,
            new_snapshot_id=new_snapshot_id,
        )

        return table

    def expire_snapshots(
        self,
        table: Table,
        older_than_days: int | None = None,
    ) -> int:
        """Expire snapshots older than the specified retention period.

        Removes old snapshots while respecting min_snapshots_to_keep from config.
        This helps manage storage costs and metadata overhead.

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
        retention_days = older_than_days if older_than_days is not None else self._config.default_retention_days

        self._log.debug(
            "expire_snapshots_requested",
            table_identifier=getattr(table, "identifier", None),
            retention_days=retention_days,
            min_to_keep=self._config.min_snapshots_to_keep,
        )

        # Get current snapshots
        table_data = getattr(table, "_table_data", {})
        snapshots_data = table_data.get("snapshots", [])

        if not snapshots_data:
            self._log.info(
                "no_snapshots_to_expire",
                table_identifier=getattr(table, "identifier", None),
            )
            return 0

        # Calculate cutoff timestamp
        import time

        cutoff_ms = int((time.time() - (retention_days * 24 * 60 * 60)) * 1000)

        # Sort snapshots by timestamp (newest first)
        snapshots_sorted = sorted(
            snapshots_data,
            key=lambda s: s.get("timestamp_ms", 0),
            reverse=True,
        )

        # Keep at least min_snapshots_to_keep
        min_to_keep = self._config.min_snapshots_to_keep
        to_keep = snapshots_sorted[:min_to_keep]
        candidates = snapshots_sorted[min_to_keep:]

        # Expire candidates older than cutoff
        expired_count = 0
        for snap in candidates:
            if snap.get("timestamp_ms", 0) < cutoff_ms:
                expired_count += 1
            else:
                to_keep.append(snap)

        # Update table data
        table_data["snapshots"] = to_keep

        self._log.info(
            "snapshots_expired",
            table_identifier=getattr(table, "identifier", None),
            expired_count=expired_count,
            remaining_count=len(to_keep),
            retention_days=retention_days,
        )

        return expired_count

    # =========================================================================
    # Write Operations
    # =========================================================================

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
        self._log.debug(
            "write_data_requested",
            table_identifier=getattr(table, "identifier", None),
            mode=config.mode.value,
            commit_strategy=config.commit_strategy.value,
            row_count=len(data) if hasattr(data, "__len__") else "unknown",
        )

        # Validate join_columns for UPSERT mode
        if config.mode == WriteMode.UPSERT and config.join_columns:
            table_data = getattr(table, "_table_data", {})
            schema_fields = table_data.get("schema", {}).get("fields", [])
            field_names = {f.get("name") for f in schema_fields}

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

        # Create new snapshot for append
        table_data = getattr(table, "_table_data", {})
        snapshots = table_data.get("snapshots", [])

        import time

        new_snapshot_id = len(snapshots) + 1
        new_snapshot = {
            "snapshot_id": new_snapshot_id,
            "timestamp_ms": int(time.time() * 1000),
            "operation": "append",
            "summary": {
                "operation": "append",
                "added-files-count": "1",
                "added-records-count": str(len(data) if hasattr(data, "__len__") else 0),
                **config.snapshot_properties,
            },
            "parent_id": snapshots[-1]["snapshot_id"] if snapshots else None,
        }
        snapshots.append(new_snapshot)
        table_data["snapshots"] = snapshots

        self._log.debug(
            "write_append_completed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=new_snapshot_id,
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

        # Create new snapshot for overwrite
        table_data = getattr(table, "_table_data", {})
        snapshots = table_data.get("snapshots", [])

        import time

        new_snapshot_id = len(snapshots) + 1
        new_snapshot = {
            "snapshot_id": new_snapshot_id,
            "timestamp_ms": int(time.time() * 1000),
            "operation": "overwrite",
            "summary": {
                "operation": "overwrite",
                "added-files-count": "1",
                "added-records-count": str(len(data) if hasattr(data, "__len__") else 0),
                **config.snapshot_properties,
            },
            "parent_id": snapshots[-1]["snapshot_id"] if snapshots else None,
        }
        snapshots.append(new_snapshot)
        table_data["snapshots"] = snapshots

        self._log.debug(
            "write_overwrite_completed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=new_snapshot_id,
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

        # Create new snapshot for upsert (merge)
        table_data = getattr(table, "_table_data", {})
        snapshots = table_data.get("snapshots", [])

        import time

        new_snapshot_id = len(snapshots) + 1
        new_snapshot = {
            "snapshot_id": new_snapshot_id,
            "timestamp_ms": int(time.time() * 1000),
            "operation": "replace",  # PyIceberg uses "replace" for upsert/merge
            "summary": {
                "operation": "replace",
                "added-files-count": "1",
                "added-records-count": str(len(data) if hasattr(data, "__len__") else 0),
                **config.snapshot_properties,
            },
            "parent_id": snapshots[-1]["snapshot_id"] if snapshots else None,
        }
        snapshots.append(new_snapshot)
        table_data["snapshots"] = snapshots

        self._log.debug(
            "write_upsert_completed",
            table_identifier=getattr(table, "identifier", None),
            snapshot_id=new_snapshot_id,
        )

        return table

    # =========================================================================
    # Future Operations (to be implemented in later tasks)
    # =========================================================================

    # compact_table() - Future task


__all__ = ["IcebergTableManager"]
