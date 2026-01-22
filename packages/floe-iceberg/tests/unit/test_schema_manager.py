"""Unit tests for _IcebergSchemaManager class.

Task ID: T027
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-014, FR-016, FR-017

Tests for the _IcebergSchemaManager helper class that encapsulates schema
evolution operations. Written TDD-style before implementation (T031).

The _IcebergSchemaManager class will be extracted from IcebergTableManager
to reduce class complexity and improve single-responsibility adherence.

Operations covered:
- evolve_schema(): Apply schema changes atomically
- Add column (optional/required)
- Rename column
- Widen type (INT→LONG, FLOAT→DOUBLE)
- Make column optional
- Delete column (requires allow_incompatible_changes)
- Update column documentation
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


# =============================================================================
# Fixtures for Schema Evolution Tests
# =============================================================================


@pytest.fixture
def schema_manager(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
) -> Any:
    """Create an IcebergTableManager with a table for schema evolution testing.

    The manager provides access to schema evolution operations. After T031,
    this fixture will return _IcebergSchemaManager directly.

    Args:
        mock_catalog_plugin: Mock catalog plugin fixture.
        mock_storage_plugin: Mock storage plugin fixture.

    Returns:
        IcebergTableManager configured for schema evolution testing.
    """
    from floe_iceberg import IcebergTableManager
    from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

    # Create manager
    manager = IcebergTableManager(
        catalog_plugin=mock_catalog_plugin,
        storage_plugin=mock_storage_plugin,
    )

    # Create test namespace
    mock_catalog_plugin.create_namespace(
        "bronze",
        {"location": "s3://mock-warehouse-bucket/warehouse/bronze"},
    )

    # Create a test table with schema
    schema = TableSchema(
        fields=[
            SchemaField(
                field_id=1,
                name="id",
                field_type=FieldType.LONG,
                required=True,
                doc="Primary key",
            ),
            SchemaField(
                field_id=2,
                name="name",
                field_type=FieldType.STRING,
                required=False,
                doc="Customer name",
            ),
            SchemaField(
                field_id=3,
                name="age",
                field_type=FieldType.INT,
                required=False,
                doc="Age in years",
            ),
            SchemaField(
                field_id=4,
                name="score",
                field_type=FieldType.FLOAT,
                required=False,
                doc="Score value",
            ),
        ]
    )

    config = TableConfig(
        namespace="bronze",
        table_name="customers",
        table_schema=schema,
        properties={"owner": "data-platform"},
    )

    manager.create_table(config)

    return manager


@pytest.fixture
def test_table(schema_manager: Any) -> Any:
    """Load the test table for schema evolution.

    Args:
        schema_manager: Manager with test table created.

    Returns:
        Mock table object for schema evolution testing.
    """
    return schema_manager.load_table("bronze.customers")


# =============================================================================
# Add Column Tests (T027)
# =============================================================================


class TestSchemaManagerAddColumn:
    """Tests for _IcebergSchemaManager add column operations."""

    @pytest.mark.requirement("FR-016")
    def test_add_optional_column_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test adding an optional column succeeds."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="email",
                        field_type=FieldType.STRING,
                        required=False,
                        doc="Email address",
                    ),
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-016")
    def test_add_required_column_requires_incompatible_flag(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test adding a required column requires allow_incompatible_changes=True."""
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="required_field",
                        field_type=FieldType.STRING,
                        required=True,  # Required = incompatible change
                    ),
                ),
            ],
            allow_incompatible_changes=False,
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            schema_manager.evolve_schema(test_table, evolution)

    @pytest.mark.requirement("FR-016")
    def test_add_required_column_with_incompatible_flag_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test adding a required column succeeds with allow_incompatible_changes=True."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="required_field",
                        field_type=FieldType.STRING,
                        required=True,
                    ),
                ),
            ],
            allow_incompatible_changes=True,  # Allow breaking change
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-016")
    def test_add_column_with_various_types(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test adding columns with different field types."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="created_at",
                        field_type=FieldType.TIMESTAMPTZ,
                        required=False,
                    ),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=11,
                        name="is_active",
                        field_type=FieldType.BOOLEAN,
                        required=False,
                    ),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=12,
                        name="birth_date",
                        field_type=FieldType.DATE,
                        required=False,
                    ),
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None


# =============================================================================
# Rename Column Tests (T027)
# =============================================================================


class TestSchemaManagerRenameColumn:
    """Tests for _IcebergSchemaManager rename column operations."""

    @pytest.mark.requirement("FR-016")
    def test_rename_existing_column_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test renaming an existing column succeeds."""
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="name",
                    new_name="full_name",
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-016")
    def test_rename_nonexistent_column_raises(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test renaming a nonexistent column raises SchemaEvolutionError."""
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="nonexistent_column",
                    new_name="new_name",
                ),
            ],
        )

        with pytest.raises(SchemaEvolutionError, match="does not exist"):
            schema_manager.evolve_schema(test_table, evolution)


# =============================================================================
# Widen Type Tests (T027)
# =============================================================================


class TestSchemaManagerWidenType:
    """Tests for _IcebergSchemaManager type widening operations."""

    @pytest.mark.requirement("FR-017")
    def test_widen_int_to_long_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test widening INT to LONG succeeds (valid widening)."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="age",  # INT field
                    target_type=FieldType.LONG,
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-017")
    def test_widen_float_to_double_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test widening FLOAT to DOUBLE succeeds (valid widening)."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="score",  # FLOAT field
                    target_type=FieldType.DOUBLE,
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-017")
    def test_invalid_type_widening_raises(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test invalid type widening raises IncompatibleSchemaChangeError."""
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="name",  # STRING field
                    target_type=FieldType.LONG,  # Invalid: STRING cannot widen to LONG
                ),
            ],
        )

        with pytest.raises(IncompatibleSchemaChangeError, match="Cannot widen type"):
            schema_manager.evolve_schema(test_table, evolution)

    @pytest.mark.requirement("FR-017")
    def test_widen_nonexistent_column_raises(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test widening a nonexistent column raises SchemaEvolutionError."""
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="nonexistent",
                    target_type=FieldType.LONG,
                ),
            ],
        )

        with pytest.raises(SchemaEvolutionError, match="does not exist"):
            schema_manager.evolve_schema(test_table, evolution)


# =============================================================================
# Make Optional Tests (T027)
# =============================================================================


class TestSchemaManagerMakeOptional:
    """Tests for _IcebergSchemaManager make optional operations."""

    @pytest.mark.requirement("FR-016")
    def test_make_column_optional_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test making a required column optional succeeds."""
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.MAKE_OPTIONAL,
                    source_column="id",  # Required field
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-016")
    def test_make_nonexistent_column_optional_raises(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test making a nonexistent column optional raises error."""
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.MAKE_OPTIONAL,
                    source_column="nonexistent",
                ),
            ],
        )

        with pytest.raises(SchemaEvolutionError, match="does not exist"):
            schema_manager.evolve_schema(test_table, evolution)


# =============================================================================
# Delete Column Tests (T027)
# =============================================================================


class TestSchemaManagerDeleteColumn:
    """Tests for _IcebergSchemaManager delete column operations."""

    @pytest.mark.requirement("FR-016")
    def test_delete_column_requires_incompatible_flag(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test deleting a column requires allow_incompatible_changes=True."""
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="name",
                ),
            ],
            allow_incompatible_changes=False,
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            schema_manager.evolve_schema(test_table, evolution)

    @pytest.mark.requirement("FR-016")
    def test_delete_column_with_incompatible_flag_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test deleting a column succeeds with allow_incompatible_changes=True."""
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="name",
                ),
            ],
            allow_incompatible_changes=True,
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-016")
    def test_delete_nonexistent_column_raises(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test deleting a nonexistent column raises error."""
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="nonexistent",
                ),
            ],
            allow_incompatible_changes=True,
        )

        with pytest.raises(SchemaEvolutionError, match="does not exist"):
            schema_manager.evolve_schema(test_table, evolution)


# =============================================================================
# Update Documentation Tests (T027)
# =============================================================================


class TestSchemaManagerUpdateDoc:
    """Tests for _IcebergSchemaManager update documentation operations."""

    @pytest.mark.requirement("FR-016")
    def test_update_column_doc_succeeds(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test updating column documentation succeeds."""
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.UPDATE_DOC,
                    source_column="name",
                    new_doc="Full name of the customer",
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-016")
    def test_update_doc_for_nonexistent_column_raises(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test updating doc for nonexistent column raises error."""
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import SchemaChange, SchemaChangeType, SchemaEvolution

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.UPDATE_DOC,
                    source_column="nonexistent",
                    new_doc="New documentation",
                ),
            ],
        )

        with pytest.raises(SchemaEvolutionError, match="does not exist"):
            schema_manager.evolve_schema(test_table, evolution)


# =============================================================================
# Multiple Changes Tests (T027)
# =============================================================================


class TestSchemaManagerMultipleChanges:
    """Tests for _IcebergSchemaManager applying multiple changes atomically."""

    @pytest.mark.requirement("FR-014")
    def test_multiple_safe_changes_succeed(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test applying multiple safe changes in one evolution."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                # Add optional column
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="email",
                        field_type=FieldType.STRING,
                        required=False,
                    ),
                ),
                # Rename column
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="name",
                    new_name="full_name",
                ),
                # Update doc
                SchemaChange(
                    change_type=SchemaChangeType.UPDATE_DOC,
                    source_column="age",
                    new_doc="Customer age in years",
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None

    @pytest.mark.requirement("FR-014")
    def test_mixed_changes_with_incompatible_requires_flag(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test mixing safe and incompatible changes requires flag."""
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                # Safe: add optional column
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="email",
                        field_type=FieldType.STRING,
                        required=False,
                    ),
                ),
                # Incompatible: delete column
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="name",
                ),
            ],
            allow_incompatible_changes=False,
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            schema_manager.evolve_schema(test_table, evolution)

    @pytest.mark.requirement("FR-014")
    def test_all_changes_validated_before_any_applied(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test that all changes are validated before any are applied.

        If one change is invalid, none should be applied (atomic validation).
        """
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                # Valid: add column
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="email",
                        field_type=FieldType.STRING,
                        required=False,
                    ),
                ),
                # Invalid: rename nonexistent column
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="nonexistent",
                    new_name="new_name",
                ),
            ],
        )

        # Should fail validation before applying any changes
        with pytest.raises(SchemaEvolutionError, match="does not exist"):
            schema_manager.evolve_schema(test_table, evolution)


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestSchemaManagerEdgeCases:
    """Edge case tests for schema evolution operations."""

    @pytest.mark.requirement("FR-016")
    def test_empty_evolution_rejected_by_validation(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test that SchemaEvolution requires at least one change.

        The model validation enforces minimum 1 change to prevent no-op evolutions.
        """
        from pydantic import ValidationError

        from floe_iceberg.models import SchemaEvolution

        # SchemaEvolution requires at least 1 change
        with pytest.raises(ValidationError, match="at least 1 item"):
            SchemaEvolution(changes=[])

    @pytest.mark.requirement("FR-016")
    def test_add_column_with_doc(
        self,
        schema_manager: Any,
        test_table: Any,
    ) -> None:
        """Test adding a column with documentation."""
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
        )

        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=10,
                        name="notes",
                        field_type=FieldType.STRING,
                        required=False,
                        doc="Additional notes about the customer",
                    ),
                ),
            ],
        )

        result = schema_manager.evolve_schema(test_table, evolution)

        assert result is not None


__all__ = [
    "TestSchemaManagerAddColumn",
    "TestSchemaManagerRenameColumn",
    "TestSchemaManagerWidenType",
    "TestSchemaManagerMakeOptional",
    "TestSchemaManagerDeleteColumn",
    "TestSchemaManagerUpdateDoc",
    "TestSchemaManagerMultipleChanges",
    "TestSchemaManagerEdgeCases",
]
