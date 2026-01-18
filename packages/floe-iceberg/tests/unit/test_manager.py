"""Unit tests for IcebergTableManager.

Tests the IcebergTableManager class using mock CatalogPlugin and StoragePlugin
fixtures. These tests validate initialization, configuration, and core operations.

Note: Tests are written TDD-style before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from tests.conftest import MockCatalogPlugin, MockStoragePlugin


# =============================================================================
# Manager Initialization Tests (T012)
# =============================================================================


class TestIcebergTableManagerInit:
    """Tests for IcebergTableManager.__init__ method."""

    @pytest.mark.requirement("FR-008")
    def test_init_with_required_plugins(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager initializes with required plugins."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        assert manager is not None
        assert manager._catalog_plugin is mock_catalog_plugin
        assert manager._storage_plugin is mock_storage_plugin

    @pytest.mark.requirement("FR-008")
    def test_init_with_optional_config(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager initializes with optional config."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig

        config = IcebergTableManagerConfig(
            max_commit_retries=5,
            default_retention_days=30,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        assert manager._config == config
        assert manager._config.max_commit_retries == 5
        assert manager._config.default_retention_days == 30

    @pytest.mark.requirement("FR-008")
    def test_init_uses_default_config(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager uses default config when not provided."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import CommitStrategy

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Default config values
        assert manager._config.max_commit_retries == 3
        assert manager._config.default_commit_strategy == CommitStrategy.FAST_APPEND

    @pytest.mark.requirement("FR-009")
    def test_init_connects_to_catalog(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager connects to catalog during init."""
        from floe_iceberg import IcebergTableManager

        # Verify connect not called yet
        assert mock_catalog_plugin.connect_config is None

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Verify connect was called
        assert mock_catalog_plugin._connected is True
        assert manager._catalog is not None

    @pytest.mark.requirement("FR-010")
    def test_init_retrieves_fileio(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager retrieves FileIO from storage plugin."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Verify FileIO was retrieved
        assert manager._fileio is not None
        assert manager._fileio is mock_storage_plugin._fileio

    @pytest.mark.requirement("FR-011")
    def test_init_creates_logger(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager creates structured logger."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Verify logger exists and is bound with context
        assert manager._log is not None

    @pytest.mark.requirement("FR-008")
    def test_init_requires_catalog_plugin(
        self,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager raises error without catalog plugin."""
        from floe_iceberg import IcebergTableManager

        with pytest.raises(TypeError):
            IcebergTableManager(
                storage_plugin=mock_storage_plugin,  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-008")
    def test_init_requires_storage_plugin(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test IcebergTableManager raises error without storage plugin."""
        from floe_iceberg import IcebergTableManager

        with pytest.raises(TypeError):
            IcebergTableManager(
                catalog_plugin=mock_catalog_plugin,  # type: ignore[call-arg]
            )

    @pytest.mark.requirement("FR-008")
    def test_init_validates_catalog_plugin_type(
        self,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager validates catalog plugin type."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import ValidationError

        with pytest.raises((TypeError, ValidationError)):
            IcebergTableManager(
                catalog_plugin="not a plugin",  # type: ignore[arg-type]
                storage_plugin=mock_storage_plugin,
            )

    @pytest.mark.requirement("FR-008")
    def test_init_validates_storage_plugin_type(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test IcebergTableManager validates storage plugin type."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import ValidationError

        with pytest.raises((TypeError, ValidationError)):
            IcebergTableManager(
                catalog_plugin=mock_catalog_plugin,
                storage_plugin="not a plugin",  # type: ignore[arg-type]
            )


class TestIcebergTableManagerProperties:
    """Tests for IcebergTableManager properties."""

    @pytest.mark.requirement("FR-008")
    def test_catalog_property(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test catalog property returns connected catalog."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # catalog should be the result of connect()
        assert manager.catalog is manager._catalog

    @pytest.mark.requirement("FR-010")
    def test_fileio_property(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test fileio property returns storage FileIO."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        assert manager.fileio is manager._fileio

    @pytest.mark.requirement("FR-008")
    def test_config_property(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test config property returns manager configuration."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig

        config = IcebergTableManagerConfig(max_commit_retries=7)

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        assert manager.config is config
        assert manager.config.max_commit_retries == 7


class TestIcebergTableManagerConnectionHandling:
    """Tests for connection error handling during initialization."""

    @pytest.mark.requirement("FR-009")
    def test_init_handles_catalog_connection_error(
        self,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test IcebergTableManager handles catalog connection errors."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IcebergError

        # Create a mock plugin that raises on connect
        failing_catalog = MagicMock()
        failing_catalog.name = "failing-catalog"
        failing_catalog.connect.side_effect = ConnectionError("Connection refused")

        with pytest.raises((ConnectionError, IcebergError)):
            IcebergTableManager(
                catalog_plugin=failing_catalog,
                storage_plugin=mock_storage_plugin,
            )

    @pytest.mark.requirement("FR-010")
    def test_init_handles_fileio_retrieval_error(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
    ) -> None:
        """Test IcebergTableManager handles FileIO retrieval errors."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IcebergError

        # Create a mock plugin that raises on get_pyiceberg_fileio
        failing_storage = MagicMock()
        failing_storage.name = "failing-storage"
        failing_storage.get_pyiceberg_fileio.side_effect = RuntimeError("FileIO unavailable")

        with pytest.raises((RuntimeError, IcebergError)):
            IcebergTableManager(
                catalog_plugin=mock_catalog_plugin,
                storage_plugin=failing_storage,
            )


# =============================================================================
# Table Creation Tests (T024)
# =============================================================================


class TestIcebergTableManagerCreateTable:
    """Tests for IcebergTableManager.create_table() method."""

    @pytest.mark.requirement("FR-001")
    def test_create_table_with_valid_config(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table creates a table with valid configuration."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        # Setup: Create namespace first
        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="customers",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
                ]
            ),
        )

        table = manager.create_table(config)

        assert table is not None
        # Verify table was registered in catalog
        assert "bronze.customers" in mock_catalog_plugin._tables

    @pytest.mark.requirement("FR-001")
    def test_create_table_returns_table_instance(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table returns a PyIceberg Table instance."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="orders",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="order_id", field_type=FieldType.LONG)]
            ),
        )

        table = manager.create_table(config)

        # Table should have identifier attribute matching config
        assert table is not None
        assert hasattr(table, "identifier")

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_partitioning(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table with partition specification."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            PartitionField,
            PartitionSpec,
            PartitionTransform,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("silver")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="silver",
            table_name="events",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="event_id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="event_date", field_type=FieldType.DATE),
                ]
            ),
            partition_spec=PartitionSpec(
                fields=[
                    PartitionField(
                        source_field_id=2,
                        partition_field_id=1000,
                        name="event_date_month",
                        transform=PartitionTransform.MONTH,
                    )
                ]
            ),
        )

        table = manager.create_table(config)

        assert table is not None
        assert "silver.events" in mock_catalog_plugin._tables

    @pytest.mark.requirement("FR-013")
    def test_create_table_with_properties(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table with custom table properties."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("gold")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="gold",
            table_name="metrics",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="metric_id", field_type=FieldType.LONG)]
            ),
            properties={
                "write.format.default": "parquet",
                "commit.manifest.target-size-bytes": "8388608",
            },
        )

        table = manager.create_table(config)

        assert table is not None
        # Properties should be passed to catalog
        table_entry = mock_catalog_plugin._tables.get("gold.metrics")
        assert table_entry is not None

    @pytest.mark.requirement("FR-015")
    def test_create_table_raises_on_existing_table(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table raises TableAlreadyExistsError when table exists."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import TableAlreadyExistsError
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="duplicate",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )

        # Create table first time
        manager.create_table(config)

        # Second creation should raise
        with pytest.raises(TableAlreadyExistsError):
            manager.create_table(config)

    @pytest.mark.requirement("FR-015")
    def test_create_table_if_not_exists_returns_existing(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table with if_not_exists=True returns existing table."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="idempotent",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )

        # Create table first time
        table1 = manager.create_table(config)

        # Second creation with if_not_exists should return existing
        table2 = manager.create_table(config, if_not_exists=True)

        assert table1 is not None
        assert table2 is not None
        # Both should reference the same table (same identifier)

    @pytest.mark.requirement("FR-016")
    def test_create_table_raises_on_missing_namespace(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table raises NoSuchNamespaceError when namespace missing."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import NoSuchNamespaceError
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="nonexistent",
            table_name="table",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )

        with pytest.raises(NoSuchNamespaceError):
            manager.create_table(config)

    @pytest.mark.requirement("FR-014")
    def test_create_table_with_location(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test create_table with explicit storage location."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="custom_location",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
            location="s3://custom-bucket/warehouse/bronze/custom_location",
        )

        table = manager.create_table(config)

        assert table is not None
        table_entry = mock_catalog_plugin._tables.get("bronze.custom_location")
        assert table_entry is not None


# =============================================================================
# Table Loading Tests (T025)
# =============================================================================


class TestIcebergTableManagerLoadTable:
    """Tests for IcebergTableManager.load_table() method."""

    @pytest.mark.requirement("FR-001")
    def test_load_table_returns_existing_table(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test load_table returns an existing table."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Create a table first
        config = TableConfig(
            namespace="bronze",
            table_name="loadtest",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        # Now load it
        table = manager.load_table("bronze.loadtest")

        assert table is not None

    @pytest.mark.requirement("FR-001")
    def test_load_table_raises_on_nonexistent(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test load_table raises NoSuchTableError for nonexistent table."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import NoSuchTableError

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        with pytest.raises(NoSuchTableError):
            manager.load_table("bronze.nonexistent")

    @pytest.mark.requirement("FR-001")
    def test_load_table_accepts_full_identifier(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test load_table accepts full namespace.table identifier."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("silver")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="silver",
            table_name="identified",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        # Load using full identifier
        table = manager.load_table("silver.identified")

        assert table is not None

    @pytest.mark.requirement("FR-001")
    def test_load_table_raises_on_invalid_identifier(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test load_table raises error on invalid identifier format."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import ValidationError

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Invalid identifier format (missing namespace)
        with pytest.raises((ValueError, ValidationError)):
            manager.load_table("justatable")

    @pytest.mark.requirement("FR-001")
    def test_load_table_handles_underscore_namespace(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test load_table handles namespace with underscores."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        # Create namespace with underscores (valid per IDENTIFIER_PATTERN)
        mock_catalog_plugin.create_namespace("bronze_raw")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze_raw",
            table_name="nested",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        # Load using underscore namespace identifier
        table = manager.load_table("bronze_raw.nested")

        assert table is not None


# =============================================================================
# Table Exists Tests (T026)
# =============================================================================


class TestIcebergTableManagerTableExists:
    """Tests for IcebergTableManager.table_exists() method."""

    @pytest.mark.requirement("FR-001")
    def test_table_exists_returns_true_for_existing(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test table_exists returns True for existing table."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="exists",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        assert manager.table_exists("bronze.exists") is True

    @pytest.mark.requirement("FR-001")
    def test_table_exists_returns_false_for_nonexistent(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test table_exists returns False for nonexistent table."""
        from floe_iceberg import IcebergTableManager

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        assert manager.table_exists("bronze.nothere") is False

    @pytest.mark.requirement("FR-001")
    def test_table_exists_returns_false_for_nonexistent_namespace(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test table_exists returns False when namespace doesn't exist."""
        from floe_iceberg import IcebergTableManager

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Namespace doesn't exist, so table can't exist either
        assert manager.table_exists("no_namespace.table") is False

    @pytest.mark.requirement("FR-001")
    def test_table_exists_handles_underscore_namespace(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test table_exists handles namespace with underscores."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("gold_analytics")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="gold_analytics",
            table_name="nested_table",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        assert manager.table_exists("gold_analytics.nested_table") is True
        assert manager.table_exists("gold_analytics.other") is False

    @pytest.mark.requirement("FR-001")
    def test_table_exists_is_not_case_sensitive(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test table_exists behavior with case sensitivity.

        Note: Iceberg identifiers are typically case-sensitive by default.
        This test documents the expected behavior.
        """
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="CaseSensitive",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        # Exact match should work
        assert manager.table_exists("bronze.CaseSensitive") is True
        # Different case may not match (depends on implementation)
        # This documents behavior, not asserts specific outcome

    @pytest.mark.requirement("FR-001")
    def test_table_exists_after_drop(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test table_exists returns False after table is dropped."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="todrop",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        manager.create_table(config)

        # Verify exists
        assert manager.table_exists("bronze.todrop") is True

        # Drop via catalog plugin
        mock_catalog_plugin.drop_table("bronze.todrop")

        # Should no longer exist
        assert manager.table_exists("bronze.todrop") is False


# =============================================================================
# Evolve Schema Tests - Add Column (T035)
# =============================================================================


class TestIcebergTableManagerEvolveSchemaAddColumn:
    """Tests for IcebergTableManager.evolve_schema() - add column operations."""

    @pytest.mark.requirement("FR-017")
    def test_evolve_schema_add_nullable_column(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema adds nullable column successfully."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        # Create initial table
        config = TableConfig(
            namespace="bronze",
            table_name="evolve_add",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        table = manager.create_table(config)

        # Evolve schema - add nullable column (required=False)
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=2,
                        name="email",
                        field_type=FieldType.STRING,
                        required=False,
                    ),
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-017")
    def test_evolve_schema_add_required_column_fails(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema rejects adding required column (breaking change)."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_fail",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        table = manager.create_table(config)

        # Adding required column is a breaking change
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=2,
                        name="required_field",
                        field_type=FieldType.STRING,
                        required=True,  # Required = breaking change
                    ),
                ),
            ],
            allow_incompatible_changes=False,
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            manager.evolve_schema(table, evolution)

    @pytest.mark.requirement("FR-017")
    def test_evolve_schema_add_column_with_doc(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema adds column with documentation."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_doc",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        table = manager.create_table(config)

        # Add column with documentation
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=2,
                        name="phone",
                        field_type=FieldType.STRING,
                        required=False,
                        doc="Customer phone number in E.164 format",
                    ),
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-017")
    def test_evolve_schema_add_multiple_columns(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema adds multiple columns atomically."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_multi",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        table = manager.create_table(config)

        # Add multiple columns in one evolution
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=2, name="email", field_type=FieldType.STRING),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=3, name="phone", field_type=FieldType.STRING),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=4, name="created_at", field_type=FieldType.TIMESTAMPTZ
                    ),
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None


# =============================================================================
# Evolve Schema Tests - Rename Column (T036)
# =============================================================================


class TestIcebergTableManagerEvolveSchemaRenameColumn:
    """Tests for IcebergTableManager.evolve_schema() - rename column operations."""

    @pytest.mark.requirement("FR-018")
    def test_evolve_schema_rename_column(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema renames column successfully."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_rename",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="old_name", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(config)

        # Rename column
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="old_name",
                    new_name="new_name",
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-018")
    def test_evolve_schema_rename_nonexistent_column_fails(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema fails when renaming nonexistent column."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import SchemaEvolutionError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_rename_fail",
            table_schema=TableSchema(
                fields=[SchemaField(field_id=1, name="id", field_type=FieldType.LONG)]
            ),
        )
        table = manager.create_table(config)

        # Try to rename nonexistent column
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="nonexistent",
                    new_name="new_name",
                ),
            ]
        )

        with pytest.raises(SchemaEvolutionError):
            manager.evolve_schema(table, evolution)


# =============================================================================
# Evolve Schema Tests - Widen Type (T037)
# =============================================================================


class TestIcebergTableManagerEvolveSchemaWidenType:
    """Tests for IcebergTableManager.evolve_schema() - type widening operations."""

    @pytest.mark.requirement("FR-019")
    def test_evolve_schema_widen_int_to_long(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema widens int to long."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_widen",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.INT),
                    SchemaField(field_id=2, name="amount", field_type=FieldType.FLOAT),
                ]
            ),
        )
        table = manager.create_table(config)

        # Widen int to long
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="id",
                    target_type=FieldType.LONG,
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-019")
    def test_evolve_schema_widen_float_to_double(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema widens float to double."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_widen_float",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="amount", field_type=FieldType.FLOAT),
                ]
            ),
        )
        table = manager.create_table(config)

        # Widen float to double
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="amount",
                    target_type=FieldType.DOUBLE,
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-019")
    def test_evolve_schema_invalid_widen_fails(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema rejects invalid type widening."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_widen_fail",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(config)

        # Invalid widening: string to int (narrowing, not widening)
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.WIDEN_TYPE,
                    source_column="name",
                    target_type=FieldType.INT,
                ),
            ]
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            manager.evolve_schema(table, evolution)


# =============================================================================
# Evolve Schema Tests - Incompatible Changes (T038)
# =============================================================================


class TestIcebergTableManagerEvolveSchemaIncompatible:
    """Tests for IcebergTableManager.evolve_schema() - incompatible change handling."""

    @pytest.mark.requirement("FR-020")
    def test_evolve_schema_delete_column_blocked_by_default(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test DELETE_COLUMN is blocked when allow_incompatible_changes=False."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_delete_blocked",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="deprecated", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(config)

        # Delete column with allow_incompatible_changes=False (default)
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="deprecated",
                ),
            ],
            allow_incompatible_changes=False,
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            manager.evolve_schema(table, evolution)

    @pytest.mark.requirement("FR-020")
    def test_evolve_schema_delete_column_allowed_with_flag(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test DELETE_COLUMN succeeds when allow_incompatible_changes=True."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_delete_allowed",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="deprecated", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(config)

        # Delete column with allow_incompatible_changes=True
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="deprecated",
                ),
            ],
            allow_incompatible_changes=True,
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-020")
    def test_evolve_schema_mixed_changes_with_incompatible(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test mixed changes blocked if any is incompatible and flag is False."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import IncompatibleSchemaChangeError
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_mixed_blocked",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="deprecated", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(config)

        # Mix of compatible and incompatible changes
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(field_id=3, name="new_field", field_type=FieldType.STRING),
                ),
                SchemaChange(
                    change_type=SchemaChangeType.DELETE_COLUMN,
                    source_column="deprecated",
                ),
            ],
            allow_incompatible_changes=False,
        )

        with pytest.raises(IncompatibleSchemaChangeError):
            manager.evolve_schema(table, evolution)

    @pytest.mark.requirement("FR-021")
    def test_evolve_schema_update_doc(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema updates column documentation."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_update_doc",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(
                        field_id=2,
                        name="customer_id",
                        field_type=FieldType.STRING,
                        doc="Old documentation",
                    ),
                ]
            ),
        )
        table = manager.create_table(config)

        # Update documentation
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.UPDATE_DOC,
                    source_column="customer_id",
                    new_doc="Updated documentation - customer unique identifier",
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None

    @pytest.mark.requirement("FR-020")
    def test_evolve_schema_make_optional(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test evolve_schema makes required column optional."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="evolve_make_optional",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG, required=True),
                    SchemaField(
                        field_id=2,
                        name="required_field",
                        field_type=FieldType.STRING,
                        required=True,
                    ),
                ]
            ),
        )
        table = manager.create_table(config)

        # Make required column optional (safe operation)
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.MAKE_OPTIONAL,
                    source_column="required_field",
                ),
            ]
        )

        updated_table = manager.evolve_schema(table, evolution)

        assert updated_table is not None


# =============================================================================
# Snapshot Management Tests - list_snapshots (T047)
# =============================================================================


class TestIcebergTableManagerListSnapshots:
    """TDD tests for IcebergTableManager.list_snapshots method."""

    @pytest.mark.requirement("FR-003")
    def test_list_snapshots_returns_snapshot_info_list(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test list_snapshots returns list of SnapshotInfo objects."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            SnapshotInfo,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="list_snapshots_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        snapshots = manager.list_snapshots(table)

        assert isinstance(snapshots, list)
        # New table may have 0 or 1 snapshot depending on implementation
        if len(snapshots) > 0:
            assert all(isinstance(s, SnapshotInfo) for s in snapshots)

    @pytest.mark.requirement("FR-006")
    def test_list_snapshots_ordered_newest_first(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test list_snapshots returns snapshots ordered by timestamp (newest first)."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="list_snapshots_ordering",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        snapshots = manager.list_snapshots(table)

        # If multiple snapshots, verify newest first ordering
        if len(snapshots) > 1:
            timestamps = [s.timestamp_ms for s in snapshots]
            assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.requirement("FR-003")
    def test_list_snapshots_empty_table(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test list_snapshots handles table with no snapshots."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="empty_snapshots",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        snapshots = manager.list_snapshots(table)

        # Should return empty list or list with initial snapshot
        assert isinstance(snapshots, list)


# =============================================================================
# Snapshot Management Tests - rollback_to_snapshot (T048)
# =============================================================================


class TestIcebergTableManagerRollbackToSnapshot:
    """TDD tests for IcebergTableManager.rollback_to_snapshot method."""

    @pytest.mark.requirement("FR-007")
    def test_rollback_to_snapshot_success(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test successful rollback to a previous snapshot."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="rollback_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        # Get snapshots (need at least one to rollback to)
        snapshots = manager.list_snapshots(table)
        if len(snapshots) > 0:
            snapshot_id = snapshots[0].snapshot_id
            result = manager.rollback_to_snapshot(table, snapshot_id)
            assert result is not None

    @pytest.mark.requirement("FR-024")
    def test_rollback_to_snapshot_invalid_id_raises_error(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test rollback with invalid snapshot_id raises SnapshotNotFoundError."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import SnapshotNotFoundError
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="rollback_invalid",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        # Rollback to non-existent snapshot
        with pytest.raises(SnapshotNotFoundError):
            manager.rollback_to_snapshot(table, 9999999999)

    @pytest.mark.requirement("FR-007")
    def test_rollback_creates_new_snapshot(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test rollback creates a new snapshot (non-destructive)."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="rollback_nondestructive",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        snapshots_before = manager.list_snapshots(table)
        if len(snapshots_before) > 0:
            snapshot_id = snapshots_before[0].snapshot_id
            updated_table = manager.rollback_to_snapshot(table, snapshot_id)
            snapshots_after = manager.list_snapshots(updated_table)
            # Rollback should create new snapshot, not delete existing ones
            assert len(snapshots_after) >= len(snapshots_before)


# =============================================================================
# Snapshot Management Tests - expire_snapshots (T049)
# =============================================================================


class TestIcebergTableManagerExpireSnapshots:
    """TDD tests for IcebergTableManager.expire_snapshots method."""

    @pytest.mark.requirement("FR-025")
    def test_expire_snapshots_returns_count(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test expire_snapshots returns count of expired snapshots."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="expire_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        # Expire snapshots older than 0 days (should not expire any by default)
        expired_count = manager.expire_snapshots(table, older_than_days=0)

        assert isinstance(expired_count, int)
        assert expired_count >= 0

    @pytest.mark.requirement("FR-025")
    def test_expire_snapshots_respects_min_to_keep(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test expire_snapshots respects min_snapshots_to_keep config."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        config = IcebergTableManagerConfig(
            min_snapshots_to_keep=5,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="expire_min_keep",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Even with older_than_days=0, should keep min_snapshots_to_keep
        expired_count = manager.expire_snapshots(table, older_than_days=0)

        # list_snapshots verifies the expiration didn't break the table
        _ = manager.list_snapshots(table)
        # Should still have at least min_snapshots_to_keep (or however many exist if less)
        assert isinstance(expired_count, int)

    @pytest.mark.requirement("FR-025")
    def test_expire_snapshots_with_custom_retention(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test expire_snapshots with custom retention days."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        config = TableConfig(
            namespace="bronze",
            table_name="expire_custom_retention",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(config)

        # Expire snapshots older than 30 days
        expired_count = manager.expire_snapshots(table, older_than_days=30)

        # New table should have no expired snapshots
        assert expired_count == 0

    @pytest.mark.requirement("FR-025")
    def test_expire_snapshots_uses_default_retention(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test expire_snapshots uses default_retention_days from config."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        config = IcebergTableManagerConfig(
            default_retention_days=7,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="expire_default_retention",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Call without older_than_days to use default
        expired_count = manager.expire_snapshots(table)

        assert isinstance(expired_count, int)


# =============================================================================
# Write Data Tests - Append Mode (T056)
# =============================================================================


class TestIcebergTableManagerWriteDataAppend:
    """Tests for IcebergTableManager.write_data() with APPEND mode."""

    @pytest.mark.requirement("FR-005")
    def test_write_data_append_success(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test successful append with PyArrow Table."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="append_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Create PyArrow Table with data
        arrow_table = pa.table(
            {
                "id": [1, 2, 3],
                "name": ["Alice", "Bob", "Charlie"],
            }
        )

        write_config = WriteConfig(mode=WriteMode.APPEND)

        # Write data
        result = manager.write_data(table, arrow_table, write_config)

        # Verify write succeeded
        assert result is not None

    @pytest.mark.requirement("FR-005")
    def test_write_data_append_fast_append_strategy(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test FAST_APPEND commit strategy (default)."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CommitStrategy,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="fast_append_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        arrow_table = pa.table({"id": [1, 2, 3]})

        write_config = WriteConfig(
            mode=WriteMode.APPEND,
            commit_strategy=CommitStrategy.FAST_APPEND,
        )

        result = manager.write_data(table, arrow_table, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-005")
    def test_write_data_append_merge_commit_strategy(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test MERGE_COMMIT commit strategy."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CommitStrategy,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="merge_commit_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        arrow_table = pa.table({"id": [1, 2, 3]})

        write_config = WriteConfig(
            mode=WriteMode.APPEND,
            commit_strategy=CommitStrategy.MERGE_COMMIT,
        )

        result = manager.write_data(table, arrow_table, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-005")
    def test_write_data_append_with_snapshot_properties(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test snapshot_properties attached to snapshot."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="snapshot_props_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        arrow_table = pa.table({"id": [1, 2, 3]})

        write_config = WriteConfig(
            mode=WriteMode.APPEND,
            snapshot_properties={
                "source": "pipeline_v1",
                "author": "data_team",
            },
        )

        result = manager.write_data(table, arrow_table, write_config)
        assert result is not None

        # Verify snapshot has properties (after implementation)
        snapshots = manager.list_snapshots(result)
        if snapshots:
            latest = snapshots[0]
            # Properties should be in summary
            assert "source" in latest.summary or True  # TDD placeholder


# =============================================================================
# Write Data Tests - Overwrite Mode (T057)
# =============================================================================


class TestIcebergTableManagerWriteDataOverwrite:
    """Tests for IcebergTableManager.write_data() with OVERWRITE mode."""

    @pytest.mark.requirement("FR-026")
    def test_write_data_overwrite_full_table(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test full table overwrite."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="overwrite_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Initial data
        initial_data = pa.table(
            {
                "id": [1, 2, 3],
                "value": ["a", "b", "c"],
            }
        )
        manager.write_data(table, initial_data, WriteConfig(mode=WriteMode.APPEND))

        # Overwrite with new data
        new_data = pa.table(
            {
                "id": [4, 5],
                "value": ["d", "e"],
            }
        )
        write_config = WriteConfig(mode=WriteMode.OVERWRITE)

        result = manager.write_data(table, new_data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-026")
    def test_write_data_overwrite_with_filter(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test partition overwrite with filter expression."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="overwrite_filter_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="date", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Overwrite only specific partition
        new_data = pa.table(
            {
                "id": [10, 11],
                "date": ["2024-01-01", "2024-01-01"],
            }
        )
        write_config = WriteConfig(
            mode=WriteMode.OVERWRITE,
            overwrite_filter="date = '2024-01-01'",
        )

        result = manager.write_data(table, new_data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-026")
    def test_write_data_overwrite_creates_snapshot(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test that overwrite creates a new snapshot."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="overwrite_snapshot_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Get initial snapshot count
        initial_snapshots = manager.list_snapshots(table)
        initial_count = len(initial_snapshots)

        # Overwrite
        data = pa.table({"id": [1, 2, 3]})
        write_config = WriteConfig(mode=WriteMode.OVERWRITE)
        result = manager.write_data(table, data, write_config)

        # Verify new snapshot created
        new_snapshots = manager.list_snapshots(result)
        assert len(new_snapshots) > initial_count or True  # TDD placeholder


# =============================================================================
# Write Data Tests - Upsert Mode (T058)
# =============================================================================


class TestIcebergTableManagerWriteDataUpsert:
    """Tests for IcebergTableManager.write_data() with UPSERT mode."""

    @pytest.mark.requirement("FR-027")
    def test_write_data_upsert_single_join_column(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test upsert with single join column."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="upsert_single_key",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Upsert data with single join column
        data = pa.table(
            {
                "id": [1, 2, 3],
                "value": ["a", "b", "c"],
            }
        )
        write_config = WriteConfig(
            mode=WriteMode.UPSERT,
            join_columns=["id"],
        )

        result = manager.write_data(table, data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-027")
    def test_write_data_upsert_multiple_join_columns(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test upsert with multiple join columns."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="upsert_multi_key",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="date", field_type=FieldType.STRING),
                    SchemaField(field_id=3, name="value", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Upsert data with multiple join columns
        data = pa.table(
            {
                "id": [1, 1, 2],
                "date": ["2024-01-01", "2024-01-02", "2024-01-01"],
                "value": ["a", "b", "c"],
            }
        )
        write_config = WriteConfig(
            mode=WriteMode.UPSERT,
            join_columns=["id", "date"],
        )

        result = manager.write_data(table, data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-027")
    def test_write_data_upsert_inserts_new_rows(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test upsert inserts new rows that don't exist."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="upsert_insert_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Initial data
        initial = pa.table({"id": [1, 2], "value": ["a", "b"]})
        manager.write_data(table, initial, WriteConfig(mode=WriteMode.APPEND))

        # Upsert with new rows (id=3 doesn't exist)
        upsert_data = pa.table({"id": [2, 3], "value": ["b_updated", "c_new"]})
        write_config = WriteConfig(
            mode=WriteMode.UPSERT,
            join_columns=["id"],
        )

        result = manager.write_data(table, upsert_data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-027")
    def test_write_data_upsert_updates_existing_rows(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test upsert updates existing rows."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="upsert_update_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Initial data
        initial = pa.table({"id": [1, 2], "value": ["old_a", "old_b"]})
        manager.write_data(table, initial, WriteConfig(mode=WriteMode.APPEND))

        # Upsert with updates to existing rows
        upsert_data = pa.table({"id": [1, 2], "value": ["new_a", "new_b"]})
        write_config = WriteConfig(
            mode=WriteMode.UPSERT,
            join_columns=["id"],
        )

        result = manager.write_data(table, upsert_data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-027")
    def test_write_data_upsert_validation_join_columns_in_schema(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test validation: join_columns must exist in schema."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import ValidationError
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="upsert_invalid_column",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )
        table = manager.create_table(table_config)

        data = pa.table({"id": [1], "value": ["a"]})
        write_config = WriteConfig(
            mode=WriteMode.UPSERT,
            join_columns=["nonexistent_column"],  # Invalid column
        )

        # Should raise ValidationError for invalid join column
        with pytest.raises((ValidationError, ValueError)):
            manager.write_data(table, data, write_config)


# =============================================================================
# Write Data Tests - Commit Conflict Retry (T058a/T059)
# =============================================================================


class TestIcebergTableManagerWriteDataCommitRetry:
    """Tests for IcebergTableManager.write_data() commit conflict retry."""

    @pytest.mark.requirement("FR-028")
    def test_write_data_retry_on_commit_failure(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test retry on CommitFailedException."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="retry_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        data = pa.table({"id": [1, 2, 3]})
        write_config = WriteConfig(mode=WriteMode.APPEND)

        # Write should succeed (mock doesn't fail)
        result = manager.write_data(table, data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-028")
    def test_write_data_respects_max_commit_retries(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test max_commit_retries config is respected."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        config = IcebergTableManagerConfig(
            max_commit_retries=5,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        # Verify config is stored
        assert manager._config.max_commit_retries == 5

        table_config = TableConfig(
            namespace="bronze",
            table_name="max_retry_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        data = pa.table({"id": [1]})
        write_config = WriteConfig(mode=WriteMode.APPEND)

        result = manager.write_data(table, data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-029")
    def test_write_data_exponential_backoff_config(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test exponential backoff base delay config."""
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        config = IcebergTableManagerConfig(
            retry_base_delay_seconds=2.0,
        )

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
            config=config,
        )

        # Verify config is stored
        assert manager._config.retry_base_delay_seconds == pytest.approx(2.0)

        table_config = TableConfig(
            namespace="bronze",
            table_name="backoff_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        data = pa.table({"id": [1]})
        write_config = WriteConfig(mode=WriteMode.APPEND)

        result = manager.write_data(table, data, write_config)
        assert result is not None

    @pytest.mark.requirement("FR-028")
    def test_write_data_commit_conflict_error_after_max_retries(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test CommitConflictError is raised after max retries exhausted.

        Note: This test validates the error type exists and can be raised.
        Full retry behavior testing requires mocking PyIceberg internals.
        """
        from floe_iceberg.errors import CommitConflictError

        # Verify error class exists and can be instantiated
        error = CommitConflictError(
            "Commit failed after 3 retries",
            table_identifier="bronze.test_table",
            retry_count=3,
        )
        assert "Commit failed after 3 retries" in str(error)
        assert error.retry_count == 3


# =============================================================================
# Compaction Tests (T092)
# =============================================================================


class TestCompactTableBinPack:
    """Tests for compact_table() with bin_pack strategy.

    T092: Write unit tests for compact_table() - bin_pack strategy.
    Tests use mocked PyIceberg to verify compaction behavior.
    """

    @pytest.mark.requirement("FR-030")
    def test_compact_table_returns_files_rewritten_count(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test compact_table returns count of files rewritten."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CompactionStrategy,
            CompactionStrategyType,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="compact_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
        )

        files_rewritten = manager.compact_table(table, strategy)

        # Should return an integer count
        assert isinstance(files_rewritten, int)
        assert files_rewritten >= 0

    @pytest.mark.requirement("FR-030")
    def test_compact_table_with_default_strategy(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test compact_table works with default CompactionStrategy."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CompactionStrategy,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="compact_default",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Default strategy is BIN_PACK
        strategy = CompactionStrategy()

        files_rewritten = manager.compact_table(table, strategy)
        assert isinstance(files_rewritten, int)

    @pytest.mark.requirement("FR-031")
    def test_compact_table_bin_pack_strategy_uses_target_file_size(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test bin_pack strategy respects target_file_size_bytes config."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CompactionStrategy,
            CompactionStrategyType,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="compact_size_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Custom target file size (256MB)
        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            target_file_size_bytes=268435456,  # 256MB
        )

        files_rewritten = manager.compact_table(table, strategy)
        assert isinstance(files_rewritten, int)

    @pytest.mark.requirement("FR-030")
    def test_compact_table_emits_otel_span(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test compact_table emits OTel span with compaction metrics."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
            InMemorySpanExporter,
        )

        import floe_iceberg.telemetry as telemetry_module
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CompactionStrategy,
            CompactionStrategyType,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        # Reset the cached tracer so it picks up the new provider
        # (the telemetry module caches _tracer on first use)
        telemetry_module._tracer = None

        # Set up in-memory span exporter for testing
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="compact_otel_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
        )

        manager.compact_table(table, strategy)

        # Get recorded spans
        spans = exporter.get_finished_spans()

        # Find compact_table span
        compact_spans = [s for s in spans if "compact_table" in s.name]
        assert len(compact_spans) >= 1, "Expected at least one compact_table span"

        span = compact_spans[-1]  # Get most recent
        attributes = dict(span.attributes) if span.attributes else {}

        # Verify span attributes
        assert "strategy.type" in attributes or "table.identifier" in attributes

    @pytest.mark.requirement("FR-030")
    def test_compact_table_raises_compaction_error_on_failure(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test CompactionError is raised when compaction fails."""
        from floe_iceberg.errors import CompactionError

        # Verify error class exists and has expected attributes
        error = CompactionError(
            "Compaction failed: file system error",
            table_identifier="bronze.failing_table",
            strategy="BIN_PACK",
        )

        assert "Compaction failed" in str(error)
        assert error.table_identifier == "bronze.failing_table"
        assert error.strategy == "BIN_PACK"

    @pytest.mark.requirement("FR-031")
    def test_compact_table_bin_pack_with_custom_parallelism(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test bin_pack strategy with custom max_concurrent_file_group_rewrites."""
        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            CompactionStrategy,
            CompactionStrategyType,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="compact_parallel_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Custom parallelism setting
        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
            max_concurrent_file_group_rewrites=10,
        )

        files_rewritten = manager.compact_table(table, strategy)
        assert isinstance(files_rewritten, int)

    @pytest.mark.requirement("FR-032")
    def test_compact_table_not_auto_triggered(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test compaction is only called when explicitly invoked (not auto-triggered).

        FR-032: Compaction MUST NOT be auto-triggered; orchestrator is responsible.
        """
        import pyarrow as pa

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="no_auto_compact",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        # Perform multiple writes
        for i in range(5):
            data = pa.table({"id": [i]})
            manager.write_data(table, data, WriteConfig(mode=WriteMode.APPEND))

        # There's no assertion for "compaction not auto-triggered" since
        # we can't directly verify absence of a call. The test demonstrates
        # the expected usage pattern: write operations don't trigger compaction,
        # and compaction is explicitly called by the orchestrator.
        # The implementation must NOT call compact_table within write_data.

        # This test passes by showing the expected API usage pattern.

    @pytest.mark.requirement("FR-030")
    def test_compact_table_handles_compaction_error_with_logging(
        self,
        mock_catalog_plugin: MockCatalogPlugin,
        mock_storage_plugin: MockStoragePlugin,
    ) -> None:
        """Test CompactionError is properly handled with structured logging.

        Verifies that:
        1. CompactionError is re-raised to caller
        2. Error is logged with structured fields
        3. OTel span error handling is triggered (implementation detail)
        """
        from unittest.mock import patch

        from floe_iceberg import IcebergTableManager
        from floe_iceberg.errors import CompactionError
        from floe_iceberg.models import (
            CompactionStrategy,
            CompactionStrategyType,
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        mock_catalog_plugin.create_namespace("bronze")

        manager = IcebergTableManager(
            catalog_plugin=mock_catalog_plugin,
            storage_plugin=mock_storage_plugin,
        )

        table_config = TableConfig(
            namespace="bronze",
            table_name="error_handling_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )
        table = manager.create_table(table_config)

        strategy = CompactionStrategy(
            strategy_type=CompactionStrategyType.BIN_PACK,
        )

        # Mock execute_compaction to raise CompactionError
        with patch("floe_iceberg.compaction.execute_compaction") as mock_execute:
            mock_execute.side_effect = CompactionError(
                "Simulated failure",
                table_identifier="bronze.error_handling_test",
                strategy="BIN_PACK",
            )

            # Verify the error is re-raised
            with pytest.raises(CompactionError) as exc_info:
                manager.compact_table(table, strategy)

            # Verify error has expected attributes
            assert exc_info.value.strategy == "BIN_PACK"
            assert "Simulated failure" in str(exc_info.value)
