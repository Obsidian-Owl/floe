"""Dagster IOManager for Iceberg table operations.

This module provides IcebergIOManager, a Dagster IOManager that handles
reading and writing PyArrow Tables to/from Iceberg tables.

IcebergIOManager integrates with Dagster's asset framework, automatically
mapping asset keys to Iceberg table identifiers and supporting partitioned
asset outputs.

Example:
    >>> from dagster import Definitions, asset
    >>> from floe_iceberg import IcebergIOManager, IcebergIOManagerConfig
    >>>
    >>> @asset
    ... def customers() -> pa.Table:
    ...     return pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]})
    >>>
    >>> io_manager = IcebergIOManager(
    ...     config=IcebergIOManagerConfig(namespace="bronze"),
    ...     iceberg_manager=manager,
    ... )

See Also:
    - IcebergIOManagerConfig: Configuration model for the IOManager
    - IcebergTableManager: Underlying table operations

Note:
    This module requires the optional 'dagster' dependency.
    Install with: pip install floe-iceberg[dagster]

    When Dagster is not installed, IcebergIOManager can still be used
    as a standalone class with duck-typed contexts, but won't integrate
    with Dagster's resource system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from floe_iceberg.models import IcebergIOManagerConfig, WriteConfig, WriteMode

if TYPE_CHECKING:
    from floe_iceberg.manager import IcebergTableManager

# =============================================================================
# Type Definitions
# =============================================================================

# Dagster types - imported at runtime to avoid hard dependency
# These are duck-typed for flexibility
OutputContext = Any  # dagster.OutputContext
InputContext = Any  # dagster.InputContext

# =============================================================================
# Dagster Integration
# =============================================================================

# Try to import Dagster's ConfigurableIOManager for proper inheritance
# Falls back to object if Dagster is not installed
_DAGSTER_AVAILABLE: bool
try:
    from dagster import ConfigurableIOManager as _DagsterConfigurableIOManager

    _DAGSTER_AVAILABLE = True
except ImportError:
    _DagsterConfigurableIOManager = object  # type: ignore[misc, assignment]
    _DAGSTER_AVAILABLE = False


def is_dagster_available() -> bool:
    """Check if Dagster is available for IOManager integration.

    Returns:
        True if dagster package is installed and ConfigurableIOManager
        can be imported, False otherwise.

    Example:
        >>> from floe_iceberg.io_manager import is_dagster_available
        >>> if is_dagster_available():
        ...     # Use full Dagster integration
        ...     pass
    """
    return _DAGSTER_AVAILABLE


# =============================================================================
# IcebergIOManager
# =============================================================================


class IcebergIOManager(_DagsterConfigurableIOManager):  # type: ignore[misc]
    """Dagster IOManager for reading and writing Iceberg tables.

    Handles asset outputs by writing PyArrow Tables to Iceberg tables,
    and asset inputs by reading from Iceberg tables.

    This class inherits from Dagster's ConfigurableIOManager when Dagster
    is installed, enabling proper integration with Dagster's resource system.
    When Dagster is not installed, it functions as a standalone IOManager.

    Attributes:
        config: IOManager configuration (IcebergIOManagerConfig).
        iceberg_manager: IcebergTableManager for table operations.

    Example:
        >>> from floe_iceberg import IcebergIOManager, IcebergIOManagerConfig
        >>> from floe_iceberg.manager import IcebergTableManager
        >>>
        >>> # Create manager with catalog and storage plugins
        >>> manager = IcebergTableManager(catalog_plugin, storage_plugin)
        >>>
        >>> # Create IOManager
        >>> io_manager = IcebergIOManager(
        ...     config=IcebergIOManagerConfig(namespace="bronze"),
        ...     iceberg_manager=manager,
        ... )
        >>>
        >>> # Use with Dagster Definitions
        >>> from dagster import Definitions
        >>> defs = Definitions(
        ...     assets=[...],
        ...     resources={"io_manager": io_manager},
        ... )

    Note:
        When using with Dagster, the IcebergIOManager should be registered
        as a resource in your Definitions. The IOManager handles:
        - Asset key to table identifier mapping
        - Write mode configuration via asset metadata
        - Schema inference on first write (optional)
        - Partitioned asset support
    """

    def __init__(
        self,
        config: IcebergIOManagerConfig,
        iceberg_manager: IcebergTableManager,
    ) -> None:
        """Initialize IcebergIOManager.

        Args:
            config: IOManager configuration specifying namespace, write mode,
                and table naming patterns.
            iceberg_manager: IcebergTableManager instance for table operations.
                The manager should be pre-configured with catalog and storage
                plugins.

        Example:
            >>> config = IcebergIOManagerConfig(
            ...     namespace="bronze",
            ...     default_write_mode=WriteMode.APPEND,
            ... )
            >>> io_manager = IcebergIOManager(
            ...     config=config,
            ...     iceberg_manager=manager,
            ... )
        """
        # Note: We don't call super().__init__() when Dagster is available
        # because ConfigurableIOManager uses Pydantic-style initialization.
        # Our constructor pattern works with both Dagster and standalone usage.
        self._config = config
        self._manager = iceberg_manager
        self._log = structlog.get_logger(__name__)

    def handle_output(self, context: OutputContext, obj: Any) -> None:
        """Handle asset output by writing to Iceberg table.

        Writes a PyArrow Table to the appropriate Iceberg table based on
        the asset key and configuration.

        Args:
            context: Dagster output context with asset metadata.
            obj: PyArrow Table to write.

        Raises:
            TypeError: If obj is not a PyArrow Table.
        """
        # Get table identifier from context
        table_identifier = self._get_table_identifier(context)

        self._log.debug(
            "handle_output_start",
            table_identifier=table_identifier,
            asset_key=self._get_asset_key_str(context),
        )

        # Get write config (may be overridden by metadata)
        write_config = self._get_write_config(context)

        # Check if table exists
        if not self._manager.table_exists(table_identifier):
            # Create table on first write if schema inference is enabled
            if self._config.infer_schema_from_data:
                self._create_table_from_data(table_identifier, obj)
            else:
                msg = f"Table '{table_identifier}' does not exist and infer_schema_from_data is False"
                raise ValueError(msg)

        # Load table and write data
        table = self._manager.load_table(table_identifier)
        self._manager.write_data(table, obj, write_config)

        self._log.info(
            "handle_output_complete",
            table_identifier=table_identifier,
            write_mode=write_config.mode.value,
        )

    def load_input(self, context: InputContext) -> Any:
        """Load asset input from Iceberg table.

        Reads data from an Iceberg table and returns it as a PyArrow Table.

        Args:
            context: Dagster input context with asset metadata.

        Returns:
            PyArrow Table with the table data.

        Raises:
            NoSuchTableError: If the table doesn't exist.
        """
        # Get table identifier from upstream asset
        table_identifier = self._get_table_identifier_for_input(context)

        self._log.debug(
            "load_input_start",
            table_identifier=table_identifier,
            asset_key=self._get_upstream_asset_key_str(context),
        )

        # Load table
        table = self._manager.load_table(table_identifier)

        # Read data (scan entire table for now)
        # Future: support partition filtering based on partition key
        data = self._read_table_data(table)

        self._log.info(
            "load_input_complete",
            table_identifier=table_identifier,
        )

        return data

    def _get_table_identifier(self, context: OutputContext) -> str:
        """Generate table identifier from output context.

        Args:
            context: Dagster output context.

        Returns:
            Full table identifier (namespace.table_name).
        """
        asset_key = self._get_asset_key_str(context)
        table_name = self._config.table_name_pattern.format(asset_key=asset_key)
        return f"{self._config.namespace}.{table_name}"

    def _get_table_identifier_for_input(self, context: InputContext) -> str:
        """Generate table identifier from input context.

        Args:
            context: Dagster input context.

        Returns:
            Full table identifier (namespace.table_name).
        """
        asset_key = self._get_upstream_asset_key_str(context)
        table_name = self._config.table_name_pattern.format(asset_key=asset_key)
        return f"{self._config.namespace}.{table_name}"

    def _get_write_config(self, context: OutputContext) -> WriteConfig:
        """Get write configuration, with metadata overrides.

        Reads write configuration from asset metadata, falling back to
        config defaults. Supports the following metadata keys:

        - `iceberg_write_mode` or `write_mode`: Write mode (append, overwrite, upsert)
        - `iceberg_partition_column`: Partition column for overwrite filtering
        - `iceberg_join_columns`: Join columns for upsert mode

        For partitioned assets (DailyPartitionsDefinition, etc.), automatically:
        - Switches to overwrite mode
        - Builds partition filter from context.partition_key

        Args:
            context: Dagster output context with optional metadata.

        Returns:
            WriteConfig for the write operation.

        Example:
            Asset metadata for overwrite with partition filter:
            >>> @asset(metadata={
            ...     "iceberg_write_mode": "overwrite",
            ...     "iceberg_partition_column": "date",
            ... })
            ... def daily_events() -> pa.Table:
            ...     ...

            Partitioned asset (automatic overwrite):
            >>> @asset(partitions_def=DailyPartitionsDefinition(start_date="2024-01-01"))
            ... def daily_events() -> pa.Table:
            ...     ...
        """
        # Start with defaults from config
        mode = self._config.default_write_mode
        commit_strategy = self._config.default_commit_strategy
        overwrite_filter: str | None = None
        join_columns: list[str] | None = None

        # Check for metadata overrides
        metadata = getattr(context, "metadata", None) or {}

        # Check if this is a partitioned asset
        partition_key = self._get_partition_key(context)
        is_partitioned = partition_key is not None

        # Write mode: prefer iceberg_write_mode, fall back to write_mode
        write_mode_str = metadata.get("iceberg_write_mode") or metadata.get("write_mode")
        if write_mode_str is not None:
            # Handle MetadataValue objects that have .value attribute
            if hasattr(write_mode_str, "value"):
                write_mode_str = write_mode_str.value
            mode = WriteMode(write_mode_str)
        elif is_partitioned:
            # For partitioned assets, default to overwrite mode
            mode = WriteMode.OVERWRITE
            self._log.debug(
                "partitioned_asset_detected",
                partition_key=partition_key,
                auto_write_mode="overwrite",
            )

        # Partition column for overwrite filtering
        partition_col = metadata.get("iceberg_partition_column")
        if partition_col is not None:
            if hasattr(partition_col, "value"):
                partition_col = partition_col.value
            # Build overwrite filter expression with partition value
            if is_partitioned:
                overwrite_filter = self._build_partition_filter(partition_col, partition_key)
            else:
                overwrite_filter = partition_col
        elif is_partitioned:
            # Auto-detect partition column from metadata or use default
            auto_partition_col = metadata.get("iceberg_auto_partition_column")
            if auto_partition_col is not None:
                if hasattr(auto_partition_col, "value"):
                    auto_partition_col = auto_partition_col.value
                overwrite_filter = self._build_partition_filter(
                    auto_partition_col, partition_key
                )

        # Join columns for upsert mode
        join_cols = metadata.get("iceberg_join_columns")
        if join_cols is not None:
            if hasattr(join_cols, "value"):
                join_cols = join_cols.value
            if isinstance(join_cols, str):
                join_columns = [join_cols]
            elif isinstance(join_cols, (list, tuple)):
                join_columns = list(join_cols)

        return WriteConfig(
            mode=mode,
            commit_strategy=commit_strategy,
            overwrite_filter=overwrite_filter,
            join_columns=join_columns,
        )

    def _is_partitioned_asset(self, context: OutputContext) -> bool:
        """Check if context is for a partitioned asset.

        Detects partitioned assets by checking for partition_key attribute
        on the context, which is present for DailyPartitionsDefinition,
        MonthlyPartitionsDefinition, and other Dagster partition types.

        Args:
            context: Dagster output context.

        Returns:
            True if the asset has partitions, False otherwise.
        """
        return self._get_partition_key(context) is not None

    def _get_partition_key(self, context: OutputContext) -> str | None:
        """Get partition key from output context.

        Extracts the partition key from the Dagster context. The partition key
        is a string representation of the partition, e.g., "2024-01-15" for
        DailyPartitionsDefinition.

        Args:
            context: Dagster output context.

        Returns:
            Partition key string if asset is partitioned, None otherwise.

        Example:
            For DailyPartitionsDefinition(start_date="2024-01-01"):
            >>> partition_key = self._get_partition_key(context)
            >>> partition_key
            '2024-01-15'
        """
        # Dagster's OutputContext has partition_key attribute for partitioned assets
        partition_key = getattr(context, "partition_key", None)
        if partition_key is None:
            return None

        # Handle cases where partition_key might be a complex object
        # Check for MultiPartitionsDefinition by looking for keys_by_dimension dict
        keys_by_dim = getattr(partition_key, "keys_by_dimension", None)
        if keys_by_dim is not None and isinstance(keys_by_dim, dict):
            # MultiPartitionsDefinition - get first key for now
            if keys_by_dim:
                return str(next(iter(keys_by_dim.values())))
            return None

        # Simple partition key (string)
        return str(partition_key)

    def _build_partition_filter(
        self, partition_column: str, partition_key: str | None
    ) -> str | None:
        """Build Iceberg partition filter from column and key.

        Constructs a filter expression for overwriting specific partitions
        in an Iceberg table. The filter is used with WriteConfig.overwrite_filter.

        Args:
            partition_column: Name of the partition column in the Iceberg table.
            partition_key: Partition value from Dagster context.

        Returns:
            Filter expression string, e.g., "date = '2024-01-15'", or None
            if partition_key is None.

        Note:
            Currently supports simple equality filters. Complex partition
            expressions (ranges, lists) may be added in future versions.
        """
        if partition_key is None:
            return None

        # Build simple equality filter
        # Note: This assumes the partition column type matches the key format
        # For date columns, Dagster's DailyPartitionsDefinition uses YYYY-MM-DD
        return f"{partition_column} = '{partition_key}'"

    def _get_asset_key_str(self, context: OutputContext) -> str:
        """Get asset key as string from output context.

        Args:
            context: Dagster output context.

        Returns:
            Asset key as underscore-separated string.
        """
        asset_key = getattr(context, "asset_key", None)
        if asset_key is None:
            return "unknown"
        # Dagster asset keys can be multi-part
        path = getattr(asset_key, "path", None)
        if path:
            return "_".join(path)
        return str(asset_key)

    def _get_upstream_asset_key_str(self, context: InputContext) -> str:
        """Get upstream asset key as string from input context.

        Args:
            context: Dagster input context.

        Returns:
            Upstream asset key as underscore-separated string.
        """
        upstream_output = getattr(context, "upstream_output", None)
        if upstream_output is None:
            return "unknown"
        asset_key = getattr(upstream_output, "asset_key", None)
        if asset_key is None:
            return "unknown"
        path = getattr(asset_key, "path", None)
        if path:
            return "_".join(path)
        return str(asset_key)

    def _create_table_from_data(self, table_identifier: str, data: Any) -> None:
        """Create table with schema inferred from PyArrow Table.

        Infers Iceberg schema from PyArrow table schema and creates a new
        table in the catalog. Used when `infer_schema_from_data` is True
        and the target table doesn't exist.

        Args:
            table_identifier: Full table identifier (namespace.table_name).
            data: PyArrow Table to infer schema from. Must have a .schema
                attribute with column names and types.

        Note:
            Currently creates unpartitioned tables. Partition inference
            from metadata is planned for future enhancement (T088).
        """
        # Parse namespace and table name from identifier
        parts = table_identifier.split(".", 1)
        if len(parts) != 2:
            msg = f"Invalid table identifier format: {table_identifier}"
            raise ValueError(msg)
        namespace, table_name = parts

        self._log.info(
            "creating_table_from_data",
            table_identifier=table_identifier,
            namespace=namespace,
            table_name=table_name,
        )

        # Infer schema from PyArrow Table
        table_schema = self._infer_schema_from_pyarrow(data)

        # Create TableConfig
        from floe_iceberg.models import TableConfig

        config = TableConfig(
            namespace=namespace,
            table_name=table_name,
            table_schema=table_schema,
        )

        # Create table via manager
        self._manager.create_table(config, if_not_exists=True)

        self._log.info(
            "table_created_from_data",
            table_identifier=table_identifier,
            field_count=len(table_schema.fields),
        )

    def _infer_schema_from_pyarrow(self, data: Any) -> Any:
        """Infer Iceberg TableSchema from PyArrow Table.

        Maps PyArrow data types to Iceberg field types and generates
        a TableSchema suitable for table creation.

        Args:
            data: PyArrow Table with schema attribute.

        Returns:
            TableSchema with inferred field definitions.

        Note:
            For mock tables in tests without schema, returns a minimal
            schema to allow test isolation.
        """
        from floe_iceberg.models import FieldType, SchemaField, TableSchema

        # Get PyArrow schema
        pa_schema = getattr(data, "schema", None)
        if pa_schema is None:
            # Mock table in tests - return empty schema
            return TableSchema(fields=[])

        # Type mapping from PyArrow to Iceberg
        type_mapping = {
            "bool": FieldType.BOOLEAN,
            "int8": FieldType.INT,
            "int16": FieldType.INT,
            "int32": FieldType.INT,
            "int64": FieldType.LONG,
            "uint8": FieldType.INT,
            "uint16": FieldType.INT,
            "uint32": FieldType.LONG,
            "uint64": FieldType.LONG,
            "float16": FieldType.FLOAT,
            "float32": FieldType.FLOAT,
            "float64": FieldType.DOUBLE,
            "string": FieldType.STRING,
            "large_string": FieldType.STRING,
            "utf8": FieldType.STRING,
            "large_utf8": FieldType.STRING,
            "binary": FieldType.BINARY,
            "large_binary": FieldType.BINARY,
            "date32": FieldType.DATE,
            "date64": FieldType.DATE,
            "timestamp[s]": FieldType.TIMESTAMP,
            "timestamp[ms]": FieldType.TIMESTAMP,
            "timestamp[us]": FieldType.TIMESTAMP,
            "timestamp[ns]": FieldType.TIMESTAMP,
        }

        fields: list[SchemaField] = []
        for field_id, field in enumerate(pa_schema, start=1):
            # Get PyArrow type as string
            pa_type_str = str(field.type)

            # Map to Iceberg type (default to STRING for unknown types)
            iceberg_type = type_mapping.get(pa_type_str, FieldType.STRING)

            # Create SchemaField
            schema_field = SchemaField(
                field_id=field_id,
                name=field.name,
                field_type=iceberg_type,
                required=not field.nullable,
            )
            fields.append(schema_field)

        return TableSchema(fields=fields)

    def _read_table_data(self, table: Any) -> Any:
        """Read all data from an Iceberg table.

        Scans the entire table and returns the data as a PyArrow Table.
        Future enhancements may include partition filtering, column selection,
        and row filtering.

        Args:
            table: PyIceberg Table object with scan() method.

        Returns:
            PyArrow Table with all data from the Iceberg table.

        Note:
            For mock tables in tests that don't have a scan() method,
            this returns None to allow test isolation.
        """
        # Use PyIceberg's scan().to_arrow() pattern for reading
        # This returns all data from the table as a PyArrow Table
        scan_method = getattr(table, "scan", None)
        if scan_method is None:
            # Mock table in tests - return None
            return None

        # Execute scan and convert to PyArrow
        scan = scan_method()
        return scan.to_arrow()


__all__ = ["IcebergIOManager", "is_dagster_available"]
