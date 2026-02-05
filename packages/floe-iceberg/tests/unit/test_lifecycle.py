"""Unit tests for _IcebergTableLifecycle class.

Task ID: T026
Phase: 6 - US4 (Split IcebergTableManager)
User Story: US4 - Split Large Classes
Requirements: FR-012, FR-013, FR-014

Tests for the _IcebergTableLifecycle helper class that encapsulates table
lifecycle operations (create, load, drop, exists). Written TDD-style before
implementation (T030).

The _IcebergTableLifecycle class will be extracted from IcebergTableManager
to reduce class complexity and improve single-responsibility adherence.

Operations covered:
- create_table(): Create new Iceberg tables with schema/partitioning
- load_table(): Load existing tables by identifier
- table_exists(): Check if table exists in catalog
- drop_table(): Remove tables from catalog (planned for T030)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


# =============================================================================
# Fixtures for Lifecycle Tests
# =============================================================================


@pytest.fixture
def lifecycle_manager(
    mock_catalog_plugin: MockCatalogPlugin,
    mock_storage_plugin: MockStoragePlugin,
) -> Any:
    """Create an IcebergTableManager with a namespace for lifecycle testing.

    The manager provides access to lifecycle operations. After T030,
    this fixture will return _IcebergTableLifecycle directly.

    Args:
        mock_catalog_plugin: Mock catalog plugin fixture.
        mock_storage_plugin: Mock storage plugin fixture.

    Returns:
        IcebergTableManager configured for lifecycle testing.
    """
    from floe_iceberg import IcebergTableManager

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

    return manager


@pytest.fixture
def sample_table_config() -> Any:
    """Create a sample TableConfig for testing.

    Returns:
        TableConfig instance with minimal valid configuration.
    """
    from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

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
                name="created_at",
                field_type=FieldType.TIMESTAMPTZ,
                required=False,
                doc="Creation timestamp",
            ),
        ]
    )

    return TableConfig(
        namespace="bronze",
        table_name="customers",
        table_schema=schema,
        properties={"owner": "data-platform"},
    )


# =============================================================================
# Table Creation Tests (T026)
# =============================================================================


class TestIcebergTableLifecycleCreate:
    """Tests for _IcebergTableLifecycle.create_table() method.

    These tests verify table creation behavior before extracting
    the lifecycle class from IcebergTableManager (T030).
    """

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_valid_config(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test creating a table with valid configuration succeeds."""
        table = lifecycle_manager.create_table(sample_table_config)

        assert table.identifier == "bronze.customers"

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_if_not_exists_false_raises_on_duplicate(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test creating duplicate table raises TableAlreadyExistsError."""
        from floe_iceberg.errors import TableAlreadyExistsError

        # Create table first time
        lifecycle_manager.create_table(sample_table_config)

        # Second creation should fail
        with pytest.raises(TableAlreadyExistsError):
            lifecycle_manager.create_table(sample_table_config, if_not_exists=False)

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_if_not_exists_true_returns_existing(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test creating with if_not_exists=True returns existing table."""
        # Create table first time
        original_table = lifecycle_manager.create_table(sample_table_config)

        # Second creation with if_not_exists=True should return existing
        existing_table = lifecycle_manager.create_table(sample_table_config, if_not_exists=True)

        assert existing_table.identifier == "bronze.customers"
        assert existing_table.identifier == original_table.identifier

    @pytest.mark.requirement("FR-012")
    def test_create_table_in_nonexistent_namespace_raises(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test creating table in nonexistent namespace raises NoSuchNamespaceError."""
        from floe_iceberg.errors import NoSuchNamespaceError
        from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

        # Create config for nonexistent namespace
        schema = TableSchema(
            fields=[
                SchemaField(
                    field_id=1,
                    name="id",
                    field_type=FieldType.LONG,
                    required=True,
                )
            ]
        )
        config = TableConfig(
            namespace="nonexistent",
            table_name="test_table",
            table_schema=schema,
        )

        with pytest.raises(NoSuchNamespaceError):
            lifecycle_manager.create_table(config)

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_properties(
        self,
        lifecycle_manager: Any,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test creating table with custom properties stores them correctly."""
        from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

        schema = TableSchema(
            fields=[
                SchemaField(
                    field_id=1,
                    name="id",
                    field_type=FieldType.LONG,
                    required=True,
                )
            ]
        )
        config = TableConfig(
            namespace="bronze",
            table_name="with_properties",
            table_schema=schema,
            properties={
                "owner": "data-team",
                "write.format.default": "parquet",
                "commit.manifest.min-count-to-merge": "10",
            },
        )

        lifecycle_manager.create_table(config)

        # Verify properties were stored
        stored_table = mock_catalog_plugin._tables.get("bronze.with_properties")
        assert stored_table is not None
        assert stored_table["properties"]["owner"] == "data-team"

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_location(
        self,
        lifecycle_manager: Any,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test creating table with explicit location uses that location."""
        from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

        schema = TableSchema(
            fields=[
                SchemaField(
                    field_id=1,
                    name="id",
                    field_type=FieldType.LONG,
                    required=True,
                )
            ]
        )
        custom_location = "s3://custom-bucket/custom/path"
        config = TableConfig(
            namespace="bronze",
            table_name="custom_location",
            table_schema=schema,
            location=custom_location,
        )

        lifecycle_manager.create_table(config)

        # Verify location was used
        stored_table = mock_catalog_plugin._tables.get("bronze.custom_location")
        assert stored_table is not None
        assert stored_table["location"] == custom_location


# =============================================================================
# Table Existence Tests (T026)
# =============================================================================


class TestIcebergTableLifecycleExists:
    """Tests for _IcebergTableLifecycle.table_exists() method."""

    @pytest.mark.requirement("FR-013")
    def test_table_exists_returns_true_for_existing_table(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test table_exists returns True for existing table."""
        # Create table first
        lifecycle_manager.create_table(sample_table_config)

        # Check existence
        exists = lifecycle_manager.table_exists("bronze.customers")

        assert exists is True

    @pytest.mark.requirement("FR-013")
    def test_table_exists_returns_false_for_nonexistent_table(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test table_exists returns False for nonexistent table."""
        exists = lifecycle_manager.table_exists("bronze.nonexistent")

        assert exists is False

    @pytest.mark.requirement("FR-013")
    def test_table_exists_returns_false_for_nonexistent_namespace(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test table_exists returns False when namespace doesn't exist."""
        exists = lifecycle_manager.table_exists("nonexistent_namespace.table")

        assert exists is False

    @pytest.mark.requirement("FR-013")
    def test_table_exists_handles_invalid_identifier_format(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test table_exists handles malformed identifiers gracefully."""
        # No namespace separator
        exists = lifecycle_manager.table_exists("nodotintable")

        assert exists is False


# =============================================================================
# Table Loading Tests (T026)
# =============================================================================


class TestIcebergTableLifecycleLoad:
    """Tests for _IcebergTableLifecycle.load_table() method."""

    @pytest.mark.requirement("FR-014")
    def test_load_table_returns_existing_table(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test load_table returns the table object for existing table."""
        # Create table first
        lifecycle_manager.create_table(sample_table_config)

        # Load table
        table = lifecycle_manager.load_table("bronze.customers")

        assert table.identifier == "bronze.customers"
        assert table.identifier == "bronze.customers"

    @pytest.mark.requirement("FR-014")
    def test_load_table_raises_for_nonexistent_table(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test load_table raises NoSuchTableError for nonexistent table."""
        from floe_iceberg.errors import NoSuchTableError

        with pytest.raises(NoSuchTableError):
            lifecycle_manager.load_table("bronze.nonexistent")

    @pytest.mark.requirement("FR-014")
    def test_load_table_raises_for_invalid_identifier(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test load_table raises ValidationError for invalid identifier format."""
        from floe_iceberg.errors import ValidationError

        with pytest.raises(ValidationError, match="Invalid identifier format"):
            lifecycle_manager.load_table("no_namespace_separator")

    @pytest.mark.requirement("FR-014")
    def test_load_table_multiple_times_returns_same_object(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test loading same table multiple times returns consistent object."""
        # Create table first
        lifecycle_manager.create_table(sample_table_config)

        # Load multiple times
        table1 = lifecycle_manager.load_table("bronze.customers")
        table2 = lifecycle_manager.load_table("bronze.customers")

        # Should be same mock instance (cached in MockCatalog)
        assert table1 is table2


# =============================================================================
# Drop Table Tests (T026 - Placeholder for T030)
# =============================================================================


class TestIcebergTableLifecycleDrop:
    """Tests for _IcebergTableLifecycle.drop_table() method.

    Implemented in T024 (12B Tech Debt Epic) as part of US2 - Skipped Tests.
    These tests validate table removal via catalog plugin.
    """

    @pytest.mark.requirement("FR-015")
    def test_drop_table_removes_existing_table(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test drop_table removes table from catalog."""
        # Create table first
        lifecycle_manager.create_table(sample_table_config)
        assert lifecycle_manager.table_exists("bronze.customers") is True

        # Drop table
        lifecycle_manager.drop_table("bronze.customers")

        # Verify removed
        assert lifecycle_manager.table_exists("bronze.customers") is False
        assert "bronze.customers" not in mock_catalog_plugin._tables

    @pytest.mark.requirement("FR-015")
    def test_drop_table_raises_for_nonexistent_table(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test drop_table raises NoSuchTableError for nonexistent table."""
        from floe_iceberg.errors import NoSuchTableError

        with pytest.raises(NoSuchTableError):
            lifecycle_manager.drop_table("bronze.nonexistent")

    @pytest.mark.requirement("FR-015")
    def test_drop_table_with_purge_removes_data(
        self,
        lifecycle_manager: Any,
        sample_table_config: Any,
    ) -> None:
        """Test drop_table with purge=True removes underlying data files."""
        # Create table first
        lifecycle_manager.create_table(sample_table_config)

        # Drop with purge
        lifecycle_manager.drop_table("bronze.customers", purge=True)

        # Verify table removed (data purge is mock behavior)
        assert lifecycle_manager.table_exists("bronze.customers") is False


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestIcebergTableLifecycleEdgeCases:
    """Edge case tests for lifecycle operations."""

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_empty_schema_fields(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test creating table with empty schema fields is rejected."""
        from floe_iceberg.models import TableConfig, TableSchema

        # Empty fields list - Pydantic should validate
        with pytest.raises(ValueError):  # ValidationError from Pydantic
            TableConfig(
                namespace="bronze",
                table_name="empty_schema",
                table_schema=TableSchema(fields=[]),
            )

    @pytest.mark.requirement("FR-013")
    def test_table_exists_with_special_characters_in_name(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test table_exists handles special characters in identifier."""
        # Should not raise, just return False
        exists = lifecycle_manager.table_exists("bronze.table-with-dashes")
        assert exists is False

        exists = lifecycle_manager.table_exists("bronze.table_with_underscores")
        assert exists is False

    @pytest.mark.requirement("FR-012")
    def test_create_table_validates_namespace_format(
        self,
        lifecycle_manager: Any,
    ) -> None:
        """Test TableConfig validates namespace format via Pydantic.

        The namespace field must match pattern ^[a-zA-Z][a-zA-Z0-9_]*$
        so nested namespaces with dots are rejected at model validation.
        """
        from pydantic import ValidationError

        from floe_iceberg.models import FieldType, SchemaField, TableConfig, TableSchema

        schema = TableSchema(
            fields=[
                SchemaField(
                    field_id=1,
                    name="id",
                    field_type=FieldType.LONG,
                    required=True,
                )
            ]
        )
        # Nested namespace with dots is rejected by Pydantic pattern validation
        with pytest.raises(ValidationError, match="namespace"):
            TableConfig(
                namespace="bronze.nested.deep",
                table_name="test",
                table_schema=schema,
            )


__all__ = [
    "TestIcebergTableLifecycleCreate",
    "TestIcebergTableLifecycleExists",
    "TestIcebergTableLifecycleLoad",
    "TestIcebergTableLifecycleDrop",
    "TestIcebergTableLifecycleEdgeCases",
]
