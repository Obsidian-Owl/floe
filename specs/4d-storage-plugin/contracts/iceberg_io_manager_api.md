# API Contract: IcebergIOManager (Dagster Integration)

**Created**: 2026-01-17
**Version**: 1.0.0
**Package**: `packages/floe-iceberg`

## Overview

IcebergIOManager is a Dagster IOManager that handles Iceberg table operations for asset materialization. It enables seamless integration between Dagster orchestration and Iceberg storage.

## Class Interface

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dagster import (
    ConfigurableIOManager,
    InputContext,
    OutputContext,
)
import pyarrow as pa

if TYPE_CHECKING:
    from pyiceberg.table import Table

from floe_iceberg import IcebergTableManager
from floe_iceberg.models import (
    IcebergIOManagerConfig,
    WriteConfig,
    WriteMode,
)


class IcebergIOManager(ConfigurableIOManager):
    """Dagster IOManager for Iceberg tables.

    Handles asset outputs by writing to configured Iceberg tables and
    asset inputs by reading from tables. Supports configurable write
    modes and partitioned assets.

    NOT a plugin - uses IcebergTableManager internally.

    Example:
        >>> from floe_iceberg.io_manager import IcebergIOManager
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

    Args:
        table_manager: IcebergTableManager instance for table operations
        config: IcebergIOManagerConfig with defaults and namespace

    Requirement: FR-037-040
    """

    table_manager: IcebergTableManager
    config: IcebergIOManagerConfig

    def handle_output(
        self,
        context: OutputContext,
        obj: pa.Table,
    ) -> None:
        """Write asset output to Iceberg table.

        Determines table identifier from asset key and namespace.
        Creates table if it doesn't exist (with schema inference).
        Writes data using configured write mode.

        Args:
            context: Dagster output context with asset info
            obj: PyArrow Table to write

        Raises:
            WriteError: If write operation fails
            ValidationError: If data is invalid

        Requirement: FR-037, FR-038

        Example:
            >>> @asset(io_manager_key="iceberg")
            >>> def customers() -> pa.Table:
            ...     return pa.Table.from_pylist([...])
            >>> # Writes to {namespace}.customers table
        """
        ...

    def load_input(
        self,
        context: InputContext,
    ) -> pa.Table:
        """Load asset input from Iceberg table.

        Reads table data as PyArrow Table. Supports partition filtering
        based on upstream partition.

        Args:
            context: Dagster input context with upstream asset info

        Returns:
            PyArrow Table with data from Iceberg table

        Raises:
            NoSuchTableError: If upstream table doesn't exist

        Requirement: FR-039

        Example:
            >>> @asset(io_manager_key="iceberg")
            >>> def customers_silver(customers_bronze: pa.Table) -> pa.Table:
            ...     return transform(customers_bronze)
            >>> # Reads from {namespace}.customers_bronze table
        """
        ...

    def _get_table_identifier(self, context: OutputContext | InputContext) -> str:
        """Generate table identifier from context.

        Uses namespace from config and asset key for table name.
        Supports custom table name via metadata.

        Args:
            context: Dagster context (input or output)

        Returns:
            Full table identifier (e.g., "silver.customers")

        Example:
            >>> # Default: asset_key -> table_name
            >>> @asset(io_manager_key="iceberg")
            >>> def customers():  # -> silver.customers
            ...     ...
            >>>
            >>> # Custom table name via metadata
            >>> @asset(
            ...     io_manager_key="iceberg",
            ...     metadata={"iceberg_table": "dim_customers"}
            ... )
            >>> def customers():  # -> silver.dim_customers
            ...     ...
        """
        ...

    def _get_write_config(self, context: OutputContext) -> WriteConfig:
        """Get write configuration from context metadata.

        Extracts write mode, commit strategy, and snapshot properties
        from asset metadata. Falls back to IOManager defaults.

        Args:
            context: Dagster output context

        Returns:
            WriteConfig for the write operation

        Example:
            >>> @asset(
            ...     io_manager_key="iceberg",
            ...     metadata={
            ...         "iceberg_write_mode": "overwrite",
            ...         "iceberg_partition_filter": "date = '2026-01-17'",
            ...     }
            ... )
            >>> def daily_metrics():
            ...     ...  # Overwrites matching partition
        """
        ...
```

## Metadata Keys

Assets can customize IOManager behavior via metadata:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `iceberg_table` | `str` | asset_key | Custom table name |
| `iceberg_namespace` | `str` | config.namespace | Override namespace |
| `iceberg_write_mode` | `str` | `"append"` | Write mode: append, overwrite, upsert |
| `iceberg_partition_filter` | `str` | None | Filter for partition overwrite |
| `iceberg_upsert_keys` | `list[str]` | None | Join columns for upsert |
| `iceberg_snapshot_props` | `dict` | {} | Custom snapshot properties |

## Partitioned Assets (FR-040)

```python
from dagster import asset, DailyPartitionsDefinition

daily_partitions = DailyPartitionsDefinition(start_date="2026-01-01")

@asset(
    io_manager_key="iceberg",
    partitions_def=daily_partitions,
    metadata={
        "iceberg_write_mode": "overwrite",  # Overwrite partition only
        "iceberg_partition_column": "date",  # Map partition to column
    }
)
def daily_events(context) -> pa.Table:
    """Process events for a single day.

    IOManager automatically:
    1. Maps Dagster partition key to Iceberg partition column
    2. Uses overwrite mode for just that partition
    3. Preserves data in other partitions
    """
    partition_date = context.partition_key
    events = fetch_events_for_date(partition_date)
    return pa.Table.from_pylist(events)
```

## Schema Inference

When `infer_schema_from_data=True` (default), IOManager infers schema on first write:

```python
# First materialization creates table with inferred schema
@asset(io_manager_key="iceberg")
def new_table() -> pa.Table:
    return pa.Table.from_pylist([
        {"id": 1, "name": "Alice", "created_at": datetime.now()},
    ])
# Table created with schema:
# - id: long (required)
# - name: string
# - created_at: timestamp
```

To disable inference and require explicit table creation:

```python
IcebergIOManager(
    table_manager=manager,
    config=IcebergIOManagerConfig(
        namespace="silver",
        infer_schema_from_data=False,  # Require pre-created table
    ),
)
```

## Integration with Dagster

### Resource Configuration

```python
from dagster import Definitions, EnvVar

defs = Definitions(
    assets=[...],
    resources={
        "iceberg": IcebergIOManager(
            table_manager=IcebergTableManager(
                catalog_plugin=polaris_plugin,
                storage_plugin=s3_plugin,
            ),
            config=IcebergIOManagerConfig(
                namespace="silver",
                default_write_mode=WriteMode.APPEND,
            ),
        ),
    },
)
```

### Multi-Namespace Support

```python
# Different IOManagers for different namespaces
defs = Definitions(
    assets=[bronze_assets, silver_assets, gold_assets],
    resources={
        "iceberg_bronze": IcebergIOManager(
            table_manager=manager,
            config=IcebergIOManagerConfig(namespace="bronze"),
        ),
        "iceberg_silver": IcebergIOManager(
            table_manager=manager,
            config=IcebergIOManagerConfig(namespace="silver"),
        ),
        "iceberg_gold": IcebergIOManager(
            table_manager=manager,
            config=IcebergIOManagerConfig(namespace="gold"),
        ),
    },
)
```

## OpenTelemetry Integration

IOManager operations include Dagster context in spans:

```python
# Additional span attributes for IOManager
{
    "dagster.asset_key": "customers_silver",
    "dagster.partition_key": "2026-01-17",
    "dagster.run_id": "abc123",
    "dagster.step_key": "customers_silver",
}
```

## Contract Versioning

| Version | Changes | Breaking |
|---------|---------|----------|
| 1.0.0 | Initial release | N/A |
