# API Contract: IcebergTableManager

**Created**: 2026-01-17
**Version**: 1.0.0
**Package**: `packages/floe-iceberg`

## Overview

IcebergTableManager is an internal utility class that wraps PyIceberg table operations. It is NOT a plugin ABC - Iceberg is enforced, not pluggable.

## Class Interface

```python
from __future__ import annotations

from typing import TYPE_CHECKING

import pyarrow as pa

if TYPE_CHECKING:
    from pyiceberg.table import Table

from floe_core.plugins.catalog import CatalogPlugin
from floe_core.plugins.storage import StoragePlugin
from floe_iceberg.models import (
    CompactionStrategy,
    IcebergTableManagerConfig,
    SchemaEvolution,
    SnapshotInfo,
    TableConfig,
    WriteConfig,
)


class IcebergTableManager:
    """Internal utility for PyIceberg table operations.

    Wraps PyIceberg complexity and provides a consistent API for
    table creation, schema evolution, writes, and snapshot management.

    NOT a plugin - Iceberg is enforced (ADR-0005), not pluggable.

    Example:
        >>> from floe_iceberg import IcebergTableManager
        >>> manager = IcebergTableManager(
        ...     catalog_plugin=polaris_plugin,
        ...     storage_plugin=s3_plugin,
        ... )
        >>> table = manager.create_table(table_config)
        >>> manager.write_data(table, data, WriteConfig(mode=WriteMode.APPEND))

    Args:
        catalog_plugin: CatalogPlugin for catalog operations (dependency injection)
        storage_plugin: StoragePlugin for FileIO (dependency injection)
        config: Optional configuration for retry behavior, defaults, etc.
    """

    def __init__(
        self,
        catalog_plugin: CatalogPlugin,
        storage_plugin: StoragePlugin,
        config: IcebergTableManagerConfig | None = None,
    ) -> None:
        """Initialize IcebergTableManager with plugin dependencies."""
        ...

    # =========================================================================
    # TABLE CREATION (FR-001, FR-012-016)
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
            config: TableConfig with namespace, name, schema, partition spec
            if_not_exists: If True, return existing table instead of raising error.
                Default False (fail fast principle).

        Returns:
            PyIceberg Table instance

        Raises:
            TableAlreadyExistsError: If table exists and if_not_exists=False
            NoSuchNamespaceError: If namespace doesn't exist
            ValidationError: If config is invalid

        Requirement: FR-001, FR-012-016

        Example:
            >>> config = TableConfig(
            ...     namespace="bronze",
            ...     table_name="customers",
            ...     schema=schema,
            ...     partition_spec=partition_spec,
            ... )
            >>> table = manager.create_table(config)
            >>> # Idempotent creation
            >>> table = manager.create_table(config, if_not_exists=True)
        """
        ...

    def load_table(self, identifier: str) -> Table:
        """Load an existing table by identifier.

        Args:
            identifier: Full table identifier (e.g., "bronze.customers")

        Returns:
            PyIceberg Table instance

        Raises:
            NoSuchTableError: If table doesn't exist

        Example:
            >>> table = manager.load_table("bronze.customers")
        """
        ...

    def table_exists(self, identifier: str) -> bool:
        """Check if a table exists.

        Args:
            identifier: Full table identifier

        Returns:
            True if table exists, False otherwise

        Example:
            >>> if not manager.table_exists("bronze.new_table"):
            ...     manager.create_table(config)
        """
        ...

    # =========================================================================
    # SCHEMA EVOLUTION (FR-002, FR-017-021)
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

        Args:
            table: PyIceberg Table instance
            evolution: SchemaEvolution with list of changes

        Returns:
            Updated Table instance with new schema

        Raises:
            ValidationError: If changes are incompatible and not allowed
            SchemaEvolutionError: If evolution fails

        Requirement: FR-002, FR-017-021

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
            ...         SchemaChange(
            ...             change_type=SchemaChangeType.RENAME_COLUMN,
            ...             old_name="name",
            ...             new_name="full_name",
            ...         ),
            ...     ],
            ... )
            >>> table = manager.evolve_schema(table, evolution)
        """
        ...

    # =========================================================================
    # WRITE OPERATIONS (FR-005, FR-026-029)
    # =========================================================================

    def write_data(
        self,
        table: Table,
        data: pa.Table,
        config: WriteConfig,
    ) -> SnapshotInfo:
        """Write data to a table with ACID guarantees.

        Supports append, overwrite, and upsert modes. Uses optimistic
        concurrency with automatic retry on conflicts.

        Args:
            table: PyIceberg Table instance
            data: PyArrow Table with data to write
            config: WriteConfig with mode, commit strategy, etc.

        Returns:
            SnapshotInfo with details of the created snapshot

        Raises:
            CommitFailedException: If all retries exhausted
            ValidationError: If data schema incompatible
            WriteError: If write operation fails

        Requirement: FR-005, FR-026-029

        Example:
            >>> import pyarrow as pa
            >>> data = pa.Table.from_pylist([
            ...     {"id": 1, "name": "Alice"},
            ...     {"id": 2, "name": "Bob"},
            ... ])
            >>> config = WriteConfig(
            ...     mode=WriteMode.APPEND,
            ...     commit_strategy=CommitStrategy.FAST_APPEND,
            ...     snapshot_properties={"pipeline_run_id": "run-123"},
            ... )
            >>> snapshot = manager.write_data(table, data, config)
            >>> print(f"Created snapshot {snapshot.snapshot_id}")
        """
        ...

    # =========================================================================
    # SNAPSHOT MANAGEMENT (FR-003, FR-006-007, FR-022-025)
    # =========================================================================

    def list_snapshots(self, table: Table) -> list[SnapshotInfo]:
        """List all snapshots for a table.

        Returns snapshot metadata including IDs, timestamps, and operations.

        Args:
            table: PyIceberg Table instance

        Returns:
            List of SnapshotInfo ordered by timestamp (newest first)

        Requirement: FR-003, FR-006

        Example:
            >>> snapshots = manager.list_snapshots(table)
            >>> for s in snapshots[:5]:
            ...     print(f"{s.snapshot_id}: {s.operation} at {s.timestamp}")
        """
        ...

    def rollback_to_snapshot(
        self,
        table: Table,
        snapshot_id: int,
    ) -> Table:
        """Rollback table to a previous snapshot.

        Reverts the table state to a specified snapshot. The current
        snapshot becomes unreachable (will be expired eventually).

        Args:
            table: PyIceberg Table instance
            snapshot_id: Target snapshot ID to rollback to

        Returns:
            Table instance pointing to rolled-back snapshot

        Raises:
            SnapshotNotFoundError: If snapshot_id doesn't exist
            RollbackError: If rollback fails

        Requirement: FR-007

        Example:
            >>> # Oops, bad write! Rollback to previous snapshot
            >>> snapshots = manager.list_snapshots(table)
            >>> previous = snapshots[1].snapshot_id
            >>> table = manager.rollback_to_snapshot(table, previous)
        """
        ...

    def expire_snapshots(
        self,
        table: Table,
        older_than_days: int | None = None,
        min_snapshots_to_keep: int | None = None,
    ) -> int:
        """Expire old snapshots to reclaim storage.

        Removes snapshots older than the retention period. Respects
        min_snapshots_to_keep regardless of age.

        GOVERNANCE-AWARE: Accepts retention from Policy Enforcer.
        IcebergTableManager does NOT enforce governance itself.

        Args:
            table: PyIceberg Table instance
            older_than_days: Snapshots older than this are expired.
                Defaults to config.default_retention_days (7).
            min_snapshots_to_keep: Minimum to preserve regardless of age.
                Defaults to config.min_snapshots_to_keep (10).

        Returns:
            Number of snapshots expired

        Requirement: FR-024

        Example:
            >>> # Default: 7 days retention
            >>> expired = manager.expire_snapshots(table)
            >>> print(f"Expired {expired} snapshots")
            >>>
            >>> # Governance-validated retention
            >>> validated_days = policy_enforcer.get_retention()
            >>> expired = manager.expire_snapshots(table, older_than_days=validated_days)
        """
        ...

    # =========================================================================
    # COMPACTION (FR-030-032)
    # =========================================================================

    def compact_table(
        self,
        table: Table,
        strategy: CompactionStrategy,
    ) -> int:
        """Compact table files to optimize performance.

        Rewrites data files according to the compaction strategy.
        Execution only - scheduling is orchestrator's responsibility.

        Args:
            table: PyIceberg Table instance
            strategy: CompactionStrategy with type and parameters

        Returns:
            Number of files rewritten

        Raises:
            CompactionError: If compaction fails

        Requirement: FR-030-032

        Example:
            >>> strategy = CompactionStrategy(
            ...     strategy_type=CompactionStrategyType.BIN_PACK,
            ...     target_file_size_bytes=134217728,  # 128MB
            ... )
            >>> rewritten = manager.compact_table(table, strategy)
            >>> print(f"Compacted {rewritten} files")
        """
        ...
```

## Error Types

```python
from floe_iceberg.errors import (
    # Base
    IcebergError,

    # Table operations
    TableAlreadyExistsError,
    NoSuchTableError,
    NoSuchNamespaceError,

    # Schema
    SchemaEvolutionError,
    IncompatibleSchemaChangeError,

    # Write
    WriteError,
    CommitConflictError,  # Maps from PyIceberg CommitFailedException

    # Snapshot
    SnapshotNotFoundError,
    RollbackError,

    # Compaction
    CompactionError,

    # Validation
    ValidationError,
)
```

## OpenTelemetry Integration (FR-041-044)

All operations emit OpenTelemetry spans:

```python
# Span attributes
{
    "iceberg.table.identifier": "bronze.customers",
    "iceberg.operation": "write_data",
    "iceberg.write.mode": "append",
    "iceberg.commit.strategy": "fast_append",
    "iceberg.snapshot.id": 805611270568163028,
    "iceberg.records.added": 1000,
    "iceberg.files.added": 2,
}

# Span names
"IcebergTableManager.create_table"
"IcebergTableManager.write_data"
"IcebergTableManager.evolve_schema"
"IcebergTableManager.expire_snapshots"
"IcebergTableManager.compact_table"
```

## Contract Versioning

| Version | Changes | Breaking |
|---------|---------|----------|
| 1.0.0 | Initial release | N/A |

**Versioning Rules:**
- MAJOR: Remove method, change return type, remove required parameter
- MINOR: Add method, add optional parameter, add new model field (optional)
- PATCH: Documentation, internal implementation changes
