"""Pydantic models and enumerations for floe-iceberg package.

This module defines all configuration models and enumerations used by
IcebergTableManager and IcebergIOManager. All models use Pydantic v2 syntax
with strict validation.

Models are designed for immutability (frozen=True) and strict validation
(extra="forbid") to ensure data integrity.

Module Constants:
    IDENTIFIER_PATTERN: Regex pattern for valid identifiers (SonarQube S1192 compliance)

Enumerations:
    FieldType: Iceberg primitive data types
    PartitionTransform: Partition transform functions
    SchemaChangeType: Schema evolution operation types
    WriteMode: Data write operation modes
    CommitStrategy: Commit optimization strategies
    OperationType: Snapshot operation types
    CompactionStrategyType: File compaction strategies

Configuration Models:
    IcebergTableManagerConfig: Manager configuration
    IcebergIOManagerConfig: Dagster IOManager configuration

Data Models (implemented in later tasks):
    SchemaField, TableSchema: Schema definition
    PartitionField, PartitionSpec: Partitioning
    TableConfig: Table creation
    SchemaChange, SchemaEvolution: Schema evolution
    WriteConfig: Write operations
    SnapshotInfo: Snapshot metadata
    CompactionStrategy: Compaction configuration

Example:
    >>> from floe_iceberg.models import (
    ...     FieldType,
    ...     WriteMode,
    ...     IcebergTableManagerConfig,
    ... )
    >>> config = IcebergTableManagerConfig(max_commit_retries=5)
    >>> config.default_commit_strategy
    <CommitStrategy.FAST_APPEND: 'fast_append'>
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Module Constants (SonarQube S1192 Compliance)
# =============================================================================

IDENTIFIER_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_]*$"
"""Regex pattern for valid identifiers (namespace, table, field names).

Used for validation of:
- TableConfig.namespace
- TableConfig.table_name
- SchemaField.name
- PartitionField.name

Pattern rules:
- Must start with a letter (a-z, A-Z)
- Can contain letters, digits, and underscores
- Cannot be empty

Examples:
    Valid: "customers", "dim_product", "raw_data_v2"
    Invalid: "123_table", "_private", "has-hyphen", ""
"""


# =============================================================================
# Iceberg Type Enumerations
# =============================================================================


class FieldType(str, Enum):
    """Iceberg primitive data types.

    Maps to PyIceberg types for schema definition. All Iceberg primitive
    types are supported.

    Attributes:
        BOOLEAN: Boolean true/false
        INT: 32-bit signed integer
        LONG: 64-bit signed integer
        FLOAT: 32-bit IEEE 754 floating point
        DOUBLE: 64-bit IEEE 754 floating point
        DECIMAL: Arbitrary precision decimal (requires precision/scale)
        DATE: Calendar date without time
        TIME: Time of day without date
        TIMESTAMP: Timestamp without timezone
        TIMESTAMPTZ: Timestamp with timezone
        STRING: UTF-8 string
        UUID: Universally unique identifier
        FIXED: Fixed-length byte array
        BINARY: Variable-length byte array

    Example:
        >>> field_type = FieldType.STRING
        >>> field_type.value
        'string'
    """

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


class PartitionTransform(str, Enum):
    """Iceberg partition transform functions.

    Transforms applied to source columns to create partition values.
    Supports both temporal and data-based partitioning.

    Attributes:
        IDENTITY: No transformation (exact value)
        YEAR: Extract year from date/timestamp
        MONTH: Extract year-month from date/timestamp
        DAY: Extract date from timestamp
        HOUR: Extract date-hour from timestamp
        BUCKET: Hash into N buckets (requires num_buckets)
        TRUNCATE: Truncate to width (requires width)

    Example:
        >>> transform = PartitionTransform.DAY
        >>> transform.value
        'day'
    """

    IDENTITY = "identity"
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    BUCKET = "bucket"
    TRUNCATE = "truncate"


class SchemaChangeType(str, Enum):
    """Types of schema evolution operations.

    Defines the supported schema modification operations.
    Some operations (DELETE_COLUMN) require allow_incompatible_changes=True.

    Attributes:
        ADD_COLUMN: Add a new column to the schema
        RENAME_COLUMN: Rename an existing column
        WIDEN_TYPE: Widen a column's type (e.g., int -> long)
        MAKE_OPTIONAL: Make a required column optional
        DELETE_COLUMN: Delete a column (incompatible change)
        UPDATE_DOC: Update column documentation

    Example:
        >>> change_type = SchemaChangeType.ADD_COLUMN
        >>> change_type.value
        'add_column'
    """

    ADD_COLUMN = "add_column"
    RENAME_COLUMN = "rename_column"
    WIDEN_TYPE = "widen_type"
    MAKE_OPTIONAL = "make_optional"
    DELETE_COLUMN = "delete_column"
    UPDATE_DOC = "update_doc"


class WriteMode(str, Enum):
    """Write operation modes for data ingestion.

    Defines how data should be written to Iceberg tables.

    Attributes:
        APPEND: Add new rows to existing data
        OVERWRITE: Replace all or filtered rows
        UPSERT: Merge based on key columns (requires PyIceberg 0.9.0+)

    Example:
        >>> mode = WriteMode.APPEND
        >>> mode.value
        'append'
    """

    APPEND = "append"
    OVERWRITE = "overwrite"
    UPSERT = "upsert"


class CommitStrategy(str, Enum):
    """Commit strategies for write operations.

    Controls how commits are optimized for different workloads.

    Attributes:
        FAST_APPEND: Create new manifests for minimal latency (default)
        MERGE_COMMIT: Consolidate manifests for better read performance

    Example:
        >>> strategy = CommitStrategy.FAST_APPEND
        >>> strategy.value
        'fast_append'
    """

    FAST_APPEND = "fast_append"
    MERGE_COMMIT = "merge_commit"


class OperationType(str, Enum):
    """Types of snapshot operations.

    Identifies what operation created a snapshot for lineage tracking.

    Attributes:
        APPEND: Data was appended
        OVERWRITE: Data was overwritten
        DELETE: Data was deleted
        REPLACE: Data was replaced (compaction, etc.)

    Example:
        >>> op_type = OperationType.APPEND
        >>> op_type.value
        'append'
    """

    APPEND = "append"
    OVERWRITE = "overwrite"
    DELETE = "delete"
    REPLACE = "replace"


class CompactionStrategyType(str, Enum):
    """Types of file compaction strategies.

    Defines how files should be rewritten during compaction.

    Attributes:
        BIN_PACK: Combine small files into target size
        SORT: Sort and rewrite files for better query performance

    Example:
        >>> strategy = CompactionStrategyType.BIN_PACK
        >>> strategy.value
        'bin_pack'
    """

    BIN_PACK = "bin_pack"
    SORT = "sort"


# =============================================================================
# Manager Configuration Models
# =============================================================================


class IcebergTableManagerConfig(BaseModel):
    """Configuration for IcebergTableManager.

    Controls default behaviors, retry policies, and table creation defaults.
    All fields have sensible defaults for typical workloads.

    Attributes:
        max_commit_retries: Maximum retries on CommitFailedException (1-10).
        retry_base_delay_seconds: Base delay for exponential backoff (0.1-30.0).
        default_retention_days: Default snapshot retention in days (1-365).
        min_snapshots_to_keep: Minimum snapshots to preserve (1-100).
        default_commit_strategy: Default commit strategy for writes.
        default_table_properties: Default table properties for new tables.

    Example:
        >>> config = IcebergTableManagerConfig(
        ...     max_commit_retries=5,
        ...     default_retention_days=30,
        ... )
        >>> config.retry_base_delay_seconds
        1.0
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Retry configuration for commit conflicts
    max_commit_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retries on CommitFailedException",
    )
    retry_base_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Base delay for exponential backoff",
    )

    # Default snapshot retention (governance-aware)
    default_retention_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Default snapshot retention in days",
    )
    min_snapshots_to_keep: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Minimum snapshots to preserve regardless of age",
    )

    # Write defaults
    default_commit_strategy: CommitStrategy = Field(
        default=CommitStrategy.FAST_APPEND,
        description="Default commit strategy for writes",
    )

    # Table creation defaults
    default_table_properties: dict[str, str] = Field(
        default_factory=lambda: {
            "write.format.default": "parquet",
            "write.target-file-size-bytes": "134217728",  # 128MB
            "write.parquet.row-group-size-bytes": "134217728",
        },
        description="Default table properties for new tables",
    )


class IcebergIOManagerConfig(BaseModel):
    """Configuration for Dagster IcebergIOManager.

    Controls how Dagster assets are mapped to Iceberg tables and
    how data is written.

    Attributes:
        default_write_mode: Default write mode for assets.
        default_commit_strategy: Default commit strategy.
        namespace: Default namespace for tables.
        table_name_pattern: Pattern for generating table names from asset keys.
        infer_schema_from_data: Infer schema from first write if table doesn't exist.

    Example:
        >>> config = IcebergIOManagerConfig(
        ...     namespace="bronze",
        ...     table_name_pattern="{asset_key}",
        ... )
        >>> config.default_write_mode
        <WriteMode.APPEND: 'append'>
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Default write behavior
    default_write_mode: WriteMode = Field(
        default=WriteMode.APPEND,
        description="Default write mode for assets",
    )
    default_commit_strategy: CommitStrategy = Field(
        default=CommitStrategy.FAST_APPEND,
        description="Default commit strategy",
    )

    # Namespace mapping
    namespace: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,
        description="Default namespace for tables",
    )

    # Table name pattern
    table_name_pattern: str = Field(
        default="{asset_key}",
        description="Pattern for generating table names from asset keys",
    )

    # Schema inference
    infer_schema_from_data: bool = Field(
        default=True,
        description="Infer schema from first write if table doesn't exist",
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "IDENTIFIER_PATTERN",
    # Enumerations
    "FieldType",
    "PartitionTransform",
    "SchemaChangeType",
    "WriteMode",
    "CommitStrategy",
    "OperationType",
    "CompactionStrategyType",
    # Configuration models
    "IcebergTableManagerConfig",
    "IcebergIOManagerConfig",
]
