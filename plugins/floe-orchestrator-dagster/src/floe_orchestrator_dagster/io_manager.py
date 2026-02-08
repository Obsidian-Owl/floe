"""IcebergIOManager - Dagster IOManager for Iceberg table storage.

This module provides a Dagster-specific IOManager that handles Iceberg table
operations for asset materialization. It wraps IcebergTableManager from
floe-iceberg to provide seamless integration between Dagster orchestration
and Iceberg storage.

Note: This IOManager is Dagster-specific. Other orchestrators (e.g., Airflow)
use dbt profiles.yml for storage configuration per ADR-0009.

Example:
    >>> from floe_orchestrator_dagster.io_manager import IcebergIOManager
    >>> from floe_iceberg import IcebergTableManager
    >>>
    >>> @asset(io_manager_key="iceberg")
    >>> def customers_silver(customers_bronze: pa.Table) -> pa.Table:
    ...     return transform(customers_bronze)
    >>>
    >>> defs = Definitions(
    ...     assets=[customers_silver],
    ...     resources={
    ...         "iceberg": IcebergIOManager(
    ...             table_manager=table_manager,
    ...             namespace="silver",
    ...         ),
    ...     },
    ... )

Requirements:
    FR-037: Handle asset outputs by writing to Iceberg tables
    FR-038: Support configurable write modes (append, overwrite, upsert)
    FR-039: Load asset inputs from Iceberg tables
    FR-040: Support partitioned assets

See Also:
    - specs/4d-storage-plugin/contracts/iceberg_io_manager_api.md
    - packages/floe-iceberg/src/floe_iceberg/manager.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from dagster import ConfigurableIOManager
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pyiceberg.expressions import BooleanExpression, EqualTo, Reference
from pyiceberg.expressions import literal as iceberg_literal

if TYPE_CHECKING:
    from floe_iceberg import IcebergTableManager

# =============================================================================
# Configuration Models
# =============================================================================


class IcebergIOManagerConfig(BaseModel):
    """Configuration for IcebergIOManager.

    Defines default behaviors for Iceberg table operations in Dagster.

    Attributes:
        namespace: Default namespace for tables (e.g., 'silver', 'gold').
        default_write_mode: Default write mode for outputs (append, overwrite, upsert).
        infer_schema_from_data: Create tables with inferred schema on first write.

    Example:
        >>> config = IcebergIOManagerConfig(
        ...     namespace="silver",
        ...     default_write_mode="append",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    namespace: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Default namespace for Iceberg tables",
    )
    default_write_mode: str = Field(
        default="append",
        pattern=r"^(append|overwrite|upsert)$",
        description="Default write mode for outputs",
    )
    infer_schema_from_data: bool = Field(
        default=True,
        description="Infer schema from data on first write (creates table if needed)",
    )


# =============================================================================
# Metadata Keys
# =============================================================================

# Asset metadata keys for customizing IOManager behavior
ICEBERG_TABLE_KEY = "iceberg_table"
ICEBERG_NAMESPACE_KEY = "iceberg_namespace"
ICEBERG_WRITE_MODE_KEY = "iceberg_write_mode"
ICEBERG_PARTITION_FILTER_KEY = "iceberg_partition_filter"
ICEBERG_UPSERT_KEYS_KEY = "iceberg_upsert_keys"
ICEBERG_PARTITION_COLUMN_KEY = "iceberg_partition_column"
ICEBERG_SNAPSHOT_PROPS_KEY = "iceberg_snapshot_props"


# =============================================================================
# IcebergIOManager Implementation
# =============================================================================


class IcebergIOManager(ConfigurableIOManager):
    """Dagster IOManager for Iceberg tables.

    Handles asset outputs by writing to configured Iceberg tables and
    asset inputs by reading from tables. Supports configurable write
    modes and partitioned assets.

    This class is Dagster-specific and NOT orchestrator-agnostic.
    It wraps IcebergTableManager from floe-iceberg for table operations.

    Inherits from Dagster's ConfigurableIOManager for proper resource
    management and Pydantic integration.

    Attributes:
        table_manager: IcebergTableManager instance for table operations.
        config: IcebergIOManagerConfig with defaults and namespace.

    Example:
        >>> from floe_orchestrator_dagster.io_manager import IcebergIOManager
        >>>
        >>> @asset(io_manager_key="iceberg")
        >>> def customers_silver(customers_bronze: pa.Table) -> pa.Table:
        ...     return transform(customers_bronze)
        >>>
        >>> defs = Definitions(
        ...     assets=[customers_silver],
        ...     resources={
        ...         "iceberg": IcebergIOManager(
        ...             table_manager=table_manager,
        ...             config=IcebergIOManagerConfig(namespace="silver"),
        ...         ),
        ...     },
        ... )

    Requirements:
        FR-037: Handle asset outputs by writing to Iceberg tables
        FR-038: Support configurable write modes
        FR-039: Load asset inputs from Iceberg tables
        FR-040: Support partitioned assets
    """

    # Private attributes (not Pydantic config fields, managed internally)
    _table_manager: Any = PrivateAttr()
    _config: IcebergIOManagerConfig = PrivateAttr()
    _log: Any = PrivateAttr()

    def __init__(
        self,
        table_manager: IcebergTableManager,
        config: IcebergIOManagerConfig,
        **data: Any,
    ) -> None:
        """Initialize IcebergIOManager with table manager and config.

        Args:
            table_manager: IcebergTableManager instance for Iceberg operations.
            config: IcebergIOManagerConfig with namespace and defaults.
            **data: Additional kwargs passed to ConfigurableIOManager base.

        Raises:
            TypeError: If table_manager doesn't have required methods.
        """
        super().__init__(**data)
        self._validate_table_manager(table_manager)
        self._table_manager = table_manager
        self._config = config
        self._log = structlog.get_logger(__name__).bind(
            namespace=config.namespace,
            default_write_mode=config.default_write_mode,
        )
        self._log.debug("iceberg_io_manager_initialized")

    def _validate_table_manager(self, table_manager: Any) -> None:
        """Validate table manager has required interface.

        Args:
            table_manager: Manager to validate.

        Raises:
            TypeError: If manager doesn't have required methods.

        Security:
            MEDIUM-01 remediation: Error message uses static text to avoid
            exposing internal attribute names in error conditions.
        """
        required_attrs = ["load_table", "table_exists", "write_data", "create_table"]
        missing_attrs = [
            attr for attr in required_attrs if not hasattr(table_manager, attr)
        ]
        if missing_attrs:
            # Security: Use static message to avoid exposing internal details
            msg = "table_manager is missing required interface methods"
            raise TypeError(msg)

    @property
    def table_manager(self) -> IcebergTableManager:
        """Return the table manager instance."""
        return self._table_manager

    @property
    def config(self) -> IcebergIOManagerConfig:
        """Return the IOManager configuration."""
        return self._config

    def handle_output(
        self,
        context: Any,  # OutputContext
        obj: Any,  # PyArrow Table
    ) -> None:
        """Write asset output to Iceberg table.

        Determines table identifier from asset key and namespace.
        Creates table if it doesn't exist (with schema inference).
        Writes data using configured write mode.

        Args:
            context: Dagster OutputContext with asset info.
            obj: PyArrow Table to write.

        Raises:
            WriteError: If write operation fails.
            ValidationError: If data is invalid.

        Requirements:
            FR-037: Handle asset outputs by writing to Iceberg tables
            FR-038: Support configurable write modes

        Example:
            >>> @asset(io_manager_key="iceberg")
            >>> def customers() -> pa.Table:
            ...     return pa.Table.from_pylist([...])
            >>> # Writes to {namespace}.customers table
        """
        identifier = self._get_table_identifier(context)
        write_config = self._get_write_config(context)

        self._log.debug(
            "handle_output_started",
            asset_key=str(context.asset_key) if hasattr(context, "asset_key") else None,
            table_identifier=identifier,
            write_mode=write_config.mode.value,
            row_count=len(obj) if hasattr(obj, "__len__") else "unknown",
        )

        # Check if table exists, create if not
        if not self._table_manager.table_exists(identifier):
            if self._config.infer_schema_from_data:
                self._create_table_from_data(identifier, obj, context)
            else:
                from floe_iceberg.errors import NoSuchTableError

                # Security: MEDIUM-01 remediation - Use static message to avoid
                # exposing table identifiers in error conditions
                msg = "Table does not exist and infer_schema_from_data=False"
                raise NoSuchTableError(msg)

        # Load table and write data
        table = self._table_manager.load_table(identifier)
        self._table_manager.write_data(table, obj, write_config)

        self._log.info(
            "handle_output_completed",
            table_identifier=identifier,
            write_mode=write_config.mode.value,
        )

    def load_input(
        self,
        context: Any,  # InputContext
    ) -> Any:  # PyArrow Table
        """Load asset input from Iceberg table.

        Reads table data as PyArrow Table. Supports partition filtering
        based on upstream partition.

        Args:
            context: Dagster InputContext with upstream asset info.

        Returns:
            PyArrow Table with data from Iceberg table.

        Raises:
            NoSuchTableError: If upstream table doesn't exist.

        Requirements:
            FR-039: Load asset inputs from Iceberg tables

        Example:
            >>> @asset(io_manager_key="iceberg")
            >>> def customers_silver(customers_bronze: pa.Table) -> pa.Table:
            ...     return transform(customers_bronze)
            >>> # Reads from {namespace}.customers_bronze table
        """
        identifier = self._get_table_identifier_for_input(context)

        self._log.debug(
            "load_input_started",
            upstream_asset_key=(
                str(context.upstream_output.asset_key)
                if hasattr(context, "upstream_output")
                and hasattr(context.upstream_output, "asset_key")
                else None
            ),
            table_identifier=identifier,
        )

        # Load table
        table = self._table_manager.load_table(identifier)

        # Get partition filter if this is a partitioned asset
        partition_filter = self._get_partition_filter_for_input(context)

        # Scan table and return as PyArrow
        scan = table.scan()
        if partition_filter is not None:
            scan = scan.filter(partition_filter)

        result = scan.to_arrow()

        self._log.info(
            "load_input_completed",
            table_identifier=identifier,
            row_count=len(result) if hasattr(result, "__len__") else "unknown",
        )

        return result

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    @staticmethod
    def _unwrap_metadata_values(metadata: Any) -> dict[str, Any]:
        """Unwrap Dagster MetadataValue wrappers to raw Python values.

        Dagster wraps Output(metadata={...}) values in MetadataValue objects
        (e.g., TextMetadataValue(text='overwrite')). This extracts the
        underlying raw values so the IOManager can use them directly.

        Args:
            metadata: Raw metadata dict (may contain MetadataValue objects).

        Returns:
            Dict with raw Python values.
        """
        if not metadata:
            return {}
        result: dict[str, Any] = {}
        for key, value in metadata.items():
            # Dagster MetadataValue objects expose a .value property
            if hasattr(value, "value") and not isinstance(
                value, (str, bytes, int, float, bool)
            ):
                result[key] = value.value
            else:
                result[key] = value
        return result

    @staticmethod
    def _get_merged_metadata(context: Any) -> dict[str, Any]:
        """Get merged metadata from Dagster OutputContext.

        Merges definition_metadata (from @asset decorator) with output_metadata
        (from Output() return value). Output metadata takes precedence for
        runtime overrides like write_mode.

        Args:
            context: Dagster OutputContext.

        Returns:
            Merged metadata dict with raw Python values.
        """
        definition_meta = IcebergIOManager._unwrap_metadata_values(
            getattr(context, "definition_metadata", None),
        )
        output_meta = IcebergIOManager._unwrap_metadata_values(
            getattr(context, "output_metadata", None),
        )
        # Merge with output_metadata taking precedence (runtime overrides static)
        return {**definition_meta, **output_meta}

    def _get_table_identifier(self, context: Any) -> str:
        """Generate table identifier from output context.

        Uses namespace from config and asset key for table name.
        Supports custom table name via metadata.

        Args:
            context: Dagster OutputContext.

        Returns:
            Full table identifier (e.g., "silver.customers").
        """
        # Check for custom table name in metadata
        metadata = self._get_merged_metadata(context)
        custom_table = metadata.get(ICEBERG_TABLE_KEY)
        custom_namespace = metadata.get(ICEBERG_NAMESPACE_KEY)

        namespace = custom_namespace or self._config.namespace

        if custom_table:
            table_name = custom_table
        elif hasattr(context, "asset_key"):
            # Use asset key as table name (last part if hierarchical)
            asset_key = context.asset_key
            if hasattr(asset_key, "path") and asset_key.path:
                table_name = asset_key.path[-1]
            else:
                table_name = str(asset_key).replace("/", "_")
        else:
            msg = "Cannot determine table name: no asset_key or iceberg_table metadata"
            raise ValueError(msg)

        return f"{namespace}.{table_name}"

    def _get_table_identifier_for_input(self, context: Any) -> str:
        """Generate table identifier from input context.

        Args:
            context: Dagster InputContext.

        Returns:
            Full table identifier for the upstream table.
        """
        # Get upstream asset key
        if hasattr(context, "upstream_output") and hasattr(
            context.upstream_output, "asset_key"
        ):
            upstream_asset_key = context.upstream_output.asset_key

            # Read upstream definition_metadata only (not output_metadata) because
            # Dagster does not expose output_metadata on InputContext (dagster#20094)
            upstream_metadata = self._unwrap_metadata_values(
                getattr(context.upstream_output, "definition_metadata", None),
            )
            custom_table = upstream_metadata.get(ICEBERG_TABLE_KEY)
            custom_namespace = upstream_metadata.get(ICEBERG_NAMESPACE_KEY)

            namespace = custom_namespace or self._config.namespace

            if custom_table:
                table_name = custom_table
            elif hasattr(upstream_asset_key, "path") and upstream_asset_key.path:
                table_name = upstream_asset_key.path[-1]
            else:
                table_name = str(upstream_asset_key).replace("/", "_")

            return f"{namespace}.{table_name}"

        msg = "Cannot determine upstream table: no upstream_output in context"
        raise ValueError(msg)

    def _get_write_config(self, context: Any) -> Any:
        """Get write configuration from context metadata.

        Extracts write mode, commit strategy, and snapshot properties
        from asset metadata. Falls back to IOManager defaults.

        Args:
            context: Dagster OutputContext.

        Returns:
            WriteConfig for the write operation.
        """
        from floe_iceberg.models import WriteConfig, WriteMode

        metadata = self._get_merged_metadata(context)

        # Get write mode from metadata or default
        write_mode_str = metadata.get(
            ICEBERG_WRITE_MODE_KEY, self._config.default_write_mode
        )
        write_mode = WriteMode(write_mode_str)

        # Get optional configuration
        overwrite_filter = metadata.get(ICEBERG_PARTITION_FILTER_KEY)
        upsert_keys = metadata.get(ICEBERG_UPSERT_KEYS_KEY)
        snapshot_props = metadata.get(ICEBERG_SNAPSHOT_PROPS_KEY, {})

        # Build WriteConfig
        config_kwargs: dict[str, Any] = {
            "mode": write_mode,
            "snapshot_properties": snapshot_props,
        }

        if overwrite_filter is not None:
            config_kwargs["overwrite_filter"] = overwrite_filter

        if upsert_keys is not None:
            config_kwargs["join_columns"] = upsert_keys

        # Handle partitioned assets - map Dagster partition to Iceberg partition
        # Use has_partition_key (not hasattr) because Dagster's partition_key property
        # raises CheckError when accessed on non-partitioned runs.
        if (
            getattr(context, "has_partition_key", False)
            and context.partition_key is not None
        ):
            partition_column = metadata.get(ICEBERG_PARTITION_COLUMN_KEY)
            if partition_column and write_mode == WriteMode.OVERWRITE:
                # Build expression and convert to string for WriteConfig compatibility
                # PyIceberg will parse this back into an expression
                expr = EqualTo(
                    Reference(partition_column),
                    iceberg_literal(context.partition_key),
                )
                config_kwargs["overwrite_filter"] = str(expr)

        return WriteConfig(**config_kwargs)

    def _get_partition_filter_for_input(self, context: Any) -> BooleanExpression | None:
        """Get partition filter for input context.

        Args:
            context: Dagster InputContext.

        Returns:
            PyIceberg BooleanExpression for partition filtering or None.
        """
        # Check if upstream was a partitioned asset
        if hasattr(context, "upstream_output"):
            # Read upstream definition_metadata only (not output_metadata) because
            # Dagster does not expose output_metadata on InputContext (dagster#20094)
            upstream_metadata = self._unwrap_metadata_values(
                getattr(context.upstream_output, "definition_metadata", None),
            )
            partition_column = upstream_metadata.get(ICEBERG_PARTITION_COLUMN_KEY)

            if (
                partition_column
                and getattr(context, "has_partition_key", False)
                and context.partition_key
            ):
                # Use PyIceberg expression API (type-safe, no parsing)
                return EqualTo(
                    Reference(partition_column),
                    iceberg_literal(context.partition_key),
                )

        return None

    def _create_table_from_data(
        self,
        identifier: str,
        data: Any,  # PyArrow Table
        context: Any,  # OutputContext
    ) -> None:
        """Create table with schema inferred from data.

        Args:
            identifier: Full table identifier.
            data: PyArrow Table to infer schema from.
            context: Dagster OutputContext.
        """
        from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

        # Parse identifier
        parts = identifier.rsplit(".", 1)
        if len(parts) != 2:
            msg = f"Invalid identifier format: {identifier}"
            raise ValueError(msg)

        namespace, table_name = parts

        # Infer schema from PyArrow table
        fields = []
        pyarrow_schema = data.schema

        # Map PyArrow types to Iceberg FieldTypes
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
            "float": FieldType.FLOAT,
            "float64": FieldType.DOUBLE,
            "double": FieldType.DOUBLE,
            "string": FieldType.STRING,
            "large_string": FieldType.STRING,
            "utf8": FieldType.STRING,
            "date32": FieldType.DATE,
            "date64": FieldType.DATE,
            "timestamp[s]": FieldType.TIMESTAMP,
            "timestamp[ms]": FieldType.TIMESTAMP,
            "timestamp[us]": FieldType.TIMESTAMP,
            "timestamp[ns]": FieldType.TIMESTAMP,
            "binary": FieldType.BINARY,
            "large_binary": FieldType.BINARY,
        }

        for i, field in enumerate(pyarrow_schema):
            field_type_str = str(field.type)

            # Handle timestamp with timezone
            if field_type_str.startswith("timestamp[") and "tz=" in field_type_str:
                iceberg_type = FieldType.TIMESTAMPTZ
            else:
                iceberg_type = type_mapping.get(field_type_str, FieldType.STRING)

            fields.append(
                SchemaField(
                    field_id=i + 1,
                    name=field.name,
                    field_type=iceberg_type,
                    required=not field.nullable,
                )
            )

        # Create table config
        table_config = TableConfig(
            namespace=namespace,
            table_name=table_name,
            table_schema=TableSchema(fields=fields),
        )

        self._log.info(
            "creating_table_from_data",
            identifier=identifier,
            num_fields=len(fields),
        )

        self._table_manager.create_table(table_config)


# =============================================================================
# Factory Functions
# =============================================================================


def create_iceberg_io_manager(
    table_manager: IcebergTableManager,
    namespace: str,
    default_write_mode: str = "append",
    infer_schema_from_data: bool = True,
) -> IcebergIOManager:
    """Factory function to create IcebergIOManager.

    Convenience function for creating an IcebergIOManager with common
    configuration options.

    Args:
        table_manager: IcebergTableManager for Iceberg operations.
        namespace: Default namespace for tables.
        default_write_mode: Default write mode (append, overwrite, upsert).
        infer_schema_from_data: Infer schema on first write.

    Returns:
        Configured IcebergIOManager instance.

    Example:
        >>> io_manager = create_iceberg_io_manager(
        ...     table_manager=manager,
        ...     namespace="silver",
        ... )
    """
    config = IcebergIOManagerConfig(
        namespace=namespace,
        default_write_mode=default_write_mode,
        infer_schema_from_data=infer_schema_from_data,
    )
    return IcebergIOManager(table_manager=table_manager, config=config)


__all__ = [
    "IcebergIOManager",
    "IcebergIOManagerConfig",
    "create_iceberg_io_manager",
    # Metadata keys
    "ICEBERG_TABLE_KEY",
    "ICEBERG_NAMESPACE_KEY",
    "ICEBERG_WRITE_MODE_KEY",
    "ICEBERG_PARTITION_FILTER_KEY",
    "ICEBERG_UPSERT_KEYS_KEY",
    "ICEBERG_PARTITION_COLUMN_KEY",
    "ICEBERG_SNAPSHOT_PROPS_KEY",
]
