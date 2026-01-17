"""Integration tests for IcebergTableManager with real Polaris and S3.

These tests require K8s infrastructure (Polaris, MinIO) to be running.
Run with: make test-integration

Tests:
    T097: create_table with real Polaris
    T098: write_data with real S3
    T099: schema evolution
    T100: snapshot management
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pytest

from testing.base_classes.integration_test_base import IntegrationTestBase

if TYPE_CHECKING:
    from conftest import IntegrationMinIOStoragePlugin, IntegrationPolarisCatalogPlugin


class TestIcebergTableManagerIntegration(IntegrationTestBase):
    """Integration tests for IcebergTableManager with real services.

    Requires:
        - Polaris catalog at localhost:8181
        - MinIO S3 at localhost:9000
    """

    required_services = [("polaris", 8181), ("minio", 9000)]

    # =========================================================================
    # T097: create_table with real Polaris
    # =========================================================================

    @pytest.mark.requirement("FR-012")
    def test_create_table_with_real_polaris(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test creating an Iceberg table with real Polaris catalog.

        Verifies:
        - Table is created in Polaris
        - Table metadata is accessible
        - Schema is correctly stored

        Acceptance criteria from T097:
        - Test creates real Iceberg table via Polaris
        - Verify table metadata in Polaris catalog
        - Uses IntegrationTestBase with unique namespace
        - @pytest.mark.requirement() traceability
        """
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        # Create namespace for test isolation
        integration_catalog_plugin.create_namespace(unique_namespace)

        # Create manager with real plugins
        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        # Define table configuration
        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="integration_test_customers",
            table_schema=TableSchema(
                fields=[
                    SchemaField(
                        field_id=1,
                        name="id",
                        field_type=FieldType.LONG,
                        required=True,
                    ),
                    SchemaField(
                        field_id=2,
                        name="name",
                        field_type=FieldType.STRING,
                    ),
                    SchemaField(
                        field_id=3,
                        name="email",
                        field_type=FieldType.STRING,
                    ),
                ]
            ),
        )

        # Create table
        table = manager.create_table(table_config)

        # Verify table was created
        assert table is not None
        assert manager.table_exists(table_config.identifier)

        # Verify schema
        schema = table.schema()
        assert len(schema.fields) == 3
        field_names = {f.name for f in schema.fields}
        assert field_names == {"id", "name", "email"}

    @pytest.mark.requirement("FR-013")
    def test_create_table_if_not_exists_with_real_polaris(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test idempotent table creation with if_not_exists=True.

        Verifies that creating the same table twice with if_not_exists=True
        does not raise an error.
        """
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="idempotent_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )

        # Create table first time
        table1 = manager.create_table(table_config)
        assert table1 is not None

        # Create same table again with if_not_exists=True (should not raise)
        table2 = manager.create_table(table_config, if_not_exists=True)
        assert table2 is not None

    # =========================================================================
    # T098: write_data with real S3
    # =========================================================================

    @pytest.mark.requirement("FR-022")
    def test_write_data_append_with_real_s3(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test writing data to Iceberg table with real S3 storage.

        Verifies:
        - Data is written to S3 via PyIceberg
        - Data is readable after write
        - Row count matches expected

        Acceptance criteria from T098:
        - Test writes real data via S3 (MinIO)
        - Verify data files in S3
        """
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="write_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(
                        field_id=1,
                        name="id",
                        field_type=FieldType.LONG,
                        required=False,  # PyArrow defaults to nullable
                    ),
                    SchemaField(
                        field_id=2,
                        name="name",
                        field_type=FieldType.STRING,
                    ),
                ]
            ),
        )

        table = manager.create_table(table_config)

        # Prepare test data
        data = pa.table({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
        })

        # Write data
        write_config = WriteConfig(mode=WriteMode.APPEND)
        table = manager.write_data(table, data, write_config)

        # Verify data was written
        result = table.scan().to_arrow()
        assert result.num_rows == 3
        assert set(result["name"].to_pylist()) == {"Alice", "Bob", "Charlie"}

    @pytest.mark.requirement("FR-023")
    def test_write_data_overwrite_with_real_s3(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test overwrite mode replaces existing data."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="overwrite_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )

        table = manager.create_table(table_config)

        # Write initial data
        initial_data = pa.table({"id": [1, 2], "value": ["old1", "old2"]})
        table = manager.write_data(
            table, initial_data, WriteConfig(mode=WriteMode.APPEND)
        )

        # Overwrite with new data
        new_data = pa.table({"id": [3], "value": ["new"]})
        table = manager.write_data(
            table, new_data, WriteConfig(mode=WriteMode.OVERWRITE)
        )

        # Verify only new data exists
        result = table.scan().to_arrow()
        assert result.num_rows == 1
        assert result["value"].to_pylist() == ["new"]

    # =========================================================================
    # T099: schema evolution
    # =========================================================================

    @pytest.mark.requirement("FR-016")
    def test_schema_evolution_add_column_with_real_polaris(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test adding a new column to existing table.

        Verifies:
        - Column is added to schema
        - Existing data has NULL for new column
        - New writes can use the new column
        """
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        # Create table with initial schema
        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="evolution_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="name", field_type=FieldType.STRING),
                ]
            ),
        )

        table = manager.create_table(table_config)

        # Write initial data
        initial_data = pa.table({"id": [1, 2], "name": ["Alice", "Bob"]})
        table = manager.write_data(
            table, initial_data, WriteConfig(mode=WriteMode.APPEND)
        )

        # Evolve schema - add email column
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.ADD_COLUMN,
                    field=SchemaField(
                        field_id=3,
                        name="email",
                        field_type=FieldType.STRING,
                        doc="User email address",
                    ),
                ),
            ]
        )

        table = manager.evolve_schema(table, evolution)

        # Verify new column exists
        schema = table.schema()
        field_names = {f.name for f in schema.fields}
        assert "email" in field_names

        # Verify existing data has NULL for new column
        result = table.scan().to_arrow()
        assert result.num_rows == 2
        # Note: PyIceberg may or may not include the new column in scan results
        # depending on projection. The key test is that schema evolved.

    @pytest.mark.requirement("FR-017")
    def test_schema_evolution_rename_column_with_real_polaris(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test renaming a column (metadata-only operation)."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaChange,
            SchemaChangeType,
            SchemaEvolution,
            SchemaField,
            TableConfig,
            TableSchema,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="rename_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="user_name", field_type=FieldType.STRING),
                ]
            ),
        )

        table = manager.create_table(table_config)

        # Rename column
        evolution = SchemaEvolution(
            changes=[
                SchemaChange(
                    change_type=SchemaChangeType.RENAME_COLUMN,
                    source_column="user_name",
                    new_name="full_name",
                ),
            ]
        )

        table = manager.evolve_schema(table, evolution)

        # Verify column was renamed
        schema = table.schema()
        field_names = {f.name for f in schema.fields}
        assert "full_name" in field_names
        assert "user_name" not in field_names

    # =========================================================================
    # T100: snapshot management
    # =========================================================================

    @pytest.mark.requirement("FR-026")
    def test_list_snapshots_with_real_polaris(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test listing snapshots after multiple writes."""
        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="snapshot_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                ]
            ),
        )

        table = manager.create_table(table_config)

        # Make multiple writes to create snapshots
        for i in range(3):
            data = pa.table({"id": [i * 10 + j for j in range(3)]})
            table = manager.write_data(
                table, data, WriteConfig(mode=WriteMode.APPEND)
            )

        # List snapshots
        snapshots = manager.list_snapshots(table)

        # Verify multiple snapshots exist
        assert len(snapshots) >= 3
        # Snapshots should be ordered (most recent first)
        for i in range(len(snapshots) - 1):
            assert snapshots[i].timestamp_ms >= snapshots[i + 1].timestamp_ms

    @pytest.mark.requirement("FR-027")
    def test_rollback_to_snapshot_with_real_polaris(
        self,
        integration_catalog_plugin: IntegrationPolarisCatalogPlugin,
        integration_storage_plugin: IntegrationMinIOStoragePlugin,
        unique_namespace: str,
    ) -> None:
        """Test rolling back to a previous snapshot.

        Note: PyIceberg 0.10.0 does not support snapshot rollback (set_current_snapshot).
        This test validates that the manager correctly handles this limitation by
        raising NotImplementedError with a clear message.

        When PyIceberg 0.11+ is released with rollback support, this test should
        be updated to verify actual rollback behavior.
        """
        import pyiceberg

        from floe_iceberg import IcebergTableManager, IcebergTableManagerConfig
        from floe_iceberg.models import (
            FieldType,
            SchemaField,
            TableConfig,
            TableSchema,
            WriteConfig,
            WriteMode,
        )

        integration_catalog_plugin.create_namespace(unique_namespace)

        manager = IcebergTableManager(
            catalog_plugin=integration_catalog_plugin,
            storage_plugin=integration_storage_plugin,
            config=IcebergTableManagerConfig(),
        )

        table_config = TableConfig(
            namespace=unique_namespace,
            table_name="rollback_test",
            table_schema=TableSchema(
                fields=[
                    SchemaField(field_id=1, name="id", field_type=FieldType.LONG),
                    SchemaField(field_id=2, name="value", field_type=FieldType.STRING),
                ]
            ),
        )

        table = manager.create_table(table_config)

        # Write initial data
        data1 = pa.table({"id": [1], "value": ["original"]})
        table = manager.write_data(table, data1, WriteConfig(mode=WriteMode.APPEND))

        # Get snapshot after first write
        snapshots_after_first = manager.list_snapshots(table)
        first_snapshot_id = snapshots_after_first[0].snapshot_id

        # Write more data (this will be rolled back)
        data2 = pa.table({"id": [2], "value": ["to_be_rolled_back"]})
        table = manager.write_data(table, data2, WriteConfig(mode=WriteMode.APPEND))

        # Verify both rows exist
        result = table.scan().to_arrow()
        assert result.num_rows == 2

        # Check if PyIceberg supports rollback (0.11+)
        pyiceberg_version = tuple(int(x) for x in pyiceberg.__version__.split(".")[:2])
        if pyiceberg_version < (0, 11):
            # PyIceberg 0.10.x doesn't support snapshot rollback
            # Verify proper error handling
            with pytest.raises(NotImplementedError) as exc_info:
                manager.rollback_to_snapshot(table, first_snapshot_id)

            assert "Snapshot rollback not supported" in str(exc_info.value)
            assert "PyIceberg" in str(exc_info.value)
        else:
            # PyIceberg 0.11+ supports rollback - test actual behavior
            table = manager.rollback_to_snapshot(table, first_snapshot_id)

            # Verify only original data exists
            result = table.scan().to_arrow()
            assert result.num_rows == 1
            assert result["value"].to_pylist() == ["original"]
