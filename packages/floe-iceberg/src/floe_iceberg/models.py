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
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
# Schema and Partition Models
# =============================================================================


class SchemaField(BaseModel):
    """Definition of a single schema field for Iceberg tables.

    Represents a column in an Iceberg table schema with all metadata
    required for PyIceberg conversion.

    Attributes:
        field_id: Unique field ID (immutable for schema evolution).
        name: Field name (must match IDENTIFIER_PATTERN).
        field_type: Iceberg data type.
        required: Whether field is required (NOT NULL).
        doc: Optional field documentation.
        precision: Decimal precision (1-38, required for DECIMAL type).
        scale: Decimal scale (>= 0, optional for DECIMAL type).

    Example:
        >>> field = SchemaField(
        ...     field_id=1,
        ...     name="customer_id",
        ...     field_type=FieldType.LONG,
        ...     required=True,
        ...     doc="Primary customer identifier",
        ... )
        >>> field.name
        'customer_id'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field_id: int = Field(
        ...,
        ge=1,
        description="Unique field ID (immutable for evolution)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,
        description="Field name",
    )
    field_type: FieldType = Field(
        ...,
        description="Field data type",
    )
    required: bool = Field(
        default=False,
        description="Whether field is required (NOT NULL)",
    )
    doc: str | None = Field(
        default=None,
        max_length=1000,
        description="Field documentation",
    )
    # For decimal type
    precision: int | None = Field(
        default=None,
        ge=1,
        le=38,
        description="Decimal precision",
    )
    scale: int | None = Field(
        default=None,
        ge=0,
        description="Decimal scale",
    )


class TableSchema(BaseModel):
    """Iceberg table schema definition.

    Contains a list of fields that define the table structure.
    Provides conversion to PyIceberg Schema objects.

    Attributes:
        fields: List of schema fields (at least one required).

    Example:
        >>> from floe_iceberg.models import TableSchema, SchemaField, FieldType
        >>> schema = TableSchema(fields=[
        ...     SchemaField(field_id=1, name="id", field_type=FieldType.LONG, required=True),
        ...     SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
        ... ])
        >>> len(schema.fields)
        2
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: list[SchemaField] = Field(
        ...,
        min_length=1,
        description="List of schema fields",
    )

    def to_pyiceberg_schema(self) -> "pyiceberg.schema.Schema":
        """Convert to PyIceberg Schema object.

        Returns:
            PyIceberg Schema instance.

        Raises:
            ImportError: If pyiceberg is not installed.
        """
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

    def _convert_field_type(self, field: SchemaField) -> "pyiceberg.types.IcebergType":
        """Convert FieldType enum to PyIceberg type.

        Args:
            field: SchemaField to convert.

        Returns:
            PyIceberg type instance.
        """
        from pyiceberg import types

        type_mapping: dict[FieldType, type] = {
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
            FieldType.FIXED: types.FixedType,
        }

        if field.field_type == FieldType.DECIMAL:
            return types.DecimalType(field.precision or 38, field.scale or 0)

        if field.field_type == FieldType.FIXED:
            # Fixed requires length, use precision as length if provided
            return types.FixedType(field.precision or 16)

        type_class = type_mapping.get(field.field_type)
        if type_class is None:
            msg = f"Unknown field type: {field.field_type}"
            raise ValueError(msg)
        return type_class()


class PartitionField(BaseModel):
    """Definition of a partition field for Iceberg tables.

    Specifies how a source column is transformed for partitioning.

    Attributes:
        source_field_id: Source field ID to partition by.
        partition_field_id: Partition field ID (convention: >= 1000).
        name: Partition field name.
        transform: Transform to apply.
        num_buckets: Number of buckets (for BUCKET transform).
        width: Truncation width (for TRUNCATE transform).

    Example:
        >>> field = PartitionField(
        ...     source_field_id=1,
        ...     partition_field_id=1000,
        ...     name="day_partition",
        ...     transform=PartitionTransform.DAY,
        ... )
        >>> field.transform
        <PartitionTransform.DAY: 'day'>
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_field_id: int = Field(
        ...,
        ge=1,
        description="Source field ID to partition by",
    )
    partition_field_id: int = Field(
        ...,
        ge=1000,
        description="Partition field ID (convention: start at 1000)",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Partition field name",
    )
    transform: PartitionTransform = Field(
        ...,
        description="Transform to apply",
    )
    # For bucket/truncate transforms
    num_buckets: int | None = Field(
        default=None,
        ge=1,
        description="Number of buckets (for bucket transform)",
    )
    width: int | None = Field(
        default=None,
        ge=1,
        description="Truncation width (for truncate transform)",
    )


class PartitionSpec(BaseModel):
    """Partition specification for an Iceberg table.

    Defines how data is partitioned for storage optimization.
    Provides conversion to PyIceberg PartitionSpec objects.

    Attributes:
        fields: List of partition fields (can be empty for unpartitioned).

    Example:
        >>> spec = PartitionSpec(fields=[
        ...     PartitionField(
        ...         source_field_id=1,
        ...         partition_field_id=1000,
        ...         name="date_day",
        ...         transform=PartitionTransform.DAY,
        ...     ),
        ... ])
        >>> len(spec.fields)
        1
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: list[PartitionField] = Field(
        default_factory=list,
        description="List of partition fields",
    )

    def to_pyiceberg_spec(
        self, schema: "pyiceberg.schema.Schema"
    ) -> "pyiceberg.partitioning.PartitionSpec":
        """Convert to PyIceberg PartitionSpec.

        Args:
            schema: PyIceberg Schema for field resolution.

        Returns:
            PyIceberg PartitionSpec instance.

        Raises:
            ImportError: If pyiceberg is not installed.
        """
        from pyiceberg.partitioning import PartitionField as PyPartitionField
        from pyiceberg.partitioning import PartitionSpec as PyPartitionSpec

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

    def _get_transform(
        self, field: PartitionField
    ) -> "pyiceberg.transforms.Transform":
        """Get PyIceberg transform for field.

        Args:
            field: PartitionField to get transform for.

        Returns:
            PyIceberg Transform instance.
        """
        from pyiceberg.transforms import (
            BucketTransform,
            DayTransform,
            HourTransform,
            IdentityTransform,
            MonthTransform,
            TruncateTransform,
            YearTransform,
        )

        transform_mapping: dict[PartitionTransform, type] = {
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

        transform_class = transform_mapping.get(field.transform)
        if transform_class is None:
            msg = f"Unknown partition transform: {field.transform}"
            raise ValueError(msg)
        return transform_class()


class TableConfig(BaseModel):
    """Configuration for Iceberg table creation.

    Defines schema, partitioning, and table properties for creating
    a new Iceberg table.

    Attributes:
        namespace: Catalog namespace (e.g., 'bronze', 'silver').
        table_name: Table name within namespace.
        table_schema: Iceberg schema definition with fields.
        partition_spec: Optional partition specification.
        location: Custom storage location (optional).
        properties: Custom table properties.

    Example:
        >>> config = TableConfig(
        ...     namespace="bronze",
        ...     table_name="customers",
        ...     table_schema=TableSchema(fields=[
        ...         SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
        ...     ]),
        ... )
        >>> config.identifier
        'bronze.customers'
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Table identifier
    namespace: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,
        description="Catalog namespace (e.g., 'bronze', 'silver')",
    )
    table_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        pattern=IDENTIFIER_PATTERN,
        description="Table name within namespace",
    )

    # Schema definition (named table_schema to avoid shadowing BaseModel.schema)
    table_schema: TableSchema = Field(
        ...,
        description="Iceberg schema definition with fields",
    )

    # Partitioning (optional)
    partition_spec: PartitionSpec | None = Field(
        default=None,
        description="Partition specification for the table",
    )

    # Storage location (optional, defaults to warehouse)
    location: str | None = Field(
        default=None,
        description="Custom storage location (e.g., 's3://bucket/path')",
    )

    # Custom properties
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Custom table properties",
    )

    @model_validator(mode="after")
    def validate_partition_spec(self) -> "TableConfig":
        """Validate partition specification against table schema.

        Validates:
        - Each partition field's source_field_id exists in table_schema
        - Partition field names are unique

        Returns:
            Self if validation passes.

        Raises:
            ValueError: If partition validation fails.
        """
        if self.partition_spec is None or not self.partition_spec.fields:
            return self

        # Build set of valid field IDs from schema
        valid_field_ids = {field.field_id for field in self.table_schema.fields}

        # Validate source_field_ids exist in schema
        for part_field in self.partition_spec.fields:
            if part_field.source_field_id not in valid_field_ids:
                msg = (
                    f"Partition field '{part_field.name}' has source_field_id "
                    f"{part_field.source_field_id} not found in schema. "
                    f"Valid field IDs: {sorted(valid_field_ids)}"
                )
                raise ValueError(msg)

        # Validate partition field names are unique
        partition_names: list[str] = []
        for part_field in self.partition_spec.fields:
            if part_field.name in partition_names:
                msg = f"Duplicate partition field name: '{part_field.name}'"
                raise ValueError(msg)
            partition_names.append(part_field.name)

        return self

    @property
    def identifier(self) -> str:
        """Full table identifier (namespace.table_name).

        Returns:
            Full qualified table identifier.
        """
        return f"{self.namespace}.{self.table_name}"


# =============================================================================
# Schema Evolution Models
# =============================================================================


class SchemaChange(BaseModel):
    """A single schema change operation.

    Represents one schema modification to apply to an Iceberg table.
    Use SchemaEvolution to apply multiple changes atomically.

    Attributes:
        change_type: Type of schema change operation.
        field: New field definition (required for ADD_COLUMN).
        parent_path: Parent field path for nested fields (optional).
        source_column: Source column for RENAME/WIDEN/DELETE operations.
        new_name: New name for RENAME_COLUMN operation.
        target_type: Target type for WIDEN_TYPE operation.
        target_column: Target column for column operations.
        new_doc: New documentation for UPDATE_DOC operation.

    Example:
        >>> # Add a new column
        >>> change = SchemaChange(
        ...     change_type=SchemaChangeType.ADD_COLUMN,
        ...     field=SchemaField(field_id=10, name="email", field_type=FieldType.STRING),
        ... )

        >>> # Rename a column
        >>> change = SchemaChange(
        ...     change_type=SchemaChangeType.RENAME_COLUMN,
        ...     source_column="old_name",
        ...     new_name="new_name",
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    change_type: SchemaChangeType = Field(
        ...,
        description="Type of schema change operation",
    )

    # For ADD_COLUMN
    field: SchemaField | None = Field(
        default=None,
        description="New field definition (for ADD_COLUMN)",
    )
    parent_path: tuple[str, ...] | None = Field(
        default=None,
        description="Parent field path for nested fields",
    )

    # For RENAME_COLUMN, WIDEN_TYPE, MAKE_OPTIONAL, DELETE_COLUMN
    source_column: str | None = Field(
        default=None,
        description="Source column name for rename/widen/delete operations",
    )

    # For RENAME_COLUMN
    new_name: str | None = Field(
        default=None,
        description="New column name (for RENAME_COLUMN)",
    )

    # For WIDEN_TYPE
    target_type: FieldType | None = Field(
        default=None,
        description="Target type (for WIDEN_TYPE)",
    )

    # For operations on specific columns
    target_column: str | None = Field(
        default=None,
        description="Target column name",
    )

    # For UPDATE_DOC
    new_doc: str | None = Field(
        default=None,
        description="New documentation (for UPDATE_DOC)",
    )


class SchemaEvolution(BaseModel):
    """Batch of schema changes to apply atomically.

    Groups multiple SchemaChange operations that will be applied
    as a single atomic operation to an Iceberg table.

    Attributes:
        changes: List of schema changes to apply (at least one required).
        allow_incompatible_changes: Allow breaking changes like DELETE_COLUMN.
            Default False (fail-safe).

    Example:
        >>> evolution = SchemaEvolution(
        ...     changes=[
        ...         SchemaChange(
        ...             change_type=SchemaChangeType.ADD_COLUMN,
        ...             field=SchemaField(field_id=10, name="email", field_type=FieldType.STRING),
        ...         ),
        ...         SchemaChange(
        ...             change_type=SchemaChangeType.RENAME_COLUMN,
        ...             source_column="old_name",
        ...             new_name="new_name",
        ...         ),
        ...     ],
        ...     allow_incompatible_changes=False,
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    changes: list[SchemaChange] = Field(
        ...,
        min_length=1,
        description="List of schema changes to apply",
    )
    allow_incompatible_changes: bool = Field(
        default=False,
        description="Allow breaking changes (DELETE_COLUMN, etc.)",
    )


# =============================================================================
# Snapshot Models
# =============================================================================


class SnapshotInfo(BaseModel):
    """Information about an Iceberg table snapshot.

    Provides a Pydantic-wrapped view of PyIceberg Snapshot metadata,
    with computed properties for common metrics.

    Attributes:
        snapshot_id: Unique snapshot identifier.
        timestamp_ms: Snapshot creation time in milliseconds since epoch.
        operation: Operation that created the snapshot.
        summary: Snapshot summary metrics (e.g., added-files-count).
        parent_id: Parent snapshot ID (None for first snapshot).

    Properties:
        added_files: Number of files added in this snapshot.
        added_records: Number of records added in this snapshot.

    Example:
        >>> info = SnapshotInfo(
        ...     snapshot_id=1234567890,
        ...     timestamp_ms=1705500000000,
        ...     operation=OperationType.APPEND,
        ...     summary={"added-files-count": "5", "added-records-count": "1000"},
        ... )
        >>> info.added_files
        5
        >>> info.added_records
        1000
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: int = Field(
        ...,
        description="Unique snapshot identifier",
    )
    timestamp_ms: int = Field(
        ...,
        ge=0,
        description="Snapshot creation time in milliseconds since epoch",
    )
    operation: OperationType = Field(
        ...,
        description="Operation that created the snapshot",
    )
    summary: dict[str, str] = Field(
        default_factory=dict,
        description="Snapshot summary metrics",
    )
    parent_id: int | None = Field(
        default=None,
        description="Parent snapshot ID (None for first snapshot)",
    )

    @property
    def added_files(self) -> int:
        """Number of files added in this snapshot.

        Returns:
            Count of added files, 0 if not in summary.
        """
        return int(self.summary.get("added-files-count", "0"))

    @property
    def added_records(self) -> int:
        """Number of records added in this snapshot.

        Returns:
            Count of added records, 0 if not in summary.
        """
        return int(self.summary.get("added-records-count", "0"))

    @classmethod
    def from_pyiceberg_snapshot(cls, snapshot: "pyiceberg.table.Snapshot") -> "SnapshotInfo":
        """Create SnapshotInfo from a PyIceberg Snapshot.

        Args:
            snapshot: PyIceberg Snapshot object.

        Returns:
            SnapshotInfo instance with data from the snapshot.
        """
        # Map PyIceberg operation string to OperationType enum
        operation_mapping = {
            "append": OperationType.APPEND,
            "overwrite": OperationType.OVERWRITE,
            "delete": OperationType.DELETE,
            "replace": OperationType.REPLACE,
        }
        operation = operation_mapping.get(
            snapshot.summary.operation if snapshot.summary else "append",
            OperationType.APPEND,
        )

        return cls(
            snapshot_id=snapshot.snapshot_id,
            timestamp_ms=snapshot.timestamp_ms,
            operation=operation,
            summary=dict(snapshot.summary) if snapshot.summary else {},
            parent_id=snapshot.parent_snapshot_id,
        )


# =============================================================================
# Write Configuration Models
# =============================================================================


class WriteConfig(BaseModel):
    """Configuration for write operations.

    Defines how data should be written to Iceberg tables, including
    write mode, commit strategy, and optional filters.

    Attributes:
        mode: Write mode (APPEND, OVERWRITE, UPSERT).
        commit_strategy: How to commit changes (FAST_APPEND, MERGE_COMMIT).
        overwrite_filter: Optional filter expression for OVERWRITE mode.
        join_columns: Columns to use for UPSERT merge (required for UPSERT).
        snapshot_properties: Custom properties to add to snapshot summary.

    Example:
        >>> # Simple append
        >>> config = WriteConfig()
        >>> config.mode
        <WriteMode.APPEND: 'append'>

        >>> # Upsert with join columns
        >>> config = WriteConfig(
        ...     mode=WriteMode.UPSERT,
        ...     join_columns=["id", "date"],
        ... )
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: WriteMode = Field(
        default=WriteMode.APPEND,
        description="Write mode (APPEND, OVERWRITE, UPSERT)",
    )
    commit_strategy: CommitStrategy = Field(
        default=CommitStrategy.FAST_APPEND,
        description="Commit strategy (FAST_APPEND, MERGE_COMMIT)",
    )
    overwrite_filter: str | None = Field(
        default=None,
        description="Filter expression for OVERWRITE mode (e.g., 'date = 2024-01-01')",
    )
    join_columns: list[str] | None = Field(
        default=None,
        description="Columns for UPSERT merge (required when mode=UPSERT)",
    )
    snapshot_properties: dict[str, str] = Field(
        default_factory=dict,
        description="Custom properties to add to snapshot summary",
    )

    @model_validator(mode="after")
    def validate_upsert_requires_join_columns(self) -> "WriteConfig":
        """Validate that join_columns is provided when mode is UPSERT.

        Returns:
            Self if validation passes.

        Raises:
            ValueError: If mode is UPSERT but join_columns is not provided.
        """
        if self.mode == WriteMode.UPSERT and not self.join_columns:
            msg = "join_columns is required when mode is UPSERT"
            raise ValueError(msg)
        return self


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
    # Schema and partition models
    "SchemaField",
    "TableSchema",
    "PartitionField",
    "PartitionSpec",
    "TableConfig",
    # Schema evolution models
    "SchemaChange",
    "SchemaEvolution",
    # Snapshot models
    "SnapshotInfo",
    # Write configuration
    "WriteConfig",
    # Configuration models
    "IcebergTableManagerConfig",
    "IcebergIOManagerConfig",
]
