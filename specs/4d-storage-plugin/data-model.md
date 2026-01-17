# Data Model: IcebergTableManager (Epic 4D)

**Created**: 2026-01-17
**Status**: Complete
**Source**: spec.md Key Entities section

## Overview

This document defines the Pydantic models and data structures for the IcebergTableManager utility class. All models use Pydantic v2 syntax with strict validation.

## Module Constants

```python
# SonarQube S1192 compliance - extract repeated string literals
IDENTIFIER_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_]*$"
"""Regex pattern for valid identifiers (namespace, table, field names).

Used for validation of:
- TableConfig.namespace
- TableConfig.table_name
- SchemaField.name
- PartitionField.name
"""
```

## Core Entities

### 1. IcebergTableManagerConfig

Configuration for the IcebergTableManager instance.

```python
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class IcebergTableManagerConfig(BaseModel):
    """Configuration for IcebergTableManager.

    Controls default behaviors and retry policies.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Retry configuration for commit conflicts
    max_commit_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retries on CommitFailedException"
    )
    retry_base_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Base delay for exponential backoff"
    )

    # Default snapshot retention (governance-aware)
    default_retention_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Default snapshot retention in days"
    )
    min_snapshots_to_keep: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Minimum snapshots to preserve regardless of age"
    )

    # Write defaults
    default_commit_strategy: CommitStrategy = Field(
        default=CommitStrategy.FAST_APPEND,
        description="Default commit strategy for writes"
    )

    # Table creation defaults
    default_table_properties: dict[str, str] = Field(
        default_factory=lambda: {
            "write.format.default": "parquet",
            "write.target-file-size-bytes": "134217728",  # 128MB
            "write.parquet.row-group-size-bytes": "134217728",
        },
        description="Default table properties for new tables"
    )
```

### 2. TableConfig

Configuration for creating a new Iceberg table.

```python
from enum import Enum


class TableConfig(BaseModel):
    """Configuration for Iceberg table creation.

    Defines schema, partitioning, and table properties.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Table identifier
    namespace: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,  # Use module constant
        description="Catalog namespace (e.g., 'bronze', 'silver')"
    )
    table_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,  # Use module constant
        description="Table name within namespace"
    )

    # Schema definition
    schema: TableSchema = Field(
        ...,
        description="Iceberg schema definition with fields"
    )

    # Partitioning (optional)
    partition_spec: PartitionSpec | None = Field(
        default=None,
        description="Partition specification for the table"
    )

    # Storage location (optional, defaults to warehouse)
    location: str | None = Field(
        default=None,
        description="Custom storage location (e.g., 's3://bucket/path')"
    )

    # Custom properties
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Custom table properties"
    )

    @property
    def identifier(self) -> str:
        """Full table identifier (namespace.table_name)."""
        return f"{self.namespace}.{self.table_name}"
```

### 3. TableSchema

Schema definition for Iceberg tables.

```python
class FieldType(str, Enum):
    """Iceberg primitive types."""
    BOOLEAN = "boolean"
    INT = "int"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    DECIMAL = "decimal"
    DATE = "date"
    TIME = "time"
    TIMESTAMP = "timestamp"
    TIMESTAMPTZ = "timestamptz"
    STRING = "string"
    UUID = "uuid"
    FIXED = "fixed"
    BINARY = "binary"


class SchemaField(BaseModel):
    """Definition of a single schema field."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    field_id: int = Field(
        ...,
        ge=1,
        description="Unique field ID (immutable for evolution)"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,  # Use module constant
        description="Field name"
    )
    field_type: FieldType = Field(
        ...,
        description="Field data type"
    )
    required: bool = Field(
        default=False,
        description="Whether field is required (NOT NULL)"
    )
    doc: str | None = Field(
        default=None,
        max_length=1000,
        description="Field documentation"
    )
    # For decimal type
    precision: int | None = Field(
        default=None,
        ge=1,
        le=38,
        description="Decimal precision"
    )
    scale: int | None = Field(
        default=None,
        ge=0,
        description="Decimal scale"
    )


class TableSchema(BaseModel):
    """Iceberg table schema definition."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: list[SchemaField] = Field(
        ...,
        min_length=1,
        description="List of schema fields"
    )

    def to_pyiceberg_schema(self) -> "pyiceberg.schema.Schema":
        """Convert to PyIceberg Schema object."""
        from pyiceberg.schema import Schema
        from pyiceberg.types import NestedField

        nested_fields = []
        for field in self.fields:
            iceberg_type = self._convert_field_type(field)
            nested_fields.append(
                NestedField(
                    field_id=field.field_id,
                    name=field.name,
                    field_type=iceberg_type,
                    required=field.required,
                    doc=field.doc,
                )
            )
        return Schema(*nested_fields)

    def _convert_field_type(self, field: SchemaField) -> Any:
        """Convert FieldType enum to PyIceberg type."""
        from pyiceberg import types

        type_mapping = {
            FieldType.BOOLEAN: types.BooleanType,
            FieldType.INT: types.IntegerType,
            FieldType.LONG: types.LongType,
            FieldType.FLOAT: types.FloatType,
            FieldType.DOUBLE: types.DoubleType,
            FieldType.DATE: types.DateType,
            FieldType.TIME: types.TimeType,
            FieldType.TIMESTAMP: types.TimestampType,
            FieldType.TIMESTAMPTZ: types.TimestamptzType,
            FieldType.STRING: types.StringType,
            FieldType.UUID: types.UUIDType,
            FieldType.BINARY: types.BinaryType,
        }

        if field.field_type == FieldType.DECIMAL:
            return types.DecimalType(field.precision or 38, field.scale or 0)

        return type_mapping[field.field_type]()
```

### 4. PartitionSpec

Partition specification for tables.

```python
class PartitionTransform(str, Enum):
    """Iceberg partition transforms."""
    IDENTITY = "identity"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    BUCKET = "bucket"
    TRUNCATE = "truncate"


class PartitionField(BaseModel):
    """Definition of a partition field."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_field_id: int = Field(
        ...,
        ge=1,
        description="Source field ID to partition by"
    )
    partition_field_id: int = Field(
        ...,
        ge=1000,
        description="Partition field ID (convention: start at 1000)"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Partition field name"
    )
    transform: PartitionTransform = Field(
        ...,
        description="Transform to apply"
    )
    # For bucket/truncate transforms
    num_buckets: int | None = Field(
        default=None,
        ge=1,
        description="Number of buckets (for bucket transform)"
    )
    width: int | None = Field(
        default=None,
        ge=1,
        description="Truncation width (for truncate transform)"
    )


class PartitionSpec(BaseModel):
    """Partition specification for an Iceberg table."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: list[PartitionField] = Field(
        default_factory=list,
        description="List of partition fields"
    )

    def to_pyiceberg_spec(self) -> "pyiceberg.partitioning.PartitionSpec":
        """Convert to PyIceberg PartitionSpec."""
        from pyiceberg.partitioning import PartitionSpec as PyPartitionSpec
        from pyiceberg.partitioning import PartitionField as PyPartitionField
        from pyiceberg import transforms

        py_fields = []
        for field in self.fields:
            transform = self._get_transform(field)
            py_fields.append(
                PyPartitionField(
                    source_id=field.source_field_id,
                    field_id=field.partition_field_id,
                    transform=transform,
                    name=field.name,
                )
            )
        return PyPartitionSpec(*py_fields)

    def _get_transform(self, field: PartitionField) -> Any:
        """Get PyIceberg transform for field."""
        from pyiceberg.transforms import (
            IdentityTransform,
            YearTransform,
            MonthTransform,
            DayTransform,
            HourTransform,
            BucketTransform,
            TruncateTransform,
        )

        transform_mapping = {
            PartitionTransform.IDENTITY: IdentityTransform,
            PartitionTransform.YEAR: YearTransform,
            PartitionTransform.MONTH: MonthTransform,
            PartitionTransform.DAY: DayTransform,
            PartitionTransform.HOUR: HourTransform,
        }

        if field.transform == PartitionTransform.BUCKET:
            return BucketTransform(field.num_buckets or 16)
        if field.transform == PartitionTransform.TRUNCATE:
            return TruncateTransform(field.width or 10)

        return transform_mapping[field.transform]()
```

### 5. SchemaChange

Represents a schema modification operation.

```python
class SchemaChangeType(str, Enum):
    """Types of schema changes."""
    ADD_COLUMN = "add_column"
    RENAME_COLUMN = "rename_column"
    WIDEN_TYPE = "widen_type"
    MAKE_OPTIONAL = "make_optional"
    DELETE_COLUMN = "delete_column"  # Requires allow_incompatible
    UPDATE_DOC = "update_doc"


class SchemaChange(BaseModel):
    """A single schema change operation.

    Use SchemaEvolution to apply multiple changes atomically.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    change_type: SchemaChangeType = Field(
        ...,
        description="Type of schema change"
    )

    # For ADD_COLUMN
    field: SchemaField | None = Field(
        default=None,
        description="New field definition (for ADD_COLUMN)"
    )
    parent_path: tuple[str, ...] | None = Field(
        default=None,
        description="Parent path for nested fields"
    )

    # For RENAME_COLUMN
    old_name: str | None = Field(
        default=None,
        description="Current column name"
    )
    new_name: str | None = Field(
        default=None,
        description="New column name"
    )

    # For WIDEN_TYPE
    column_name: str | None = Field(
        default=None,
        description="Column to widen"
    )
    new_type: FieldType | None = Field(
        default=None,
        description="New wider type"
    )

    # For DELETE_COLUMN, MAKE_OPTIONAL, UPDATE_DOC
    target_column: str | None = Field(
        default=None,
        description="Target column name"
    )
    new_doc: str | None = Field(
        default=None,
        description="New documentation (for UPDATE_DOC)"
    )


class SchemaEvolution(BaseModel):
    """Batch of schema changes to apply atomically."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    changes: list[SchemaChange] = Field(
        ...,
        min_length=1,
        description="List of schema changes"
    )
    allow_incompatible_changes: bool = Field(
        default=False,
        description="Allow breaking changes (DELETE_COLUMN, etc.)"
    )
```

### 6. WriteMode

Enumeration of supported write modes.

```python
class WriteMode(str, Enum):
    """Write operation modes."""
    APPEND = "append"          # Add new rows
    OVERWRITE = "overwrite"    # Replace all rows
    UPSERT = "upsert"          # Merge based on key columns


class CommitStrategy(str, Enum):
    """Commit strategies for writes."""
    FAST_APPEND = "fast_append"  # Default: new manifests, minimal latency
    MERGE_COMMIT = "merge_commit"  # Consolidate manifests


class WriteConfig(BaseModel):
    """Configuration for a write operation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: WriteMode = Field(
        default=WriteMode.APPEND,
        description="Write mode"
    )
    commit_strategy: CommitStrategy = Field(
        default=CommitStrategy.FAST_APPEND,
        description="Commit strategy"
    )

    # For OVERWRITE mode
    overwrite_filter: str | None = Field(
        default=None,
        description="Filter expression for overwrite (e.g., 'status == pending')"
    )

    # For UPSERT mode
    join_columns: list[str] | None = Field(
        default=None,
        description="Columns to join on for upsert"
    )

    # Snapshot properties for lineage
    snapshot_properties: dict[str, str] = Field(
        default_factory=dict,
        description="Custom snapshot properties (e.g., pipeline_run_id)"
    )
```

### 7. SnapshotInfo

Metadata about a table snapshot.

```python
from datetime import datetime


class OperationType(str, Enum):
    """Types of snapshot operations."""
    APPEND = "append"
    OVERWRITE = "overwrite"
    DELETE = "delete"
    REPLACE = "replace"


class SnapshotInfo(BaseModel):
    """Metadata about a table snapshot."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: int = Field(
        ...,
        description="Unique snapshot ID"
    )
    parent_snapshot_id: int | None = Field(
        default=None,
        description="Parent snapshot ID (None for initial snapshot)"
    )
    timestamp: datetime = Field(
        ...,
        description="Snapshot creation timestamp"
    )
    operation: OperationType = Field(
        ...,
        description="Type of operation that created snapshot"
    )
    summary: dict[str, str] = Field(
        default_factory=dict,
        description="Snapshot summary (files added, rows, etc.)"
    )

    @property
    def added_files(self) -> int:
        """Number of data files added in this snapshot."""
        return int(self.summary.get("added-data-files", 0))

    @property
    def added_records(self) -> int:
        """Number of records added in this snapshot."""
        return int(self.summary.get("added-records", 0))
```

### 8. CompactionStrategy

Configuration for table compaction.

```python
class CompactionStrategyType(str, Enum):
    """Types of compaction strategies."""
    BIN_PACK = "bin_pack"      # Combine small files
    SORT = "sort"              # Sort and rewrite


class CompactionStrategy(BaseModel):
    """Configuration for compaction operation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_type: CompactionStrategyType = Field(
        default=CompactionStrategyType.BIN_PACK,
        description="Compaction strategy"
    )

    # Target file size
    target_file_size_bytes: int = Field(
        default=134217728,  # 128MB
        ge=1048576,  # 1MB min
        le=1073741824,  # 1GB max
        description="Target file size in bytes"
    )

    # For SORT strategy
    sort_columns: list[str] | None = Field(
        default=None,
        description="Columns to sort by (for SORT strategy)"
    )

    # Parallelism
    max_concurrent_file_group_rewrites: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Maximum concurrent file group rewrites"
    )
```

### 9. IcebergIOManagerConfig

Configuration for the Dagster IOManager.

```python
class IcebergIOManagerConfig(BaseModel):
    """Configuration for Dagster IcebergIOManager."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Default write behavior
    default_write_mode: WriteMode = Field(
        default=WriteMode.APPEND,
        description="Default write mode for assets"
    )
    default_commit_strategy: CommitStrategy = Field(
        default=CommitStrategy.FAST_APPEND,
        description="Default commit strategy"
    )

    # Namespace mapping
    namespace: str = Field(
        ...,
        description="Default namespace for tables"
    )

    # Table name pattern
    table_name_pattern: str = Field(
        default="{asset_key}",
        description="Pattern for generating table names from asset keys"
    )

    # Schema inference
    infer_schema_from_data: bool = Field(
        default=True,
        description="Infer schema from first write if table doesn't exist"
    )
```

## State Transitions

### Table Lifecycle

```
NOT_EXISTS → CREATED → HAS_DATA → EVOLVED → COMPACTED
                ↓         ↓          ↓          ↓
             DROPPED   DROPPED    DROPPED    DROPPED
```

### Snapshot Lifecycle

```
CURRENT → ANCESTOR → EXPIRED
              ↓
          ROLLED_BACK_TO (becomes CURRENT)
```

## Validation Rules

### Schema Validation
1. Field IDs must be unique within a schema
2. Field IDs must be positive integers
3. Field names must be valid identifiers
4. Decimal fields must specify precision (1-38)
5. Required fields cannot be added to existing tables

### Partition Validation
1. Source field must exist in schema
2. Partition field IDs must be >= 1000 (convention)
3. Bucket transform requires num_buckets
4. Truncate transform requires width

### Write Validation
1. Data schema must be compatible with table schema
2. Upsert requires join_columns to be specified
3. Overwrite filter must be valid Iceberg expression

## JSON Schema Export

All models export JSON Schema for IDE autocomplete:

```bash
# Generate schemas
python -c "from floe_iceberg.models import TableConfig; print(TableConfig.model_json_schema())"
```

Schema files stored in `specs/4d-storage-plugin/contracts/schemas/`.
