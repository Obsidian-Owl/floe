"""Unit tests for floe-iceberg error types.

Tests the exception hierarchy and error message formatting for all
exception types defined in floe_iceberg.errors.
"""

from __future__ import annotations

import pytest

from floe_iceberg.errors import (
    CommitConflictError,
    CompactionError,
    IcebergError,
    IncompatibleSchemaChangeError,
    NoSuchNamespaceError,
    NoSuchTableError,
    RollbackError,
    SchemaEvolutionError,
    SnapshotError,
    SnapshotNotFoundError,
    TableAlreadyExistsError,
    TableError,
    ValidationError,
    WriteError,
)

# =============================================================================
# Base Exception Tests
# =============================================================================


class TestIcebergError:
    """Tests for base IcebergError exception."""

    @pytest.mark.requirement("FR-001")
    def test_basic_construction(self) -> None:
        """Test IcebergError can be constructed with message only."""
        error = IcebergError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details == {}

    @pytest.mark.requirement("FR-001")
    def test_construction_with_details(self) -> None:
        """Test IcebergError includes details in string representation."""
        error = IcebergError(
            "Operation failed",
            details={"table": "test", "reason": "timeout"},
        )
        assert "Operation failed" in str(error)
        assert "table=test" in str(error)
        assert "reason=timeout" in str(error)
        assert error.details == {"table": "test", "reason": "timeout"}

    @pytest.mark.requirement("FR-001")
    def test_inheritance(self) -> None:
        """Test IcebergError inherits from Exception."""
        error = IcebergError("Test")
        assert isinstance(error, Exception)

    @pytest.mark.requirement("FR-001")
    def test_can_be_caught_as_exception(self) -> None:
        """Test IcebergError can be caught as Exception."""
        with pytest.raises(Exception):  # noqa: B017 - intentional: testing inheritance
            raise IcebergError("Test error")

    @pytest.mark.requirement("FR-001")
    def test_empty_details_not_shown_in_str(self) -> None:
        """Test string representation doesn't include empty details."""
        error = IcebergError("Simple error")
        assert str(error) == "Simple error"
        assert "(" not in str(error)


# =============================================================================
# Validation Error Tests
# =============================================================================


class TestValidationError:
    """Tests for ValidationError exception."""

    @pytest.mark.requirement("FR-001")
    def test_basic_construction(self) -> None:
        """Test ValidationError with message only."""
        error = ValidationError("Invalid input")
        assert str(error) == "Invalid input"
        assert error.field is None
        assert error.value is None

    @pytest.mark.requirement("FR-001")
    def test_construction_with_field(self) -> None:
        """Test ValidationError with field information."""
        error = ValidationError("Invalid value", field="namespace")
        assert "Invalid value" in str(error)
        assert "field=namespace" in str(error)
        assert error.field == "namespace"

    @pytest.mark.requirement("FR-001")
    def test_construction_with_field_and_value(self) -> None:
        """Test ValidationError with field and value."""
        error = ValidationError("Invalid value", field="age", value=-5)
        assert error.field == "age"
        assert error.value == -5
        assert "field=age" in str(error)
        assert "value=-5" in str(error)

    @pytest.mark.requirement("FR-001")
    def test_inheritance(self) -> None:
        """Test ValidationError inherits from IcebergError."""
        error = ValidationError("Test")
        assert isinstance(error, IcebergError)

    @pytest.mark.requirement("FR-001")
    def test_can_be_caught_as_iceberg_error(self) -> None:
        """Test ValidationError can be caught as IcebergError."""
        with pytest.raises(IcebergError):
            raise ValidationError("Invalid input")


# =============================================================================
# Table Error Tests
# =============================================================================


class TestTableError:
    """Tests for TableError and subclasses."""

    @pytest.mark.requirement("FR-001")
    def test_table_error_basic(self) -> None:
        """Test TableError with message only."""
        error = TableError("Table operation failed")
        assert "Table operation failed" in str(error)
        assert error.table_identifier is None

    @pytest.mark.requirement("FR-001")
    def test_table_error_with_identifier(self) -> None:
        """Test TableError includes table identifier."""
        error = TableError("Failed", table_identifier="bronze.customers")
        assert error.table_identifier == "bronze.customers"
        assert "table_identifier=bronze.customers" in str(error)

    @pytest.mark.requirement("FR-001")
    def test_table_error_inheritance(self) -> None:
        """Test TableError inherits from IcebergError."""
        error = TableError("Test")
        assert isinstance(error, IcebergError)


class TestTableAlreadyExistsError:
    """Tests for TableAlreadyExistsError exception."""

    @pytest.mark.requirement("FR-001")
    def test_basic_construction(self) -> None:
        """Test TableAlreadyExistsError construction."""
        error = TableAlreadyExistsError(
            "Table already exists",
            table_identifier="bronze.customers",
        )
        assert error.table_identifier == "bronze.customers"
        assert "Table already exists" in str(error)

    @pytest.mark.requirement("FR-001")
    def test_inheritance(self) -> None:
        """Test TableAlreadyExistsError inherits from TableError."""
        error = TableAlreadyExistsError("Test")
        assert isinstance(error, TableError)
        assert isinstance(error, IcebergError)

    @pytest.mark.requirement("FR-001")
    def test_can_be_caught_specifically(self) -> None:
        """Test TableAlreadyExistsError can be caught specifically."""
        with pytest.raises(TableAlreadyExistsError):
            raise TableAlreadyExistsError("Table exists", table_identifier="test.table")


class TestNoSuchTableError:
    """Tests for NoSuchTableError exception."""

    @pytest.mark.requirement("FR-001")
    def test_basic_construction(self) -> None:
        """Test NoSuchTableError construction."""
        error = NoSuchTableError(
            "Table not found",
            table_identifier="bronze.nonexistent",
        )
        assert error.table_identifier == "bronze.nonexistent"
        assert "Table not found" in str(error)

    @pytest.mark.requirement("FR-001")
    def test_inheritance(self) -> None:
        """Test NoSuchTableError inherits from TableError."""
        error = NoSuchTableError("Test")
        assert isinstance(error, TableError)
        assert isinstance(error, IcebergError)


class TestNoSuchNamespaceError:
    """Tests for NoSuchNamespaceError exception."""

    @pytest.mark.requirement("FR-001")
    def test_basic_construction(self) -> None:
        """Test NoSuchNamespaceError construction."""
        error = NoSuchNamespaceError(
            "Namespace not found",
            namespace="nonexistent",
        )
        assert error.namespace == "nonexistent"
        assert "Namespace not found" in str(error)
        assert "namespace=nonexistent" in str(error)

    @pytest.mark.requirement("FR-001")
    def test_inheritance(self) -> None:
        """Test NoSuchNamespaceError inherits from TableError."""
        error = NoSuchNamespaceError("Test")
        assert isinstance(error, TableError)
        assert isinstance(error, IcebergError)

    @pytest.mark.requirement("FR-001")
    def test_without_namespace(self) -> None:
        """Test NoSuchNamespaceError without namespace parameter."""
        error = NoSuchNamespaceError("Namespace error")
        assert error.namespace is None


# =============================================================================
# Schema Evolution Error Tests
# =============================================================================


class TestSchemaEvolutionError:
    """Tests for SchemaEvolutionError exception."""

    @pytest.mark.requirement("FR-002")
    def test_basic_construction(self) -> None:
        """Test SchemaEvolutionError construction."""
        error = SchemaEvolutionError("Schema evolution failed")
        assert "Schema evolution failed" in str(error)
        assert error.table_identifier is None
        assert error.change_type is None

    @pytest.mark.requirement("FR-002")
    def test_with_table_and_change_type(self) -> None:
        """Test SchemaEvolutionError with full context."""
        error = SchemaEvolutionError(
            "Cannot rename column",
            table_identifier="bronze.customers",
            change_type="rename_column",
            details={"column": "old_name"},
        )
        assert error.table_identifier == "bronze.customers"
        assert error.change_type == "rename_column"
        assert "table_identifier=bronze.customers" in str(error)
        assert "change_type=rename_column" in str(error)

    @pytest.mark.requirement("FR-002")
    def test_inheritance(self) -> None:
        """Test SchemaEvolutionError inherits from IcebergError."""
        error = SchemaEvolutionError("Test")
        assert isinstance(error, IcebergError)


class TestIncompatibleSchemaChangeError:
    """Tests for IncompatibleSchemaChangeError exception."""

    @pytest.mark.requirement("FR-002")
    def test_basic_construction(self) -> None:
        """Test IncompatibleSchemaChangeError construction."""
        error = IncompatibleSchemaChangeError(
            "Cannot delete column without allow_incompatible_changes=True",
            table_identifier="bronze.customers",
            change_type="delete_column",
        )
        assert "Cannot delete column" in str(error)
        assert error.change_type == "delete_column"

    @pytest.mark.requirement("FR-002")
    def test_inheritance(self) -> None:
        """Test IncompatibleSchemaChangeError inherits from SchemaEvolutionError."""
        error = IncompatibleSchemaChangeError("Test")
        assert isinstance(error, SchemaEvolutionError)
        assert isinstance(error, IcebergError)


# =============================================================================
# Write Error Tests
# =============================================================================


class TestWriteError:
    """Tests for WriteError exception."""

    @pytest.mark.requirement("FR-003")
    def test_basic_construction(self) -> None:
        """Test WriteError construction."""
        error = WriteError("Write failed")
        assert "Write failed" in str(error)
        assert error.table_identifier is None
        assert error.write_mode is None

    @pytest.mark.requirement("FR-003")
    def test_with_full_context(self) -> None:
        """Test WriteError with table and write mode."""
        error = WriteError(
            "Data schema mismatch",
            table_identifier="bronze.customers",
            write_mode="append",
        )
        assert error.table_identifier == "bronze.customers"
        assert error.write_mode == "append"
        assert "write_mode=append" in str(error)

    @pytest.mark.requirement("FR-003")
    def test_inheritance(self) -> None:
        """Test WriteError inherits from IcebergError."""
        error = WriteError("Test")
        assert isinstance(error, IcebergError)


class TestCommitConflictError:
    """Tests for CommitConflictError exception."""

    @pytest.mark.requirement("FR-003")
    def test_basic_construction(self) -> None:
        """Test CommitConflictError construction."""
        error = CommitConflictError(
            "Commit failed after retries",
            table_identifier="bronze.customers",
            retry_count=3,
        )
        assert error.retry_count == 3
        assert "retry_count=3" in str(error)

    @pytest.mark.requirement("FR-003")
    def test_default_retry_count(self) -> None:
        """Test CommitConflictError default retry count is 0."""
        error = CommitConflictError("Commit failed")
        assert error.retry_count == 0
        assert "retry_count=0" in str(error)

    @pytest.mark.requirement("FR-003")
    def test_inheritance(self) -> None:
        """Test CommitConflictError inherits from WriteError."""
        error = CommitConflictError("Test")
        assert isinstance(error, WriteError)
        assert isinstance(error, IcebergError)


# =============================================================================
# Snapshot Error Tests
# =============================================================================


class TestSnapshotError:
    """Tests for SnapshotError base class."""

    @pytest.mark.requirement("FR-004")
    def test_basic_construction(self) -> None:
        """Test SnapshotError construction."""
        error = SnapshotError("Snapshot operation failed")
        assert "Snapshot operation failed" in str(error)
        assert error.table_identifier is None
        assert error.snapshot_id is None

    @pytest.mark.requirement("FR-004")
    def test_with_full_context(self) -> None:
        """Test SnapshotError with table and snapshot ID."""
        error = SnapshotError(
            "Snapshot error",
            table_identifier="bronze.customers",
            snapshot_id=12345,
        )
        assert error.table_identifier == "bronze.customers"
        assert error.snapshot_id == 12345
        assert "snapshot_id=12345" in str(error)

    @pytest.mark.requirement("FR-004")
    def test_inheritance(self) -> None:
        """Test SnapshotError inherits from IcebergError."""
        error = SnapshotError("Test")
        assert isinstance(error, IcebergError)


class TestSnapshotNotFoundError:
    """Tests for SnapshotNotFoundError exception."""

    @pytest.mark.requirement("FR-004")
    def test_basic_construction(self) -> None:
        """Test SnapshotNotFoundError construction."""
        error = SnapshotNotFoundError(
            "Snapshot not found",
            table_identifier="bronze.customers",
            snapshot_id=12345,
        )
        assert error.snapshot_id == 12345
        assert "Snapshot not found" in str(error)

    @pytest.mark.requirement("FR-004")
    def test_inheritance(self) -> None:
        """Test SnapshotNotFoundError inherits from SnapshotError."""
        error = SnapshotNotFoundError("Test")
        assert isinstance(error, SnapshotError)
        assert isinstance(error, IcebergError)


class TestRollbackError:
    """Tests for RollbackError exception."""

    @pytest.mark.requirement("FR-004")
    def test_basic_construction(self) -> None:
        """Test RollbackError construction."""
        error = RollbackError(
            "Cannot rollback: snapshot expired",
            table_identifier="bronze.customers",
            snapshot_id=12345,
        )
        assert error.snapshot_id == 12345
        assert "Cannot rollback" in str(error)

    @pytest.mark.requirement("FR-004")
    def test_inheritance(self) -> None:
        """Test RollbackError inherits from SnapshotError."""
        error = RollbackError("Test")
        assert isinstance(error, SnapshotError)
        assert isinstance(error, IcebergError)


class TestCompactionError:
    """Tests for CompactionError exception."""

    @pytest.mark.requirement("FR-005")
    def test_basic_construction(self) -> None:
        """Test CompactionError construction."""
        error = CompactionError(
            "Compaction failed",
            table_identifier="bronze.customers",
            strategy="bin_pack",
        )
        assert error.strategy == "bin_pack"
        assert "strategy=bin_pack" in str(error)

    @pytest.mark.requirement("FR-005")
    def test_without_strategy(self) -> None:
        """Test CompactionError without strategy."""
        error = CompactionError("Compaction failed")
        assert error.strategy is None

    @pytest.mark.requirement("FR-005")
    def test_inheritance(self) -> None:
        """Test CompactionError inherits from SnapshotError."""
        error = CompactionError("Test")
        assert isinstance(error, SnapshotError)
        assert isinstance(error, IcebergError)


# =============================================================================
# Exception Hierarchy Tests
# =============================================================================


class TestExceptionHierarchy:
    """Tests for exception hierarchy and catch-all behavior."""

    @pytest.mark.requirement("FR-001")
    def test_all_exceptions_inherit_from_iceberg_error(self) -> None:
        """Test all custom exceptions inherit from IcebergError."""
        exceptions = [
            ValidationError("test"),
            TableError("test"),
            TableAlreadyExistsError("test"),
            NoSuchTableError("test"),
            NoSuchNamespaceError("test"),
            SchemaEvolutionError("test"),
            IncompatibleSchemaChangeError("test"),
            WriteError("test"),
            CommitConflictError("test"),
            SnapshotError("test"),
            SnapshotNotFoundError("test"),
            RollbackError("test"),
            CompactionError("test"),
        ]

        for exc in exceptions:
            assert isinstance(
                exc, IcebergError
            ), f"{type(exc).__name__} should inherit from IcebergError"

    @pytest.mark.requirement("FR-001")
    def test_catch_all_with_iceberg_error(self) -> None:
        """Test IcebergError can catch all subclass exceptions."""
        exception_classes = [
            ValidationError,
            TableAlreadyExistsError,
            NoSuchTableError,
            NoSuchNamespaceError,
            SchemaEvolutionError,
            IncompatibleSchemaChangeError,
            WriteError,
            CommitConflictError,
            SnapshotNotFoundError,
            RollbackError,
            CompactionError,
        ]

        for exc_class in exception_classes:
            caught = False
            try:
                raise exc_class("Test error")
            except IcebergError:
                caught = True
            assert caught, f"{exc_class.__name__} should be catchable as IcebergError"

    @pytest.mark.requirement("FR-001")
    def test_specific_catch_before_general(self) -> None:
        """Test specific exceptions can be caught before general ones."""
        caught_type = None
        try:
            raise TableAlreadyExistsError("Table exists", table_identifier="test.table")
        except TableAlreadyExistsError:
            caught_type = "specific"
        except TableError:
            caught_type = "table"
        except IcebergError:
            caught_type = "general"

        assert caught_type == "specific"
