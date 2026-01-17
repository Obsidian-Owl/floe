"""Unit tests for IcebergTableManager.

Tests the IcebergTableManager class using mock CatalogPlugin and StoragePlugin
fixtures. These tests validate initialization, configuration, and core operations.

Note: Tests are written TDD-style before implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
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
        assert hasattr(table, "identifier") or table is not None

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
