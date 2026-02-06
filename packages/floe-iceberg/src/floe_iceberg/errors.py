"""Exception types for floe-iceberg package.

This module defines the exception hierarchy for IcebergTableManager operations.
All exceptions inherit from IcebergError to enable catch-all error handling.

Exception Hierarchy:
    IcebergError (base)
    ├── ValidationError - Input validation failures
    ├── TableError - Table-related errors
    │   ├── TableAlreadyExistsError - Table creation conflict
    │   ├── NoSuchTableError - Table not found
    │   └── NoSuchNamespaceError - Namespace not found
    ├── SchemaEvolutionError - Schema change failures
    │   └── IncompatibleSchemaChangeError - Breaking change rejected
    ├── WriteError - Write operation failures
    │   └── CommitConflictError - Optimistic locking failure
    └── SnapshotError - Snapshot-related errors
        ├── SnapshotNotFoundError - Snapshot not found
        ├── RollbackError - Rollback operation failed
        └── CompactionError - Compaction operation failed

Example:
    >>> from floe_iceberg.errors import IcebergError, TableAlreadyExistsError
    >>> try:
    ...     manager.create_table(config)
    ... except TableAlreadyExistsError as e:
    ...     print(f"Table {e.table_identifier} already exists")
    ... except IcebergError as e:
    ...     print(f"Iceberg operation failed: {e}")
"""

from __future__ import annotations

from typing import Any


class IcebergError(Exception):
    """Base exception for all floe-iceberg errors.

    All exceptions raised by IcebergTableManager inherit from this class,
    enabling catch-all error handling for Iceberg operations.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional error context.

    Example:
        >>> try:
        ...     manager.create_table(config)
        ... except IcebergError as e:
        ...     logger.error("Iceberg operation failed", error=str(e), details=e.details)
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize IcebergError.

        Args:
            message: Human-readable error description.
            details: Optional dictionary with additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(IcebergError):
    """Input validation failed.

    Raised when configuration, schema, or data validation fails before
    an operation is attempted.

    Attributes:
        field: Name of the field that failed validation (if applicable).
        value: The invalid value (if applicable and safe to include).

    Example:
        >>> raise ValidationError(
        ...     "Invalid partition transform",
        ...     details={"field": "transform", "value": "invalid", "allowed": ["identity", "year"]}
        ... )
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ValidationError.

        Args:
            message: Human-readable error description.
            field: Name of the field that failed validation.
            value: The invalid value.
            details: Additional error context.
        """
        _details = details or {}
        if field:
            _details["field"] = field
        if value is not None:
            _details["value"] = str(value)
        super().__init__(message, _details)
        self.field = field
        self.value = value


# =============================================================================
# Table Errors
# =============================================================================


class TableError(IcebergError):
    """Base class for table-related errors.

    Attributes:
        table_identifier: Full table identifier (namespace.table_name).
    """

    def __init__(
        self,
        message: str,
        table_identifier: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize TableError.

        Args:
            message: Human-readable error description.
            table_identifier: Full table identifier.
            details: Additional error context.
        """
        _details = details or {}
        if table_identifier:
            _details["table_identifier"] = table_identifier
        super().__init__(message, _details)
        self.table_identifier = table_identifier


class TableAlreadyExistsError(TableError):
    """Table already exists in the catalog.

    Raised when attempting to create a table that already exists and
    if_not_exists=False.

    Example:
        >>> raise TableAlreadyExistsError(
        ...     "Table already exists",
        ...     table_identifier="bronze.customers"
        ... )
    """

    pass


class NoSuchTableError(TableError):
    """Table not found in the catalog.

    Raised when attempting to load, modify, or delete a table that
    does not exist.

    Example:
        >>> raise NoSuchTableError(
        ...     "Table not found",
        ...     table_identifier="bronze.nonexistent"
        ... )
    """

    pass


class NoSuchNamespaceError(TableError):
    """Namespace not found in the catalog.

    Raised when attempting to create a table in a namespace that
    does not exist.

    Attributes:
        namespace: The namespace that was not found.

    Example:
        >>> raise NoSuchNamespaceError(
        ...     "Namespace not found",
        ...     namespace="nonexistent"
        ... )
    """

    def __init__(
        self,
        message: str,
        namespace: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize NoSuchNamespaceError.

        Args:
            message: Human-readable error description.
            namespace: The namespace that was not found.
            details: Additional error context.
        """
        _details = details or {}
        if namespace:
            _details["namespace"] = namespace
        super().__init__(message, details=_details)
        self.namespace = namespace


# =============================================================================
# Schema Evolution Errors
# =============================================================================


class SchemaEvolutionError(IcebergError):
    """Schema evolution operation failed.

    Raised when a schema change cannot be applied to a table.

    Attributes:
        table_identifier: Full table identifier.
        change_type: Type of schema change that failed.

    Example:
        >>> raise SchemaEvolutionError(
        ...     "Cannot rename column: column does not exist",
        ...     table_identifier="bronze.customers",
        ...     change_type="rename_column",
        ...     details={"column": "old_name"}
        ... )
    """

    def __init__(
        self,
        message: str,
        table_identifier: str | None = None,
        change_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize SchemaEvolutionError.

        Args:
            message: Human-readable error description.
            table_identifier: Full table identifier.
            change_type: Type of schema change that failed.
            details: Additional error context.
        """
        _details = details or {}
        if table_identifier:
            _details["table_identifier"] = table_identifier
        if change_type:
            _details["change_type"] = change_type
        super().__init__(message, _details)
        self.table_identifier = table_identifier
        self.change_type = change_type


class IncompatibleSchemaChangeError(SchemaEvolutionError):
    """Incompatible schema change rejected.

    Raised when attempting a breaking schema change (e.g., DELETE_COLUMN)
    without setting allow_incompatible_changes=True.

    Example:
        >>> raise IncompatibleSchemaChangeError(
        ...     "Cannot delete column without allow_incompatible_changes=True",
        ...     table_identifier="bronze.customers",
        ...     change_type="delete_column",
        ...     details={"column": "deprecated_field"}
        ... )
    """

    pass


# =============================================================================
# Write Errors
# =============================================================================


class WriteError(IcebergError):
    """Write operation failed.

    Raised when a write operation (append, overwrite, upsert) fails.

    Attributes:
        table_identifier: Full table identifier.
        write_mode: The write mode that was attempted.

    Example:
        >>> raise WriteError(
        ...     "Write operation failed: data schema mismatch",
        ...     table_identifier="bronze.customers",
        ...     write_mode="append"
        ... )
    """

    def __init__(
        self,
        message: str,
        table_identifier: str | None = None,
        write_mode: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize WriteError.

        Args:
            message: Human-readable error description.
            table_identifier: Full table identifier.
            write_mode: The write mode that was attempted.
            details: Additional error context.
        """
        _details = details or {}
        if table_identifier:
            _details["table_identifier"] = table_identifier
        if write_mode:
            _details["write_mode"] = write_mode
        super().__init__(message, _details)
        self.table_identifier = table_identifier
        self.write_mode = write_mode


class CommitConflictError(WriteError):
    """Optimistic locking failure during commit.

    Raised when a commit fails due to concurrent modifications.
    The operation should be retried with fresh data.

    Attributes:
        retry_count: Number of retries attempted before failing.

    Example:
        >>> raise CommitConflictError(
        ...     "Commit failed after 3 retries",
        ...     table_identifier="bronze.customers",
        ...     retry_count=3
        ... )
    """

    def __init__(
        self,
        message: str,
        table_identifier: str | None = None,
        retry_count: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CommitConflictError.

        Args:
            message: Human-readable error description.
            table_identifier: Full table identifier.
            retry_count: Number of retries attempted.
            details: Additional error context.
        """
        _details = details or {}
        _details["retry_count"] = retry_count
        super().__init__(message, table_identifier=table_identifier, details=_details)
        self.retry_count = retry_count


# =============================================================================
# Snapshot Errors
# =============================================================================


class SnapshotError(IcebergError):
    """Base class for snapshot-related errors.

    Attributes:
        table_identifier: Full table identifier.
        snapshot_id: The snapshot ID involved in the error.
    """

    def __init__(
        self,
        message: str,
        table_identifier: str | None = None,
        snapshot_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize SnapshotError.

        Args:
            message: Human-readable error description.
            table_identifier: Full table identifier.
            snapshot_id: The snapshot ID involved in the error.
            details: Additional error context.
        """
        _details = details or {}
        if table_identifier:
            _details["table_identifier"] = table_identifier
        if snapshot_id is not None:
            _details["snapshot_id"] = snapshot_id
        super().__init__(message, _details)
        self.table_identifier = table_identifier
        self.snapshot_id = snapshot_id


class SnapshotNotFoundError(SnapshotError):
    """Snapshot not found in table history.

    Raised when attempting to access a snapshot that does not exist
    (may have been expired or never existed).

    Example:
        >>> raise SnapshotNotFoundError(
        ...     "Snapshot not found",
        ...     table_identifier="bronze.customers",
        ...     snapshot_id=12345
        ... )
    """

    pass


class RollbackError(SnapshotError):
    """Rollback operation failed.

    Raised when a rollback to a previous snapshot fails.

    Example:
        >>> raise RollbackError(
        ...     "Cannot rollback: snapshot has been expired",
        ...     table_identifier="bronze.customers",
        ...     snapshot_id=12345
        ... )
    """

    pass


class CompactionError(SnapshotError):
    """Compaction operation failed.

    Raised when a table compaction operation fails.

    Attributes:
        strategy: The compaction strategy that was attempted.

    Example:
        >>> raise CompactionError(
        ...     "Compaction failed: concurrent modification",
        ...     table_identifier="bronze.customers",
        ...     strategy="bin_pack"
        ... )
    """

    def __init__(
        self,
        message: str,
        table_identifier: str | None = None,
        strategy: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CompactionError.

        Args:
            message: Human-readable error description.
            table_identifier: Full table identifier.
            strategy: The compaction strategy that was attempted.
            details: Additional error context.
        """
        _details = details or {}
        if strategy:
            _details["strategy"] = strategy
        super().__init__(message, table_identifier=table_identifier, details=_details)
        self.strategy = strategy


class CompactionAnalysisError(IcebergError):
    """Raised when compaction analysis fails.

    This replaces silent swallowing of exceptions during snapshot
    manifest traversal. Callers should handle this explicitly rather
    than receiving misleading (0, 0) return values.

    Example:
        >>> raise CompactionAnalysisError(
        ...     "Cannot access manifests for snapshot: connection refused"
        ... )
    """


# Export all exception types
__all__ = [
    # Base
    "IcebergError",
    # Validation
    "ValidationError",
    # Table errors
    "TableError",
    "TableAlreadyExistsError",
    "NoSuchTableError",
    "NoSuchNamespaceError",
    # Schema errors
    "SchemaEvolutionError",
    "IncompatibleSchemaChangeError",
    # Write errors
    "WriteError",
    "CommitConflictError",
    # Snapshot errors
    "SnapshotError",
    "SnapshotNotFoundError",
    "RollbackError",
    "CompactionError",
    "CompactionAnalysisError",
]
